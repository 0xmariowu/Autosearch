"""Metadata-assisted channel selection for v2 tool-supplier."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from autosearch.skills.loader import SkillLoadError, load_frontmatter

_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "channels"
_MODE_LIMITS = {"fast": 5, "deep": 8}
_GENERIC_WEB_DOMAIN = "generic-web"
_CJK_PATTERN = re.compile(r"[\u3400-\u9FFF]")
_WORD_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.IGNORECASE)
_DOMAIN_ALIASES: dict[str, str] = {
    "brand": "market-product",
    "consumer": "market-product",
    "finance": "market-product",
    "infrastructure": "code-package",
    "lifestyle": "market-product",
    "medical": "academic",
    "professional": "social-career",
    "social": "social-career",
    "video": "video-audio",
}

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chinese-ugc": (
        "linux do",
        "linux.do",
        "linuxdo",
        "discourse",
        "小红书",
        "抖音",
        "b站",
        "微博",
        "知乎",
        "播客",
        "快手",
        "v2ex",
        "贴吧",
        "公众号",
        "wechat article",
        "wechat official account",
    ),
    "cn-tech": ("36kr", "csdn", "掘金", "infoq", "公众号", "juejin"),
    "academic": (
        "paper",
        "papers",
        "arxiv",
        "citation",
        "benchmark",
        "论文",
        "survey",
        "openreview",
        "semantic scholar",
        "conference",
        "ieee",
        "acm",
    ),
    "code-package": (
        "github",
        "repo",
        "repository",
        "issue",
        "npm",
        "pypi",
        "huggingface",
        "package",
        "library",
        "sdk",
        "docker image",
        "container image",
    ),
    "community-en": (
        "stackoverflow",
        "stack overflow",
        "hacker news",
        "hackernews",
        "dev.to",
        "devto",
        "reddit",
        "hn",
    ),
    "social-career": ("twitter", "linkedin", " career ", "招聘", "hiring", "job"),
    "video-audio": (
        "视频",
        "字幕",
        "转录",
        "podcast",
        "youtube",
        "video",
        "transcript",
        "音频",
    ),
    _GENERIC_WEB_DOMAIN: ("搜索", "search", "news", "网页", "google", "bing", "ddgs"),
}

_CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "bilibili": ("b站", "哔哩哔哩"),
    "discourse_forum": ("linux do", "linux.do", "linuxdo", "discourse"),
    "douyin": ("抖音",),
    "github": ("github", "git repo", "repository"),
    "google_news": ("google news", "新闻"),
    "hackernews": ("hacker news", "hackernews", "hn"),
    "infoq_cn": ("infoq",),
    "kr36": ("36kr",),
    "package_search": ("npm", "pypi", "package", "dependency"),
    "podcast_cn": ("播客", "podcast"),
    "reddit": ("reddit",),
    "sogou_weixin": ("公众号", "微信文章", "wechat article", "wechat official account"),
    "stackoverflow": ("stackoverflow", "stack overflow"),
    "tieba": ("贴吧", "百度贴吧"),
    "twitter": ("twitter", "tweet", "x "),
    "v2ex": ("v2ex",),
    "weibo": ("微博",),
    "wechat_channels": ("视频号", "微信视频号", "wechat channels"),
    "xiaohongshu": ("小红书", "xhs", "rednote"),
    "xueqiu": ("雪球",),
    "youtube": ("youtube", "视频"),
    "zhihu": ("知乎",),
}


@dataclass(frozen=True, slots=True)
class ChannelRouteSpec:
    """Routing metadata distilled from a channel skill's frontmatter."""

    name: str
    domains: tuple[str, ...]
    scenarios: tuple[str, ...]
    query_types: tuple[str, ...]
    query_languages: tuple[str, ...]
    aliases: tuple[str, ...]
    keywords: tuple[str, ...]


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _normalize_channel_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_values(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = _normalize_text(value)
            if text:
                normalized.append(text)
    return tuple(normalized)


def _normalize_domain(value: str) -> str:
    normalized = _normalize_text(value)
    return _DOMAIN_ALIASES.get(normalized, normalized)


def _keyword_variants(value: str) -> set[str]:
    """Expand a routing hint into safe match variants without oversplitting phrases."""
    normalized = _normalize_text(value.replace("-", " "))
    if not normalized:
        return set()

    variants = {normalized}
    compact = normalized.replace(" ", "")
    if compact and compact != normalized:
        variants.add(compact)

    if _CJK_PATTERN.search(normalized):
        return {variant for variant in variants if variant}

    if " " not in normalized:
        for token in _WORD_PATTERN.findall(normalized):
            if len(token) >= 3:
                variants.add(token)

    return {variant for variant in variants if len(variant) >= 3}


def _channel_aliases(name: str) -> tuple[str, ...]:
    variants = {
        _normalize_channel_name(name),
        _normalize_text(name),
        _normalize_text(name.replace("_", "")),
    }
    for alias in _CHANNEL_ALIASES.get(name, ()):
        normalized_alias = _normalize_channel_name(alias)
        if normalized_alias:
            variants.add(normalized_alias)
        variants.update(_keyword_variants(alias))

    return tuple(sorted(variant for variant in variants if variant))


def _channel_keywords(
    *,
    name: str,
    domains: tuple[str, ...],
    scenarios: tuple[str, ...],
    query_types: tuple[str, ...],
    domain_hints: tuple[str, ...],
) -> tuple[str, ...]:
    keywords: set[str] = set()
    for value in (*domains, *scenarios, *query_types, *domain_hints):
        keywords.update(_keyword_variants(value))

    # Keep the canonical channel id searchable even when no alias exists.
    keywords.update(_keyword_variants(name))
    keywords.update(_keyword_variants(name.replace("_", " ")))
    return tuple(sorted(keywords))


@lru_cache(maxsize=1)
def _load_channel_route_catalog() -> tuple[ChannelRouteSpec, ...]:
    """Build the cached routing catalog from channel `SKILL.md` metadata."""
    if not _SKILLS_ROOT.is_dir():
        return ()

    specs: list[ChannelRouteSpec] = []
    for skill_dir in sorted(path for path in _SKILLS_ROOT.iterdir() if path.is_dir()):
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.is_file():
            continue

        try:
            payload = load_frontmatter(skill_path)
        except (OSError, SkillLoadError):
            continue

        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            name = skill_dir.name
        canonical_name = _normalize_channel_name(name)

        domains = tuple(
            dict.fromkeys(
                _normalize_domain(domain) for domain in _normalize_values(payload.get("domains"))
            )
        )
        if not domains:
            continue

        scenarios = _normalize_values(payload.get("scenarios"))
        when_to_use = payload.get("when_to_use")
        query_types = ()
        query_languages = ()
        domain_hints = ()
        if isinstance(when_to_use, dict):
            query_types = _normalize_values(when_to_use.get("query_types"))
            query_languages = _normalize_values(when_to_use.get("query_languages"))
            domain_hints = _normalize_values(when_to_use.get("domain_hints"))

        specs.append(
            ChannelRouteSpec(
                name=canonical_name,
                domains=domains,
                scenarios=scenarios,
                query_types=query_types,
                query_languages=query_languages,
                aliases=_channel_aliases(canonical_name),
                keywords=_channel_keywords(
                    name=canonical_name,
                    domains=domains,
                    scenarios=scenarios,
                    query_types=query_types,
                    domain_hints=domain_hints,
                ),
            )
        )

    return tuple(sorted(specs, key=lambda spec: spec.name))


load_channel_route_catalog = _load_channel_route_catalog


def _channels_by_domain(
    catalog: tuple[ChannelRouteSpec, ...],
) -> dict[str, tuple[ChannelRouteSpec, ...]]:
    mapping: dict[str, list[ChannelRouteSpec]] = defaultdict(list)
    for spec in catalog:
        for domain in spec.domains:
            mapping[domain].append(spec)

    return {
        domain: tuple(sorted(specs, key=lambda spec: spec.name))
        for domain, specs in mapping.items()
    }


def _has_cjk(value: str) -> bool:
    return bool(_CJK_PATTERN.search(value))


def _query_tokens(query_lower: str) -> set[str]:
    return set(_WORD_PATTERN.findall(query_lower))


def _matches_query(term: str, query_lower: str, query_tokens: set[str]) -> bool:
    """Match short aliases on token boundaries and longer terms by substring."""
    if len(term) < 3 and term.isascii():
        return term in query_tokens
    return term in query_lower


def _channel_match_score(
    spec: ChannelRouteSpec,
    query_lower: str,
    query_tokens: set[str],
) -> int:
    alias_score = sum(
        3 for alias in spec.aliases if alias and _matches_query(alias, query_lower, query_tokens)
    )
    keyword_score = sum(
        1
        for keyword in spec.keywords
        if keyword
        and keyword not in spec.aliases
        and _matches_query(keyword, query_lower, query_tokens)
    )
    return alias_score + keyword_score


def _language_affinity(spec: ChannelRouteSpec, *, has_cjk: bool) -> int:
    query_languages = set(spec.query_languages)
    if has_cjk:
        return 1 if {"zh", "mixed"} & query_languages else 0
    return 1 if {"en", "mixed"} & query_languages else 0


def _domain_score(
    domain: str,
    *,
    query_lower: str,
    query_tokens: set[str],
    channels: tuple[ChannelRouteSpec, ...],
) -> int:
    """Score a metadata domain from both domain keywords and member-channel matches."""
    keyword_score = sum(1 for keyword in _DOMAIN_KEYWORDS.get(domain, ()) if keyword in query_lower)
    channel_scores = sorted(
        (_channel_match_score(spec, query_lower, query_tokens) for spec in channels),
        reverse=True,
    )
    metadata_score = sum(score for score in channel_scores[:2] if score > 0)
    return keyword_score + metadata_score


def select_channels(
    query: str,
    channel_priority: list[str] | None = None,
    channel_skip: list[str] | None = None,
    mode: str = "fast",
    max_channels: int = 8,
) -> dict:
    """Select channels from channel SKILL metadata plus light query hints.

    Returns {"groups": list[str], "channels": list[str], "rationale": str}.
    """
    priority = list(channel_priority or [])
    skip = {_normalize_channel_name(name) for name in channel_skip or []}
    limit = min(_MODE_LIMITS.get(mode, 5), max_channels)

    query_lower = _normalize_text(query)
    query_tokens = _query_tokens(query_lower)
    has_cjk = _has_cjk(query)
    catalog = load_channel_route_catalog()
    channels_by_domain = _channels_by_domain(catalog)

    scores: dict[str, int] = {}
    for domain, specs in channels_by_domain.items():
        score = _domain_score(
            domain,
            query_lower=query_lower,
            query_tokens=query_tokens,
            channels=specs,
        )
        if score > 0:
            scores[domain] = score

    top_groups = sorted(scores, key=lambda domain: (-scores[domain], domain))[:3]

    channels: list[str] = []
    seen: set[str] = set()

    for channel_name in priority:
        normalized = _normalize_channel_name(channel_name)
        if normalized and normalized not in seen and normalized not in skip:
            channels.append(normalized)
            seen.add(normalized)

    ranked_specs_by_group = {
        group: [
            spec
            for spec in sorted(
                channels_by_domain.get(group, ()),
                key=lambda spec: (
                    -_channel_match_score(spec, query_lower, query_tokens),
                    -_language_affinity(spec, has_cjk=has_cjk),
                    spec.name,
                ),
            )
            if spec.name not in skip
        ]
        for group in top_groups
    }

    while len(channels) < limit:
        added = False
        for group in top_groups:
            for spec in ranked_specs_by_group.get(group, []):
                if spec.name in seen:
                    continue
                channels.append(spec.name)
                seen.add(spec.name)
                added = True
                break
            if len(channels) >= limit:
                break
        if not added:
            break

    if not channels:
        for spec in channels_by_domain.get(_GENERIC_WEB_DOMAIN, ()):
            if spec.name in seen or spec.name in skip or len(channels) >= limit:
                continue
            channels.append(spec.name)
            seen.add(spec.name)
        top_groups = [_GENERIC_WEB_DOMAIN]

    rationale = (
        f"Groups: {top_groups or [_GENERIC_WEB_DOMAIN]}. "
        f"Mode: {mode} (limit {limit}). "
        "Selected from channel metadata with query-hint scoring. "
        f"Selected {len(channels)} channels."
    )

    return {
        "groups": top_groups or [_GENERIC_WEB_DOMAIN],
        "channels": channels[:limit],
        "rationale": rationale,
    }
