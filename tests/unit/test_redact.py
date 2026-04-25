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


def test_redact_bearer_preserves_surrounding_text() -> None:
    out = redact("I tested with Bearer abc.def.ghi+/=tail")

    assert out == "I tested with [REDACTED]"


def test_redact_quoted_env_secret_preserves_key() -> None:
    out = redact("TIKHUB_API_KEY='secret-value-123'")

    assert out == "TIKHUB_API_KEY='[REDACTED]'"
    assert "secret-value-123" not in out


def test_redact_json_secret_preserves_key() -> None:
    out = redact('"ANTHROPIC_API_KEY": "sk-ant-secret-tail"')

    assert out == '"ANTHROPIC_API_KEY": "[REDACTED]"'
    assert "sk-ant-secret-tail" not in out


def test_redact_cookie_header_preserves_cookie_names() -> None:
    out = redact("Cookie: SESSDATA=xyz; bili_jct=abc")

    assert out == "Cookie: SESSDATA=[REDACTED]; bili_jct=[REDACTED]"
    assert "xyz" not in out
    assert "abc" not in out


def test_redact_normal_message_unchanged() -> None:
    message = "Hello world, this is a normal message"

    assert redact(message) == message


def test_redact_non_secret_quoted_assignment_unchanged() -> None:
    message = "The quoted_var='not_secret_test'"

    assert redact(message) == message


def test_redact_common_cookie_env_assignment() -> None:
    out = redact("SESSDATA=xyz; _uuid=abc")

    assert out == "SESSDATA=[REDACTED]; _uuid=[REDACTED]"
