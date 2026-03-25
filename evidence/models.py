"""Evidence record model helpers."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .classify import clean_text, evidence_content_type, evidence_domain


def _evidence_id(url: str, title: str, query: str) -> str:
    raw = f"{url}\n{title}\n{query}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def _keywords(*parts: str, limit: int = 8) -> list[str]:
    seen: list[str] = []
    for part in parts:
        for token in re.findall(r"[A-Za-z0-9_\\-]{4,}", str(part or "").lower()):
            if token in seen:
                continue
            seen.append(token)
            if len(seen) >= limit:
                return seen
    return seen


def _summary(title: str, snippet: str) -> str:
    pieces = [clean_text(title, limit=180), clean_text(snippet, limit=220)]
    return " — ".join(piece for piece in pieces if piece).strip(" —")


def _extract(snippet: str, fit_markdown: str) -> str:
    if fit_markdown:
        return clean_text(fit_markdown, limit=500)
    return clean_text(snippet, limit=280)


def _repo_name(url: str) -> str:
    value = str(url or "").strip()
    if "github.com/" not in value:
        return ""
    tail = value.split("github.com/", 1)[1].strip("/")
    parts = tail.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _dataset_name(url: str, content_type: str) -> str:
    if content_type != "dataset":
        return ""
    value = str(url or "").strip()
    if "huggingface.co/datasets/" in value:
        return value.split("huggingface.co/datasets/", 1)[1].strip("/").split("/")[0]
    return ""


def build_evidence_record(
    *,
    title: str,
    url: str,
    body: str,
    source: str,
    query: str,
    query_family: str = "unknown",
    backend: str = "",
    clean_markdown: str = "",
    fit_markdown: str = "",
    references: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    clean_title = clean_text(title, limit=240)
    snippet = clean_text(body, limit=500)
    domain = evidence_domain(url)
    content_type = evidence_content_type(source, url)
    canonical_parts = [clean_title, snippet]
    if fit_markdown:
        canonical_parts.append(clean_text(fit_markdown, limit=1200))
    canonical_text = "\n\n".join(part for part in canonical_parts if part).strip()
    citations = [str(item.get("url") or "").strip() for item in list(references or []) if str(item.get("url") or "").strip()]
    extract = _extract(snippet, fit_markdown)
    summary = _summary(clean_title, snippet)
    return {
        "record_type": "evidence",
        "evidence_id": _evidence_id(str(url or "").strip(), clean_title, str(query or "").strip()),
        "title": clean_title,
        "url": str(url or "").strip(),
        "body": snippet,
        "snippet": snippet,
        "source": str(source or "").strip(),
        "provider": str(source or "").strip(),
        "query": str(query or "").strip(),
        "query_family": str(query_family or "unknown").strip() or "unknown",
        "backend": str(backend or source or "").strip(),
        "domain": domain,
        "content_type": content_type,
        "evidence_type": content_type,
        "summary": summary,
        "extract": extract,
        "citations": citations,
        "keywords": _keywords(clean_title, snippet, fit_markdown, query),
        "repo": _repo_name(url),
        "dataset": _dataset_name(url, content_type),
        "author": "",
        "published_at": "",
        "doc_quality": "high" if fit_markdown else "medium" if snippet else "low",
        "canonical_text": canonical_text,
        "clean_markdown": str(clean_markdown or ""),
        "fit_markdown": str(fit_markdown or ""),
        "references": list(references or []),
    }
