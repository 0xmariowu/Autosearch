"""Document models for acquisition and extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser


def _clean_text(text: str, *, limit: int = 12000) -> str:
    cleaned = unescape(str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


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
    url: str
    final_url: str
    content_type: str
    title: str
    text: str
    raw_html: str = ""
    clean_markdown: str = ""
    fit_markdown: str = ""
    references: list[dict[str, str]] = field(default_factory=list)
    used_render_fallback: bool = False

    @classmethod
    def from_html(
        cls,
        url: str,
        html: str,
        *,
        content_type: str = "text/html",
        final_url: str | None = None,
        used_render_fallback: bool = False,
    ) -> "AcquiredDocument":
        parser = _VisibleTextExtractor()
        parser.feed(str(html or ""))
        parser.close()
        return cls(
            url=str(url or "").strip(),
            final_url=str(final_url or url or "").strip(),
            content_type=str(content_type or ""),
            title=parser.title,
            text=parser.text,
            raw_html=str(html or ""),
            used_render_fallback=used_render_fallback,
        )
