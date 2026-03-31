---
name: search-github-repos
description: "Use when the task is best answered by open-source repositories, libraries, frameworks, SDKs, or active code projects discoverable through GitHub repository search."
---

# Platform

GitHub repository search through `gh search repos`.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- open-source frameworks, libraries, SDKs, tools, and starter repos
- implementation ecosystems around a topic
- active maintainer and adoption signals from code-hosting metadata
- fast filtering by language, stars, and recency

This should usually be one of the first platforms for code-first tasks.
It is especially strong when the user wants real projects rather than discussion.

# API Surface

This skill restores the V1 GitHub repository connector.
The underlying capability is GitHub search via the GitHub CLI.

Think in terms of repository-level retrieval:

- repository name and owner
- description
- stars and forks
- primary language
- updated time
- topics and homepage when available

# What It Is Good For

GitHub repo search is best for:

- finding canonical libraries in a category
- discovering active frameworks by topic
- comparing competing implementations
- spotting momentum through recent updates and star velocity proxies

It is weaker for nuanced pain points or support issues than issue search.

# Quality Signals

Prioritize results with:

- higher stars, especially when matched with recent activity
- recent `updatedAt` values when freshness matters
- clear, specific repository descriptions rather than vague taglines
- a language match that fits the task
- recognizable org or maintainer names when trust matters
- topic tags or repo names that tightly match the query

Down-rank results when:

- the description is missing or generic
- the repo looks abandoned
- the match is only a weak keyword collision
- the language is irrelevant to the user's likely stack

# Known V1 Patterns

Patterns already validated in state:

- Direct topic search on GitHub yields high relevance for framework discovery tasks.
- Exact phrase queries can work unusually well for narrow concepts. One saved example is `self-evolving AI agent`, which produced highly relevant repos.

Use that lesson to prefer specific topic anchors over long natural-language questions.

# Rate Limits And Requirements

Requirements:

- GitHub CLI available
- authentication is strongly preferred for stable search behavior and quota headroom

Rate limiting is governed by GitHub search quotas.
Repository search is usually practical for normal research runs, but it is not an unlimited crawl interface.
Avoid wasting budget on many near-duplicate queries.

# Output Expectations

Return repository-shaped evidence.
Each result should normally preserve:

- repo name or `owner/name`
- GitHub URL
- description
- stars
- primary language
- last update time
- short note on why it matched

Write date metadata for freshness scoring.
The `updatedAt` field from `gh search repos` is available for every result.
Write it to `metadata.updated_at` in ISO 8601 format.
If `createdAt` is also available, write it to `metadata.created_utc`.
The judge uses these fields for the freshness dimension — missing dates score as zero freshness.

Expect strong precision for code ecosystems and decent recall when the query uses concrete topic nouns.
