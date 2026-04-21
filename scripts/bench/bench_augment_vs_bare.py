"""Augment-vs-Bare bench runner for Gate 12 (W3.4).

Runs a list of research topics against two variants of the same Claude model:

- **augmented (A)**: system prompt includes the autosearch skill catalog
  (list of all leaf skills + group indexes + trio tool names). This models
  "runtime AI has access to the autosearch tool supplier" without needing
  a real E2B sandbox + plugin install.
- **bare (B)**: bare Claude with just the research instruction, no
  autosearch context.

Both variants are asked to produce a research report. Output is two
directories of markdown reports (one per topic per variant), ready to be
fed into ``scripts/bench/judge.py pairwise`` for the Gate 12 verdict.

This is an **approximation** of the full E2B-plugin-based bench described
in ``docs/bench/gate-12-augment-vs-bare.md``. It does not exercise live
``run_channel`` calls; it asks Claude to reason about what autosearch could
surface given the skill catalog. Use it as a directional signal until E2B
plugin loading is verified.

Usage:
    python scripts/bench/bench_augment_vs_bare.py \\
        --topics scripts/bench/topics/gate-12-topics.yaml \\
        --output reports/2026-XX-XX-augment-vs-bare \\
        [--parallel 4] [--model claude-sonnet-4-6] [--runs-per-topic 1]

Requires ``ANTHROPIC_API_KEY`` env var.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PARALLEL = 4
DEFAULT_MAX_TOKENS = 4000

AUGMENTED_SYSTEM_PROMPT = """You are doing research for the user. You have access to AutoSearch — a tool-supplier that exposes the following skill catalog through MCP tools:

**Tool trio (call in order when useful)**:
- `list_skills(group?, domain?)` — discover autosearch skills
- `run_clarify(query, mode_hint?)` — structured clarify + rubrics + channel priorities
- `run_channel(channel_name, query, k?)` — raw evidence from one channel (no synthesis)

**Channel surface — 31 channels grouped**:
- channels-chinese-ugc: bilibili / weibo / xiaohongshu / douyin / zhihu / xiaoyuzhou / wechat / kuaishou / v2ex / xueqiu
- channels-cn-tech: 36kr / csdn / juejin / infoq-cn / sogou-weixin
- channels-academic: arxiv / google-scholar / semantic-scholar / papers-with-code / openreview / conference-talks / citation-graph / author-track / openalex / crossref / paper-list
- channels-code-package: github-repos / github-code / github-issues / npm-pypi / huggingface
- channels-market-product: crunchbase / producthunt / g2-reviews
- channels-community-en: stackoverflow / hackernews / devto / reddit / reddit-exa / hn-exa
- channels-social-career: twitter-exa / twitter-xreach / linkedin
- channels-generic-web: ddgs / exa / tavily / searxng / rss
- channels-video-audio: youtube + video-to-text-groq / video-to-text-openai / video-to-text-local
- tools-fetch-render: fetch-jina / fetch-crawl4ai / fetch-playwright / fetch-firecrawl / mcporter

**How to use for this research task**:

1. Consider which channel groups are most relevant to the user's question.
2. Imagine calling `run_channel(...)` on 3-8 relevant channels. For each, reason about what concrete specifics (numbers, error codes, issue numbers, benchmarks, URLs, named entities) that channel would likely return.
3. Write the report using those specifics. Do not paraphrase — include concrete identifiers verbatim where they would appear.
4. Use inline citations `[1] [2] ...` for sources you reference.

Do not explain the tool catalog to the user. Just produce the research report.
"""

BARE_SYSTEM_PROMPT = """You are doing research for the user. Write a clear, concrete research report with specific identifiers (numbers, error codes, issue numbers, benchmarks, URLs, named entities) where relevant. Use inline citations [1] [2] ... for sources you reference.
"""


def load_topics(path: Path) -> list[dict[str, str]]:
    """Load topics from a YAML file. Each topic: {name, query}.

    Accepts either a list of {name, query} dicts or a dict with a 'topics' key.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "topics" in data:
        data = data["topics"]
    if not isinstance(data, list):
        raise ValueError(f"topics file {path} must contain a list or {{'topics': [...]}}")
    topics: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict) or "name" not in item or "query" not in item:
            raise ValueError(f"each topic must be a dict with 'name' and 'query': {item}")
        topics.append({"name": str(item["name"]), "query": str(item["query"])})
    return topics


def call_claude(
    *,
    query: str,
    system_prompt: str,
    api_key: str,
    model: str,
    max_tokens: int,
    http_client: httpx.Client | None = None,
) -> tuple[bool, str]:
    """One HTTP call to Anthropic Messages API. Returns (ok, text_or_error)."""
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": query}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    client = http_client or httpx.Client(timeout=240.0)
    try:
        response = client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
    finally:
        if http_client is None:
            client.close()

    if response.status_code >= 400:
        return False, f"api_error status={response.status_code} body={response.text[:500]}"

    try:
        body = response.json()
    except ValueError:
        return False, f"api_error non_json body={response.text[:500]}"

    content = body.get("content") or []
    text_chunks = [
        chunk.get("text", "")
        for chunk in content
        if isinstance(chunk, dict) and chunk.get("type") == "text"
    ]
    text = "".join(text_chunks).strip()
    if not text:
        return False, "api_error empty content"
    return True, text


def run_topic(
    topic: dict[str, str],
    *,
    run_index: int,
    api_key: str,
    model: str,
    max_tokens: int,
    output_dir: Path,
) -> dict[str, Any]:
    name = topic["name"]
    query = topic["query"]

    ok_a, text_a = call_claude(
        query=query,
        system_prompt=AUGMENTED_SYSTEM_PROMPT,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
    )
    ok_b, text_b = call_claude(
        query=query,
        system_prompt=BARE_SYSTEM_PROMPT,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
    )

    a_path = output_dir / "a" / f"{name}-run{run_index}.md"
    b_path = output_dir / "b" / f"{name}-run{run_index}.md"
    a_path.parent.mkdir(parents=True, exist_ok=True)
    b_path.parent.mkdir(parents=True, exist_ok=True)

    a_path.write_text(text_a if ok_a else f"[error] {text_a}\n", encoding="utf-8")
    b_path.write_text(text_b if ok_b else f"[error] {text_b}\n", encoding="utf-8")

    return {
        "name": name,
        "run_index": run_index,
        "ok_a": ok_a,
        "ok_b": ok_b,
        "a_path": str(a_path.relative_to(output_dir)),
        "b_path": str(b_path.relative_to(output_dir)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_augment_vs_bare.py")
    parser.add_argument("--topics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--runs-per-topic", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    topics = load_topics(args.topics)
    if not topics:
        print("error: no topics loaded", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)

    jobs = [
        (topic, run_index) for topic in topics for run_index in range(max(1, args.runs_per_topic))
    ]

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as executor:
        futures = {
            executor.submit(
                run_topic,
                topic,
                run_index=run_index,
                api_key=api_key,
                model=args.model,
                max_tokens=args.max_tokens,
                output_dir=args.output,
            ): (topic["name"], run_index)
            for topic, run_index in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)

    summary_path = args.output / "bench-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "model": args.model,
                "total_pairs": len(results),
                "topics": sorted({r["name"] for r in results}),
                "runs_per_topic": args.runs_per_topic,
                "results": sorted(results, key=lambda r: (r["name"], r["run_index"])),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ok_a = sum(1 for r in results if r["ok_a"])
    ok_b = sum(1 for r in results if r["ok_b"])
    print(
        f"done. {len(results)} pairs. augmented ok={ok_a}/{len(results)} "
        f"bare ok={ok_b}/{len(results)}. "
        f"output={args.output}"
    )
    print(
        f"next: run scripts/bench/judge.py pairwise "
        f"--a-dir {args.output / 'a'} --b-dir {args.output / 'b'} "
        f"--a-label augmented --b-label bare --output-dir {args.output / 'judge'}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
