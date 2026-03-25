"""Optional Meilisearch adapter.

This is an accelerator path, not a required boundary.
"""

from __future__ import annotations


class MeilisearchEvidenceAdapter:
    def __init__(self, url: str, api_key: str = ""):
        self.url = str(url or "").strip()
        self.api_key = str(api_key or "").strip()

    def enabled(self) -> bool:
        return bool(self.url)

    def add(self, records):
        raise RuntimeError("Meilisearch adapter not configured in the native runtime")

    def search(self, query: str, limit: int = 10):
        raise RuntimeError("Meilisearch adapter not configured in the native runtime")
