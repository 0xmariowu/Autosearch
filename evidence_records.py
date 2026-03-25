"""Backward-compatible wrapper over the formal evidence package."""

from __future__ import annotations

from typing import Any

from evidence.classify import evidence_content_type, evidence_domain
from evidence.models import build_evidence_record
from evidence.normalize import normalize_result_record

__all__ = [
    "build_evidence_record",
    "build_evidence_record_from_result",
    "evidence_content_type",
    "evidence_domain",
]


def build_evidence_record_from_result(result: Any, query: str) -> dict[str, Any]:
    return normalize_result_record(result, query)
