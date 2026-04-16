from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from harness.base import AdapterConfig

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_ROOT = ROOT / "adapters"

REPO_RE = re.compile(r'REPO\s*=\s*["\']([^"\']+)["\']')
PLATFORM_RE = re.compile(r'PLATFORM\s*=\s*["\']([^"\']+)["\']')


@dataclass(frozen=True)
class AdapterMetadata:
    name: str
    config: AdapterConfig


def _parse_run_py(run_py: Path) -> tuple[str, str]:
    text = run_py.read_text(encoding="utf-8")
    repo_match = REPO_RE.search(text)
    platform_match = PLATFORM_RE.search(text)
    repo = repo_match.group(1) if repo_match else ""
    platform = (
        platform_match.group(1) if platform_match else run_py.parent.name.split("__")[0]
    )
    return platform, repo


def _auto_discover() -> dict[str, AdapterMetadata]:
    registry: dict[str, AdapterMetadata] = {}
    for adapter_dir in sorted(ADAPTERS_ROOT.iterdir()):
        if not adapter_dir.is_dir():
            continue
        setup = adapter_dir / "setup.sh"
        run_py = adapter_dir / "run.py"
        if not setup.exists() or not run_py.exists():
            continue
        path_id = adapter_dir.name
        platform, repo = _parse_run_py(run_py)
        registry[path_id] = AdapterMetadata(
            name=path_id,
            config=AdapterConfig(
                platform=platform,
                path_id=path_id,
                repo=repo,
                setup_script=setup,
                run_script=run_py,
            ),
        )
    return registry


REGISTRY = _auto_discover()


def list_adapters() -> list[AdapterConfig]:
    return [metadata.config for metadata in REGISTRY.values()]


def get_adapter(path_id: str) -> AdapterConfig:
    return REGISTRY[path_id].config
