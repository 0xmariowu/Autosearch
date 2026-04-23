# Self-written for task F206 Wave G phase 1.
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import autosearch.cli.main as cli_main
from autosearch.channels.base import ChannelMetadata, CompiledMethod, Environment
from autosearch.cli.main import app
from autosearch.init.channel_status import infer_tier, summarize_registry
from autosearch.skills.loader import MethodSpec

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


async def _search_stub(*_: object) -> list[object]:
    return []


def _method(
    *,
    method_id: str,
    requires: list[str],
    available: bool,
    unmet_requires: list[str],
) -> CompiledMethod:
    return CompiledMethod(
        id=method_id,
        skill_method=MethodSpec(id=method_id, impl=f"methods/{method_id}.py", requires=requires),
        callable=_search_stub,
        available=available,
        unmet_requires=unmet_requires,
    )


def _metadata(name: str, *methods: CompiledMethod) -> ChannelMetadata:
    return ChannelMetadata(
        name=name,
        description=f"{name} description",
        languages=["en"],
        when_to_use=None,
        quality_hint=None,
        layer="leaf",
        domains=[],
        scenarios=[],
        model_tier="Fast",
        tier=None,
        fix_hint=None,
        methods=list(methods),
        fallback_chain=[method.id for method in methods],
    )


class _StubChannel:
    def __init__(self, name: str) -> None:
        self.name = name

    async def search(self, *_: object) -> list[object]:
        return []


class _StubRegistry:
    def __init__(self, metadata: dict[str, ChannelMetadata]) -> None:
        self._metadata = metadata

    def all_channels(self) -> list[_StubChannel]:
        return [_StubChannel(name) for name in sorted(self._metadata)]

    def metadata(self, name: str) -> ChannelMetadata:
        return self._metadata[name]


def test_infer_tier_t0_when_shipped_no_requires() -> None:
    metadata = _metadata(
        "ddgs",
        _method(method_id="text_search", requires=[], available=True, unmet_requires=[]),
    )

    assert infer_tier(metadata) == "t0"


def test_infer_tier_t1_when_tikhub_required() -> None:
    metadata = _metadata(
        "zhihu",
        _method(
            method_id="via_tikhub",
            requires=["env:TIKHUB_API_KEY"],
            available=False,
            unmet_requires=["env:TIKHUB_API_KEY"],
        ),
        _method(
            method_id="api_search",
            requires=[],
            available=False,
            unmet_requires=["impl_missing"],
        ),
    )

    assert infer_tier(metadata) == "t1"


def test_infer_tier_t1_when_env_required_not_tikhub() -> None:
    metadata = _metadata(
        "youtube",
        _method(
            method_id="data_api_search",
            requires=["env:YOUTUBE_API_KEY"],
            available=False,
            unmet_requires=["env:YOUTUBE_API_KEY"],
        ),
    )

    assert infer_tier(metadata) == "t1"


def test_infer_tier_t2_when_cookie_env_required() -> None:
    metadata = _metadata(
        "xueqiu",
        _method(
            method_id="api_search",
            requires=["env:XUEQIU_COOKIES"],
            available=False,
            unmet_requires=["env:XUEQIU_COOKIES"],
        ),
    )

    assert infer_tier(metadata) == "t2"


def test_infer_tier_prefers_declared_skill_tier() -> None:
    metadata = _metadata(
        "declared_login",
        _method(
            method_id="api_search",
            requires=["env:SERVICE_KEY"],
            available=False,
            unmet_requires=["env:SERVICE_KEY"],
        ),
    )
    metadata.tier = 2

    assert infer_tier(metadata) == "t2"


def test_infer_tier_scaffold_when_all_methods_impl_missing() -> None:
    metadata = _metadata(
        "future_channel",
        _method(
            method_id="planned",
            requires=[],
            available=False,
            unmet_requires=["impl_missing"],
        ),
    )

    assert infer_tier(metadata) == "scaffold"


def test_check_channels_command_groups_by_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _StubRegistry(
        {
            "always_on": _metadata(
                "always_on",
                _method(method_id="free", requires=[], available=True, unmet_requires=[]),
            ),
            "env_only": _metadata(
                "env_only",
                _method(
                    method_id="api",
                    requires=["env:YOUTUBE_API_KEY"],
                    available=False,
                    unmet_requires=["env:YOUTUBE_API_KEY"],
                ),
            ),
            "api_key_only": _metadata(
                "api_key_only",
                _method(
                    method_id="via_tikhub",
                    requires=["env:TIKHUB_API_KEY"],
                    available=False,
                    unmet_requires=["env:TIKHUB_API_KEY"],
                ),
            ),
            "future": _metadata(
                "future",
                _method(
                    method_id="planned",
                    requires=[],
                    available=False,
                    unmet_requires=["impl_missing"],
                ),
            ),
        }
    )

    monkeypatch.setattr(cli_main, "default_channels_root", lambda: Path("."))
    monkeypatch.setattr(cli_main, "probe_environment", lambda: Environment())
    monkeypatch.setattr(
        cli_main,
        "compile_channel_statuses",
        lambda channels_root, env: summarize_registry(registry),
    )

    result = runner.invoke(app, ["init", "--check-channels"])

    assert result.exit_code == 0
    assert "Tier 0 - always-on (1)" in result.stdout
    assert "Tier 1 - env/API gated (2)" in result.stdout
    assert "Scaffold-only (channel templates not shipped) (1)" in result.stdout
    assert "Total: 4 channels | 1 available | 2 blocked | 1 scaffold-only" in result.stdout


def test_check_channels_shows_available_vs_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _StubRegistry(
        {
            "github": _metadata(
                "github",
                _method(
                    method_id="search_public_repos",
                    requires=[],
                    available=True,
                    unmet_requires=[],
                ),
            ),
            "anthropic_feed": _metadata(
                "anthropic_feed",
                _method(
                    method_id="search",
                    requires=["env:ANTHROPIC_API_KEY"],
                    available=False,
                    unmet_requires=["env:ANTHROPIC_API_KEY"],
                ),
            ),
        }
    )

    monkeypatch.setattr(cli_main, "default_channels_root", lambda: Path("."))
    monkeypatch.setattr(cli_main, "probe_environment", lambda: Environment())
    monkeypatch.setattr(
        cli_main,
        "compile_channel_statuses",
        lambda channels_root, env: summarize_registry(registry),
    )

    result = runner.invoke(app, ["init", "--check-channels"])

    assert result.exit_code == 0
    assert "github            available" in result.stdout
    assert "anthropic_feed    blocked" in result.stdout
    assert "env:ANTHROPIC_API_KEY" in result.stdout
