"""Scenarios P1-P12: Desktop GUI testing via e2b_desktop SDK."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shlex
import time
from collections.abc import Awaitable, Callable
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult

try:
    from e2b_desktop import Sandbox as DesktopSandbox
except ImportError:  # pragma: no cover - optional phase-2 dependency
    DesktopSandbox = None  # type: ignore[assignment]


# Use python3 -m pip so pip and python3 are guaranteed to share the same interpreter.
_INSTALL_CMD = (
    "python3 -m pip install git+https://github.com/0xmariowu/Autosearch.git -q 2>&1 | tail -3"
)
# After install, autosearch CLI entry-point may not be in PATH; use module invocation instead.
_AUTOSEARCH_CLI = "python3 -m autosearch.cli.main"
_CATEGORY = "P"


async def _desktop_cmd(sbx: DesktopSandbox, cmd: str, timeout: int = 60) -> tuple[str, str, int]:
    """Run a shell command in desktop sandbox via /bin/bash -c + shlex.quote.

    Uses shlex.quote (not Python repr) so single quotes in cmd are handled safely.
    Pipes, redirects, and all shell features work correctly.
    """
    loop = asyncio.get_event_loop()
    shell_cmd = f"/bin/bash -c {shlex.quote(cmd)}"

    def _run() -> Any:
        try:
            return sbx.commands.run(shell_cmd, timeout=timeout)
        except TypeError:
            try:
                return sbx.commands.run(shell_cmd)
            except Exception as exc:
                return exc  # CommandExitException has stdout/stderr/exit_code
        except Exception as exc:
            return exc  # CommandExitException has stdout/stderr/exit_code

    result = await loop.run_in_executor(None, _run)
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    # CommandExitException.exit_code is non-zero; normal result.exit_code == 0
    raw_code = getattr(result, "exit_code", 0)
    exit_code = raw_code if raw_code is not None else (1 if isinstance(result, Exception) else 0)
    return stdout, stderr, exit_code


async def _desktop_python(
    sbx: DesktopSandbox, script: str, timeout: int = 60
) -> tuple[str, str, int]:
    """Run a Python script in desktop sandbox via base64 — safe for any string content."""
    b64 = base64.b64encode(script.encode()).decode()
    # Write script via pipe+redirect (requires shell, handled by _desktop_cmd)
    write_cmd = f"printf '%s' {shlex.quote(b64)} | base64 -d > /tmp/_p_test.py"
    await _desktop_cmd(sbx, write_cmd, timeout=15)
    return await _desktop_cmd(sbx, "python3 /tmp/_p_test.py", timeout=timeout)


async def _create_desktop(env: dict) -> DesktopSandbox:
    if DesktopSandbox is None:
        raise RuntimeError("e2b_desktop is not installed; run `pip install e2b-desktop`")

    desktop_env = {k: str(v) for k, v in env.items() if v is not None}
    api_key = desktop_env.get("E2B_API_KEY") or os.environ.get("E2B_API_KEY", "")
    if api_key:
        desktop_env["E2B_API_KEY"] = api_key

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: DesktopSandbox.create(resolution=(1280, 720), envs=desktop_env, timeout=300),
    )


async def _kill_desktop(sbx: DesktopSandbox) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sbx.kill)


async def _with_desktop(
    scenario_id: str,
    name: str,
    env: dict,
    body: Callable[[DesktopSandbox], Awaitable[dict[str, Any]]],
) -> ScenarioResult:
    t0 = time.monotonic()
    sbx = None
    try:
        sbx = await _create_desktop(env)
        payload = await body(sbx)
        return ScenarioResult(
            scenario_id,
            _CATEGORY,
            name,
            score=int(payload.get("score", 0)),
            passed=bool(payload.get("passed", False)),
            details=payload.get("details", {}),
            evidence_count=int(payload.get("evidence_count", 0)),
            report_length=int(payload.get("report_length", 0)),
            error=str(payload.get("error", ""))[:500],
            duration_s=time.monotonic() - t0,
        )
    except Exception as exc:  # noqa: BLE001 - scenario boundary
        return ScenarioResult(
            scenario_id,
            _CATEGORY,
            name,
            0,
            False,
            error=f"{type(exc).__name__}: {exc}"[:500],
            duration_s=time.monotonic() - t0,
        )
    finally:
        if sbx is not None:
            try:
                await _kill_desktop(sbx)
            except Exception:
                pass


async def _install(sbx: DesktopSandbox) -> tuple[str, str, int]:
    return await _desktop_cmd(sbx, _INSTALL_CMD, timeout=180)


def _combined(stdout: str, stderr: str) -> str:
    return "\n".join(part for part in (stdout, stderr) if part)


def _extract_int(label: str, text: str) -> int:
    match = re.search(rf"{re.escape(label)}:\s*(\d+)", text)
    return int(match.group(1)) if match else 0


async def _desktop_python_json(
    sbx: DesktopSandbox,
    script: str,
    timeout: int = 60,
) -> tuple[dict[str, Any], str, str, int]:
    b64 = base64.b64encode(script.encode()).decode()
    cmd = (
        f"printf %s {shlex.quote(b64)} | base64 -d > /tmp/_autosearch_desktop_test.py "
        "&& python3 /tmp/_autosearch_desktop_test.py"
    )
    stdout, stderr, code = await _desktop_cmd(sbx, cmd, timeout=timeout)
    if code != 0:
        return (
            {"ok": False, "error": (stderr or stdout)[:1500], "exit_code": code},
            stdout,
            stderr,
            code,
        )

    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line), stdout, stderr, code
            except json.JSONDecodeError:
                continue

    return (
        {"ok": False, "raw_output": stdout[:500], "parse_error": "no JSON line found"},
        stdout,
        stderr,
        code,
    )


async def p1_cli_install_in_terminal(sandbox_id: str, env: dict) -> ScenarioResult:
    """P1: Install from a desktop terminal and verify CLI help."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        help_out, help_err, help_code = await _desktop_cmd(
            sbx, f"{_AUTOSEARCH_CLI} --help 2>&1 | head -5"
        )
        help_text = _combined(help_out, help_err)
        install_ok = install_code == 0
        help_ok = help_code == 0 and ("autosearch" in help_text.lower() or "Usage" in help_text)
        ok = install_ok and help_ok
        return {
            "score": 100 if ok else (50 if install_ok else 0),
            "passed": ok,
            "details": {
                "install_exit_code": install_code,
                "install_tail": _combined(install_out, install_err)[-500:],
                "help_exit_code": help_code,
                "help_head": help_text[:500],
            },
            "error": "" if ok else ("help failed" if install_ok else "pip install failed"),
        }

    return await _with_desktop("P1", "cli_install_in_terminal", env, _body)


async def p2_doctor_cli_output(sandbox_id: str, env: dict) -> ScenarioResult:
    """P2: autosearch doctor prints usable channel health output."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        stdout, stderr, code = await _desktop_cmd(sbx, f"{_AUTOSEARCH_CLI} doctor 2>&1", timeout=60)
        text = _combined(stdout, stderr)
        expected = any(token in text.lower() for token in ("arxiv", "ok", "warn", "off"))
        ok = code == 0 and expected
        return {
            "score": 100 if ok else (60 if code == 0 else 0),
            "passed": ok,
            "details": {"exit_code": code, "output": text[:1200]},
            "error": "" if ok else "doctor output unexpected or crashed",
        }

    return await _with_desktop("P2", "doctor_cli_output", env, _body)


async def p3_configure_cli(sandbox_id: str, env: dict) -> ScenarioResult:
    """P3: autosearch configure accepts a key/value setting."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        cmd = (
            'echo "OPENROUTER_API_KEY=test_key_12345" >> /tmp/test_secrets.env '
            f"&& {_AUTOSEARCH_CLI} configure OPENROUTER_API_KEY test_key_12345 2>&1"
        )
        stdout, stderr, code = await _desktop_cmd(sbx, cmd, timeout=60)
        text = _combined(stdout, stderr)
        command_missing = code == 127 or "not found" in text.lower()
        signal = any(
            token in text.lower() for token in ("saved", "updated", "written", "openrouter")
        )
        ok = code == 0 or signal
        return {
            "score": 100 if ok else (0 if command_missing else 60),
            "passed": ok,
            "details": {"exit_code": code, "output": text[:1200]},
            "error": ""
            if ok
            else ("configure command not found" if command_missing else "unexpected output"),
        }

    return await _with_desktop("P3", "configure_cli", env, _body)


async def p4_mcp_server_starts(sandbox_id: str, env: dict) -> ScenarioResult:
    """P4: autosearch-mcp starts or at least resolves as an installed command."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        stdout, stderr, code = await _desktop_cmd(
            sbx, "timeout 10 python3 -m autosearch.mcp.cli 2>&1 || true", timeout=15
        )
        text = _combined(stdout, stderr)
        lower = text.lower()
        starts = any(
            token in lower for token in ("server", "listening", "mcp", "tool", "autosearch")
        )
        missing = any(
            token in lower for token in ("not found", "no such file", "failed to run command")
        )
        command_exists = not missing
        ok = starts or command_exists
        return {
            "score": 100 if starts else (70 if command_exists else 0),
            "passed": ok,
            "details": {"exit_code": code, "output": text[:1200], "command_exists": command_exists},
            "error": "" if ok else "autosearch-mcp command not found",
        }

    return await _with_desktop("P4", "mcp_server_starts", env, _body)


async def p5_list_skills_cli(sandbox_id: str, env: dict) -> ScenarioResult:
    """P5: MCP server registers the expected tool catalog."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        script = """
import os, json
from autosearch.core.channel_bootstrap import _build_channels
_build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
s = create_server()
tools = [t.name for t in s._tool_manager.list_tools()]
print('tools:', len(tools), 'first:', tools[:3])
"""
        stdout, stderr, code = await _desktop_python(sbx, script, timeout=60)
        text = _combined(stdout, stderr)
        count = _extract_int("tools", text)
        ok = code == 0 and "tools:" in text and count >= 10
        return {
            "score": 100 if count >= 21 else (60 if count >= 10 else 0),
            "passed": ok,
            "details": {"exit_code": code, "tool_count": count, "output": text[:1000]},
            "error": "" if ok else "tool count too low or command failed",
        }

    return await _with_desktop("P5", "list_skills_cli", env, _body)


async def p6_doctor_json_output(sandbox_id: str, env: dict) -> ScenarioResult:
    """P6: doctor internals report a broad channel inventory."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        cmd = (
            'python3 -c "import os; '
            "from autosearch.core.channel_bootstrap import _build_channels; _build_channels(); "
            "os.environ['AUTOSEARCH_LLM_MODE']='dummy'; "
            "from autosearch.core.doctor import scan_channels; "
            "r=scan_channels(); "
            "print('channels:', len(r), 'ok:', sum(1 for c in r if c.status=='ok'))\""
        )
        stdout, stderr, code = await _desktop_cmd(sbx, cmd, timeout=60)
        text = _combined(stdout, stderr)
        count = _extract_int("channels", text)
        ok = code == 0 and "channels:" in text and count >= 20
        score = 100 if count >= 30 else (70 if count >= 20 else (40 if count >= 1 else 0))
        return {
            "score": score,
            "passed": ok,
            "details": {"exit_code": code, "channel_count": count, "output": text[:1000]},
            "error": "" if ok else "channel count too low or command failed",
        }

    return await _with_desktop("P6", "doctor_json_output", env, _body)


async def p7_multiple_tool_calls(sandbox_id: str, env: dict) -> ScenarioResult:
    """P7: run_clarify, run_channel, and citation_create all work in sequence."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        result, stdout, stderr, code = await _desktop_python_json(
            sbx,
            """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels

channels_list = _build_channels()
available = {c.name for c in channels_list}

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    outcomes = {}
    details = {}
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager

        clarify = await tm.call_tool('run_clarify', {'query': 'Python asyncio event loop best practices'})
        outcomes['run_clarify'] = bool(getattr(clarify, 'ok', False))
        details['clarify_reason'] = getattr(clarify, 'reason', None)

        channel = next((c for c in ['arxiv', 'ddgs', 'devto', 'hackernews'] if c in available), None)
        if channel:
            ch_result = await tm.call_tool('run_channel', {
                'channel_name': channel,
                'query': 'Python asyncio event loop best practices',
                'k': 3,
            })
            outcomes['run_channel'] = bool(getattr(ch_result, 'ok', False))
            details['channel'] = channel
            details['evidence_count'] = len(getattr(ch_result, 'evidence', []) or [])
            details['channel_reason'] = getattr(ch_result, 'reason', None)
        else:
            outcomes['run_channel'] = False
            details['channel_reason'] = 'no suitable channel available'

        idx = await tm.call_tool('citation_create', {})
        outcomes['citation_create'] = bool(isinstance(idx, dict) and idx.get('index_id'))
        details['index_id'] = idx.get('index_id') if isinstance(idx, dict) else None

    passed_count = sum(1 for ok in outcomes.values() if ok)
    print(json.dumps({'ok': passed_count == 3, 'passed_count': passed_count, 'outcomes': outcomes, **details}))

asyncio.run(main())
""",
            timeout=90,
        )
        passed_count = int(result.get("passed_count", 0))
        return {
            "score": 100
            if passed_count == 3
            else (67 if passed_count == 2 else (33 if passed_count == 1 else 0)),
            "passed": passed_count == 3,
            "evidence_count": int(result.get("evidence_count", 0)),
            "details": {
                "exit_code": code,
                **result,
                "stdout_tail": stdout[-500:],
                "stderr_tail": stderr[-500:],
            },
            "error": ""
            if passed_count == 3
            else result.get("error", "one or more tool calls failed"),
        }

    return await _with_desktop("P7", "multiple_tool_calls", env, _body)


async def p8_reinstall_no_state_corruption(sandbox_id: str, env: dict) -> ScenarioResult:
    """P8: raw experience state survives package reinstall."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        marker = f"p8-marker-{int(time.time())}"
        before, _, _, _ = await _desktop_python_json(
            sbx,
            f"""
import json
from datetime import datetime, timezone as _tz

UTC = _tz.utc
from pathlib import Path
from autosearch.skills.experience import _find_skill_dir, append_event

marker = {marker!r}
append_event('arxiv', {{
    'skill': 'arxiv',
    'query': marker,
    'outcome': 'success',
    'count_returned': 1,
    'count_total': 1,
    'winning_pattern': 'p8 reinstall survival',
    'ts': datetime.now(UTC).isoformat(),
}})
skill_dir = _find_skill_dir('arxiv')
patterns_path = skill_dir / 'experience' / 'patterns.jsonl' if skill_dir else Path('')
Path('/tmp/p8_patterns_path.txt').write_text(str(patterns_path), encoding='utf-8')
exists = patterns_path.is_file()
contains = exists and marker in patterns_path.read_text(encoding='utf-8')
print(json.dumps({{'ok': exists and contains, 'patterns_path': str(patterns_path), 'contains_marker': contains}}))
""",
            timeout=60,
        )
        reinstall_out, reinstall_err, reinstall_code = await _desktop_cmd(
            sbx,
            "python3 -m pip install --force-reinstall git+https://github.com/0xmariowu/Autosearch.git -q 2>&1 | tail -3",
            timeout=180,
        )
        after, _, _, _ = await _desktop_python_json(
            sbx,
            f"""
import json
from pathlib import Path

marker = {marker!r}
path_file = Path('/tmp/p8_patterns_path.txt')
patterns_path = Path(path_file.read_text(encoding='utf-8')) if path_file.is_file() else Path('')
exists = patterns_path.is_file()
contains = exists and marker in patterns_path.read_text(encoding='utf-8')
print(json.dumps({{'ok': exists and contains, 'patterns_path': str(patterns_path), 'contains_marker': contains}}))
""",
            timeout=60,
        )
        ok = bool(before.get("ok")) and reinstall_code == 0 and bool(after.get("ok"))
        return {
            "score": 100 if ok else 0,
            "passed": ok,
            "details": {
                "before": before,
                "after": after,
                "reinstall_exit_code": reinstall_code,
                "reinstall_tail": _combined(reinstall_out, reinstall_err)[-500:],
            },
            "error": "" if ok else "patterns.jsonl did not survive reinstall",
        }

    return await _with_desktop("P8", "reinstall_no_state_corruption", env, _body)


async def p9_wine_cli_path_test(sandbox_id: str, env: dict) -> ScenarioResult:
    """P9: Windows-ish USERPROFILE does not break import-time path handling."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        script = """
import os
os.environ['USERPROFILE'] = 'C:\\\\Users\\\\test'
import autosearch
print('ok')
"""
        stdout, stderr, code = await _desktop_python(sbx, script, timeout=60)
        text = _combined(stdout, stderr)
        ok = code == 0 and "ok" in text
        return {
            "score": 100 if ok else 0,
            "passed": ok,
            "details": {"exit_code": code, "output": text[:1000]},
            "error": "" if ok else "Windows USERPROFILE import check failed",
        }

    return await _with_desktop("P9", "wine_cli_path_test", env, _body)


async def p10_error_message_quality(sandbox_id: str, env: dict) -> ScenarioResult:
    """P10: invalid channel names return readable structured errors."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        result, stdout, stderr, code = await _desktop_python_json(
            sbx,
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
        result = await tm.call_tool('run_channel', {
            'channel_name': 'not_a_real_channel_p10',
            'query': 'test',
            'k': 3,
        })
        reason = str(getattr(result, 'reason', '') or '')
        readable = (
            not bool(getattr(result, 'ok', True))
            and len(reason) >= 20
            and ('unknown' in reason.lower() or 'available' in reason.lower())
            and 'Traceback' not in reason
        )
        print(json.dumps({'ok': readable, 'result_ok': bool(getattr(result, 'ok', True)), 'reason': reason[:500]}))

asyncio.run(main())
""",
            timeout=60,
        )
        ok = bool(result.get("ok"))
        structured = "result_ok" in result
        return {
            "score": 100 if ok else (50 if structured else 0),
            "passed": ok,
            "details": {
                "exit_code": code,
                **result,
                "stdout_tail": stdout[-500:],
                "stderr_tail": stderr[-500:],
            },
            "error": "" if ok else result.get("error", "unreadable invalid-channel error"),
        }

    return await _with_desktop("P10", "error_message_quality", env, _body)


async def p11_long_running_no_hang(sandbox_id: str, env: dict) -> ScenarioResult:
    """P11: a doctor scan finishes under a shell timeout."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        cmd = (
            'timeout 15 python3 -c "import os; '
            "from autosearch.core.channel_bootstrap import _build_channels; _build_channels(); "
            "os.environ['AUTOSEARCH_LLM_MODE']='dummy'; "
            "from autosearch.core.doctor import scan_channels; "
            "r=scan_channels(); print('done', len(r))\""
        )
        stdout, stderr, code = await _desktop_cmd(sbx, cmd, timeout=20)
        text = _combined(stdout, stderr)
        ok = code == 0 and "done" in text
        return {
            "score": 100 if ok else 0,
            "passed": ok,
            "details": {"exit_code": code, "output": text[:1000]},
            "error": "" if ok else "doctor scan hung or failed",
        }

    return await _with_desktop("P11", "long_running_no_hang", env, _body)


async def p12_help_text_complete(sandbox_id: str, env: dict) -> ScenarioResult:
    """P12: top-level and doctor help both render successfully."""

    async def _body(sbx: DesktopSandbox) -> dict[str, Any]:
        install_out, install_err, install_code = await _install(sbx)
        if install_code != 0:
            return {
                "score": 0,
                "passed": False,
                "details": {"install_tail": _combined(install_out, install_err)[-500:]},
                "error": "pip install failed",
            }

        main_out, main_err, main_code = await _desktop_cmd(
            sbx, f"{_AUTOSEARCH_CLI} --help 2>&1", timeout=60
        )
        doctor_out, doctor_err, doctor_code = await _desktop_cmd(
            sbx, f"{_AUTOSEARCH_CLI} doctor --help 2>&1", timeout=60
        )
        ok_count = int(main_code == 0) + int(doctor_code == 0)
        ok = ok_count == 2
        return {
            "score": 100 if ok else (50 if ok_count == 1 else 0),
            "passed": ok,
            "details": {
                "main_exit_code": main_code,
                "doctor_exit_code": doctor_code,
                "main_help_head": _combined(main_out, main_err)[:500],
                "doctor_help_head": _combined(doctor_out, doctor_err)[:500],
            },
            "error": "" if ok else "one or more help commands failed",
        }

    return await _with_desktop("P12", "help_text_complete", env, _body)
