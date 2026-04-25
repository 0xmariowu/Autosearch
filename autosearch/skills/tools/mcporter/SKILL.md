---
name: mcporter
description: Route the runtime AI to free third-party MCP servers via the upstream `mcporter` router — semantic web search (Exa), Chinese UGC (Weibo / Douyin / Xiaohongshu), and professional (LinkedIn). Zero API keys; free fallback path before reaching for paid TikHub on hard Chinese anti-bot platforms.
version: 0.1.0
layer: leaf
domains: [mcp-routing, web-search, chinese-ugc, social]
scenarios: [free-search-fallback, chinese-native-free-path, mcp-discovery]
trigger_keywords: [mcporter, mcp router, 免费 MCP, exa, weibo mcp, douyin mcp, xhs mcp, linkedin mcp]
model_tier: Fast
auth_required: false
cost: free
experience_digest: experience.md
---

Expose a curated set of upstream free MCP servers to the runtime AI through the `mcporter` router, so autosearch's Chinese UGC / web-search surface area extends beyond the paid TikHub fallback without introducing per-provider Python wrappers.

## Architecture (why there is no Python file in this skill)

This skill is **documentation-only**. The runtime AI invokes MCP tools directly through its MCP client — autosearch does not wrap them. The skill exists so the runtime AI knows:

1. Which free MCP servers are available through `mcporter`.
2. How to install and configure them.
3. Where each one fits in autosearch's channel / fetch decision chain.

## Install

Register with your MCP client. For Claude Code, prefer `claude mcp add` (writes to `~/.claude.json`); for project-scoped config use `<project>/.mcp.json`. Cursor reads `~/.cursor/mcp.json`; Zed reads `<project>/.zed/mcp.json`. Schema for any of them:

```json
{
  "mcpServers": {
    "mcporter": {
      "command": "npx",
      "args": ["-y", "@mcporter/mcp-router"]
    }
  }
}
```

On first run, `npx` downloads `@mcporter/mcp-router`. Individual upstream servers (Exa, Weibo, Douyin, Xiaohongshu, LinkedIn) are registered through `mcporter`'s own config file — see upstream docs. No API keys required for the free providers listed below; some (Douyin / LinkedIn) require the user to ship a browser cookie once.

## Servers Routed (free, no API key)

| Upstream MCP | What it returns | Autosearch equivalent | Relationship |
|---|---|---|---|
| **Exa web search** | Semantic web results, supports `site:`-style filtering | `search-exa` (paid) / `search-ddgs` (keyword) | Use when you want semantic relevance without paying for Exa — lighter, free tier. |
| **Weibo MCP** | Hot search, timeline, topic, user posts, comments | `search-weibo` (free native + TikHub fallback) | Free path when autosearch native Weibo is rate-limited or TikHub key is absent. |
| **Douyin MCP** | Video metadata, no-watermark URL, search | `search-douyin` (TikHub paid) | Free alternative to TikHub for Douyin; requires browser cookie. |
| **Xiaohongshu MCP** | Note search, read, comment, post | `search-xiaohongshu` (TikHub paid) | Free alternative to TikHub for XHS; requires browser cookie and login. |
| **LinkedIn MCP** | Profile detail, company page, job search | `search-linkedin` (paid) | Free alternative; requires browser session. |

## Decision Chain (how the runtime AI should choose)

For Chinese UGC platforms (Weibo / Douyin / Xiaohongshu):

1. Try autosearch native channel skill (`search-weibo`, `search-douyin`, `search-xiaohongshu`) — cheapest, no setup.
2. If rate-limited or content blocked: try the corresponding free `mcporter`-routed MCP (this skill).
3. If free MCP fails (quota, cookie expired, upstream flaky): reach for TikHub paid fallback via the channel skill.
4. If TikHub is unavailable and content cannot be had: report failure to the user.

For generic web search:

1. `search-ddgs` (free, no key, simple keyword).
2. `mcporter`-routed Exa (free semantic tier, via this skill).
3. `search-exa` / `search-tavily` (paid) if deeper semantic coverage is needed.

## When to Use

- User does not have a TikHub key and needs Chinese UGC data.
- Free-tier semantic web search that outperforms raw DDGS keyword matches.
- Quick fallback when a native autosearch channel is temporarily rate-limited.

## When NOT to Use

- Mission-critical content with hard deadlines — free community MCPs can go flaky; pay for TikHub.
- Platform-specific deep extraction that the free MCP does not expose (only TikHub covers the full API).
- If the upstream `mcporter` is not installed or the MCP client is not configured.

## Limits

- Free MCPs are community-maintained and can regress without notice. Autosearch does not pin versions.
- Cookie-based providers (Douyin / Xiaohongshu / LinkedIn) need one-time browser-session export from the user.
- `mcporter` runs as a subprocess under the MCP client; resources (Node.js, memory) scale with how many upstream servers the user registers.
- Language and regional restrictions of each upstream MCP still apply.

## Downgrade / Upgrade Chain

- Below: native autosearch channel skills (cheapest, no setup).
- Above: TikHub paid fallback via the channel skills (reliable, broader API).

This tool does **not** produce a summary. The runtime AI reads the MCP results directly; autosearch only provides the routing catalog in this SKILL.md.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
