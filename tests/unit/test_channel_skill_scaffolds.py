# Self-written, plan autosearch-0418-channels-and-skills.md § F002c
from pathlib import Path

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.skills.loader import load_all


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "autosearch" / "skills" / "channels"


def _load_specs():
    return load_all(_channels_root())


def test_all_channels_loadable() -> None:
    specs = _load_specs()

    assert len(specs) >= 37
    assert [spec.name for spec in specs] == [
        "arxiv",
        "bilibili",
        "crossref",
        "dblp",
        "ddgs",
        "devto",
        "discourse_forum",
        "dockerhub",
        "douyin",
        "github",
        "google_news",
        "hackernews",
        "huggingface_hub",
        "infoq_cn",
        "instagram",
        "kr36",
        "kuaishou",
        "linkedin",
        "openalex",
        "package_search",
        "papers",
        "podcast_cn",
        "pubmed",
        "reddit",
        "searxng",
        "sec_edgar",
        "sogou_weixin",
        "stackoverflow",
        "tieba",
        "tiktok",
        "twitter",
        "v2ex",
        "wechat_channels",
        "weibo",
        "wikidata",
        "wikipedia",
        "xiaohongshu",
        "xueqiu",
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


def test_chinese_native_channels_cover_expected_set() -> None:
    chinese_native = {
        spec.name
        for spec in _load_specs()
        if spec.quality_hint is not None and spec.quality_hint.chinese_native
    }

    assert chinese_native == {
        "bilibili",
        "discourse_forum",
        "douyin",
        "infoq_cn",
        "kuaishou",
        "kr36",
        "podcast_cn",
        "sogou_weixin",
        "tieba",
        "v2ex",
        "weibo",
        "xiaohongshu",
        "xueqiu",
        "zhihu",
    }
    assert len(chinese_native) == 14


def test_shipped_method_impls_exist_for_registry_channels() -> None:
    expected_impls = {
        "arxiv": ["methods/api_search.py"],
        "bilibili": ["methods/api_search.py", "methods/via_tikhub.py"],
        "instagram": ["methods/via_tikhub.py"],
        "wechat_channels": ["methods/via_tikhub.py"],
        "crossref": ["methods/api_search.py"],
        "dblp": ["methods/api_search.py"],
        "ddgs": ["methods/api.py"],
        "devto": ["methods/api_search.py"],
        "discourse_forum": ["methods/api_search.py"],
        "dockerhub": ["methods/api_search.py"],
        "douyin": ["methods/via_tikhub.py"],
        "github": ["methods/search_public_repos.py"],
        "google_news": ["methods/api_search.py"],
        "hackernews": ["methods/algolia.py"],
        "huggingface_hub": ["methods/api_search.py"],
        "infoq_cn": ["methods/api_search.py"],
        "kuaishou": ["methods/via_tikhub.py"],
        "kr36": ["methods/api_search.py"],
        "openalex": ["methods/api_search.py"],
        "package_search": ["methods/api_search.py"],
        "podcast_cn": ["methods/api_search.py"],
        "papers": ["methods/via_paper_search.py"],
        "pubmed": ["methods/api_search.py"],
        "reddit": ["methods/api_search.py"],
        "searxng": ["methods/api_search.py"],
        "sec_edgar": ["methods/api_search.py"],
        "sogou_weixin": ["methods/api_search.py"],
        "stackoverflow": ["methods/api_search.py"],
        "tieba": ["methods/api_search.py"],
        "tiktok": ["methods/via_tikhub.py"],
        "twitter": ["methods/via_tikhub.py"],
        "v2ex": ["methods/api_search.py"],
        "weibo": ["methods/via_tikhub.py"],
        "wikidata": ["methods/api_search.py"],
        "wikipedia": ["methods/api_search.py"],
        "xiaohongshu": ["methods/via_tikhub.py", "methods/via_signsrv.py"],
        "xueqiu": ["methods/api_search.py"],
        "zhihu": ["methods/via_tikhub.py"],
        "youtube": ["methods/data_api_v3.py"],
        "linkedin": ["methods/via_jina.py"],
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
        "bilibili",
        "crossref",
        "dblp",
        "ddgs",
        "devto",
        "discourse_forum",
        "dockerhub",
        "github",
        "google_news",
        "hackernews",
        "huggingface_hub",
        "infoq_cn",
        "kr36",
        "linkedin",
        "openalex",
        "package_search",
        "papers",
        "podcast_cn",
        "pubmed",
        "reddit",
        "sec_edgar",
        "sogou_weixin",
        "stackoverflow",
        "tieba",
        "v2ex",
        "wikidata",
        "wikipedia",
    ]
    for spec in _load_specs():
        metadata = registry.metadata(spec.name)
        expected_impls = {
            "arxiv": "methods/api_search.py",
            "crossref": "methods/api_search.py",
            "dblp": "methods/api_search.py",
            "ddgs": "methods/api.py",
            "devto": "methods/api_search.py",
            "discourse_forum": "methods/api_search.py",
            "dockerhub": "methods/api_search.py",
            "google_news": "methods/api_search.py",
            "hackernews": "methods/algolia.py",
            "huggingface_hub": "methods/api_search.py",
            "infoq_cn": "methods/api_search.py",
            "kr36": "methods/api_search.py",
            "openalex": "methods/api_search.py",
            "package_search": "methods/api_search.py",
            "podcast_cn": "methods/api_search.py",
            "papers": "methods/via_paper_search.py",
            "pubmed": "methods/api_search.py",
            "reddit": "methods/api_search.py",
            "sec_edgar": "methods/api_search.py",
            "sogou_weixin": "methods/api_search.py",
            "stackoverflow": "methods/api_search.py",
            "tieba": "methods/api_search.py",
            "v2ex": "methods/api_search.py",
            "wikidata": "methods/api_search.py",
            "wikipedia": "methods/api_search.py",
        }
        if spec.name == "github":
            methods = {method.id: method for method in metadata.methods}

            # Only the no-token public-repo search ships with an impl. The
            # token-gated search_repositories/issues/code declarations were
            # removed because their impl files never existed (see plan §P0-2).
            assert [method.id for method in metadata.available_methods()] == ["search_public_repos"]
            assert methods["search_public_repos"].available is True
            assert methods["search_public_repos"].unmet_requires == []
            assert set(methods.keys()) == {"search_public_repos"}
            continue
        if spec.name == "devto":
            assert len(metadata.methods) == 1
            assert metadata.methods[0].available is True
            assert metadata.methods[0].unmet_requires == []
            continue
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
        if spec.name == "searxng":
            assert len(metadata.methods) == 1
            assert metadata.methods[0].available is False
            assert metadata.methods[0].unmet_requires == ["env:SEARXNG_URL"]
            continue
        if spec.name == "zhihu":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            assert set(methods.keys()) == {"via_tikhub"}
            continue
        if spec.name == "xiaohongshu":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_signsrv"].available is False
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            assert set(methods.keys()) == {"via_signsrv", "via_tikhub"}
            continue
        if spec.name == "twitter":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            assert set(methods.keys()) == {"via_tikhub"}
            continue
        if spec.name == "tiktok":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            continue
        if spec.name == "weibo":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            continue
        if spec.name == "kuaishou":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            continue
        if spec.name == "douyin":
            methods = {method.id: method for method in metadata.methods}

            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            for other_id, method in methods.items():
                if other_id != "via_tikhub":
                    assert method.available is False
                    assert method.unmet_requires == ["impl_missing"]
            continue
        if spec.name == "bilibili":
            methods = {method.id: method for method in metadata.methods}

            # api_search (direct WBI, no key needed) is now the primary free method
            available = metadata.available_methods()
            assert len(available) == 1
            assert available[0].id == "api_search"
            assert methods["api_search"].available is True
            assert methods["api_search"].unmet_requires == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            continue

        if spec.name in ("instagram", "wechat_channels"):
            methods = {method.id: method for method in metadata.methods}
            assert metadata.available_methods() == []
            assert methods["via_tikhub"].available is False
            assert methods["via_tikhub"].unmet_requires == ["env:TIKHUB_API_KEY"]
            continue

        if spec.name == "linkedin":
            available = metadata.available_methods()
            assert len(available) == 1
            assert available[0].id == "via_jina"
            assert available[0].available is True
            continue

        if spec.name == "xueqiu":
            methods = {method.id: method for method in metadata.methods}
            assert metadata.available_methods() == []
            assert methods["api_search"].available is False
            assert methods["api_search"].unmet_requires == ["env:XUEQIU_COOKIES"]
            continue

        assert metadata.available_methods() == []
        assert len(metadata.methods) == len(spec.methods)
        assert all(method.available is False for method in metadata.methods)
        assert all(method.unmet_requires == ["impl_missing"] for method in metadata.methods)


def test_xiaohongshu_signsrv_available_with_login_cookie_secret_names() -> None:
    env = Environment(
        env_keys={
            "AUTOSEARCH_SIGNSRV_URL",
            "AUTOSEARCH_SERVICE_TOKEN",
            "XHS_COOKIES",
        }
    )
    registry = ChannelRegistry.compile_from_skills(_channels_root(), env)
    methods = {method.id: method for method in registry.metadata("xiaohongshu").methods}

    assert methods["via_signsrv"].available is True
    assert methods["via_signsrv"].unmet_requires == []


def test_xiaohongshu_signsrv_unavailable_without_login_cookie_secret() -> None:
    env = Environment(
        env_keys={
            "AUTOSEARCH_SIGNSRV_URL",
            "AUTOSEARCH_SERVICE_TOKEN",
        }
    )
    registry = ChannelRegistry.compile_from_skills(_channels_root(), env)
    methods = {method.id: method for method in registry.metadata("xiaohongshu").methods}

    assert methods["via_signsrv"].available is False
    assert methods["via_signsrv"].unmet_requires == ["env:XHS_COOKIES"]
