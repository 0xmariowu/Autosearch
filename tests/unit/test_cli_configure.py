"""Plan §P1-3: `autosearch configure` must not require the secret value on the
command line by default. Hidden prompt is the safe default; `--stdin` covers
automation; `--replace` is needed to overwrite existing keys."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from autosearch.cli import main as cli_main

runner = CliRunner()


def _read_secrets(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            out[k.strip()] = v.strip()
    return out


def test_configure_accepts_value_from_stdin(tmp_path, monkeypatch):
    """The automation path: piping a value in via stdin must work and must not
    require any TTY."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        cli_main.app,
        ["configure", "OPENAI_API_KEY", "--stdin"],
        input="sk-from-stdin-test-value\n",
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    secrets = _read_secrets(tmp_path / ".config" / "ai-secrets.env")
    assert secrets["OPENAI_API_KEY"] == "sk-from-stdin-test-value"


def test_configure_keeps_existing_key_without_replace(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    secrets_dir = tmp_path / ".config"
    secrets_dir.mkdir()
    (secrets_dir / "ai-secrets.env").write_text("OPENAI_API_KEY=existing-value\n", encoding="utf-8")

    result = runner.invoke(
        cli_main.app,
        ["configure", "OPENAI_API_KEY", "--stdin"],
        input="new-value-must-be-ignored\n",
    )
    assert result.exit_code == 0
    secrets = _read_secrets(secrets_dir / "ai-secrets.env")
    assert secrets["OPENAI_API_KEY"] == "existing-value"


def test_configure_replace_flag_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    secrets_dir = tmp_path / ".config"
    secrets_dir.mkdir()
    (secrets_dir / "ai-secrets.env").write_text(
        "OPENAI_API_KEY=old\nOTHER_KEY=stay\n", encoding="utf-8"
    )

    result = runner.invoke(
        cli_main.app,
        ["configure", "OPENAI_API_KEY", "--stdin", "--replace"],
        input="brand-new-value\n",
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    secrets = _read_secrets(secrets_dir / "ai-secrets.env")
    assert secrets["OPENAI_API_KEY"] == "brand-new-value"
    # Unrelated keys preserved
    assert secrets["OTHER_KEY"] == "stay"


def test_configure_rejects_empty_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(cli_main.app, ["configure", "OPENAI_API_KEY", "--stdin"], input="")
    assert result.exit_code != 0
    assert "empty" in (result.stdout + (result.stderr or "")).lower()


def test_configure_sets_0600_permissions(tmp_path, monkeypatch):
    """Per plan §P1-3: secrets file mode must be 0600 so other users on a
    shared host can't read it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    runner.invoke(
        cli_main.app,
        ["configure", "OPENAI_API_KEY", "--stdin"],
        input="sk-perm-test-12345\n",
    )
    mode = (tmp_path / ".config" / "ai-secrets.env").stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600 perms, got 0o{mode:o}"


def test_configure_with_inline_value_still_works_for_backwards_compat(tmp_path, monkeypatch):
    """The old `configure KEY VALUE` form must keep working for existing
    install scripts and docs — but is no longer the recommended path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        cli_main.app,
        ["configure", "OPENAI_API_KEY", "inline-value-here"],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    secrets = _read_secrets(tmp_path / ".config" / "ai-secrets.env")
    assert secrets["OPENAI_API_KEY"] == "inline-value-here"
