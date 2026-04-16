from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.base import AdapterConfig

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_ROOT = ROOT / "adapters"


@dataclass(frozen=True)
class AdapterMetadata:
    name: str
    config: AdapterConfig


def _adapter_dir(name: str) -> Path:
    return ADAPTERS_ROOT / name


def _build_registry() -> dict[str, AdapterMetadata]:
    bilibili_dir = _adapter_dir("bilibili__nemo2011")
    seo_dir = _adapter_dir("seo__bing_via_ddgs")

    return {
        "bilibili__nemo2011": AdapterMetadata(
            name="bilibili__nemo2011",
            config=AdapterConfig(
                platform="bilibili",
                path_id="bilibili__nemo2011",
                repo="https://github.com/Nemo2011/bilibili-api",
                setup_script=bilibili_dir / "setup.sh",
                run_script=bilibili_dir / "run.py",
            ),
        ),
        "seo__bing_via_ddgs": AdapterMetadata(
            name="seo__bing_via_ddgs",
            config=AdapterConfig(
                platform="seo",
                path_id="seo__bing_via_ddgs",
                repo="https://github.com/deedy5/ddgs",
                setup_script=seo_dir / "setup.sh",
                run_script=seo_dir / "run.py",
                max_items=10,
            ),
        ),
    }


REGISTRY = _build_registry()


def list_adapters() -> list[AdapterConfig]:
    return [metadata.config for metadata in REGISTRY.values()]


def get_adapter(path_id: str) -> AdapterConfig:
    return REGISTRY[path_id].config
