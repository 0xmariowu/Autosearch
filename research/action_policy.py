"""Action gating for deep research loops."""

from __future__ import annotations

from typing import Any


def build_action_policy(
    *,
    mode: str,
    bundle_state: dict[str, Any],
    judge_result: dict[str, Any],
    round_history: list[dict[str, Any]],
    gap_queue: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    allowed = {"search", "repair", "cross_verify"}
    disabled_reasons: dict[str, str] = {}

    accepted_findings = list(bundle_state.get("accepted_findings") or [])
    open_gaps = [
        item for item in list(gap_queue or [])
        if str(item.get("status") or "open") == "open"
    ]
    if len(accepted_findings) >= 40:
        allowed.discard("search")
        disabled_reasons["search"] = "too_many_unread_findings"
    if not judge_result.get("missing_dimensions") and not open_gaps:
        allowed.discard("repair")
        disabled_reasons["repair"] = "no_open_gaps"
    if mode == "speed":
        allowed.discard("cross_verify")
        disabled_reasons["cross_verify"] = "mode_speed"
    if round_history:
        last = dict(round_history[-1] or {})
        if str(last.get("role") or "") in {"graph_followup", "decomposition_followup"}:
            allowed.discard("cross_verify")
            disabled_reasons["cross_verify"] = "recent_cross_verification"

    return {
        "allowed_actions": sorted(allowed),
        "disabled_reasons": disabled_reasons,
    }
