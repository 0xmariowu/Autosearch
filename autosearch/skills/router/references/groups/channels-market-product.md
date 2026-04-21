---
name: channels-market-product
description: Business intelligence — Crunchbase (companies + funding), Product Hunt (launches), G2 (software reviews).
layer: group
domains: [market, product]
scenarios: [company-profile, funding-check, competitor-map, product-launch, review-aggregation]
model_tier: Fast
experience_digest: experience.md
---

# Market & Product Channels

Company profiles, funding, product launches, user reviews.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-crunchbase` | Company / funding / investor profile | Fast | free tier |
| `search-producthunt` | Recent product launches (last 6 months+) | Fast | free |
| `search-g2-reviews` | Software user reviews with ratings | Fast | free |

## Routing notes

- For new products Claude's training data misses (launched last 6 months), `search-producthunt` is the go-to.
- Combine with `channels-generic-web` (`search-exa` / `search-tavily`) for richer company background.
- G2 reviews are business-user facing; for consumer product reviews use `channels-chinese-ugc` (`search-xiaohongshu`) for Chinese market.
