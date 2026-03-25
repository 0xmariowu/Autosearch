# Search Methodology — Changelog

## 2026-03-24

### New Platform: alphaXiv MCP
- **Added**: `platforms/alphaxiv.md` — alphaXiv MCP usage patterns for paper discovery, paper reading, PDF QA, and paper-linked code exploration
- **Added**: `INDEX.jsonl` entry for `platforms/alphaxiv.md`
- **Why**: AutoSearch needed a documented academic-evidence source that complements Exa's broad discovery with paper-native retrieval and analysis
- **Impact**: future search and deep-research flows can distinguish general discovery from paper-first research work

## 2026-03-23

### Initial build: principles + methods + platforms
- **Added**: `CLAUDE.md` — AI operations manual for the search-methodology directory
- **Added**: `principles.md` — evidence standards with 3-channel reliability framework
- **Added**: `methods/2026-03-21-github-fingerprint-search.md` — moved from `AIMD/cross-project/`, updated frontmatter to method format
- **Added**: `platforms/github.md` — GitHub search patterns (code search, issues, repos, Exa complement)
- **Added**: `platforms/reddit.md` — Reddit patterns (sort=relevance, pain verbs, subreddit guide)
- **Added**: `platforms/hackernews.md` — HN patterns (quoted names, no modifiers, Show HN filter)
- **Added**: `platforms/exa.md` — Exa patterns (semantic discovery, site-scoped, cross-platform)
- **Added**: `platforms/twitter.md` — Twitter patterns (xreach unreliable, Exa→xreach workflow)
- **Added**: `platforms/huggingface.md` — HF patterns (2-keyword API limit, author chain, Exa fallback)
- **Added**: `INDEX.jsonl` — grep-able index of 8 content files (excludes ops files: CLAUDE.md, INDEX.jsonl, CHANGELOG.md)
- **Why**: Consolidate scattered search knowledge (from autosearch/CLAUDE.md, platforms.md, patterns.jsonl, cross-project/) into a single AI-friendly knowledge base with governance rules
- **Source data**: 15 validated patterns from `~/Dev/autosearch/patterns.jsonl`, 46 evolution experiments from `evolution.jsonl`, 30 playbook queries from `playbook-final.jsonl`
