# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: github
description: Use for code-level, issue-level, and repository discovery when query involves a library, framework, or implementation detail.
version: 1
languages: [en]
methods:
  - id: search_repositories
    impl: methods/search_repos.py
    requires: [env:GITHUB_TOKEN]
    rate_limit: {per_min: 30, per_hour: 5000}
  - id: search_issues
    impl: methods/search_issues.py
    requires: [env:GITHUB_TOKEN]
    rate_limit: {per_min: 30, per_hour: 5000}
  - id: search_code
    impl: methods/search_code.py
    requires: [env:GITHUB_TOKEN]
    rate_limit: {per_min: 10, per_hour: 5000}
fallback_chain: [search_repositories, search_issues, search_code]
when_to_use:
  query_languages: [en, mixed]
  query_types: [code, library, implementation, debugging, tooling]
  avoid_for: [news, product-review, people]
quality_hint:
  typical_yield: high
  chinese_native: false
---

## Overview

GitHub is the primary channel for repository discovery, issue triage, and code search across open source software. It is the right surface when the user is asking how something is implemented, which repo is authoritative, or whether a bug already exists upstream.

For autosearch, this channel anchors developer intent to concrete artifacts instead of commentary. It matters because many technical queries are better answered by repositories, issue threads, and source snippets than by generic web summaries.

## When to Choose It

- Choose it when the query names a package, framework, SDK, CLI, or implementation pattern.
- Choose it for debugging signals such as open issues, regressions, workarounds, or maintainer discussion.
- Choose it when repository health, stars, forks, recent activity, and code examples are relevant.
- Prefer it over forum channels when the user wants source-of-truth implementation detail.
- Avoid it for general news, consumer reviews, or person-focused lookups.

## How To Search (Planned)

- `search_repositories` - Call the GitHub Search Repositories API with keyword and language qualifiers, then rank likely primary repos by relevance and activity.
- `search_issues` - Call the GitHub Search Issues API to find bug reports, feature requests, and maintainer responses tied to the query.
- `search_code` - Call the GitHub Search Code API for symbol names, config fragments, or error strings when implementation detail matters more than repo discovery.
- `search_code` - Normalize output around repository, path, snippet context, and canonical GitHub URLs for downstream evidence ranking.

## Known Quirks

- All planned methods require `GITHUB_TOKEN`; unauthenticated search is too constrained for reliable routing.
- Code search is usually the tightest rate-limited method, so it belongs later in the fallback chain.
- Repository popularity can overwhelm niche but relevant results if ranking is not intent-aware.
- Issue search returns mixed issue and PR style records, so later impls should normalize thread type carefully.
