---
title: Twitter/X — Search Patterns & Validated Knowledge
date: 2026-03-23
project: search-methodology
type: platform
tags: [twitter, x, social-media, developer-sentiment]
status: active
---

# Twitter / X

## What It's Best For

- Real-time developer complaints and hot takes
- Product announcements and reactions
- Quick sentiment signals on tools and releases

## Access Methods

| Method | API / Tool | Best For | Reliability |
|--------|-----------|----------|------------|
| Exa + `site:x.com` | Exa semantic search | **Discovery** — finding tweet URLs | Reliable |
| `xreach tweet URL --json` | xreach CLI | **Reading** specific tweets | Reliable |
| `xreach tweets @user -n 20 --json` | xreach CLI | **Timeline** scanning for known users | Reliable |
| `xreach search "query"` | xreach CLI | General search | **UNRELIABLE — do not use** |

## Validated Patterns

### xreach search is unreliable — use Exa instead
- **Finding**: `xreach search` returns empty results for all query types tested.
- **Date validated**: 2026-03-21
- **How validated**: Tested 10+ queries across different topics, all returned empty
- **Confidence**: systematic
- **Rule**: NEVER rely on `xreach search` for discovery. Use Exa with `site:x.com` instead.

### Exa → xreach workflow
- **Finding**: The reliable Twitter search workflow is:
  1. Exa search with topic + `site:x.com` → find tweet URLs
  2. `xreach tweet URL --json` → read full tweet + engagement data
  3. If the user is prolific, `xreach tweets @user -n 20 --json` → scan their timeline
- **Date validated**: 2026-03-21
- **How validated**: Used successfully during AutoSearch sessions
- **Confidence**: multiple tests

## Engagement Scoring

Available via `xreach tweet URL --json`: likes, retweets, replies.

## Known Failures

| What | Why It Fails | Date |
|------|-------------|------|
| `xreach search` | Returns empty for all queries | 2026-03-21 |
| Direct Twitter API | Requires paid access since 2023 | Known |

## Unvalidated

- Cookie-based authentication may expire, causing `xreach` to fail silently. Check `xreach auth check` if results are empty.
