import json
import os
import subprocess
from pathlib import Path


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
