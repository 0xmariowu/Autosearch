"""Project-agnostic runtime state for autoresearch-style goal loops."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
GOAL_CASES_ROOT = REPO_ROOT / "goal_cases"
GOAL_RUNTIME_ROOT = GOAL_CASES_ROOT / "runtime"

DEFAULT_HARNESS = {
    "version": 1,
    "bundle_policy": {
        "per_query_cap": 5,
        "per_source_cap": 18,
        "per_domain_cap": 18,
    },
    "anti_cheat": {
        "min_new_unique_urls": 1,
        "min_novelty_ratio": 0.01,
        "min_source_diversity": 0.15,
        "max_source_concentration": 0.82,
        "max_query_concentration": 0.70,
        "min_new_sources_when_score_improves": 0,
    },
}


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})
    return payload if isinstance(payload, dict) else dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_paths(goal_id: str) -> dict[str, Path]:
    runtime_root = GOAL_RUNTIME_ROOT / goal_id
    return {
        "runtime_root": runtime_root,
        "accepted_program": runtime_root / "accepted-program.json",
        "harness": runtime_root / "evaluation-harness.json",
        "program_archive": runtime_root / "program-archive",
    }


def ensure_harness(goal_case: dict[str, Any]) -> dict[str, Any]:
    goal_id = str(goal_case.get("id") or "goal")
    paths = runtime_paths(goal_id)
    payload = _read_json(paths["harness"])
    if not payload:
        payload = {
            "goal_id": goal_id,
            "created_at": datetime.now().astimezone().isoformat(),
            **DEFAULT_HARNESS,
        }
        _write_json(paths["harness"], payload)
    return payload


def _normalize_query_spec(query: Any) -> dict[str, Any]:
    if isinstance(query, dict):
        return {
            "text": str(query.get("text") or "").strip(),
            "platforms": list(query.get("platforms") or []),
        }
    return {"text": str(query or "").strip(), "platforms": []}


def default_program(goal_case: dict[str, Any], available_providers: list[str]) -> dict[str, Any]:
    queries = [
        _normalize_query_spec(query)
        for query in list(goal_case.get("seed_queries") or [])
        if _normalize_query_spec(query)["text"]
    ]
    return {
        "program_id": "seed-program",
        "goal_id": str(goal_case.get("id") or ""),
        "parent_program_id": None,
        "label": "seed-program",
        "created_at": datetime.now().astimezone().isoformat(),
        "queries": queries,
        "provider_mix": list(available_providers),
        "plan_count": 3,
        "max_queries": 5,
        "mutation_history": [],
        "score": 0,
        "dimension_scores": {},
    }


def load_accepted_program(goal_case: dict[str, Any], available_providers: list[str]) -> dict[str, Any]:
    goal_id = str(goal_case.get("id") or "goal")
    paths = runtime_paths(goal_id)
    payload = _read_json(paths["accepted_program"])
    if payload:
        return payload
    return default_program(goal_case, available_providers)


def save_accepted_program(goal_id: str, program: dict[str, Any]) -> Path:
    paths = runtime_paths(goal_id)
    _write_json(paths["accepted_program"], program)
    return paths["accepted_program"]


def build_candidate_program(
    *,
    goal_id: str,
    parent_program: dict[str, Any],
    label: str,
    queries: list[dict[str, Any]],
    provider_mix: list[str],
    round_index: int,
    candidate_index: int,
) -> dict[str, Any]:
    created_at = datetime.now().astimezone().isoformat()
    run_token = datetime.now().strftime("%H%M%S%f")
    return {
        "program_id": f"{goal_id}-r{round_index}-c{candidate_index}-{run_token}",
        "goal_id": goal_id,
        "parent_program_id": parent_program.get("program_id"),
        "label": label,
        "created_at": created_at,
        "queries": list(queries),
        "provider_mix": list(provider_mix),
        "plan_count": int(parent_program.get("plan_count", 3) or 3),
        "max_queries": int(parent_program.get("max_queries", 5) or 5),
        "mutation_history": list(parent_program.get("mutation_history") or []) + [label],
        "score": int(parent_program.get("score", 0) or 0),
        "dimension_scores": dict(parent_program.get("dimension_scores") or {}),
    }


def archive_candidate_program(
    goal_id: str,
    candidate_program: dict[str, Any],
    *,
    result: dict[str, Any],
) -> Path:
    paths = runtime_paths(goal_id)
    archive_dir = paths["program_archive"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{candidate_program['program_id']}.json"
    payload = {
        "candidate_program": candidate_program,
        "result": result,
    }
    _write_json(archive_path, payload)
    return archive_path
