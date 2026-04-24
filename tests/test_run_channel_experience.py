"""Tests for run_channel experience-layer integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from autosearch.core.models import Evidence, SubQuery
from autosearch.mcp.server import RunChannelResponse, create_server
from autosearch.skills import experience


class _CapturingChannel:
    def __init__(self, name: str, results: list[Evidence]):
        self.name = name
        self.languages = ["en"]
        self._results = results
        self.last_query: SubQuery | None = None

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.last_query = query
        return list(self._results)


def _make_evidence(url: str, title: str, source_channel: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet="snippet text",
        content=None,
        source_channel=source_channel,
        fetched_at=datetime.now(tz=UTC),
        score=0.5,
    )


def _make_skill_dir(tmp_path, monkeypatch, skill_name: str = "bilibili"):
    root = tmp_path / "skills"
    skill_dir = root / "channels" / skill_name
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr(experience, "_SKILLS_ROOT", root)
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(root))
    return skill_dir


@pytest.mark.asyncio
async def test_run_channel_includes_experience_digest_in_rationale(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_dir = _make_skill_dir(tmp_path, monkeypatch)
    skill_dir.joinpath("experience.md").write_text(
        "## Active Rules\n- Prefer exact product terms.\n",
        encoding="utf-8",
    )
    channel = _CapturingChannel(
        "bilibili",
        [_make_evidence("https://example.com/a", "Item A", "bilibili")],
    )
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: [channel])

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001
    response = await tm.call_tool(
        "run_channel",
        {
            "channel_name": "bilibili",
            "query": "test query",
            "rationale": "original rationale",
        },
    )

    assert isinstance(response, RunChannelResponse)
    assert response.ok is True
    assert channel.last_query is not None
    assert channel.last_query.rationale.startswith("original rationale")
    assert "[Experience Digest]" in channel.last_query.rationale
    assert "Prefer exact product terms." in channel.last_query.rationale


@pytest.mark.asyncio
async def test_run_channel_appends_to_patterns_jsonl_after_execution(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_dir = _make_skill_dir(tmp_path, monkeypatch)
    channel = _CapturingChannel(
        "bilibili",
        [
            _make_evidence("https://example.com/a", "Item A", "bilibili"),
            _make_evidence("https://example.com/b", "Item B", "bilibili"),
        ],
    )
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: [channel])

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001
    response = await tm.call_tool(
        "run_channel",
        {"channel_name": "bilibili", "query": "test query", "k": 1},
    )

    assert isinstance(response, RunChannelResponse)
    assert response.ok is True

    patterns_path = skill_dir / "experience" / "patterns.jsonl"
    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["skill"] == "bilibili"
    assert payload["query"] == "test query"
    assert payload["outcome"] == "success"
    assert payload["count_total"] == 2
    assert payload["count_returned"] == 1
    assert datetime.fromisoformat(payload["ts"]).tzinfo is not None


@pytest.mark.asyncio
async def test_experience_digest_text_appears_in_subquery_rationale(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2-T13: Specific text from experience.md must appear in SubQuery.rationale."""
    skill_dir = _make_skill_dir(tmp_path, monkeypatch, skill_name="arxiv")
    unique_marker = "USE_EXACT_ARXIV_IDS_FOR_BETTER_RESULTS"
    skill_dir.joinpath("experience.md").write_text(
        f"## Active Rules\n- {unique_marker}\n",
        encoding="utf-8",
    )
    channel = _CapturingChannel(
        "arxiv",
        [_make_evidence("https://arxiv.org/abs/1234", "Test Paper", "arxiv")],
    )
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: [channel])

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    await server._tool_manager.call_tool(
        "run_channel",
        {"channel_name": "arxiv", "query": "LLM survey", "rationale": "research"},
    )

    assert channel.last_query is not None
    assert unique_marker in channel.last_query.rationale, (
        f"Expected '{unique_marker}' from experience.md to appear in rationale, "
        f"got: {channel.last_query.rationale!r}"
    )
