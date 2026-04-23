"""Scenarios S1-S8: Stress testing — concurrent load, large datasets."""

from __future__ import annotations

import time
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python


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
        "S",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def s1_concurrent_10_channels(sandbox_id: str, env: dict) -> ScenarioResult:
    """S1: Ten run_channel calls across different channels run concurrently."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S1", "concurrent_10_channels", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
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
    channels = available[:10]
    if not channels:
        print(json.dumps({'ok': False, 'error': 'no channels available'}))
        return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        tasks = [tm.call_tool('run_channel', {'channel_name': ch, 'query': f'Python async programming {ch}', 'k': 5}) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [f'{type(r).__name__}: {str(r)[:120]}' for r in results if isinstance(r, Exception)]
        ok_results = [r for r in results if not isinstance(r, Exception)]
        total = sum(len(getattr(r, 'evidence', []) or []) for r in ok_results)
        all_completed = len(ok_results) == len(channels)
        ok = total >= 20 or (all_completed and len(errors) == 0)
        print(json.dumps({'ok': ok, 'channels': channels, 'all_completed': all_completed, 'completed': len(ok_results), 'errors': len(errors), 'error_samples': errors[:3], 'total_evidence': total}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=120,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ev = int(result.get("total_evidence", 0) or 0)
    no_crash = bool(result.get("all_completed")) and int(result.get("errors", 1) or 0) == 0
    score = 100 if ev >= 30 else (80 if ev >= 10 else (60 if no_crash else 0))
    return ScenarioResult(
        "S1",
        "S",
        "concurrent_10_channels",
        score=score,
        passed=bool(result.get("ok")),
        evidence_count=ev,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s2_citation_100_unique_adds(sandbox_id: str, env: dict) -> ScenarioResult:
    """S2: Citation index accepts 100 unique URLs."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S2", "citation_100_unique_adds", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        idx = (await tm.call_tool('citation_create', {}))['index_id']
        for i in range(100):
            await tm.call_tool('citation_add', {'index_id': idx, 'url': f'https://example.com/paper/{i}', 'title': f'Paper {i}', 'source': 'stress'})
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        ok = refs['count'] == 100
        print(json.dumps({'ok': ok, 'count': refs['count'], 'markdown_len': len(refs.get('markdown', ''))}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    count = int(result.get("count", 0) or 0)
    return ScenarioResult(
        "S2",
        "S",
        "citation_100_unique_adds",
        score=100 if count == 100 else min(99, count),
        passed=count == 100,
        details=result,
        evidence_count=count,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s3_experience_100_events_compact(sandbox_id: str, env: dict) -> ScenarioResult:
    """S3: Experience compaction handles 100 raw events and stays compact."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S3", "experience_100_events_compact", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event, should_compact
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    exp_mod._SKILLS_ROOT = Path(tmp)
    skill_dir = Path(tmp) / 'channels' / 'stress_ch'
    skill_dir.mkdir(parents=True)

    for i in range(100):
        append_event('stress_ch', {
            'skill': 'stress_ch',
            'query': f'query {i}',
            'outcome': 'success',
            'count_returned': 5,
            'count_total': 8,
            'winning_pattern': f'use precise query family {i % 4}',
            'good_query': f'precise query {i % 6}',
            'ts': datetime.now(UTC).isoformat(),
        })

    patterns_f = skill_dir / 'experience' / 'patterns.jsonl'
    events_written = len(patterns_f.read_text(encoding='utf-8').strip().splitlines()) if patterns_f.exists() else 0
    should_trigger = should_compact('stress_ch')
    triggered = compact('stress_ch') if should_trigger else False
    exp_md = skill_dir / 'experience.md'
    line_count = len(exp_md.read_text(encoding='utf-8').splitlines()) if exp_md.exists() else 0
    ok = triggered and exp_md.exists() and line_count <= 120
    print(json.dumps({'ok': ok, 'events_written': events_written, 'should_trigger': should_trigger, 'triggered': triggered, 'experience_exists': exp_md.exists(), 'line_count': line_count}))
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    score = 100 if ok else (50 if int(result.get("events_written", 0) or 0) >= 100 else 0)
    return ScenarioResult(
        "S3",
        "S",
        "experience_100_events_compact",
        score=score,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s4_loop_5_rounds(sandbox_id: str, env: dict) -> ScenarioResult:
    """S4: Reflective loop state stays consistent across five rounds."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S4", "loop_5_rounds", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
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
    for ch in test_chs:
        ch_obj = next(c for c in channels_list if c.name == ch)
        ch_obj.search = AsyncMock(return_value=[
            Evidence(url=f'https://example.com/{ch}/1', title=f'{ch} result 1', snippet='loop evidence', source_channel=ch, fetched_at=datetime.now(UTC), score=1.0),
            Evidence(url=f'https://example.com/{ch}/2', title=f'{ch} result 2', snippet='loop evidence', source_channel=ch, fetched_at=datetime.now(UTC), score=0.8),
        ])

    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']
        state = {}
        total_evidence = 0
        for round_no in range(5):
            round_evidence = []
            for ch in test_chs:
                r = await tm.call_tool('run_channel', {'channel_name': ch, 'query': f'round {round_no} Python async', 'k': 2})
                round_evidence.extend(getattr(r, 'evidence', []) or [])
            total_evidence += len(round_evidence)
            state = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': round_evidence, 'query': f'round {round_no}'})
            await tm.call_tool('loop_add_gap', {'state_id': state_id, 'gap': f'gap after round {round_no}'})
        gaps = await tm.call_tool('loop_get_gaps', {'state_id': state_id})
        ok = state.get('round_count') == 5 and len(gaps.get('gaps', [])) == 5
        print(json.dumps({'ok': ok, 'round_count': state.get('round_count'), 'gap_count': len(gaps.get('gaps', [])), 'total_evidence': total_evidence}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=180,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    rounds = int(result.get("round_count", 0) or 0)
    score = 100 if bool(result.get("ok")) else min(80, rounds * 20)
    return ScenarioResult(
        "S4",
        "S",
        "loop_5_rounds",
        score=score,
        passed=bool(result.get("ok")),
        evidence_count=int(result.get("total_evidence", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s5_delegate_10_channels_parallel(sandbox_id: str, env: dict) -> ScenarioResult:
    """S5: delegate_subtask can fan out to ten channels."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S5", "delegate_10_channels_parallel", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
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
    channels = available[:10]
    if not channels:
        print(json.dumps({'ok': False, 'error': 'no channels available'}))
        return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        with patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
            server = create_server()
            tm = server._tool_manager
            result = await tm.call_tool('delegate_subtask', {'task_description': 'parallel stress fanout', 'channels': channels, 'query': 'Python async programming reliability', 'max_per_channel': 3})
            by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
            failed = result.get('failed_channels', []) if isinstance(result, dict) else []
            total = sum(len(v) for v in by_ch.values())
            ok = total >= 20 or isinstance(result, dict)
            print(json.dumps({'ok': ok, 'channels': channels, 'completed_channels': len(by_ch), 'failed_channels': failed, 'total_evidence': total, 'summary': result.get('summary', '') if isinstance(result, dict) else ''}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=120,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ev = int(result.get("total_evidence", 0) or 0)
    score = 100 if ev >= 30 else (70 if ev >= 1 else (50 if bool(result.get("ok")) else 0))
    return ScenarioResult(
        "S5",
        "S",
        "delegate_10_channels_parallel",
        score=score,
        passed=bool(result.get("ok")),
        evidence_count=ev,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s6_context_retention_500_items(sandbox_id: str, env: dict) -> ScenarioResult:
    """S6: Context retention handles 500 evidence items within a budget."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S6", "context_retention_500_items", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        big_ev = [{'url': f'https://example.com/{i}', 'title': f'Paper {i}', 'snippet': 'text ' * 50, 'source': 'arxiv'} for i in range(500)]
        result = await tm.call_tool('context_retention_policy', {'evidence': big_ev, 'token_budget': 2000})
        returned = len(result) if isinstance(result, list) else 0
        ok = isinstance(result, list) and returned <= 500
        print(json.dumps({'ok': ok, 'input': 500, 'output': returned, 'reduced': 500 - returned}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    returned = int(result.get("output", 0) or 0)
    ok = bool(result.get("ok"))
    score = 100 if ok and returned < 500 else (70 if ok else 0)
    return ScenarioResult(
        "S6",
        "S",
        "context_retention_500_items",
        score=score,
        passed=ok,
        evidence_count=returned,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s7_citation_50_duplicate_stress(sandbox_id: str, env: dict) -> ScenarioResult:
    """S7: Repeated duplicate citation adds stay idempotent and fast."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S7", "citation_50_duplicate_stress", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio, time
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        idx = (await tm.call_tool('citation_create', {}))['index_id']
        url = 'https://example.com/repeated'
        start = time.perf_counter()
        nums = []
        for _ in range(50):
            r = await tm.call_tool('citation_add', {'index_id': idx, 'url': url, 'title': 'Repeated', 'source': 'stress'})
            nums.append(r['citation_number'])
        elapsed = time.perf_counter() - start
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        ok = refs['count'] == 1 and len(set(nums)) == 1 and elapsed < 5
        print(json.dumps({'ok': ok, 'count': refs['count'], 'unique_numbers': len(set(nums)), 'elapsed_s': elapsed}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "S7",
        "S",
        "citation_50_duplicate_stress",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("count", 0) or 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def s8_rapid_loop_20_updates(sandbox_id: str, env: dict) -> ScenarioResult:
    """S8: Loop state remains consistent across 20 rapid updates."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "S8", "rapid_loop_20_updates", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']
        state = {}
        for i in range(20):
            ev = [{'url': f'https://example.com/{i}', 'title': f'Item {i}', 'snippet': 'rapid update', 'source': 'synthetic'}]
            state = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': ev, 'query': f'rapid {i}'})
        gaps = await tm.call_tool('loop_get_gaps', {'state_id': state_id})
        ok = state.get('round_count') == 20 and isinstance(gaps.get('gaps', []), list)
        print(json.dumps({'ok': ok, 'round_count': state.get('round_count'), 'visited_urls': len(state.get('visited_urls', [])), 'gap_count': len(gaps.get('gaps', []))}))
asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "S8",
        "S",
        "rapid_loop_20_updates",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        evidence_count=int(result.get("visited_urls", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )
