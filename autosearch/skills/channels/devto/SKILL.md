# Skill Attribution
> Source: self-written for task F201.

---
name: devto
description: Developer blog articles tagged by technology topic, via the public dev.to API.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [tutorial, how-to, experience-report, tech-blog]
  domain_hints: [software, web-dev, devops]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [community-en]
scenarios: [developer-article, tutorial, experience-share]
model_tier: Fast
experience_digest: experience.md
---

## Overview

dev.to adds developer-written tutorials, how-to guides, experience reports, and opinionated engineering posts through its public article API. It is useful when the query benefits from practitioner blog content rather than docs, Q&A, or source repositories, especially for technology-tagged topics in software, web development, and DevOps.

## Known Quirks

- The public API is tag-based, not keyword-based, so `query.text` must be passed as `tag=` and broad free-text recall is limited.
- List responses only include `description`, not full article bodies, so evidence content is snippet-grade rather than complete post text.
- Public read access is comparatively generous, but this channel still uses a conservative fixed rate limit.
