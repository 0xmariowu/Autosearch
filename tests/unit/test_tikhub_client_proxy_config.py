from __future__ import annotations

import pytest

from autosearch.channels.base import ChannelAuthError
from autosearch.lib.tikhub_client import TikhubClient


def test_init_raises_channel_auth_error_when_proxy_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://proxy.example")
    monkeypatch.delenv("AUTOSEARCH_PROXY_TOKEN", raising=False)

    with pytest.raises(ChannelAuthError, match="AUTOSEARCH_PROXY_TOKEN"):
        TikhubClient()
