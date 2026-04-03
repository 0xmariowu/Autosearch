---
name: normalize-results
description: "Use after collecting results from any platform to standardize into canonical evidence schema, deduplicate across platforms, and ensure judge.py gets clean input."
---

# Purpose

Every platform returns results in a different shape.
judge.py expects a specific schema.
This skill bridges the gap: normalize all platform outputs into one canonical format and remove duplicates.

Without normalization, the same resource found on GitHub AND web search counts as two separate results with inconsistent metadata.
With normalization, it counts once with the richest metadata from all sources.

# Canonical Evidence Schema

Every evidence record must have these fields:

```
url            — canonical URL (normalized, no tracking params)
title          — result title
snippet        — description or summary text
source         — platform name (github, arxiv, web-ddgs, reddit, hn, exa, hf, etc.)
query          — the query that found this result
metadata.llm_relevant    — true/false (set by llm-evaluate)
metadata.llm_reason      — one sentence justification
metadata.published_at    — ISO 8601 (set by extract-dates, optional)
metadata.updated_at      — ISO 8601 (optional)
metadata.created_utc     — ISO 8601 (optional)
```

Optional enrichment fields:

```
metadata.stars           — GitHub stars (integer)
metadata.citations       — academic citations (integer)
metadata.language        — primary programming language
metadata.topics          — list of tags/topics
metadata.author          — author or org name
```

# URL Normalization

Before dedup, canonicalize URLs:

- Remove tracking parameters (utm_*, ref, source, etc.)
- Remove trailing slashes
- Remove fragment identifiers unless they point to specific content
- Normalize github.com URLs: strip /tree/main, /blob/main when pointing to repo root
- Lowercase the hostname
- Decode percent-encoded characters that don't need encoding

Two URLs are the same if their canonical forms match.

# Cross-Platform Deduplication

After URL normalization, check for near-duplicates:

- Same canonical URL → merge (keep the record with richer metadata)
- Same title AND overlapping snippet (>50% word overlap) → merge
- Same GitHub repo appearing as both github source and web-ddgs source → keep github version (has stars, language, updatedAt)

When merging, keep:
- The most specific source tag (github > web-ddgs for repos)
- The longest snippet
- All metadata fields from both records (union, not replace)
- The first query that found it

# Source Tagging

The `source` field directly affects judge.py's diversity score (Simpson index).
Tag accurately:

- `github` — from gh search repos/issues/code
- `arxiv` — from arXiv search
- `web-ddgs` — from DuckDuckGo/web search
- `reddit` — from Reddit search
- `hn` — from Hacker News search
- `exa` — from Exa search
- `hf` — from HuggingFace search
- `own-knowledge` — from use-own-knowledge.md
- `tavily` — from Tavily search
- `searxng` — from SearXNG search

Do not tag web-found GitHub URLs as `github` unless they came from gh CLI.
The source reflects HOW the result was found, not WHERE the URL points.

# When To Run

Run normalization after each platform's results are collected, before LLM evaluation.
Run cross-platform dedup after all platforms have been searched in a round.

# Quality Bar

After normalization, every record in the evidence file should:
- have all required fields populated
- have a canonical URL
- not duplicate another record by URL or title+snippet
- have an accurate source tag
