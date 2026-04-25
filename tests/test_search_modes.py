"""Tests for autosearch.core.search_modes."""

from __future__ import annotations

import pytest

from autosearch.core import search_modes


@pytest.fixture(autouse=True)
def no_custom_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_modes, "_load_custom_modes", lambda: [])


@pytest.mark.parametrize(
    ("query", "expected_mode"),
    [
        ("研究国内用户对 Cursor 的真实体验和吐槽", "chinese_ugc"),
        ("Cursor 用户口碑分享", "chinese_ugc"),
        ("国内 AI 编辑器评测", "chinese_ugc"),
        ("transformer attention paper 2024", "academic"),
        ("Cursor 吐槽", "chinese_ugc"),
        ("BERT 综述", "academic"),
        ("openai 最新政策", "news"),
        ("python async pattern", "developer"),
        ("cursor 公司信息", "product"),
        ("财经讨论 比亚迪股价", "chinese_ugc"),
    ],
)
def test_detect_mode_regressions(query: str, expected_mode: str) -> None:
    mode = search_modes.detect_mode(query)

    assert mode is not None
    assert mode.key == expected_mode
