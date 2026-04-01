import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autosearch.v2 import judge


NOW = dt.datetime(2026, 3, 28, tzinfo=dt.timezone.utc)
DIMENSION_NAMES = {
    "quantity",
    "diversity",
    "relevance",
    "freshness",
    "efficiency",
    "latency",
    "adoption",
    "knowledge_growth",
}


def write_jsonl(path: Path, rows: list[object]) -> Path:
    path.write_text(
        "".join(
            json.dumps(row) + "\n" if isinstance(row, dict) else f"{row}\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    return path


def write_state_json(base: Path, filename: str, payload: dict) -> Path:
    path = base / "state" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def result(
    url: str,
    source: str,
    query: str,
    title: str = "",
    snippet: str = "",
    metadata: dict | None = None,
) -> dict:
    return {
        "url": url,
        "title": title,
        "source": source,
        "snippet": snippet,
        "found_at": NOW.isoformat().replace("+00:00", "Z"),
        "query": query,
        "metadata": metadata or {},
    }


def score_file(path: Path, target: int = 30) -> dict:
    # Ensure test has its own state/ dir so judge doesn't fall back to real state/
    state_dir = path.parent / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return judge.score_results(
        judge.load_results(path), str(path), target=target, now=NOW
    )


def assert_dimensions(score: dict, **expected: float) -> None:
    assert set(score["dimensions"]) == DIMENSION_NAMES
    for name, value in expected.items():
        assert score["dimensions"][name] == pytest.approx(value)


def test_empty_input(tmp_path: Path) -> None:
    score = score_file(write_jsonl(tmp_path / "empty.jsonl", []))
    assert_dimensions(
        score,
        quantity=0.0,
        diversity=0.0,
        relevance=0.0,
        freshness=0.0,
        efficiency=0.0,
        latency=0.5,
        adoption=0.5,
    )
    expected_total = (
        judge.DEFAULT_WEIGHTS["latency"] * 0.5
        + judge.DEFAULT_WEIGHTS["adoption"] * 0.5
        + judge.DEFAULT_WEIGHTS["knowledge_growth"] * 0.5
    ) / sum(judge.DEFAULT_WEIGHTS.values())
    assert score["total"] == pytest.approx(expected_total)


def test_single_result(tmp_path: Path) -> None:
    row = result(
        "https://example.com/1", "github", "python judge", title="Python judge"
    )
    score = score_file(write_jsonl(tmp_path / "single.jsonl", [row]))
    assert_dimensions(
        score,
        quantity=1 / 30,
        diversity=0.0,
        relevance=1.0,
        latency=0.5,
        adoption=0.5,
    )


def test_multi_platform_diversity(tmp_path: Path) -> None:
    rows = [
        result(f"https://example.com/{idx}", source, "topic", title="topic")
        for idx, source in enumerate(
            ["github"] * 4 + ["reddit"] * 3 + ["hackernews"] * 3,
            start=1,
        )
    ]
    score = score_file(write_jsonl(tmp_path / "diverse.jsonl", rows))
    assert set(score["dimensions"]) == DIMENSION_NAMES
    assert score["dimensions"]["diversity"] > 0.5
    assert score["dimensions"]["latency"] == pytest.approx(0.5)
    assert score["dimensions"]["adoption"] == pytest.approx(0.5)


def test_single_platform_low_diversity(tmp_path: Path) -> None:
    rows = [
        result(f"https://example.com/{idx}", "github", "topic", title="topic")
        for idx in range(10)
    ]
    score = score_file(write_jsonl(tmp_path / "single-platform.jsonl", rows))
    assert set(score["dimensions"]) == DIMENSION_NAMES
    assert score["dimensions"]["diversity"] == 0.0
    assert score["dimensions"]["latency"] == pytest.approx(0.5)
    assert score["dimensions"]["adoption"] == pytest.approx(0.5)


def test_relevance_all_match(tmp_path: Path) -> None:
    rows = [
        result(
            f"https://example.com/{idx}",
            "github",
            "agent search",
            title="Agent search guide",
        )
        for idx in range(3)
    ]
    score = score_file(write_jsonl(tmp_path / "all-match.jsonl", rows))
    assert_dimensions(score, relevance=1.0, latency=0.5, adoption=0.5)


def test_relevance_none_match(tmp_path: Path) -> None:
    rows = [
        result(
            f"https://example.com/{idx}",
            "github",
            "agent search",
            title="database tuning",
            snippet="sql indexes",
        )
        for idx in range(3)
    ]
    score = score_file(write_jsonl(tmp_path / "none-match.jsonl", rows))
    assert_dimensions(score, relevance=0.0, latency=0.5, adoption=0.5)


def test_llm_relevance(tmp_path: Path) -> None:
    rows = [
        result(
            "https://example.com/1",
            "github",
            "agent search",
            title="database tuning",
            metadata={"llm_relevant": True},
        ),
        result(
            "https://example.com/2",
            "github",
            "agent search",
            title="agent search guide",
            metadata={"llm_relevant": False},
        ),
    ]
    score = score_file(write_jsonl(tmp_path / "llm-relevance.jsonl", rows))
    assert_dimensions(score, relevance=0.5, latency=0.5, adoption=0.5)


def test_llm_relevance_fallback(tmp_path: Path) -> None:
    rows = [
        result(
            "https://example.com/1",
            "github",
            "agent search",
            title="agent systems handbook",
            metadata={"published_at": NOW.isoformat().replace("+00:00", "Z")},
        ),
        result(
            "https://example.com/2",
            "github",
            "agent search",
            title="database tuning",
            snippet="sql indexes",
            metadata={"published_at": NOW.isoformat().replace("+00:00", "Z")},
        ),
    ]
    score = score_file(write_jsonl(tmp_path / "llm-fallback.jsonl", rows))
    assert_dimensions(score, relevance=0.5, latency=0.5, adoption=0.5)


def test_freshness_all_recent(tmp_path: Path) -> None:
    recent = (NOW - dt.timedelta(days=30)).isoformat().replace("+00:00", "Z")
    rows = [
        result(
            f"https://example.com/{idx}",
            "reddit",
            "topic",
            metadata={"published_at": recent},
        )
        for idx in range(3)
    ]
    score = score_file(write_jsonl(tmp_path / "fresh.jsonl", rows))
    assert_dimensions(score, freshness=1.0, latency=0.5, adoption=0.5)


def test_freshness_all_old(tmp_path: Path) -> None:
    old = (NOW - dt.timedelta(days=300)).isoformat().replace("+00:00", "Z")
    rows = [
        result(
            f"https://example.com/{idx}",
            "reddit",
            "topic",
            metadata={"updated_at": old},
        )
        for idx in range(3)
    ]
    score = score_file(write_jsonl(tmp_path / "old.jsonl", rows))
    assert_dimensions(score, freshness=0.0, latency=0.5, adoption=0.5)


def test_freshness_unix_timestamp(tmp_path: Path) -> None:
    recent_ts = int((NOW - dt.timedelta(days=30)).timestamp())
    old_ts = int((NOW - dt.timedelta(days=300)).timestamp())
    rows = [
        result(
            "https://example.com/1",
            "reddit",
            "topic",
            metadata={"created_utc": recent_ts},
        ),
        result(
            "https://example.com/2", "reddit", "topic", metadata={"created_utc": old_ts}
        ),
    ]
    score = score_file(write_jsonl(tmp_path / "unix.jsonl", rows))
    assert_dimensions(score, freshness=0.5, latency=0.5, adoption=0.5)


def test_latency_dimension(tmp_path: Path) -> None:
    start = NOW - dt.timedelta(seconds=30)
    end = NOW
    write_state_json(
        tmp_path,
        "config.json",
        {"scoring": {"latency_budget_seconds": 60}},
    )
    write_state_json(
        tmp_path,
        "timing.json",
        {
            "start_ts": start.isoformat().replace("+00:00", "Z"),
            "end_ts": end.isoformat().replace("+00:00", "Z"),
        },
    )
    score = score_file(
        write_jsonl(
            tmp_path / "latency.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    assert_dimensions(score, latency=0.5, adoption=0.5)


def test_adoption_dimension(tmp_path: Path) -> None:
    write_state_json(tmp_path, "adoption.json", {"score": 0.8})
    score = score_file(
        write_jsonl(
            tmp_path / "adoption.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    assert_dimensions(score, latency=0.5, adoption=0.8)


def test_custom_target(tmp_path: Path) -> None:
    rows = [
        result(f"https://example.com/{idx}", "github", f"query {idx}", title="query")
        for idx in range(10)
    ]
    score = score_file(write_jsonl(tmp_path / "target.jsonl", rows), target=10)
    assert_dimensions(score, quantity=1.0, latency=0.5, adoption=0.5)


def test_invalid_json_lines(tmp_path: Path) -> None:
    rows = [
        result("https://example.com/1", "github", "judge", title="judge"),
        "{bad json",
        result("https://example.com/2", "reddit", "judge", title="judge"),
    ]
    score = score_file(write_jsonl(tmp_path / "invalid.jsonl", rows))
    assert set(score["dimensions"]) == DIMENSION_NAMES
    assert score["meta"]["total_results"] == 2
    assert score["meta"]["unique_urls"] == 2
    assert score["dimensions"]["latency"] == pytest.approx(0.5)
    assert score["dimensions"]["adoption"] == pytest.approx(0.5)


def test_knowledge_growth_no_file(tmp_path: Path) -> None:
    """Returns NEUTRAL when knowledge-growth.json does not exist."""
    score = score_file(
        write_jsonl(
            tmp_path / "kg-none.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    assert_dimensions(score, knowledge_growth=0.5)


def test_knowledge_growth_empty_data(tmp_path: Path) -> None:
    """Returns NEUTRAL when file exists but all values are zero."""
    write_state_json(
        tmp_path,
        "knowledge-growth.json",
        {
            "initial_entries": 0,
            "final_entries": 0,
            "initial_gaps": 0,
            "remaining_gaps": 0,
            "high_confidence": 0,
        },
    )
    score = score_file(
        write_jsonl(
            tmp_path / "kg-empty.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    assert_dimensions(score, knowledge_growth=0.5)


def test_knowledge_growth_full_session(tmp_path: Path) -> None:
    """Scores growth, gap closure, and confidence correctly."""
    write_state_json(
        tmp_path,
        "knowledge-growth.json",
        {
            "initial_entries": 10,
            "final_entries": 20,
            "initial_gaps": 8,
            "remaining_gaps": 2,
            "high_confidence": 15,
        },
    )
    score = score_file(
        write_jsonl(
            tmp_path / "kg-full.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    # growth_ratio = min((20-10)/max(10,1), 1.0) = 1.0
    # gap_closure = (8-2)/max(8,1) = 0.75
    # confidence_ratio = 15/max(20,1) = 0.75
    # score = 0.4*0.75 + 0.35*0.75 + 0.25*1.0 = 0.3 + 0.2625 + 0.25 = 0.8125
    assert_dimensions(score, knowledge_growth=pytest.approx(0.8125))


def test_knowledge_growth_gaps_regressed(tmp_path: Path) -> None:
    """Gap regression (more gaps than before) returns 0 for gap_closure."""
    write_state_json(
        tmp_path,
        "knowledge-growth.json",
        {
            "initial_entries": 10,
            "final_entries": 10,
            "initial_gaps": 3,
            "remaining_gaps": 5,
            "high_confidence": 5,
        },
    )
    score = score_file(
        write_jsonl(
            tmp_path / "kg-regress.jsonl",
            [result("https://example.com/1", "github", "judge", title="judge")],
        )
    )
    # growth_ratio = 0.0 (no growth)
    # gap_closure = 0.0 (regression)
    # confidence_ratio = 5/10 = 0.5
    # score = 0.4*0 + 0.35*0.5 + 0.25*0 = 0.175
    assert_dimensions(score, knowledge_growth=pytest.approx(0.175))


def test_cli_exit_codes(tmp_path: Path) -> None:
    evidence = write_jsonl(
        tmp_path / "cli.jsonl",
        [result("https://example.com/1", "github", "judge", title="judge")],
    )
    script = Path(judge.__file__)
    success = subprocess.run(
        [sys.executable, str(script), str(evidence)], capture_output=True, text=True
    )
    missing = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "missing.jsonl")],
        capture_output=True,
        text=True,
    )
    assert success.returncode == 0
    payload = json.loads(success.stdout)
    assert payload["meta"]["total_results"] == 1
    assert set(payload["dimensions"]) == DIMENSION_NAMES
    assert missing.returncode == 1
