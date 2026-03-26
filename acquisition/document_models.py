"""Document models for acquisition and extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser


def _clean_text(text: str, *, limit: int = 12000) -> str:
    cleaned = unescape(str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def _document_id(url: str, final_url: str, title: str) -> str:
    raw = f"{url}\n{final_url}\n{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


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
        return _clean_text(" ".join(self._text_parts), limit=12000)


@dataclass
class AcquiredDocument:
    document_id: str = ""
    url: str = ""
    final_url: str = ""
    status_code: int = 0
    content_type: str = ""
    fetch_method: str = "http_fetch"
    title: str = ""
    text: str = ""
    raw_html: str = ""
    raw_html_path: str = ""
    clean_markdown: str = ""
    fit_markdown: str = ""
    chunk_scores: list[dict[str, object]] = field(default_factory=list)
    selected_chunks: list[str] = field(default_factory=list)
    references: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    used_render_fallback: bool = False

    @classmethod
    def from_html(
        cls,
        url: str,
        html: str,
        *,
        content_type: str = "text/html",
        final_url: str | None = None,
        status_code: int = 200,
        fetch_method: str = "http_fetch",
        raw_html_path: str = "",
        metadata: dict[str, str] | None = None,
        used_render_fallback: bool = False,
    ) -> "AcquiredDocument":
        parser = _VisibleTextExtractor()
        parser.feed(str(html or ""))
        parser.close()
        clean_url = str(url or "").strip()
        clean_final_url = str(final_url or url or "").strip()
        clean_title = parser.title
        return cls(
            document_id=_document_id(clean_url, clean_final_url, clean_title),
            url=clean_url,
            final_url=clean_final_url,
            status_code=int(status_code or 0),
            content_type=str(content_type or ""),
            fetch_method=str(fetch_method or "http_fetch"),
            title=clean_title,
            text=parser.text,
            raw_html=str(html or ""),
            raw_html_path=str(raw_html_path or ""),
            metadata=dict(metadata or {}),
            used_render_fallback=used_render_fallback,
        )
