"""Scenarios F1-F2: Multi-channel parallel searches."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_ENV_DUMMY = {"AUTOSEARCH_LLM_MODE": "dummy"}


async def f1_delegate_subtask_parallel(sandbox_id: str, env: dict) -> ScenarioResult:
    """F1: delegate_subtask across 3 channels concurrently."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels

# Build real channels BEFORE setting dummy mode
channels_list = _build_channels()
available = {c.name for c in channels_list}

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    # Pick 3 channels that are available
    candidates = ['arxiv', 'stackoverflow', 'hackernews', 'devto', 'ddgs']
    test_channels = [c for c in candidates if c in available][:3]

    if len(test_channels) < 2:
        print(json.dumps({'ok': False, 'error': 'fewer than 2 channels available', 'available_sample': list(available)[:10]}))
        return

    with patch('autosearch.mcp.server._build_channels', return_value=channels_list), \
         patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager

        delegation = await tm.call_tool('delegate_subtask', {
            'task_description': 'Find Python asyncio best practices and common pitfalls',
            'channels': test_channels,
            'query': 'Python asyncio best practices common pitfalls timeout',
            'max_per_channel': 5,
        })

        ev_by_ch = delegation.get('evidence_by_channel', {})
        failed = delegation.get('failed_channels', [])
        total = sum(len(v) for v in ev_by_ch.values())

        ok = (
            len(ev_by_ch) >= 2 and
            total >= 3 and
            len(failed) < len(test_channels)
        )
        print(json.dumps({
            'ok': ok,
            'channels_tested': test_channels,
            'channels_returned': list(ev_by_ch.keys()),
            'total_evidence': total,
            'failed_channels': failed,
            'summary': delegation.get('summary', ''),
        }))

asyncio.run(main())
""",
        env={**env, "AUTOSEARCH_LLM_MODE": "dummy"},
        timeout=90,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    ev = result.get("total_evidence", 0)
    return ScenarioResult(
        "F1",
        "F",
        "delegate_subtask_parallel",
        score=100 if ok else max(0, min(70, ev * 10)),
        passed=ok,
        evidence_count=ev,
        details=result,
        duration_s=dur,
    )


async def f2_select_channels_cross_group(sandbox_id: str, env: dict) -> ScenarioResult:
    """F2: select_channels_tool picks channels across groups for mixed query."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server

async def main():
    server = create_server()
    tm = server._tool_manager

    # Mixed query: English tech + possible Chinese context
    sel = await tm.call_tool('select_channels_tool', {
        'query': 'MCP protocol adoption enterprise 2026',
        'mode': 'fast',
    })

    channels = sel.get('channels', [])
    groups = sel.get('groups', [])
    rationale = sel.get('rationale', '')

    # Verify: at least 3 channels, at least 1 rationale word
    ok = len(channels) >= 3 and len(rationale) > 10

    # Perspective questioning: generates 4 viewpoints
    pq = await tm.call_tool('perspective_questioning', {
        'topic': 'MCP protocol enterprise adoption challenges',
        'n': 4,
    })
    pq_ok = isinstance(pq, list) and len(pq) == 4 and all('viewpoint' in p and 'question' in p for p in pq)

    print(json.dumps({
        'ok': ok and pq_ok,
        'channel_count': len(channels),
        'channels': channels[:8],
        'groups': groups,
        'rationale_preview': rationale[:100],
        'perspective_count': len(pq) if isinstance(pq, list) else 0,
        'perspective_sample': pq[0] if pq else None,
    }))

asyncio.run(main())
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "F2",
        "F",
        "select_channels_cross_group",
        score=100 if ok else (60 if result.get("channel_count", 0) >= 3 else 20),
        passed=ok,
        details=result,
        duration_s=dur,
    )
