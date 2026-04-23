"""Group-first two-stage channel selection for v2 tool-supplier."""

from __future__ import annotations

_GROUP_KEYWORDS: dict[str, list[str]] = {
    "chinese-ugc": [
        "Linux DO",
        "linux do",
        "linux.do",
        "linuxdo",
        "discourse",
        "小红书",
        "抖音",
        "B站",
        "微博",
        "知乎",
        "播客",
        "快手",
        "雪球",
        "V2EX",
        "bilibili",
        "xhs",
        "douyin",
        "weibo",
        "zhihu",
        "xiaohongshu",
        "kuaishou",
    ],
    "cn-tech": ["36kr", "CSDN", "掘金", "InfoQ", "公众号", "juejin", "infoq", "csdn"],
    "academic": [
        "paper",
        "arxiv",
        "citation",
        "benchmark",
        "论文",
        "survey",
        "openreview",
        "semantic scholar",
        "semanticscholar",
        "conference",
        "ieee",
        "acm",
    ],
    "code-package": [
        "github",
        "repo",
        "code",
        "issue",
        "npm",
        "pypi",
        "huggingface",
        "package",
        "library",
        "sdk",
        "crate",
        "gem",
    ],
    "market-product": [
        "crunchbase",
        "融资",
        "producthunt",
        "G2",
        "review",
        "startup",
        "funding",
        "投资",
        "竞品",
    ],
    "community-en": [
        "stackoverflow",
        "hacker news",
        "hackernews",
        "dev.to",
        "devto",
        "reddit",
        "hn",
    ],
    "social-career": ["twitter", "linkedin", "X ", "职业", "career", "招聘", "hiring"],
    "video-audio": [
        "视频",
        "字幕",
        "转录",
        "podcast",
        "youtube",
        "video",
        "transcript",
        "bilibili视频",
        "音频",
    ],
    "generic-web": ["搜索", "search", "news", "网页", "google", "bing", "tavily", "exa", "ddgs"],
}

_GROUP_CHANNELS: dict[str, list[str]] = {
    "chinese-ugc": ["discourse_forum", "bilibili", "xiaohongshu", "zhihu", "weibo", "douyin"],
    "cn-tech": ["kr36", "infoq_cn", "sogou_weixin"],
    "academic": ["arxiv", "papers", "google_scholar"],
    "code-package": ["github", "package_search"],
    "market-product": ["hackernews", "ddgs"],
    "community-en": ["hackernews", "stackoverflow", "reddit"],
    "social-career": ["twitter", "ddgs"],
    "video-audio": ["youtube"],
    "generic-web": ["ddgs", "exa", "tavily"],
}

_MODE_LIMITS = {"fast": 5, "deep": 8}


def select_channels(
    query: str,
    channel_priority: list[str] | None = None,
    channel_skip: list[str] | None = None,
    mode: str = "fast",
    max_channels: int = 8,
) -> dict:
    """Two-stage group-first channel selection.

    Stage 1: score groups against query keywords.
    Stage 2: collect leaf channels from matched groups.

    Returns {"groups": list[str], "channels": list[str], "rationale": str}.
    """
    priority = list(channel_priority or [])
    skip = set(channel_skip or [])
    limit = min(_MODE_LIMITS.get(mode, 5), max_channels)

    query_lower = query.lower()

    # Stage 1 — score groups
    scores: dict[str, int] = {}
    for group, keywords in _GROUP_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in query_lower)
        if score:
            scores[group] = score

    top_groups = sorted(scores, key=lambda g: scores[g], reverse=True)[:3]

    # Stage 2 — collect leaf channels
    channels: list[str] = []
    seen: set[str] = set()

    # priority channels first (from clarify result)
    for ch in priority:
        if ch not in seen and ch not in skip:
            channels.append(ch)
            seen.add(ch)

    # then fill from matched groups
    for group in top_groups:
        for ch in _GROUP_CHANNELS.get(group, []):
            if ch not in seen and ch not in skip and len(channels) < limit:
                channels.append(ch)
                seen.add(ch)

    # fallback to generic-web if nothing matched
    if not channels:
        for ch in _GROUP_CHANNELS["generic-web"]:
            if ch not in seen and ch not in skip and len(channels) < limit:
                channels.append(ch)
                seen.add(ch)
        top_groups = ["generic-web"]

    rationale = (
        f"Groups: {top_groups or ['generic-web']}. "
        f"Mode: {mode} (limit {limit}). "
        f"Selected {len(channels)} channels."
    )

    return {
        "groups": top_groups or ["generic-web"],
        "channels": channels[:limit],
        "rationale": rationale,
    }
