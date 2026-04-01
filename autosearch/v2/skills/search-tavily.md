---
name: search-tavily
description: "Use when the task needs a paid, research-oriented web search API with consistent structured results and strong fit for evidence gathering."
---

# Platform

Tavily search API over HTTP POST to `tavily.com/api/search`.
This is a paid platform skill.

# When To Choose It

Choose this when you need:

- research-focused web search
- a structured paid web-search source
- better consistency than ad hoc free search layers
- strong general web evidence gathering with manageable latency

Use this when you want a premium web-search option but Exa is not the only semantic path you want to rely on.

# API Surface

This restores the V1-style Tavily connector.

Treat Tavily as a structured research search API with fields like:

- title
- URL
- content or snippet
- domain or source cues

# What It Is Good For

Tavily is best for:

- general research-focused web retrieval
- collecting article, documentation, and product-page evidence
- supplementing or validating free web search findings

It is weaker than platform-native APIs for engagement metadata, and its main advantage is paid consistency rather than community-native signal.

# Quality Signals

Prioritize results with:

- strong title match
- relevant content snippets
- trustworthy domains
- diverse source types across docs, articles, and official pages

Down-rank results when:

- several results cluster on the same weak domain
- the title match is broad but the content misses the target
- the result duplicates evidence already captured elsewhere

# Known V1 Patterns

No connector-specific Tavily pattern is currently saved in state.
Apply the general system lessons:

- concrete queries beat emotional or abstract wording
- freshness qualifiers should be added deliberately, not by default
- new URLs matter more than volume alone

# Rate Limits And Requirements

Requirements:

- `TAVILY_API_KEY`

This is a paid API.
Use budget intentionally and prefer query quality over large paraphrase sets.

# Output Expectations

Return web-result evidence.
Each result should normally preserve:

- title
- URL
- content snippet
- domain
- short relevance note

Expect Tavily to serve as a reliable paid web research layer rather than a platform-native social or code source.

# Standard Output Schema

Write each result as a JSON line conforming to the canonical evidence schema:

- url: canonical URL
- title: result title
- snippet: description or summary
- source: "tavily"
- query: the query that found this
- metadata: object with llm_relevant, llm_reason, date fields

The source field must be exactly "tavily" for this platform.
judge.py uses source for diversity scoring — inconsistent tags hurt the diversity dimension.

After collecting results, pass them to normalize-results.md for cross-platform dedup and extract-dates.md for freshness metadata.

# Date Metadata

Extract dates from platform-specific fields and write to metadata:

- metadata.published_at — when the content was created (ISO 8601)
- metadata.updated_at — when the content was last modified (ISO 8601)
- metadata.created_utc — creation timestamp (ISO 8601)

See extract-dates.md for the full extraction priority and format rules.
Missing dates score as zero freshness in judge.py.

# Quality Bar

This platform skill is working when results have accurate source tags, populated date metadata, and conform to the canonical evidence schema defined in normalize-results.md.
