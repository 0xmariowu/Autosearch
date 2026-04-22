---
name: fetch-jina
description: Fetch any public URL as clean Markdown via Jina Reader (r.jina.ai). Best for articles, docs, blog posts; weak on heavy anti-bot sites (Zhihu, Xiaohongshu).
version: 0.1.0
layer: leaf
domains: [web-fetch]
scenarios: [url-reading, article-extraction]
trigger_keywords: [read url, 读网页, fetch markdown, 抓全文, jina reader]
model_tier: Fast
auth_required: false
cost: free
experience_digest: experience.md
---

Fetch public web pages as Markdown through Jina Reader's `https://r.jina.ai/<URL>` endpoint.

## URL Fit

- Best for articles, documentation, blogs, changelogs, and other mostly static public pages.
- Weak for JavaScript-heavy pages, login-gated content, and anti-bot sites such as Zhihu or Xiaohongshu.
- Use it as the first fast path when the task needs URL-to-Markdown content without browser state.

## Invocation

Call `fetch.py`'s async `fetch(url: str)` function with the original public URL:

```python
result = await fetch("https://example.com/article")
```

Successful calls return:

```python
{
    "ok": True,
    "url": "https://example.com/article",
    "reader_url": "https://r.jina.ai/https://example.com/article",
    "markdown": "...",
    "metadata": {"title": "...", "fetched_at": "...", "status": 200},
}
```

## Failure Modes

- Timeout, network errors, 4xx, and 5xx responses return `ok: false` with a structured `reason`.
- Anti-bot refusals return `reason: jina_refused` and `suggest_fallback: fetch-crawl4ai`.
- Runtime callers should choose their own fallback instead of assuming this tool retries.

## Limits

- Public Jina Reader availability and rate limits are upstream dependencies.
- Some sites block reader-style fetches or return degraded content.
- This skill does not execute JavaScript, click through consent flows, or authenticate.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
