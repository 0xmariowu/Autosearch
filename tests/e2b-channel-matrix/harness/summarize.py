"""Aggregate smoke-full.jsonl into health-matrix.json + markdown tables.

Usage: .venv/bin/python tests/e2b-channel-matrix/harness/summarize.py reports/2026-04-16/smoke-full.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def load_results(path: Path) -> list[dict]:
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def by_platform(results: list[dict]) -> dict[str, dict[str, list[dict]]]:
    buckets: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        buckets[r["platform"]][r["path_id"]].append(r)
    return buckets


def adapter_summary(runs: list[dict]) -> dict:
    n = len(runs)
    status_counts = defaultdict(int)
    for r in runs:
        status_counts[r.get("status", "unknown")] += 1
    avg_items = sum(r.get("items_returned", 0) or 0 for r in runs) / max(n, 1)
    avg_len = sum(r.get("avg_content_len", 0) or 0 for r in runs) / max(n, 1)
    avg_ms = sum(r.get("total_ms", 0) or 0 for r in runs) / max(n, 1)
    ok = status_counts.get("ok", 0)
    ok_rate = ok / n if n else 0
    primary_status = (
        max(status_counts.items(), key=lambda kv: kv[1])[0]
        if status_counts
        else "unknown"
    )
    return {
        "runs": n,
        "ok_rate": round(ok_rate, 2),
        "status_counts": dict(status_counts),
        "primary_status": primary_status,
        "avg_items_returned": round(avg_items, 1),
        "avg_content_len": int(avg_len),
        "avg_total_ms": int(avg_ms),
        "sample_errors": list({r.get("error") for r in runs if r.get("error")})[:2],
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: summarize.py <jsonl>", file=sys.stderr)
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 2

    results = load_results(src)
    grouped = by_platform(results)
    matrix: dict[str, dict] = {}
    for platform, adapters in sorted(grouped.items()):
        platform_entry = {}
        for path_id, runs in sorted(adapters.items()):
            platform_entry[path_id] = adapter_summary(runs)
        matrix[platform] = platform_entry

    out_dir = src.parent
    matrix_path = out_dir / "health-matrix.json"
    matrix_path.write_text(
        json.dumps(
            {"source": str(src), "adapters": matrix}, ensure_ascii=False, indent=2
        )
    )

    md_lines = [
        f"# v2 Health Matrix ({src.name})",
        "",
        "| platform | path_id | primary_status | ok_rate | items | content_len | ms | sample_error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    totals = defaultdict(int)
    for platform, adapters in matrix.items():
        for path_id, s in sorted(
            adapters.items(), key=lambda kv: (-kv[1]["ok_rate"], kv[0])
        ):
            totals[s["primary_status"]] += 1
            err = ""
            if s["sample_errors"]:
                err = (s["sample_errors"][0] or "")[:60]
            md_lines.append(
                f"| {platform} | {path_id} | {s['primary_status']} | {s['ok_rate']} | "
                f"{s['avg_items_returned']} | {s['avg_content_len']} | {s['avg_total_ms']} | {err} |"
            )
    md_lines.append("")
    md_lines.append("## Totals")
    md_lines.append("")
    total_adapters = sum(totals.values())
    for status, count in sorted(totals.items(), key=lambda kv: -kv[1]):
        pct = round(100 * count / total_adapters, 1) if total_adapters else 0
        md_lines.append(f"- {status}: {count} ({pct}%)")

    md_path = out_dir / "health-matrix.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"wrote {matrix_path}")
    print(f"wrote {md_path}")
    print(f"total adapters: {total_adapters}")
    for status, count in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
