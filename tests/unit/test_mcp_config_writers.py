"""Tests for autosearch.cli.mcp_config_writers."""

from __future__ import annotations

import json
from pathlib import Path

from autosearch.cli.mcp_config_writers import (
    WRITERS,
    ClaudeCodeWriter,
    CursorWriter,
    ZedWriter,
    write_for_clients,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_claude_writer_uses_mcpServers_namespace(tmp_path: Path) -> None:
    """Regression: previous writer dumped {'autosearch': ...} at root, which
    Claude Code silently ignored. Schema must be `mcpServers.<name>`."""
    target = tmp_path / "claude_dir" / "mcp.json"
    target.parent.mkdir()

    result = ClaudeCodeWriter().write(path_override=target)
    assert result.status == "written"

    data = _read(target)
    assert "mcpServers" in data, "Claude Code expects mcpServers namespace"
    assert data["mcpServers"]["autosearch"] == {
        "command": "autosearch-mcp",
        "type": "stdio",
    }


def test_cursor_writer_also_uses_mcpServers_namespace(tmp_path: Path) -> None:
    target = tmp_path / "cursor_dir" / "mcp.json"
    target.parent.mkdir()
    CursorWriter().write(path_override=target)
    assert "mcpServers" in _read(target)


def test_zed_writer_uses_context_servers_namespace(tmp_path: Path) -> None:
    """Zed has its own schema — `context_servers`, not `mcpServers`."""
    target = tmp_path / "zed_dir" / "settings.json"
    target.parent.mkdir()

    result = ZedWriter().write(path_override=target)
    assert result.status == "written"

    data = _read(target)
    assert "context_servers" in data
    assert "mcpServers" not in data
    assert data["context_servers"]["autosearch"]["command"] == "autosearch-mcp"


def test_writer_preserves_unrelated_keys(tmp_path: Path) -> None:
    """Critical: real configs contain other servers / settings the user owns.
    Our write must merge, never clobber."""
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "other-server": {"command": "other", "type": "stdio"},
                },
                "userSetting": "do-not-touch",
            }
        ),
        encoding="utf-8",
    )

    ClaudeCodeWriter().write(path_override=target)

    data = _read(target)
    assert data["userSetting"] == "do-not-touch"
    assert data["mcpServers"]["other-server"] == {"command": "other", "type": "stdio"}
    assert data["mcpServers"]["autosearch"]["command"] == "autosearch-mcp"


def test_writer_already_set_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    writer = ClaudeCodeWriter()

    first = writer.write(path_override=target)
    second = writer.write(path_override=target)

    assert first.status == "written"
    assert second.status == "already-set"


def test_writer_skipped_when_parent_dir_missing(tmp_path: Path) -> None:
    target = tmp_path / "absent_client_dir" / "mcp.json"
    # parent never created
    result = ClaudeCodeWriter().write(path_override=target)
    assert result.status == "skipped"
    assert not target.exists()


def test_writer_backs_up_corrupt_json_and_rewrites(tmp_path: Path) -> None:
    """Million-user safety: never silently overwrite a user's config. If the
    file is unparseable, move it to <name>.bak.<ts> first."""
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    target.write_text("{this is not json", encoding="utf-8")

    result = ClaudeCodeWriter().write(path_override=target)
    assert result.status == "backup-and-replaced"
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.read_text(encoding="utf-8") == "{this is not json"

    data = _read(target)
    assert data["mcpServers"]["autosearch"]["command"] == "autosearch-mcp"


def test_dry_run_does_not_modify_anything(tmp_path: Path) -> None:
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()

    result = ClaudeCodeWriter().write(path_override=target, dry_run=True)
    assert result.status == "written"
    assert not target.exists(), "dry-run must not touch the filesystem"


def test_dry_run_reports_backup_for_corrupt_file_without_renaming(tmp_path: Path) -> None:
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    target.write_text("garbage", encoding="utf-8")

    result = ClaudeCodeWriter().write(path_override=target, dry_run=True)
    assert result.status == "backup-and-replaced"
    # original still in place, no backup created
    assert target.read_text(encoding="utf-8") == "garbage"


def test_verify_returns_false_when_entry_missing(tmp_path: Path) -> None:
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    ok, msg = ClaudeCodeWriter().verify(path_override=target)
    assert ok is False
    assert "no `mcpServers.autosearch` entry" in msg


def test_verify_detects_wrong_namespace(tmp_path: Path) -> None:
    """The exact bug the old writer caused: entry at root, no `mcpServers`
    namespace. verify() should catch it."""
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps({"autosearch": {"command": "autosearch-mcp"}}),
        encoding="utf-8",
    )
    ok, msg = ClaudeCodeWriter().verify(path_override=target)
    assert ok is False
    assert "mcpServers" in msg


def test_verify_passes_after_writer_runs(tmp_path: Path) -> None:
    target = tmp_path / "claude" / "mcp.json"
    target.parent.mkdir()
    writer = ClaudeCodeWriter()
    writer.write(path_override=target)

    ok, msg = writer.verify(path_override=target)
    assert ok is True
    assert "autosearch-mcp" in msg


def test_write_for_clients_runs_each_known_writer(tmp_path: Path, monkeypatch) -> None:
    """The orchestrator hits every registered client (skipping those whose
    config dir doesn't exist) without crashing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    # zed dir intentionally missing

    results = write_for_clients()
    by_client = {r.client: r for r in results}
    assert by_client["claude"].status == "written"
    assert by_client["cursor"].status == "written"
    assert by_client["zed"].status == "skipped"


def test_writers_registry_lists_three_clients() -> None:
    assert set(WRITERS) == {"claude", "cursor", "zed"}
