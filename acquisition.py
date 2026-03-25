"""Minimal local acquisition layer for turning web pages into clean text."""

from __future__ import annotations

import re
import urllib.request
from html import unescape
from html.parser import HTMLParser
from typing import Any


class _VisibleTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        lowered = str(tag or "").lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif lowered == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):  # type: ignore[override]
        lowered = str(tag or "").lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif lowered == "title":
            self._in_title = False

    def handle_data(self, data: str):  # type: ignore[override]
        if self._skip_depth > 0:
            return
        text = str(data or "").strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        self._text_parts.append(text)

    @property
    def title(self) -> str:
        return _clean_text(" ".join(self._title_parts), limit=240)

    @property
    def text(self) -> str:
        return _clean_text(" ".join(self._text_parts), limit=4000)


def _clean_text(text: str, *, limit: int = 4000) -> str:
    cleaned = unescape(str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def extract_visible_text(html: str) -> dict[str, str]:
    parser = _VisibleTextExtractor()
    parser.feed(str(html or ""))
    parser.close()
    return {
        "title": parser.title,
        "text": parser.text,
    }


def fetch_page(url: str, *, timeout: int = 10) -> dict[str, Any]:
    request = urllib.request.Request(
        str(url or "").strip(),
        headers={"User-Agent": "autosearch/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "")
        payload = response.read().decode("utf-8", errors="replace")
    extracted = extract_visible_text(payload)
    return {
        "url": str(url or "").strip(),
        "content_type": content_type,
        "raw_html": payload,
        "title": extracted["title"],
        "text": extracted["text"],
    }


def enrich_evidence_record(
    record: dict[str, Any],
    *,
    timeout: int = 10,
) -> dict[str, Any]:
    enriched = dict(record)
    try:
        page = fetch_page(str(record.get("url") or ""), timeout=timeout)
    except Exception as exc:
        enriched["acquired"] = False
        enriched["acquisition_error"] = str(exc)
        return enriched
    enriched["acquired"] = True
    enriched["acquired_title"] = page.get("title", "")
    enriched["acquired_text"] = page.get("text", "")
    enriched["acquired_content_type"] = page.get("content_type", "")
    return enriched
