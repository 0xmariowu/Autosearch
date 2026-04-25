# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

import importlib.util
import inspect
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, NoReturn, Protocol, Self

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.core.rate_limiter import RateLimiter
from autosearch.skills.loader import MethodSpec, QualityHint, WhenToUse, load_all

if TYPE_CHECKING:
    from autosearch.observability.channel_health import ChannelHealth

LOGGER = structlog.get_logger(__name__).bind(component="channel_registry")
_TIKHUB_API_KEY_TOKEN = "env:TIKHUB_API_KEY"
_TIKHUB_PROXY_FALLBACK = {"AUTOSEARCH_PROXY_URL", "AUTOSEARCH_PROXY_TOKEN"}


class ChannelRegistryError(ValueError):
    """Raised when a channel skill cannot be compiled into a runtime channel."""


class MethodUnavailable(Exception):
    """Raised when a method is unavailable in the current environment."""


class RateLimited(Exception):
    """Raised when a channel method hits a retryable rate limit."""


class TransientError(Exception):
    """Raised when a channel method fails in a retryable way."""


class PermanentError(Exception):
    """Raised when a channel method fails in a non-retryable way."""


class ChannelAuthError(PermanentError):
    """Raised when an upstream rejects the request as unauthenticated /
    unauthorized (HTTP 401 / 403, expired cookie, missing API key the
    channel forgot to declare). Distinct from a quiet `[]` result so the
    host agent can surface "your key looks invalid" instead of
    "no matches" (Bug 1 / fix-plan)."""


class BudgetExhausted(PermanentError):
    """Raised when an upstream rejects the request because the caller's paid
    quota / wallet is empty (TikHub 402, OpenAI insufficient_quota, etc).
    Distinct from RateLimited because the fix is "top up balance", not
    "wait and retry" (Bug 3 / fix-plan v8 follow-up)."""


def raise_as_channel_error(exc: BaseException) -> NoReturn:
    """Translate a generic transport/parsing exception into the typed
    channels.base error the MCP boundary expects.

    Bug 1 (fix-plan): channel methods used to swallow errors with
    `except Exception: return []`. That conflates "search returned nothing"
    with "401" / "429" / "schema changed" / "network died". This helper is
    the standard adapter — call it from a channel's broad except block to
    propagate the failure as a typed exception the MCP layer can route to
    the right `run_channel` status (auth_failed / rate_limited / channel_error).
    """
    if isinstance(exc, (ChannelAuthError, RateLimited, TransientError, PermanentError)):
        raise exc

    try:
        import httpx  # noqa: PLC0415

        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            status = exc.response.status_code
            if status in (401, 403):
                raise ChannelAuthError(str(exc)) from exc
            if status == 429:
                raise RateLimited(str(exc)) from exc
            if 500 <= status < 600:
                raise TransientError(str(exc)) from exc
            raise PermanentError(str(exc)) from exc
        if isinstance(exc, httpx.HTTPError):  # network / timeout / connect
            raise TransientError(str(exc)) from exc
    except ImportError:  # pragma: no cover — httpx is a runtime dep
        pass

    if isinstance(exc, ValueError):
        raise PermanentError(str(exc)) from exc
    raise TransientError(str(exc)) from exc


@dataclass(slots=True)
class Environment:
    """Runtime probe result: what credentials/servers/binaries are available."""

    cookies: set[str] = field(default_factory=set)
    mcp_servers: set[str] = field(default_factory=set)
    env_keys: set[str] = field(default_factory=set)
    binaries: set[str] = field(default_factory=set)


@dataclass(slots=True)
class CompiledMethod:
    """One method of a channel, compiled from SKILL.md + imported from methods/*.py."""

    id: str
    skill_method: MethodSpec
    callable: Callable[..., Awaitable[list[Evidence]]]
    available: bool
    unmet_requires: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChannelMetadata:
    """Compiled from SKILL.md frontmatter — runtime view."""

    name: str
    description: str
    languages: list[str]
    when_to_use: WhenToUse | None
    quality_hint: QualityHint | None
    layer: str | None
    domains: list[str]
    scenarios: list[str]
    model_tier: str | None
    tier: int | None
    fix_hint: str | None
    methods: list[CompiledMethod]
    fallback_chain: list[str]

    def available_methods(self) -> list[CompiledMethod]:
        return [method for method in self.methods if method.available]


class Channel(Protocol):
    name: str
    languages: list[str]

    async def search(self, query: SubQuery) -> list[Evidence]: ...


class _CompiledChannel:
    def __init__(
        self,
        metadata: ChannelMetadata,
        health_provider: Callable[[], ChannelHealth | None],
        limiter_provider: Callable[[], RateLimiter | None] | None = None,
    ) -> None:
        self.name = metadata.name
        self.languages = list(metadata.languages)
        self._metadata = metadata
        self._health_provider = health_provider
        self._limiter_provider = limiter_provider or (lambda: None)
        self._methods_by_id = {method.id: method for method in metadata.methods}

    async def search(self, query: SubQuery) -> list[Evidence]:
        last_retryable: Exception | None = None
        attempted = False
        method_ids = self._metadata.fallback_chain or [
            method.id for method in self._metadata.methods
        ]

        for method_id in method_ids:
            method = self._methods_by_id[method_id]
            if not method.available:
                continue

            health = self._health_provider()
            if health is not None and health.is_in_cooldown(self.name, method.id):
                continue

            # Rate limit check (per-method declared in SKILL.md).
            limiter = self._limiter_provider()
            rate_limit_meta = method.skill_method.rate_limit or {}
            per_min = rate_limit_meta.get("per_min") if isinstance(rate_limit_meta, dict) else None
            per_hour = (
                rate_limit_meta.get("per_hour") if isinstance(rate_limit_meta, dict) else None
            )
            if limiter is not None and (per_min or per_hour):
                allowed, retry_after = limiter.acquire(
                    self.name,
                    method.id,
                    per_min=int(per_min) if per_min else None,
                    per_hour=int(per_hour) if per_hour else None,
                )
                if not allowed:
                    last_retryable = RateLimited(
                        f"rate_limited: {self.name}.{method.id} retry_after={retry_after:.1f}s"
                    )
                    continue

            attempted = True
            started_at = time.monotonic()
            try:
                results = await method.callable(query)
            except (MethodUnavailable, RateLimited, TransientError) as exc:
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(exc).__name__,
                )
                last_retryable = exc
                continue
            except ChannelAuthError as exc:
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(exc).__name__,
                )
                last_retryable = exc
                continue
            except PermanentError as exc:
                # Must come before the bare-Exception clause below; previously this
                # handler was unreachable because Exception caught it first.
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(exc).__name__,
                )
                raise
            except Exception as _budget_exc:  # noqa: BLE001
                # Check if it's TikhubBudgetExhausted — treat as rate-limited, fall through
                if type(_budget_exc).__name__ == "TikhubBudgetExhausted":
                    LOGGER.warning(
                        "channel_budget_exhausted",
                        channel=self.name,
                        method=method_id,
                        reason=str(_budget_exc)[:120],
                    )
                    self._record_health(
                        method=method.id,
                        success=False,
                        started_at=started_at,
                        error="TikhubBudgetExhausted",
                    )
                    last_retryable = _budget_exc
                    continue
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(_budget_exc).__name__,
                )
                raise

            self._record_health(method=method.id, success=True, started_at=started_at)
            return results

        if last_retryable is not None:
            raise last_retryable

        if not attempted:
            raise MethodUnavailable(f"Channel '{self.name}' has no available search methods")

        raise MethodUnavailable(f"Channel '{self.name}' exhausted all fallback methods")

    def _record_health(
        self,
        *,
        method: str,
        success: bool,
        started_at: float,
        error: str | None = None,
    ) -> None:
        health = self._health_provider()
        if health is None:
            return

        latency_ms = (time.monotonic() - started_at) * 1000
        health.record(
            self.name,
            method,
            success=success,
            latency_ms=latency_ms,
            error=error,
        )


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._metadata: dict[str, ChannelMetadata] = {}
        self._health: ChannelHealth | None = None
        self._limiter: RateLimiter | None = None

    @classmethod
    def compile_from_skills(
        cls,
        channels_root: Path,
        env: Environment,
        *,
        log_missing_impls: bool = True,
    ) -> Self:
        registry = cls()
        for skill in load_all(channels_root):
            methods = [
                cls._compile_method(
                    channel_name=skill.name,
                    skill_dir=skill.skill_dir,
                    method=method,
                    env=env,
                    log_missing_impls=log_missing_impls,
                )
                for method in skill.methods
            ]
            metadata = ChannelMetadata(
                name=skill.name,
                description=skill.description,
                languages=list(skill.languages),
                when_to_use=skill.when_to_use,
                quality_hint=skill.quality_hint,
                layer=skill.layer,
                domains=list(skill.domains),
                scenarios=list(skill.scenarios),
                model_tier=skill.model_tier,
                tier=skill.tier,
                fix_hint=skill.fix_hint,
                methods=methods,
                fallback_chain=list(skill.fallback_chain),
            )
            registry._metadata[skill.name] = metadata
            registry.register(
                _CompiledChannel(
                    metadata,
                    lambda: registry._health,
                    lambda: registry._limiter,
                )
            )

        return registry

    @staticmethod
    def _compile_method(
        *,
        channel_name: str,
        skill_dir: Path,
        method: MethodSpec,
        env: Environment,
        log_missing_impls: bool,
    ) -> CompiledMethod:
        impl_path = skill_dir / method.impl
        if not impl_path.is_file():
            if log_missing_impls:
                LOGGER.debug(
                    "channel_method_impl_missing",
                    channel=channel_name,
                    method=method.id,
                    impl=str(impl_path),
                )
            return CompiledMethod(
                id=method.id,
                skill_method=method,
                callable=_build_missing_impl_stub(channel_name, method.id, impl_path),
                available=False,
                unmet_requires=["impl_missing"],
            )

        search_callable = ChannelRegistry._load_search_callable(
            channel_name=channel_name,
            method_id=method.id,
            impl_path=impl_path,
        )
        unmet_requires = ChannelRegistry._resolve_requires(method.requires, env)
        return CompiledMethod(
            id=method.id,
            skill_method=method,
            callable=search_callable,
            available=not unmet_requires,
            unmet_requires=unmet_requires,
        )

    @staticmethod
    def _load_search_callable(
        *,
        channel_name: str,
        method_id: str,
        impl_path: Path,
    ) -> Callable[..., Awaitable[list[Evidence]]]:
        module_name = f"autosearch_skill_{channel_name}_{method_id}"
        spec = importlib.util.spec_from_file_location(module_name, impl_path)
        if spec is None or spec.loader is None:
            raise ChannelRegistryError(
                f"Failed to create import spec for channel '{channel_name}' "
                f"method '{method_id}' from {impl_path}"
            )

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ChannelRegistryError(
                f"Failed to import channel '{channel_name}' method '{method_id}' "
                f"from {impl_path}: {exc}"
            ) from exc

        search_callable = getattr(module, "search", None)
        if not callable(search_callable) or not inspect.iscoroutinefunction(search_callable):
            raise ChannelRegistryError(
                f"Channel '{channel_name}' method '{method_id}' must export "
                "an async callable named 'search'"
            )

        return search_callable

    @staticmethod
    def _resolve_requires(requires: list[str], env: Environment) -> list[str]:
        unmet: list[str] = []
        for token in requires:
            kind, value = token.split(":", maxsplit=1)
            if kind == "cookie" and value not in env.cookies:
                unmet.append(token)
            elif kind == "mcp" and value not in env.mcp_servers:
                unmet.append(token)
            elif kind == "env" and value not in env.env_keys:
                if token == _TIKHUB_API_KEY_TOKEN and _TIKHUB_PROXY_FALLBACK.issubset(env.env_keys):
                    continue
                unmet.append(token)
            elif kind == "binary" and value not in env.binaries:
                unmet.append(token)

        return unmet

    def register(self, channel: Channel) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> Channel:
        return self._channels[name]

    def all_channels(self) -> list[Channel]:
        return list(self._channels.values())

    def available(self) -> list[Channel]:
        available_channels: list[Channel] = []
        for channel in self._channels.values():
            metadata = self._metadata.get(channel.name)
            if metadata is None:
                if self._health is None or not self._health.is_in_cooldown(channel.name):
                    available_channels.append(channel)
                continue

            if not metadata.available_methods():
                continue

            if self._health is not None and self._health.is_in_cooldown(channel.name):
                continue

            available_channels.append(channel)

        return available_channels

    def metadata(self, name: str) -> ChannelMetadata:
        return self._metadata[name]

    def attach_health(self, health: ChannelHealth) -> None:
        self._health = health

    def attach_limiter(self, limiter: RateLimiter) -> None:
        self._limiter = limiter


def _build_missing_impl_stub(
    channel_name: str,
    method_id: str,
    impl_path: Path,
) -> Callable[[SubQuery], Awaitable[list[Evidence]]]:
    async def _search(_: SubQuery) -> list[Evidence]:
        raise NotImplementedError(
            f"Channel '{channel_name}' method '{method_id}' is missing its implementation "
            f"at {impl_path}"
        )

    return _search
