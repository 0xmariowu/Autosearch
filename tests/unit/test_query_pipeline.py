"""Tests for autosearch.cli.query_pipeline (P1-7 thin CLI orchestration).

These tests mock the clarifier and channel runtime so they run without
network access. The behaviors covered:

- clarifier `need_clarification=True` → result returns the question
- clarifier returns `channel_priority` → top-N channels are searched
- per-channel exception is swallowed (one failure doesn't kill the run)
- empty `channel_priority` → falls back to a default trio
- markdown / JSON renderers handle clarification, empty, and populated states
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from autosearch.cli.query_pipeline import (
    QueryResult,
    render_json,
    render_markdown,
    run_query,
)
from autosearch.core.models import Evidence


def _evidence(url: str, title: str, channel: str = "arxiv") -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet="snippet text",
        source_channel=channel,
        fetched_at=datetime.now(UTC),
    )


class _FakeChannel:
    def __init__(
        self, name: str, evidence: list[Evidence] | None = None, raises: bool = False
    ) -> None:
        self.name = name
        self._evidence = evidence or []
        self._raises = raises

    async def search(self, _subquery: Any) -> list[Evidence]:
        if self._raises:
            raise RuntimeError(f"channel {self.name} failed")
        return self._evidence


class _FakeRuntime:
    def __init__(self, channels: list[_FakeChannel]) -> None:
        self.channels = channels


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clarify_response: Any,
    channels: list[_FakeChannel],
) -> None:
    async def _fake_clarify(_query: str, _mode_hint: Any) -> Any:
        return clarify_response

    def _fake_runtime() -> _FakeRuntime:
        return _FakeRuntime(channels)

    monkeypatch.setattr("autosearch.mcp.server._invoke_clarifier", _fake_clarify)
    monkeypatch.setattr("autosearch.core.channel_runtime.get_channel_runtime", _fake_runtime)


# ---------- run_query ----------


class TestRunQuery:
    def test_clarification_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clarify = type(
            "Resp",
            (),
            {
                "need_clarification": True,
                "question": "Which language?",
                "question_options": ["en", "zh"],
                "channel_priority": [],
            },
        )()
        _patch_pipeline(monkeypatch, clarify_response=clarify, channels=[])

        result = asyncio.run(run_query("ambiguous"))

        assert result.clarify_question == "Which language?"
        assert result.clarify_options == ["en", "zh"]
        assert result.channels_used == []
        assert result.evidence == []

    def test_top_n_channels_searched_with_evidence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ch1 = _FakeChannel(
            "arxiv", [_evidence(f"https://a.example/{i}", f"a-{i}") for i in range(3)]
        )
        ch2 = _FakeChannel(
            "github", [_evidence(f"https://g.example/{i}", f"g-{i}", "github") for i in range(2)]
        )
        ch3 = _FakeChannel("ddgs", [_evidence("https://d.example/0", "d-0", "ddgs")])
        ch_extra = _FakeChannel("ignored", [_evidence("https://x.example/0", "x-0")])

        clarify = type(
            "Resp",
            (),
            {
                "need_clarification": False,
                "question": "",
                "question_options": [],
                "channel_priority": ["arxiv", "github", "ddgs", "ignored"],
            },
        )()
        _patch_pipeline(monkeypatch, clarify_response=clarify, channels=[ch1, ch2, ch3, ch_extra])

        result = asyncio.run(run_query("transformers", top_k_channels=3, per_channel_k=5))

        assert result.channels_used == ["arxiv", "github", "ddgs"]
        assert "ignored" not in result.channels_used
        # 3 + 2 + 1 = 6 evidence rows
        assert len(result.evidence) == 6

    def test_per_channel_failure_is_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ok_channel = _FakeChannel("arxiv", [_evidence("https://a/1", "a1")])
        bad_channel = _FakeChannel("github", raises=True)

        clarify = type(
            "Resp",
            (),
            {
                "need_clarification": False,
                "question": "",
                "question_options": [],
                "channel_priority": ["arxiv", "github"],
            },
        )()
        _patch_pipeline(monkeypatch, clarify_response=clarify, channels=[ok_channel, bad_channel])

        result = asyncio.run(run_query("test", top_k_channels=2))

        assert "arxiv" in result.channels_used
        assert "github" in result.channels_used  # name still listed even if its search failed
        assert len(result.evidence) == 1  # only arxiv contributed evidence

    def test_unknown_channel_name_yields_no_evidence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clarify = type(
            "Resp",
            (),
            {
                "need_clarification": False,
                "question": "",
                "question_options": [],
                "channel_priority": ["nonexistent_channel"],
            },
        )()
        _patch_pipeline(monkeypatch, clarify_response=clarify, channels=[])

        result = asyncio.run(run_query("test", top_k_channels=1))

        assert result.channels_used == ["nonexistent_channel"]
        assert result.evidence == []

    def test_empty_priority_falls_back_to_default_trio(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clarify = type(
            "Resp",
            (),
            {
                "need_clarification": False,
                "question": "",
                "question_options": [],
                "channel_priority": [],
            },
        )()
        # Don't register any matching channels — fallback names will resolve to nothing.
        _patch_pipeline(monkeypatch, clarify_response=clarify, channels=[])

        result = asyncio.run(run_query("test", top_k_channels=3))

        assert result.channels_used == ["arxiv", "ddgs", "github"]


# ---------- renderers ----------


class TestRenderMarkdown:
    def test_clarification(self) -> None:
        out = render_markdown(
            QueryResult(
                query="x",
                clarify_question="What language?",
                clarify_options=["en", "zh"],
            )
        )
        assert "Clarification needed" in out
        assert "What language?" in out
        assert "- en" in out
        assert "- zh" in out

    def test_empty_evidence(self) -> None:
        out = render_markdown(QueryResult(query="x", channels_used=["arxiv"]))
        assert "No evidence found" in out
        assert "arxiv" in out

    def test_populated_evidence_has_citations_and_handoff(self) -> None:
        result = QueryResult(
            query="transformers 2026",
            channels_used=["arxiv"],
            evidence=[
                {
                    "url": "https://arxiv.org/abs/2026.0001",
                    "title": "Paper One",
                    "snippet": "About transformers.",
                    "source_channel": "arxiv",
                    "published_at": "2026-04-01",
                }
            ],
        )
        out = render_markdown(result)
        assert "AutoSearch evidence brief" in out
        assert "## Evidence" in out
        assert "Paper One" in out
        assert "arxiv" in out
        assert "## Citations" in out
        assert "[1] Paper One" in out
        assert "Paste the brief above into Claude / ChatGPT / Cursor" in out


class TestRenderJSON:
    def test_round_trips(self) -> None:
        result = QueryResult(
            query="x",
            channels_used=["arxiv"],
            evidence=[{"url": "u", "title": "t"}],
        )
        parsed = json.loads(render_json(result))
        assert parsed["query"] == "x"
        assert parsed["channels_used"] == ["arxiv"]
        assert parsed["evidence_count"] == 1
        assert parsed["evidence"] == [{"url": "u", "title": "t"}]
        assert parsed["clarify_question"] is None

    def test_clarification_serialized(self) -> None:
        result = QueryResult(query="x", clarify_question="Q?", clarify_options=["a", "b"])
        parsed = json.loads(render_json(result))
        assert parsed["clarify_question"] == "Q?"
        assert parsed["clarify_options"] == ["a", "b"]
        assert parsed["evidence_count"] == 0
