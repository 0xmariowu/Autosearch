# Self-written, plan v2.3 § W2 smoke helpers
import json
import os
import re
import select
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

_RESERVED_FALLBACK_PORTS: set[int] = set()
_UVICORN_URL_RE = re.compile(r"http://127\.0\.0\.1:(\d+)")


def find_free_port() -> int:
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", 0))
                sock.listen(1)
                return int(sock.getsockname()[1])
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.05)

    for candidate in range(38000, 39000):
        if candidate in _RESERVED_FALLBACK_PORTS:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", candidate)) != 0:
                _RESERVED_FALLBACK_PORTS.add(candidate)
                return candidate

    raise AssertionError(f"Unable to allocate a free localhost port: {last_error}")


def wait_until_healthy(url: str, timeout: float = 10.0) -> httpx.Response:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                return response
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.1)

    detail = f" last error: {last_error}" if last_error is not None else ""
    raise AssertionError(f"Timed out waiting for healthy response from {url}.{detail}")


def console_script_command(script_name: str, module_name: str) -> list[str]:
    script_path = shutil.which(script_name)
    if script_path is not None:
        return [script_path]
    return [sys.executable, "-m", module_name]


def smoke_env(
    *,
    home: str | Path | None = None,
    **overrides: str,
) -> dict[str, str]:
    env = os.environ.copy()
    cwd = str(Path.cwd())
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = cwd if not pythonpath else f"{cwd}{os.pathsep}{pythonpath}"
    if home is not None:
        home_value = str(home)
        env["HOME"] = home_value
        env["USERPROFILE"] = home_value
    env.update(overrides)
    if "HOME" in overrides and "USERPROFILE" not in overrides:
        env["USERPROFILE"] = overrides["HOME"]
    return env


def stop_process(process: subprocess.Popen[str], timeout: float = 5.0) -> tuple[str, str]:
    if process.stdin is not None and process.stdin.closed:
        process.stdin = None
    if process.poll() is None:
        process.terminate()
    try:
        return process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.communicate(timeout=timeout)


def read_jsonrpc_message(
    process: subprocess.Popen[str],
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    if process.stdout is None:
        raise AssertionError("Process stdout is not available.")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _, stderr = stop_process(process, timeout=1.0)
            raise AssertionError(
                f"Process exited before sending a JSON-RPC response. stderr:\n{stderr}"
            )

        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([process.stdout], [], [], remaining)
        if not ready:
            continue

        line = process.stdout.readline()
        if not line:
            continue
        return json.loads(line)

    _, stderr = stop_process(process, timeout=1.0)
    raise AssertionError(f"Timed out waiting for JSON-RPC response. stderr:\n{stderr}")


@pytest.fixture(scope="session")
def live_server_base_url() -> str:
    requested_port = _requested_server_port()
    process = _launch_live_server(requested_port)
    try:
        try:
            base_url = _wait_for_server_base_url(process, timeout=10.0)
        except AssertionError:
            if requested_port != 0:
                stop_process(process)
                process = _launch_live_server(0)
                base_url = _wait_for_server_base_url(process, timeout=10.0)
            else:
                raise

        wait_until_healthy(f"{base_url}/health", timeout=10.0)
        yield base_url
    except Exception as exc:
        _, stderr = stop_process(process)
        detail = stderr or str(exc)
        raise AssertionError(f"Live server failed to start. stderr:\n{detail}") from None
    finally:
        stop_process(process)


def _requested_server_port() -> int:
    try:
        return find_free_port()
    except AssertionError:
        return 0


def _launch_live_server(port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            *console_script_command("autosearch", "autosearch.cli.main"),
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
    )


def _wait_for_server_base_url(
    process: subprocess.Popen[str],
    *,
    timeout: float,
) -> str:
    if process.stderr is None:
        raise AssertionError("Live server stderr is not available.")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _, stderr = stop_process(process, timeout=1.0)
            raise AssertionError(f"Live server exited early. stderr:\n{stderr}")

        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([process.stderr], [], [], remaining)
        if not ready:
            continue

        line = process.stderr.readline()
        if not line:
            continue
        match = _UVICORN_URL_RE.search(line)
        if match is not None:
            return f"http://127.0.0.1:{match.group(1)}"
        if "error while attempting to bind" in line.lower():
            raise AssertionError(line.strip())

    _, stderr = stop_process(process, timeout=1.0)
    raise AssertionError(f"Timed out waiting for live server URL. stderr:\n{stderr}")
