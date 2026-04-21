from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest


def _load_judge() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "bench" / "judge.py"
    module_name = "_judge_under_test"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass type-hint resolution can find the module.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


JUDGE = _load_judge()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _anthropic_response(text: str, *, status: int = 200) -> dict[str, object]:
    return {"content": [{"type": "text", "text": text}]}


def test_discover_pairs_matches_common_filenames(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "en_topic.md").write_text("A report one", encoding="utf-8")
    (tmp_path / "a" / "zh_topic.md").write_text("A report two", encoding="utf-8")
    (tmp_path / "a" / "only_a.md").write_text("A only", encoding="utf-8")
    (tmp_path / "b" / "en_topic.md").write_text("B report one", encoding="utf-8")
    (tmp_path / "b" / "zh_topic.md").write_text("B report two", encoding="utf-8")
    (tmp_path / "b" / "only_b.md").write_text("B only", encoding="utf-8")

    pairs = JUDGE.discover_pairs(tmp_path / "a", tmp_path / "b")

    assert [p.name for p in pairs] == ["en_topic.md", "zh_topic.md"]
    assert pairs[0].a_text == "A report one"
    assert pairs[0].b_text == "B report one"


def test_parse_judge_response_winner_position_1() -> None:
    preferred, reason = JUDGE.parse_judge_response(
        '{"preferred": 1, "reason": "report 1 has concrete specifics"}'
    )
    assert preferred == 1
    assert reason == "report 1 has concrete specifics"


def test_parse_judge_response_winner_position_2_with_code_fence() -> None:
    preferred, reason = JUDGE.parse_judge_response(
        '```json\n{"preferred": 2, "reason": "better coverage"}\n```'
    )
    assert preferred == 2
    assert reason == "better coverage"


def test_parse_judge_response_tie_preferred_null() -> None:
    preferred, reason = JUDGE.parse_judge_response('{"preferred": null, "reason": "equivalent"}')
    assert preferred is None
    assert reason == "equivalent"


def test_parse_judge_response_malformed_returns_tie() -> None:
    preferred, reason = JUDGE.parse_judge_response("this is not json")
    assert preferred is None
    assert "malformed" in reason


def test_judge_pair_winner_a_no_swap() -> None:
    pair = JUDGE.PairInput(name="en.md", a_text="A text", b_text="B text")
    rng = random.Random(0)  # first call rng.random() > 0.5 → swap=False
    # Confirm rng behaviour is deterministic in this test environment.
    assert rng.random() > 0.5
    rng = random.Random(0)  # reset after probe

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_response('{"preferred": 1, "reason": "A wins"}'))

    with _client(handler) as client:
        verdict = JUDGE.judge_pair(
            pair,
            a_label="aug",
            b_label="bare",
            model="claude-sonnet-4-6",
            api_key="test-key",
            http_client=client,
            rng=rng,
        )

    assert verdict.swapped is False
    assert verdict.winner == "a"
    assert verdict.reason == "A wins"


def test_judge_pair_winner_b_with_swap() -> None:
    pair = JUDGE.PairInput(name="x.md", a_text="A text", b_text="B text")

    # Craft an rng that swaps (first rng.random() < 0.5).
    rng = random.Random()
    rng.random = lambda: 0.1  # type: ignore[assignment]

    # Judge says "preferred: 1" (i.e., the report in slot 1). With swap, slot 1 = B.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_response('{"preferred": 1, "reason": "B wins"}'))

    with _client(handler) as client:
        verdict = JUDGE.judge_pair(
            pair,
            a_label="aug",
            b_label="bare",
            model="claude-sonnet-4-6",
            api_key="test-key",
            http_client=client,
            rng=rng,
        )

    assert verdict.swapped is True
    assert verdict.winner == "b"


def test_judge_pair_api_error_returns_tie() -> None:
    pair = JUDGE.PairInput(name="err.md", a_text="A", b_text="B")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server down")

    with _client(handler) as client:
        verdict = JUDGE.judge_pair(
            pair,
            a_label="aug",
            b_label="bare",
            model="claude-sonnet-4-6",
            api_key="test-key",
            http_client=client,
        )

    assert verdict.winner == "tie"
    assert "judge_api_error" in verdict.reason


def test_judge_pair_malformed_response_returns_tie() -> None:
    pair = JUDGE.PairInput(name="garbled.md", a_text="A", b_text="B")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_response("not json at all"))

    with _client(handler) as client:
        verdict = JUDGE.judge_pair(
            pair,
            a_label="aug",
            b_label="bare",
            model="claude-sonnet-4-6",
            api_key="test-key",
            http_client=client,
        )

    assert verdict.winner == "tie"


def test_summarize_counts_wins_and_ties() -> None:
    verdicts = [
        JUDGE.PairVerdict(name="1", winner="a", reason="x", swapped=False),
        JUDGE.PairVerdict(name="2", winner="a", reason="x", swapped=True),
        JUDGE.PairVerdict(name="3", winner="b", reason="x", swapped=False),
        JUDGE.PairVerdict(name="4", winner="tie", reason="x", swapped=False),
    ]

    stats = JUDGE.summarize(verdicts, "aug", "bare")

    assert stats["total"] == 4
    assert stats["a_wins"] == 2
    assert stats["b_wins"] == 1
    assert stats["ties"] == 1
    assert stats["a_win_rate"] == pytest.approx(0.5)
    assert stats["b_win_rate"] == pytest.approx(0.25)


def test_render_summary_markdown_contains_labels_and_counts() -> None:
    verdicts = [
        JUDGE.PairVerdict(name="pair1.md", winner="a", reason="A has specifics", swapped=False),
    ]
    stats = JUDGE.summarize(verdicts, "aug", "bare")

    md = JUDGE.render_summary_markdown(stats, verdicts)

    assert "aug vs bare" in md
    assert "total pairs: 1" in md
    assert "**aug** wins: 1" in md
    assert "A has specifics" in md
