"""Scenarios G1-G3: Deep research + full Markdown report via OpenRouter."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_ENV_DUMMY = {"AUTOSEARCH_LLM_MODE": "dummy"}


async def g1_loop_gap_detection(sandbox_id: str, env: dict) -> ScenarioResult:
    """G1: loop_init → run_channel × 2 → loop_update → gap detection → round 2."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels

channels_list = _build_channels()
available = {c.name for c in channels_list}

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    chs = [c for c in ['arxiv', 'hackernews', 'stackoverflow'] if c in available][:2]
    if len(chs) < 1:
        print(json.dumps({'ok': False, 'error': 'no channels available'}))
        return

    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager

        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']

        ev_all = []
        for ch in chs:
            r = await tm.call_tool('run_channel', {'channel_name': ch, 'query': 'Claude Code hooks API 2026', 'k': 5})
            if r.ok:
                ev_all.extend(r.evidence)

        s1 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': ev_all, 'query': 'Claude Code hooks'})
        await tm.call_tool('loop_add_gap', {'state_id': state_id, 'gap': 'missing pre-2025 breaking changes'})
        gaps = await tm.call_tool('loop_get_gaps', {'state_id': state_id})

        r2 = await tm.call_tool('run_channel', {'channel_name': chs[0], 'query': 'Claude Code breaking changes pre-2025', 'k': 3})
        ev2 = r2.evidence if r2.ok else []
        s2 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': ev2, 'query': 'breaking changes'})

        ok = (
            s2['round_count'] == 2 and
            len(s2['visited_urls']) >= len(s1['visited_urls']) and
            'missing pre-2025 breaking changes' in gaps['gaps']
        )
        print(json.dumps({
            'ok': ok,
            'round_count': s2['round_count'],
            'visited_r1': len(s1['visited_urls']),
            'visited_r2': len(s2['visited_urls']),
            'gaps': gaps['gaps'],
            'total_evidence': len(ev_all) + len(ev2),
        }))

asyncio.run(main())
""",
        env=env,  # dummy mode set inside script after channels built
        timeout=90,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "G1",
        "G",
        "loop_gap_detection",
        score=100 if ok else (60 if result.get("round_count", 0) >= 1 else 0),
        passed=ok,
        evidence_count=result.get("total_evidence", 0),
        details=result,
        duration_s=dur,
    )


_G2_SCRIPT = """
import os, json, asyncio, httpx
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY', '')
from autosearch.core.channel_bootstrap import _build_channels

# Build real channels BEFORE setting dummy mode
_channels_list = _build_channels()
_available = {c.name for c in _channels_list}

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server

async def synthesize(ev_summary, query):
    if not OPENROUTER_KEY:
        return f'[no key] {len(ev_summary)} items'
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'anthropic/claude-haiku-4.5',
                'max_tokens': 800,
                'messages': [
                    {'role': 'system', 'content': 'Research assistant. Write a concise Markdown report with [1][2] citations.'},
                    {'role': 'user', 'content': f'Query: {query}\\nEvidence:\\n{ev_summary}\\nWrite a research report.'},
                ],
            },
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

async def main():
    test_chs = [c for c in ['arxiv', 'hackernews', 'stackoverflow', 'devto'] if c in _available][:3]

    from unittest.mock import patch
    with patch('autosearch.mcp.server._build_channels', return_value=_channels_list), \\
         patch('autosearch.core.channel_bootstrap._build_channels', return_value=_channels_list):
        server = create_server()
        tm = server._tool_manager

        idx = (await tm.call_tool('citation_create', {}))['index_id']

        delegation = await tm.call_tool('delegate_subtask', {
            'task_description': 'Find uv workspace monorepo issues',
            'channels': test_chs,
            'query': 'astral-sh/uv workspace monorepo Python issues',
            'max_per_channel': 5,
        })

        ev_lines = []
        for ch, evs in delegation.get('evidence_by_channel', {}).items():
            for ev in evs[:3]:
                num = (await tm.call_tool('citation_add', {
                    'index_id': idx, 'url': ev['url'],
                    'title': ev.get('title','')[:60], 'source': ch,
                }))['citation_number']
                ev_lines.append(f'[{num}] {ev.get("title","")[:60]} ({ch}): {ev.get("snippet","")[:80]}')

        refs = await tm.call_tool('citation_export', {'index_id': idx})
        report = await synthesize('\\n'.join(ev_lines[:10]) or 'No evidence', 'astral-sh/uv workspace issues')

        ok = refs['count'] >= 2 and len(report) >= 200 and ('[1]' in report or refs['count'] > 0)
        print(json.dumps({
            'ok': ok,
            'citation_count': refs['count'],
            'report_length': len(report),
            'report_has_citations': '[1]' in report or '[2]' in report,
            'report_preview': report[:300],
            'total_evidence': sum(len(v) for v in delegation.get('evidence_by_channel', {}).values()),
            'synthesis_used_llm': bool(OPENROUTER_KEY),
        }))

asyncio.run(main())
"""


async def g2_golden_path_with_report(sandbox_id: str, env: dict) -> ScenarioResult:
    """G2: Full golden path + OpenRouter synthesis → Markdown report."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        _G2_SCRIPT,
        env=env,  # dummy mode set inside script after channels built
        timeout=120,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 0
    if result.get("citation_count", 0) >= 2:
        score += 40
    if result.get("report_length", 0) >= 200:
        score += 30
    if result.get("report_has_citations"):
        score += 20
    if result.get("total_evidence", 0) >= 5:
        score += 10
    return ScenarioResult(
        "G2",
        "G",
        "golden_path_with_report",
        score=score,
        passed=ok,
        evidence_count=result.get("total_evidence", 0),
        report_length=result.get("report_length", 0),
        details={k: v for k, v in result.items() if k != "report_preview"},
        duration_s=dur,
    )


_G3_SCRIPT = """
import os, json, asyncio, httpx
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY', '')
from autosearch.core.channel_bootstrap import _build_channels

_channels_list = _build_channels()
_available = {c.name for c in _channels_list}

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server

async def synthesize(ev_list, query, refs_md):
    if not OPENROUTER_KEY:
        return f'[no key] {len(ev_list)} items. Refs: {refs_md[:100]}'
    ev_text = '\\n'.join(f'[{i+1}] {e.get("title","")[:60]}: {e.get("snippet","")[:80]}' for i, e in enumerate(ev_list[:8]))
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'anthropic/claude-haiku-4.5',
                'max_tokens': 1000,
                'messages': [
                    {'role': 'system', 'content': 'Research assistant. Write a 300+ word Markdown report with [1][2] citations, specific numbers and examples.'},
                    {'role': 'user', 'content': f'Query: {query}\\nEvidence:\\n{ev_text}\\nRefs:\\n{refs_md[:500]}\\nWrite report.'},
                ],
            },
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

async def main():
    query = 'grafana/k6 load testing REST API best practices 2024'

    from unittest.mock import patch
    with patch('autosearch.mcp.server._build_channels', return_value=_channels_list), \\
         patch('autosearch.core.channel_bootstrap._build_channels', return_value=_channels_list):
        server = create_server()
        tm = server._tool_manager

        # Perspective questioning
        persp = await tm.call_tool('perspective_questioning', {'topic': query, 'n': 4})

        # Graph search plan
        plan = await tm.call_tool('graph_search_plan', {'subtasks': [
            {'id': 'A', 'description': 'Find k6 docs', 'depends_on': []},
            {'id': 'B', 'description': 'Find user experiences', 'depends_on': []},
            {'id': 'C', 'description': 'Synthesize', 'depends_on': ['A', 'B']},
        ]})

        test_chs = [c for c in ['devto', 'hackernews', 'stackoverflow'] if c in _available][:3]
        idx = (await tm.call_tool('citation_create', {}))['index_id']

        delegation = await tm.call_tool('delegate_subtask', {
            'task_description': query, 'channels': test_chs, 'query': query, 'max_per_channel': 5,
        })

        flat_ev = []
        for ch, evs in delegation.get('evidence_by_channel', {}).items():
            for ev in evs[:3]:
                flat_ev.append(ev)
                await tm.call_tool('citation_add', {'index_id': idx, 'url': ev['url'], 'title': ev.get('title','')[:60], 'source': ch})

        filtered = await tm.call_tool('recent_signal_fusion', {'evidence': flat_ev, 'days': 180})
        trimmed = await tm.call_tool('context_retention_policy', {'evidence': flat_ev, 'token_budget': 2000})
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        report = await synthesize(flat_ev, query, refs.get('markdown', ''))

        ok = len(flat_ev) >= 3 and refs['count'] >= 2 and len(report) >= 300
        print(json.dumps({
            'ok': ok,
            'perspectives_count': len(persp) if isinstance(persp, list) else 0,
            'plan_batches': len(plan) if isinstance(plan, list) else 0,
            'total_evidence': len(flat_ev),
            'after_fusion': len(filtered),
            'after_trim': len(trimmed),
            'citation_count': refs['count'],
            'report_length': len(report),
            'report_preview': report[:400],
            'synthesis_used_llm': bool(OPENROUTER_KEY),
        }))

asyncio.run(main())
"""


async def g3_complex_report_with_workflows(sandbox_id: str, env: dict) -> ScenarioResult:
    """G3: Complex research using all workflow skills + full report."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        _G3_SCRIPT,
        env=env,  # dummy mode set inside script after channels built
        timeout=150,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 0
    if result.get("perspectives_count", 0) >= 4:
        score += 10
    if result.get("plan_batches", 0) >= 2:
        score += 10
    if result.get("total_evidence", 0) >= 3:
        score += 20
    if result.get("citation_count", 0) >= 2:
        score += 20
    if result.get("report_length", 0) >= 300:
        score += 30
    if result.get("report_length", 0) >= 500:
        score += 10
    return ScenarioResult(
        "G3",
        "G",
        "complex_report_with_workflows",
        score=score,
        passed=ok,
        evidence_count=result.get("total_evidence", 0),
        report_length=result.get("report_length", 0),
        details={k: v for k, v in result.items() if k != "report_preview"},
        duration_s=dur,
    )
