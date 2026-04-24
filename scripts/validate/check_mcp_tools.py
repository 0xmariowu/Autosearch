#!/usr/bin/env python3
"""F012 S2: Verify all expected MCP tools are registered in create_server().

Usage: python scripts/validate/check_mcp_tools.py
Exit 0 = all tools present. Exit 1 = missing tools.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("AUTOSEARCH_LLM_MODE", "dummy")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2]))

from autosearch.mcp.server import create_server  # noqa: E402

# `research` is opt-in since 2026.04.24.5 (plan §P1-4); it must NOT be in the
# default expected list and must reappear when AUTOSEARCH_LEGACY_RESEARCH=1.
EXPECTED_TOOLS = [
    "health",
    "run_clarify",
    "run_channel",
    "list_skills",
    "list_channels",
    "loop_init",
    "loop_update",
    "loop_get_gaps",
    "loop_add_gap",
    "citation_create",
    "citation_add",
    "citation_export",
    "citation_merge",
    "select_channels_tool",
    "delegate_subtask",
    "doctor",
    "trace_harvest",
    "perspective_questioning",
    "graph_search_plan",
    "recent_signal_fusion",
    "context_retention_policy",
]


def main() -> int:
    server = create_server()
    registered = {t.name for t in server._tool_manager.list_tools()}

    missing = [t for t in EXPECTED_TOOLS if t not in registered]
    extra = [t for t in registered if t not in EXPECTED_TOOLS]

    total = len(EXPECTED_TOOLS)
    found = total - len(missing)

    print(f"MCP tool check (default): {found}/{total} expected tools registered")

    if missing:
        print(f"  MISSING: {missing}")
    if extra:
        print(f"  EXTRA (not in expected list, may be ok): {extra}")

    if missing:
        print("FAIL")
        return 1

    if "research" in registered:
        print("FAIL: deprecated `research` tool registered by default (plan §P1-4)")
        return 1

    # Legacy opt-in check: with the env var set, research must come back.
    os.environ["AUTOSEARCH_LEGACY_RESEARCH"] = "1"
    try:
        from autosearch.mcp.server import create_server as _create  # noqa: PLC0415

        opt_in_tools = {t.name for t in _create()._tool_manager.list_tools()}
    finally:
        os.environ.pop("AUTOSEARCH_LEGACY_RESEARCH", None)
    if "research" not in opt_in_tools:
        print("FAIL: AUTOSEARCH_LEGACY_RESEARCH=1 did not restore `research`")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
