---
name: search-exa
description: "Use when the task needs high-quality semantic web search, strong paraphrase matching, or premium search precision across the open web through Exa."
---

# Platform

Exa semantic search API, accessed through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- semantic matches that keyword search may miss
- premium web search quality
- better first-pass precision on research-heavy tasks
- site-filtered semantic search across chosen domains

Use this when retrieval quality matters enough to justify API spend.

# API Surface

This restores the V1 Exa connector through the local `mcporter` interface.

Treat Exa as semantic web retrieval with result fields such as:

- title
- URL
- snippet or summary
- domain
- optional metadata depending on the endpoint

# What It Is Good For

Exa is best for:

- semantically phrased search over the web
- hard recall problems where keywords are brittle
- premium-quality discovery when free platforms are noisy
- filtered search across specific sites or source classes

It is especially useful when the user's concept can be phrased many ways across the wild web.

# Quality Signals

Prioritize results with:

- high semantic fit to the user intent
- trustworthy domains
- titles and snippets that mention the target mechanism, not just a loose keyword
- source diversity across different sites

Down-rank results when:

- many results are semantic cousins but not task-relevant
- domain trust is weak
- the result repeats evidence already found on free sources

# Known V1 Patterns

Patterns already validated in state:

- Exa outperformed GitHub issue search on at least one issue-discovery task, finding strong matches where `gh search issues` found none.

Take that seriously for semantically indirect search problems.
If keyword search keeps missing likely evidence, route to Exa early.

# Rate Limits And Requirements

Requirements:

- `EXA_API_KEY`
- `mcporter` available in the environment

This is a paid API.
Budget usage should be intentional, especially when many follow-up queries are possible.
Prefer compact, high-information queries over brute-force paraphrase sweeps.

# Output Expectations

Return web-result evidence.
Each result should normally preserve:

- title
- URL
- snippet
- domain
- short semantic-fit note

Expect Exa to contribute fewer but cleaner candidates than broad free search layers.
