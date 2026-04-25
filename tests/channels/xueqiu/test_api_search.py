from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path

import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "xueqiu"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_xueqiu_api_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _query(text: str = "贵州茅台") -> SubQuery:
    return SubQuery(text=text, rationale="Need Xueqiu finance coverage")


@pytest.mark.asyncio
async def test_cookie_expired_403_raises_channel_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autosearch.channels.base import ChannelAuthError

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    monkeypatch.setattr(MODULE, "_load_cookies", lambda: True)

    def _expired_cookie(_url: str) -> dict:
        raise urllib.error.HTTPError(_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(MODULE, "_get_json", _expired_cookie)

    with pytest.raises(ChannelAuthError):
        await search(_query())

    assert [event for event, _ in logger.events] == [
        "xueqiu_source_failed",
        "xueqiu_source_failed",
    ]
    assert {kwargs["source"] for _, kwargs in logger.events} == {"stock", "hot_posts"}
    assert all("403" in str(kwargs["reason"]) for _, kwargs in logger.events)


@pytest.mark.asyncio
async def test_network_fail_raises_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autosearch.channels.base import TransientError

    monkeypatch.setattr(MODULE, "_load_cookies", lambda: True)

    def _network_fail(_url: str) -> dict:
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(MODULE, "_get_json", _network_fail)

    with pytest.raises(TransientError):
        await search(_query())


@pytest.mark.asyncio
async def test_partial_source_failure_returns_results_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    monkeypatch.setattr(MODULE, "_load_cookies", lambda: True)

    def _mixed_response(url: str) -> dict:
        if "stock/search.json" in url:
            raise urllib.error.URLError("timed out")
        return {
            "list": [
                {
                    "data": (
                        '{"title": "贵州茅台 投资讨论", "text": "贵州茅台 今日热帖", '
                        '"target": "/123", "user": {"screen_name": "investor"}}'
                    )
                }
            ]
        }

    monkeypatch.setattr(MODULE, "_get_json", _mixed_response)

    results = await search(_query())

    assert len(results) == 1
    assert results[0].url == "https://xueqiu.com/123"
    assert results[0].source_channel == "xueqiu:investor"
    assert logger.events == [
        ("xueqiu_source_failed", {"source": "stock", "reason": "<urlopen error timed out>"})
    ]
