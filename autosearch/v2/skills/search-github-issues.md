---
name: search-github-issues
description: "Use when the task needs bug patterns, user pain points, support friction, or feature requests from GitHub issues and discussions surfaced through GitHub issue search."
---

# Platform

GitHub issue search through `gh search issues`.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- recurring bug reports
- feature requests and roadmap pressure
- concrete symptoms users report against a project
- evidence of implementation gaps or adoption friction

Use it after repo search when you already know likely repositories, or early when the task is specifically about problems rather than solutions.

# API Surface

This restores the V1 GitHub issues connector through GitHub CLI search.

Think in terms of issue-level retrieval:

- issue title
- URL
- repository context
- state
- comment count
- updated time
- labels when available

Treat repository context as part of the evidence.
The same issue text means different things in a niche experimental repo versus a large production library.

# What It Is Good For

GitHub issues are best for:

- bug pattern discovery
- feature demand
- integration pain points
- upgrade breakage
- maintainer response patterns

This source is stronger than repo search for failure modes, but weaker for broad web context or social perception.

# Quality Signals

Prioritize issues with:

- higher comment counts, because active threads often indicate real pain or importance
- recent activity when the task cares about current behavior
- issue titles that use concrete symptoms
- repository context from a credible or widely used project
- labels such as `bug`, `feature request`, `help wanted`, or `breaking`

Down-rank issues when:

- the thread is stale and unresolved in a dead repo
- the issue is a one-off local environment problem
- there is no meaningful repo context

# Known V1 Patterns

Patterns already validated in state:

- Exa beat GitHub issue search for at least one hard issue-discovery task, finding strong matches where `gh search issues` found none.

Treat that as a routing hint, not a reason to skip this platform entirely.
Use GitHub issues when keyword matching is likely to work and the repo ecosystem matters.
Escalate to Exa when issue phrasing is likely to be varied or semantically indirect.

# Rate Limits And Requirements

Requirements:

- GitHub CLI available
- authentication preferred

Issue search shares GitHub search quota behavior.
Do not spray large numbers of paraphrases when a few symptom-led queries will do.

# Output Expectations

Return issue-shaped evidence.
Each result should normally preserve:

- issue title
- URL
- repository name
- state
- comment count
- updated time
- concise relevance note

Good output from this platform should help explain what users are struggling with, not just that a repository exists.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: canonical URL
- `title`: result title
- `snippet`: description or summary
- `source`: `"github"`
- `query`: the query that found this
- `metadata`: object with `llm_relevant`, `llm_reason`, and date fields

The source field must be exactly `"github"` for this platform.
`judge.py` uses `source` for diversity scoring, so inconsistent tags hurt the diversity dimension.

Preserve issue-specific context inside the schema where useful, especially via `snippet` and `metadata`.
After collecting results, pass them to `normalize-results.md` for cross-platform dedup and `extract-dates.md` for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to `metadata`:

- `metadata.published_at` — when the content was created (ISO 8601)
- `metadata.updated_at` — when the content was last modified (ISO 8601)
- `metadata.created_utc` — creation timestamp (ISO 8601)

For GitHub issues, prefer issue creation and last update timestamps from the search or fetch response when available.
See `extract-dates.md` for the full extraction priority and format rules.
Missing dates score as zero freshness in `judge.py`.
