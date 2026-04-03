---
name: search-papers-with-code
description: "Use when the task needs academic papers that have associated code implementations, or when you want to find code for a known paper."
---

# Platform

Papers With Code — links machine learning papers to their code implementations, benchmarks, and datasets. Essential for finding reproducible research.

# When To Choose It

Choose this when:

- need papers that come with working code (not just theory)
- want to find the reference implementation of a method
- looking for benchmark results and leaderboards
- searching for datasets associated with a research area

# How To Search

- `site:paperswithcode.com {research topic}`

Example queries:
- `site:paperswithcode.com self-evolving agent`
- `site:paperswithcode.com LLM self-improvement benchmark`
- `site:paperswithcode.com agent memory architecture`

# Standard Output Schema

- `source`: `"papers-with-code"`

# Date Metadata

Papers have publication dates. Extract year from title or snippet.

# Quality Bar

This skill is working when it discovers paper+code pairs that separate arXiv or GitHub searches would miss the connection between.
