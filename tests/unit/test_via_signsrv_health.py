from __future__ import annotations

import httpx
import pytest

from autosearch.skills.channels.xiaohongshu.methods.via_signsrv import (
    _check_account_health,
)

_HEADERS = {
    "Cookie": "a1=test",
    "X-s": "sig",
    "Content-Type": "application/json",
}


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _ClientReturning:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    async def get(self, url: str, **kwargs: object) -> _Response:
        _ = url
        _ = kwargs
        return _Response(self._payload)


class _ClientRaising:
    async def get(self, url: str, **kwargs: object) -> _Response:
        _ = url
        _ = kwargs
        raise httpx.RequestError("boom")


@pytest.mark.asyncio
async def test_check_account_health_returns_healthy_on_code_zero() -> None:
    client = _ClientReturning({"code": 0})

    healthy, code = await _check_account_health(client, _HEADERS)

    assert healthy is True
    assert code is None


@pytest.mark.asyncio
async def test_check_account_health_returns_restricted_on_300011() -> None:
    client = _ClientReturning({"code": 300011})

    healthy, code = await _check_account_health(client, _HEADERS)

    assert healthy is False
    assert code == "300011"


@pytest.mark.asyncio
async def test_check_account_health_returns_healthy_on_network_failure() -> None:
    client = _ClientRaising()

    healthy, code = await _check_account_health(client, _HEADERS)

    assert healthy is True
    assert code is None
