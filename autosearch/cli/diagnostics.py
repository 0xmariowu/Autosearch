"""Generate a redacted diagnostics bundle for support / bug reports.

Goal: turn "it doesn't work" into one copy-paste payload that surfaces enough
state for triage (versions, paths, tool registration, channel readiness)
WITHOUT leaking any secret value, cookie, full user query, or other PII.

Two design rules:
  1. Never include a secret VALUE — only key names (and even those only when
     present in env, not their raw values).
  2. Strip anything that looks like an API key / Bearer token / Cookie before
     emitting, even from accidental sources (e.g. environment variable dumps).
"""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from autosearch.core.redact import redact

# Re-export for backwards compatibility — the canonical home is core.redact.
__all__ = ["build_bundle", "render_bundle", "redact", "DiagnosticsBundle"]


@dataclass
class DiagnosticsBundle:
    autosearch_version: str
    python_version: str
    python_executable: str
    platform_string: str
    install_method: str
    mcp_config_paths: dict[str, str] = field(default_factory=dict)
    secrets_file: dict[str, object] = field(default_factory=dict)
    runtime_experience_dir: dict[str, object] = field(default_factory=dict)
    mcp_tool_count: int | None = None
    mcp_required_missing: list[str] = field(default_factory=list)
    doctor_summary: dict[str, int] = field(default_factory=dict)


def _detect_install_method() -> str:
    exe = sys.executable
    if "pipx" in exe:
        return "pipx"
    if ".venv" in exe or "virtualenv" in exe.lower():
        return "venv"
    if "uv" in exe:
        return "uv"
    return "system"


def _mcp_config_paths_status() -> dict[str, str]:
    candidates = {
        "claude": Path.home() / ".claude" / "mcp.json",
        "cursor": Path.home() / ".cursor" / "mcp.json",
        "zed": Path.home() / ".config" / "zed" / "settings.json",
    }
    out: dict[str, str] = {}
    for name, path in candidates.items():
        if path.is_file():
            try:
                size = path.stat().st_size
                out[name] = f"present ({size}B at {path})"
            except OSError:
                out[name] = f"present but unreadable ({path})"
        elif path.parent.is_dir():
            out[name] = f"client dir exists, no config at {path}"
        else:
            out[name] = "not installed"
    return out


def _secrets_file_status() -> dict[str, object]:
    from autosearch.core.secrets_store import load_secrets, secrets_path

    path = secrets_path()
    info: dict[str, object] = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        try:
            mode = path.stat().st_mode & 0o777
            info["permissions_octal"] = f"0o{mode:o}"
            keys = list(load_secrets().keys())
            info["key_count"] = len(keys)
            # Only key NAMES, never values.
            info["key_names"] = sorted(keys)
        except OSError:
            info["error"] = "stat or read failed"
    return info


def _runtime_experience_dir_status() -> dict[str, object]:
    from autosearch.skills.experience import _runtime_root

    root = _runtime_root()
    info: dict[str, object] = {"path": str(root), "exists": root.is_dir()}
    if root.is_dir():
        try:
            channels = (
                [d.name for d in (root / "channels").iterdir() if d.is_dir()]
                if (root / "channels").is_dir()
                else []
            )
            info["channel_count_with_state"] = len(channels)
            total_size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
            info["total_bytes"] = total_size
        except OSError:
            info["error"] = "could not enumerate"
    return info


def _mcp_surface() -> tuple[int | None, list[str]]:
    """Try to inspect the MCP server's tool registry. Returns (count, missing).
    On any error, returns (None, []) — never raises."""
    try:
        import asyncio  # noqa: PLC0415

        from autosearch.cli.main import _REQUIRED_MCP_TOOLS  # noqa: PLC0415
        from autosearch.mcp.server import create_server  # noqa: PLC0415

        server = create_server()
        tools = asyncio.run(server.list_tools())
        names = {t.name for t in tools}
        missing = [name for name in _REQUIRED_MCP_TOOLS if name not in names]
        return len(names), missing
    except Exception:
        return None, []


def _doctor_summary() -> dict[str, int]:
    try:
        from autosearch.core.doctor import scan_channels  # noqa: PLC0415

        results = scan_channels()
        summary = {"total": len(results), "ok": 0, "warn": 0, "off": 0}
        for r in results:
            summary[r.status] = summary.get(r.status, 0) + 1
        return summary
    except Exception:
        return {}


def build_bundle() -> DiagnosticsBundle:
    """Collect everything needed for a support bundle. Caller is responsible
    for redacting before printing."""
    from autosearch import __version__  # noqa: PLC0415

    tool_count, missing = _mcp_surface()
    return DiagnosticsBundle(
        autosearch_version=__version__,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        python_executable=sys.executable,
        platform_string=platform.platform(),
        install_method=_detect_install_method(),
        mcp_config_paths=_mcp_config_paths_status(),
        secrets_file=_secrets_file_status(),
        runtime_experience_dir=_runtime_experience_dir_status(),
        mcp_tool_count=tool_count,
        mcp_required_missing=missing,
        doctor_summary=_doctor_summary(),
    )


def render_bundle(bundle: DiagnosticsBundle, *, redact_output: bool) -> str:
    import json  # noqa: PLC0415

    text = json.dumps(asdict(bundle), indent=2, ensure_ascii=False, sort_keys=True)
    if redact_output:
        text = redact(text)
    return text


# Re-export so `which autosearch-mcp` is easy to spot in the bundle.
def autosearch_mcp_on_path() -> str | None:
    return shutil.which("autosearch-mcp")
