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
        judge.DEFAULT_WEIGHTS["latency"] * 0.5 + judge.DEFAULT_WEIGHTS["adoption"] * 0.5
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
