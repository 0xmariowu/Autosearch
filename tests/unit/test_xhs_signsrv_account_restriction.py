from __future__ import annotations

import pytest

from autosearch.channels.base import ChannelAuthError
from autosearch.core.models import SubQuery
from autosearch.skills.channels.xiaohongshu.methods import via_signsrv


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _Client:
    async def post(self, url: str, **kwargs: object) -> _Response:
        _ = kwargs
        if url.endswith("/sign/xhs"):
            return _Response(
                {
                    "ok": True,
                    "X-s": "sig",
                    "X-t": "123",
                    "X-s-common": "common",
                    "X-b3-traceid": "trace",
                }
            )
        return _Response({"code": 0, "data": {"data": {"items": []}}})

    async def get(self, url: str, **kwargs: object) -> _Response:
        _ = url
        _ = kwargs
        return _Response({"code": 300011})


@pytest.mark.asyncio
async def test_xhs_signsrv_empty_search_with_me_300011_raises_channel_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(via_signsrv.__dict__, "_SIGNSRV_URL", "https://signsrv.example")
    monkeypatch.setitem(via_signsrv.__dict__, "_SERVICE_TOKEN", "as_test")
    monkeypatch.setitem(via_signsrv.__dict__, "_XHS_COOKIES", "a1=test-cookie")

    with pytest.raises(ChannelAuthError, match="300011"):
        await via_signsrv.search(
            SubQuery(text="防晒", rationale="Need XHS coverage"),
            client=_Client(),
        )
