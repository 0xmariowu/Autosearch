"""Tests for the list_skills MCP tool and skill-catalog scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from autosearch.mcp.server import (
    SkillSummary,
    _parse_skill_md,
    _scan_skill_catalog,
    create_server,
)


def _write_skill(
    root: Path,
    group: str,
    name: str,
    *,
    description: str = "",
    layer: str = "leaf",
    domains: list[str] | None = None,
    scenarios: list[str] | None = None,
    model_tier: str = "Fast",
    deprecated: bool = False,
    body: str = "Body text here.",
) -> Path:
    skill_dir = root / group / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter_lines = [
        "---",
        f"name: {name}",
        f"description: {description or 'Test skill ' + name}",
        f"layer: {layer}",
        f"domains: [{', '.join(domains or [])}]",
        f"scenarios: [{', '.join(scenarios or [])}]",
        f"model_tier: {model_tier}",
    ]
    if deprecated:
        frontmatter_lines.append("deprecated: true")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")
    frontmatter_lines.append(body)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("\n".join(frontmatter_lines) + "\n", encoding="utf-8")
    return skill_path


def _write_router_skill(root: Path, name: str = "autosearch:router") -> Path:
    """router/SKILL.md sits at the group root, not under a leaf."""
    router_dir = root / "router"
    router_dir.mkdir(parents=True, exist_ok=True)
    skill_path = router_dir / "SKILL.md"
    skill_path.write_text(
        "---\n"
        f"name: {name}\n"
        "description: Router.\n"
        "layer: router\n"
        "domains: [meta]\n"
        "scenarios: [task-routing]\n"
        "model_tier: Fast\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )
    return skill_path


def test_parse_skill_md_reads_frontmatter(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path,
        "channels",
        "bilibili",
        description="Chinese video.",
        domains=["chinese-ugc"],
        scenarios=["chinese-native"],
    )

    summary = _parse_skill_md(skill_path, group="channels")

    assert summary is not None
    assert summary.name == "bilibili"
    assert summary.description == "Chinese video."
    assert summary.group == "channels"
    assert summary.layer == "leaf"
    assert summary.domains == ["chinese-ugc"]
    assert summary.scenarios == ["chinese-native"]
    assert summary.model_tier == "Fast"
    assert summary.deprecated is False


def test_parse_actual_discourse_forum_skill_md_exposes_governance_metadata() -> None:
    skill_path = (
        Path(__file__).resolve().parents[2]
        / "autosearch"
        / "skills"
        / "channels"
        / "discourse_forum"
        / "SKILL.md"
    )

    summary = _parse_skill_md(skill_path, group="channels")

    assert summary is not None
    assert summary.name == "discourse_forum"
    assert summary.group == "channels"
    assert summary.layer == "leaf"
    assert summary.domains == ["chinese-ugc"]
    assert {"developer-community", "public-forum"} <= set(summary.scenarios)
    assert summary.model_tier == "Fast"
    assert summary.deprecated is False


def test_parse_skill_md_returns_none_on_missing_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "channels" / "weird"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("no frontmatter here\njust plain text\n", encoding="utf-8")

    assert _parse_skill_md(skill_path, group="channels") is None


def test_parse_skill_md_returns_none_on_malformed_yaml(tmp_path: Path) -> None:
    skill_dir = tmp_path / "channels" / "broken"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("---\n: :\n  [:]\n---\nbody\n", encoding="utf-8")

    assert _parse_skill_md(skill_path, group="channels") is None


def test_scan_skill_catalog_scans_all_groups(tmp_path: Path) -> None:
    _write_skill(tmp_path, "channels", "bilibili", domains=["chinese-ugc"])
    _write_skill(tmp_path, "channels", "arxiv", domains=["academic"])
    _write_skill(tmp_path, "tools", "fetch-jina", domains=["web-fetch"])
    _write_skill(tmp_path, "meta", "model-routing", layer="meta", domains=["meta"])
    _write_router_skill(tmp_path)

    summaries = _scan_skill_catalog(skills_root=tmp_path)
    names = [s.name for s in summaries]

    assert set(names) == {"bilibili", "arxiv", "fetch-jina", "model-routing", "autosearch:router"}
    assert len(summaries) == 5
    # All sorted by (group, name) — channels group first, then meta, router, tools
    assert names.index("arxiv") < names.index("bilibili")  # same group, alphabetical


def test_scan_skill_catalog_filters_by_group(tmp_path: Path) -> None:
    _write_skill(tmp_path, "channels", "bilibili", domains=["chinese-ugc"])
    _write_skill(tmp_path, "tools", "fetch-jina", domains=["web-fetch"])
    _write_router_skill(tmp_path)

    summaries = _scan_skill_catalog(skills_root=tmp_path, group_filter="tools")

    assert [s.name for s in summaries] == ["fetch-jina"]


def test_scan_skill_catalog_filters_by_domain(tmp_path: Path) -> None:
    _write_skill(tmp_path, "channels", "bilibili", domains=["chinese-ugc"])
    _write_skill(tmp_path, "channels", "arxiv", domains=["academic"])
    _write_skill(tmp_path, "channels", "weibo", domains=["chinese-ugc"])

    summaries = _scan_skill_catalog(skills_root=tmp_path, domain_filter="chinese-ugc")

    assert sorted(s.name for s in summaries) == ["bilibili", "weibo"]


def test_scan_skill_catalog_hides_deprecated_by_default(tmp_path: Path) -> None:
    _write_skill(tmp_path, "channels", "bilibili", domains=["chinese-ugc"])
    _write_skill(tmp_path, "channels", "legacy_channel", deprecated=True)

    summaries = _scan_skill_catalog(skills_root=tmp_path)

    assert [s.name for s in summaries] == ["bilibili"]


def test_scan_skill_catalog_shows_deprecated_when_requested(tmp_path: Path) -> None:
    _write_skill(tmp_path, "channels", "bilibili", domains=["chinese-ugc"])
    _write_skill(tmp_path, "channels", "legacy_channel", deprecated=True)

    summaries = _scan_skill_catalog(skills_root=tmp_path, include_deprecated=True)

    assert sorted(s.name for s in summaries) == ["bilibili", "legacy_channel"]
    deprecated_entry = next(s for s in summaries if s.name == "legacy_channel")
    assert deprecated_entry.deprecated is True


def test_scan_returns_empty_for_missing_root(tmp_path: Path) -> None:
    summaries = _scan_skill_catalog(skills_root=tmp_path / "does_not_exist")

    assert summaries == []


@pytest.mark.asyncio
async def test_list_skills_mcp_tool_is_registered() -> None:
    """End-to-end: create MCP server, confirm list_skills tool is registered."""
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert "list_skills" in tool_names
    assert "research" in tool_names
    assert "health" in tool_names


def test_skill_summary_pydantic_roundtrip() -> None:
    summary = SkillSummary(
        name="fetch-jina",
        description="URL to markdown.",
        path="autosearch/skills/tools/fetch-jina",
        group="tools",
        layer="leaf",
        domains=["web-fetch"],
        scenarios=["url-reading"],
        model_tier="Fast",
    )
    dumped = summary.model_dump()
    assert dumped["name"] == "fetch-jina"
    assert dumped["domains"] == ["web-fetch"]
    assert dumped["deprecated"] is False
