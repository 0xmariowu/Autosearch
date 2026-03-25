"""Markdown cleaning utilities inspired by Crawl4AI patterns."""

from __future__ import annotations

import re

from .content_filter import select_relevant_content


def clean_markdown(text: str) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def fit_markdown(text: str, *, query: str = "", max_chars: int = 2400) -> str:
    cleaned = clean_markdown(text)
    if len(cleaned) <= max_chars:
        return cleaned
    if query:
        return select_relevant_content(cleaned, query=query, max_chars=max_chars)
    paragraphs = [paragraph.strip() for paragraph in cleaned.split("\n\n") if paragraph.strip()]
    if len(paragraphs) <= 5:
        truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
        return truncated or cleaned[:max_chars].strip()
    intro = paragraphs[:2]
    conclusion = paragraphs[-1:]
    middle = paragraphs[2:-1]
    ranked = sorted(middle, key=lambda paragraph: len(re.findall(r"[A-Za-z0-9_\-]{4,}", paragraph)), reverse=True)[:3]
    selected = "\n\n".join(intro + ranked + conclusion)
    truncated = selected[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or selected[:max_chars].strip()
