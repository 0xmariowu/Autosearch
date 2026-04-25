"""Contracts from autosearch:channel-selection meta skill."""

from __future__ import annotations

from autosearch.core.channel_select import select_channels


def test_cjk_ugc_intent_enforces_chinese_native_guard() -> None:
    result = select_channels(
        "研究国内用户对 Cursor 的真实体验和吐槽",
        channel_priority=["arxiv", "pubmed", "openalex", "crossref", "dblp"],
        mode="fast",
    )
    chinese_native_channels = {
        "xiaohongshu",
        "zhihu",
        "weibo",
        "tieba",
        "bilibili",
        "douyin",
        "kr36",
        "infoq_cn",
        "v2ex",
        "sogou_weixin",
    }

    assert len([ch for ch in result["channels"] if ch in chinese_native_channels]) >= 2
