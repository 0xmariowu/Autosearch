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
import re
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
    namespace, write back. Subclasses customize path + namespace key, and may
    override `_parse_text` and `_serialize` to support non-strict-JSON formats."""

    name: str = ""
    namespace_key: str = ""  # e.g. "mcpServers" or "context_servers"

    def default_path(self) -> Path:
        raise NotImplementedError

    def _parse_text(self, raw: str) -> dict:
        """Parse the existing config file. Default: strict JSON. Raises on
        anything else."""
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("top-level value is not an object")
        return data

    def _serialize(self, existing: dict, original_text: str | None) -> str:
        """Render the new file body. Default: pretty-printed JSON."""
        return json.dumps(existing, indent=2, ensure_ascii=False) + "\n"

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
        original_text: str | None = None
        backup_path: Path | None = None
        if path.exists():
            try:
                original_text = path.read_text(encoding="utf-8")
                existing = self._parse_text(original_text)
            except (json.JSONDecodeError, ValueError, OSError):
                if dry_run:
                    return WriteResult(
                        client=self.name,
                        path=path,
                        status="backup-and-replaced",
                    )
                backup_path = _backup_corrupt_file(path)
                existing = {}
                original_text = None

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
        path.write_text(self._serialize(existing, original_text), encoding="utf-8")
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
            data = self._parse_text(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            return False, f"{path} is not parseable: {exc}"
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


def _strip_jsonc(text: str) -> str:
    """Strip `// line` and `/* block */` comments + trailing commas before `}` / `]`.

    Naive — does not understand `//` inside string literals — but Zed
    `settings.json` rarely embeds those, and getting it wrong only means we
    fall back to the corrupt-file backup path, never silent data loss.
    """
    text = re.sub(r"(?m)//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _find_top_object_close(text: str) -> int | None:
    """Return the index of the `}` that closes the top-level JSON object, or
    None if the brace structure is broken. Aware of strings + JSONC comments."""
    depth = 0
    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if escape:
            escape = False
            i += 1
            continue
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


class ZedWriter(_BaseWriter):
    """Zed uses JSONC (JSON with // comments and trailing commas).

    The base writer's strict-JSON parser would reject a perfectly normal Zed
    settings file as "corrupt" and back it up — wiping the user's editor
    preferences. This subclass parses JSONC for read, and uses a surgical
    text insert when adding `context_servers` for the first time so existing
    comments and formatting survive untouched.
    """

    name = "zed"
    namespace_key = "context_servers"

    def default_path(self) -> Path:
        return Path.home() / ".config" / "zed" / "settings.json"

    def _parse_text(self, raw: str) -> dict:
        if not raw.strip():
            return {}
        data = json.loads(_strip_jsonc(raw))
        if not isinstance(data, dict):
            raise ValueError("top-level value is not an object")
        return data

    def _serialize(self, existing: dict, original_text: str | None) -> str:
        # Best path: surgical insert preserves comments + user formatting.
        # Triggered only when the original file did NOT already contain a
        # `context_servers` block — otherwise we don't know how to merge into
        # the existing JSONC structure without parsing it, so we re-emit clean
        # JSON (Zed still parses that, just loses comments).
        target_entry = _autosearch_entry(existing[self.namespace_key]["autosearch"]["command"])
        if original_text is not None and '"context_servers"' not in original_text:
            close_idx = _find_top_object_close(original_text)
            if close_idx is not None:
                before = original_text[:close_idx].rstrip()
                # Add a comma if the last non-whitespace char isn't already one
                separator = "" if before.endswith(("{", ",")) else ","
                block = (
                    f"{separator}\n"
                    f'  "context_servers": {{\n'
                    f'    "autosearch": {{\n'
                    f'      "command": {json.dumps(target_entry["command"])},\n'
                    f'      "type": {json.dumps(target_entry["type"])}\n'
                    f"    }}\n"
                    f"  }}\n"
                )
                tail = original_text[close_idx:]
                return before + block + tail
        # Fallback: re-emit as plain JSON (loses any comments).
        return json.dumps(existing, indent=2, ensure_ascii=False) + "\n"


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
