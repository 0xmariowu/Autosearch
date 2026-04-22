"""Scenarios B1-B4: English tech searches using corpus repos."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_CHANNEL_SEARCH_TEMPLATE = """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {{c.name: c for c in _build_channels()}}
    results = []
    for ch_name in {channels!r}:
        if ch_name not in channels:
            continue
        try:
            evs = await channels[ch_name].search(SubQuery(text={query!r}, rationale="e2b test"))
            for ev in evs[:5]:
                results.append({{'channel': ch_name, 'url': ev.url, 'title': ev.title[:80]}})
        except Exception as e:
            results.append({{'channel': ch_name, 'error': str(e)[:100]}})
    ok = sum(1 for r in results if 'url' in r)
    print(json.dumps({{'ok': ok >= {min_count}, 'evidence_count': ok, 'results': results}}))

asyncio.run(main())
"""


async def _run_channel_search(
    sandbox_id: str,
    env: dict,
    scenario_id: str,
    name: str,
    query: str,
    channels: list[str],
    min_count: int = 3,
) -> ScenarioResult:
    t0 = time.monotonic()
    script = _CHANNEL_SEARCH_TEMPLATE.format(channels=channels, query=query, min_count=min_count)
    result, _ = await run_python(sandbox_id, script, env=env, timeout=60)
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    ev_count = result.get("evidence_count", 0)
    score = min(100, int(ev_count / min_count * 80) + (20 if ok else 0))
    return ScenarioResult(
        scenario_id,
        "B",
        name,
        score=score,
        passed=ok,
        evidence_count=ev_count,
        details={"query": query, "channels": channels, **result},
        duration_s=dur,
    )


async def b1_uv_monorepo(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_search(
        sandbox_id,
        env,
        "B1",
        "uv_monorepo",
        query="Python uv package manager monorepo workspace",
        channels=["hackernews", "devto", "stackoverflow", "ddgs"],
        min_count=2,
    )


async def b2_cockroachdb_dev(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_search(
        sandbox_id,
        env,
        "B2",
        "cockroachdb_dev_tool",
        query="cockroachdb distributed database dev build commands patterns",
        channels=["github", "hackernews", "devto"],
        min_count=3,
    )


async def b3_nextjs_migration(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_channel_search(
        sandbox_id,
        env,
        "B3",
        "nextjs_app_router",
        query="Next.js App Router breaking changes 2024 migration guide",
        channels=["github", "devto", "stackoverflow"],
        min_count=5,
    )


async def b4_docker_inference(sandbox_id: str, env: dict) -> ScenarioResult:
    """B4: Tests the new dockerhub channel specifically."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {c.name: c for c in _build_channels()}
    dockerhub_results = []
    if 'dockerhub' in channels:
        evs = await channels['dockerhub'].search(
            SubQuery(text='LLM inference server vLLM TGI ollama', rationale='e2b test')
        )
        for ev in evs[:5]:
            dockerhub_results.append({'title': ev.title[:60], 'url': ev.url, 'snippet': (ev.snippet or '')[:80]})

    ok = len(dockerhub_results) >= 2 and any(
        any(term in r['title'].lower() for term in ['ollama','vllm','tgi','llm','inference'])
        for r in dockerhub_results
    )
    print(json.dumps({
        'ok': ok,
        'dockerhub_available': 'dockerhub' in channels,
        'evidence_count': len(dockerhub_results),
        'results': dockerhub_results,
    }))

asyncio.run(main())
""",
        env=env,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "B4",
        "B",
        "docker_inference_new_channel",
        score=100 if ok else (50 if result.get("dockerhub_available") else 0),
        passed=ok,
        evidence_count=result.get("evidence_count", 0),
        details=result,
        duration_s=dur,
    )
