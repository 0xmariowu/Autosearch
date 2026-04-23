"""E2B sandbox runner — create / exec / kill helpers."""

from __future__ import annotations

import base64
import json
import os
import struct
from dataclasses import dataclass, field
from typing import Any

import httpx

E2B_API_KEY = os.environ.get("E2B_API_KEY", "")
TEMPLATE_ID = "y6nmb7m9h84kswgrddd6"  # autosearch-claude
MANAGEMENT_URL = "https://api.e2b.app"
SANDBOX_TIMEOUT = 900  # 15 min


# ── Keys to inject from local env ────────────────────────────────────────────

_KEY_NAMES = [
    "OPENROUTER_API_KEY",
    "TIKHUB_API_KEY",
    "GITHUB_TOKEN",
    "YOUTUBE_API_KEY",
]


def _collect_keys() -> dict[str, str]:
    """Read keys from local env (populated from ai-secrets.env by ~/.zshenv)."""
    keys: dict[str, str] = {}
    for name in _KEY_NAMES:
        val = os.environ.get(name, "").strip()
        if val:
            keys[name] = val
    return keys


# ── ConnectRPC helpers ────────────────────────────────────────────────────────


def _encode_msg(payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return struct.pack(">BI", 0, len(body)) + body


def _decode_stream(raw: bytes) -> list[dict]:
    msgs: list[dict] = []
    i = 0
    while i < len(raw):
        if i + 5 > len(raw):
            break
        _flags, length = struct.unpack(">BI", raw[i : i + 5])
        i += 5
        if i + length > len(raw):
            break
        data = raw[i : i + length]
        i += length
        try:
            obj = json.loads(data)
            ev = obj.get("event", obj)
            msgs.append(ev)
        except json.JSONDecodeError:
            pass
    return msgs


# ── Sandbox lifecycle ─────────────────────────────────────────────────────────


async def create_sandbox(client: httpx.AsyncClient) -> str:
    api_key = os.environ.get("E2B_API_KEY", E2B_API_KEY)
    resp = await client.post(
        f"{MANAGEMENT_URL}/sandboxes",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={"templateID": TEMPLATE_ID, "timeout": SANDBOX_TIMEOUT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["sandboxID"]


async def kill_sandbox(client: httpx.AsyncClient, sandbox_id: str) -> None:
    try:
        api_key = os.environ.get("E2B_API_KEY", E2B_API_KEY)
        await client.delete(
            f"{MANAGEMENT_URL}/sandboxes/{sandbox_id}",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
    except Exception:
        pass


# ── Command execution ─────────────────────────────────────────────────────────


async def run_cmd(
    sandbox_id: str,
    cmd: str,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, str, int]:
    """Run a bash command in the sandbox. Returns (stdout, stderr, exit_code)."""
    url = f"https://49983-{sandbox_id}.e2b.app/process.Process/Start"
    payload = {
        "process": {
            "cmd": "/bin/bash",
            "args": ["-c", cmd],
            "envs": env or {},
            "cwd": "/home/user",
        },
        "pty": None,
        "tag": None,
        "stdin": False,
    }
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    exit_code = -1

    _client = client or httpx.AsyncClient(timeout=timeout)
    try:
        async with _client.stream(
            "POST",
            url,
            headers={
                "Connect-Protocol-Version": "1",
                "Content-Type": "application/connect+json",
            },
            content=_encode_msg(payload),
        ) as resp:
            resp.raise_for_status()
            raw = b""
            async for chunk in resp.aiter_bytes():
                raw += chunk
    finally:
        if client is None:
            await _client.aclose()

    for ev in _decode_stream(raw):
        if "data" in ev:
            d = ev["data"]
            if d.get("stdout"):
                stdout_parts.append(base64.b64decode(d["stdout"]).decode("utf-8", errors="replace"))
            if d.get("stderr"):
                stderr_parts.append(base64.b64decode(d["stderr"]).decode("utf-8", errors="replace"))
        elif "end" in ev:
            status = ev["end"].get("status", "")
            exit_code = 0 if status == "exit status 0" else 1
        elif "error" in ev:
            exit_code = 1

    return "".join(stdout_parts), "".join(stderr_parts), exit_code


async def run_python(
    sandbox_id: str,
    script: str,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> tuple[Any, str]:
    """Run a Python script; parse stdout as JSON. Returns (result_dict, stderr).

    Uses a temp file to avoid shell-escaping issues with complex scripts.
    Extracts the last JSON line from stdout (skipping structlog lines).
    """
    import base64 as _b64

    # Write script to sandbox via echo+base64 to avoid any escaping issues
    b64 = _b64.b64encode(script.encode()).decode()
    write_cmd = f"echo '{b64}' | base64 -d > /tmp/_autosearch_test.py"
    await run_cmd(sandbox_id, write_cmd, timeout=15)

    out, err, code = await run_cmd(
        sandbox_id,
        "python3 /tmp/_autosearch_test.py",
        env=env,
        timeout=timeout,
    )
    if code != 0:
        full_error = err or out
        return {"ok": False, "error": full_error[:1500], "exit_code": code}, err

    # Find the last line that looks like JSON (handles structlog noise on stdout)
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line), err
            except json.JSONDecodeError:
                continue

    return {"ok": False, "raw_output": out[:500], "parse_error": "no JSON line found"}, err


# ── Install autosearch ────────────────────────────────────────────────────────

AUTOSEARCH_INSTALL_CMD = (
    "pip3 install git+https://github.com/0xmariowu/Autosearch.git -q 2>&1 | tail -3"
)


async def install_autosearch(sandbox_id: str, timeout: int = 180) -> bool:
    _, _, code = await run_cmd(sandbox_id, AUTOSEARCH_INSTALL_CMD, timeout=timeout)
    return code == 0


async def clone_autosearch(
    sandbox_id: str, clone_path: str = "/tmp/autosearch_k", timeout: int = 300
) -> bool:
    """Clone autosearch repo and pip install -e so judge reads cloned skills/."""
    _, _, c1 = await run_cmd(
        sandbox_id,
        f"git clone https://github.com/0xmariowu/Autosearch.git {clone_path} -q 2>&1 | tail -2",
        timeout=120,
    )
    if c1 != 0:
        return False
    _, _, c2 = await run_cmd(
        sandbox_id,
        f"pip install -e {clone_path} -q 2>&1 | tail -2",
        timeout=180,
    )
    return c2 == 0


# ── ScenarioResult ────────────────────────────────────────────────────────────


@dataclass
class ScenarioResult:
    scenario_id: str
    category: str
    name: str
    score: int  # 0-100
    passed: bool
    details: dict = field(default_factory=dict)
    evidence_count: int = 0
    report_length: int = 0
    error: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "category": self.category,
            "name": self.name,
            "score": self.score,
            "passed": self.passed,
            "evidence_count": self.evidence_count,
            "report_length": self.report_length,
            "error": self.error,
            "duration_s": round(self.duration_s, 1),
            "details": self.details,
        }
