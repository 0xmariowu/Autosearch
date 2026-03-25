---
title: Hacker News — Search Patterns & Validated Knowledge
date: 2026-03-23
project: search-methodology
type: platform
tags: [hackernews, hn, tech-discourse, product-launches]
status: active
---

# Hacker News

## What It's Best For

- High-level technical discourse and analysis
- Product launches and industry reactions
- Technical deep-dives from experienced practitioners

## Access Methods

| Method | API / Tool | Best For |
|--------|-----------|----------|
| Algolia API | `hn.algolia.com/api/v1/search?query=...&tags=story` | Keyword search with engagement data |
| Exa + `site:news.ycombinator.com` | Exa semantic search | Natural language discovery |

## Validated Patterns

### Quoted product names only
- **Finding**: `"Claude Code"` (quoted) = 16,600 score. `"Claude Code" rules` (with modifier) = 46 score. 99.7% drop.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch direct comparison
- **Confidence**: systematic
- **Rule**: On HN, search ONLY the product name in quotes. Never add modifiers.

### Abstract concepts score near zero
- **Finding**: "AI coding agent context" scores 26 points. HN users use product names, not category descriptions.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch post-mortem
- **Confidence**: systematic
- **Rule**: Never use abstract/category terms on HN. Always use specific product/project names.

### Show HN filter: 100+ points
- **Finding**: Show HN posts with <100 points are usually self-promotion, not community-validated content.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch manual review of Show HN results
- **Confidence**: multiple tests
- **Rule**: When evaluating Show HN tool posts, require ≥100 points for signal.

## Engagement Scoring

```
engagement = points + num_comments
```

Both fields from Algolia API (`points`, `num_comments`).

## Search Tips

- `tags=story` filters to submitted links (not comments)
- `hitsPerPage=20` is a reasonable limit per query
- Results are sorted by relevance by default, which works well for HN

## Known Failures

| Query Pattern | Why It Fails | Date |
|--------------|-------------|------|
| Product name + modifier | 99% score drop vs bare name | 2026-03-21 |
| Abstract concept terms | Near-zero engagement | 2026-03-21 |
| Show HN with <100 points | Self-promo, not signal | 2026-03-21 |

## Unvalidated

(None currently)
