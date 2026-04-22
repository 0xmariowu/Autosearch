"""Scenarios A1-A3: Installation and infrastructure checks."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python

_ENV_DUMMY = {"AUTOSEARCH_LLM_MODE": "dummy"}


async def a1_clean_install(sandbox_id: str, env: dict) -> ScenarioResult:
    """A1: Install autosearch, verify MCP tools registered."""
    t0 = time.monotonic()
    ok = await install_autosearch(sandbox_id)
    if not ok:
        return ScenarioResult(
            "A1",
            "A",
            "clean_install",
            0,
            False,
            error="pip install failed",
            duration_s=time.monotonic() - t0,
        )

    result, _ = await run_python(
        sandbox_id,
        """
import os, json
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
s = create_server()
tools = [t.name for t in s._tool_manager.list_tools()]
required = ['run_clarify','run_channel','list_skills','doctor','select_channels_tool',
            'delegate_subtask','loop_init','citation_create','trace_harvest',
            'perspective_questioning','graph_search_plan']
missing = [t for t in required if t not in tools]
import autosearch
print(json.dumps({
    'ok': not missing,
    'tool_count': len(tools),
    'missing': missing,
    'version': autosearch.__version__,
}))
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok2 = result.get("ok", False)
    return ScenarioResult(
        "A1",
        "A",
        "clean_install",
        score=100 if ok2 else 40,
        passed=ok2,
        details=result,
        duration_s=dur,
    )


async def a2_channel_health(sandbox_id: str, env: dict) -> ScenarioResult:
    """A2: doctor() scans channels, free channels = ok."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.doctor import scan_channels
results = scan_channels()
ok_ch = [r.channel for r in results if r.status == 'ok']
warn_ch = [r.channel for r in results if r.status == 'warn']
off_ch = [r.channel for r in results if r.status == 'off']
# free channels should be ok
free = ['arxiv','pubmed','dockerhub','hackernews','ddgs','devto','reddit','stackoverflow']
free_ok = [c for c in free if c in ok_ch]
print(json.dumps({
    'ok': len(results) >= 34 and len(ok_ch) >= 20,
    'total': len(results),
    'ok_count': len(ok_ch),
    'warn_count': len(warn_ch),
    'off_count': len(off_ch),
    'free_channels_ok': free_ok,
    'free_channels_missing': [c for c in free if c not in ok_ch],
}))
""",
        env={**env, **_ENV_DUMMY},
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "A2",
        "A",
        "channel_health",
        score=100 if ok else 50,
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def a3_experience_layer(sandbox_id: str, env: dict) -> ScenarioResult:
    """A3: run_channel 3x, verify patterns.jsonl written correctly."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio, tempfile
from pathlib import Path
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.skills import experience as exp_mod
from autosearch.skills.experience import append_event
from datetime import UTC, datetime

with tempfile.TemporaryDirectory() as tmp:
    skill_dir = Path(tmp) / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    exp_mod._SKILLS_ROOT = Path(tmp)

    for i in range(3):
        append_event('arxiv', {
            'skill': 'arxiv', 'query': f'q{i}', 'outcome': 'success',
            'count_returned': 7, 'count_total': 10,
            'winning_pattern': 'use specific terms',
            'ts': datetime.now(UTC).isoformat(),
        })

    pf = skill_dir / 'experience' / 'patterns.jsonl'
    lines = pf.read_text().strip().splitlines() if pf.exists() else []
    ok = len(lines) == 3 and all('outcome' in l for l in lines)
    print(json.dumps({
        'ok': ok,
        'events_written': len(lines),
        'file_exists': pf.exists(),
    }))
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "A3",
        "A",
        "experience_layer",
        score=100 if ok else 30,
        passed=ok,
        details=result,
        duration_s=dur,
    )
