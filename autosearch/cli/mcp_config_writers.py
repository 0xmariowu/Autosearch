"""Per-client MCP config writers.

`autosearch init` used to dump `{"autosearch": {...}}` at the root of every MCP
config file. Claude Code, Cursor, and Zed each expect a different shape (see
`docs/mcp-clients.md`), so the old writer silently produced configs that the
clients couldn't actually load — `init` would say "MCP server: ready" while the
host agent saw nothing.

This module ships one writer per supported client. Each writer:
- knows the canonical config path for that client
- knows the schema (e.g. Claude Code uses `mcpServers.<name>`, Zed uses
  `context_servers.<name>`)
- merges the autosearch entry into existing config without dropping unrelated
  keys
- backs up corrupt JSON to `<path>.bak.<timestamp>` instead of overwriting it
- can verify whether autosearch is already correctly registered

Adding a new client = one new subclass + one entry in `WRITERS`.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

WriteStatus = Literal[
    "written",  # newly added entry
    "already-set",  # entry already correct, no-op
    "skipped",  # parent dir doesn't exist (client not installed)
    "backup-and-replaced",  # existing file was unparseable, backed up + rewritten
]


@dataclass(slots=True)
class WriteResult:
    client: str
    path: Path
    status: WriteStatus
    backup_path: Path | None = None


def _autosearch_entry(server_command: str) -> dict[str, object]:
    """The autosearch MCP entry — same shape across `mcpServers`/`context_servers`."""
    return {"command": server_command, "type": "stdio"}


def _backup_corrupt_file(path: Path) -> Path:
    """Move an unparseable JSON file to <path>.bak.<unix-ts> and return new path."""
    suffix = f".bak.{int(time.time())}"
    backup = path.with_suffix(path.suffix + suffix)
    path.rename(backup)
    return backup


class _BaseWriter:
    """Shared logic: load existing config, place autosearch under the right
    namespace, write back. Subclasses customize path + namespace key."""

    name: str = ""
    namespace_key: str = ""  # e.g. "mcpServers" or "context_servers"

    def default_path(self) -> Path:
        raise NotImplementedError

    def write(
        self,
        *,
        server_command: str = "autosearch-mcp",
        dry_run: bool = False,
        path_override: Path | None = None,
    ) -> WriteResult:
        path = path_override or self.default_path()
        if not path.parent.exists():
            return WriteResult(client=self.name, path=path, status="skipped")

        existing: dict[str, object] = {}
        backup_path: Path | None = None
        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8").strip()
                existing = json.loads(raw) if raw else {}
                if not isinstance(existing, dict):
                    raise ValueError("top-level value is not an object")
            except (json.JSONDecodeError, ValueError, OSError):
                if dry_run:
                    return WriteResult(
                        client=self.name,
                        path=path,
                        status="backup-and-replaced",
                    )
                backup_path = _backup_corrupt_file(path)
                existing = {}

        servers = existing.setdefault(self.namespace_key, {})
        if not isinstance(servers, dict):
            servers = {}
            existing[self.namespace_key] = servers

        target_entry = _autosearch_entry(server_command)
        if servers.get("autosearch") == target_entry:
            return WriteResult(
                client=self.name,
                path=path,
                status="already-set",
                backup_path=backup_path,
            )

        if dry_run:
            status: WriteStatus = "backup-and-replaced" if backup_path else "written"
            return WriteResult(client=self.name, path=path, status=status, backup_path=backup_path)

        servers["autosearch"] = target_entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return WriteResult(
            client=self.name,
            path=path,
            status="backup-and-replaced" if backup_path else "written",
            backup_path=backup_path,
        )

    def verify(
        self,
        *,
        server_command: str = "autosearch-mcp",
        path_override: Path | None = None,
    ) -> tuple[bool, str]:
        """Return (ok, message). ok=True when this client's config has a properly
        shaped autosearch entry under `namespace_key`."""
        path = path_override or self.default_path()
        if not path.exists():
            return False, f"{path} does not exist"
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            return False, f"{path} is not valid JSON: {exc}"
        if not isinstance(data, dict):
            return False, f"{path} top-level is not an object"

        servers = data.get(self.namespace_key)
        if not isinstance(servers, dict):
            return False, f"{path} missing `{self.namespace_key}` object"
        entry = servers.get("autosearch")
        if not isinstance(entry, dict):
            return False, f"{path} has no `{self.namespace_key}.autosearch` entry"
        if entry.get("command") != server_command:
            return False, (
                f"{path} `{self.namespace_key}.autosearch.command` is "
                f"{entry.get('command')!r}, expected {server_command!r}"
            )
        return True, f"{path}: {self.namespace_key}.autosearch -> {entry.get('command')}"


class ClaudeCodeWriter(_BaseWriter):
    name = "claude"
    namespace_key = "mcpServers"

    def default_path(self) -> Path:
        return Path.home() / ".claude" / "mcp.json"


class CursorWriter(_BaseWriter):
    name = "cursor"
    namespace_key = "mcpServers"

    def default_path(self) -> Path:
        return Path.home() / ".cursor" / "mcp.json"


class ZedWriter(_BaseWriter):
    name = "zed"
    namespace_key = "context_servers"

    def default_path(self) -> Path:
        return Path.home() / ".config" / "zed" / "settings.json"


WRITERS: dict[str, _BaseWriter] = {
    "claude": ClaudeCodeWriter(),
    "cursor": CursorWriter(),
    "zed": ZedWriter(),
}


def write_for_clients(
    clients: list[str] | None = None,
    *,
    server_command: str = "autosearch-mcp",
    dry_run: bool = False,
) -> list[WriteResult]:
    """Run the writer for each named client (or all known clients if None)."""
    targets = clients if clients else list(WRITERS.keys())
    results: list[WriteResult] = []
    for client_name in targets:
        writer = WRITERS.get(client_name)
        if writer is None:
            continue
        results.append(writer.write(server_command=server_command, dry_run=dry_run))
    return results
