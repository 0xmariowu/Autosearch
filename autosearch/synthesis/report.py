"""Legacy report synthesizer shell — gutted under v2 wave 3 W3.3 PR D.

The M7 section-writing + outline synthesis logic was deleted in v2 wave 3.
Runtime AI now synthesizes reports directly from the Evidence the v2 trio
(``list_skills`` + ``run_clarify`` + ``run_channel``) returns.

This module is kept only so legacy callers that still ``from
autosearch.synthesis.report import ReportSynthesizer`` can import without
crashing. ``ReportSynthesizer.synthesize()`` raises
:class:`NotImplementedError`.

See ``docs/migration/legacy-research-to-tool-supplier.md``.
"""

from __future__ import annotations

from typing import Any

_DEPRECATION_MESSAGE = (
    "ReportSynthesizer is removed in v2 wave 3 (PR D). "
    "The runtime AI synthesizes reports directly from Evidence returned by "
    "list_skills + run_clarify + run_channel. See "
    "docs/migration/legacy-research-to-tool-supplier.md."
)


class ReportSynthesizer:
    """Stub ReportSynthesizer kept for legacy import compatibility."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ARG002
        """Accept any legacy init signature; do nothing."""

    async def synthesize(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        """Raise :class:`NotImplementedError` pointing at the trio."""
        raise NotImplementedError(_DEPRECATION_MESSAGE)


__all__ = ["ReportSynthesizer"]
