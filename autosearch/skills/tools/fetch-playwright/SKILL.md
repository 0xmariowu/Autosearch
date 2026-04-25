---
name: fetch-playwright
description: Interactive browser automation (click, type, wait, screenshot, navigate) for dynamic pages that need user-like actions — pagination, login, form submission, infinite scroll. Uses Microsoft's official @playwright/mcp server; no autosearch-side Python. Use when fetch-jina and fetch-crawl4ai still cannot get the content.
version: 0.1.0
layer: leaf
domains: [web-fetch, browser-automation]
scenarios: [interactive-page, login-required, pagination, click-to-reveal, screenshot-capture]
trigger_keywords: [playwright, 浏览器自动化, 点击, 登录, 分页, 截图, interactive fetch]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

Drive a real Chromium browser from the runtime AI via Microsoft's official `@playwright/mcp` server. Use this when `fetch-jina` (cheapest) and `fetch-crawl4ai` (depth + basic JS) still cannot reach the content — typically because the page requires clicking, typing, scrolling, waiting for an event, or capturing a screenshot.

## Architecture (why there is no Python file in this skill)

This skill is **documentation-only**. The runtime AI calls `playwright-mcp` tools directly through its MCP client — autosearch does not wrap them. The skill exists so the runtime AI knows:

1. When to reach for Playwright (vs. fetch-jina / fetch-crawl4ai).
2. How to install `@playwright/mcp`.
3. Which MCP tools to call for common web-research patterns.

## Install

Register with your MCP client. For Claude Code, prefer `claude mcp add` (writes to `~/.claude.json`); for project-scoped config use `<project>/.mcp.json`. Cursor reads `~/.cursor/mcp.json`; Zed reads `<project>/.zed/mcp.json`. Schema for any of them:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

On first run, `npx` will download `@playwright/mcp` and Playwright will install a Chromium bundle. No API keys. Works offline for local pages.

## Common Tool Calls (as used by the runtime AI)

Tool names below come from `@playwright/mcp`. Exact schemas are served by the MCP server itself; the runtime AI enumerates them via the MCP client.

- `browser_navigate(url)` — go to a URL.
- `browser_snapshot()` — accessibility tree of the current page (cheap text form, no screenshot).
- `browser_click(ref)` / `browser_type(ref, text)` / `browser_press_key(key)` — interact with elements from the snapshot.
- `browser_wait_for(text | time | element)` — wait for an event or selector.
- `browser_take_screenshot()` — capture the current page as an image.
- `browser_evaluate(script)` — run custom JS (use sparingly).
- `browser_network_requests()` / `browser_console_messages()` — inspection.
- `browser_tabs(...)` — open, list, select, close tabs.
- `browser_close()` — release the browser.

## When to Use

- Page requires clicking a "Show more" / "Accept cookies" before content renders.
- Login-gated content where the user has supplied a session (via storage state).
- Infinite-scroll feed where lazy-load fires on scroll.
- Verifying a production flow where screenshots are the deliverable.
- Debugging network / console errors on a third-party page.

## When NOT to Use

- Static article, documentation, blog post → `fetch-jina` is cheaper.
- Lightly JS-rendered page that works with plain crawl → `fetch-crawl4ai`.
- Paid, hardened anti-bot site → `fetch-firecrawl` (paid) may still succeed where an ordinary Chromium cannot.

## Limits

- `@playwright/mcp` requires Node.js >= 18 and writes a Playwright browser bundle to the user's cache on first run (~200 MB).
- Long sessions consume memory; the runtime AI should call `browser_close()` when a task ends.
- Headful mode requires a desktop; CI / headless servers must use the default headless mode.
- Cookie / profile / storage state setup is the caller's responsibility (see `@playwright/mcp` docs for `storageState`).

## Downgrade / Upgrade Chain

- Below: `fetch-crawl4ai` (Playwright, same browser engine but no interactive control) → `fetch-jina` (HTTP Markdown only).
- Above: `fetch-firecrawl` (paid, stronger anti-bot and managed infra).

This tool does **not** produce a summary. The runtime AI processes the tool outputs directly; autosearch provides only the routing guidance in this SKILL.md.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
