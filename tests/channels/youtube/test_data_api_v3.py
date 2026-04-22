"""G2-T8: Tests for youtube channel data_api_v3 method."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/youtube/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("yt_search", _SKILL_DIR / "data_api_v3.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="MLX Apple Silicon tutorial", rationale="test")


_YT_RESPONSE = {
    "items": [
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "MLX Tutorial for Apple Silicon",
                "description": "Learn to run LLMs on Apple Silicon with MLX.",
                "channelTitle": "MLX Channel",
                "publishedAt": "2024-03-01T00:00:00Z",
            },
        }
    ]
}


@pytest.mark.asyncio()
async def test_search_skips_when_no_api_key(search, subquery):
    """Without YOUTUBE_API_KEY the channel raises MethodUnavailable or returns empty."""
    from autosearch.channels.base import MethodUnavailable

    with patch.dict(os.environ, {}, clear=False):
        env_backup = os.environ.pop("YOUTUBE_API_KEY", None)
        try:
            try:
                results = await search(subquery)
                assert results == []
            except MethodUnavailable:
                pass  # also acceptable
        finally:
            if env_backup is not None:
                os.environ["YOUTUBE_API_KEY"] = env_backup


@pytest.mark.asyncio()
async def test_search_returns_evidence_with_key(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = _YT_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake_key"}),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp),
    ):
        results = await search(subquery)

    assert len(results) >= 1
    assert results[0].source_channel == "youtube"
    assert "youtube.com" in results[0].url or "youtu.be" in results[0].url
