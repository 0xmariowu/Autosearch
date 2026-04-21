---
name: tools-fetch-render
description: URL fetching and rendering — Jina Reader (fast path), crawl4ai (JS / anti-bot), Playwright MCP (interactive), Firecrawl (paid fallback), fetch-webpage, follow-links, mcporter routing.
layer: group
domains: [web-fetch]
scenarios: [url-reading, js-rendering, interactive-page, anti-bot, link-following]
model_tier: Fast
experience_digest: experience.md
---

# Fetch & Render Tools

Turning a URL into usable content. Ordered cheapest → strongest.

## Leaf skills

| Leaf | Best for | Tier | Auth / cost |
|---|---|---|---|
| `fetch-jina` | Static pages, blogs, docs, changelogs | Fast | free (no key) |
| `fetch-crawl4ai` | JS-rendered pages, anti-bot sites | Standard | free (user installs crawl4ai + Playwright) |
| `fetch-playwright` | Interactive flows — click / type / wait / screenshot | Standard | free (user installs `@playwright/mcp`) |
| `fetch-firecrawl` | Paid fallback for the hardest anti-bot sites | Standard | `FIRECRAWL_API_KEY` (paid) |
| `fetch-webpage` | Legacy autosearch in-repo HTML fetcher | Fast | free |
| `follow-links` | Crawl outlinks from a curated list / awesome page | Standard | free |
| `mcporter` | Free MCP routing (Exa / Weibo / Douyin / XHS / LinkedIn) | Fast | see `mcporter` SKILL |

## Routing notes

Default chain the runtime AI should apply when asked to fetch a URL:

1. `fetch-jina` — cheapest, zero-key. Works for 60-70% of public pages.
2. `fetch-crawl4ai` — if Jina returns empty / blocked or the page needs JS.
3. `fetch-playwright` — if the task needs user-like interaction.
4. `fetch-firecrawl` — only if all above fail and the user has a paid key.

`follow-links` runs **on top** of whatever fetcher is chosen — it's the link-extraction layer, not a fetcher itself.

`mcporter` is the free semantic-search path; treat it as channel surface rather than fetch layer.
