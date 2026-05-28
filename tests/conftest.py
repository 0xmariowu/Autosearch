"""Pytest fixtures shared across the whole test tree."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_channel_runtime():
    """Drop the cached `ChannelRuntime` before AND after every test so each
    test sees a fresh build that respects its own monkeypatches/env."""
    from autosearch.core.channel_runtime import reset_channel_runtime

    reset_channel_runtime()
    yield
    reset_channel_runtime()


@pytest.fixture(autouse=True)
def _reset_structlog():
    # autosearch/cli/main.py and autosearch/mcp/cli.py call
    # structlog.configure(WriteLoggerFactory(file=sys.stderr)) on entry.
    # Under pytest, sys.stderr is a per-test capture file that gets closed
    # at teardown. Without a reset, a later test logging through structlog
    # (e.g. Clarifier) writes to the closed file and raises ValueError.
    import structlog

    structlog.reset_defaults()
    yield
    structlog.reset_defaults()
