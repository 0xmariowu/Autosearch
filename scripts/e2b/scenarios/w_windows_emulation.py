"""Scenarios W1-W3: Windows platform emulation — crash safety only (not full Windows compatibility)."""

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
        "W",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def w1_windows_platform_mock(sandbox_id: str, env: dict) -> ScenarioResult:
    """W1: Post-import Windows platform mock does not break experience writes."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "W1", "windows_platform_mock", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, sys, tempfile
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from datetime import datetime, UTC
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    exp_mod._SKILLS_ROOT = Path(tmp)
    (Path(tmp) / 'channels' / 'test_ch').mkdir(parents=True)
    pf = Path(tmp)/'channels'/'test_ch'/'experience'/'patterns.jsonl'
    real_p, real_n = sys.platform, os.name
    sys.platform = 'win32'; os.name = 'nt'
    try:
        append_event('test_ch', {'skill':'test_ch','query':'test','outcome':'success','count_returned':3,'ts':datetime.now(UTC).isoformat()})
        written = pf.exists() and len(pf.read_text().strip()) > 0
        print(json.dumps({'ok': written, 'written': written, 'note': 'post-import mock only'}))
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e)[:200]}))
    finally:
        sys.platform = real_p; os.name = real_n
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "W1",
        "W",
        "windows_platform_mock",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def w2_windows_home_dir_mock(sandbox_id: str, env: dict) -> ScenarioResult:
    """W2: Windows USERPROFILE in the environment does not crash imports."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "W2", "windows_home_dir_mock", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
os.environ['USERPROFILE'] = r'C:\\Users\\TestUser'
try:
    from autosearch.config import settings as cfg_settings
    home = str(getattr(cfg_settings, 'home_dir', os.environ.get('HOME', 'N/A')))
    ok = 'C:\\\\' not in home
    print(json.dumps({'ok': True, 'home_used': home, 'windows_ignored': ok}))
except ImportError:
    # config module may not exist, check simpler import
    import autosearch
    print(json.dumps({'ok': True, 'note': 'no config module, import ok'}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)[:200]}))
finally:
    os.environ.pop('USERPROFILE', None)
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "W2",
        "W",
        "windows_home_dir_mock",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def w3_windows_path_separator(sandbox_id: str, env: dict) -> ScenarioResult:
    """W3: Windows-style path separators in queries do not crash channel search."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "W3", "windows_path_separator", t0)
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
    win_query = r"C:\\Users\\vimala\\Documents\\project\\README.md file path handling in Python"
    ch = next((c for c in ['arxiv','devto','ddgs'] if c in _av), None)
    if not ch:
        print(json.dumps({'ok': True, 'skipped': True})); return
    with patch('autosearch.mcp.server._build_channels', return_value=_cl):
        server = create_server()
        tm = server._tool_manager
        try:
            r = await tm.call_tool('run_channel', {'channel_name': ch, 'query': win_query, 'k': 3})
            print(json.dumps({'ok': True, 'result_ok': r.ok, 'evidence': len(r.evidence) if r.ok else 0}))
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
        "W3",
        "W",
        "windows_path_separator",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=result.get("evidence", 0),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )
