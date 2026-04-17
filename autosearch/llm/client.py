# Self-written, plan v2.3 § 1 decision 15
import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar, cast

import httpx
import structlog
from pydantic import BaseModel

from autosearch.observability.cost import CostTracker, estimate_tokens
from autosearch.llm.providers.anthropic import AnthropicProvider
from autosearch.llm.providers.claude_code import ClaudeCodeProvider
from autosearch.llm.providers.dummy import DummyProvider
from autosearch.llm.providers.gemini import GeminiProvider
from autosearch.llm.providers.openai import OpenAIProvider

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class AllProvidersFailedError(RuntimeError):
    def __init__(self, provider_errors: Mapping[str, Exception]) -> None:
        self.provider_errors = dict(provider_errors)
        details = "; ".join(
            f"{provider}: {type(error).__name__}: {error}"
            for provider, error in self.provider_errors.items()
        )
        super().__init__(f"All configured LLM providers failed: {details}")


class ProviderProtocol(Protocol):
    name: str

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str: ...


class LLMClient:
    """Auto-detect an available provider.

    Set `AUTOSEARCH_LLM_MODE=dummy` to force the in-repo `DummyProvider` for smoke tests,
    CI, or local development without API keys.
    """

    def __init__(
        self,
        provider_name: str | None = None,
        provider_chain: list[str] | None = None,
        providers: Mapping[str, ProviderProtocol] | None = None,
        cost_tracker: CostTracker | None = None,
        max_parse_retries: int = 3,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="llm_client")
        self.cost_tracker = cost_tracker
        self.max_parse_retries = max_parse_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.providers = dict(providers) if providers is not None else self._detect_providers()
        if not self.providers:
            raise RuntimeError(
                "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "GOOGLE_API_KEY, or install the `claude` CLI."
            )

        preferred_provider = provider_name or os.getenv("AUTOSEARCH_LLM_PROVIDER")
        if preferred_provider is not None and preferred_provider not in self.providers:
            raise ValueError(f"Unknown provider: {preferred_provider}")

        self.provider_chain = self._resolve_provider_chain(
            preferred_provider=preferred_provider,
            provider_chain=provider_chain,
        )
        self.fallback_count = 0
        self._provider_index = 0
        self.provider_name = ""
        self.provider: ProviderProtocol
        self._set_active_provider(0)
        self.logger.info(
            "llm_provider_selected",
            provider=self.provider_name,
            available_providers=list(self.providers),
            provider_chain=self.provider_chain,
        )

    def _detect_providers(self) -> dict[str, ProviderProtocol]:
        if os.environ.get("AUTOSEARCH_LLM_MODE") == "dummy":
            self.logger.info(
                "llm_provider_forced",
                provider="dummy",
                reason="AUTOSEARCH_LLM_MODE=dummy",
            )
            return {"dummy": DummyProvider()}

        providers: dict[str, ProviderProtocol] = {}

        if ClaudeCodeProvider.is_available():
            providers["claude_code"] = ClaudeCodeProvider()
        else:
            self.logger.info(
                "llm_provider_disabled",
                provider="claude_code",
                reason="`claude` binary not found on PATH",
            )

        if os.getenv("ANTHROPIC_API_KEY"):
            providers["anthropic"] = AnthropicProvider()

        if os.getenv("OPENAI_API_KEY"):
            providers["openai"] = OpenAIProvider()

        if os.getenv("GOOGLE_API_KEY"):
            providers["gemini"] = GeminiProvider()

        self.logger.info("llm_providers_detected", providers=list(providers))
        return providers

    @staticmethod
    def _strip_code_fences(raw: str) -> str:
        stripped = raw.strip()
        first_line, separator, remainder = stripped.partition("\n")
        if first_line.startswith("```") and separator:
            stripped = remainder
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        return stripped.strip()

    async def complete(self, prompt: str, response_model: type[ResponseModelT]) -> ResponseModelT:
        provider_errors: dict[str, Exception] = {}
        while True:
            provider_name = self.provider_name
            provider = self.provider
            try:
                return await self._complete_with_parse_retries(
                    provider_name=provider_name,
                    provider=provider,
                    prompt=prompt,
                    response_model=response_model,
                )
            except Exception as exc:
                if not self._should_fallback(exc):
                    raise

                provider_errors[provider_name] = exc
                next_provider_index = self._provider_index + 1
                if next_provider_index >= len(self.provider_chain):
                    raise AllProvidersFailedError(provider_errors) from exc

                next_provider_name = self.provider_chain[next_provider_index]
                self.logger.warning(
                    "llm_provider_fallback",
                    from_provider=provider_name,
                    to_provider=next_provider_name,
                    error=str(exc),
                )
                self.fallback_count += 1
                self._set_active_provider(next_provider_index)

    async def _complete_with_parse_retries(
        self,
        *,
        provider_name: str,
        provider: ProviderProtocol,
        prompt: str,
        response_model: type[ResponseModelT],
    ) -> ResponseModelT:
        for attempt in range(1, self.max_parse_retries + 1):
            raw_response = await provider.complete(prompt, response_model)
            raw_json = raw_response if isinstance(raw_response, str) else json.dumps(raw_response)
            raw_json = self._strip_code_fences(raw_json)
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                self.logger.warning(
                    "llm_json_parse_failed",
                    provider=provider_name,
                    attempt=attempt,
                    max_attempts=self.max_parse_retries,
                    error=str(exc),
                )
                if attempt == self.max_parse_retries:
                    raise
                await asyncio.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
                continue

            result = response_model.model_validate(payload)
            if self.cost_tracker is not None:
                self.cost_tracker.add_usage(
                    model=self._cost_model_name(provider_name=provider_name, provider=provider),
                    input_tokens=estimate_tokens(prompt),
                    output_tokens=estimate_tokens(raw_json),
                    note=f"served_by_provider={provider_name}",
                )
            self.logger.info(
                "llm_completion_validated",
                provider=provider_name,
                response_model=response_model.__name__,
            )
            return cast(ResponseModelT, result)

        raise RuntimeError("LLM completion exhausted retries without returning valid JSON.")

    def _cost_model_name(
        self,
        *,
        provider_name: str,
        provider: ProviderProtocol,
    ) -> str:
        model_name = getattr(provider, "model", None)
        if isinstance(model_name, str) and model_name:
            return model_name
        return provider_name

    def _resolve_provider_chain(
        self,
        *,
        preferred_provider: str | None,
        provider_chain: Sequence[str] | None,
    ) -> list[str]:
        env_chain = self._provider_chain_from_env() if provider_chain is None else []
        configured_chain = provider_chain if provider_chain is not None else env_chain
        chain = self._normalize_provider_chain(
            configured_chain,
            strict=provider_chain is not None,
        )
        if preferred_provider is None:
            return chain

        return [preferred_provider, *[name for name in chain if name != preferred_provider]]

    def _normalize_provider_chain(
        self,
        chain: Sequence[str],
        *,
        strict: bool,
    ) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for raw_name in chain:
            provider_name = raw_name.strip()
            if not provider_name or provider_name in seen:
                continue
            if provider_name not in self.providers:
                if strict:
                    raise ValueError(f"Unknown provider in chain: {provider_name}")
                continue
            ordered.append(provider_name)
            seen.add(provider_name)

        for provider_name in self.providers:
            if provider_name not in seen:
                ordered.append(provider_name)
        return ordered

    def _provider_chain_from_env(self) -> list[str]:
        env_value = os.getenv("AUTOSEARCH_PROVIDER_CHAIN", "")
        if not env_value:
            return []
        return env_value.split(",")

    def _set_active_provider(self, provider_index: int) -> None:
        provider_name = self.provider_chain[provider_index]
        self._provider_index = provider_index
        self.provider_name = provider_name
        self.provider = self.providers[provider_name]

    @staticmethod
    def _should_fallback(error: Exception) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            return status_code == 429 or status_code >= 500
        return isinstance(error, httpx.HTTPError)
