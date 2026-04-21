"""Legacy pipeline shell — gutted under v2 wave 3 W3.3 PR D.

The full AutoSearch pipeline (clarify → decompose → channel fan-out → m3
compaction → m7 synthesis) was deleted in v2 wave 3. Runtime AI now drives
research directly via the tool-supplier trio:

- `list_skills` — discover autosearch skills (channels / tools / meta / router)
- `run_clarify` — structured clarification envelope + rubrics
- `run_channel` — raw evidence from a single channel

See `docs/migration/legacy-research-to-tool-supplier.md`.

This module is kept only to:

- satisfy `from autosearch.core.pipeline import Pipeline, PipelineResult,
  PipelineEvent` imports in legacy callers (mcp/server.py, cli/main.py,
  server/main.py) until PR E deletes those call sites too.
- keep `Pipeline.run()` callable but raise `NotImplementedError` pointing at
  the migration guide.
- preserve the `PipelineEvent` dataclass (kept as a simple passthrough).

Legacy opt-in env var `AUTOSEARCH_LEGACY_RESEARCH=1` still exists on the MCP
tool, but the legacy path now raises immediately — previously it ran a real
pipeline; now the only meaningful behavior is the deprecation envelope built
by the MCP tool BEFORE reaching this class.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from autosearch.core.models import PipelineResult
from autosearch.core.search_scope import SearchScope

_TRUTHY_ENV = frozenset({"1", "true", "yes", "on"})


def _bypass_clarify_enabled() -> bool:
    """Return True if the user opted into auto-bypassing the Clarifier.

    Checks the ``AUTOSEARCH_BYPASS_CLARIFY`` env var. Kept here for legacy
    callers; under v2 the runtime AI drives clarification explicitly via
    ``run_clarify``, so this helper is effectively dead but preserved for
    backward-compat tests and any third-party integration code.
    """
    value = os.environ.get("AUTOSEARCH_BYPASS_CLARIFY", "").strip().lower()
    return value in _TRUTHY_ENV


_DEPRECATION_MESSAGE = (
    "Pipeline is removed in v2 wave 3 (PR D). "
    "Use list_skills + run_clarify + run_channel MCP tools and let the runtime "
    "AI synthesize. See docs/migration/legacy-research-to-tool-supplier.md."
)


@dataclass
class PipelineEvent:
    """Retained for import-compatibility with legacy callers.

    Under v2, no pipeline runs and no events are emitted; this class is kept
    only so stale callers don't crash at import time.
    """

    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Stub Pipeline retained for legacy import compatibility.

    ``run()`` raises :class:`NotImplementedError` pointing at the
    tool-supplier trio. All constructor arguments are accepted and ignored
    so any code that still calls ``Pipeline(llm=..., channels=...)`` can
    import + construct without crashing.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ARG002
        """Accept any legacy init signature; store nothing."""

    async def run(
        self,
        query: str,  # noqa: ARG002 — accepted for signature parity only
        *,
        mode_hint: Any = None,  # noqa: ARG002
        scope: SearchScope | None = None,  # noqa: ARG002
        **_kwargs: Any,
    ) -> PipelineResult:
        """Raise :class:`NotImplementedError` pointing at the tool-supplier trio."""
        raise NotImplementedError(_DEPRECATION_MESSAGE)


__all__ = ["Pipeline", "PipelineEvent", "PipelineResult"]
