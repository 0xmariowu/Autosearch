---
name: search-reddit
description: "Use when the task needs community opinions, user experiences, comparisons, and pain-point discussion from Reddit's public JSON search surface."
---

# Platform

Reddit public JSON search.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- community opinions and first-hand experiences
- product comparisons
- complaints, friction, and practical workarounds
- discussion intensity around a topic

This is usually a better source for perceived usefulness and failure modes than for canonical technical truth.

# API Surface

This restores the V1 Reddit connector over the public JSON endpoints.

Think in terms of post-level retrieval:

- post title
- permalink
- subreddit
- score
- `num_comments`
- created time
- snippet or selftext preview when available

# What It Is Good For

Reddit is best for:

- qualitative sentiment
- pain points in plain language
- comparisons between alternatives
- identifying what actual users complain about or praise

It is weaker for authoritative documentation and weaker than GitHub for implementation details.

# Quality Signals

Prioritize results with:

- higher score
- higher `num_comments`
- subreddit relevance to the topic
- recent posts when the ecosystem moves quickly
- titles that describe concrete symptoms or comparisons

Down-rank results when:

- the subreddit is off-topic
- the post is low-engagement or promotional
- the title uses vague or emotional language without a concrete issue

# Known V1 Patterns

Patterns already validated in state:

- `sort=relevance` produced about 5x better pain-point quality than `sort=top`.
- `restrict_sr=on` is mandatory for subreddit-specific search; otherwise results leak from `r/all`.
- Symptom language beats solution language for pain discovery. Example pattern: concrete verbs like `ignores` outperform queries about `best practices`.
- Avoid first-person narrative phrasing such as `I told it`, which skewed toward brag posts rather than complaints.

This platform is highly query-sensitive.
Use concrete symptoms and comparisons, not abstract sentiment words.

# Rate Limits And Requirements

Requirements:

- no paid API key for the public JSON surface

Unauthenticated access is still rate-limited in practice.
Use moderate pacing and avoid redundant query floods.

# Output Expectations

Return post-shaped evidence.
Each result should normally preserve:

- title
- Reddit URL or permalink
- subreddit
- score
- comment count
- created time
- short note on the discussion angle

Expect this source to explain what communities are saying and how strongly they are reacting.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"reddit"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, `date` fields

The `source` field must be exactly `"reddit"` for this platform.
`judge.py` uses `source` for diversity scoring; inconsistent tags hurt the diversity dimension.

After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to `metadata`:

- `metadata.published_at` — when the content was created (ISO 8601)
- `metadata.updated_at` — when the content was last modified (ISO 8601)
- `metadata.created_utc` — creation timestamp (ISO 8601)

See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.

# Quality Bar

This platform skill is working when results have accurate source tags, populated date metadata, and conform to the canonical evidence schema defined in normalize-results.md.
