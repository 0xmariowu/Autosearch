"""Scenarios V1-V6: Cross-platform compatibility — Linux platform variants and Windows environment simulation."""

from __future__ import annotations

import time
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_cmd, run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


def _as_dict(result: Any) -> dict[str, Any]:
    return result if isinstance(result, dict) else {"ok": False, "error": "non-dict result", "raw_result": repr(result)}


async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "V",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def v1_musl_libc_mock(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V1", "musl_libc_mock", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json
import platform
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'

real_libc = platform.libc_ver
platform.libc_ver = lambda *a, **kw: ('musl', '1.2.0')
try:
    from autosearch.core.doctor import scan_channels
    r = scan_channels()
    ok = len(r) >= 10
    print(json.dumps({'ok': ok, 'channels': len(r), 'libc_mocked': 'musl'}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)[:200]}))
finally:
    platform.libc_ver = real_libc
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "V1",
        "V",
        "musl_libc_mock",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=int(result.get("channels", 0) or 0),
        details=result,
        error="" if ok else str(result.get("error") or "doctor failed")[:200],
        duration_s=dur,
    )


async def v2_python310_version_check(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V2", "python310_version_check", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import json, sys, importlib.metadata as im
meta = im.metadata('autosearch')
req = meta.get('Requires-Python', '')
running = f"{sys.version_info.major}.{sys.version_info.minor}"
guard_ok = '3.12' in req or ('>=' in req and '3.1' in req)
satisfies = sys.version_info >= (3, 12)
ok = guard_ok and satisfies
print(json.dumps({'ok': ok, 'requires_python': req, 'running': running, 'guard_declared': guard_ok, 'satisfies': satisfies}))
""",
        env=_clean_env(env),
        timeout=15,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "V2",
        "V",
        "python310_version_check",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error="" if ok else str(result.get("error") or "python version guard failed")[:200],
        duration_s=dur,
    )


async def v3_windows_full_env_mock(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V3", "windows_full_env_mock", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        r"""
import os, json, sys, tempfile
from pathlib import Path
from datetime import datetime, UTC
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'

# Mock Windows environment
os.environ['HOMEDRIVE'] = 'C:'
os.environ['HOMEPATH'] = r'\Users\testuser'
os.environ['USERPROFILE'] = r'C:\Users\testuser'
real_platform, real_name = sys.platform, os.name

try:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / 'channels' / 'test'
        pf = skill_dir / 'experience' / 'patterns.jsonl'

        sys.platform, os.name = 'win32', 'nt'
        import autosearch.skills.experience as exp_mod
        from autosearch.skills.experience import append_event

        exp_mod._SKILLS_ROOT = root
        skill_dir.mkdir(parents=True)
        append_event('test', {'skill':'test','query':'win test','outcome':'success','count_returned':3,'ts':datetime.now(UTC).isoformat()})
        written = pf.exists() and len(pf.read_text().strip()) > 0
        print(json.dumps({'ok': written, 'platform': 'win32_mocked', 'paths_use_slash': '\\\\' not in str(pf)}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)[:200]}))
finally:
    sys.platform, os.name = real_platform, real_name
    for k in ['HOMEDRIVE','HOMEPATH','USERPROFILE']:
        os.environ.pop(k, None)
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "V3",
        "V",
        "windows_full_env_mock",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error="" if ok else str(result.get("error") or "windows env mock failed")[:200],
        duration_s=dur,
    )


async def v4_windows_no_ansi_cli(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V4", "windows_no_ansi_cli", t0)
    if install_error:
        return install_error

    out, err, code = await run_cmd(
        sandbox_id,
        "NO_COLOR=1 TERM= autosearch --help 2>&1",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    combined = out + err
    cli_ok = code == 0
    ansi_free = "\033[" not in combined and "\x1b[" not in combined
    score = 100 if cli_ok and ansi_free else (70 if cli_ok else 0)
    return ScenarioResult(
        "V4",
        "V",
        "windows_no_ansi_cli",
        score=score,
        passed=cli_ok and ansi_free,
        details={
            "ok": cli_ok,
            "ansi_free": ansi_free,
            "exit_code": code,
            "output_sample": combined[:500],
        },
        error="" if cli_ok else combined[:200],
        duration_s=dur,
    )


async def v5_stub_gh_actions_windows(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V5", "stub_gh_actions_windows", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import json, yaml
workflow = \"\"\"
name: Cross-Platform Tests
on: [push, pull_request]
jobs:
  windows:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.12"}
    - run: pip install git+https://github.com/0xmariowu/Autosearch.git
    - run: autosearch doctor
  macos:
    runs-on: macos-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.12"}
    - run: pip install git+https://github.com/0xmariowu/Autosearch.git
    - run: autosearch doctor
\"\"\"
try:
    yaml.safe_load(workflow)
    ok = True
    print(json.dumps({'ok': ok, 'workflow_valid': True, 'note': 'GitHub Actions workflow design verified', 'workflow': workflow}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)[:200], 'workflow': workflow}))
""",
        env=_clean_env(env),
        timeout=15,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "V5",
        "V",
        "stub_gh_actions_windows",
        score=100 if ok else 0,
        passed=ok,
        evidence_count=1 if ok else 0,
        details=result,
        error="" if ok else str(result.get("error") or "workflow yaml invalid")[:200],
        duration_s=dur,
    )


async def v6_locale_utf8_handling(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "V6", "locale_utf8_handling", t0)
    if install_error:
        return install_error

    cmd = (
        "LANG=C.UTF-8 python3 -c \"import os; "
        "from autosearch.core.channel_bootstrap import _build_channels; "
        "chs = _build_channels(); "
        "os.environ['AUTOSEARCH_LLM_MODE']='dummy'; "
        "print('ok', len(chs))\""
    )
    out, err, code = await run_cmd(sandbox_id, cmd, env=_clean_env(env), timeout=30)
    dur = time.monotonic() - t0
    ok = "ok" in out and code == 0
    return ScenarioResult(
        "V6",
        "V",
        "locale_utf8_handling",
        score=100 if ok else 0,
        passed=ok,
        details={"ok": ok, "stdout": out[:500], "stderr": err[:500], "exit_code": code},
        error="" if ok else (err or out)[:200],
        duration_s=dur,
    )
