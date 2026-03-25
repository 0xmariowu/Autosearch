"""Normalize raw search hits into stable evidence records."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def evidence_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower()
    except Exception:
        return ""


def _clean_text(text: str, *, limit: int = 500) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned[:limit]


def evidence_content_type(source: str, url: str) -> str:
    source_name = str(source or "").strip().lower()
    url_value = str(url or "").strip().lower()
    if source_name == "github_code":
        return "code"
    if source_name == "github_repos":
        return "repository"
    if source_name == "github_issues":
        return "issue"
    if source_name in {"twitter", "twitter_xreach", "twitter_exa"}:
        return "social"
    if source_name == "huggingface_datasets":
        return "dataset"
    if "github.com" in url_value and "/issues/" in url_value:
        return "issue"
    if "github.com" in url_value and "/blob/" in url_value:
        return "code"
    if "github.com" in url_value:
        return "repository"
    if "huggingface.co/datasets/" in url_value:
        return "dataset"
    return "web"


def build_evidence_record(
    *,
    title: str,
    url: str,
    body: str,
    source: str,
    query: str,
) -> dict[str, Any]:
    clean_title = _clean_text(title, limit=240)
    snippet = _clean_text(body, limit=500)
    domain = evidence_domain(url)
    content_type = evidence_content_type(source, url)
    canonical_text = "\n\n".join(part for part in [clean_title, snippet] if part).strip()
    return {
        "record_type": "evidence",
        "title": clean_title,
        "url": str(url or "").strip(),
        "body": snippet,
        "snippet": snippet,
        "source": str(source or "").strip(),
        "provider": str(source or "").strip(),
        "query": str(query or "").strip(),
        "domain": domain,
        "content_type": content_type,
        "canonical_text": canonical_text,
    }


def build_evidence_record_from_result(result: Any, query: str) -> dict[str, Any]:
    return build_evidence_record(
        title=str(getattr(result, "title", "") or ""),
        url=str(getattr(result, "url", "") or ""),
        body=str(getattr(result, "body", "") or ""),
        source=str(getattr(result, "source", "") or ""),
        query=query,
    )
