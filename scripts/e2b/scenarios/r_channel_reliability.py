"""Scenarios R1-R10: Channel reliability under error conditions."""

from __future__ import annotations

import time
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python as _run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


def _as_dict(result: Any) -> dict[str, Any]:
    return result if isinstance(result, dict) else {"ok": False, "raw_result": repr(result)}


async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "R",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def r1_channel_timeout_graceful(sandbox_id: str, env: dict) -> ScenarioResult:
    """R1: A timeout in one channel does not crash delegated search."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R1", "channel_timeout_graceful", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch, AsyncMock
import httpx

async def main():
    test_chs = [c for c in ['arxiv','hackernews','devto','ddgs'] if c in available][:3]
    if len(test_chs) < 2:
        print(json.dumps({'ok': False, 'error': 'not enough channels'}))
        return
    bad_ch = test_chs[0]
    ch_obj = next(c for c in channels_list if c.name == bad_ch)
    ch_obj.search = AsyncMock(side_effect=httpx.TimeoutException('timeout'))
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        with patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
            server = create_server()
            tm = server._tool_manager
            result = await tm.call_tool('delegate_subtask', {'task_description': 'test', 'channels': test_chs, 'query': 'Python async', 'max_per_channel': 3})
            by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
            good_ev = sum(len(v) for k, v in by_ch.items() if k != bad_ch)
            ok = True
            print(json.dumps({'ok': ok, 'good_evidence': good_ev, 'channels_returned': list(by_ch.keys()), 'failed_channels': result.get('failed_channels', [])}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    completed = result.get("ok", False) and "good_evidence" in result
    good_evidence = int(result.get("good_evidence", 0) or 0)
    score = 100 if good_evidence >= 2 else (70 if completed else 0)
    return ScenarioResult(
        "R1",
        "R",
        "channel_timeout_graceful",
        score=score,
        passed=completed,
        evidence_count=good_evidence,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r2_channel_429_graceful(sandbox_id: str, env: dict) -> ScenarioResult:
    """R2: HTTP 429 from a channel returns ok=False with a useful reason."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R2", "channel_429_graceful", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch, AsyncMock
import httpx

async def main():
    ch_name = next((c for c in ['arxiv','hackernews','devto','ddgs'] if c in available), None)
    if not ch_name:
        print(json.dumps({'ok': False, 'error': 'no test channel'}))
        return
    ch_obj = next(c for c in channels_list if c.name == ch_name)
    request = httpx.Request('GET', 'https://example.com/rate-limit')
    response = httpx.Response(429, request=request)
    ch_obj.search = AsyncMock(side_effect=httpx.HTTPStatusError('429 rate limit', request=request, response=response))
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        try:
            result = await tm.call_tool('run_channel', {'channel_name': ch_name, 'query': 'Python async', 'k': 3})
            reason = str(getattr(result, 'reason', '') or '')
            graceful = getattr(result, 'ok', True) is False
            clear = '429' in reason or 'rate' in reason.lower()
            print(json.dumps({'ok': graceful, 'clear_reason': clear, 'result_ok': getattr(result, 'ok', None), 'reason': reason[:300]}))
        except Exception as e:
            print(json.dumps({'ok': False, 'exception': type(e).__name__, 'error': str(e)[:300]}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    graceful = bool(result.get("ok"))
    clear = bool(result.get("clear_reason"))
    score = 100 if graceful and clear else (60 if graceful else 0)
    return ScenarioResult(
        "R2",
        "R",
        "channel_429_graceful",
        score=score,
        passed=graceful,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r3_channel_malformed_response(sandbox_id: str, env: dict) -> ScenarioResult:
    """R3: Malformed channel evidence is contained by the tool boundary."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R3", "channel_malformed_response", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch, AsyncMock

async def main():
    ch_name = next((c for c in ['arxiv','hackernews','devto','ddgs'] if c in available), None)
    if not ch_name:
        print(json.dumps({'ok': False, 'error': 'no test channel'}))
        return
    ch_obj = next(c for c in channels_list if c.name == ch_name)
    ch_obj.search = AsyncMock(return_value=[{'url': None, 'title': None}, {'invalid': True}])
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        try:
            result = await tm.call_tool('run_channel', {'channel_name': ch_name, 'query': 'Python async', 'k': 3})
            evidence = getattr(result, 'evidence', []) or []
            ok = True
            print(json.dumps({'ok': ok, 'result_ok': getattr(result, 'ok', None), 'evidence_count': len(evidence), 'reason': str(getattr(result, 'reason', '') or '')[:300]}))
        except Exception as e:
            print(json.dumps({'ok': False, 'exception': type(e).__name__, 'error': str(e)[:300]}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "R3",
        "R",
        "channel_malformed_response",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("evidence_count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r4_empty_channel_loop_continues(sandbox_id: str, env: dict) -> ScenarioResult:
    """R4: A zero-result round can log a gap and continue to another channel."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R4", "empty_channel_loop_continues", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from datetime import UTC, datetime
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.models import Evidence
from autosearch.mcp.server import create_server
from unittest.mock import patch, AsyncMock

async def main():
    test_chs = [c for c in ['arxiv','hackernews','devto','ddgs'] if c in available][:2]
    if len(test_chs) < 2:
        print(json.dumps({'ok': False, 'error': 'not enough channels'}))
        return
    empty_ch, good_ch = test_chs
    empty_obj = next(c for c in channels_list if c.name == empty_ch)
    good_obj = next(c for c in channels_list if c.name == good_ch)
    empty_obj.search = AsyncMock(return_value=[])
    good_obj.search = AsyncMock(return_value=[
        Evidence(url='https://example.com/recovered', title='Recovered result', snippet='second round evidence', source_channel=good_ch, fetched_at=datetime.now(UTC), score=1.0)
    ])
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']
        r1 = await tm.call_tool('run_channel', {'channel_name': empty_ch, 'query': 'obscure topic', 'k': 5})
        s1 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': getattr(r1, 'evidence', []), 'query': 'obscure topic'})
        await tm.call_tool('loop_add_gap', {'state_id': state_id, 'gap': 'zero evidence from first channel'})
        r2 = await tm.call_tool('run_channel', {'channel_name': good_ch, 'query': 'broader topic', 'k': 5})
        s2 = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': getattr(r2, 'evidence', []), 'query': 'broader topic'})
        gaps = await tm.call_tool('loop_get_gaps', {'state_id': state_id})
        gap_logged = any('zero evidence' in g for g in gaps.get('gaps', []))
        ok = s2.get('round_count') == 2 and gap_logged and len(getattr(r2, 'evidence', []) or []) >= 1
        print(json.dumps({'ok': ok, 'rounds_after_empty': s1.get('round_count'), 'round_count': s2.get('round_count'), 'gap_logged': gap_logged, 'gaps': gaps.get('gaps', []), 'evidence_count': len(getattr(r2, 'evidence', []) or [])}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=90,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "R4",
        "R",
        "empty_channel_loop_continues",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("evidence_count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r5_concurrent_5_arxiv(sandbox_id: str, env: dict) -> ScenarioResult:
    """R5: Five concurrent arxiv calls complete without unhandled exceptions."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R5", "concurrent_5_arxiv", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import asyncio, os, json
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch
async def main():
    if 'arxiv' not in available:
        print(json.dumps({'ok': False, 'error': 'arxiv not available'}))
        return
    queries = ['Python', 'machine learning', 'transformer', 'attention', 'BERT']
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        tasks = [tm.call_tool('run_channel', {'channel_name': 'arxiv', 'query': q, 'k': 3}) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        ok_results = [r for r in results if not isinstance(r, Exception)]
        ok = len(errors) == 0
        evidence_count = sum(len(getattr(r, 'evidence', []) or []) for r in ok_results)
        print(json.dumps({'ok': ok, 'completed': len(ok_results), 'errors': len(errors), 'evidence_count': evidence_count}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=90,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    errors = int(result.get("errors", 5) or 0)
    completed = int(result.get("completed", 0) or 0)
    score = 100 if errors == 0 and completed == 5 else int(max(0, completed) * 20)
    return ScenarioResult(
        "R5",
        "R",
        "concurrent_5_arxiv",
        score=score,
        passed=bool(result.get("ok")),
        evidence_count=int(result.get("evidence_count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r6_delegate_1_channel_fails(sandbox_id: str, env: dict) -> ScenarioResult:
    """R6: Delegation completes when one channel raises a generic exception."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R6", "delegate_1_channel_fails", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch, AsyncMock

async def main():
    test_chs = [c for c in ['arxiv','hackernews','devto','ddgs'] if c in available][:3]
    if len(test_chs) < 2:
        print(json.dumps({'ok': False, 'error': 'not enough channels'}))
        return
    bad_ch = test_chs[0]
    ch_obj = next(c for c in channels_list if c.name == bad_ch)
    ch_obj.search = AsyncMock(side_effect=RuntimeError('simulated generic failure'))
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        with patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
            server = create_server()
            tm = server._tool_manager
            result = await tm.call_tool('delegate_subtask', {'task_description': 'test generic failure', 'channels': test_chs, 'query': 'Python async', 'max_per_channel': 3})
            by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
            good_ev = sum(len(v) for k, v in by_ch.items() if k != bad_ch)
            print(json.dumps({'ok': True, 'good_evidence': good_ev, 'channels_returned': list(by_ch.keys()), 'failed_channels': result.get('failed_channels', [])}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    completed = result.get("ok", False) and "good_evidence" in result
    good_evidence = int(result.get("good_evidence", 0) or 0)
    score = 100 if good_evidence >= 2 else (70 if completed else 0)
    return ScenarioResult(
        "R6",
        "R",
        "delegate_1_channel_fails",
        score=score,
        passed=completed,
        evidence_count=good_evidence,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r7_long_query_all_free_channels(sandbox_id: str, env: dict) -> ScenarioResult:
    """R7: A long query is stable across a five-channel delegate call."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R7", "long_query_all_free_channels", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
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
    candidates = ['arxiv','hackernews','devto','ddgs','wikipedia','stackoverflow','github','dockerhub','pubmed','crossref','dblp','openalex']
    test_chs = [c for c in candidates if c in available][:5]
    if not test_chs:
        print(json.dumps({'ok': False, 'error': 'no free channels available'}))
        return
    query = 'Python async programming ' * 20
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        with patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
            server = create_server()
            tm = server._tool_manager
            result = await tm.call_tool('delegate_subtask', {'task_description': 'long query stability', 'channels': test_chs, 'query': query, 'max_per_channel': 3})
            by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
            failed = result.get('failed_channels', []) if isinstance(result, dict) else []
            total = sum(len(v) for v in by_ch.values())
            print(json.dumps({'ok': True, 'channels': test_chs, 'completed_channels': len(by_ch), 'failed_channels': failed, 'total_evidence': total, 'query_len': len(query)}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=90,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    tested = len(result.get("channels", []) or [])
    failed = len(result.get("failed_channels", []) or [])
    completed = int(result.get("completed_channels", 0) or 0)
    score = 100 if tested and failed == 0 else (int(100 * completed / tested) if tested else 0)
    return ScenarioResult(
        "R7",
        "R",
        "long_query_all_free_channels",
        score=score,
        passed=bool(result.get("ok")),
        evidence_count=int(result.get("total_evidence", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r8_unicode_query_stability(sandbox_id: str, env: dict) -> ScenarioResult:
    """R8: Mixed-script Unicode queries do not crash arxiv/ddgs calls."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R8", "unicode_query_stability", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
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
    query = '机器学习 🤖 machine learning مرحبا 日本語 mixed 🚀'
    test_chs = [c for c in ['arxiv', 'ddgs'] if c in available]
    if not test_chs:
        print(json.dumps({'ok': False, 'error': 'arxiv/ddgs unavailable'}))
        return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        tasks = [tm.call_tool('run_channel', {'channel_name': ch, 'query': query, 'k': 3}) for ch in test_chs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [str(r)[:200] for r in results if isinstance(r, Exception)]
        total = sum(len(getattr(r, 'evidence', []) or []) for r in results if not isinstance(r, Exception))
        print(json.dumps({'ok': len(errors) == 0, 'channels': test_chs, 'errors': errors, 'evidence_count': total, 'query_len': len(query)}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "R8",
        "R",
        "unicode_query_stability",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("evidence_count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r9_large_k_parameter(sandbox_id: str, env: dict) -> ScenarioResult:
    """R9: Large k values are accepted by run_channel without crashing."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "R9", "large_k_parameter", t0)
    if install_error:
        return install_error

    result, _ = await _run_python(
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
    if 'arxiv' not in available:
        print(json.dumps({'ok': False, 'error': 'arxiv not available'}))
        return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        try:
            result = await tm.call_tool('run_channel', {'channel_name': 'arxiv', 'query': 'machine learning', 'k': 100})
            print(json.dumps({'ok': True, 'result_ok': getattr(result, 'ok', None), 'count_returned': getattr(result, 'count_returned', 0), 'count_total': getattr(result, 'count_total', 0)}))
        except Exception as e:
            print(json.dumps({'ok': False, 'exception': type(e).__name__, 'error': str(e)[:300]}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "R9",
        "R",
        "large_k_parameter",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("count_returned", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def r10_10_different_channels_simultaneous(sandbox_id: str, env: dict) -> ScenarioResult:
    """R10: Ten different channels can be invoked simultaneously."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(
        sandbox_id, "R10", "10_different_channels_simultaneous", t0
    )
    if install_error:
        return install_error

    result, _ = await _run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = [c.name for c in channels_list]
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    test_chs = available[:10]
    if not test_chs:
        print(json.dumps({'ok': False, 'error': 'no channels available'}))
        return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        tasks = [tm.call_tool('run_channel', {'channel_name': ch, 'query': f'Python async {ch}', 'k': 3}) for ch in test_chs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [f'{type(r).__name__}: {str(r)[:120]}' for r in results if isinstance(r, Exception)]
        ok_results = [r for r in results if not isinstance(r, Exception)]
        total = sum(len(getattr(r, 'evidence', []) or []) for r in ok_results)
        ok = len(errors) < 3
        print(json.dumps({'ok': ok, 'channels': test_chs, 'completed': len(ok_results), 'exceptions': len(errors), 'errors': errors, 'evidence_count': total}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=120,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    exceptions = int(result.get("exceptions", 10) or 0)
    score = 100 if exceptions == 0 else (80 if exceptions == 1 else (60 if exceptions == 2 else 0))
    return ScenarioResult(
        "R10",
        "R",
        "10_different_channels_simultaneous",
        score=score,
        passed=exceptions < 3,
        evidence_count=int(result.get("evidence_count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )
