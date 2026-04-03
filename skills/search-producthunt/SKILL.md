---
name: search-producthunt
description: "Use when the task needs to discover new product launches, startups, and tools — especially products launched in the last 6 months that Claude's training data misses."
---

# Platform

Product Hunt — daily feed of new tech product launches. Community upvotes surface the most interesting products. Essential for discovering recent tools and startups.

# When To Choose It

Choose this when:

- searching for new tools or products in a category
- need to find recent startup launches (last 6 months)
- want community reception and upvote signals for a product
- looking for alternatives to a known product

# How To Search

- `site:producthunt.com {product category keywords}`
- Add year for freshness: `{category} 2026`

Example queries:
- `site:producthunt.com AI agent self-improving 2026`
- `site:producthunt.com LLM search tool`
- `site:producthunt.com AI research assistant`

# Standard Output Schema

- `source`: `"producthunt"`

# Date Metadata

Product Hunt launches have clear dates. Extract from snippet.

# Quality Bar

This skill is working when it discovers recently launched products that neither GitHub search nor general web search surfaces.
