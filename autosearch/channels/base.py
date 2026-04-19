# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

import importlib.util
import inspect
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Protocol, Self

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.skills.loader import MethodSpec, QualityHint, WhenToUse, load_all

if TYPE_CHECKING:
    from autosearch.observability.channel_health import ChannelHealth

LOGGER = structlog.get_logger(__name__).bind(component="channel_registry")


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
    methods: list[CompiledMethod]
    fallback_chain: list[str]

    def available_methods(self) -> list[CompiledMethod]:
        return [method for method in self.methods if method.available]


class Channel(Protocol):
    name: str

    async def search(self, query: SubQuery) -> list[Evidence]: ...


class _CompiledChannel:
    def __init__(
        self,
        metadata: ChannelMetadata,
        health_provider: Callable[[], ChannelHealth | None],
    ) -> None:
        self.name = metadata.name
        self._metadata = metadata
        self._health_provider = health_provider
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
            except PermanentError as exc:
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(exc).__name__,
                )
                raise
            except Exception as exc:
                self._record_health(
                    method=method.id,
                    success=False,
                    started_at=started_at,
                    error=type(exc).__name__,
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
                methods=methods,
                fallback_chain=list(skill.fallback_chain),
            )
            registry._metadata[skill.name] = metadata
            registry.register(_CompiledChannel(metadata, lambda: registry._health))

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
                LOGGER.info(
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
