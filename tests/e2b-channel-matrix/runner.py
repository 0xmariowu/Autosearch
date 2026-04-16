from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.base import ScrapeResult, median_total_ms, synthetic_result
from harness.registry import list_adapters
from harness.scoring import grade, wilson_lower

QUERIES_PATH = ROOT / "queries" / "standard.json"
REPORTS_ROOT = ROOT / "reports"
SMOKE_SAMPLE = [
    ("consumer", "iPhone 16 值得买吗"),
    ("tech", "RAG 架构教程"),
    ("finance", "英伟达财报"),
]


def load_standard_queries() -> list[tuple[str, str]]:
    raw = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    queries: list[tuple[str, str]] = []
    for category, values in raw.items():
        for value in values:
            queries.append((category, value))
    return queries


def dry_run_results() -> list[ScrapeResult]:
    results: list[ScrapeResult] = []
    for adapter in list_adapters():
        for ordinal, (category, query) in enumerate(SMOKE_SAMPLE, start=1):
            results.append(
                synthetic_result(
                    adapter=adapter,
                    query=query,
                    query_category=category,
                    ordinal=ordinal,
                )
            )
    return results


def summarize(results: list[ScrapeResult]) -> dict[str, object]:
    grouped: dict[str, list[ScrapeResult]] = defaultdict(list)
    for result in results:
        grouped[result.path_id].append(result)

    summary: dict[str, object] = {}
    for path_id, adapter_results in grouped.items():
        successes = sum(result.status == "ok" for result in adapter_results)
        total = len(adapter_results)
        avg_content_len = int(
            sum(result.avg_content_len for result in adapter_results) / max(total, 1)
        )
        median_latency = median_total_ms(adapter_results)
        ci_lower = wilson_lower(successes, total)
        summary[path_id] = {
            "samples": total,
            "successes": successes,
            "ci_lower": round(ci_lower, 4),
            "avg_content_len": avg_content_len,
            "median_latency_ms": median_latency,
            "grade": grade(ci_lower, avg_content_len, median_latency, total),
        }
    return summary


def write_reports(results: list[ScrapeResult]) -> Path:
    report_dir = REPORTS_ROOT / date.today().isoformat()
    report_dir.mkdir(parents=True, exist_ok=True)

    raw_path = report_dir / "raw.jsonl"
    raw_path.write_text(
        "\n".join(
            json.dumps(result.model_dump(), ensure_ascii=False) for result in results
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize(results)
    (report_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_lines = ["# Day 1 Smoke Report", ""]
    for path_id, payload in summary.items():
        report_lines.append(
            f"- {path_id}: {payload['grade']} | success={payload['successes']}/{payload['samples']} | "
            f"ci_lower={payload['ci_lower']} | median_latency_ms={payload['median_latency_ms']}"
        )
    (report_dir / "report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    return raw_path


async def smoke_results() -> list[ScrapeResult]:
    from harness.sandbox import run_adapter_batch

    queries = [(query, category) for category, query in SMOKE_SAMPLE]
    tasks = [run_adapter_batch(adapter, queries, reps=1) for adapter in list_adapters()]
    batches = await asyncio.gather(*tasks)
    return [result for batch in batches for result in batch]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="skip E2B sandboxes")
    parser.add_argument(
        "--smoke", action="store_true", help="run the Day 1 smoke suite"
    )
    parser.add_argument("--full", action="store_true", help="reserved for Day 2")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    _ = load_standard_queries()

    if args.full:
        print("Day 1 scope: smoke only")
        return 0

    if args.dry_run:
        results = dry_run_results()
        mode = "dry-run"
    else:
        results = await smoke_results()
        mode = "smoke"

    raw_path = write_reports(results)
    print(f"mode={mode} results={len(results)} raw_report={raw_path}")
    for result in results:
        print(json.dumps(result.model_dump(), ensure_ascii=False))
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
