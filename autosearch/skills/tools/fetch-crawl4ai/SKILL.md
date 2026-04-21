---
name: fetch-crawl4ai
description: Deep URL fetch using crawl4ai (Playwright-powered) for JS-rendered pages, anti-bot sites, and dynamic content. Slower than fetch-jina but handles sites that block simple fetchers. Requires user-installed crawl4ai package.
version: 0.1.0
layer: leaf
domains: [web-fetch]
scenarios: [url-reading, js-heavy, anti-bot-site, dynamic-content]
trigger_keywords: [fetch, 深抓, crawl, JS 渲染, playwright, 动态页, anti-bot]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

Deep URL fetch through `crawl4ai`, backed by Playwright and Chromium. Use this as the fallback when `fetch-jina` fails, refuses a URL, returns an empty page, or cannot see JavaScript-rendered content.

## Input Fit

- JavaScript-heavy SPAs where server HTML is mostly empty.
- Anti-bot or dynamic sites that block simple HTTP fetchers.
- Pages that need a CSS selector wait before extraction.
- Public pages where a local Chromium browser can render the content.

## Invocation

Call `fetch.py`'s sync `fetch(url: str, wait_for: str | None = None, timeout_seconds: float = 30.0)` function:

```python
result = fetch("https://example.com/app", wait_for=".loaded")
```

Successful calls return:

```python
{
    "ok": True,
    "markdown": "...",
    "title": "Rendered page title",
    "url": "https://example.com/final-url",
    "meta": {
        "status_code": 200,
        "backend": "crawl4ai",
        "browser": "chromium",
        "elapsed_sec": 2.4,
    },
    "source": "https://example.com/app",
}
```

## Failure Modes

- Missing `crawl4ai` package returns `reason: crawl4ai_unavailable`. Install with `pip install crawl4ai` plus `playwright install chromium`, or fall back to `fetch-jina`.
- Browser or crawl4ai runtime failures return `reason: crawl4ai_runtime_error` with the error message or stderr tail.
- DNS, connection, and transport failures return `reason: network_error`.
- Slow pages that exceed `timeout_seconds` return `reason: timeout`.
- HTTP 403 or detectable challenge pages return `reason: anti_bot_blocked`; degrade to `fetch-playwright` or `fetch-firecrawl` paid fallback.
- Successful crawls with empty or too-short Markdown return `reason: empty_content`.

## Limits

- Requires user opt-in installation: `pip install crawl4ai`.
- Requires a Chromium browser installed for Playwright: `playwright install chromium`.
- This tool is slower and heavier than `fetch-jina`; use it only when a simple fetch cannot retrieve the useful content.
- It does not solve sites that require authentication, strong bot mitigation, paid proxies, or long interactive flows.
