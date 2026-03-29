---
name: search-searxng
description: "Use when the task needs free meta-search across multiple engines through a local SearXNG instance, especially for broad web expansion and source diversity."
---

# Platform

Local SearXNG over HTTP.
Read the endpoint from `SEARXNG_URL`, defaulting to `http://localhost:8888`.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- a self-hosted meta-search layer
- broader web coverage than one engine alone
- diversity across multiple search backends
- a local replacement when other free web search paths are limited

Use this when local infrastructure is available and broad web recall matters.

# API Surface

This restores the V1-style SearXNG connector.

Treat it as meta-search over multiple engines.
Result fields typically include:

- title
- URL
- content snippet
- engine or source attribution when returned

# What It Is Good For

SearXNG is best for:

- broad web expansion
- source diversity
- adding a local, no-key search layer
- collecting candidate URLs for later quality filtering

It is weaker than platform-native APIs for engagement metadata and weaker than semantic APIs for hard paraphrase matching.

# Quality Signals

Prioritize results with:

- strong title match
- trustworthy domains
- snippets that clearly include target entities
- engine diversity when multiple backends surface different high-quality URLs

Down-rank results when:

- many results collapse to the same domain
- the instance returns noisy or spam-heavy engines
- snippets are vague and low-information

# Known V1 Patterns

No specific SearXNG pattern is saved in state.
Apply the general web-search lessons:

- prefer concrete query anchors
- use time qualifiers only when freshness is actually needed
- value new URLs over repeated high-volume duplicates

# Rate Limits And Requirements

Requirements:

- a local SearXNG instance must be running
- `SEARXNG_URL` may override the default port and host

This platform is free in API-cost terms, but its quality depends on local configuration and engine health.
Treat provider health as dynamic.

# Output Expectations

Return web-result evidence.
Each result should normally preserve:

- title
- URL
- snippet
- optional engine attribution
- short relevance note

Expect SearXNG to act as a diversity and recall layer rather than a final authority.
