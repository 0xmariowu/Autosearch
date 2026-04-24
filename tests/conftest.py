"""Pytest fixtures shared across the whole test tree.

Currently only resets the singleton ChannelRuntime between tests so a test
that monkeypatches `_build_channels` / channel sources doesn't get a stale
cached runtime built by an earlier test.
"""

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
