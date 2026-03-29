---
name: search-huggingface
description: "Use when the task needs Hugging Face Hub assets such as datasets, models, or spaces, with hub-native metadata like downloads, likes, and recency."
---

# Platform

Hugging Face Hub API, with V1 centered on `huggingface.co/api/datasets`.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- ML datasets
- model families or hub-native artifacts
- spaces and adjacent hub ecosystem signal
- ecosystem discovery inside the Hugging Face network

Use this when the task is specifically about ML assets rather than general web discussion.

# API Surface

This restores the V1 Hugging Face connector.
V1 primarily used the Hub API dataset surface, but the same hub-native reasoning transfers to models and spaces when those are the actual target.

Think in terms of asset-level retrieval:

- asset id
- Hub URL
- downloads
- likes
- last modified time
- author or organization
- tags and task metadata when present

# What It Is Good For

Hugging Face is best for:

- dataset discovery
- model and benchmark ecosystem scanning
- surfacing niche ML artifacts that general web search may miss
- following promising authors or collections once a strong seed is found

It is weaker than GitHub for code integration detail and weaker than DDGS for broad editorial context.

# Quality Signals

Prioritize results with:

- higher downloads
- higher likes
- recent modification when freshness matters
- trusted or recognizable authors
- tags or metadata that tightly match the task

Down-rank results when:

- engagement is near zero
- the asset is stale and unloved
- the keyword match is only incidental

# Known V1 Patterns

Patterns already validated in state:

- Keep API search terms to 1 or 2 core words. Queries with 3 or more keywords often returned empty results.
- When you find a strong dataset, check that author's other datasets and any Hugging Face Collections including it. This is a high-ROI follow-on move.

This platform rewards terse seed terms and graph-following from good results.

# Rate Limits And Requirements

Requirements:

- no paid API key required for basic Hub API access

Public access is available, but you should still avoid unnecessary query churn.
Hub-native follow-up on authors and collections is often a better use of budget than brute-force keyword expansion.

# Output Expectations

Return asset-shaped evidence.
Each result should normally preserve:

- asset id or name
- Hub URL
- downloads
- likes
- last modified time
- author
- short task-fit note

Expect this platform to contribute structured ML ecosystem evidence, especially around datasets.
