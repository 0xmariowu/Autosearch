"""
Static source capability registry and doctor output for AutoSearch.

This layer is intentionally separate from runtime experience:

- capability answers "can this source/provider be used right now?"
- experience answers "should this provider be preferred or cooled down?"
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent
SOURCES_ROOT = REPO_ROOT / "sources"
SOURCE_CATALOG_PATH = SOURCES_ROOT / "catalog.json"
LATEST_CAPABILITY_PATH = SOURCES_ROOT / "latest-capability.json"
GLOBAL_MCP_PATH = Path.home() / ".mcp.json"

STATUS_PRIORITY = {
    "ok": 0,
    "warn": 1,
    "off": 9,
    "error": 9,
}


def _default_capability_report() -> dict[str, Any]:
    return {
        "generated_at": None,
        "sources": {},
        "summary": {
            "ok": 0,
            "warn": 0,
            "off": 0,
            "error": 0,
            "runtime_sources": [],
            "runtime_available": [],
            "runtime_unavailable": [],
        },
    }


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default or {})
    return payload if isinstance(payload, dict) else dict(default or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ensure_source_files() -> None:
    SOURCES_ROOT.mkdir(parents=True, exist_ok=True)
    if not LATEST_CAPABILITY_PATH.exists():
        write_json(LATEST_CAPABILITY_PATH, _default_capability_report())


def load_source_catalog() -> dict[str, Any]:
    return load_json(SOURCE_CATALOG_PATH, {"sources": []})


def load_source_capability_report() -> dict[str, Any]:
    ensure_source_files()
    return load_json(LATEST_CAPABILITY_PATH, _default_capability_report())


def _runtime_provider_names_from_catalog(catalog: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for source in catalog.get("sources", []):
        if source.get("kind") == "provider" and source.get("runtime_enabled"):
            names.append(str(source.get("name") or ""))
    return [name for name in names if name]


def runtime_provider_names() -> list[str]:
    return _runtime_provider_names_from_catalog(load_source_catalog())


def _read_global_mcp_servers() -> dict[str, Any]:
    payload = load_json(GLOBAL_MCP_PATH, {})
    if "mcpServers" in payload and isinstance(payload["mcpServers"], dict):
        return payload["mcpServers"]
    return payload if isinstance(payload, dict) else {}


def _run_command(command: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _status(
    source: dict[str, Any],
    *,
    status: str,
    message: str,
    available: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "available": bool(available),
        "message": message,
        "kind": source.get("kind", "source"),
        "family": source.get("family", ""),
        "tier": int(source.get("tier", 0) or 0),
        "runtime_enabled": bool(source.get("runtime_enabled")),
        "backend": source.get("backend", ""),
        "check": source.get("check", ""),
    }


def _check_github_cli(source: dict[str, Any]) -> dict[str, Any]:
    gh = shutil.which("gh")
    if not gh:
        return _status(source, status="off", message="gh CLI not installed", available=False)
    result = _run_command([gh, "auth", "status"])
    if result is None:
        return _status(source, status="warn", message="gh auth status check failed", available=True)
    if result.returncode == 0:
        return _status(source, status="ok", message="gh CLI authenticated", available=True)
    return _status(source, status="off", message="gh CLI installed but not authenticated", available=False)


def _check_xreach_cli(source: dict[str, Any]) -> dict[str, Any]:
    xreach = shutil.which("xreach")
    if not xreach:
        return _status(source, status="off", message="xreach CLI not installed", available=False)
    result = _run_command([xreach, "auth", "check"], timeout=10)
    if result is None:
        return _status(source, status="warn", message="xreach auth check failed", available=True)
    if result.returncode == 0:
        return _status(source, status="ok", message="xreach authenticated", available=True)
    return _status(source, status="off", message="xreach installed but not authenticated", available=False)


def _check_exa_mcporter(source: dict[str, Any]) -> dict[str, Any]:
    mcporter = shutil.which("mcporter")
    if not mcporter:
        return _status(source, status="off", message="mcporter not installed", available=False)
    version = _run_command([mcporter, "--version"])
    if version is None or version.returncode != 0:
        return _status(source, status="off", message="mcporter not working", available=False)
    config = _run_command([mcporter, "config", "list"])
    config_text = ((config.stdout if config else "") or "") + ((config.stderr if config else "") or "")
    if "exa" in config_text.lower():
        return _status(source, status="ok", message="mcporter Exa connector configured", available=True)
    return _status(source, status="off", message="mcporter installed but Exa connector missing", available=False)


def _check_tavily_api(source: dict[str, Any]) -> dict[str, Any]:
    api_key = str(__import__("os").environ.get("TAVILY_API_KEY", "")).strip()
    if api_key.startswith("tvly-") and len(api_key) > 20:
        return _status(source, status="ok", message="Tavily API key configured", available=True)
    return _status(source, status="off", message="Tavily API key missing", available=False)


def _check_alphaxiv_mcp(source: dict[str, Any]) -> dict[str, Any]:
    servers = _read_global_mcp_servers()
    server = servers.get("alphaxiv")
    if not isinstance(server, dict):
        return _status(source, status="off", message="alphaxiv MCP not configured in ~/.mcp.json", available=False)

    url = str(server.get("url") or "")
    server_type = str(server.get("type") or "")
    if "alphaxiv" not in url or server_type != "sse":
        return _status(source, status="warn", message="alphaxiv MCP config looks incomplete", available=False)

    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=8) as response:
            code = getattr(response, "status", 200)
    except Exception as exc:
        code = getattr(exc, "code", None)
    if code in (200, 401, 405):
        return _status(source, status="ok", message="alphaxiv MCP configured and endpoint reachable", available=True)
    return _status(source, status="warn", message="alphaxiv MCP configured but endpoint check failed", available=False)


def _check_huggingface_public(source: dict[str, Any]) -> dict[str, Any]:
    try:
        request = urllib.request.Request(
            "https://huggingface.co/api/models?limit=1",
            headers={"User-Agent": "autosearch/1.0"},
        )
        with urllib.request.urlopen(request, timeout=8):
            pass
        return _status(source, status="ok", message="Hugging Face public API reachable", available=True)
    except Exception:
        return _status(source, status="warn", message="Hugging Face API check failed", available=False)


def _check_web_reader(source: dict[str, Any]) -> dict[str, Any]:
    return _status(source, status="ok", message="web reader is stateless and available", available=True)


CHECKERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "github_cli": _check_github_cli,
    "xreach_cli": _check_xreach_cli,
    "exa_mcporter": _check_exa_mcporter,
    "tavily_api": _check_tavily_api,
    "alphaxiv_mcp": _check_alphaxiv_mcp,
    "huggingface_public": _check_huggingface_public,
    "web_reader": _check_web_reader,
}


def check_source(source: dict[str, Any]) -> dict[str, Any]:
    checker = CHECKERS.get(str(source.get("check") or ""))
    if not checker:
        return _status(source, status="warn", message="no checker implemented", available=False)
    return checker(source)


def build_source_capability_report(
    catalog: dict[str, Any],
    *,
    selected_names: list[str] | None = None,
    checker: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    names = set(selected_names or [])
    selected_sources: list[dict[str, Any]] = []
    for source in catalog.get("sources", []):
        name = str(source.get("name") or "")
        if not name:
            continue
        if names and name not in names:
            continue
        selected_sources.append(source)

    results: dict[str, Any] = {}
    summary = {
        "ok": 0,
        "warn": 0,
        "off": 0,
        "error": 0,
        "runtime_sources": [],
        "runtime_available": [],
        "runtime_unavailable": [],
    }

    active_checker = checker or check_source
    for source in selected_sources:
        name = str(source.get("name") or "")
        result = active_checker(source)
        results[name] = result
        status = str(result.get("status") or "warn")
        summary[status] = int(summary.get(status, 0)) + 1
        if result.get("runtime_enabled"):
            summary["runtime_sources"].append(name)
            if result.get("available"):
                summary["runtime_available"].append(name)
            else:
                summary["runtime_unavailable"].append(name)

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "sources": results,
        "summary": summary,
    }


def refresh_source_capability(selected_names: list[str] | None = None) -> dict[str, Any]:
    ensure_source_files()
    report = build_source_capability_report(load_source_catalog(), selected_names=selected_names)
    write_json(LATEST_CAPABILITY_PATH, report)
    return report


def get_source_decision(report: dict[str, Any], source_name: str) -> dict[str, Any]:
    source = ((report.get("sources") or {}).get(source_name) or {})
    status = str(source.get("status") or "ok")
    available = bool(source.get("available", True))
    runtime_enabled = bool(source.get("runtime_enabled", True))
    should_skip = (not runtime_enabled) or (not available)
    return {
        "name": source_name,
        "status": status,
        "available": available,
        "runtime_enabled": runtime_enabled,
        "should_skip": should_skip,
        "priority": STATUS_PRIORITY.get(status, 5),
        "message": str(source.get("message") or ""),
    }


def format_source_capability_report(report: dict[str, Any]) -> str:
    lines = ["AutoSearch Source Capability", "=" * 32, ""]
    sources = report.get("sources") or {}
    for name in sorted(sources.keys()):
        entry = sources[name]
        status = str(entry.get("status") or "warn").upper()
        runtime = "runtime" if entry.get("runtime_enabled") else "optional"
        lines.append(f"[{status}] {name} ({runtime}) — {entry.get('message', '')}")
    summary = report.get("summary") or {}
    lines.append("")
    lines.append(
        "Summary: "
        f"ok={summary.get('ok', 0)} "
        f"warn={summary.get('warn', 0)} "
        f"off={summary.get('off', 0)} "
        f"error={summary.get('error', 0)}"
    )
    runtime_unavailable = summary.get("runtime_unavailable") or []
    if runtime_unavailable:
        lines.append("Unavailable runtime providers: " + ", ".join(runtime_unavailable))
    return "\n".join(lines)
