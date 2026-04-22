---
name: fetch-firecrawl
description: Use to scrape a URL into clean Markdown when the page is JS-rendered, behind anti-bot, or a PDF — and FIRECRAWL_API_KEY is available. Degrades gracefully to warn when key is missing.
version: 1
languages: [en, zh, mixed]
methods:
  - id: scrape
    impl: methods/scrape.py
    requires: [env:FIRECRAWL_API_KEY]
fallback_chain: [scrape]
when_to_use:
  query_languages: [en, zh, mixed]
  query_types: [web-fetch, url-scrape, deep-read]
  avoid_for: [keyword-search, batch-crawl]
quality_hint:
  typical_yield: high
  chinese_native: false
layer: leaf
domains: [generic-web]
scenarios: [url-to-markdown, js-rendered, anti-bot, pdf-scrape]
model_tier: Fast
auth_required: true
cost: paid
---

## Overview

Firecrawl turns any URL into clean Markdown via a managed browser cluster. Handles JS rendering, anti-bot defenses, and PDFs. Paid per-page; requires `FIRECRAWL_API_KEY`. When the key is missing, `doctor()` reports `warn`.

## When to Choose It

- Page is heavily JS-rendered (SPA, React, Next.js)
- Target site blocks `fetch-jina` or `fetch-crawl4ai`
- PDF or document conversion needed

## How To Use

Call via `run_channel("fetch-firecrawl", url)` where the query IS the URL to scrape.
Returns one Evidence item with `body` = full Markdown content.
