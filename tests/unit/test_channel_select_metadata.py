from __future__ import annotations

import pytest

from autosearch.core import channel_select
from autosearch.core.channel_select import ChannelRouteSpec, select_channels


@pytest.fixture(autouse=True)
def clear_channel_catalog_cache() -> None:
    cache_clear = getattr(channel_select.load_channel_route_catalog, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
    yield
    cache_clear = getattr(channel_select.load_channel_route_catalog, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def test_selector_prefers_channel_alias_match_within_metadata_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        channel_select,
        "load_channel_route_catalog",
        lambda: (
            ChannelRouteSpec(
                name="xiaohongshu",
                domains=("chinese-ugc",),
                scenarios=("community",),
                query_types=("developer",),
                query_languages=("zh", "mixed"),
                aliases=("小红书", "xhs", "rednote"),
                keywords=("社区", "种草"),
            ),
        ),
    )

    result = select_channels("小红书上有没有人用 Cursor")

    assert "chinese-ugc" in result["groups"]
    assert result["channels"][0] == "xiaohongshu"


def test_selector_uses_metadata_catalog_for_domain_membership(monkeypatch) -> None:
    monkeypatch.setattr(
        channel_select,
        "load_channel_route_catalog",
        lambda: (
            ChannelRouteSpec(
                name="custom_paper",
                domains=("academic",),
                scenarios=("benchmark",),
                query_types=("paper-review",),
                query_languages=("en",),
                aliases=("custom paper",),
                keywords=("benchmark", "paper", "review"),
            ),
        ),
    )

    result = select_channels("recent paper benchmark")

    assert result["groups"] == ["academic"]
    assert result["channels"] == ["custom_paper"]


def test_selector_mixes_domains_from_metadata_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        channel_select,
        "load_channel_route_catalog",
        lambda: (
            ChannelRouteSpec(
                name="bilibili",
                domains=("chinese-ugc",),
                scenarios=("video",),
                query_types=("community",),
                query_languages=("zh", "mixed"),
                aliases=("bilibili", "b站"),
                keywords=("视频",),
            ),
            ChannelRouteSpec(
                name="arxiv",
                domains=("academic",),
                scenarios=("paper-search",),
                query_types=("paper-review",),
                query_languages=("en", "mixed"),
                aliases=("arxiv",),
                keywords=("paper", "papers"),
            ),
            ChannelRouteSpec(
                name="github",
                domains=("code-package",),
                scenarios=("repo",),
                query_types=("developer",),
                query_languages=("en", "mixed"),
                aliases=("github",),
                keywords=("repo", "repository"),
            ),
        ),
    )

    result = select_channels("deep research across bilibili arxiv github", mode="deep")

    assert "chinese-ugc" in result["groups"]
    assert "academic" in result["groups"]
    assert "code-package" in result["groups"]
    assert "bilibili" in result["channels"]
    assert "arxiv" in result["channels"]
    assert "github" in result["channels"]


def test_selector_does_not_promote_phrase_fragment_as_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        channel_select,
        "load_channel_route_catalog",
        lambda: (
            ChannelRouteSpec(
                name="discourse_forum",
                domains=("chinese-ugc",),
                scenarios=("public-forum",),
                query_types=("community",),
                query_languages=("zh", "mixed"),
                aliases=("linux do", "linuxdo", "discourse"),
                keywords=("linux do", "linuxdo", "discourse"),
            ),
        ),
    )

    result = select_channels("linux kernel module bug")

    assert "discourse_forum" not in result["channels"]
