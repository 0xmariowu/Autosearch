"""Local evidence index package."""

from .index import LocalEvidenceIndex
from .query import search_evidence

__all__ = [
    "LocalEvidenceIndex",
    "search_evidence",
]
