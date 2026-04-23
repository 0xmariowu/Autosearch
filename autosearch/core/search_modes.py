"""Dynamic search modes — DB-backed research personalities.

Each mode configures:
  - Channel priority (search these first)
  - Channel skip (never search these)
  - System prompt addon (injected into clarify/synthesize steps)
  - Intent keywords (auto-detect mode from query)

Usage:
  from autosearch.core.search_modes import get_mode, list_modes, SearchMode

  mode = get_mode("academic")   # returns SearchModeConfig
  mode = detect_mode("最新 AI 论文综述")  # auto-detect from query
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ── Built-in modes ────────────────────────────────────────────────────────────

@dataclass
class SearchModeConfig:
    key: str
    label_zh: str
    label_en: str
    keywords: list[str] = field(default_factory=list)
    channel_priority: list[str] = field(default_factory=list)
    channel_skip: list[str] = field(default_factory=list)
    system_prompt: str = ""
    enabled: bool = True
    is_system: bool = True

    def matches_query(self, query: str) -> bool:
        """True if any keyword appears in the query (case-insensitive)."""
        q = query.lower()
        return any(kw.lower() in q for kw in self.keywords)


_BUILTIN_MODES: list[SearchModeConfig] = [
    SearchModeConfig(
        key="academic",
        label_zh="学术研究",
        label_en="Academic",
        keywords=["论文", "研究", "文献", "综述", "paper", "research", "survey", "journal",
                  "arxiv", "pubmed", "citation", "methodology"],
        channel_priority=["arxiv", "pubmed", "openalex", "crossref", "dblp", "papers"],
        channel_skip=["tiktok", "instagram", "kuaishou", "wechat_channels"],
        system_prompt=(
            "You are a rigorous academic research assistant. "
            "Prioritize peer-reviewed sources, cite DOIs when available, "
            "note publication dates and citation counts. "
            "Flag preprints vs. published work."
        ),
    ),
    SearchModeConfig(
        key="news",
        label_zh="时事新闻",
        label_en="News & Current Events",
        keywords=["最新", "今天", "新闻", "动态", "latest", "today", "news", "breaking",
                  "current", "2024", "2025", "2026", "recent"],
        channel_priority=["google_news", "twitter", "hackernews", "weibo", "ddgs"],
        channel_skip=["arxiv", "sec_edgar", "crossref", "dblp"],
        system_prompt=(
            "You are a news researcher. Prioritize recency — sources from the last 7 days "
            "are strongly preferred. Note publication dates. Flag outdated information. "
            "Cross-reference multiple sources before citing a claim."
        ),
    ),
    SearchModeConfig(
        key="chinese_ugc",
        label_zh="中文社区",
        label_en="Chinese Community",
        keywords=["中文", "国内", "中国", "用户", "经验", "评测", "推荐", "种草",
                  "小红书", "知乎", "B站", "微博", "抖音", "UGC"],
        channel_priority=["xiaohongshu", "zhihu", "bilibili", "weibo", "douyin",
                          "tieba", "v2ex", "sogou_weixin"],
        channel_skip=["arxiv", "pubmed", "sec_edgar", "reddit", "stackoverflow"],
        system_prompt=(
            "你是一位中文内容研究员。优先引用来自中文社区的第一手用户经验，"
            "注意区分口碑内容与广告软文，关注发布时间和互动数据。"
        ),
    ),
    SearchModeConfig(
        key="developer",
        label_zh="技术开发",
        label_en="Developer & Technical",
        keywords=["代码", "实现", "API", "库", "框架", "bug", "debug", "code", "implement",
                  "library", "framework", "tutorial", "how to", "github", "npm", "pypi"],
        channel_priority=["github", "stackoverflow", "hackernews", "devto",
                          "huggingface_hub", "package_search", "arxiv"],
        channel_skip=["tiktok", "kuaishou", "wechat_channels", "sec_edgar"],
        system_prompt=(
            "You are a senior developer assistant. Include working code examples. "
            "Reference official docs and GitHub repos. Note version compatibility. "
            "Prefer answers with code snippets over abstract explanations."
        ),
    ),
    SearchModeConfig(
        key="product",
        label_zh="产品调研",
        label_en="Product Research",
        keywords=["产品", "竞品", "用户反馈", "体验", "对比", "评测", "product", "review",
                  "compare", "competitor", "feedback", "ux", "pricing"],
        channel_priority=["reddit", "hackernews", "twitter", "xiaohongshu",
                          "instagram", "devto", "v2ex"],
        channel_skip=["arxiv", "pubmed", "sec_edgar", "crossref"],
        system_prompt=(
            "You are a product researcher. Surface user pain points and genuine opinions. "
            "Distinguish paid reviews from organic feedback. "
            "Note competitor comparisons and pricing context. "
            "Quote specific user complaints and praise."
        ),
    ),
]

# ── Mode registry ─────────────────────────────────────────────────────────────

_MODE_MAP: dict[str, SearchModeConfig] = {m.key: m for m in _BUILTIN_MODES}

# User-customizable modes file (JSON)
_CUSTOM_MODES_PATH = Path.home() / ".config" / "autosearch" / "custom_modes.json"


def _load_custom_modes() -> list[SearchModeConfig]:
    """Load user-defined modes from ~/.config/autosearch/custom_modes.json."""
    if not _CUSTOM_MODES_PATH.exists():
        return []
    try:
        data = json.loads(_CUSTOM_MODES_PATH.read_text(encoding="utf-8"))
        modes = []
        for entry in data if isinstance(data, list) else []:
            if isinstance(entry, dict) and entry.get("key"):
                modes.append(SearchModeConfig(
                    key=entry["key"],
                    label_zh=entry.get("label_zh", entry["key"]),
                    label_en=entry.get("label_en", entry["key"]),
                    keywords=entry.get("keywords", []),
                    channel_priority=entry.get("channel_priority", []),
                    channel_skip=entry.get("channel_skip", []),
                    system_prompt=entry.get("system_prompt", ""),
                    enabled=entry.get("enabled", True),
                    is_system=False,
                ))
        return modes
    except Exception:
        return []


def _get_all_modes() -> dict[str, SearchModeConfig]:
    """Return all modes: builtins + user custom (custom overrides builtins by key)."""
    merged = dict(_MODE_MAP)
    for mode in _load_custom_modes():
        if mode.enabled:
            merged[mode.key] = mode
    return merged


def list_modes() -> list[SearchModeConfig]:
    """List all enabled modes."""
    return [m for m in _get_all_modes().values() if m.enabled]


def get_mode(key: str) -> SearchModeConfig | None:
    """Get a mode by key. Returns None if not found."""
    return _get_all_modes().get(key)


def detect_mode(query: str) -> SearchModeConfig | None:
    """Auto-detect the best mode for a query using keyword matching.

    Returns None if no mode matches (caller uses default behavior).
    Priority: user custom > academic > developer > news > chinese_ugc > product
    """
    # Custom modes checked first
    all_modes = _get_all_modes()
    custom_keys = [k for k, m in all_modes.items() if not m.is_system and m.enabled]
    priority_keys = custom_keys + ["academic", "developer", "news", "chinese_ugc", "product"]

    for key in priority_keys:
        mode = all_modes.get(key)
        if mode and mode.enabled and mode.matches_query(query):
            return mode
    return None


def save_custom_mode(mode: SearchModeConfig) -> None:
    """Save a custom mode to ~/.config/autosearch/custom_modes.json."""
    _CUSTOM_MODES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_custom_modes()
    # Replace if key exists
    updated = [m for m in existing if m.key != mode.key] + [mode]
    data = [
        {
            "key": m.key,
            "label_zh": m.label_zh,
            "label_en": m.label_en,
            "keywords": m.keywords,
            "channel_priority": m.channel_priority,
            "channel_skip": m.channel_skip,
            "system_prompt": m.system_prompt,
            "enabled": m.enabled,
        }
        for m in updated
    ]
    _CUSTOM_MODES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
