from __future__ import annotations

from dataclasses import dataclass, field

from autosearch.channels.base import (
    BudgetExhausted,
    ChannelAuthError,
    MethodUnavailable,
    PermanentError,
    RateLimited,
    TransientError,
)
from autosearch.core.redact import redact


@dataclass(frozen=True)
class ChannelFailureStatus:
    status: str
    reason: str
    fix_hint: str | None = None
    unmet_requires: list[str] = field(default_factory=list)


_MISSING_CONFIG_MARKERS = (
    "not configured",
    "missing config",
    "missing required",
    "missing env",
    "missing key",
    "requirements unmet",
    "unmet require",
    "no available search methods",
)


def _custom_fix_hint(exc: Exception) -> str | None:
    fix_hint = getattr(exc, "fix_hint", None)
    if isinstance(fix_hint, str) and fix_hint.strip():
        return fix_hint.strip()
    return None


def _method_unavailable_status(exc: MethodUnavailable) -> str:
    message = str(exc).lower()
    if any(marker in message for marker in _MISSING_CONFIG_MARKERS):
        return "not_configured"
    return "channel_unavailable"


def exception_to_channel_status(exc: Exception) -> ChannelFailureStatus:
    """Map channel exceptions to MCP-facing status fields."""

    if isinstance(exc, BudgetExhausted):
        status = "budget_exhausted"
        fix_hint = "Top up the provider balance or switch to a free channel."
    elif isinstance(exc, ChannelAuthError):
        status = "auth_failed"
        fix_hint = "Refresh the channel login or configure a valid API key."
    elif isinstance(exc, RateLimited):
        status = "rate_limited"
        fix_hint = "Wait before retrying or reduce parallel channel fan-out."
    elif isinstance(exc, TransientError):
        status = "transient_error"
        fix_hint = "Retry this channel later."
    elif isinstance(exc, MethodUnavailable):
        status = _method_unavailable_status(exc)
        fix_hint = (
            "Configure the channel requirements and retry."
            if status == "not_configured"
            else "Try another channel or retry after methods recover."
        )
    elif isinstance(exc, PermanentError):
        status = "channel_error"
        fix_hint = "Do not retry blindly; check for schema drift or a permanent upstream failure."
    else:
        status = "channel_error"
        fix_hint = None

    fix_hint = _custom_fix_hint(exc) or fix_hint

    return ChannelFailureStatus(
        status=status,
        reason=redact(f"{status}: {type(exc).__name__}: {exc}"),
        fix_hint=fix_hint,
    )
