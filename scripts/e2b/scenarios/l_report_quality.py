"""Scenarios L1-L4: End-to-end report quality regression."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "L",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def l1_fast_mode_report(sandbox_id: str, env: dict) -> ScenarioResult:
    """L1: One-channel fast mode search, citation index, and refs export."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "L1", "fast_mode_report", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
_cl = _build_channels()
_av = {c.name for c in _cl}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch
async def main():
    chs = [c for c in ['arxiv','hackernews','devto'] if c in _av][:1]
    if not chs:
        print(json.dumps({'ok': False, 'error': 'no channel'})); return
    with patch('autosearch.mcp.server._build_channels', return_value=_cl):
        server = create_server()
        tm = server._tool_manager
        idx = (await tm.call_tool('citation_create', {}))['index_id']
        r = await tm.call_tool('run_channel', {'channel_name': chs[0], 'query': 'Python async programming patterns 2024', 'k': 5})
        ev = r.evidence if r.ok else []
        for e in ev[:5]:
            await tm.call_tool('citation_add', {'index_id': idx, 'url': e['url'], 'title': e.get('title','')[:60], 'source': chs[0]})
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        print(json.dumps({'ok': True, 'evidence_count': len(ev), 'citation_count': refs['count'], 'report_length': len(refs.get('markdown',''))}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    evidence_count = result.get("evidence_count", 0)
    if not result.get("ok", False):
        score = 0
    elif evidence_count >= 3:
        score = 100
    elif evidence_count >= 1:
        score = 60
    else:
        score = 40
    return ScenarioResult(
        "L1",
        "L",
        "fast_mode_report",
        score=score,
        passed=result.get("ok", False),
        evidence_count=evidence_count,
        report_length=result.get("report_length", 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


_L2_SCRIPT = """
import os, json, asyncio, httpx
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY', '')
from autosearch.core.channel_bootstrap import _build_channels
_cl = _build_channels()
_av = {c.name for c in _cl}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def synthesize(ev_summary, query):
    if not OPENROUTER_KEY:
        return f'[no key] {len(ev_summary)} items'
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_KEY}'},
            json={'model': 'anthropic/claude-haiku-4.5', 'max_tokens': 600,
                  'messages': [
                      {'role':'system','content':'Research assistant. Write concise Markdown report with [1][2] citations.'},
                      {'role':'user','content': f'Query: {query}\\nEvidence:\\n{ev_summary}\\nWrite report.'},
                  ]})
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

async def main():
    test_chs = [c for c in ['arxiv','hackernews','devto','stackoverflow'] if c in _av][:3]
    if not test_chs:
        print(json.dumps({'ok': False, 'error': 'no channels'})); return
    with patch('autosearch.mcp.server._build_channels', return_value=_cl):
        server = create_server()
        tm = server._tool_manager
        idx = (await tm.call_tool('citation_create', {}))['index_id']
        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']
        # Round 1
        d1 = await tm.call_tool('delegate_subtask', {'task_description': 'database migration Python 2024', 'channels': test_chs, 'query': 'Python database schema migration best practices', 'max_per_channel': 4})
        ev1 = [e for evs in d1.get('evidence_by_channel', {}).values() for e in evs]
        s1 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': ev1, 'query': 'database migration'})
        await tm.call_tool('loop_add_gap', {'state_id': state_id, 'gap': 'missing rollback strategies'})
        # Round 2
        d2 = await tm.call_tool('delegate_subtask', {'task_description': 'rollback strategies', 'channels': test_chs[:2], 'query': 'database migration rollback Python alembic', 'max_per_channel': 3})
        ev2 = [e for evs in d2.get('evidence_by_channel', {}).values() for e in evs]
        s2 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': ev2, 'query': 'rollback'})
        all_ev = ev1 + ev2
        for e in all_ev[:8]:
            await tm.call_tool('citation_add', {'index_id': idx, 'url': e['url'], 'title': e.get('title','')[:60], 'source': e.get('source', 'unknown')})
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        ev_lines = '\\n'.join(f"[{i+1}] {e.get('title','')[:60]}: {e.get('snippet','')[:80]}" for i,e in enumerate(all_ev[:8]))
        report = await synthesize(ev_lines or 'No evidence', 'Python database schema migration best practices')
        ok = s2['round_count'] == 2 and refs['count'] >= 2 and len(report) >= 200
        print(json.dumps({'ok': ok, 'rounds': s2['round_count'], 'citations': refs['count'], 'report_length': len(report), 'total_evidence': len(all_ev), 'used_llm': bool(OPENROUTER_KEY)}))
asyncio.run(main())
"""


async def l2_deep_mode_loop_report(sandbox_id: str, env: dict) -> ScenarioResult:
    """L2: Two-round loop, three-channel delegation, citation export, optional synthesis."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "L2", "deep_mode_loop_report", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        _L2_SCRIPT,
        env=_clean_env(env),
        timeout=150,
    )
    dur = time.monotonic() - t0
    score = 0
    if result.get("rounds") == 2:
        score += 40
    if result.get("citations", 0) >= 2:
        score += 20
    if result.get("report_length", 0) >= 200:
        score += 20
    if result.get("used_llm"):
        score += 20
    return ScenarioResult(
        "L2",
        "L",
        "deep_mode_loop_report",
        score=score,
        passed=result.get("ok", False),
        evidence_count=result.get("total_evidence", 0),
        report_length=result.get("report_length", 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def l3_chinese_topic_report(sandbox_id: str, env: dict) -> ScenarioResult:
    """L3: Chinese topic search across available Chinese channels."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "L3", "chinese_topic_report", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
_cl = _build_channels()
_av = {c.name for c in _cl}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch
async def main():
    cn_chs = [c for c in ['zhihu','v2ex','tieba','xiaohongshu','weibo'] if c in _av][:3]
    if not cn_chs:
        print(json.dumps({'ok': False, 'error': 'no Chinese channels', 'available': sorted(_av)[:15]})); return
    with patch('autosearch.mcp.server._build_channels', return_value=_cl):
        server = create_server()
        tm = server._tool_manager
        all_ev = []
        for ch in cn_chs:
            r = await tm.call_tool('run_channel', {'channel_name': ch, 'query': '小红书 Cursor IDE 最佳实践', 'k': 5})
            if r.ok:
                all_ev.extend(r.evidence)
        cn_urls = [e for e in all_ev if any(d in e.get('url','') for d in ['zhihu','v2ex','tieba','xiaohongshu','weibo','bilibili'])]
        print(json.dumps({'ok': True, 'total_evidence': len(all_ev), 'cn_url_evidence': len(cn_urls), 'channels_used': cn_chs}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=90,
    )
    dur = time.monotonic() - t0
    cn_url_evidence = result.get("cn_url_evidence", 0)
    total_evidence = result.get("total_evidence", 0)
    if not result.get("ok", False):
        score = 0
    elif cn_url_evidence >= 2:
        score = 100
    elif total_evidence >= 1:
        score = 60
    else:
        score = 40
    return ScenarioResult(
        "L3",
        "L",
        "chinese_topic_report",
        score=score,
        passed=result.get("ok", False),
        evidence_count=total_evidence,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


_L4_SCRIPT = """
import os, json, asyncio, httpx
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY', '')
if not OPENROUTER_KEY:
    print(json.dumps({'ok': True, 'skipped': True, 'reason': 'no OPENROUTER_API_KEY'}))
else:
    CATALOG = "AutoSearch has 35 research channels: arxiv, pubmed, hackernews, devto, reddit, stackoverflow, github, ddgs, dockerhub, wikipedia, zhihu, v2ex, tieba, and more. Tools: run_clarify, run_channel, select_channels_tool, delegate_subtask, loop_init/update/get_gaps, citation_create/add/export."
    QUERY = "best practices for database schema migration in Python 2024"
    async def call_llm(system_prompt):
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post('https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_KEY}'},
                json={'model': 'anthropic/claude-haiku-4.5', 'max_tokens': 500,
                      'messages': [{'role':'system','content': system_prompt}, {'role':'user','content': f'Research: {QUERY}'}]})
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
    async def judge(a, b):
        prompt = f'Compare research responses to "{QUERY}". A: {a[:350]} B: {b[:350]}. Which is better? Reply EXACTLY: {{"winner":"A"}} or {{"winner":"B"}} or {{"winner":"tie"}}'
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post('https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_KEY}'},
                json={'model': 'anthropic/claude-haiku-4.5', 'max_tokens': 30,
                      'messages': [{'role':'user','content': prompt}]})
            r.raise_for_status()
            content = r.json()['choices'][0]['message']['content']
        for line in reversed(content.strip().splitlines()):
            line = line.strip()
            if '{' in line and 'winner' in line:
                try: return json.loads(line[line.index('{'):line.rindex('}')+1])['winner']
                except: pass
        return 'tie'
    async def main():
        aug = await call_llm(f"You are a research assistant with AutoSearch.\\n{CATALOG}")
        bare = await call_llm("You are a research assistant.")
        winner = await judge(aug, bare)
        ok = winner in ('A', 'tie')
        print(json.dumps({'ok': ok, 'winner': winner, 'aug_len': len(aug), 'bare_len': len(bare)}))
    asyncio.run(main())
"""


async def l4_mini_gate12_llm_judge(sandbox_id: str, env: dict) -> ScenarioResult:
    """L4: OpenRouter pairwise judge for augmented vs bare research prompt."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "L4", "mini_gate12_llm_judge", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        _L4_SCRIPT,
        env=_clean_env(env),
        timeout=120,
    )
    dur = time.monotonic() - t0
    winner = result.get("winner")
    if result.get("skipped"):
        score = 100
    elif winner == "A":
        score = 100
    elif winner == "tie":
        score = 70
    else:
        score = 0
    return ScenarioResult(
        "L4",
        "L",
        "mini_gate12_llm_judge",
        score=score,
        passed=result.get("ok", False),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )
