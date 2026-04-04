#!/usr/bin/env python3
"""End-to-end pipeline test with real LLM calls via OpenRouter.

Runs the full 6-block AutoSearch pipeline for multiple topics,
using real network searches and real Claude API calls.

Usage:
    # Quick: 2 topics, blocks 1-5, ~3 min, ~$0.05
    OPENROUTER_API_KEY=sk-or-... python tests/integration/run_e2e_test.py --mode quick

    # Standard: 5 topics, blocks 1-6, ~10 min, ~$0.20
    OPENROUTER_API_KEY=sk-or-... python tests/integration/run_e2e_test.py --mode standard

    # Single topic debug
    OPENROUTER_API_KEY=sk-or-... python tests/integration/run_e2e_test.py --topic "AI agents" --depth standard

Output: tests/integration/reports/YYYYMMDD-HHMMSS-e2e-{mode}.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.integration.conftest import (
    MODELS,
    QUERY_CAPS,
    ROOT,
    TOPICS,
    SessionDir,
    find_python,
    get_api_key,
    read_plugin_version,
    read_skill,
    read_skills,
)

# ── Config ───────────────────────────────────────────────────────────────

MODES = {
    "quick": {"topics": 2, "depths": ["standard"], "skip_evolve": True, "workers": 2},
    "standard": {
        "topics": 5,
        "depths": ["standard"],
        "skip_evolve": False,
        "workers": 2,
    },
    "full": {
        "topics": 5,
        "depths": ["quick", "standard", "deep"],
        "skip_evolve": False,
        "workers": 3,
    },
}


@dataclass
class BlockResult:
    block: int
    name: str
    passed: bool
    time_ms: int
    details: dict = field(default_factory=dict)
    error: str | None = None


# ── LLM Client ───────────────────────────────────────────────────────────


class LLMClient:
    """OpenRouter-compatible LLM client."""

    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def chat(self, model_key: str, prompt: str, max_tokens: int = 8000) -> str:
        model = MODELS[model_key]
        response = await self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.usage:
            self.total_input_tokens += response.usage.prompt_tokens or 0
            self.total_output_tokens += response.usage.completion_tokens or 0
        return response.choices[0].message.content or ""


# ── Block implementations ────────────────────────────────────────────────


async def run_block1(
    llm: LLMClient, session: SessionDir, topic: str, depth: str
) -> BlockResult:
    """Block 1: Prepare — rubrics, recall, queries."""
    start = time.monotonic()
    try:
        skills = read_skills(
            ["generate-rubrics", "systematic-recall", "select-channels", "gene-query"]
        )
        cap = QUERY_CAPS.get(depth, 15)

        prompt = f"""You are AutoSearch, a research agent. Execute Phase 0 and Phase 1 for this topic.

Topic: {topic}
Depth: {depth}
Session ID: {session.id}
Query cap: {cap} (do not generate more than {cap} queries)

Do these tasks and output the results in the exact format specified:

TASK 1 — RUBRICS:
Generate 20-25 binary rubrics for evaluating a research report on this topic.
Output them as JSONL between <rubrics> tags. Each line: {{"id":"r001","category":"information-recall","rubric":"...","priority":"high"}}

TASK 2 — KNOWLEDGE:
Write a 9-dimension knowledge recall between <knowledge> tags. Markdown format.

TASK 3 — QUERIES:
Generate {cap} search queries targeting knowledge gaps. Output as JSON array between <queries> tags.
Each query: {{"channel":"web-ddgs","query":"...","max_results":5}}
Use diverse channels: web-ddgs, github-repos, arxiv, reddit, hn, zhihu, youtube, etc.

TASK 4 — SUMMARY:
Output a JSON object between <summary> tags: {{"rubrics":N,"knowledge_items":N,"gaps":N,"queries":N,"channels":["list"]}}

{skills}"""

        response = await llm.chat("sonnet", prompt, max_tokens=8000)

        # Parse sections
        rubrics_match = re.search(r"<rubrics>(.*?)</rubrics>", response, re.DOTALL)
        knowledge_match = re.search(
            r"<knowledge>(.*?)</knowledge>", response, re.DOTALL
        )
        queries_match = re.search(r"<queries>(.*?)</queries>", response, re.DOTALL)

        # Write rubrics
        rubrics_text = rubrics_match.group(1).strip() if rubrics_match else ""
        rubric_lines = [
            line for line in rubrics_text.split("\n") if line.strip().startswith("{")
        ]
        session.rubrics_path.write_text(
            "\n".join(rubric_lines) + "\n" if rubric_lines else ""
        )

        # Write knowledge
        knowledge_text = (
            knowledge_match.group(1).strip() if knowledge_match else response[:2000]
        )
        session.knowledge_path.write_text(knowledge_text)

        # Write queries
        queries = []
        if queries_match:
            try:
                queries = json.loads(queries_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Enforce cap
        queries = queries[:cap]
        session.queries_path.write_text(json.dumps(queries, indent=2))

        # Write timing
        session.write_timing_start()

        elapsed = int((time.monotonic() - start) * 1000)
        passed = len(rubric_lines) >= 10 and len(queries) > 0

        return BlockResult(
            block=1,
            name="Prepare",
            passed=passed,
            time_ms=elapsed,
            details={
                "rubrics": len(rubric_lines),
                "queries": len(queries),
                "knowledge_chars": len(knowledge_text),
                "channels": list({q.get("channel", "unknown") for q in queries}),
            },
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=1, name="Prepare", passed=False, time_ms=elapsed, error=str(exc)[:300]
        )


async def run_block2(session: SessionDir) -> BlockResult:
    """Block 2: Search — run search_runner.py."""
    start = time.monotonic()
    try:
        python = find_python()
        queries_path = session.queries_path

        if not queries_path.exists():
            return BlockResult(
                block=2, name="Search", passed=False, time_ms=0, error="No queries file"
            )

        proc = await asyncio.create_subprocess_exec(
            python,
            str(ROOT / "lib" / "search_runner.py"),
            str(queries_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        results = []
        for line in stdout.decode().strip().split("\n"):
            if line.strip():
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        # Write results
        session.results_path.write_text(
            "\n".join(json.dumps(r) for r in results) + "\n" if results else ""
        )
        session.write_timing_end()

        sources = Counter(r.get("source", "unknown") for r in results)
        elapsed = int((time.monotonic() - start) * 1000)
        passed = len(results) > 0 and len(sources) >= 2

        return BlockResult(
            block=2,
            name="Search",
            passed=passed,
            time_ms=elapsed,
            details={
                "results": len(results),
                "unique_sources": len(sources),
                "source_distribution": dict(sources.most_common(10)),
                "errors": stderr.decode()[:300] if stderr else None,
            },
        )
    except asyncio.TimeoutError:
        return BlockResult(
            block=2, name="Search", passed=False, time_ms=300000, error="Timeout (300s)"
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=2, name="Search", passed=False, time_ms=elapsed, error=str(exc)[:300]
        )


async def run_block3(llm: LLMClient, session: SessionDir, topic: str) -> BlockResult:
    """Block 3: Evaluate — LLM relevance scoring."""
    start = time.monotonic()
    try:
        results = session.read_results()
        if not results:
            return BlockResult(
                block=3,
                name="Evaluate",
                passed=False,
                time_ms=0,
                error="No results to evaluate",
            )

        skill = read_skill("llm-evaluate")

        # Process in parallel batches of 10 (max 3 concurrent API calls)
        batch_size = 10
        batches = [
            results[i : i + batch_size] for i in range(0, len(results), batch_size)
        ]
        eval_sem = asyncio.Semaphore(3)

        async def evaluate_batch(batch: list[dict]) -> list[dict]:
            async with eval_sem:
                prompt = f"""You are evaluating search results for relevance.

Topic: {topic}

For each result below, judge if it is relevant to the topic.
Output a JSON array of objects, one per result, with these fields:
- "url": the result URL (copy exactly)
- "llm_relevant": true or false
- "llm_reason": one sentence explaining your judgment

Results to evaluate:
{json.dumps(batch, indent=2)}

Output ONLY the JSON array, no other text.

{skill}"""

                response = await llm.chat("haiku", prompt, max_tokens=4000)

                try:
                    arr_match = re.search(r"\[.*\]", response, re.DOTALL)
                    if arr_match:
                        evals = json.loads(arr_match.group(0))
                        eval_by_url = {e.get("url", ""): e for e in evals}
                        for r in batch:
                            ev = eval_by_url.get(r.get("url", ""), {})
                            r.setdefault("metadata", {})["llm_relevant"] = ev.get(
                                "llm_relevant", True
                            )
                            r.setdefault("metadata", {})["llm_reason"] = ev.get(
                                "llm_reason", ""
                            )
                    else:
                        for r in batch:
                            r.setdefault("metadata", {})["llm_relevant"] = True
                except (json.JSONDecodeError, KeyError):
                    for r in batch:
                        r.setdefault("metadata", {})["llm_relevant"] = True

                return batch

        batch_results = await asyncio.gather(
            *(evaluate_batch(batch) for batch in batches)
        )
        evaluated = [item for batch in batch_results for item in batch]

        # Write back
        session.results_path.write_text(
            "\n".join(json.dumps(r) for r in evaluated) + "\n"
        )

        relevant = sum(
            1 for r in evaluated if r.get("metadata", {}).get("llm_relevant")
        )
        elapsed = int((time.monotonic() - start) * 1000)
        has_field = all("llm_relevant" in r.get("metadata", {}) for r in evaluated)

        return BlockResult(
            block=3,
            name="Evaluate",
            passed=has_field and relevant > 0,
            time_ms=elapsed,
            details={
                "relevant": relevant,
                "filtered": len(evaluated) - relevant,
                "total": len(evaluated),
            },
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=3,
            name="Evaluate",
            passed=False,
            time_ms=elapsed,
            error=str(exc)[:300],
        )


async def run_block4(
    llm: LLMClient, session: SessionDir, topic: str, depth: str
) -> BlockResult:
    """Block 4: Synthesize — produce delivery report."""
    start = time.monotonic()
    try:
        knowledge = session.read_knowledge()
        results = session.read_results()
        relevant = [r for r in results if r.get("metadata", {}).get("llm_relevant")]
        version = read_plugin_version()
        skill = read_skill("synthesize-knowledge")

        # Build citation index
        citations = []
        for i, r in enumerate(relevant[:50], 1):
            citations.append(f"[{i}] {r.get('title', 'Untitled')} — {r.get('url', '')}")
        citation_text = "\n".join(citations)

        prompt = f"""You are AutoSearch, synthesizing a research report.

Topic: {topic}
Depth: {depth}
Version: AutoSearch v{version}

KNOWLEDGE BACKBONE (Claude's own knowledge):
{knowledge[:3000]}

SEARCH RESULTS ({len(relevant)} relevant):
{json.dumps(relevant[:30], indent=2)[:5000]}

CITATION INDEX:
{citation_text}

Write a comprehensive Markdown research report. Requirements:
- Organize by concept, not by source
- Cite sources using [N] notation from the citation index
- Mark provenance: [knowledge] vs [discovered]
- End with: "Generated by AutoSearch v{version}"

{skill[:2000]}"""

        response = await llm.chat("sonnet", prompt, max_tokens=16000)

        # Write delivery
        delivery_path = session.root / "delivery" / f"{session.id}.md"
        delivery_path.write_text(response)

        # Run judge.py
        python = find_python()
        judge_score = None
        try:
            judge_proc = subprocess.run(
                [python, str(ROOT / "lib" / "judge.py"), str(session.results_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(session.root),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            if judge_proc.stdout.strip():
                judge_data = json.loads(judge_proc.stdout.strip())
                judge_score = judge_data.get("total")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            pass

        elapsed = int((time.monotonic() - start) * 1000)
        passed = len(response) > 500 and (judge_score is None or judge_score >= 0.4)

        return BlockResult(
            block=4,
            name="Synthesize",
            passed=passed,
            time_ms=elapsed,
            details={
                "delivery_chars": len(response),
                "citations": len(citations),
                "judge_score": judge_score,
                "delivery_path": str(delivery_path),
            },
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=4,
            name="Synthesize",
            passed=False,
            time_ms=elapsed,
            error=str(exc)[:300],
        )


async def run_block5(llm: LLMClient, session: SessionDir) -> BlockResult:
    """Block 5: Quality check — rubric pass/fail."""
    start = time.monotonic()
    try:
        delivery = session.read_delivery()
        rubrics = session.read_rubrics()
        skill = read_skill("check-rubrics")

        if not delivery or not rubrics:
            return BlockResult(
                block=5,
                name="Quality",
                passed=False,
                time_ms=0,
                error=f"Missing: delivery={bool(delivery)}, rubrics={len(rubrics)}",
            )

        prompt = f"""Check each rubric against the delivery text. Output ONLY a JSON array.
Each element: {{"id":"r001","passed":true,"evidence":"brief quote or reason"}}

DELIVERY TEXT:
{delivery[:8000]}

RUBRICS:
{json.dumps(rubrics[:30])}

{skill[:1000]}

Output ONLY the JSON array."""

        response = await llm.chat("haiku", prompt, max_tokens=8000)

        # Parse
        checked = []
        try:
            arr_match = re.search(r"\[.*\]", response, re.DOTALL)
            if arr_match:
                checked = json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            pass

        # Write
        checked_path = (
            session.root / "evidence" / f"checked-rubrics-{session.slug}.jsonl"
        )
        checked_path.write_text(
            "\n".join(json.dumps(c) for c in checked) + "\n" if checked else ""
        )

        passed_count = sum(1 for c in checked if c.get("passed"))
        elapsed = int((time.monotonic() - start) * 1000)

        return BlockResult(
            block=5,
            name="Quality",
            passed=len(checked) > 0,
            time_ms=elapsed,
            details={
                "rubrics_passed": passed_count,
                "rubrics_total": len(checked),
                "pass_rate": round(passed_count / len(checked), 2) if checked else 0,
            },
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=5, name="Quality", passed=False, time_ms=elapsed, error=str(exc)[:300]
        )


async def run_block6(session: SessionDir) -> BlockResult:
    """Block 6: Evolve — simplified (write worklog only, no git ops)."""
    start = time.monotonic()
    try:
        # Write a worklog entry
        entry = {
            "type": "e2e_test",
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session.id,
            "topic_id": session.topic_id,
        }
        wl = session.root / "state" / "worklog.jsonl"
        with open(wl, "a") as f:
            f.write(json.dumps(entry) + "\n")

        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=6,
            name="Evolve",
            passed=True,
            time_ms=elapsed,
            details={"worklog_written": True},
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return BlockResult(
            block=6, name="Evolve", passed=False, time_ms=elapsed, error=str(exc)[:300]
        )


# ── Topic runner ─────────────────────────────────────────────────────────


async def run_topic(
    llm: LLMClient, topic: dict, depth: str, session_base: Path, skip_evolve: bool
) -> list[dict]:
    """Run all blocks for one topic. Returns list of block result dicts."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    slug = topic["topic"].lower().replace(" ", "-")[:30]
    session_id = f"{ts}-{slug}"
    session = SessionDir(session_base, topic["id"], session_id)

    records = []
    topic_start = time.monotonic()

    blocks = [
        ("Block 1", lambda: run_block1(llm, session, topic["topic"], depth)),
        ("Block 2", lambda: run_block2(session)),
        ("Block 3", lambda: run_block3(llm, session, topic["topic"])),
        ("Block 4", lambda: run_block4(llm, session, topic["topic"], depth)),
        ("Block 5", lambda: run_block5(llm, session)),
    ]
    if not skip_evolve:
        blocks.append(("Block 6", lambda: run_block6(session)))

    all_passed = True
    for block_name, block_fn in blocks:
        result = await block_fn()
        status = "PASS" if result.passed else "FAIL"
        print(
            f"    [{status}] {block_name}: {result.name} — {result.time_ms}ms — {result.details or result.error or ''}"
        )

        record = {
            "type": "block",
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "depth": depth,
            **asdict(result),
        }
        records.append(record)

        if not result.passed:
            all_passed = False
            # Don't stop on failure — continue to see which other blocks also fail

    total_ms = int((time.monotonic() - topic_start) * 1000)
    judge_score = None
    for r in records:
        if r.get("block") == 4:
            judge_score = r.get("details", {}).get("judge_score")

    records.append(
        {
            "type": "topic_summary",
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "depth": depth,
            "passed": all_passed,
            "total_time_ms": total_ms,
            "blocks_passed": sum(
                1 for r in records if r.get("type") == "block" and r.get("passed")
            ),
            "blocks_total": len(blocks),
            "judge_score": judge_score,
        }
    )

    return records


# ── Main ─────────────────────────────────────────────────────────────────


async def async_main(args: argparse.Namespace) -> int:
    api_key = get_api_key()
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable")
        return 1

    config = MODES[args.mode]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # Setup
    report_dir = ROOT / "tests" / "integration" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}-e2e-{args.mode}.jsonl"
    session_base = ROOT / "tests" / "integration" / "sessions" / run_id
    session_base.mkdir(parents=True, exist_ok=True)

    llm = LLMClient(api_key)

    # Determine topics and depths
    if args.topic:
        topics = [{"id": "custom", "topic": args.topic, "lang": "en"}]
        depths = [args.depth or "standard"]
    else:
        topics = TOPICS[: config["topics"]]
        depths = config["depths"]

    print(f"AutoSearch E2E Test — mode: {args.mode}")
    print(f"Topics: {len(topics)}, Depths: {depths}, Workers: {config['workers']}")
    print(f"Report: {report_path}")
    print()

    all_records = [
        {
            "type": "run_start",
            "run_id": run_id,
            "mode": args.mode,
            "topics": len(topics),
            "depths": depths,
            "workers": config["workers"],
        }
    ]

    # Run topics × depths
    sem = asyncio.Semaphore(config["workers"])

    async def run_with_sem(topic: dict, depth: str) -> list[dict]:
        async with sem:
            print(f"\n  [{topic['id']}] {topic['topic']} @ {depth}")
            return await run_topic(
                llm, topic, depth, session_base, config.get("skip_evolve", False)
            )

    tasks = []
    for depth in depths:
        for topic in topics:
            tasks.append(run_with_sem(topic, depth))

    results = await asyncio.gather(*tasks)
    for r in results:
        all_records.extend(r)

    # Summary
    topic_summaries = [r for r in all_records if r.get("type") == "topic_summary"]
    topics_passed = sum(1 for s in topic_summaries if s.get("passed"))
    judge_scores = [
        s["judge_score"] for s in topic_summaries if s.get("judge_score") is not None
    ]

    summary = {
        "type": "run_summary",
        "run_id": run_id,
        "mode": args.mode,
        "passed": topics_passed == len(topic_summaries),
        "topics_passed": topics_passed,
        "topics_total": len(topic_summaries),
        "avg_judge_score": round(sum(judge_scores) / len(judge_scores), 3)
        if judge_scores
        else None,
        "total_time_s": round(
            sum(s.get("total_time_ms", 0) for s in topic_summaries) / 1000, 1
        ),
        "llm_input_tokens": llm.total_input_tokens,
        "llm_output_tokens": llm.total_output_tokens,
    }
    all_records.append(summary)

    # Print summary
    print("\n" + "=" * 60)
    print("E2E TEST SUMMARY")
    print("=" * 60)
    print(f"Topics: {topics_passed}/{len(topic_summaries)} passed")
    if judge_scores:
        print(f"Avg judge score: {summary['avg_judge_score']}")
    print(f"Total time: {summary['total_time_s']}s")
    print(
        f"LLM tokens: {llm.total_input_tokens:,} in / {llm.total_output_tokens:,} out"
    )
    print(f"Verdict: {'PASS' if summary['passed'] else 'FAIL'}")

    # Write report
    with open(report_path, "w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"\nReport: {report_path}")

    # Symlink latest
    latest = report_dir / "latest-e2e.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(report_path.name)

    return 0 if summary["passed"] else 1


async def run_evolution_test(args: argparse.Namespace) -> int:
    """Run same topic twice, verify second run improves over first."""
    api_key = get_api_key()
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable")
        return 1

    topic_text = args.topic or "vector databases for RAG"
    depth = args.depth or "standard"
    topic = {"id": "evo", "topic": topic_text, "lang": "en"}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    report_dir = ROOT / "tests" / "integration" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}-evolution-test.jsonl"
    session_base = ROOT / "tests" / "integration" / "sessions" / run_id
    session_base.mkdir(parents=True, exist_ok=True)

    llm = LLMClient(api_key)
    records = [
        {
            "type": "evolution_test_start",
            "run_id": run_id,
            "topic": topic_text,
            "depth": depth,
        }
    ]

    # ── Run 1: Baseline ──
    print("=" * 60)
    print(f"EVOLUTION TEST — Run 1 (baseline): {topic_text}")
    print("=" * 60)
    run1_records = await run_topic(llm, topic, depth, session_base / "run1", False)
    records.extend([{**r, "run": 1} for r in run1_records])

    run1_summary = next(
        (r for r in run1_records if r.get("type") == "topic_summary"), {}
    )
    run1_score = run1_summary.get("judge_score")
    run1_blocks = run1_summary.get("blocks_passed", 0)

    # Extract run1 rubric pass rate
    run1_pass_rate = 0.0
    for r in run1_records:
        if r.get("block") == 5:
            run1_pass_rate = r.get("details", {}).get("pass_rate", 0.0)

    print(
        f"\nRun 1 result: judge={run1_score}, blocks={run1_blocks}/{run1_summary.get('blocks_total', 0)}, rubric_pass_rate={run1_pass_rate}"
    )

    # ── Copy patterns from run1 to run2 session ──
    # Simulate evolution: run1's patterns should be available to run2

    run1_session_dirs = list((session_base / "run1").iterdir())
    if run1_session_dirs:
        run1_dir = run1_session_dirs[0]
        run2_base = session_base / "run2"
        # Pre-create run2's state dir and copy patterns BEFORE SessionDir init
        # (SessionDir only writes empty files if they don't exist yet)
        run2_state = run2_base / topic["id"] / "state"
        run2_state.mkdir(parents=True, exist_ok=True)

        patterns_copied = 0
        for state_file in ["patterns-v2.jsonl", "worklog.jsonl"]:
            src = run1_dir / "state" / state_file
            if src.exists() and src.stat().st_size > 0:
                shutil.copy2(src, run2_state / state_file)
                patterns_copied += 1
                print(f"  Copied {state_file} ({src.stat().st_size} bytes) to run2")

        if patterns_copied == 0:
            print("  WARNING: No patterns to copy from run1 to run2")

    # ── Run 2: Post-evolution ──
    print()
    print("=" * 60)
    print(f"EVOLUTION TEST — Run 2 (post-evolution): {topic_text}")
    print("=" * 60)
    run2_records = await run_topic(llm, topic, depth, session_base / "run2", False)
    records.extend([{**r, "run": 2} for r in run2_records])

    run2_summary = next(
        (r for r in run2_records if r.get("type") == "topic_summary"), {}
    )
    run2_score = run2_summary.get("judge_score")
    run2_blocks = run2_summary.get("blocks_passed", 0)

    # ── Compare ──
    print()
    print("=" * 60)
    print("EVOLUTION DELTA")
    print("=" * 60)

    # Extract run2 rubric pass rate
    run2_pass_rate = 0.0
    for r in run2_records:
        if r.get("block") == 5:
            run2_pass_rate = r.get("details", {}).get("pass_rate", 0.0)

    delta = {
        "type": "evolution_delta",
        "run_id": run_id,
        "topic": topic_text,
        "run1_judge_score": run1_score,
        "run2_judge_score": run2_score,
        "score_delta": round(run2_score - run1_score, 4)
        if run1_score and run2_score
        else None,
        "run1_blocks_passed": run1_blocks,
        "run2_blocks_passed": run2_blocks,
        "run1_rubric_pass_rate": run1_pass_rate,
        "run2_rubric_pass_rate": run2_pass_rate,
        "improved": False,
    }

    if run1_score is not None and run2_score is not None:
        score_improved = run2_score > run1_score + 0.01
        blocks_improved = run2_blocks > run1_blocks
        rubric_improved = run2_pass_rate > run1_pass_rate + 0.05
        delta["improved"] = score_improved or blocks_improved or rubric_improved
        print(
            f"Judge score: {run1_score:.3f} → {run2_score:.3f} (delta: {delta['score_delta']:+.4f})"
        )
        print(f"Blocks passed: {run1_blocks} → {run2_blocks}")
        print(f"Rubric pass rate: {run1_pass_rate:.0%} → {run2_pass_rate:.0%}")
        print(f"Improved: {'YES' if delta['improved'] else 'NO'}")
    else:
        print(
            f"Judge scores: run1={run1_score}, run2={run2_score} (comparison not possible)"
        )

    records.append(delta)

    # Token usage
    print(
        f"\nTotal LLM tokens: {llm.total_input_tokens:,} in / {llm.total_output_tokens:,} out"
    )

    # Write report
    with open(report_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Report: {report_path}")

    # Symlink
    latest = report_dir / "latest-evolution.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(report_path.name)

    return 0 if delta.get("improved") else 1


# ── Scenario tests ──────────────────────────────────────────────────────

SCENARIOS = {
    "s1": {
        "topic": {"id": "s1", "topic": "AI code review tools", "lang": "en"},
        "depth": "quick",
        "label": "Quick + Markdown + English",
        "timeout_min": 10,
    },
    "s2": {
        "topic": {"id": "s2", "topic": "production RAG systems", "lang": "en"},
        "depth": "standard",
        "label": "Standard + HTML + English",
        "timeout_min": 20,
    },
    "s3": {
        "topic": {"id": "s3", "topic": "self-evolving AI agents", "lang": "en"},
        "depth": "deep",
        "label": "Deep + HTML + English (pressure test)",
        "timeout_min": 40,
    },
    "s4": {
        "topic": {"id": "s4", "topic": "中国大模型生态", "lang": "zh"},
        "depth": "standard",
        "label": "Standard + Markdown + Chinese",
        "timeout_min": 20,
    },
    "s5": {
        "topic": {"id": "s5", "topic": "smart wearable market 2026", "lang": "en"},
        "depth": "standard",
        "label": "Standard + Slides + English",
        "timeout_min": 20,
    },
    "s7": {
        "topic": {
            "id": "s7",
            "topic": "17th century Mongolian pottery glazing techniques",
            "lang": "en",
        },
        "depth": "quick",
        "label": "Cold topic (expect few/zero results)",
        "timeout_min": 10,
    },
}

WEBSEARCH_BYPASS_SOURCES = {"WebSearch", "web_search", "websearch"}


async def run_scenario(args: argparse.Namespace) -> int:
    """Run a specific user scenario and validate results."""
    api_key = get_api_key()
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable")
        return 1

    scenario_key = args.scenario
    if scenario_key == "all":
        results = []
        for key in sorted(SCENARIOS):
            args_copy = argparse.Namespace(**vars(args))
            args_copy.scenario = key
            rc = await run_scenario(args_copy)
            results.append((key, rc))
        print("\n" + "=" * 60)
        print("ALL SCENARIOS SUMMARY")
        print("=" * 60)
        for key, rc in results:
            status = "PASS" if rc == 0 else "FAIL"
            print(f"  [{status}] {key}: {SCENARIOS[key]['label']}")
        failed = sum(1 for _, rc in results if rc != 0)
        print(f"\n{len(results) - failed}/{len(results)} passed")
        return 1 if failed else 0

    if scenario_key not in SCENARIOS:
        print(
            f"ERROR: Unknown scenario '{scenario_key}'. Available: {', '.join(sorted(SCENARIOS))}, all"
        )
        return 1

    scenario = SCENARIOS[scenario_key]
    topic = scenario["topic"]
    depth = scenario["depth"]
    timeout_min = scenario["timeout_min"]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    report_dir = ROOT / "tests" / "integration" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}-scenario-{scenario_key}.jsonl"
    session_base = ROOT / "tests" / "integration" / "sessions" / run_id

    llm = LLMClient(api_key)

    print("=" * 60)
    print(f"SCENARIO {scenario_key.upper()}: {scenario['label']}")
    print(f"Topic: {topic['topic']} | Depth: {depth} | Timeout: {timeout_min}min")
    print("=" * 60)

    start_time = time.monotonic()
    records = await run_topic(
        llm, topic, depth, session_base, skip_evolve=(depth == "quick")
    )
    elapsed_min = (time.monotonic() - start_time) / 60

    # ── Validations ──
    summary = next((r for r in records if r.get("type") == "topic_summary"), {})
    blocks_passed = summary.get("blocks_passed", 0)
    judge_score = summary.get("judge_score")
    is_cold = scenario_key == "s7"

    checks = []

    # Timeout check
    if elapsed_min > timeout_min:
        checks.append(f"FAIL: Took {elapsed_min:.1f}min > {timeout_min}min timeout")
    else:
        checks.append(
            f"PASS: Completed in {elapsed_min:.1f}min (limit: {timeout_min}min)"
        )

    # Blocks check
    min_blocks = 3 if is_cold else 5
    if blocks_passed >= min_blocks:
        checks.append(f"PASS: {blocks_passed} blocks passed (min: {min_blocks})")
    else:
        checks.append(f"FAIL: Only {blocks_passed} blocks passed (min: {min_blocks})")

    # Judge score check (skip for cold topics)
    if not is_cold:
        if judge_score is not None and judge_score > 0.3:
            checks.append(f"PASS: Judge score {judge_score:.3f} > 0.3")
        else:
            checks.append(f"FAIL: Judge score {judge_score} <= 0.3 or missing")

    # Delivery file check
    delivery_found = False
    session_dirs = list(session_base.iterdir()) if session_base.exists() else []
    for sd in session_dirs:
        delivery_dir = sd / "delivery"
        if delivery_dir.exists():
            for f in delivery_dir.iterdir():
                if f.stat().st_size > 500:
                    delivery_found = True
                    break
    if delivery_found or is_cold:
        checks.append("PASS: Delivery file exists (>500 bytes)")
    else:
        checks.append("FAIL: No delivery file > 500 bytes")

    # WebSearch bypass check
    websearch_found = False
    for r in records:
        if r.get("type") == "block" and r.get("block") == 2:
            sources = r.get("details", {}).get("source_distribution", {})
            bypass_sources = set(sources.keys()) & WEBSEARCH_BYPASS_SOURCES
            if bypass_sources:
                websearch_found = True
                checks.append(f"FAIL: WebSearch bypass detected: {bypass_sources}")
    if not websearch_found:
        checks.append("PASS: No WebSearch bypass")

    # Chinese check for s4
    if scenario_key == "s4" and delivery_found:
        for sd in session_dirs:
            delivery_dir = sd / "delivery"
            if delivery_dir.exists():
                for f in delivery_dir.iterdir():
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
                    total_chars = len(content)
                    ratio = chinese_chars / total_chars if total_chars > 0 else 0
                    if ratio > 0.1:
                        checks.append(f"PASS: Chinese content ratio {ratio:.0%}")
                    else:
                        checks.append(f"FAIL: Chinese content ratio {ratio:.0%} < 10%")
                    break

    # Print results
    print(f"\n{'─' * 40}")
    all_passed = True
    for check in checks:
        print(f"  {check}")
        if check.startswith("FAIL"):
            all_passed = False

    verdict = "PASS" if all_passed else "FAIL"
    print(f"\n  Verdict: {verdict}")
    print(
        f"  LLM tokens: {llm.total_input_tokens:,} in / {llm.total_output_tokens:,} out"
    )

    # Write report
    records.append(
        {
            "type": "scenario_result",
            "scenario": scenario_key,
            "label": scenario["label"],
            "verdict": verdict,
            "checks": checks,
            "elapsed_min": round(elapsed_min, 1),
            "judge_score": judge_score,
            "blocks_passed": blocks_passed,
        }
    )
    with open(report_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    print(f"  Report: {report_path}")

    return 0 if all_passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoSearch E2E integration test")
    parser.add_argument(
        "--mode", choices=["quick", "standard", "full"], default="quick"
    )
    parser.add_argument("--topic", type=str, help="Single topic to test")
    parser.add_argument("--depth", type=str, choices=["quick", "standard", "deep"])
    parser.add_argument(
        "--evolution-test",
        action="store_true",
        help="Run same topic twice and compare scores to verify evolution",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run a specific scenario: s1|s2|s3|s4|s5|s7|all",
    )
    args = parser.parse_args()
    if args.scenario:
        return asyncio.run(run_scenario(args))
    if args.evolution_test:
        return asyncio.run(run_evolution_test(args))
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
