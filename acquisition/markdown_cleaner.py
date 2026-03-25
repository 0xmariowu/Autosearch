"""Markdown cleaning utilities inspired by Crawl4AI patterns."""

from __future__ import annotations

import re


def clean_markdown(text: str) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def fit_markdown(text: str, *, max_chars: int = 2400) -> str:
    cleaned = clean_markdown(text)
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or cleaned[:max_chars].strip()
