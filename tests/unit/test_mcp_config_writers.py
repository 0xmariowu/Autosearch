"""Tests for autosearch.cli.mcp_config_writers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from autosearch.cli import main as cli_main
from autosearch.cli.mcp_config_writers import (
    MCPConfigWriteError,
    WRITERS,
    ClaudeCodeWriter,
    CursorWriter,
    ZedWriter,
    write_for_clients,
)


@pytest.fixture(autouse=True)
def no_claude_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("autosearch.cli.mcp_config_writers.shutil.which", lambda command: None)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_claude_writer_calls_claude_mcp_add_when_cli_is_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(
        "autosearch.cli.mcp_config_writers.shutil.which",
        lambda command: "/usr/bin/claude" if command == "claude" else None,
    )
    monkeypatch.setattr("autosearch.cli.mcp_config_writers.subprocess.run", fake_run)

    result = ClaudeCodeWriter().write()

    assert result.status == "written"
    assert calls == [
        ["claude", "mcp", "add", "--transport", "stdio", "autosearch", "--", "autosearch-mcp"]
    ]


def test_claude_writer_writes_project_mcp_json_without_cli_when_project_scope(
    tmp_path: Path,
) -> None:
    """Regression: previous writer dumped {'autosearch': ...} at root, which
    Claude Code silently ignored. Schema must be `mcpServers.<name>`."""
    target = tmp_path / ".mcp.json"

    result = ClaudeCodeWriter().write(path_override=target, scope="project")
    assert result.status == "written"

    data = _read(target)
    assert "mcpServers" in data, "Claude Code expects mcpServers namespace"
    assert data["mcpServers"]["autosearch"] == {
        "command": "autosearch-mcp",
        "type": "stdio",
    }


def test_claude_writer_errors_without_cli_and_without_explicit_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()

    with pytest.raises(MCPConfigWriteError, match="stale ~/.claude/mcp.json"):
        ClaudeCodeWriter().write()

    assert not (tmp_path / ".claude" / "mcp.json").exists()


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
    target = tmp_path / ".mcp.json"
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

    ClaudeCodeWriter().write(path_override=target, scope="project")

    data = _read(target)
    assert data["userSetting"] == "do-not-touch"
    assert data["mcpServers"]["other-server"] == {"command": "other", "type": "stdio"}
    assert data["mcpServers"]["autosearch"]["command"] == "autosearch-mcp"


def test_writer_already_set_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / ".mcp.json"
    writer = ClaudeCodeWriter()

    first = writer.write(path_override=target, scope="project")
    second = writer.write(path_override=target, scope="project")

    assert first.status == "written"
    assert second.status == "already-set"


def test_writer_skipped_when_parent_dir_missing(tmp_path: Path) -> None:
    target = tmp_path / "absent_client_dir" / "mcp.json"
    # parent never created
    result = ClaudeCodeWriter().write(path_override=target, scope="project")
    assert result.status == "skipped"
    assert not target.exists()


def test_writer_backs_up_corrupt_json_and_rewrites(tmp_path: Path) -> None:
    """Million-user safety: never silently overwrite a user's config. If the
    file is unparseable, move it to <name>.bak.<ts> first."""
    target = tmp_path / ".mcp.json"
    target.write_text("{this is not json", encoding="utf-8")

    result = ClaudeCodeWriter().write(path_override=target, scope="project")
    assert result.status == "backup-and-replaced"
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.read_text(encoding="utf-8") == "{this is not json"

    data = _read(target)
    assert data["mcpServers"]["autosearch"]["command"] == "autosearch-mcp"


def test_dry_run_does_not_modify_anything(tmp_path: Path) -> None:
    target = tmp_path / ".mcp.json"

    result = ClaudeCodeWriter().write(path_override=target, dry_run=True, scope="project")
    assert result.status == "written"
    assert not target.exists(), "dry-run must not touch the filesystem"


def test_dry_run_reports_backup_for_corrupt_file_without_renaming(tmp_path: Path) -> None:
    target = tmp_path / ".mcp.json"
    target.write_text("garbage", encoding="utf-8")

    result = ClaudeCodeWriter().write(path_override=target, dry_run=True, scope="project")
    assert result.status == "backup-and-replaced"
    # original still in place, no backup created
    assert target.read_text(encoding="utf-8") == "garbage"


def test_verify_returns_false_when_entry_missing(tmp_path: Path) -> None:
    target = tmp_path / ".mcp.json"
    target.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    ok, msg = ClaudeCodeWriter().verify(path_override=target)
    assert ok is False
    assert "no `mcpServers.autosearch` entry" in msg


def test_verify_detects_wrong_namespace(tmp_path: Path) -> None:
    """The exact bug the old writer caused: entry at root, no `mcpServers`
    namespace. verify() should catch it."""
    target = tmp_path / ".mcp.json"
    target.write_text(
        json.dumps({"autosearch": {"command": "autosearch-mcp"}}),
        encoding="utf-8",
    )
    ok, msg = ClaudeCodeWriter().verify(path_override=target)
    assert ok is False
    assert "mcpServers" in msg


def test_verify_passes_after_writer_runs(tmp_path: Path) -> None:
    target = tmp_path / ".mcp.json"
    writer = ClaudeCodeWriter()
    writer.write(path_override=target, scope="project")

    ok, msg = writer.verify(path_override=target)
    assert ok is True
    assert "autosearch-mcp" in msg


def test_write_for_clients_runs_each_known_writer(tmp_path: Path, monkeypatch) -> None:
    """The orchestrator hits every registered client (skipping those whose
    config dir doesn't exist) without crashing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".cursor").mkdir()
    # zed dir intentionally missing

    results = write_for_clients(scope="project")
    by_client = {r.client: r for r in results}
    assert by_client["claude"].status == "written"
    assert by_client["cursor"].status == "written"
    assert by_client["zed"].status == "skipped"


def test_writers_registry_lists_three_clients() -> None:
    assert set(WRITERS) == {"claude", "cursor", "zed"}


def test_mcp_check_reports_configured_when_claude_cli_lists_autosearch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert command == ["claude", "mcp", "list", "--json"]
        assert kwargs["check"] is True
        return SimpleNamespace(
            stdout=json.dumps(
                {"mcpServers": {"autosearch": {"command": "autosearch-mcp", "type": "stdio"}}}
            )
        )

    monkeypatch.setattr(
        "autosearch.cli.mcp_config_writers.shutil.which",
        lambda command: "/usr/bin/claude" if command == "claude" else None,
    )
    monkeypatch.setattr("autosearch.cli.mcp_config_writers.subprocess.run", fake_run)

    result = runner.invoke(cli_main.app, ["mcp-check", "--client", "claude"])

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "Client config check (claude)" in result.stdout
    assert "autosearch -> autosearch-mcp" in result.stdout


def test_mcp_check_ignores_legacy_claude_mcp_json_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / ".claude" / "mcp.json"
    legacy.parent.mkdir()
    legacy.write_text(
        json.dumps({"mcpServers": {"autosearch": {"command": "autosearch-mcp"}}}),
        encoding="utf-8",
    )

    result = runner.invoke(cli_main.app, ["mcp-check", "--client", "claude"])

    assert result.exit_code != 0
    output = result.stdout + (result.stderr or "")
    assert "Claude Code MCP not configured" in output


# ── Zed JSONC handling ──────────────────────────────────────────────────────


def test_zed_writer_does_not_treat_jsonc_settings_as_corrupt(tmp_path: Path) -> None:
    """Regression: Zed ships `settings.json` as JSONC (// comments + trailing
    commas). The original writer parsed it as strict JSON, called it corrupt,
    backed it up, and wrote a fresh file — nuking the user's font/theme
    settings. The Zed-specific writer must treat this file as parseable."""
    target = tmp_path / "zed" / "settings.json"
    target.parent.mkdir()
    target.write_text(
        """// Zed settings — preamble comment

{
  "ui_font_size": 16,
  "buffer_font_size": 15,
  "theme": {
    "mode": "system",
    "light": "One Light",
    "dark": "One Dark",
  },
}
""",
        encoding="utf-8",
    )

    result = ZedWriter().write(path_override=target)
    assert result.status == "written", "JSONC must be accepted, not backed up as corrupt"
    assert result.backup_path is None, "no backup file should be created for valid JSONC"

    new_text = target.read_text(encoding="utf-8")
    # User's existing settings + comments must survive
    assert "ui_font_size" in new_text
    assert "buffer_font_size" in new_text
    assert "Zed settings — preamble comment" in new_text, "comments must be preserved"
    # And the new context_servers block must be present
    assert '"context_servers"' in new_text
    assert '"autosearch"' in new_text
    assert '"autosearch-mcp"' in new_text


def test_zed_writer_falls_back_to_plain_json_when_context_servers_already_present(
    tmp_path: Path,
) -> None:
    """If the file already has a `context_servers` block we don't try to
    surgically merge into it — re-emit as plain JSON. Comments are lost in
    this case but data is preserved (Zed still reads JSON fine)."""
    target = tmp_path / "zed" / "settings.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps(
            {
                "ui_font_size": 16,
                "context_servers": {"other-server": {"command": "x", "type": "stdio"}},
            }
        ),
        encoding="utf-8",
    )

    result = ZedWriter().write(path_override=target)
    assert result.status == "written"
    data = json.loads(target.read_text(encoding="utf-8"))
    # Both servers preserved, autosearch added
    assert data["context_servers"]["other-server"]["command"] == "x"
    assert data["context_servers"]["autosearch"]["command"] == "autosearch-mcp"
    assert data["ui_font_size"] == 16


def test_zed_writer_idempotent_on_jsonc_file(tmp_path: Path) -> None:
    target = tmp_path / "zed" / "settings.json"
    target.parent.mkdir()
    target.write_text(
        '{ "ui_font_size": 16, } // trailing comma + comment',
        encoding="utf-8",
    )
    writer = ZedWriter()
    writer.write(path_override=target)
    second = writer.write(path_override=target)
    assert second.status == "already-set"
