---
name: search-linkedin
description: "Use when the task needs professional perspectives, company hiring signals, industry expert opinions, or business networking context."
---

# Platform

LinkedIn — professional network. Company pages, job postings (hiring signals), industry expert posts, professional discussions.

# When To Choose It

Choose this when:

- need professional/business perspective on a technology
- searching for what companies are hiring for (technology adoption signal)
- looking for industry expert opinions and thought leadership
- want company profiles and team information

# How To Search

## Lite Mode (always available)

- `site:linkedin.com {keywords}`
- Works for public profiles, company pages, public posts

Example queries:
- `site:linkedin.com "self-evolving agent" engineer hiring`
- `site:linkedin.com AI agent startup founder`
- `site:linkedin.com LLM tool company`

## Full Mode (when linkedin-mcp installed)

- Full profile reading
- Connection-based search
- Private post access

# Standard Output Schema

- `source`: `"linkedin"`

# Date Metadata

LinkedIn posts have dates. Extract from snippet.

# Quality Bar

This skill is working when it discovers professional insights and hiring signals that tech blogs and GitHub don't surface.
