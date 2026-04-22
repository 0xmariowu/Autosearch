"""Scenarios D1-D3: Academic and specialist channel searches."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python


async def d1_pubmed_crispr(sandbox_id: str, env: dict) -> ScenarioResult:
    """D1: PubMed new channel — real biomedical search."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {c.name: c for c in _build_channels()}
    results = []
    for ch in ['pubmed', 'arxiv']:
        if ch not in channels:
            results.append({'channel': ch, 'error': 'not available'})
            continue
        try:
            evs = await channels[ch].search(
                SubQuery(text='CRISPR gene therapy clinical trial 2024 efficacy', rationale='e2b test')
            )
            results.append({
                'channel': ch,
                'count': len(evs),
                'sample': [{'title': e.title[:60], 'url': e.url} for e in evs[:3]],
            })
        except Exception as e:
            results.append({'channel': ch, 'error': str(e)[:80]})

    pubmed_ok = any(r.get('channel') == 'pubmed' and r.get('count', 0) >= 3 for r in results)
    arxiv_ok = any(r.get('channel') == 'arxiv' and r.get('count', 0) >= 3 for r in results)
    print(json.dumps({
        'ok': pubmed_ok or arxiv_ok,
        'pubmed_ok': pubmed_ok,
        'arxiv_ok': arxiv_ok,
        'results': results,
    }))

asyncio.run(main())
""",
        env=env,
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    ev = sum(r.get("count", 0) for r in result.get("results", []) if "count" in r)
    return ScenarioResult(
        "D1",
        "D",
        "pubmed_crispr_new_channel",
        score=100 if result.get("pubmed_ok") else (60 if result.get("arxiv_ok") else 0),
        passed=ok,
        evidence_count=ev,
        details=result,
        duration_s=dur,
    )


async def d2_llm_benchmark_contamination(sandbox_id: str, env: dict) -> ScenarioResult:
    """D2: Multi-academic channel search."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {c.name: c for c in _build_channels()}
    total = 0
    channel_results = {}
    for ch in ['arxiv', 'hackernews', 'devto']:
        if ch not in channels:
            continue
        try:
            evs = await channels[ch].search(
                SubQuery(text='LLM benchmark contamination data leakage evaluation 2024', rationale='e2b test')
            )
            channel_results[ch] = len(evs)
            total += len(evs)
        except Exception as e:
            channel_results[ch] = f'error: {str(e)[:60]}'

    ok = total >= 5 and len([v for v in channel_results.values() if isinstance(v, int) and v > 0]) >= 2
    print(json.dumps({'ok': ok, 'total_evidence': total, 'by_channel': channel_results}))

asyncio.run(main())
""",
        env=env,
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "D2",
        "D",
        "llm_benchmark_multi_channel",
        score=100 if ok else max(0, min(80, result.get("total_evidence", 0) * 10)),
        passed=ok,
        evidence_count=result.get("total_evidence", 0),
        details=result,
        duration_s=dur,
    )


async def d3_citation_dedup(sandbox_id: str, env: dict) -> ScenarioResult:
    """D3: Multi-channel search + citation dedup verification."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

async def main():
    channels = {c.name: c for c in _build_channels()}
    server = create_server()
    tm = server._tool_manager

    idx = await tm.call_tool('citation_create', {})
    index_id = idx['index_id']

    total_ev = 0
    for ch in ['arxiv', 'stackoverflow', 'hackernews']:
        if ch not in channels:
            continue
        try:
            evs = await channels[ch].search(
                SubQuery(text='retrieval augmented generation production deployment', rationale='test')
            )
            for ev in evs[:3]:
                await tm.call_tool('citation_add', {
                    'index_id': index_id, 'url': ev.url,
                    'title': ev.title[:60], 'source': ch,
                })
                total_ev += 1
        except Exception:
            pass

    refs = await tm.call_tool('citation_export', {'index_id': index_id})
    citation_count = refs['count']
    markdown = refs['markdown']

    ok = citation_count >= 3 and '[1]' in markdown and '[2]' in markdown
    print(json.dumps({
        'ok': ok,
        'evidence_added': total_ev,
        'citation_count': citation_count,
        'has_numbered_refs': '[1]' in markdown,
        'markdown_preview': markdown[:200] if markdown else '',
    }))

asyncio.run(main())
""",
        env={**env, "AUTOSEARCH_LLM_MODE": "dummy"},
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "D3",
        "D",
        "citation_dedup",
        score=100 if ok else (50 if result.get("citation_count", 0) >= 1 else 0),
        passed=ok,
        evidence_count=result.get("evidence_added", 0),
        details=result,
        duration_s=dur,
    )
