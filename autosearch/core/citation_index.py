"""Citation index — cross-channel citation deduplication.

In-memory, per server process (lost on restart — intentional).
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid

from autosearch.core.redact import redact_signed_url


_TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
}
_ARXIV_ABS_VERSION_RE = re.compile(r"^(/abs/.+?)v\d+$")


def _canonicalize_url(url: str) -> str:
    """Return a dedupe-only canonical URL while preserving display URLs elsewhere."""
    parsed = urlsplit(url)

    netloc = parsed.netloc
    if parsed.hostname:
        host_start = netloc.lower().rfind(parsed.hostname.lower())
        if host_start >= 0:
            netloc = (
                netloc[:host_start]
                + netloc[host_start : host_start + len(parsed.hostname)].lower()
                + netloc[host_start + len(parsed.hostname) :]
            )

    path = re.sub(r"/{2,}", "/", parsed.path)
    if path != "/":
        path = path.rstrip("/")
    if parsed.hostname and parsed.hostname.lower() == "arxiv.org":
        path = _ARXIV_ABS_VERSION_RE.sub(r"\1", path)

    query_items = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_query_param(name)
    ]
    query = urlencode(query_items, doseq=True)

    return urlunsplit((parsed.scheme, netloc, path, query, ""))


def _is_tracking_query_param(name: str) -> bool:
    normalized = name.lower()
    return normalized.startswith("utm_") or normalized in _TRACKING_QUERY_PARAMS


class CitationIndex:
    """Tracks URLs with sequential citation numbers."""

    def __init__(self, index_id: str) -> None:
        self.index_id = index_id
        self._url_to_num: dict[str, int] = {}
        self._entries: list[dict] = []  # [{num, url, title, source}]
        self._next_num: int = 1


# Module-level storage — in-memory, lost on server restart (intentional)
_CITATION_INDEXES: dict[str, CitationIndex] = {}


def create_index() -> str:
    """Create a new citation index and return its index_id."""
    index_id = str(uuid.uuid4())
    _CITATION_INDEXES[index_id] = CitationIndex(index_id)
    return index_id


def add_citation(index_id: str, url: str, title: str = "", source: str = "") -> int:
    """Add URL to index (idempotent — same URL returns same number).

    Returns the citation number assigned to the URL.
    """
    idx = _CITATION_INDEXES[index_id]
    canonical_url = _canonicalize_url(url)
    if canonical_url in idx._url_to_num:
        return idx._url_to_num[canonical_url]
    num = idx._next_num
    idx._next_num += 1
    idx._url_to_num[canonical_url] = num
    idx._entries.append({"num": num, "url": url, "title": title, "source": source})
    return num


def export_citations(index_id: str, *, raw_urls: bool = False) -> str:
    """Export citation index as a Markdown reference list.

    Format: [N] title — source (url)
    """
    idx = _CITATION_INDEXES[index_id]
    lines: list[str] = []
    for entry in sorted(idx._entries, key=lambda e: e["num"]):
        num = entry["num"]
        url = entry["url"]
        if not raw_urls:
            url = redact_signed_url(url)
        title = entry["title"] or url
        source = entry["source"]
        if source:
            lines.append(f"[{num}] {title} — {source} ({url})")
        else:
            lines.append(f"[{num}] {title} ({url})")
    return "\n".join(lines)


def merge_index(target_id: str, source_id: str) -> dict:
    """Merge source citation index into target.

    URLs already in target are skipped (counted as skipped_duplicates).
    New entries from source are re-numbered in target sequence.

    Returns {merged_count, skipped_duplicates}.
    """
    target = _CITATION_INDEXES[target_id]
    source = _CITATION_INDEXES[source_id]
    merged = 0
    skipped = 0
    for entry in source._entries:
        url = entry["url"]
        if _canonicalize_url(url) in target._url_to_num:
            skipped += 1
        else:
            add_citation(target_id, url, title=entry["title"], source=entry["source"])
            merged += 1
    return {"merged_count": merged, "skipped_duplicates": skipped}
