---
name: assemble-context
description: "Use before synthesis to select, deduplicate, compress, and organize evidence into a coherent context that fits the token budget and preserves source attribution."
---

# Purpose

You have collected and evaluated many results.
Before synthesis, organize the evidence into a context that:
- fits within available token budget
- prioritizes the most relevant and diverse evidence
- removes content duplication
- preserves source attribution for citations

Without this step, synthesis either overflows context or produces shallow output by treating all evidence equally.

# When To Use

Use after LLM evaluation and reranking, before synthesize-knowledge.md.
This skill is the bridge between raw evidence and structured synthesis.

# Step 1: Filter

Start with only results where `metadata.llm_relevant = true`.
If rerank-evidence.md produced a ranking, use the ranked order.
Otherwise, sort by: platform diversity first, then by relevance confidence.

# Step 2: Deduplicate Content

Even after URL dedup (normalize-results.md), content can overlap:
- Multiple results describing the same project from different sources
- Blog posts that summarize papers already in the bundle
- Nested awesome-lists that reference the same repos

When content overlaps:
- Keep the most detailed version
- Discard the shallower duplicate
- Note the discarded source in case synthesis needs it later

# Step 3: Estimate Token Budget

Estimate available tokens for the evidence context.
Reserve space for:
- System prompt and skill instructions (~2K tokens)
- Synthesis output (~3K tokens for a thorough report)
- Conversation history if any (~1K tokens)

The remaining budget is for evidence.
A typical evidence entry (title + URL + snippet + metadata) is ~100-200 tokens.
Full fetched content can be 1K-5K tokens per page.

# Step 4: Select Top-K

If total evidence exceeds token budget:

1. Always include: results from each unique platform (1 per platform minimum, for diversity)
2. Always include: own-knowledge entries (foundational works)
3. Fill remaining budget by relevance rank
4. Prefer results with richer metadata (dates, stars, citations)
5. Prefer results with fetched full content over snippet-only

If still over budget: truncate the longest snippets, keeping title + URL + first 2 sentences.

# Step 5: Organize for Synthesis

Group selected evidence by concept cluster, not by platform or query.
Suggested organization:

- Core frameworks and tools (with adoption signals)
- Academic foundations (papers, with dates and venues)
- Design patterns and architecture approaches
- Practical resources (tutorials, blog posts, courses)
- Commercial products and startups
- Risks, limitations, and open problems

This organization directly supports synthesize-knowledge.md's requirement to produce a conceptual framework.

# Step 6: Preserve Attribution

Every piece of evidence in the assembled context must carry:
- source URL
- source platform
- a short label (e.g., "STaR [NeurIPS 2022]", "Voyager [6.8K stars]")

These labels become citation anchors in the final synthesis.

# Quality Bar

A well-assembled context lets synthesis produce a structured report without going back to search.
If synthesis has to say "I don't have enough information about X," the assembly missed something the evidence bundle actually contained.
