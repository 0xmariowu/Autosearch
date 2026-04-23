---
name: linkedin
description: LinkedIn public pages — company profiles, job posts, professional articles via Jina Reader (no auth needed for public content).
version: 1
languages: [en, mixed]
methods:
  - id: via_jina
    impl: methods/via_jina.py
    requires: []
    rate_limit: {per_min: 5, per_hour: 30}
fallback_chain: [via_jina]
when_to_use:
  query_languages: [en, mixed]
  query_types: [career, company, professional, job]
  domain_hints: [career, hiring, company-research, professional]
quality_hint:
  typical_yield: low
  chinese_native: false
layer: leaf
domains: [professional]
scenarios: [company-research, job-search, professional-profiles]
model_tier: Fast
experience_digest: experience.md
tier: 0
---

## Overview

LinkedIn public content via Jina Reader. Useful for company profiles, public job posts, and professional articles. Requires no authentication for public pages.

## Known Quirks

- Only public content is accessible
- Rate limited — 5 requests/min
- For deeper access (private profiles, search), linkedin-scraper-mcp is needed


# Quality Bar

- Evidence has non-empty url and title.
- Returns empty list gracefully when Jina Reader is unavailable.
