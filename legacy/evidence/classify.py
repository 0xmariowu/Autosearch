"""Evidence classification helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def evidence_domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower()
    except Exception:
        return ""


def clean_text(text: str, *, limit: int = 500) -> str:
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
