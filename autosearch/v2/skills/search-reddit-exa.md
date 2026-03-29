---
name: search-reddit-exa
description: "Use when the task needs semantic Reddit discovery with `site:reddit.com`, especially when keyword Reddit search misses relevant discussions or phrasing is highly variable."
---

# Platform

Exa semantic search with a `site:reddit.com` filter, accessed through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- Reddit discussion discovery beyond brittle keyword matching
- semantically similar complaint or comparison threads
- broader Reddit recall than the native search surface provides

Use this when native Reddit search is too literal or when you do not know the likely subreddit in advance.

# API Surface

This restores the V1-style premium Reddit connector by routing Exa to Reddit pages only.

Treat it as Reddit-thread retrieval with Exa semantics.
Expected fields are still web-like:

- title
- URL
- snippet
- domain

Thread-level Reddit metadata may need enrichment separately if score or comment count is required.

# What It Is Good For

This platform is best for:

- semantic Reddit discovery
- complaint and comparison mining
- recovering threads that keyword search missed
- widening subreddit coverage without manually enumerating communities

It is often the right escalation when Reddit public JSON search yields thin or oddly phrased results.

# Quality Signals

Prioritize results with:

- clear Reddit thread titles that match the problem space
- subreddits that are obviously relevant
- snippets describing concrete symptoms, comparisons, or experience reports
- evidence of strong thread engagement after enrichment

Down-rank results when:

- the result is a weak semantic cousin
- the subreddit is irrelevant or generic
- the thread looks like spam or self-promotion

# Known V1 Patterns

Carry forward Reddit-specific V1 lessons:

- symptom language beats solution language for pain discovery
- concrete verbs outperform emotional language
- first-person narrative phrasing often surfaces brag threads instead of complaints

Using Exa does not remove the need for good Reddit-style query framing.
It mainly improves retrieval when wording varies.

# Rate Limits And Requirements

Requirements:

- `EXA_API_KEY`
- `mcporter` available

This is a paid API route.
Use it when semantic recovery is worth the cost, especially after native Reddit search underperforms.

# Output Expectations

Return Reddit-thread candidates with web-style fields:

- title
- Reddit URL
- snippet
- probable subreddit from the URL or title context
- short note on why the thread matters

Expect stronger recall than native Reddit keyword search, with engagement enrichment added afterward when needed.
