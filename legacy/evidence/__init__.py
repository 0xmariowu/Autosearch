"""Evidence package."""

from .classify import evidence_content_type, evidence_domain
from .legacy_adapter import normalize_legacy_finding
from .models import build_evidence_record
from .normalize import (
    coerce_evidence_record,
    coerce_evidence_records,
    normalize_acquired_document,
    normalize_evidence_record,
    normalize_result_record,
)

__all__ = [
    "build_evidence_record",
    "coerce_evidence_record",
    "coerce_evidence_records",
    "evidence_content_type",
    "evidence_domain",
    "normalize_acquired_document",
    "normalize_evidence_record",
    "normalize_legacy_finding",
    "normalize_result_record",
]
