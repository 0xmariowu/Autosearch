from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import pytest

from autosearch.channels.base import PermanentError
from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "instagram"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_instagram_via_tikhub", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _FakeTikhubClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        return self.payload


@pytest.mark.asyncio
async def test_search_raises_on_invalid_payload_shape() -> None:
    client = _FakeTikhubClient({"data": {"data": {"items": {"unexpected": []}}}})

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(
            SubQuery(text="camera", rationale="Need Instagram post coverage"),
            client=cast(TikhubClient, client),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload"),
    [
        {},
        {"data": "wrong"},
        {"data": {"data": []}},
    ],
)
async def test_search_raises_when_nested_data_is_missing_or_wrong_type(
    payload: dict[str, object],
) -> None:
    client = _FakeTikhubClient(payload)

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(
            SubQuery(text="camera", rationale="Need Instagram post coverage"),
            client=cast(TikhubClient, client),
        )


@pytest.mark.asyncio
async def test_search_allows_legitimate_empty_items_list() -> None:
    client = _FakeTikhubClient({"data": {"data": {"items": []}}})

    results = await search(
        SubQuery(text="camera", rationale="Need Instagram post coverage"),
        client=cast(TikhubClient, client),
    )

    assert results == []
