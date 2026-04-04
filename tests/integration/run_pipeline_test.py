#!/usr/bin/env python3
"""End-to-end pipeline integration test.

Runs real searches across all channels for multiple topics in parallel.
Produces a structured JSONL report with per-channel health, timing,
source diversity, and judge scores.

Usage:
    # Quick (3 topics, 5 queries each, ~2 min)
    python tests/integration/run_pipeline_test.py --mode quick

    # Standard (5 topics, 15 queries each, ~5 min)
    python tests/integration/run_pipeline_test.py --mode standard

    # Full (5 topics, 25 queries each, all channels, ~10 min)
    python tests/integration/run_pipeline_test.py --mode full

Output: tests/integration/reports/YYYYMMDD-HHMMSS-{mode}.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Test topics ──────────────────────────────────────────────────────────

TOPICS = [
    {"id": "t1", "topic": "self-evolving AI agents", "lang": "en"},
    {"id": "t2", "topic": "vector databases for RAG", "lang": "en"},
    {"id": "t3", "topic": "smart wearable market 2026", "lang": "en"},
    {"id": "t4", "topic": "中国大模型生态", "lang": "zh"},
    {"id": "t5", "topic": "production RAG systems", "lang": "en"},
]

# ── Mode configs ─────────────────────────────────────────────────────────

MODES = {
    "quick": {"topics": 3, "queries_per_topic": 5, "channels": 8},
    "standard": {"topics": 5, "queries_per_topic": 15, "channels": 15},
    "full": {"topics": 5, "queries_per_topic": 25, "channels": 32},
}

# ── Channel test queries by category ────────────────────────────────────

CHANNEL_QUERIES = {
    "web-ddgs": "AI search engine 2026",
    "github-repos": "self-evolving agent",
    "github-issues": "vector database performance",
    "github-code": "async search runner python",
    "arxiv": "self-improving search agents",
    "semantic-scholar": "retrieval augmented generation survey",
    "google-scholar": "neural information retrieval",
    "reddit": "best vector database 2026",
    "hn": "AI agent framework",
    "stackoverflow": "asyncio run_in_executor example",
    "twitter": "AI search tool launch",
    "devto": "building RAG pipeline",
    "zhihu": "大模型搜索",
    "bilibili": "AI搜索引擎",
    "csdn": "向量数据库对比",
    "juejin": "RAG应用开发",
    "36kr": "AI创业融资",
    "wechat": "大模型应用",
    "weibo": "AI搜索",
    "xiaohongshu": "AI工具推荐",
    "douyin": "AI产品",
    "xiaoyuzhou": "人工智能播客",
    "xueqiu": "AI概念股",
    "infoq-cn": "大模型架构",
    "youtube": "AI agent tutorial",
    "conference-talks": "retrieval augmented generation",
    "producthunt": "AI research tool",
    "crunchbase": "AI search startup funding",
    "g2": "AI research software review",
    "linkedin": "AI search engineer",
    "npm-pypi": "vector database python",
    "rss": "AI news",
    "citation-graph": "retrieval augmented generation",
    "papers-with-code": "self-evolving agents",
    "openreview": "retrieval augmented generation ICLR",
    "paper-list": "awesome RAG papers",
}


def find_python() -> str:
    """Find the best Python for running search_runner."""
    venv = ROOT / ".venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return "python3"


# ── Channel health check ────────────────────────────────────────────────


async def check_single_channel(channel_name: str, query: str) -> dict:
    """Test one channel, return health record."""
    start = time.monotonic()
    try:
        from channels import load_channels

        channels = load_channels()
        if channel_name not in channels:
            return {
                "channel": channel_name,
                "status": "skip",
                "reason": "not loaded",
                "results": 0,
                "time_ms": 0,
            }

        results = await channels[channel_name](query, 3)
        elapsed = int((time.monotonic() - start) * 1000)

        return {
            "channel": channel_name,
            "status": "ok" if results else "empty",
            "results": len(results),
            "time_ms": elapsed,
            "sample_url": results[0]["url"] if results else None,
            "source_tag": results[0].get("source", "unknown") if results else None,
        }
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "channel": channel_name,
            "status": "error",
            "error": str(exc)[:200],
            "results": 0,
            "time_ms": elapsed,
        }


async def run_channel_health(channels_to_test: list[str]) -> list[dict]:
    """Test all channels in parallel."""
    tasks = []
    for ch in channels_to_test:
        query = CHANNEL_QUERIES.get(ch, "AI technology 2026")
        tasks.append(check_single_channel(ch, query))
    return await asyncio.gather(*tasks)


# ── Search pipeline test ─────────────────────────────────────────────────


def run_search_pipeline(topic: dict, max_queries: int, max_channels: int) -> dict:
    """Run search_runner.py for a topic, return pipeline metrics."""
    start = time.monotonic()

    # Build queries — simple keyword expansion (no LLM needed)
    base = topic["topic"]
    queries = []
    channels_to_use = list(CHANNEL_QUERIES.keys())[:max_channels]

    for ch in channels_to_use:
        if len(queries) >= max_queries:
            break
        queries.append({"channel": ch, "query": base, "max_results": 5})

    # Run search_runner.py
    query_json = json.dumps(queries)
    python = find_python()
    try:
        result = subprocess.run(
            [python, "lib/search_runner.py", query_json],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
    except subprocess.TimeoutExpired:
        return {
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "status": "timeout",
            "time_s": 120,
            "results": 0,
        }

    elapsed = round(time.monotonic() - start, 1)

    # Parse results
    results = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Analyze
    sources = Counter(r.get("source", "unknown") for r in results)
    urls = {r.get("url", "") for r in results}

    # Run judge.py if we have results
    judge_score = None
    if results:
        evidence_path = ROOT / f"tests/integration/tmp/{topic['id']}-evidence.jsonl"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("\n".join(json.dumps(r) for r in results) + "\n")
        try:
            judge_result = subprocess.run(
                [python, "lib/judge.py", str(evidence_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            # Parse judge output for total score
            for line in judge_result.stdout.split("\n"):
                if "total" in line.lower() or "score" in line.lower():
                    try:
                        judge_score = float(line.split(":")[-1].strip())
                    except (ValueError, IndexError):
                        pass
        except (subprocess.TimeoutExpired, Exception):
            pass

    return {
        "topic_id": topic["id"],
        "topic": topic["topic"],
        "lang": topic["lang"],
        "status": "ok" if results else "empty",
        "time_s": elapsed,
        "queries_sent": len(queries),
        "results": len(results),
        "unique_urls": len(urls),
        "unique_sources": len(sources),
        "source_distribution": dict(sources.most_common()),
        "judge_score": judge_score,
        "errors": result.stderr[:500] if result.stderr else None,
    }


# ── Main runner ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="AutoSearch pipeline integration test")
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "full"],
        default="quick",
        help="Test depth (default: quick)",
    )
    args = parser.parse_args()

    config = MODES[args.mode]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = ROOT / "tests/integration/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{ts}-{args.mode}.jsonl"

    print(f"AutoSearch Integration Test — mode: {args.mode}")
    print(
        f"Topics: {config['topics']}, Queries/topic: {config['queries_per_topic']}, Channels: {config['channels']}"
    )
    print(f"Report: {report_path}")
    print()

    records = []

    # ── Phase 1: Channel health ──
    print("Phase 1: Channel health check...")
    channels_to_test = list(CHANNEL_QUERIES.keys())[: config["channels"]]
    health_results = asyncio.run(run_channel_health(channels_to_test))

    ok = sum(1 for h in health_results if h["status"] == "ok")
    empty = sum(1 for h in health_results if h["status"] == "empty")
    errors = sum(1 for h in health_results if h["status"] == "error")
    skipped = sum(1 for h in health_results if h["status"] == "skip")

    print(f"  {ok} ok, {empty} empty, {errors} errors, {skipped} skipped")
    for h in health_results:
        records.append({"type": "channel_health", "ts": ts, "mode": args.mode, **h})
        if h["status"] == "error":
            print(f"  FAIL: {h['channel']} — {h.get('error', '')[:80]}")

    # ── Phase 2: Pipeline tests ──
    print(f"\nPhase 2: Pipeline test ({config['topics']} topics)...")
    topics = TOPICS[: config["topics"]]

    # Run topics in parallel using threads (subprocess is blocking)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pipeline_results = []
    with ThreadPoolExecutor(max_workers=min(config["topics"], 3)) as executor:
        futures = {
            executor.submit(
                run_search_pipeline,
                topic,
                config["queries_per_topic"],
                config["channels"],
            ): topic
            for topic in topics
        }
        for future in as_completed(futures):
            result = future.result()
            pipeline_results.append(result)
            status_icon = "ok" if result["status"] == "ok" else "FAIL"
            print(
                f"  [{status_icon}] {result['topic']}: "
                f"{result['results']} results from {result.get('unique_sources', 0)} channels "
                f"in {result['time_s']}s"
            )

    for r in pipeline_results:
        records.append({"type": "pipeline", "ts": ts, "mode": args.mode, **r})

    # ── Phase 3: Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_results = sum(r.get("results", 0) for r in pipeline_results)
    avg_sources = (
        sum(r.get("unique_sources", 0) for r in pipeline_results)
        / len(pipeline_results)
        if pipeline_results
        else 0
    )
    avg_time = (
        sum(r.get("time_s", 0) for r in pipeline_results) / len(pipeline_results)
        if pipeline_results
        else 0
    )

    summary = {
        "type": "summary",
        "ts": ts,
        "mode": args.mode,
        "channels_tested": len(channels_to_test),
        "channels_ok": ok,
        "channels_error": errors,
        "topics_tested": len(pipeline_results),
        "total_results": total_results,
        "avg_sources_per_topic": round(avg_sources, 1),
        "avg_time_per_topic_s": round(avg_time, 1),
        "pass": ok >= len(channels_to_test) * 0.7 and avg_sources >= 3,
    }

    print(f"Channels: {ok}/{len(channels_to_test)} working ({errors} errors)")
    print(f"Results: {total_results} total, {avg_sources:.1f} avg sources/topic")
    print(f"Time: {avg_time:.1f}s avg per topic")
    print(f"Verdict: {'PASS' if summary['pass'] else 'FAIL'}")

    records.append(summary)

    # ── Write report ──
    with open(report_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"\nReport: {report_path}")

    # Also write latest symlink for easy access
    latest = report_dir / "latest.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(report_path.name)

    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
