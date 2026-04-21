---
name: channels-generic-web
description: General-purpose web search — DDGS (keyword, free), Exa (semantic, paid), Tavily (research, paid), SearXNG (self-hosted meta-search), Hacker News via Exa, RSS feeds.
layer: group
domains: [web-search, generic]
scenarios: [general-search, fallback, rss-feed, serp-aggregation]
model_tier: Fast
experience_digest: experience.md
---

# Generic Web Search Channels

Broad web coverage and RSS. Default fallbacks when no specialized channel fits, and the base layer for every research task that is not narrowly scoped to one surface.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-ddgs` | Free keyword search (DuckDuckGo) | Fast | free |
| `search-exa` | Semantic web search (best for paraphrase queries) | Fast | Exa key (paid) |
| `search-tavily` | Research-oriented paid search | Fast | Tavily key (paid) |
| `search-searxng` | Self-hosted meta-search aggregator | Fast | self-hosted |
| `search-hn-exa` | HN threads via Exa semantic | Fast | free (also in community-en) |
| `search-rss` | Arbitrary RSS / Atom feed polling | Fast | free |

## Routing notes

- When the query phrasing is **unknown / paraphrased**, prefer `search-exa` or `search-tavily` over keyword `search-ddgs`.
- When BYOK paid keys are missing: fall back to `search-ddgs` + `mcporter`-routed free Exa tier.
- For news / blog tracking, `search-rss` is cheapest; for ad-hoc search use Tavily.
- SearXNG is an opt-in self-hosting path for privacy / censorship-free meta-search.
