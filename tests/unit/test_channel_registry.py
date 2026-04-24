# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from autosearch.channels.base import ChannelRegistry, Environment, MethodUnavailable
from autosearch.channels.demo import DemoChannel
from autosearch.core.models import Evidence, SubQuery
from autosearch.observability.channel_health import ChannelHealth


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "skills" / "channels"


def _write_channel_skill(
    root: Path,
    *,
    name: str,
    skill_text: str,
    methods: dict[str, str] | None = None,
) -> Path:
    skill_dir = root / name
    (skill_dir / "methods").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(dedent(skill_text).strip() + "\n", encoding="utf-8")
    for relative_path, content in (methods or {}).items():
        path = skill_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content).lstrip(), encoding="utf-8")
    return skill_dir


@pytest.mark.asyncio
async def test_compile_from_skills_loads_stub() -> None:
    registry = ChannelRegistry.compile_from_skills(_fixture_root(), Environment())

    results = await registry.get("stub_ok").search(
        SubQuery(text="ranking signals", rationale="Need one compiled stub result")
    )

    assert len(results) >= 1
    assert all(isinstance(item, Evidence) for item in results)
    assert results[0].source_channel == "stub_ok:echo"


def test_compile_from_skills_method_unavailable_with_unmet_requires() -> None:
    registry = ChannelRegistry.compile_from_skills(_fixture_root(), Environment())

    metadata = registry.metadata("stub_cookie")

    assert len(metadata.methods) == 1
    assert metadata.methods[0].available is False
    assert "cookie:stub_cookie" in metadata.methods[0].unmet_requires


def test_compile_from_skills_preserves_declared_metadata(tmp_path: Path) -> None:
    root = tmp_path / "channels"
    _write_channel_skill(
        root,
        name="metadata_stub",
        skill_text="""
        ---
        name: metadata_stub
        description: "Fixture channel with declared routing metadata."
        version: 1
        languages: [zh, mixed]
        methods:
          - id: api_search
            impl: methods/api_search.py
            requires: [env:STUB_COOKIE]
        fallback_chain: [api_search]
        when_to_use:
          query_languages: [zh, mixed]
          query_types: [community, troubleshooting]
          domain_hints: [linux.do, discourse]
        quality_hint:
          typical_yield: medium
          chinese_native: true
        layer: leaf
        domains: [chinese-ugc]
        scenarios: [developer-community, public-forum]
        model_tier: Fast
        tier: 2
        fix_hint: "autosearch login metadata_stub"
        ---
        """,
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())
    metadata = registry.metadata("metadata_stub")

    assert metadata.layer == "leaf"
    assert metadata.domains == ["chinese-ugc"]
    assert metadata.scenarios == ["developer-community", "public-forum"]
    assert metadata.model_tier == "Fast"
    assert metadata.tier == 2
    assert metadata.fix_hint == "autosearch login metadata_stub"
    assert metadata.when_to_use is not None
    assert metadata.when_to_use.domain_hints == ["linux.do", "discourse"]


def test_compile_from_skills_impl_missing_marks_unavailable(tmp_path: Path) -> None:
    root = tmp_path / "channels"
    _write_channel_skill(
        root,
        name="missing_impl",
        skill_text="""
        ---
        name: missing_impl
        description: "Fixture channel with a missing implementation file."
        version: 1
        languages: [en]
        methods:
          - id: pending
            impl: methods/pending.py
            requires: []
        fallback_chain: [pending]
        ---
        """,
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())
    method = registry.metadata("missing_impl").methods[0]

    assert method.available is False
    assert method.unmet_requires == ["impl_missing"]
    assert registry.available() == []


def test_available_filters_out_channels_with_no_available_methods() -> None:
    registry = ChannelRegistry.compile_from_skills(_fixture_root(), Environment())

    available_names = {channel.name for channel in registry.available()}

    assert "stub_ok" in available_names
    assert "stub_cookie" not in available_names


@pytest.mark.asyncio
async def test_fallback_chain_tries_methods_in_order(tmp_path: Path) -> None:
    root = tmp_path / "channels"
    _write_channel_skill(
        root,
        name="fallback_stub",
        skill_text="""
        ---
        name: fallback_stub
        description: "Fixture channel with retryable fallback ordering."
        version: 1
        languages: [en]
        methods:
          - id: first
            impl: methods/first.py
            requires: []
          - id: second
            impl: methods/second.py
            requires: []
        fallback_chain: [first, second]
        ---
        """,
        methods={
            "methods/first.py": """
                # Self-written, plan autosearch-0418-channels-and-skills.md § F001
                from autosearch.channels.base import MethodUnavailable
                from autosearch.core.models import Evidence, SubQuery


                async def search(query: SubQuery) -> list[Evidence]:
                    raise MethodUnavailable(f"first method unavailable for {query.text}")
            """,
            "methods/second.py": """
                # Self-written, plan autosearch-0418-channels-and-skills.md § F001
                from datetime import UTC, datetime

                from autosearch.core.models import Evidence, SubQuery


                async def search(query: SubQuery) -> list[Evidence]:
                    return [
                        Evidence(
                            url="https://example.com/fallback/second",
                            title=f"fallback result for {query.text}",
                            snippet=query.rationale,
                            source_channel="fallback_stub:second",
                            fetched_at=datetime.now(UTC),
                        )
                    ]
            """,
        },
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())

    results = await registry.get("fallback_stub").search(
        SubQuery(text="fallback query", rationale="Exercise method ordering")
    )

    assert len(results) == 1
    assert results[0].source_channel == "fallback_stub:second"
    assert results[0].title == "fallback result for fallback query"


def test_existing_register_and_get_still_work() -> None:
    registry = ChannelRegistry()
    channel = DemoChannel(name="legacy-demo")

    registry.register(channel)

    assert registry.get("legacy-demo") is channel
    assert registry.all_channels() == [channel]


def test_attach_health_filters_cooldown() -> None:
    registry = ChannelRegistry.compile_from_skills(_fixture_root(), Environment())
    health = ChannelHealth()
    registry.attach_health(health)

    for _ in range(3):
        health.record("stub_ok", "echo", success=False, latency_ms=5.0, error="timeout")

    available_names = {channel.name for channel in registry.available()}

    assert health.is_in_cooldown("stub_ok", "echo") is True
    assert "stub_ok" not in available_names


@pytest.mark.asyncio
async def test_missing_impl_channel_raises_method_unavailable(tmp_path: Path) -> None:
    root = tmp_path / "channels"
    _write_channel_skill(
        root,
        name="missing_impl_call",
        skill_text="""
        ---
        name: missing_impl_call
        description: "Fixture channel with no callable methods."
        version: 1
        languages: [en]
        methods:
          - id: pending
            impl: methods/pending.py
            requires: []
        fallback_chain: [pending]
        ---
        """,
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())

    with pytest.raises(MethodUnavailable, match="no available search methods"):
        await registry.get("missing_impl_call").search(
            SubQuery(text="pending query", rationale="Exercise missing impl stub")
        )
