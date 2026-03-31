---
name: search-google-scholar
description: "Use when the task needs comprehensive academic paper search with citation counts, or when arXiv and Semantic Scholar miss relevant papers."
---

# Platform

Google Scholar — broadest academic search engine. Covers journals, conferences, preprints, theses, books, and patents. Includes citation counts.

# When To Choose It

Choose this when:

- need comprehensive academic coverage beyond arXiv
- want to find papers by citation count (most cited = most influential)
- searching for survey papers or literature reviews
- looking for papers from non-CS venues (social science, economics, etc.)
- Semantic Scholar returned too few results

# How To Search

- `site:scholar.google.com {academic keywords}`
- Add year for recency: `{topic} 2025 2026`

Example queries:
- `site:scholar.google.com "self-evolving agent" survey 2025`
- `site:scholar.google.com LLM self-improvement reinforcement learning`
- `site:scholar.google.com agent memory architecture long-term`

# Standard Output Schema

- `source`: `"google-scholar"`

# Date Metadata

Scholar results show year. Extract from snippet.

# Quality Bar

This skill is working when it discovers influential papers (high citation count) that keyword-based arXiv search misses.
