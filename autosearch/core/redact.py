"""Shared secret-redaction utility.

Used at every CLI/MCP boundary so an upstream library, third-party API
response, or accidental exception text can't leak credentials into
agent-visible output. The diagnostics command, MCP tool responses, and
runtime experience writes all funnel through `redact()`.

Conservative match list — must NOT alter ordinary user prose.
"""

from __future__ import annotations

import re

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
    re.compile(r"(?i)Cookie:\s*[^\n]+"),
    # Generic KEY=value where value looks token-shaped — preserve key name
    re.compile(r"([A-Z][A-Z0-9_]+_(KEY|TOKEN|SECRET|COOKIES?))=([^\s\"']{8,})"),
]


def _replacer(match: re.Match) -> str:
    if match.lastindex and match.lastindex >= 1 and match.group(1):
        return f"{match.group(1)}=[REDACTED]"
    return "[REDACTED]"


def redact(text: str) -> str:
    """Replace anything matching `_SECRET_PATTERNS` with `[REDACTED]`."""
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_replacer, out)
    return out
