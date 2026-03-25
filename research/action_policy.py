"""Action gating for deep research loops."""

from __future__ import annotations

from typing import Any

from .modes import get_mode_policy


def build_action_policy(
    *,
    mode: str,
    active_program: dict[str, Any] | None = None,
    bundle_state: dict[str, Any],
    judge_result: dict[str, Any],
    round_history: list[dict[str, Any]],
    gap_queue: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    program = dict(active_program or {})
    mode_policy = get_mode_policy(mode, dict(program.get("mode_policy_overrides") or {}))
    allowed = {"search", "repair", "cross_verify"}
    disabled_reasons: dict[str, str] = {}

    accepted_findings = list(bundle_state.get("accepted_findings") or [])
    open_gaps = [
        item for item in list(gap_queue or [])
        if str(item.get("status") or "open") == "open"
    ]
    max_findings = int(
        (program.get("action_policy_defaults") or {}).get("max_findings_before_search_disable", mode_policy.max_findings_before_search_disable)
        or mode_policy.max_findings_before_search_disable
    )
    if len(accepted_findings) >= max_findings:
        allowed.discard("search")
        disabled_reasons["search"] = "too_many_unread_findings"
    if not judge_result.get("missing_dimensions") and not open_gaps:
        allowed.discard("repair")
        disabled_reasons["repair"] = "no_open_gaps"
    for action in list((program.get("action_policy_defaults") or {}).get("disabled_actions") or list(mode_policy.disabled_actions)):
        clean = str(action or "").strip()
        if clean in allowed:
            allowed.discard(clean)
            disabled_reasons[clean] = f"mode_{mode_policy.name}"
    if round_history:
        last = dict(round_history[-1] or {})
        if str(last.get("role") or "") in {"graph_followup", "decomposition_followup"}:
            allowed.discard("cross_verify")
            disabled_reasons["cross_verify"] = "recent_cross_verification"
        if mode_policy.name == "speed" and len(round_history) >= 1 and accepted_findings:
            allowed.discard("repair")
            disabled_reasons["repair"] = "mode_speed_short_cycle"
    if mode_policy.name == "deep" and open_gaps:
        allowed.add("cross_verify")
        disabled_reasons.pop("cross_verify", None)

    return {
        "allowed_actions": sorted(allowed),
        "disabled_reasons": disabled_reasons,
    }
