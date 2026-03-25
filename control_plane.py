"""
Build the current AutoSearch control plane.

This is the runtime-facing "org state" for the project:

- what the current objective is
- which runtime providers are usable
- which providers are preferred / cooled down
- which optional research sources are available
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_experience import get_provider_decision
from source_capability import get_source_decision, load_source_catalog


REPO_ROOT = Path(__file__).resolve().parent
CONTROL_ROOT = REPO_ROOT / "control"
CONTROL_PLANE_PATH = CONTROL_ROOT / "latest-program.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _empty_control_plane() -> dict[str, Any]:
    return {
        "generated_at": None,
        "run_id": None,
        "objective": "",
        "runtime": {
            "providers": [],
            "top_providers": [],
            "skipped_providers": [],
        },
        "research_sources": [],
        "query_families": [],
    }


def ensure_control_files() -> None:
    CONTROL_ROOT.mkdir(parents=True, exist_ok=True)
    if not CONTROL_PLANE_PATH.exists():
        write_json(CONTROL_PLANE_PATH, _empty_control_plane())


def build_control_plane(
    *,
    target_spec: str,
    capability_report: dict[str, Any],
    experience_policy: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    catalog = load_source_catalog()
    runtime_rows: list[dict[str, Any]] = []
    research_rows: list[dict[str, Any]] = []
    query_family_rows: list[dict[str, Any]] = []

    for source in catalog.get("sources", []):
        name = str(source.get("name") or "")
        if not name:
            continue
        capability = get_source_decision(capability_report, name)
        if source.get("runtime_enabled"):
            experience = get_provider_decision(experience_policy, name, "unknown")
            row = {
                "name": name,
                "family": str(source.get("family") or ""),
                "backend": str(source.get("backend") or ""),
                "capability_status": capability["status"],
                "capability_available": capability["available"],
                "experience_status": experience["status"],
                "should_skip": capability["should_skip"] or experience["should_skip"],
                "priority": [capability["priority"], experience["priority"]],
                "reason": experience.get("reason", ""),
                "message": capability.get("message", ""),
            }
            runtime_rows.append(row)
        else:
            research_rows.append({
                "name": name,
                "kind": str(source.get("kind") or ""),
                "family": str(source.get("family") or ""),
                "available": capability["available"],
                "status": capability["status"],
                "message": capability.get("message", ""),
            })

    runtime_rows.sort(key=lambda row: (row["priority"][0], row["priority"][1], row["name"]))

    search_policy = ((experience_policy.get("aspects") or {}).get("search") or {})
    for family, policy in sorted((search_policy.get("query_families") or {}).items()):
        query_family_rows.append({
            "name": family,
            "preferred_providers": list(policy.get("preferred_providers") or []),
            "cooldown_providers": list(policy.get("cooldown_providers") or []),
        })

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "run_id": run_id,
        "objective": target_spec,
        "runtime": {
            "providers": runtime_rows,
            "top_providers": [row["name"] for row in runtime_rows if not row["should_skip"]][:5],
            "skipped_providers": [row["name"] for row in runtime_rows if row["should_skip"]],
        },
        "research_sources": research_rows,
        "query_families": query_family_rows,
    }


def refresh_control_plane(
    *,
    target_spec: str,
    capability_report: dict[str, Any],
    experience_policy: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    ensure_control_files()
    payload = build_control_plane(
        target_spec=target_spec,
        capability_report=capability_report,
        experience_policy=experience_policy,
        run_id=run_id,
    )
    write_json(CONTROL_PLANE_PATH, payload)
    return payload
