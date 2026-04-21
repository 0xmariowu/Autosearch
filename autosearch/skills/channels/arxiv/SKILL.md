# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: arxiv
description: Use for academic preprint searches in CS/ML/physics when query is English or mixed and expects peer-reviewed or preprint papers.
version: 1
languages: [en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [academic, research-paper, literature-review, survey]
  avoid_for: [news, product-review, real-time]
quality_hint:
  typical_yield: medium-high
  chinese_native: false
layer: leaf
domains: [academic]
scenarios: [preprint, latest-paper, literature-review]
model_tier: Fast
experience_digest: experience.md
---

## Overview

arXiv is the core discovery surface for open academic preprints in computer science, machine learning, mathematics, and physics. It is useful when the user wants papers, author names, abstracts, and recent literature rather than social discussion or product sentiment.

For autosearch coverage, this channel gives the planner a clean paper-oriented source with predictable metadata and low noise. It complements web search by making research intent explicit and by supporting literature-review style queries that should not route to news or community channels.

## When to Choose It

- Choose it for English or mixed-language paper lookup on topics like model architectures, benchmarks, safety methods, or optimization techniques.
- Choose it when the user asks for research papers, surveys, or literature review material rather than blog posts.
- Choose it when titles, authors, abstracts, and paper identifiers are more important than commentary.
- Avoid it for breaking news, shopping advice, or fast-moving public opinion.

## How To Search (Planned)

- `api_search` - Query the arXiv API search endpoint with keyword and category filters, then parse Atom feed results into normalized paper evidence.
- `api_search` - Expected fields include title, authors, summary, published date, primary category, and canonical arXiv URL.
- `api_search` - Initial ranking should favor exact topic matches and recent relevant submissions for literature-review workflows.

## Known Quirks

- The API is stable but not high throughput; keep requests conservative even though no auth is required.
- arXiv indexes preprints, not peer-review status, so downstream ranking should not imply formal publication.
- Query syntax can be sensitive to exact author names and category terms.
- Some papers are highly relevant but have terse abstracts, so recall can be uneven on broad queries.
