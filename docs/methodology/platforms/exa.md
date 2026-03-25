---
title: Exa — Search Patterns & Validated Knowledge
date: 2026-03-23
project: search-methodology
type: platform
tags: [exa, semantic-search, discovery, cross-platform]
status: active
---

# Exa

## What It's Best For

- **Semantic discovery**: finding things keyword search can't reach
- **Cross-platform discovery**: GitHub issues, blog posts, research papers in one query
- **Site-scoped search**: `site:github.com`, `site:reddit.com`, `site:x.com` to find content on specific platforms via natural language

## Access Methods

| Method | API / Tool | Best For |
|--------|-----------|----------|
| mcporter | `mcporter call 'exa.web_search_exa(query: "...", numResults: 10)'` | Programmatic access from AutoSearch engine |
| Firecrawl MCP | `firecrawl_search` | Conversational use within Claude Code |

## Validated Patterns

### Natural language queries outperform keywords
- **Finding**: Exa is a semantic search engine. Describe what you want in natural language, don't just list keywords.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch comparison
- **Confidence**: multiple tests
- **Good**: "coding agent that loses context in long conversations"
- **Bad**: "agent context loss long"

### Exa beats gh search for GitHub issues
- **Finding**: Exa found 8/8 relevant GitHub issues in one query. `gh search issues` found 0.
- **Date validated**: 2026-03-21
- **How validated**: Side-by-side comparison
- **Confidence**: multiple tests
- **Implication**: Default to Exa for GitHub issue discovery, use `gh search` only for precise content/path matching.

### Site-scoped search for platform-specific discovery
- **Finding**: Adding `site:x.com` or `site:reddit.com` to Exa queries effectively searches those platforms with semantic understanding.
- **Date validated**: 2026-03-21
- **How validated**: Twitter discovery workflow (see platforms/twitter.md)
- **Confidence**: systematic
- **Pattern**: Use Exa + `site:` to discover URLs, then use platform-native tools to read full content.

### HuggingFace semantic discovery
- **Finding**: Exa with natural language like "coding agent trajectory tool-use dataset" finds HF datasets better than HF API with keyword limits.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch comparison
- **Confidence**: multiple tests

## Engagement Scoring

Exa does **not** provide engagement data. It contributes URLs for discovery. Engagement must be verified on the source platform.

```
Exa finds URL → read URL on source platform → get engagement from source
```

## Output Format

mcporter returns plain text blocks (Title / URL / Published), **not JSON**. AutoSearch engine parses this text format.

## Known Failures

| Query Pattern | Why It Fails | Date |
|--------------|-------------|------|
| Very short keyword queries | Exa is semantic — needs context to work well | 2026-03-21 |

## Unvalidated

(None currently)
