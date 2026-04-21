"""F203 variance + F206 fast-vs-deep + F207 cross-provider bench.

Runs autosearch end-to-end multiple times per (topic, config) combo in
parallel E2B sandboxes to capture quality/cost/time variance.

Usage:
    bench_variance.py --tarball TAR --output DIR [--parallel 15] [--runs-per-topic 3] [--mode {fast,deep}]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from e2b_code_interpreter import Sandbox


TOPICS_15 = [
    ("en_tech_rag", "retrieval augmented generation latest survey 2026"),
    ("zh_tech_moe", "MoE 模型工程实践最佳指南"),
    ("en_tech_vdb", "vector database comparison for production RAG"),
    ("zh_tech_kvcache", "Transformer 架构 KV cache 优化方法"),
    ("en_prod_ai_code", "best AI coding assistant comparison 2026"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tarball", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--parallel", type=int, default=15)
    p.add_argument("--runs-per-topic", type=int, default=3, help="K in variance")
    p.add_argument("--mode", default="fast", choices=["fast", "deep"])
    return p.parse_args()


def collect_secrets() -> dict[str, str]:
    # Only forward secrets the sandbox actually needs. E2B_API_KEY is consumed
    # host-side by Sandbox.create and must stay out of sandbox env.
    keys = ["ANTHROPIC_API_KEY"]
    return {k: os.environ[k] for k in keys if os.environ.get(k)}


def run_one(
    topic_id: str,
    query: str,
    run_idx: int,
    tarball_path: str,
    secrets: dict[str, str],
    mode: str,
    output_dir: Path,
) -> dict:
    """One sandbox: install + run single query + collect JSON."""
    cell_id = f"{topic_id}-run{run_idx}"
    t_overall = time.monotonic()

    try:
        sbx = Sandbox.create("autosearch-claude", timeout=1800, envs=secrets)
    except Exception as exc:
        return {
            "cell_id": cell_id,
            "topic_id": topic_id,
            "run_idx": run_idx,
            "status": "sandbox_create_failed",
            "error": str(exc),
        }

    try:
        with open(tarball_path, "rb") as fh:
            sbx.files.write("/tmp/autosearch-src.tar.gz", fh)

        setup = """
set -e
mkdir -p $HOME/work/autosearch
tar -xzf /tmp/autosearch-src.tar.gz -C $HOME/work/autosearch
cd $HOME/work/autosearch
uv venv --python 3.12 .venv > /tmp/venv.log 2>&1
uv pip install --python .venv/bin/python -e . > /tmp/install.log 2>&1
echo install_done
"""
        res = sbx.commands.run(setup, timeout=300)
        if res.exit_code != 0:
            return {
                "cell_id": cell_id,
                "topic_id": topic_id,
                "run_idx": run_idx,
                "status": "install_failed",
                "stderr_tail": res.stderr[-500:],
            }

        t0 = time.monotonic()
        # --json envelope lands on stdout; keep stderr (log noise) separate.
        cmd = (
            f"cd $HOME/work/autosearch && AUTOSEARCH_PROVIDER_CHAIN=anthropic "
            f'.venv/bin/autosearch query "{query}" --mode {mode} --no-stream --json '
            f"2>/tmp/autosearch.stderr"
        )
        q_res = sbx.commands.run(cmd, timeout=1200, envs=secrets)
        wall = time.monotonic() - t0

        # Stdout should now be a clean JSON envelope (possibly preceded by a few
        # non-JSON chars). Try full parse, then fall back to first-brace-to-end.
        stdout = (q_res.stdout or "").strip()
        parsed: dict = {}
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            idx = stdout.find("{")
            if idx >= 0:
                try:
                    parsed = json.loads(stdout[idx:])
                except json.JSONDecodeError:
                    parsed = {}

        result = {
            "cell_id": cell_id,
            "topic_id": topic_id,
            "run_idx": run_idx,
            "query": query,
            "mode": mode,
            "wall_time": round(wall, 2),
            "overall_wall": round(time.monotonic() - t_overall, 2),
            "exit_code": q_res.exit_code,
            "status": "ok" if q_res.exit_code == 0 else "query_failed",
            "markdown_len": len(parsed.get("markdown", "")) if parsed else 0,
            "reference_count": parsed.get("markdown", "").count("[") if parsed else 0,
            "evidences": parsed.get("metadata", {}).get("totalEvidences") if parsed else None,
            "cost_usd": parsed.get("metadata", {}).get("cost") if parsed else None,
            "sources": parsed.get("sources") if parsed else None,
        }
    except Exception as exc:
        result = {
            "cell_id": cell_id,
            "topic_id": topic_id,
            "run_idx": run_idx,
            "status": "exception",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        try:
            sbx.kill()
        except Exception:
            pass

    out = output_dir / "runs" / f"{cell_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str))
    return result


def summarize(results: list[dict], output_dir: Path) -> None:
    by_topic: dict[str, list[dict]] = {}
    for r in results:
        # Future-failed fallbacks emitted by main() have no topic_id; bucket them
        # separately so a worker crash doesn't take down the whole summary pass.
        topic_id = r.get("topic_id", "_orphaned")
        by_topic.setdefault(topic_id, []).append(r)

    lines = [
        "# Variance summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Topics: {len(by_topic)} | Cells: {len(results)}",
        "",
        "| Topic | Runs | OK | Wall p50 (s) | Wall stdev | Markdown p50 chars | Md stdev | Cost p50 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tid, rs in by_topic.items():
        ok_rs = [r for r in rs if r.get("status") == "ok"]
        walls = [r["wall_time"] for r in ok_rs if r.get("wall_time") is not None]
        mds = [r["markdown_len"] for r in ok_rs if r.get("markdown_len") is not None]
        costs = [r["cost_usd"] for r in ok_rs if r.get("cost_usd") is not None]

        def stat(vals):
            if not vals:
                return ("NA", "NA")
            p50 = statistics.median(vals)
            stdev = statistics.stdev(vals) if len(vals) >= 2 else 0.0
            return (f"{p50:.1f}", f"{stdev:.1f}")

        wp50, wsd = stat(walls)
        mdp50, mdsd = stat(mds)
        costs_p50 = f"${statistics.median(costs):.3f}" if costs else "NA"
        lines.append(
            f"| {tid} | {len(rs)} | {len(ok_rs)} | {wp50} | {wsd} | {mdp50} | {mdsd} | {costs_p50} |"
        )

    (output_dir / "variance-summary.md").write_text("\n".join(lines))

    (output_dir / "variance-raw.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_cells": len(results),
                "by_topic": {tid: rs for tid, rs in by_topic.items()},
            },
            indent=2,
            default=str,
        )
    )
    print("\n=== Summary ===")
    print(f"{output_dir}/variance-summary.md")
    print(f"{output_dir}/variance-raw.json")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    secrets = collect_secrets()
    if not secrets.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY missing", file=sys.stderr)
        return 1

    topics = TOPICS_15
    total = len(topics) * args.runs_per_topic
    print(f"Variance bench: {len(topics)} topics × K={args.runs_per_topic} = {total} cells")
    print(f"Pool: {args.parallel} | Mode: {args.mode} | Output: {output_dir}")

    tasks = [(tid, q, r) for tid, q in topics for r in range(args.runs_per_topic)]

    t0 = time.monotonic()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {
            pool.submit(run_one, tid, q, r, args.tarball, secrets, args.mode, output_dir): (
                tid,
                q,
                r,
            )
            for tid, q, r in tasks
        }
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                res = fut.result()
            except Exception as exc:
                res = {"status": "future_failed", "error": str(exc)}
            results.append(res)
            tid = res.get("topic_id", "?")
            ridx = res.get("run_idx", "?")
            status = res.get("status")
            print(f"[{i}/{total}] {tid}#{ridx} -> {status}")

    wall = time.monotonic() - t0
    print(f"\nDone. Wall: {wall:.1f}s ({wall / 60:.1f}m)")
    summarize(results, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
