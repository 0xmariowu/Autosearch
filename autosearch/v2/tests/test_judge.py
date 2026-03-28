import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autosearch.v2 import judge


NOW = dt.datetime(2026, 3, 28, tzinfo=dt.timezone.utc)


def write_jsonl(path: Path, rows: list[object]) -> Path:
    path.write_text(
        "".join(json.dumps(row) + "\n" if isinstance(row, dict) else f"{row}\n" for row in rows),
        encoding="utf-8",
    )
    return path


def result(url: str, source: str, query: str, title: str = "", snippet: str = "", metadata: dict | None = None) -> dict:
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
    return judge.score_results(judge.load_results(path), str(path), target=target, now=NOW)


def test_empty_input(tmp_path: Path) -> None:
    score = score_file(write_jsonl(tmp_path / "empty.jsonl", []))
    assert score["total"] == 0.0
    assert all(value == 0.0 for value in score["dimensions"].values())


def test_single_result(tmp_path: Path) -> None:
    row = result("https://example.com/1", "github", "python judge", title="Python judge")
    score = score_file(write_jsonl(tmp_path / "single.jsonl", [row]))
    assert score["dimensions"]["quantity"] == pytest.approx(1 / 30)
    assert score["dimensions"]["diversity"] == 0.0
    assert score["dimensions"]["relevance"] == 1.0


def test_multi_platform_diversity(tmp_path: Path) -> None:
    rows = [result(f"https://example.com/{idx}", source, "topic", title="topic") for idx, source in enumerate(
        ["github"] * 4 + ["reddit"] * 3 + ["hackernews"] * 3,
        start=1,
    )]
    score = score_file(write_jsonl(tmp_path / "diverse.jsonl", rows))
    assert score["dimensions"]["diversity"] > 0.5


def test_single_platform_low_diversity(tmp_path: Path) -> None:
    rows = [result(f"https://example.com/{idx}", "github", "topic", title="topic") for idx in range(10)]
    score = score_file(write_jsonl(tmp_path / "single-platform.jsonl", rows))
    assert score["dimensions"]["diversity"] == 0.0


def test_relevance_all_match(tmp_path: Path) -> None:
    rows = [result(f"https://example.com/{idx}", "github", "agent search", title="Agent search guide") for idx in range(3)]
    score = score_file(write_jsonl(tmp_path / "all-match.jsonl", rows))
    assert score["dimensions"]["relevance"] == 1.0


def test_relevance_none_match(tmp_path: Path) -> None:
    rows = [result(f"https://example.com/{idx}", "github", "agent search", title="database tuning", snippet="sql indexes") for idx in range(3)]
    score = score_file(write_jsonl(tmp_path / "none-match.jsonl", rows))
    assert score["dimensions"]["relevance"] == 0.0


def test_freshness_all_recent(tmp_path: Path) -> None:
    recent = (NOW - dt.timedelta(days=30)).isoformat().replace("+00:00", "Z")
    rows = [result(f"https://example.com/{idx}", "reddit", "topic", metadata={"published_at": recent}) for idx in range(3)]
    score = score_file(write_jsonl(tmp_path / "fresh.jsonl", rows))
    assert score["dimensions"]["freshness"] == 1.0


def test_freshness_all_old(tmp_path: Path) -> None:
    old = (NOW - dt.timedelta(days=300)).isoformat().replace("+00:00", "Z")
    rows = [result(f"https://example.com/{idx}", "reddit", "topic", metadata={"updated_at": old}) for idx in range(3)]
    score = score_file(write_jsonl(tmp_path / "old.jsonl", rows))
    assert score["dimensions"]["freshness"] == 0.0


def test_freshness_unix_timestamp(tmp_path: Path) -> None:
    recent_ts = int((NOW - dt.timedelta(days=30)).timestamp())
    old_ts = int((NOW - dt.timedelta(days=300)).timestamp())
    rows = [
        result("https://example.com/1", "reddit", "topic", metadata={"created_utc": recent_ts}),
        result("https://example.com/2", "reddit", "topic", metadata={"created_utc": old_ts}),
    ]
    score = score_file(write_jsonl(tmp_path / "unix.jsonl", rows))
    assert score["dimensions"]["freshness"] == 0.5


def test_custom_target(tmp_path: Path) -> None:
    rows = [result(f"https://example.com/{idx}", "github", f"query {idx}", title="query") for idx in range(10)]
    score = score_file(write_jsonl(tmp_path / "target.jsonl", rows), target=10)
    assert score["dimensions"]["quantity"] == 1.0


def test_invalid_json_lines(tmp_path: Path) -> None:
    rows = [
        result("https://example.com/1", "github", "judge", title="judge"),
        "{bad json",
        result("https://example.com/2", "reddit", "judge", title="judge"),
    ]
    score = score_file(write_jsonl(tmp_path / "invalid.jsonl", rows))
    assert score["meta"]["total_results"] == 2
    assert score["meta"]["unique_urls"] == 2


def test_cli_exit_codes(tmp_path: Path) -> None:
    evidence = write_jsonl(tmp_path / "cli.jsonl", [result("https://example.com/1", "github", "judge", title="judge")])
    script = Path(judge.__file__)
    success = subprocess.run([sys.executable, str(script), str(evidence)], capture_output=True, text=True)
    missing = subprocess.run([sys.executable, str(script), str(tmp_path / "missing.jsonl")], capture_output=True, text=True)
    assert success.returncode == 0
    assert json.loads(success.stdout)["meta"]["total_results"] == 1
    assert missing.returncode == 1
