---
name: channels-community-en
description: English developer communities — Stack Overflow, Hacker News, dev.to, Reddit (keyword + Exa semantic), HN via Exa.
layer: group
domains: [english-community, developer]
scenarios: [programming-qna, tech-discussion, community-opinion, launch-reaction]
model_tier: Fast
experience_digest: experience.md
---

# English Community Channels

English-language developer and tech community discussions.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-stackoverflow` | Programming Q&A, error messages, API usage | Fast | free |
| `search-hackernews` | HN threads by keyword (Algolia) | Fast | free |
| `search-hn-exa` | HN threads by semantic meaning (Exa) | Fast | free |
| `search-devto` | Developer blog articles and tutorials | Fast | free |
| `search-reddit` | Reddit keyword search | Fast | free |
| `search-reddit-exa` | Reddit semantic search (via Exa) | Fast | free |

## Routing notes

- Stack Overflow for **specific error messages**; HN / Reddit for **discussion, opinions, comparisons**.
- When keyword search misses likely-phrasing variants, prefer the `*-exa` semantic variants (`hn-exa`, `reddit-exa`).
- For Chinese equivalents, see `channels-chinese-ugc` (`search-v2ex` for dev community, `search-zhihu` for deep Q&A).
