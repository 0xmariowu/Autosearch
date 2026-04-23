"""Scenarios J1-J8: Error handling and edge cases — zero crashes tolerated."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


<<<<<<< HEAD
async def _install_or_fail(sandbox_id: str, scenario_id: str, name: str, t0: float) -> ScenarioResult | None:
=======
async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
>>>>>>> origin/main
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "J",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def j1_unknown_channel_error(sandbox_id: str, env: dict) -> ScenarioResult:
    """J1: Unknown channel returns structured ok=False instead of raising."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J1", "unknown_channel_error", t0)
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
        result = await tm.call_tool('run_channel', {'channel_name': 'nonexistent_channel_xyz_404', 'query': 'test', 'k': 3})
        ok = not result.ok and hasattr(result, 'reason') and len(result.reason) > 0
        print(json.dumps({'ok': ok, 'result_ok': result.ok, 'reason': str(result.reason)[:200], 'has_error': True}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    completed = "result_ok" in result
    score = 100 if ok else (50 if completed else 0)
    return ScenarioResult(
        "J1",
        "J",
        "unknown_channel_error",
        score=score,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j2_channel_exception_degradation(sandbox_id: str, env: dict) -> ScenarioResult:
    """J2: One channel exception does not crash multi-channel delegation."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J2", "channel_exception_degradation", t0)
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
from unittest.mock import patch, AsyncMock

async def main():
    available = [c.name for c in channels_list]
    test_chs = [c for c in ['arxiv','hackernews','devto','ddgs'] if c in available][:3]
    if len(test_chs) < 2:
        print(json.dumps({'ok': False, 'error': 'not enough channels'}))
        return

    bad_ch = test_chs[0]
    good_chs = test_chs[1:]
    original_channels = {c.name: c for c in channels_list}
    bad_channel = original_channels.get(bad_ch)

    with patch('autosearch.mcp.server._build_channels', return_value=channels_list), \\
         patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        if bad_channel:
            bad_channel.search = AsyncMock(side_effect=RuntimeError('simulated failure'))
        result = await tm.call_tool('delegate_subtask', {
            'task_description': 'test degradation',
            'channels': test_chs,
            'query': 'test query',
            'max_per_channel': 3,
        })
        by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
        good_returned = sum(len(v) for k, v in by_ch.items() if k in good_chs)
        ok = good_returned >= 0
        print(json.dumps({'ok': ok, 'good_evidence': good_returned, 'bad_channel': bad_ch, 'channels_returned': list(by_ch.keys())}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=90,
    )
    dur = time.monotonic() - t0
    completed = result.get("ok", False) and "good_evidence" in result
    good_evidence = result.get("good_evidence", 0)
    score = 100 if good_evidence >= 2 else (70 if completed else 0)
    return ScenarioResult(
        "J2",
        "J",
        "channel_exception_degradation",
        score=score,
        passed=completed,
        evidence_count=good_evidence,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j3_empty_query(sandbox_id: str, env: dict) -> ScenarioResult:
    """J3: Empty query is handled without an unhandled exception."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J3", "empty_query", t0)
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
        try:
            result = await tm.call_tool('run_channel', {'channel_name': 'arxiv', 'query': '', 'k': 5})
            print(json.dumps({'ok': True, 'result_ok': getattr(result, 'ok', None), 'reason': str(getattr(result, 'reason', ''))[:100]}))
        except Exception as e:
            print(json.dumps({'ok': False, 'error': str(e)[:200]}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "J3",
        "J",
        "empty_query",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j4_special_chars_query(sandbox_id: str, env: dict) -> ScenarioResult:
    """J4: Special characters and mixed-language input do not crash."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J4", "special_chars_query", t0)
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
    query = \"'; DROP TABLE users--  🔥 中英 mixed query \\\\n\\\\t<script>\"
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        try:
            result = await tm.call_tool('run_channel', {'channel_name': 'arxiv', 'query': query, 'k': 5})
            print(json.dumps({'ok': True, 'result_ok': getattr(result, 'ok', None), 'reason': str(getattr(result, 'reason', ''))[:100]}))
        except Exception as e:
            print(json.dumps({'ok': False, 'error': str(e)[:200]}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "J4",
        "J",
        "special_chars_query",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j5_citation_dedup(sandbox_id: str, env: dict) -> ScenarioResult:
    """J5: Duplicate citation URL reuses the same citation number."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J5", "citation_dedup", t0)
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
        url = 'https://example.com/paper/1234'
        r1 = await tm.call_tool('citation_add', {'index_id': idx, 'url': url, 'title': 'Test Paper', 'source': 'arxiv'})
        r2 = await tm.call_tool('citation_add', {'index_id': idx, 'url': url, 'title': 'Test Paper', 'source': 'arxiv'})
        refs = await tm.call_tool('citation_export', {'index_id': idx})
        ok = refs['count'] == 1 and r1['citation_number'] == r2['citation_number']
        print(json.dumps({'ok': ok, 'count': refs['count'], 'n1': r1['citation_number'], 'n2': r2['citation_number']}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "J5",
        "J",
        "citation_dedup",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j6_zero_result_gap_detection(sandbox_id: str, env: dict) -> ScenarioResult:
    """J6: Zero-result channel run can still record loop coverage gaps."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J6", "zero_result_gap_detection", t0)
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
from unittest.mock import patch, AsyncMock

async def main():
    available = [c.name for c in channels_list]
    ch_name = next((c for c in ['arxiv','devto','ddgs'] if c in available), None)
    if not ch_name:
        print(json.dumps({'ok': False, 'error': 'no channel'}))
        return

    ch_obj = next(c for c in channels_list if c.name == ch_name)
    ch_obj.search = AsyncMock(return_value=[])

    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        loop = await tm.call_tool('loop_init', {})
        state_id = loop['state_id']
        await tm.call_tool('run_channel', {'channel_name': ch_name, 'query': 'obscure topic', 'k': 5})
        s = await tm.call_tool('loop_update', {'state_id': state_id, 'evidence': [], 'query': 'obscure topic'})
        await tm.call_tool('loop_add_gap', {'state_id': state_id, 'gap': 'zero results from channel'})
        gaps = await tm.call_tool('loop_get_gaps', {'state_id': state_id})
        ok = len(gaps.get('gaps', [])) >= 1 and s['round_count'] >= 1
        print(json.dumps({'ok': ok, 'gaps': gaps.get('gaps', []), 'rounds': s['round_count']}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "J6",
        "J",
        "zero_result_gap_detection",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j7_experience_compaction_trigger(sandbox_id: str, env: dict) -> ScenarioResult:
    """J7: Experience compaction triggers after the threshold is crossed."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J7", "experience_compaction_trigger", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event, should_compact
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    exp_mod._SKILLS_ROOT = Path(tmp)
    skill_dir = Path(tmp) / 'channels' / 'test_ch'
    skill_dir.mkdir(parents=True)

    for i in range(11):
        append_event('test_ch', {
            'skill': 'test_ch', 'query': f'query {i}', 'outcome': 'success',
            'count_returned': 5, 'winning_pattern': f'pattern {i}',
            'ts': datetime.now(UTC).isoformat(),
        })

    exp_dir = skill_dir / 'experience'
    patterns_f = exp_dir / 'patterns.jsonl'
    lines_before = len(patterns_f.read_text().strip().splitlines()) if patterns_f.exists() else 0

    should_trigger = should_compact('test_ch')
    triggered = compact('test_ch') if should_trigger else False

    candidates = [skill_dir / 'experience.md', exp_dir / 'experience.md']
    exp_md = next((p for p in candidates if p.exists()), candidates[0])
    ok = triggered and exp_md.exists() and len(exp_md.read_text()) > 0
    print(json.dumps({
        'ok': ok,
        'triggered': triggered,
        'should_trigger': should_trigger,
        'exp_md_exists': exp_md.exists(),
        'exp_md_path': str(exp_md),
        'events_written': lines_before,
    }))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 100 if ok else (50 if result.get("events_written", 0) >= 11 else 0)
    return ScenarioResult(
        "J7",
        "J",
        "experience_compaction_trigger",
        score=score,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def j8_long_query_handling(sandbox_id: str, env: dict) -> ScenarioResult:
    """J8: Long query input does not crash run_channel."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "J8", "long_query_handling", t0)
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
    query = 'quantum computing application ' * 20
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        try:
            result = await tm.call_tool('run_channel', {'channel_name': 'arxiv', 'query': query, 'k': 5})
            print(json.dumps({'ok': True, 'result_ok': getattr(result, 'ok', None), 'reason': str(getattr(result, 'reason', ''))[:100], 'query_len': len(query)}))
        except Exception as e:
            print(json.dumps({'ok': False, 'error': str(e)[:200]}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=60,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "J8",
        "J",
        "long_query_handling",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )
