"""Chinese-native channel selection regressions."""

from __future__ import annotations

import pytest

from autosearch.core.channel_select import select_channels

CHINESE_UGC_CHANNELS = {
    "xiaohongshu",
    "zhihu",
    "weibo",
    "tieba",
    "bilibili",
    "douyin",
    "xueqiu",
}
ACADEMIC_CHANNELS = {"arxiv", "pubmed", "openalex", "crossref", "dblp"}


@pytest.mark.parametrize(
    "query",
    [
        "研究国内用户对 Cursor 的真实体验和吐槽",
        "Cursor 用户口碑分享",
        "国内 AI 编辑器评测",
        "Cursor 吐槽",
        "财经讨论 比亚迪股价",
    ],
)
def test_cjk_ugc_queries_keep_chinese_ugc_channels(query: str) -> None:
    result = select_channels(
        query,
        channel_priority=["arxiv", "pubmed", "openalex", "crossref", "dblp"],
        mode="fast",
    )
    selected = set(result["channels"])
    chinese_selected = selected & CHINESE_UGC_CHANNELS
    academic_selected = selected & ACADEMIC_CHANNELS

    assert len(chinese_selected) >= 2
    assert len(academic_selected) < len(chinese_selected)
