"""Smoke tests for all 32 search channels.

Each channel is called with a simple query and verified to return
a valid list[dict] with the required keys. These tests hit real
network endpoints and should be run with: pytest -m network
"""

from __future__ import annotations

from pathlib import Path

import pytest

from channels import load_channels

CHANNELS_DIR = Path(__file__).resolve().parents[1] / "channels"
REQUIRED_KEYS = {"url", "title", "snippet", "source", "query", "metadata"}


def _channel_names() -> list[str]:
    names = []
    for entry in sorted(CHANNELS_DIR.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if entry.name == "__pycache__" or entry.name.startswith("_"):
            continue
        if not (entry / "search.py").is_file():
            continue
        names.append(entry.name)
    return names


ALL_CHANNELS = _channel_names()


@pytest.mark.network
@pytest.mark.parametrize("channel_name", ALL_CHANNELS)
async def test_channel_returns_valid_results(channel_name: str) -> None:
    channels = load_channels()
    assert channel_name in channels, f"Channel {channel_name!r} not loaded"

    results = await channels[channel_name]("test", 3)

    assert isinstance(results, list), (
        f"{channel_name} returned {type(results)}, expected list"
    )

    for i, result in enumerate(results):
        assert isinstance(result, dict), (
            f"{channel_name} result[{i}] is {type(result)}, expected dict"
        )
        missing = REQUIRED_KEYS - set(result.keys())
        assert not missing, f"{channel_name} result[{i}] missing keys: {missing}"
        assert isinstance(result["metadata"], dict), (
            f"{channel_name} result[{i}] metadata is {type(result['metadata'])}, expected dict"
        )


@pytest.mark.network
@pytest.mark.parametrize("channel_name", ALL_CHANNELS)
async def test_channel_does_not_raise(channel_name: str) -> None:
    channels = load_channels()
    if channel_name not in channels:
        pytest.skip(f"Channel {channel_name!r} not loaded")

    # Should not raise — errors return [] per STANDARD.md §3
    results = await channels[channel_name]("python asyncio tutorial", 2)
    assert isinstance(results, list)
