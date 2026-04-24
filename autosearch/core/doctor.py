"""Channel health scanner for autosearch doctor() MCP tool.

Tier system (1:1 from Agent-Reach doctor.py):
  Tier 0 — zero config, works out of the box
  Tier 1 — needs API key (free or paid)
  Tier 2 — needs login / cookie
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from autosearch.skills import SkillLoadError, load_all

if TYPE_CHECKING:
    from autosearch.skills.loader import SkillSpec

# Maps unmet env var names → actionable fix commands (1:1 from Agent-Reach cookie_extract.py)
_ENV_FIX_HINTS: dict[str, str] = {
    # Login-based channels
    "XHS_COOKIES": "autosearch login xhs",
    "XHS_A1_COOKIE": "autosearch login xhs",
    "XIAOHONGSHU_COOKIES": "autosearch login xhs",
    "TWITTER_COOKIES": "autosearch login twitter",
    "BILIBILI_COOKIES": "autosearch login bilibili",
    "WEIBO_COOKIES": "autosearch login weibo",
    "DOUYIN_COOKIES": "autosearch login douyin",
    "ZHIHU_COOKIES": "autosearch login zhihu",
    "XUEQIU_COOKIES": "autosearch login xueqiu",
    # API key channels
    "TIKHUB_API_KEY": "autosearch configure TIKHUB_API_KEY <your-key>",
    "YOUTUBE_API_KEY": "autosearch configure YOUTUBE_API_KEY <your-key>",
    "FIRECRAWL_API_KEY": "autosearch configure FIRECRAWL_API_KEY <your-key>",
    "SEARXNG_URL": "autosearch configure SEARXNG_URL http://localhost:8080",
    # Worker
    "AUTOSEARCH_SIGNSRV_URL": "autosearch configure AUTOSEARCH_SIGNSRV_URL <worker-url>",
    "AUTOSEARCH_SERVICE_TOKEN": "autosearch configure AUTOSEARCH_SERVICE_TOKEN <token>",
}

# Channels that need login/cookie are tier 2; API key channels are tier 1; free are tier 0
_TIER2_ENV_PATTERNS = ("COOKIES", "COOKIE", "SESSION", "SESSDATA", "AUTH_TOKEN")
_TIER1_ENV_PATTERNS = ("API_KEY", "TIKHUB", "YOUTUBE", "FIRECRAWL", "OPENROUTER")


@dataclass
class ChannelStatus:
    channel: str
    status: str  # "ok" | "warn" | "off"
    message: str
    unmet_requires: list[str]
    tier: int = 0  # 0=free, 1=api_key, 2=login_required
    fix_hint: str = ""  # actionable one-liner to fix


def scan_channels(channels_root: Path | None = None) -> list[ChannelStatus]:
    """Scan all channel skills and return health status for each.

    status:
      ok   — all methods have their requires satisfied
      warn — at least one method available, some unmet
      off  — no methods available (all requires unmet or no methods)
    """
    root = channels_root or _default_channels_root()
    if not root.is_dir():
        return []

    try:
        specs = load_all(root)
    except SkillLoadError:
        return []

    env_keys = _current_env_keys()
    results: list[ChannelStatus] = []

    for spec in sorted(specs, key=lambda s: s.name):
        all_unmet: list[str] = []
        available_methods = 0
        for method in spec.methods:
            unmet = [token for token in method.requires if not _token_satisfied(token, env_keys)]
            if not unmet:
                available_methods += 1
            else:
                all_unmet.extend(unmet)

        if not spec.methods:
            status = "off"
            message = "no methods defined"
        elif available_methods == len(spec.methods):
            status = "ok"
            message = f"{available_methods}/{len(spec.methods)} methods available"
        elif available_methods > 0:
            status = "warn"
            unique_unmet = list(dict.fromkeys(all_unmet))
            message = (
                f"{available_methods}/{len(spec.methods)} methods available; "
                f"unmet: {', '.join(unique_unmet)}"
            )
        else:
            status = "off"
            unique_unmet = list(dict.fromkeys(all_unmet))
            message = f"unmet: {', '.join(unique_unmet)}"

        unique_unmet = list(dict.fromkeys(all_unmet))
        all_requires = [token for method in spec.methods for token in method.requires]
        tier = _resolve_tier(spec, all_requires)
        fix = _resolve_fix_hint(spec, unique_unmet)

        results.append(
            ChannelStatus(
                channel=spec.name,
                status=status,
                message=message,
                unmet_requires=unique_unmet,
                tier=tier,
                fix_hint=fix,
            )
        )

    return results


def format_report(results: list[ChannelStatus]) -> str:
    """Format results as a readable text report.

    1:1 tier-grouped format from Agent-Reach agent_reach/doctor.py:format_report.
    """
    tier0 = [r for r in results if r.tier == 0]
    tier1 = [r for r in results if r.tier == 1]
    tier2 = [r for r in results if r.tier == 2]

    ok_count = sum(1 for r in results if r.status == "ok")
    total = len(results)

    lines: list[str] = []
    lines.append("AutoSearch 渠道状态")
    lines.append("=" * 42)

    # Tier 0 — zero config
    ok0 = [r for r in tier0 if r.status == "ok"]
    lines.append(f"\n开箱即用 ({len(ok0)}/{len(tier0)})")
    for r in tier0:
        icon = "✅" if r.status == "ok" else ("⚠️ " if r.status == "warn" else "❌")
        lines.append(f"  {icon} {r.channel:<22} {r.message}")

    # Tier 1 — API key
    if tier1:
        ok1 = [r for r in tier1 if r.status == "ok"]
        lines.append(f"\nAPI key 渠道 ({len(ok1)}/{len(tier1)})")
        for r in tier1:
            if r.status == "ok":
                icon = "✅"
                lines.append(f"  {icon} {r.channel:<22} {r.message}")
            else:
                icon = "❌"
                hint = f"  →  {r.fix_hint}" if r.fix_hint else ""
                lines.append(f"  {icon} {r.channel:<22} 未配置{hint}")

    # Tier 2 — login required
    if tier2:
        ok2 = [r for r in tier2 if r.status == "ok"]
        lines.append(f"\n需登录渠道 ({len(ok2)}/{len(tier2)})")
        for r in tier2:
            if r.status == "ok":
                icon = "✅"
                lines.append(f"  {icon} {r.channel:<22} {r.message}")
            else:
                icon = "⚠️ " if r.status == "warn" else "❌"
                hint = f"  →  {r.fix_hint}" if r.fix_hint else ""
                lines.append(f"  {icon} {r.channel:<22} 未配置{hint}")

    # Summary
    lines.append("")
    lines.append(f"状态：{ok_count}/{total} 个渠道可用")

    off_count = total - ok_count
    if off_count > 0:
        lines.append("提示：运行 autosearch doctor --fix 查看所有修复步骤")

    return "\n".join(lines)


# ── helpers ───────────────────────────────────────────────────────────────────


def _resolve_tier(spec: SkillSpec, all_requires: list[str]) -> int:
    """Resolve doctor tier from declared metadata first, then infer as fallback."""
    declared_tier = getattr(spec, "tier", None)
    if declared_tier is not None:
        return declared_tier
    return _compute_tier(all_requires)


def _compute_tier(all_requires: list[str]) -> int:
    """Infer tier from a channel's full requires list.

    Tier 2 > Tier 1 > Tier 0: if any require implies login, tier=2.
    """
    for token in all_requires:
        kind, _, value = token.partition(":")
        if kind == "env":
            if any(p in value.upper() for p in _TIER2_ENV_PATTERNS):
                return 2
        elif kind in ("cookie",):
            return 2
    for token in all_requires:
        kind, _, value = token.partition(":")
        if kind == "env":
            if any(p in value.upper() for p in _TIER1_ENV_PATTERNS):
                return 1
        elif kind in ("binary", "mcp"):
            return 1
    return 0


def _resolve_fix_hint(spec: SkillSpec, unmet_requires: list[str]) -> str:
    """Resolve fix hint from declared metadata first, then infer as fallback."""
    declared_fix_hint = getattr(spec, "fix_hint", None)
    if isinstance(declared_fix_hint, str) and declared_fix_hint.strip():
        return declared_fix_hint.strip()
    return _fix_hint(unmet_requires)


def _fix_hint(unmet_requires: list[str]) -> str:
    """Generate the most actionable one-line fix from unmet requires.

    Priority: login commands > configure commands > generic hints.
    """
    login_hints = []
    configure_hints = []

    for token in unmet_requires:
        kind, _, value = token.partition(":")
        if kind == "env":
            hint = _ENV_FIX_HINTS.get(value)
            if hint:
                if hint.startswith("autosearch login"):
                    login_hints.append(hint)
                else:
                    configure_hints.append(hint)
            else:
                configure_hints.append(f"autosearch configure {value} <value>")
        elif kind == "cookie":
            login_hints.append(f"autosearch login {value}")
        elif kind == "binary":
            configure_hints.append(f"pipx install {value}")
        elif kind == "mcp":
            configure_hints.append(f"# enable MCP server: {value}")

    if login_hints:
        return login_hints[0]
    if configure_hints:
        return configure_hints[0]
    return ""


def _token_satisfied(token: str, env_keys: set[str]) -> bool:
    kind, _, value = token.partition(":")
    if kind == "env":
        return value in env_keys
    # cookie / mcp / binary: treat as unsatisfied unless env override exists
    return False


def _current_env_keys() -> set[str]:
    return {key for key, val in os.environ.items() if val}


def _default_channels_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / "channels"
