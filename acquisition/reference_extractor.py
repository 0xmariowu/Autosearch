"""Extract lightweight references from acquired documents."""

from __future__ import annotations

import re
from urllib.parse import urljoin


_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)


def extract_references(
    base_url: str, raw_html: str, *, limit: int = 20
) -> list[dict[str, str]]:
    seen: set[str] = set()
    refs: list[dict[str, str]] = []
    for match in _HREF_RE.finditer(str(raw_html or "")):
        href = str(match.group(1) or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        refs.append({"url": absolute})
        if len(refs) >= limit:
            break
    return refs
