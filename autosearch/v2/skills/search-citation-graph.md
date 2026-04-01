---
name: search-citation-graph
description: "Use when you know a foundational paper and want to discover all follow-up work that cites it or all references it builds on."
---

# Platform

Semantic Scholar API (free, no key required for basic search).
This is a specialized platform skill for academic citation traversal.

# When To Choose It

Choose this when you need:

- all papers that cite a known foundational work
- all references a paper builds on
- the citation chain between two papers
- to discover the "descendants" of a technique

This is especially powerful after systematic-recall.md identifies foundational papers — you can find everything that built on them since publication.

# API Surface

Semantic Scholar provides:

- Paper search by title or arXiv ID
- Citation list (papers that cite this one)
- Reference list (papers this one cites)
- Author search and author's paper list

Base URL: `https://api.semanticscholar.org/graph/v1/`

Key endpoints:
- `GET /paper/search?query={title}` → find paper ID
- `GET /paper/{paper_id}/citations` → who cites this paper
- `GET /paper/{paper_id}/references` → what this paper cites
- `GET /paper/arXiv:{arxiv_id}` → lookup by arXiv ID directly

# What It Is Good For

- Discovering the full "family tree" of a technique
- Finding the latest work in a sub-field (recent citations of a foundational paper)
- Verifying that a paper is real and checking its actual citation count
- Building a complete literature map from a few seed papers

# Rate Limits And Requirements

- No API key required for basic access
- Rate limit: 100 requests per 5 minutes (without key)
- With API key (free registration): higher limits
- Request via `curl` or `WebFetch` to the API endpoint

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: semantic scholar paper URL or arXiv URL
- `title`: paper title
- `snippet`: abstract or first sentence
- `source`: `"semantic-scholar"`
- `query`: the seed paper title or ID
- `metadata`: object with `llm_relevant`, `llm_reason`, date fields, `citations` count

# Date Metadata

- `metadata.published_at`: paper publication date (from API `year` field)
- `metadata.citations`: citation count (from API `citationCount` field)

# Quality Bar

This platform skill is working when it discovers papers that web search and arXiv search miss — especially recent papers that cite foundational works.
