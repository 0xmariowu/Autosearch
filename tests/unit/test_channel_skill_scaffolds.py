# Self-written, plan autosearch-0418-channels-and-skills.md § F002c
from pathlib import Path

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.skills.loader import load_all


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "channels"


def _load_specs():
    return load_all(_channels_root())


def test_all_11_channels_loadable() -> None:
    specs = _load_specs()

    assert len(specs) == 11
    assert [spec.name for spec in specs] == [
        "arxiv",
        "bilibili",
        "ddgs",
        "douyin",
        "github",
        "hackernews",
        "twitter",
        "weibo",
        "xiaohongshu",
        "youtube",
        "zhihu",
    ]


def test_channels_have_required_frontmatter_fields() -> None:
    for spec in _load_specs():
        assert spec.name
        assert spec.description
        assert spec.languages
        assert spec.methods
        assert spec.when_to_use is not None
        assert spec.when_to_use.query_languages
        assert spec.when_to_use.query_types
        assert spec.quality_hint is not None


def test_fallback_chain_matches_methods() -> None:
    for spec in _load_specs():
        method_ids = {method.id for method in spec.methods}

        assert spec.fallback_chain
        assert set(spec.fallback_chain).issubset(method_ids)


def test_chinese_native_channels_cover_5() -> None:
    chinese_native = {
        spec.name
        for spec in _load_specs()
        if spec.quality_hint is not None and spec.quality_hint.chinese_native
    }

    assert chinese_native == {
        "bilibili",
        "douyin",
        "weibo",
        "xiaohongshu",
        "zhihu",
    }
    assert len(chinese_native) == 5


def test_shipped_method_impls_exist_for_registry_channels() -> None:
    expected_impls = {
        "arxiv": ["methods/api_search.py"],
        "ddgs": ["methods/api.py"],
        "hackernews": ["methods/algolia.py"],
        "youtube": ["methods/data_api_v3.py"],
    }

    for spec in _load_specs():
        expected = expected_impls.get(spec.name, [])
        for method in spec.methods:
            exists = (spec.skill_dir / method.impl).exists()
            assert exists is (method.impl in expected)


def test_compile_from_skills_marks_shipped_channels_available_without_keys() -> None:
    registry = ChannelRegistry.compile_from_skills(_channels_root(), Environment())

    assert [channel.name for channel in registry.available()] == [
        "arxiv",
        "ddgs",
        "hackernews",
    ]
    for spec in _load_specs():
        metadata = registry.metadata(spec.name)
        expected_impls = {
            "arxiv": "methods/api_search.py",
            "ddgs": "methods/api.py",
            "hackernews": "methods/algolia.py",
        }
        if spec.name in expected_impls:
            assert len(metadata.methods) == 1
            assert metadata.methods[0].available is True
            assert metadata.methods[0].unmet_requires == []
            continue
        if spec.name == "youtube":
            assert len(metadata.methods) == 1
            assert metadata.methods[0].available is False
            assert metadata.methods[0].unmet_requires == ["env:YOUTUBE_API_KEY"]
            continue

        assert metadata.available_methods() == []
        assert len(metadata.methods) == len(spec.methods)
        assert all(method.available is False for method in metadata.methods)
        assert all(method.unmet_requires == ["impl_missing"] for method in metadata.methods)
