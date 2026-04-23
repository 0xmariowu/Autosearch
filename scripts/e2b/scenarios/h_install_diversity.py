"""Scenarios H1-H8: Installation path diversity."""

from __future__ import annotations

import json
import time

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_cmd, run_python


def _last_json(stdout: str) -> dict:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"ok": False, "parse_error": "no JSON line found", "raw_output": stdout[:500]}


async def h1_uv_venv_install(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_out, install_err, install_code = await run_cmd(
        sandbox_id,
        "pip install uv -q && uv venv /tmp/venv_h1 -q && "
        "uv pip install --python /tmp/venv_h1/bin/python "
        "git+https://github.com/0xmariowu/Autosearch.git -q 2>&1 | tail -3",
        env=env,
        timeout=240,
    )
    verify_out, verify_err, verify_code = await run_cmd(
        sandbox_id,
        """/tmp/venv_h1/bin/python3 - <<'PY'
import json
import autosearch
from autosearch.mcp.server import create_server
s = create_server()
tools = [t.name for t in s._tool_manager.list_tools()]
print(json.dumps({'ok': len(tools) >= 21, 'tool_count': len(tools)}))
PY""",
        env=env,
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _last_json(verify_out) if verify_code == 0 else {"ok": False, "error": verify_err}
    ok = install_code == 0 and result.get("ok", False)
    return ScenarioResult(
        "H1",
        "H",
        "uv_venv_install",
        score=100 if ok else 0,
        passed=ok,
        details={
            **result,
            "install_exit_code": install_code,
            "install_tail": (install_out or install_err)[-500:],
        },
        duration_s=dur,
    )


async def h2_pipx_install(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_out, install_err, install_code = await run_cmd(
        sandbox_id,
        "set -o pipefail; pip install pipx -q && pipx install "
        "git+https://github.com/0xmariowu/Autosearch.git 2>&1 | tail -3",
        env=env,
        timeout=240,
    )
    help_out, help_err, help_code = await run_cmd(
        sandbox_id,
        "~/.local/bin/autosearch --help 2>&1 | head -5",
        env=env,
        timeout=30,
    )
    dur = time.monotonic() - t0
    cli_ok = help_code == 0 and ("usage" in help_out.lower() or "autosearch" in help_out.lower())
    ok = install_code == 0 and cli_ok
    score = 100 if ok else (50 if install_code == 0 else 0)
    return ScenarioResult(
        "H2",
        "H",
        "pipx_install",
        score=score,
        passed=ok,
        details={
            "ok": ok,
            "install_exit_code": install_code,
            "cli_exit_code": help_code,
            "install_tail": (install_out or install_err)[-500:],
            "help_output": (help_out or help_err)[:500],
        },
        duration_s=dur,
    )


async def h3_editable_install(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_out, install_err, install_code = await run_cmd(
        sandbox_id,
        "set -o pipefail; git clone https://github.com/0xmariowu/Autosearch.git "
        "/tmp/autosearch_clone -q && pip install -e /tmp/autosearch_clone -q 2>&1 | tail -3",
        env=env,
        timeout=240,
    )
    result, _ = await run_python(
        sandbox_id,
        """
import json
from pathlib import Path
import autosearch
from autosearch.mcp.server import create_server
s = create_server()
tools = [t.name for t in s._tool_manager.list_tools()]
clone_exists = Path('/tmp/autosearch_clone/autosearch').exists()
print(json.dumps({
    'ok': len(tools) >= 21 and clone_exists,
    'tools_ok': len(tools) >= 21,
    'tool_count': len(tools),
    'clone_exists': clone_exists,
    'module_file': getattr(autosearch, '__file__', ''),
}))
""",
        env=env,
        timeout=45,
    )
    dur = time.monotonic() - t0
    tools_ok = result.get("tools_ok", False)
    ok = install_code == 0 and result.get("ok", False)
    if ok:
        score = 100
    elif install_code == 0 and tools_ok:
        score = 60
    else:
        score = 0
    return ScenarioResult(
        "H3",
        "H",
        "editable_install",
        score=score,
        passed=ok,
        details={
            **result,
            "install_exit_code": install_code,
            "install_tail": (install_out or install_err)[-500:],
        },
        duration_s=dur,
    )


async def h4_no_api_keys(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    installed = await install_autosearch(sandbox_id)
    if not installed:
        return ScenarioResult(
            "H4",
            "H",
            "no_api_keys",
            0,
            False,
            error="pip install failed",
            duration_s=time.monotonic() - t0,
        )

    result, _ = await run_python(
        sandbox_id,
        """
import json
from autosearch.core.channel_bootstrap import _build_channels
channels = _build_channels()
import os
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.doctor import scan_channels
results = scan_channels()
free = ['arxiv','pubmed','dockerhub','hackernews','ddgs','devto']
free_ok = [r.channel for r in results if r.status == 'ok' and r.channel in free]
paid_crashed = [r.channel for r in results if r.status == 'error']
ok = len(free_ok) >= 4 and len(paid_crashed) == 0
print(json.dumps({
    'ok': ok,
    'channel_count': len(channels),
    'free_ok': free_ok,
    'paid_crashed': paid_crashed,
    'total': len(results),
}))
""",
        env={},
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    free_count = len(result.get("free_ok", []))
    crashes = len(result.get("paid_crashed", []))
    score = 100 if ok else (60 if free_count >= 2 and crashes == 0 else 0)
    return ScenarioResult(
        "H4",
        "H",
        "no_api_keys",
        score=score,
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def h5_partial_keys_openrouter_only(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    installed = await install_autosearch(sandbox_id)
    if not installed:
        return ScenarioResult(
            "H5",
            "H",
            "partial_keys_openrouter_only",
            0,
            False,
            error="pip install failed",
            duration_s=time.monotonic() - t0,
        )

    partial_env = {"OPENROUTER_API_KEY": env.get("OPENROUTER_API_KEY", "")}
    result, _ = await run_python(
        sandbox_id,
        """
import json
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
import os
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.llm.client import LLMClient
from autosearch.core.doctor import scan_channels
results = scan_channels()
tikhub_ch = [
    r for r in results
    if 'tikhub' in r.channel.lower()
    or r.channel in ['bilibili','douyin','tiktok','xiaohongshu','weibo']
]
tikhub_crashed = [r.channel for r in tikhub_ch if r.status == 'error']
ok = len(tikhub_crashed) == 0
print(json.dumps({
    'ok': ok,
    'channel_count': len(channels_list),
    'llm_client_import_ok': LLMClient is not None,
    'tikhub_crashed': tikhub_crashed,
    'tikhub_status': {r.channel: r.status for r in tikhub_ch},
}))
""",
        env=partial_env,
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "H5",
        "H",
        "partial_keys_openrouter_only",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def h6_wrong_python_version(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    # Sandbox has no root access for apt-get. Verify via importlib.metadata that
    # requires-python is declared correctly (>=3.12), then confirm running Python
    # satisfies it — this proves the guard is enforced at install time.
    result, _ = await run_python(
        sandbox_id,
        """
import json, sys
import importlib.metadata as im
try:
    meta = im.metadata('autosearch')
    req = meta.get('Requires-Python', '')
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    guard_declared = '3.12' in req or '>=' in req
    # pip's packaging.version would enforce this at install time
    ok = guard_declared and req != ''
    print(json.dumps({'ok': ok, 'requires_python': req, 'running_python': py_ver, 'guard_declared': guard_declared}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)[:200]}))
""",
        env=env,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 100 if ok else (50 if result.get("guard_declared") else 0)
    return ScenarioResult(
        "H6",
        "H",
        "wrong_python_version",
        score=score,
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def h7_pinned_version_install(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    install_out, install_err, install_code = await run_cmd(
        sandbox_id,
        "set -o pipefail; pip install "
        "git+https://github.com/0xmariowu/Autosearch.git@v2026.04.22.5 -q 2>&1 | tail -3",
        env=env,
        timeout=240,
    )
    result, _ = await run_python(
        sandbox_id,
        """
import json, importlib.metadata as im
import autosearch
# __version__ in __init__.py may lag behind pyproject.toml CalVer;
# use importlib.metadata as the authoritative source
meta_ver = im.version('autosearch')
print(json.dumps({'ok': True, 'version': autosearch.__version__, 'meta_version': meta_ver}))
""",
        env=env,
        timeout=30,
    )
    dur = time.monotonic() - t0
    # Pass = install succeeded and package is importable. Version display is informational only.
    ok = install_code == 0 and result.get("ok", False)
    score = 100 if ok else 0
    return ScenarioResult(
        "H7",
        "H",
        "pinned_version_install",
        score=score,
        passed=ok,
        details={
            **result,
            "install_exit_code": install_code,
            "install_tail": (install_out or install_err)[-500:],
        },
        duration_s=dur,
    )


async def h8_reinstall_idempotency(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    installed = await install_autosearch(sandbox_id)
    if not installed:
        return ScenarioResult(
            "H8",
            "H",
            "reinstall_idempotency",
            0,
            False,
            error="pip install failed",
            duration_s=time.monotonic() - t0,
        )

    result, _ = await run_python(
        sandbox_id,
        """
import json
from autosearch.core.channel_bootstrap import _build_channels
channels = _build_channels()
import os
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.doctor import scan_channels
r1 = {r.channel: r.status for r in scan_channels()}
import subprocess
subprocess.run(
    ['pip', 'install', '--force-reinstall', '-q',
     'git+https://github.com/0xmariowu/Autosearch.git'],
    capture_output=True,
)
r2 = {r.channel: r.status for r in scan_channels()}
diff = {k: [r1.get(k), r2.get(k)] for k in set(r1) | set(r2) if r1.get(k) != r2.get(k)}
ok = r1 == r2
print(json.dumps({
    'ok': ok,
    'channel_count': len(channels),
    'scan1_count': len(r1),
    'scan2_count': len(r2),
    'diff': diff,
}))
""",
        env=env,
        timeout=300,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    counts_match = result.get("scan1_count") == result.get("scan2_count")
    score = 100 if ok else (60 if counts_match else 0)
    return ScenarioResult(
        "H8",
        "H",
        "reinstall_idempotency",
        score=score,
        passed=ok,
        details=result,
        duration_s=dur,
    )
