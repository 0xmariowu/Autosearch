"""Compatibility adapters for legacy findings and prior run artifacts."""

from __future__ import annotations

from typing import Any

from .normalize import normalize_evidence_record


def normalize_legacy_finding(item: dict[str, Any]) -> dict[str, Any]:
    if str(item.get("record_type") or "") == "evidence":
        return normalize_evidence_record(item)
    adapted = {
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "body": str(item.get("body") or item.get("snippet") or ""),
        "source": str(item.get("source") or item.get("provider") or "unknown"),
        "query": str(item.get("query") or ""),
        "clean_markdown": str(item.get("clean_markdown") or ""),
        "fit_markdown": str(item.get("fit_markdown") or ""),
        "references": list(item.get("references") or []),
    }
    return normalize_evidence_record(adapted)
