---
name: search-paper-list
description: "Use when you need to discover academic papers through curated GitHub paper lists, awesome-lists, and survey reference collections rather than direct search engine queries."
---

# Platform

GitHub repository search and content fetching.
This is a free platform skill that combines `gh search repos` with `WebFetch` to mine curated paper collections.

# When To Choose It

Choose this when:

- you need papers on a specific topic that are curated by researchers
- keyword search keeps returning the seed paper instead of citing work
- you want to find papers grouped by sub-topic within a research area
- citation graph traversal returns too many loosely related papers
- you need to discover survey papers and their organized reference lists
- the topic has well-known GitHub awesome-lists or paper-list repositories

This skill fills the gap between `search-citation-graph.md` (API-level citation traversal) and `search-github-repos.md` (code repository discovery). Paper-list repos are neither code nor citations -- they are human-curated evidence collections.

# Strategy

## Phase 1: Find Paper List Repos

Search GitHub for curated paper collections on the target topic.

Query patterns that work:
- `{topic} paper list` (e.g., "LLM agent paper list")
- `awesome {topic}` (e.g., "awesome LLM agents")
- `{topic} survey papers` (e.g., "self-reflection survey papers")
- `{topic} reading list` (e.g., "AI agent reading list")
- `{specific-paper-name} related work`

Use `gh search repos` with `--sort=stars` to find the most trusted collections first.
Filter for repos with 50+ stars when possible -- lower-star paper lists are often incomplete or abandoned.

## Phase 2: Extract Papers From READMEs

For each high-value paper-list repo found:

1. Fetch the README content using WebFetch on `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` (try `master` branch if `main` fails)
2. Parse the markdown for paper entries -- look for patterns like:
   - `[Paper Title](url)` markdown links pointing to arxiv.org, openreview.net, semanticscholar.org
   - Entries with year tags like `(2025)`, `[ICLR 2026]`, `NeurIPS 2025`
   - Sections organized by topic, year, or methodology
3. Filter extracted papers for relevance to the current task
4. Prioritize papers from the last 2 years for freshness

## Phase 3: Enrich Extracted Papers

For each extracted paper:

- If the URL is an arXiv link, derive the date from the arXiv ID (YYMM.NNNNN)
- If the paper has a Semantic Scholar link, optionally fetch citation count
- Write the paper-list repo as the discovery source for provenance

# What It Is Good For

Paper-list repos are best for:

- discovering the canonical papers in a sub-field that researchers actually read
- finding papers organized by methodology or application area
- getting a human-curated quality filter on top of raw search results
- discovering papers that cite a foundational work (many paper lists group by lineage)
- finding survey papers that themselves contain organized reference lists

# What It Is Not Good For

- Finding very recent papers (paper lists have update lag)
- Finding obscure or unpublished work
- Finding non-academic resources (use web search skills for that)

# Source Tagging

Tag results from this skill as `"paper-list"` to distinguish them from direct GitHub repo search results. This adds a new source class for diversity scoring.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- `url`: paper URL (arxiv, openreview, semanticscholar, or conference site)
- `title`: paper title as listed in the curated collection
- `snippet`: paper description or abstract excerpt from the list
- `source`: `"paper-list"`
- `query`: the search query or paper-list repo that surfaced this
- `metadata.llm_relevant`: true/false after evaluation
- `metadata.llm_reason`: one sentence justification
- `metadata.published_at`: paper publication date in ISO 8601
- `metadata.paper_list_repo`: the GitHub repo URL where this paper was found
- `metadata.paper_list_section`: the section heading under which the paper appeared

# Date Metadata

- For arXiv papers: derive from arXiv ID (YYMM.NNNNN -> 20YY-MM-01)
- For conference papers: use conference date
- For papers with explicit year tags in the list: use that year
- Write to `metadata.published_at` in ISO 8601 format

# Quality Bar

This skill is working when it discovers relevant papers that were NOT found by direct web search or citation graph traversal. The unique value is human curation -- if the same papers could have been found with a simple web search query, the skill is not adding value. Measure by checking how many results from this skill are unique (not duplicated in other sources).
