from __future__ import annotations

from autosearch.core.channel_select import select_channels


def test_linux_do_query_selects_discourse_forum() -> None:
    result = select_channels("Linux DO 上关于 Claude Code 的讨论多吗")

    assert "chinese-ugc" in result["groups"]
    assert "discourse_forum" in result["channels"]
