---
name: instagram
description: Instagram public posts and reels search via TikHub. Best for product demos, tutorials, and visual content. English-first but works with any language keyword.
version: 1
languages: [en, mixed]
methods:
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
fallback_chain: [via_tikhub]
when_to_use:
  query_languages: [en, zh, mixed]
  query_types: [tutorial, product, brand, lifestyle, visual-demo]
  avoid_for: [academic-papers, code-repositories, technical-docs]
quality_hint:
  typical_yield: medium
  content_type: visual-posts
layer: leaf
domains: [social, lifestyle, consumer, brand]
scenarios: [product research, brand monitoring, tutorial discovery]
model_tier: Fast
experience_digest: experience/experience.md
---

Use this channel to search Instagram posts and reels for a keyword.
Returns post URL, caption text, and author username.

## When to use

- Product demos and tutorials
- Brand/influencer research
- Consumer lifestyle content
- Visual how-to content

## When NOT to use

- Academic research (use arxiv/pubmed)
- Code search (use github/stackoverflow)
- News (use ddgs/google_news)

## MCP tool example

```
run_channel("instagram", "Python machine learning tutorial", k=10)
```

# Quality Bar

- ≥3 results with valid `instagram.com/p/...` URLs
- Caption text extracted into `title` / `snippet`
- `source_channel = "instagram:{username}"`
