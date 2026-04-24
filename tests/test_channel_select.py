"""Tests for autosearch.core.channel_select."""

from __future__ import annotations

from autosearch.core.channel_select import select_channels


def test_chinese_query_selects_chinese_ugc():
    result = select_channels("小红书上有没有人用 Cursor")
    assert "chinese-ugc" in result["groups"]
    assert any(ch in result["channels"] for ch in ["xiaohongshu", "bilibili", "zhihu"])


def test_academic_query_selects_arxiv_group():
    result = select_channels("recent arxiv papers on LLM reasoning benchmark")
    assert "academic" in result["groups"]
    assert "arxiv" in result["channels"]


def test_channel_priority_appears_first():
    result = select_channels("test query", channel_priority=["stackoverflow", "hackernews"])
    assert result["channels"][0] == "stackoverflow"
    assert result["channels"][1] == "hackernews"


def test_channel_skip_removes_channels():
    result = select_channels("general search query", channel_skip=["ddgs", "exa"])
    assert "ddgs" not in result["channels"]
    assert "exa" not in result["channels"]


def test_fast_mode_returns_five_or_fewer():
    result = select_channels("comprehensive research on everything", mode="fast")
    assert len(result["channels"]) <= 5


def test_deep_mode_returns_up_to_eight():
    result = select_channels(
        "deep research across multiple platforms bilibili arxiv github", mode="deep"
    )
    assert len(result["channels"]) <= 8
