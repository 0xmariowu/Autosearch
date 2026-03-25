"""Render fallback for acquisition.

Current native implementation is intentionally conservative: return the same
document shape without requiring a browser runtime. This keeps the boundary in
place so a richer renderer can be added later without changing callers.
"""

from __future__ import annotations

from .document_models import AcquiredDocument


def render_document(
    url: str,
    *,
    timeout: int = 15,
) -> AcquiredDocument:
    raise RuntimeError("render fallback not configured")
