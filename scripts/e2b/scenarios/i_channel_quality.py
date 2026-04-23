"""Scenarios I1-I12: Per-channel quality — each free channel returns domain-relevant results."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_CHANNEL_QUALITY_TEMPLATE = """
import json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {{c.name: c for c in _build_channels()}}
    channel_names = {channel_names!r}
    ch = None
    selected_name = None
    for candidate in channel_names:
        if candidate in channels:
            ch = channels[candidate]
            selected_name = candidate
            break
    if not ch:
        print(json.dumps({{
            'ok': False,
            'error': 'channel not found',
            'available': list(channels.keys())[:20],
        }}))
        return
    try:
        evs = await ch.search(SubQuery(text={query!r}, rationale='e2b quality test'))
        results = [
            {{
                'url': e.url or '',
                'title': (e.title or '')[:80],
                'snippet': (e.snippet or '')[:60],
            }}
            for e in evs[:10]
        ]
        ok_urls = [
            r for r in results
            if {url_contains!r}.lower() in r['url'].lower() and r['title']
        ]
        ok = len(ok_urls) >= {min_count}
        print(json.dumps({{
            'ok': ok,
            'channel': selected_name,
            'evidence_count': len(results),
            'ok_count': len(ok_urls),
            'sample': results[:3],
        }}))
    except Exception as e:
        print(json.dumps({{'ok': False, 'error': str(e)[:200], 'channel': selected_name}}))

asyncio.run(main())
"""


async def _run_channel_quality(
    sandbox_id: str,
    env: dict,
    scenario_id: str,
    channel_name: str,
    query: str,
    min_count: int,
    url_contains: str,
) -> ScenarioResult:
    t0 = time.monotonic()
    channel_names = [channel_name]
    if channel_name == "hackernews":
        channel_names.append("hn")

    script = _CHANNEL_QUALITY_TEMPLATE.format(
        channel_names=channel_names,
        query=query,
        min_count=min_count,
        url_contains=url_contains,
    )
    result, _ = await run_python(sandbox_id, script, env=env, timeout=60)
    dur = time.monotonic() - t0
    if not isinstance(result, dict):
        result = {"ok": False, "error": "non-dict result", "raw_result": result}

    ok = result.get("ok", False)
    ok_count = result.get("ok_count", 0)
    score = min(100, int(ok_count / min_count * 80) + (20 if ok else 0))
    error = ""
    if result.get("error") == "channel not found":
        error = "channel not available in this version"
    elif result.get("error"):
        error = result.get("error", "")

    return ScenarioResult(
        scenario_id,
        "I",
        f"{channel_name}_quality",
        score=score,
        passed=ok,
        evidence_count=result.get("evidence_count", 0),
        details={
            "query": query,
            "channel_name": channel_name,
            "channel_names": channel_names,
            "url_contains": url_contains,
            "min_count": min_count,
            **result,
        },
        error=error,
        duration_s=dur,
    )


async def i1_arxiv_transformer_attention(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I1",
        "arxiv",
        query="transformer attention mechanism 2024",
        min_count=5,
        url_contains="arxiv.org",
    )


async def i2_pubmed_crispr_off_target(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I2",
        "pubmed",
        query="CRISPR off-target effects treatment",
        min_count=3,
        url_contains="pubmed.ncbi",
    )


async def i3_hackernews_rust_systems(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I3",
        "hackernews",
        query="Rust systems programming 2024",
        min_count=5,
        url_contains="news.ycombinator",
    )


async def i4_devto_typescript_performance(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I4",
        "devto",
        query="TypeScript performance tips",
        min_count=3,
        url_contains="dev.to",
    )


async def i5_dockerhub_redis_alpine(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I5",
        "dockerhub",
        query="redis alpine",
        min_count=3,
        url_contains="hub.docker.com",
    )


async def i6_reddit_python_async(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I6",
        "reddit",
        query="Python async best practices",
        min_count=3,
        url_contains="reddit.com",
    )


async def i7_stackoverflow_postgres_index(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I7",
        "stackoverflow",
        query="PostgreSQL index optimization",
        min_count=5,
        url_contains="stackoverflow.com",
    )


async def i8_ddgs_vector_database(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I8",
        "ddgs",
        query="open source vector database 2024",
        min_count=5,
        url_contains="http",
    )


async def i9_github_vector_embeddings(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I9",
        "github",
        query="vector database embeddings",
        min_count=3,
        url_contains="github.com",
    )


async def i10_papers_diffusion_survey(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I10",
        "papers",
        query="diffusion models survey",
        min_count=3,
        url_contains="arxiv",
    )


async def i11_wikipedia_quantum(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I11",
        "wikipedia",
        query="quantum computing",
        min_count=3,
        url_contains="wikipedia.org",
    )


async def i12_wikidata_python_language(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_quality(
        sandbox_id,
        env,
        "I12",
        "wikidata",
        query="Python programming language",
        min_count=1,
        url_contains="wikidata.org",
    )
