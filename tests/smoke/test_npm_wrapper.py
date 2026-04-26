import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
NPM_DIR = ROOT / "npm"
PACKAGE_JSON = NPM_DIR / "package.json"
WRAPPER_BIN = "./bin/autosearch-ai.js"
AUTO_INSTALL_SCRIPTS = {"preinstall", "install", "postinstall"}


def read_package_json() -> dict:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def test_npm_package_has_no_install_lifecycle_scripts() -> None:
    package = read_package_json()

    scripts = package.get("scripts") or {}
    assert isinstance(scripts, dict)
    assert AUTO_INSTALL_SCRIPTS.isdisjoint(scripts)


def test_npm_bin_points_at_wrapper_script() -> None:
    package = read_package_json()

    assert package["bin"]["autosearch-ai"] == WRAPPER_BIN
    assert (NPM_DIR / WRAPPER_BIN).resolve().is_file()


def test_npm_pack_dry_run_has_no_install_lifecycle_scripts(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["npm_config_cache"] = str(tmp_path / "npm-cache")

    result = subprocess.run(
        [
            "npm",
            "pack",
            "--dry-run",
            "--json",
            "--prefix",
            "npm",
            "./npm",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output

    pack_output = json.loads(result.stdout)
    assert len(pack_output) == 1

    package = read_package_json()
    scripts = package.get("scripts") or {}
    assert AUTO_INSTALL_SCRIPTS.isdisjoint(scripts)

    packed_files = {entry["path"] for entry in pack_output[0]["files"]}
    assert "package.json" in packed_files
    assert "bin/autosearch-ai.js" in packed_files


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only fake autosearch shim")
def test_spawn_enoent_returns_nonzero(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_autosearch = fake_bin / "autosearch"
    fake_autosearch.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f'  rm -f "{fake_autosearch}"\n'
        '  echo "2026.4.24.1"\n'
        "  exit 0\n"
        "fi\n"
        'echo "unexpected autosearch invocation" >&2\n'
        "exit 2\n",
        encoding="utf-8",
    )
    fake_autosearch.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"])

    result = subprocess.run(
        [
            shutil.which("node") or "node",
            str(NPM_DIR / "bin" / "autosearch-ai.js"),
            "doctor",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "autosearch not found" in result.stderr.lower()
    assert "path" in result.stderr.lower()


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only fake bash installer shim")
def test_path_after_install_finds_binary(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_bash = fake_bin / "bash"
    fake_bash.write_text(
        "#!/bin/sh\n"
        'mkdir -p "$HOME/.local/bin"\n'
        "cat > \"$HOME/.local/bin/autosearch\" <<'EOF'\n"
        "#!/bin/sh\n"
        'echo "installed autosearch $*"\n'
        "exit 0\n"
        "EOF\n"
        'chmod +x "$HOME/.local/bin/autosearch"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"])

    result = subprocess.run(
        [
            shutil.which("node") or "node",
            str(NPM_DIR / "bin" / "autosearch-ai.js"),
            "--yes",
            "doctor",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert "installed autosearch doctor" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only fake bash installer shim")
def test_install_passes_no_init(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    install_argv = tmp_path / "install-argv.txt"
    fake_bash = fake_bin / "bash"
    fake_bash.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" > "{install_argv}"\n'
        'mkdir -p "$HOME/.local/bin"\n'
        "cat > \"$HOME/.local/bin/autosearch\" <<'EOF'\n"
        "#!/bin/sh\n"
        "exit 0\n"
        "EOF\n"
        'chmod +x "$HOME/.local/bin/autosearch"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"])

    result = subprocess.run(
        [
            shutil.which("node") or "node",
            str(NPM_DIR / "bin" / "autosearch-ai.js"),
            "--yes",
            "doctor",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert "--no-init" in install_argv.read_text(encoding="utf-8")
