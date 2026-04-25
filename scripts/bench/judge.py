"""Pairwise judge for autosearch benchmarks.

Usage:
    python scripts/bench/judge.py pairwise \\
        --a-dir reports/run-A/reports \\
        --b-dir reports/run-B/reports \\
        --a-label augmented --b-label bare \\
        --output-dir reports/judge-A-vs-B \\
        [--parallel 8] [--model claude-sonnet-4-6]

For each filename that exists in both --a-dir and --b-dir, sends both reports
to the Anthropic Claude API with randomized A/B ordering and asks for a
pairwise winner. Writes per-pair JSON verdicts plus a summary markdown.

Requires `ANTHROPIC_API_KEY` env var.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
from datetime import UTC, datetime
import json
import os
import random
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Iterable

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PARALLEL = 4
ROOT = Path(__file__).resolve().parents[2]
PAIRWISE_PROMPT = """You are judging two research reports that answer the same question.

Read both reports carefully. Decide which one answers the question better.

Criteria (in order):
1. Concrete specifics — numbers, error codes, issue numbers, benchmarks, named entities, working code — beats vague summaries.
2. Accuracy — demonstrably correct statements beat plausible but wrong ones.
3. Coverage — answering more angles of the question beats answering fewer.
4. Structure — clear organization beats a wall of text.

If one report is clearly better, pick it. If they are roughly equivalent, reply tie.

Respond ONLY with a JSON object of exactly this shape:
{"preferred": 1, "reason": "one-sentence explanation"}
or
{"preferred": 2, "reason": "one-sentence explanation"}
or
{"preferred": null, "reason": "one-sentence explanation"}
"""


@dataclasses.dataclass(frozen=True)
class PairInput:
    name: str
    a_text: str
    b_text: str


@dataclasses.dataclass
class PairVerdict:
    name: str
    winner: str  # "a", "b", or "tie"
    reason: str
    swapped: bool  # whether A was presented as position 2 to the judge
    raw_response: str = ""


def discover_pairs(a_dir: Path, b_dir: Path) -> list[PairInput]:
    a_files = {p.name: p for p in sorted(a_dir.glob("*.md"))}
    b_files = {p.name: p for p in sorted(b_dir.glob("*.md"))}
    common = sorted(a_files.keys() & b_files.keys())
    pairs: list[PairInput] = []
    for name in common:
        pairs.append(
            PairInput(
                name=name,
                a_text=a_files[name].read_text(encoding="utf-8"),
                b_text=b_files[name].read_text(encoding="utf-8"),
            )
        )
    return pairs


def build_judge_message(
    question_hint: str,
    first_report: str,
    second_report: str,
) -> list[dict[str, object]]:
    body = (
        f"{PAIRWISE_PROMPT}\n\n"
        f"<question>\n{question_hint}\n</question>\n\n"
        f"<report_1>\n{first_report}\n</report_1>\n\n"
        f"<report_2>\n{second_report}\n</report_2>\n"
    )
    return [{"role": "user", "content": body}]


def parse_judge_response(raw: str) -> tuple[int | None, str]:
    """Extract the JSON verdict from the model response.

    Returns (preferred_position, reason) where preferred_position is 1, 2, or None (tie).
    """
    # Model often returns just a JSON object; also tolerate fenced code blocks.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, "malformed judge response"
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None, "malformed judge JSON"
    preferred = payload.get("preferred")
    reason = str(payload.get("reason") or "")
    if preferred in (1, 2):
        return int(preferred), reason
    return None, reason or "tie"


def judge_pair(
    pair: PairInput,
    *,
    a_label: str,
    b_label: str,
    model: str,
    api_key: str,
    http_client: httpx.Client | None = None,
    rng: random.Random | None = None,
    max_tokens: int = 400,
) -> PairVerdict:
    rng = rng or random.Random(pair.name)
    swap = rng.random() < 0.5
    first_report = pair.b_text if swap else pair.a_text
    second_report = pair.a_text if swap else pair.b_text
    question_hint = f"See filename: {pair.name}. Judge which report answers the underlying research question better."

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": build_judge_message(question_hint, first_report, second_report),
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    client = http_client or httpx.Client(timeout=120.0)
    try:
        response = client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
    finally:
        if http_client is None:
            client.close()

    raw_text = ""
    if response.status_code >= 400:
        reason = f"judge_api_error status={response.status_code} body={response.text[:200]}"
        return PairVerdict(
            name=pair.name, winner="tie", reason=reason, swapped=swap, raw_response=response.text
        )

    try:
        body = response.json()
    except ValueError:
        return PairVerdict(
            name=pair.name,
            winner="tie",
            reason="judge_api_non_json",
            swapped=swap,
            raw_response=response.text,
        )

    content = body.get("content") or []
    text_chunks = [chunk.get("text", "") for chunk in content if isinstance(chunk, dict)]
    raw_text = "".join(text_chunks).strip()
    preferred, reason = parse_judge_response(raw_text)

    if preferred is None:
        winner = "tie"
    elif preferred == 1:
        winner = b_label if swap else a_label
    else:  # preferred == 2
        winner = a_label if swap else b_label

    if winner == a_label:
        winner_code = "a"
    elif winner == b_label:
        winner_code = "b"
    else:
        winner_code = "tie"

    return PairVerdict(
        name=pair.name,
        winner=winner_code,
        reason=reason,
        swapped=swap,
        raw_response=raw_text,
    )


def summarize(verdicts: Iterable[PairVerdict], a_label: str, b_label: str) -> dict[str, object]:
    verdicts_list = list(verdicts)
    total = len(verdicts_list)
    a_wins = sum(1 for v in verdicts_list if v.winner == "a")
    b_wins = sum(1 for v in verdicts_list if v.winner == "b")
    ties = sum(1 for v in verdicts_list if v.winner == "tie")
    a_win_rate = a_wins / total if total else 0.0
    b_win_rate = b_wins / total if total else 0.0
    return {
        "total": total,
        "a_label": a_label,
        "b_label": b_label,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "a_win_rate": a_win_rate,
        "b_win_rate": b_win_rate,
    }


def current_commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    return result.stdout.strip()


def current_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def add_report_metadata(
    stats: dict[str, object],
    *,
    model: str,
    parallel: int,
    a_dir: Path,
    b_dir: Path,
) -> dict[str, object]:
    return {
        **stats,
        "commit_sha": current_commit_sha(),
        "version": current_version(),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "test_config": {
            "model": model,
            "parallel": parallel,
            "sample_size": stats["total"],
            "a_label": stats["a_label"],
            "b_label": stats["b_label"],
            "a_dir": str(a_dir),
            "b_dir": str(b_dir),
        },
    }


def render_summary_markdown(stats: dict[str, object], verdicts: list[PairVerdict]) -> str:
    lines = [
        f"# Pairwise judge summary — {stats['a_label']} vs {stats['b_label']}",
        "",
        f"- total pairs: {stats['total']}",
        f"- **{stats['a_label']}** wins: {stats['a_wins']} ({float(stats['a_win_rate']):.2%})",
        f"- **{stats['b_label']}** wins: {stats['b_wins']} ({float(stats['b_win_rate']):.2%})",
        f"- ties: {stats['ties']}",
        "",
        "## Per-pair verdicts",
        "",
        "| Pair | Winner | Swapped | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for v in verdicts:
        reason_clean = v.reason.replace("|", "\\|").replace("\n", " ")[:160]
        winner_label = {
            "a": str(stats["a_label"]),
            "b": str(stats["b_label"]),
            "tie": "tie",
        }[v.winner]
        lines.append(
            f"| {v.name} | {winner_label} | {'yes' if v.swapped else 'no'} | {reason_clean} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="judge.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pw = subparsers.add_parser("pairwise", help="Pairwise judge two directories of reports.")
    pw.add_argument("--a-dir", type=Path, required=True)
    pw.add_argument("--b-dir", type=Path, required=True)
    pw.add_argument("--a-label", type=str, default="a")
    pw.add_argument("--b-label", type=str, default="b")
    pw.add_argument("--output-dir", type=Path, required=True)
    pw.add_argument("--model", type=str, default=DEFAULT_MODEL)
    pw.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)

    args = parser.parse_args(argv)

    if args.command != "pairwise":  # pragma: no cover - argparse guarantees subcommand
        parser.error("unknown command")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    pairs = discover_pairs(args.a_dir, args.b_dir)
    if not pairs:
        print(
            f"error: no overlapping .md files between {args.a_dir} and {args.b_dir}",
            file=sys.stderr,
        )
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    verdicts: list[PairVerdict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as executor:
        futures = {
            executor.submit(
                judge_pair,
                pair,
                a_label=args.a_label,
                b_label=args.b_label,
                model=args.model,
                api_key=api_key,
            ): pair
            for pair in pairs
        }
        for future in concurrent.futures.as_completed(futures):
            verdict = future.result()
            verdicts.append(verdict)

    verdicts.sort(key=lambda v: v.name)

    for verdict in verdicts:
        verdict_path = args.output_dir / f"pair__{verdict.name.replace('/', '_')}.json"
        verdict_path.write_text(
            json.dumps(dataclasses.asdict(verdict), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    stats = add_report_metadata(
        summarize(verdicts, args.a_label, args.b_label),
        model=args.model,
        parallel=args.parallel,
        a_dir=args.a_dir,
        b_dir=args.b_dir,
    )
    (args.output_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "pairwise-summary.md").write_text(
        render_summary_markdown(stats, verdicts),
        encoding="utf-8",
    )

    print(
        f"{args.a_label}: {stats['a_wins']}/{stats['total']} "
        f"({float(stats['a_win_rate']):.1%})  |  "
        f"{args.b_label}: {stats['b_wins']}/{stats['total']} "
        f"({float(stats['b_win_rate']):.1%})  |  "
        f"ties: {stats['ties']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
