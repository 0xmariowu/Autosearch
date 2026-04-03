---
name: search-stackoverflow
description: "Use when the task involves specific programming problems, API usage patterns, error messages, or needs community-validated technical solutions."
---

# Platform

Stack Overflow — world's largest programming Q&A site. Answers are community-voted, so top answers represent validated solutions. Strong for implementation details, error debugging, and API usage patterns.

# When To Choose It

Choose this when:

- debugging a specific error or unexpected behavior
- need community-validated implementation patterns
- looking for API usage examples with real-world edge cases
- comparing approaches to a technical problem (answers show trade-offs)

# How To Search

- `site:stackoverflow.com {technical keywords}`
- Include error messages verbatim for debugging queries
- Use tag notation for specificity: `[python] [langchain] agent memory`

Example queries:
- `site:stackoverflow.com self-evolving agent implementation python`
- `site:stackoverflow.com LLM tool calling error handling best practice`
- `site:stackoverflow.com "semantic scholar API" rate limit`

# Standard Output Schema

- `source`: `"stackoverflow"`

# Date Metadata

SO answers have creation and last-edit dates. Extract from snippet text.

# Quality Bar

This skill is working when it discovers specific, community-validated solutions that general web search returns buried in noise.
