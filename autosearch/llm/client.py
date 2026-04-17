# Self-written, plan v2.3 § 1 decision 15
import asyncio
import json
import os
from collections.abc import Mapping
from typing import Protocol, TypeVar, cast

import structlog
from pydantic import BaseModel

from autosearch.llm.providers.anthropic import AnthropicProvider
from autosearch.llm.providers.claude_code import ClaudeCodeProvider
from autosearch.llm.providers.gemini import GeminiProvider
from autosearch.llm.providers.openai import OpenAIProvider

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class ProviderProtocol(Protocol):
    name: str

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        ...


class LLMClient:
    def __init__(
        self,
        provider_name: str | None = None,
        providers: Mapping[str, ProviderProtocol] | None = None,
        max_parse_retries: int = 3,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="llm_client")
        self.max_parse_retries = max_parse_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.providers = dict(providers) if providers is not None else self._detect_providers()
        if not self.providers:
            raise RuntimeError(
                "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "GOOGLE_API_KEY, or install the `claude` CLI."
            )

        preferred_provider = provider_name or os.getenv("AUTOSEARCH_LLM_PROVIDER")
        self.provider_name = preferred_provider or next(iter(self.providers))
        if self.provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {self.provider_name}")

        self.provider = self.providers[self.provider_name]
        self.logger.info(
            "llm_provider_selected",
            provider=self.provider_name,
            available_providers=list(self.providers),
        )

    def _detect_providers(self) -> dict[str, ProviderProtocol]:
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

    async def complete(
        self, prompt: str, response_model: type[ResponseModelT]
    ) -> ResponseModelT:
        for attempt in range(1, self.max_parse_retries + 1):
            raw_response = await self.provider.complete(prompt, response_model)
            raw_json = raw_response if isinstance(raw_response, str) else json.dumps(raw_response)
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                self.logger.warning(
                    "llm_json_parse_failed",
                    provider=self.provider_name,
                    attempt=attempt,
                    max_attempts=self.max_parse_retries,
                    error=str(exc),
                )
                if attempt == self.max_parse_retries:
                    raise
                await asyncio.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
                continue

            result = response_model.model_validate(payload)
            self.logger.info(
                "llm_completion_validated",
                provider=self.provider_name,
                response_model=response_model.__name__,
            )
            return cast(ResponseModelT, result)

        raise RuntimeError("LLM completion exhausted retries without returning valid JSON.")
