"""Tests for autosearch.core.redact."""

from __future__ import annotations

from autosearch.core.redact import redact


def test_redact_bearer_token_with_plus_slash_equals_redacts_full_token() -> None:
    out = redact("Authorization: Bearer abcDEF123+/=SECRETTAIL")

    assert "abcDEF123" not in out
    assert "SECRETTAIL" not in out
    assert "[REDACTED]" in out


def test_redact_bearer_token_with_underscore_and_hyphen_redacts_full_token() -> None:
    out = redact("Authorization: Bearer abc_DEF-SECRETTAIL")

    assert "abc_DEF" not in out
    assert "SECRETTAIL" not in out
    assert "[REDACTED]" in out


def test_redact_bearer_jwt_style_token_redacts_full_token() -> None:
    out = redact("Authorization: Bearer header.payload.SECRETTAIL")

    assert "header.payload" not in out
    assert "SECRETTAIL" not in out
    assert "[REDACTED]" in out
