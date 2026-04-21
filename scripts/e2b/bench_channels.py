"""F111/F204 channel bench orchestrator.

Runs autosearch Pipeline with one target channel enabled in each sandbox and
collects per-channel health cards. Bypasses the matrix.yaml orchestrator so it
can fan out channels across the sandbox pool cleanly.

Design
------
- One sandbox per (channel). Each sandbox installs autosearch once and runs
  every query in sequence (amortizes install cost).
- Pool size = --parallel (default 15, matches sandbox pool cap).
- Collects JSON from each query, writes per-channel cards + master matrix.

Usage
-----
    python scripts/e2b/bench_channels.py \\
        --tarball /tmp/autosearch-src.tar.gz \\
        --output reports/channels \\
        --parallel 15 \\
        [--channels arxiv,ddgs,...  (default: all T0 available)] \\
        [--mode fast]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from e2b_code_interpreter import Sandbox

# Default T0 (always-on) channels + T1 youtube (needs key)
# T2 (TikHub) can be added via --channels with tikhub key injected
DEFAULT_CHANNELS_T0 = [
    "arxiv",
    "crossref",
    "dblp",
    "ddgs",
    "devto",
    "github",
    "google_news",
    "hackernews",
    "huggingface_hub",
    "infoq_cn",
    "kr36",
    "openalex",
    "package_search",
    "papers",
    "podcast_cn",
    "reddit",
    "sec_edgar",
    "sogou_weixin",
    "stackoverflow",
    "v2ex",
    "wikidata",
    "wikipedia",
]
DEFAULT_CHANNELS_T1 = ["youtube"]  # needs YOUTUBE_API_KEY
DEFAULT_CHANNELS_T2 = [  # needs TIKHUB_API_KEY
    "bilibili",
    "douyin",
    "kuaishou",
    "tiktok",
    "twitter",
    "weibo",
    "xiaohongshu",
    "zhihu",
]

DEFAULT_QUERIES = [
    ("en_tech", "bm25 ranking algorithm explained with formula"),
    ("zh_tech", "向量数据库怎么选 FAISS Qdrant Milvus 对比"),
    ("current", "anthropic claude model release 2026"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tarball", required=True, help="Path to autosearch source tarball")
    p.add_argument("--output", required=True, help="Output directory for reports")
    p.add_argument("--parallel", type=int, default=15, help="Max concurrent sandboxes")
    p.add_argument("--channels", help="Comma-separated channel names (default: T0+T1+T2)")
    p.add_argument("--mode", default="fast", choices=["fast", "deep"])
    p.add_argument("--skip-install-log", action="store_true")
    return p.parse_args()


def build_channel_list(cli_arg: str | None) -> list[str]:
    if cli_arg:
        return [c.strip() for c in cli_arg.split(",") if c.strip()]
    channels = list(DEFAULT_CHANNELS_T0)
    if os.environ.get("YOUTUBE_API_KEY"):
        channels.extend(DEFAULT_CHANNELS_T1)
    if os.environ.get("TIKHUB_API_KEY"):
        channels.extend(DEFAULT_CHANNELS_T2)
    return channels


def collect_secrets() -> dict[str, str]:
    keys = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "YOUTUBE_API_KEY",
        "TIKHUB_API_KEY",
        "AUTOSEARCH_PROXY_URL",
        "AUTOSEARCH_PROXY_TOKEN",
    ]
    return {k: os.environ[k] for k in keys if os.environ.get(k)}


def run_channel_bench(
    channel: str,
    queries: list[tuple[str, str]],
    tarball_path: str,
    secrets: dict[str, str],
    mode: str,
    output_dir: Path,
) -> dict:
    """Single sandbox: install autosearch, run all queries for one channel."""
    log_lines: list[str] = []
    t_overall = time.monotonic()

    def log(msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{stamp}] [{channel}] {msg}"
        log_lines.append(line)
        print(line, flush=True)

    try:
        log("sandbox.create")
        sbx = Sandbox.create("autosearch-claude", timeout=1800, envs=secrets)
    except Exception as exc:
        return {"channel": channel, "status": "sandbox_create_failed", "error": str(exc)}

    try:
        # Upload tarball
        log("upload tarball")
        with open(tarball_path, "rb") as fh:
            sbx.files.write("/tmp/autosearch-src.tar.gz", fh)

        # Install
        log("install autosearch (uv)")
        setup = """
set -e
mkdir -p $HOME/work/autosearch
tar -xzf /tmp/autosearch-src.tar.gz -C $HOME/work/autosearch
curl -LsSf https://astral.sh/uv/install.sh | sh > /tmp/uv-install.log 2>&1
cd $HOME/work/autosearch
$HOME/.local/bin/uv venv --python 3.12 .venv > /tmp/venv.log 2>&1
$HOME/.local/bin/uv pip install --python .venv/bin/python -e . > /tmp/install.log 2>&1
echo install_done
"""
        install_res = sbx.commands.run(setup, timeout=300)
        if install_res.exit_code != 0:
            return {
                "channel": channel,
                "status": "install_failed",
                "exit": install_res.exit_code,
                "stderr_tail": install_res.stderr[-500:],
            }

        # Run each query
        query_results = []
        for qid, qtext in queries:
            log(f"query {qid}: {qtext[:40]}...")
            t0 = time.monotonic()
            cmd = (
                f"cd $HOME/work/autosearch && AUTOSEARCH_BENCH_MODE={mode} "
                f'.venv/bin/python tests/e2b/bench/single_channel_bench.py "{channel}" "{qtext}"'
            )
            res = sbx.commands.run(cmd, timeout=1500 if mode == "deep" else 600, envs=secrets)
            wall = time.monotonic() - t0
            stdout = res.stdout.strip()
            try:
                parsed = json.loads(stdout.splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                parsed = {
                    "channel": channel,
                    "query": qtext,
                    "status": "output_parse_failed",
                    "stdout_tail": stdout[-500:],
                    "stderr_tail": res.stderr[-500:],
                    "exit": res.exit_code,
                }
            parsed["query_id"] = qid
            parsed["sandbox_wall"] = round(wall, 2)
            query_results.append(parsed)
            log(f"query {qid} done wall={wall:.1f}s status={parsed.get('status')}")

        overall_wall = time.monotonic() - t_overall
        result = {
            "channel": channel,
            "status": "ok",
            "mode": mode,
            "queries": query_results,
            "overall_wall_sec": round(overall_wall, 2),
        }
    except Exception as exc:
        result = {
            "channel": channel,
            "status": "exception",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        try:
            sbx.kill()
            log("sandbox killed")
        except Exception:
            pass

    # Persist per-channel card
    card_path = output_dir / "cards" / f"{channel}.json"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(json.dumps(result, indent=2))

    log_path = output_dir / "logs" / f"{channel}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines))

    return result


def aggregate(results: list[dict], output_dir: Path) -> None:
    """Emit channel-leaderboard.md + channel-matrix.json."""
    # Flatten: each row = (channel, query_id, evidence_count, wall, cost, status)
    rows = []
    for r in results:
        if r.get("status") != "ok":
            rows.append(
                {
                    "channel": r["channel"],
                    "query_id": "*",
                    "status": r.get("status"),
                    "error": r.get("error") or r.get("stderr_tail") or "",
                    "evidence_count": None,
                    "wall_time": None,
                    "cost_usd": None,
                }
            )
            continue
        for q in r.get("queries", []):
            rows.append(
                {
                    "channel": r["channel"],
                    "query_id": q.get("query_id"),
                    "status": q.get("status"),
                    "evidence_count": q.get("evidence_count"),
                    "avg_content_len": q.get("avg_content_len"),
                    "unique_urls": q.get("unique_urls"),
                    "markdown_len": q.get("markdown_len"),
                    "wall_time": q.get("wall_time"),
                    "cost_usd": q.get("cost_usd"),
                    "prompt_tokens": q.get("prompt_tokens"),
                    "completion_tokens": q.get("completion_tokens"),
                }
            )

    # Master matrix JSON
    matrix_path = output_dir / "channel-matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "row_count": len(rows),
                "rows": rows,
            },
            indent=2,
        )
    )

    # Leaderboard markdown (grouped by channel, ranked by avg evidence count)
    by_channel: dict[str, list[dict]] = {}
    for row in rows:
        by_channel.setdefault(row["channel"], []).append(row)

    def avg_evidence(entries: list[dict]) -> float:
        valid = [e["evidence_count"] for e in entries if e.get("evidence_count") is not None]
        return sum(valid) / len(valid) if valid else -1

    ranked = sorted(by_channel.items(), key=lambda x: -avg_evidence(x[1]))

    lines = [
        "# Channel health leaderboard",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Channels: {len(by_channel)} | Rows: {len(rows)}",
        "",
        "| Rank | Channel | Avg Evidence | Avg Wall (s) | Empty Rate | Avg Cost | Notes |",
        "|------|---------|--------------|--------------|------------|----------|-------|",
    ]
    for rank, (ch, entries) in enumerate(ranked, 1):
        ev = [e["evidence_count"] for e in entries if e.get("evidence_count") is not None]
        w = [e["wall_time"] for e in entries if e.get("wall_time") is not None]
        c = [e["cost_usd"] for e in entries if e.get("cost_usd") is not None]
        total = len(entries)
        empty = sum(
            1
            for e in entries
            if e.get("status") == "empty_report" or (e.get("evidence_count") == 0)
        )
        non_ok = [e for e in entries if e.get("status") and e.get("status") != "ok"]
        note = non_ok[0].get("status") if non_ok else ""
        ev_str = f"{sum(ev) / len(ev):.1f}" if ev else "NA"
        w_str = f"{sum(w) / len(w):.1f}" if w else "NA"
        c_str = f"${sum(c) / len(c):.3f}" if c else "NA"
        empty_str = f"{empty}/{total}"
        lines.append(f"| {rank} | {ch} | {ev_str} | {w_str} | {empty_str} | {c_str} | {note} |")

    leaderboard_path = output_dir / "channel-leaderboard.md"
    leaderboard_path.write_text("\n".join(lines))

    print("\n=== Aggregated ===")
    print(f"Matrix: {matrix_path}")
    print(f"Leaderboard: {leaderboard_path}")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    channels = build_channel_list(args.channels)
    queries = DEFAULT_QUERIES
    secrets = collect_secrets()

    if not secrets.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not in env", file=sys.stderr)
        return 1
    # E2B_API_KEY is host-side only (used by Sandbox.create), never forwarded
    # into the sandbox env; read it straight from the process environment.
    if not os.environ.get("E2B_API_KEY"):
        print("WARN: E2B_API_KEY not in env; sandbox may fail", file=sys.stderr)

    tarball_path = args.tarball
    if not Path(tarball_path).is_file():
        print(f"ERROR: tarball not found: {tarball_path}", file=sys.stderr)
        return 1

    print(
        f"Bench kickoff: {len(channels)} channels × {len(queries)} queries = {len(channels) * len(queries)} cells"
    )
    print(f"Pool: {args.parallel} | Mode: {args.mode} | Output: {output_dir}")
    print(f"Channels: {', '.join(channels)}")
    print()

    results: list[dict] = []
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {
            pool.submit(
                run_channel_bench,
                channel,
                queries,
                tarball_path,
                secrets,
                args.mode,
                output_dir,
            ): channel
            for channel in channels
        }
        for i, fut in enumerate(as_completed(futures), 1):
            channel = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = {
                    "channel": channel,
                    "status": "future_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            results.append(res)
            print(f"[{i}/{len(channels)}] {channel} → {res.get('status')}")

    wall = time.monotonic() - t0
    print(f"\nAll done. Wall: {wall:.1f}s ({wall / 60:.1f}m)")

    aggregate(results, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
