---
name: follow-links
description: "Use when high-value pages link to many relevant resources that search APIs would not find directly. Follow outlinks from awesome-lists, survey papers, and curated collections."
---

# Purpose

Some of the best resources are not directly searchable — they are linked FROM pages that are searchable.
An awesome-list with 40 relevant repos, a survey paper with 50 citations, or a curated blog post with 20 tool links — following these links is often higher yield than running more search queries.

# When To Follow Links

Follow links when:

- a result is an awesome-list, curated collection, or resource directory
- a result is a survey paper or literature review
- a result is a blog post that explicitly compares or lists multiple tools
- you found a high-quality hub page and want to explore its references

Do NOT follow links when:

- the result is a normal repo or article (not a hub/collection)
- you are already over budget
- the links would be off-topic

# How To Follow

1. Identify the high-value page (usually scored highly by llm-evaluate)
2. Fetch full content using fetch-webpage.md
3. Extract outlinks from the content
4. Score each outlink for relevance:
   - Does the link text suggest relevance to the task?
   - Is the domain likely to have useful content? (github.com, arxiv.org, reputable blogs)
   - Is the link to a specific resource or just navigation?
5. Fetch the top-scoring outlinks (max 10 per hub page)
6. Add fetched results to the evidence bundle with source tagged as the original platform

# URL Scoring Heuristics

High score:
- Links to GitHub repos (github.com/{org}/{repo})
- Links to arXiv papers (arxiv.org/abs/*)
- Links with descriptive anchor text that matches task keywords
- Links to project homepages with clear names

Low score:
- Navigation links (About, Contact, Home, Login)
- Social media share buttons
- Links to the same domain (internal navigation)
- Links to generic resources (Wikipedia main pages, Google)
- Links with anchor text like "click here", "read more", "link"

# Depth Limit

Follow links to depth 1 only (one hop from the original page).
Do not recursively follow links from followed pages.
Hub pages are valuable; their outlinks are valuable; outlinks of outlinks are noise.

# Hostname Diversity

When selecting which outlinks to follow, prefer hostnames not already in the evidence bundle.
If you already have 10 github.com results, following 5 more GitHub links adds less value than following links to new domains.

# Quality Bar

Good link following discovers 5-15 new resources per hub page that search APIs did not find directly.
If followed links produce mostly duplicates of existing evidence, the hub page was not a good candidate.
