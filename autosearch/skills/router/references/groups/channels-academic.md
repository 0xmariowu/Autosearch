---
name: channels-academic
description: Academic search — arXiv, Google Scholar, Semantic Scholar, Papers with Code, OpenReview, conference talks, citation graph, author tracking, OpenAlex, Crossref, DBLP, paper lists.
layer: group
domains: [academic]
scenarios: [literature-review, benchmark-check, citation-heavy, survey, author-profile]
model_tier: Fast
experience_digest: experience.md
---

# Academic Channels

Peer-reviewed papers, preprints, citations, benchmarks, conference materials. Strongest for deep-research tasks that require primary sources.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-arxiv` | Preprints / latest papers | Fast | free |
| `search-google-scholar` | Broad academic search with citations | Fast | free |
| `search-semantic-scholar` | Semantic paper / author search with metadata | Fast | free |
| `search-papers-with-code` | Benchmark leaderboards, code-paper pairs | Fast | free |
| `search-openreview` | Peer reviews, ICLR/NeurIPS/ICML forums | Fast | free |
| `search-conference-talks` | Conference talk videos / slides | Fast | free |
| `search-citation-graph` | Forward / backward citation exploration | Standard | free |
| `search-author-track` | Specific researcher's body of work | Fast | free |
| `search-openalex` | Metadata / entity search | Fast | free |
| `search-crossref` | DOI / publication metadata | Fast | free |
| `search-paper-list` | Curated awesome-paper collections | Fast | free |

## Routing notes

- Start with `search-arxiv` or `search-semantic-scholar` for discovery; use `search-citation-graph` (Standard) only when following up on a specific seminal paper.
- Pair with `channels-code-package` when the task asks for "paper with implementation" (use `search-papers-with-code` first).
- For conference-specific queries (e.g. "ICLR 2026 RLHF papers"), `search-openreview` is more precise than Google Scholar.
