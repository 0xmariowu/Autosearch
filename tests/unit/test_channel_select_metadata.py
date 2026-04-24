from __future__ import annotations

from autosearch.core import channel_select
from autosearch.core.channel_select import ChannelRouteSpec, select_channels


def test_selector_prefers_channel_alias_match_within_metadata_domain() -> None:
    result = select_channels("小红书上有没有人用 Cursor")

    assert "chinese-ugc" in result["groups"]
    assert result["channels"][0] == "xiaohongshu"


def test_selector_uses_metadata_catalog_for_domain_membership(monkeypatch) -> None:
    monkeypatch.setattr(
        channel_select,
        "_load_channel_route_catalog",
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


def test_selector_mixes_domains_from_metadata_catalog() -> None:
    result = select_channels("deep research across bilibili arxiv github", mode="deep")

    assert "chinese-ugc" in result["groups"]
    assert "academic" in result["groups"]
    assert "code-package" in result["groups"]
    assert "bilibili" in result["channels"]
    assert "arxiv" in result["channels"]
    assert "github" in result["channels"]
