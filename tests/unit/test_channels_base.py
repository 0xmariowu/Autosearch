from __future__ import annotations

from autosearch.channels.base import (
    AccountRestrictedError,
    ChannelAuthError,
    PermanentError,
)


class TestAccountRestrictedError:
    def test_is_channel_auth_error_and_permanent_error(self) -> None:
        assert issubclass(AccountRestrictedError, ChannelAuthError)
        assert issubclass(AccountRestrictedError, PermanentError)

    def test_preserves_message(self) -> None:
        exc = AccountRestrictedError("XHS account restricted: code=300011")

        assert str(exc) == "XHS account restricted: code=300011"
