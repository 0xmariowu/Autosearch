"""Tests for autosearch.core.redact."""

from __future__ import annotations

import pytest

from autosearch.core.redact import redact, redact_signed_url, redact_url


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


@pytest.mark.parametrize(
    "query_key",
    [
        "access_token",
        "X-Amz-Signature",
        "X-Amz-Credential",
        "sig",
        "token",
        "expires",
    ],
)
def test_redact_url_strips_high_risk_query_key_values(query_key: str) -> None:
    url = f"https://example.com/path?{query_key}=SECRET_VALUE_PLACEHOLDER"

    out = redact_url(url)

    assert "SECRET_VALUE_PLACEHOLDER" not in out
    assert out == "https://example.com/path"


def test_redact_url_without_query_is_unchanged() -> None:
    url = "https://example.com/path"

    assert redact_url(url) == url


def test_redact_url_preserves_fragment_after_stripping_query() -> None:
    out = redact_url("https://example.com/path?token=SECRET_VALUE_PLACEHOLDER#foo")

    assert out == "https://example.com/path#foo"


def test_redact_url_preserves_port_after_stripping_query() -> None:
    out = redact_url("https://example.com:8080/path?token=SECRET_VALUE_PLACEHOLDER")

    assert out == "https://example.com:8080/path"


def test_redact_url_strips_multiple_query_keys() -> None:
    out = redact_url(
        "https://example.com/path?token=SECRET_VALUE_PLACEHOLDER&expires=123&safe=value"
    )

    assert "SECRET_VALUE_PLACEHOLDER" not in out
    assert "expires=123" not in out
    assert "safe=value" not in out
    assert out == "https://example.com/path"


@pytest.mark.parametrize("scheme", ["https", "http"])
def test_redact_url_strips_query_for_http_and_https_variants(scheme: str) -> None:
    out = redact_url(f"{scheme}://example.com/path?token=SECRET_VALUE_PLACEHOLDER")

    assert out == f"{scheme}://example.com/path"


def test_redact_url_empty_string_is_unchanged() -> None:
    assert redact_url("") == ""


def test_redact_url_none_input_raises_type_error() -> None:
    with pytest.raises(TypeError):
        redact_url(None)  # type: ignore[arg-type]


def test_redact_url_malformed_url_returns_as_is() -> None:
    url = "http://[::1"

    assert redact_url(url) == url


class TestRedactSignedUrl:
    def test_redact_signed_url_strips_aws_sig(self) -> None:
        url = (
            "https://bucket.s3.amazonaws.com/key.txt?"
            "X-Amz-Signature=abc123def&X-Amz-Expires=3600&"
            "X-Amz-Date=20260426T000000Z&keepme=ok"
        )

        out = redact_signed_url(url)

        assert "X-Amz-Signature" not in out
        assert "X-Amz-Expires" not in out
        assert "X-Amz-Date" not in out
        assert "keepme=ok" in out
        assert "/key.txt" in out

    def test_redact_signed_url_strips_gcs_sig(self) -> None:
        url = (
            "https://storage.googleapis.com/b/o.json?"
            "X-Goog-Signature=xyz789&X-Goog-Expires=3600&keepme=yes"
        )

        out = redact_signed_url(url)

        assert "X-Goog-Signature" not in out
        assert "X-Goog-Expires" not in out
        assert "keepme=yes" in out

    def test_redact_signed_url_strips_azure_sas(self) -> None:
        url = (
            "https://acct.blob.core.windows.net/c/o.json?"
            "sig=verysecret&se=2026-04-27T00:00:00Z&sp=r&keepme=1"
        )

        out = redact_signed_url(url)

        assert "sig=" not in out
        assert "keepme=1" in out

    def test_redact_signed_url_strips_generic_token(self) -> None:
        url = "https://example.com/path?token=abc&signature=def&Expires=123&keepme=ok"

        out = redact_signed_url(url)

        assert "token=" not in out
        assert "signature=" not in out
        assert "Expires=" not in out
        assert "keepme=ok" in out
