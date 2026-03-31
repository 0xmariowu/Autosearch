---
name: search-hackernews
description: "Use when the task needs tech-launch discussion, developer reaction, startup signal, or historically high-signal technical threads from the Hacker News Algolia API."
---

# Platform

Hacker News search through the Algolia API.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- developer discussion around launches or tools
- startup and product-validation signal
- high-signal comment threads from a technical audience
- fast retrieval of known products or companies

HN is especially useful for product names, launches, and technical zeitgeist.

# API Surface

This restores the V1 Hacker News connector through the Algolia search API.

Think in terms of story-level retrieval:

- title
- URL
- HN item URL
- points
- `num_comments`
- created time
- story tags such as launch-related variants

# What It Is Good For

HN is best for:

- launches and breakout products
- developer adoption signals
- high-value discussion threads
- startup and infrastructure trend sensing

It is weaker for broad general-web coverage and weaker than Reddit for everyday consumer opinion.

# Quality Signals

Prioritize results with:

- higher points
- higher `num_comments`
- recent stories when freshness matters
- titles that mention exact products, companies, or project names
- Show HN posts only when they crossed enough community validation

Down-rank results when:

- the query only matches a broad abstract concept
- the post is a low-point self-promo thread
- the title has a weak keyword overlap

# Known V1 Patterns

Patterns already validated in state:

- Quote exact product names. This was worth roughly a 100x retrieval difference in V1.
- Avoid abstract concept queries. HN users talk about products and companies, not broad category prose.
- Filter weak Show HN posts. Show HN items under about 100 points were usually self-promotion rather than community-validated signal.

This is one of the most pattern-sensitive platforms in the system.
Prefer exact named entities over conceptual descriptions.

# Rate Limits And Requirements

Requirements:

- no paid API key for Algolia HN search

The public API is usually easy to use, but treat it as a shared service.
Do not waste rounds on many trivial query variations.

# Output Expectations

Return story-shaped evidence.
Each result should normally preserve:

- title
- target URL when present
- HN discussion URL
- points
- comment count
- created time
- short relevance note

Expect this source to contribute strong developer-discussion signal when exact products are known.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema.
Map the story-level fields above into that schema rather than inventing a platform-specific output shape.

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"hn"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, and date fields

The `source` field must be exactly `"hn"` for this platform.
`judge.py` uses `source` for diversity scoring, so inconsistent tags reduce the diversity dimension.

After collecting results, pass them to [normalize-results.md](normalize-results.md) for cross-platform dedup and [extract-dates.md](extract-dates.md) for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write them into `metadata`.
For Hacker News, the story created time is the primary source for creation metadata.

- `metadata.published_at`: when the content was created (ISO 8601)
- `metadata.updated_at`: when the content was last modified (ISO 8601)
- `metadata.created_utc`: creation timestamp (ISO 8601)

See [extract-dates.md](extract-dates.md) for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.

# Quality Bar

This platform skill is working when results have accurate source tags, populated date metadata, and conform to the canonical evidence schema defined in normalize-results.md.
