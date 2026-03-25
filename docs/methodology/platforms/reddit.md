---
title: Reddit — Search Patterns & Validated Knowledge
date: 2026-03-23
project: search-methodology
type: platform
tags: [reddit, community, user-feedback, pain-points]
status: active
---

# Reddit

## What It's Best For

- User pain points and complaints (real-world failure reports)
- Community discussions and tips/workarounds
- Sentiment on tools, frameworks, products

## Access Methods

| Method | API / Tool | Best For |
|--------|-----------|----------|
| Reddit JSON API | `reddit.com/r/{sub}/search.json?q=...` | Direct subreddit search with engagement data |
| Exa + `site:reddit.com` | Exa semantic search | Natural language discovery across all subreddits |

**Header required**: `User-Agent: autosearch-engine/1.0` (Reddit blocks requests without UA)
**Rate limit**: ~0.2s between requests

## Validated Patterns

### sort=relevance >> sort=top
- **Finding**: `sort=relevance` gives 53% pain ratio vs 10% for `sort=top`. 5x improvement.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch A/B comparison across 20 queries
- **Confidence**: systematic (AutoSearch post-mortem)
- **Why**: `sort=top` surfaces popular content (memes, celebrations). `sort=relevance` surfaces content that matches your actual query.

### restrict_sr=on is mandatory
- **Finding**: Without `restrict_sr=on`, Reddit API returns r/all results. Net neutrality posts, unrelated subreddits.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch debugging session
- **Confidence**: systematic
- **Implication**: ALWAYS include `restrict_sr=on` when searching a specific subreddit.

### Pain verbs beat solution terms
- **Finding**: "ignores CLAUDE.md" finds pain points. "CLAUDE.md best practices" finds guides. Symptom language discovers problems; solution language discovers tutorials.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch pattern analysis
- **Confidence**: systematic (AutoSearch post-mortem)
- **Pain verbs that work**: ignores, breaks, forgets, loses, violates, deletes, overwrites, fails
- **Solution terms to avoid** (when looking for pain points): best practices, how to, guide, tutorial

### Emotional queries fail
- **Finding**: "frustrating", "hate", "terrible" don't find pain points. Specific symptom descriptions do.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch post-mortem analysis (winner/loser classification)
- **Confidence**: systematic
- **Why**: People don't title posts with emotions. They describe what happened.

### First-person narrative patterns match success stories
- **Finding**: "I told it" matches bragging/success posts, not complaints.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch post-mortem
- **Confidence**: systematic
- **Implication**: Avoid "I + past tense" patterns when searching for problems.

## Subreddit Selection Guide

| Topic | Subreddits |
|-------|-----------|
| Claude / AI coding agents | r/ClaudeCode, r/ClaudeAI |
| Cursor | r/cursor |
| General AI coding | r/ChatGPTCoding |
| Programming | r/programming, r/webdev, r/reactjs, r/typescript |
| AI general | r/LocalLLaMA, r/artificial |

Choose based on the product/topic in the requirement. Don't search r/all.

## Engagement Scoring

```
engagement = score + num_comments
```

Both fields available in Reddit JSON API response (`data.score`, `data.num_comments`).

## Known Failures

| Query Pattern | Why It Fails | Date |
|--------------|-------------|------|
| Emotional language ("hate", "terrible") | Doesn't match how people title posts | 2026-03-21 |
| First-person narrative ("I told it") | Matches success stories, not complaints | 2026-03-21 |
| Missing `restrict_sr=on` | Returns r/all noise | 2026-03-21 |
| `sort=top` for pain point discovery | Surfaces popular, not relevant | 2026-03-21 |

## Unvalidated

(None currently)
