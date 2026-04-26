"""Shared secret-redaction utility.

Used at every CLI/MCP boundary so an upstream library, third-party API
response, or accidental exception text can't leak credentials into
agent-visible output. The diagnostics command, MCP tool responses, and
runtime experience writes all funnel through `redact()`.

Conservative match list — must NOT alter ordinary user prose.
"""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SECRET_KEY_PATTERN = (
    r"(?:"
    r"[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|COOKIES?|PASSWORD|PASSWD|AUTH|CREDENTIALS?|SESSION)[A-Z0-9_]*"
    r"|XHS_COOKIES|SESSDATA|bili_jct|_uuid|buvid3|buvid4|DedeUserID(?:__ckMd5)?"
    r")"
)

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-or-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"),
    re.compile(r"tvly-[A-Za-z0-9_-]{16,}"),
    re.compile(r"exa-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-+/=~]+"),
    # Generic KEY=value where value looks token-shaped — preserve key name
    re.compile(r"([A-Z][A-Z0-9_]+_(KEY|TOKEN|SECRET|COOKIES?))=([^\s\"']{8,})"),
]

_QUOTED_ENV_PATTERN = re.compile(
    rf"(?P<prefix>\b{_SECRET_KEY_PATTERN}=)(?P<quote>['\"])(?P<value>[^'\"\r\n]*)(?P=quote)"
)
_JSON_SECRET_PATTERN = re.compile(
    rf'(?P<prefix>"{_SECRET_KEY_PATTERN}"\s*:\s*")(?P<value>[^"\r\n]*)(?P<suffix>")'
)
_COOKIE_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:XHS_COOKIES|SESSDATA|bili_jct|_uuid|buvid3|buvid4|DedeUserID(?:__ckMd5)?)=)(?P<value>[^'\"\s;]+)"
)
_COOKIE_HEADER_PATTERN = re.compile(r"(?im)(?P<prefix>\bCookie:\s*)(?P<cookies>[^\r\n]*)")
_COOKIE_PAIR_PATTERN = re.compile(r"(?P<name>[^=;\s]+)=(?P<value>[^;]*)")
_SIGNED_URL_QUERY_KEYS = {
    key.lower()
    for key in {
        # Generic
        "Signature",
        "signature",
        "sig",
        "token",
        "Expires",
        # AWS SigV4 (S3 / CloudFront / etc.)
        "X-Amz-Signature",
        "X-Amz-Credential",
        "X-Amz-Algorithm",
        "X-Amz-SignedHeaders",
        "X-Amz-Security-Token",
        "X-Amz-Date",
        "X-Amz-Expires",
        # Google Cloud Storage
        "X-Goog-Signature",
        "X-Goog-Expires",
        # Azure Blob SAS
        "se",
        "sp",
        "sv",
        "srt",
        "ss",
        "st",
        "spr",
        "skoid",
        "sktid",
        "skt",
        "ske",
        "sks",
        "skv",
        # CloudFront signed URLs
        "Policy",
        "Key-Pair-Id",
    }
}
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_EXPLICIT_URL_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_DOMAIN_HOST_PATTERN = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
_IPV4_HOST_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def _replacer(match: re.Match) -> str:
    if match.lastindex and match.lastindex >= 1 and match.group(1):
        return f"{match.group(1)}=[REDACTED]"
    return "[REDACTED]"


def _replace_quoted_env(match: re.Match) -> str:
    return f"{match.group('prefix')}{match.group('quote')}[REDACTED]{match.group('quote')}"


def _replace_json_secret(match: re.Match) -> str:
    return f"{match.group('prefix')}[REDACTED]{match.group('suffix')}"


def _replace_cookie_assignment(match: re.Match) -> str:
    return f"{match.group('prefix')}[REDACTED]"


def _replace_cookie_header(match: re.Match) -> str:
    cookies = _COOKIE_PAIR_PATTERN.sub(
        lambda cookie_match: f"{cookie_match.group('name')}=[REDACTED]",
        match.group("cookies"),
    )
    return f"{match.group('prefix')}{cookies}"


def redact(text: str) -> str:
    """Replace anything matching `_SECRET_PATTERNS` with `[REDACTED]`."""
    if not text:
        return text
    out = text
    out = _COOKIE_HEADER_PATTERN.sub(_replace_cookie_header, out)
    out = _QUOTED_ENV_PATTERN.sub(_replace_quoted_env, out)
    out = _JSON_SECRET_PATTERN.sub(_replace_json_secret, out)
    out = _COOKIE_ASSIGNMENT_PATTERN.sub(_replace_cookie_assignment, out)
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_replacer, out)
    return out


def redact_url(url: str, *, strip_query: bool = True) -> str:
    """Return `url` with query-string secrets removed."""
    if not isinstance(url, str):
        raise TypeError("url must be str")

    try:
        parts = urlsplit(url)
    except ValueError:
        return url

    query = "" if strip_query else parts.query
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def redact_path_for_output(p: str) -> str:
    """Return a URL-redacted value or basename-only local path for structured output."""
    if not p:
        return ""

    if _is_windows_drive_path(p):
        return _local_path_name(p)

    if _EXPLICIT_URL_SCHEME_PATTERN.match(p) or _looks_like_schemeless_url(p):
        return redact_url(p)
    return _local_path_name(p)


def _is_windows_drive_path(value: str) -> bool:
    return bool(_WINDOWS_DRIVE_PATH_PATTERN.match(value))


def _local_path_name(value: str) -> str:
    if "\\" in value or _is_windows_drive_path(value):
        return PureWindowsPath(value).name
    return Path(value).name


def _looks_like_schemeless_url(value: str) -> bool:
    if value.startswith(("/", "\\")) or _is_windows_drive_path(value):
        return False

    try:
        parts = urlsplit(f"//{value}")
    except ValueError:
        return False

    host = parts.hostname or ""
    return (
        host == "localhost"
        or bool(_DOMAIN_HOST_PATTERN.match(host))
        or bool(_IPV4_HOST_PATTERN.match(host))
    )


def redact_signed_url(url: str) -> str:
    """Default-redact signed URL params at the citation MCP boundary."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url

    if not parts.scheme:
        return url

    query_items = parse_qsl(parts.query, keep_blank_values=True)
    filtered_query = [
        (name, value) for name, value in query_items if name.lower() not in _SIGNED_URL_QUERY_KEYS
    ]
    query = urlencode(filtered_query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
