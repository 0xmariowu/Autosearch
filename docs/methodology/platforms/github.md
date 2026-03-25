---
title: GitHub — Search Patterns & Validated Knowledge
date: 2026-03-23
project: search-methodology
type: platform
tags: [github, code-search, issues, repos]
status: active
---

# GitHub

## What It's Best For

- **Code search**: finding specific file signatures, field names, path patterns in public repos
- **Issues**: bug reports, feature requests, reproducible problems with real discussion
- **Repos**: discovering tools, frameworks, reference implementations

## Access Methods

| Method | API / Tool | Best For |
|--------|-----------|----------|
| `gh search code` | GitHub CLI | Precise file content + path matching (fingerprint search) |
| `gh search issues` | GitHub CLI | Issue discovery by keyword, sortable by comments |
| `gh search repos` | GitHub CLI | Repo discovery by keyword, sortable by stars |
| Exa + `site:github.com` | Exa semantic search | Natural language discovery — finds things keyword search misses |
| `gh api` | REST API | Reading specific repo trees, file contents, metadata |

## Validated Patterns

### Exa beats gh search for discovery
- **Finding**: Exa found 8/8 relevant GitHub issues in one query. `gh search issues` found 0 for the same topic.
- **Date validated**: 2026-03-21
- **How validated**: Side-by-side comparison during AutoSearch session
- **Confidence**: multiple tests
- **Implication**: Use Exa for discovery (finding what exists), `gh search` for precision (finding specific content). They complement, not compete.

### gh search code is unmatched for file signatures
- **Finding**: `gh search code "path:.claude/statsig"` returns exact repos containing that path. No other tool can do this.
- **Date validated**: 2026-03-21
- **How validated**: Reverse fingerprint search campaign (see methods/2026-03-21-github-fingerprint-search.md)
- **Confidence**: systematic (70+ repos found)
- **Implication**: For known file structures, `gh search code` with `path:` filter is the gold standard.

### Sort issues by comments, not reactions
- **Finding**: `--sort comments` surfaces issues with real discussion. `--sort reactions` surfaces popular but often shallow issues.
- **Date validated**: 2026-03-21
- **How validated**: AutoSearch engine comparison
- **Confidence**: multiple tests

### Multi-repo search for competitive analysis
- **Finding**: Searching the same query across competing repos reveals shared pain points.
- **Date validated**: 2026-03-21
- **How validated**: Searched `anthropics/claude-code`, `getcursor/cursor`, `paul-gauthier/aider` for same issues
- **Confidence**: multiple tests
- **Repos to cross-check**: anthropics/claude-code, getcursor/cursor, paul-gauthier/aider, continuedev/continue, windsurf-ai/windsurf

### Tree API for repo structure assessment
- **Finding**: `gh api repos/OWNER/REPO/git/trees/HEAD?recursive=1` returns full file tree. Pipe through `jq` to count file types, assess repo size/structure before cloning.
- **Date validated**: 2026-03-21
- **How validated**: Used during fingerprint search to assess data volume before clone
- **Confidence**: systematic

## Rate Limits

- `gh search code`: ~30 requests/minute, results capped at ~1000 per query
- `gh search issues/repos`: similar limits
- `gh api`: 5000 requests/hour (authenticated)

## Known Failures

| Query Pattern | Why It Fails | Date |
|--------------|-------------|------|
| Generic keywords in code search | Too many results, mostly noise | 2026-03-21 |
| `gh search code` without `path:` or `--extension` | Returns random matches across all repos | 2026-03-21 |

## Unvalidated

(None currently)
