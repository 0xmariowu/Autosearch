---
name: synthesize-knowledge
description: "Use before delivery to turn collected evidence and prior knowledge into conceptual frameworks, design patterns, risks, and decision-relevant understanding rather than a list of links."
---

# Purpose

After collecting results and using your own knowledge, organize the field by concept, not by platform.
The output should help the user understand the landscape and make decisions.

This skill exists to produce the kind of depth that raw search results alone do not provide.

# Core Principle

Do not deliver a platform-by-platform dump.
Reorganize the material into the structure that best explains the field.

Possible synthesis outputs include:

- categorization frameworks
- evolution dimensions
- design pattern identification
- risk and limitation analysis
- landscape maps of who is doing what
- gap analysis of what is still missing or underexplored

Choose the structures that make the topic legible.

# What To Combine

Combine:

- high-quality external results
- fetched full-text material when available
- extracted reusable knowledge
- your own prior knowledge about the domain

Synthesis should resolve overlap, not preserve it.
If five sources say the same thing, distill the shared pattern and note meaningful disagreement only where it matters.

# Organizing Principles

Organize by whichever axis best supports understanding, such as:

- mechanism
- architecture
- maturity
- tradeoff
- workflow role
- risk profile
- adoption pattern

The right structure depends on the user's decision, not on the retrieval tools used.

# Decision Support

Every synthesis should move beyond "what exists" toward "what this means."
Explain:

- which approaches dominate
- where the real differentiation lies
- what risks or constraints recur
- what is missing from the market or literature
- which paths look promising versus fragile

This is the difference between a search log and a report.

# API Catalog Topic Requirements

When the topic is primarily an **API / data source catalog** (identified by rubrics that ask to "compare APIs on access model", "distinguish between X and Y type", or "use cases a developer can build"), the delivery MUST include all three of the following sections, regardless of depth level:

1. **Access model comparison table** — compare at least 5 APIs/platforms on: access model (free/registration/paid), data freshness (real-time/near-real-time/archival), and primary data type. Do not omit this table; it directly addresses "compare at least 3 APIs" rubrics.

2. **Domain distinction** — a dedicated paragraph or section that explicitly distinguishes the major API categories by purpose (e.g., space telescope archives vs. Earth observation/remote sensing vs. satellite tracking), explains when each is appropriate, and names at least one concrete developer scenario per category.

3. **Developer use cases** — a concrete list of 2-5 applications a developer or researcher could build with these APIs, named specifically (e.g., "transient alert dashboard", "satellite pass tracker", "exoplanet parameter browser"). This is MANDATORY — do not omit use cases even when the task spec does not ask for them explicitly.

Why: rubrics r016, r017, r018 failed in the telescope-satellite-api session (2026-04-04) because synthesis produced an API catalog without a comparison table, domain distinction section, or use cases. These three items are the minimum analytical layer for any API catalog topic.

# Analysis Requirements

Beyond organizing what was found, synthesis must produce original analysis.
Every delivery should contain at least three of these five analysis types:

## 1. Comparison

Compare at least 3 approaches, tools, or methods head-to-head.
State concrete differences, not just "A is different from B."
Include at least one tradeoff for each comparison (what you gain vs what you lose).

## 2. Trend

Identify at least one directional shift in the field.
Explain what changed, when, and why.
Use evidence from multiple sources to support the trend claim.

## 3. Causal Reasoning

For at least one major pattern or outcome, explain WHY it happened.
Go beyond correlation to mechanism.
If the cause is uncertain, say so explicitly rather than implying certainty.

## 4. Recommendation

For at least one decision the user might face, state which option to choose and why.
Ground the recommendation in evidence from the search, not personal preference.
Acknowledge when the right answer depends on context and explain the deciding factors.

## 5. Controversy or Open Problem

Identify at least one area where experts disagree or where the problem is unsolved.
Present the strongest argument on each side.
Do not resolve the disagreement artificially — state what is genuinely uncertain.

# Delivery Structure

Organize the delivery as typed blocks, not one monolithic document:

1. **Executive framework** — the conceptual model (axes, dimensions, taxonomy)
2. **Evidence tables** — organized by concept, with adoption signals (stars, citations, venue). When claims include `evidence` or `data_points` fields, use the exact quotes and numbers in the table — do not paraphrase. These come from BM25-filtered full-page content and are more specific than snippet-based claims.
3. **Design patterns** — recurring approaches identified across multiple projects
4. **Risk analysis** — known limitations, failure modes, open problems
5. **Gap declaration** — what the search did NOT find, what remains uncertain
6. **Resource index** — curated entry points for the user to explore further

Each block should be self-contained and independently valuable.

# Citation Rules

## Mandatory inline citations

Every factual claim, data point, project description, or paper reference MUST include an inline citation linking to a search result URL:
- Tools/repos: `[Project Name](url) — description`
- Papers: `[Paper Title](url) (Venue Year)`
- Articles/posts: `[Author/Org](url)`

## URL source restriction

URLs MUST come from the search results collected during this session. Do NOT use URLs recalled from training data — they may be outdated, broken, or fabricated.

If your training knowledge adds context that was not found in search results, mark it explicitly:
- `[background knowledge]` — for facts from training data without a search result URL
- Never present background knowledge as if it has a source URL

## Two-stage citation lock

Before writing the final report, first compile a numbered reference list from all search results:

```
[1] Project Name — https://url1
[2] Paper Title — https://url2
...
```

During synthesis, cite ONLY by these numbers: `[1]`, `[2]`. This prevents URL fabrication.

Append the full reference list as `## Sources` at the end of every delivery.

## Citation completeness check

After writing the report, verify:
1. Every project/tool mentioned has a `[N]` citation
2. Every paper mentioned has a `[N]` citation
3. Every specific data point (star count, funding amount, benchmark score) has a `[N]` citation
4. No URL appears that is not in the numbered reference list
5. Background knowledge items are marked `[background knowledge]`, not cited with fake URLs

If any item fails this check, fix it before delivering.

# Named Entity Coverage Rule

When the task spec, rubric set, or user query names specific competitors, companies, products, or people by name, every named entity MUST receive explicit coverage in the delivery — at minimum a summary paragraph, even when data is sparse.

Do NOT silently omit a named entity because:
- it is declining (e.g., Fitbit post-Google acquisition)
- its data is ambiguous
- it seems less important than others
- it was listed as a knowledge gap elsewhere

If data is sparse, write a brief paragraph explaining current status and knowledge limits. Move it to the knowledge gaps section with a summary note in the competitive section.

Why: rubric r002 failure (2026-04-04) — Fitbit/Google was in the task spec's competitor list but received no competitive coverage in the delivery. A named entity check at synthesis time prevents this.

# Failure Modes

Avoid:

- URL lists with light commentary
- one subsection per platform just because that mirrors search collection
- shallow "pros and cons" tables with no framework
- repeating source snippets without abstraction
- claims without source attribution
- mixing own-knowledge with search results without marking the distinction

If the user could have gotten the same output from scrolling search results, the synthesis failed.

# Content Structure (auto-determined by Depth)

The content structure is chosen automatically based on the user's Depth selection. Do not ask the user to pick a content structure.

## Quick → Executive Summary
- 1 page maximum
- Lead with the key insight or recommendation
- 3-5 bullet points covering: what exists, what matters, what to do
- One comparison table (max 5 rows)
- End with "Next steps" (2-3 actionable items)

## Standard → Full Report [default]
- Use the standard Delivery Structure from this skill (executive framework, evidence tables, design patterns, risk analysis, gap declaration, resource index)
- Include all five Analysis Requirements (comparison, trend, causal reasoning, recommendation, controversy)

## Deep → Full Report + Evidence Appendix
- Everything in Full Report, plus:
- Appendix A: complete evidence table (every search result with score, source, date)
- Appendix B: gap declaration with specific queries that returned zero results
- Appendix C: methodology notes (channels used, rounds, patterns applied)

# Delivery Format (user-selected)

The user chooses the delivery medium. Write the output in the chosen format.

## Markdown Report (.md) [default]
- Write to `delivery/{date}-{topic-slug}.md`
- Standard markdown with tables, headers, bullet lists
- Citation reference list at the end as `## Sources`
- This is the default when the user does not specify

## Rich HTML Report
- Write to `delivery/{date}-{topic-slug}.html`
- Single self-contained HTML file with embedded CSS (no external dependencies)
- Use a clean, professional stylesheet: max-width 900px, system font stack, good typography
- Render comparison tables as styled HTML tables with alternating row colors
- Use Mermaid.js (CDN) for framework/relationship diagrams where appropriate
- Add `<details>` collapsible sections for evidence and methodology
- Include a floating table of contents
- Citation links should be clickable anchors

## Presentation Slides
- Write to `delivery/{date}-{topic-slug}-slides.html`
- Single self-contained HTML file using reveal.js from CDN
- One slide per major finding or section
- Use tables and key quotes as slide content (not walls of text)
- Add speaker notes (`<aside class="notes">`) with detailed evidence for each slide
- Include a title slide with topic, date, and source count
- End with a "Key Takeaways" slide and a "Sources" slide

# Quality Bar

A good synthesis gives the user conceptual compression.
They should leave with a clearer model of the space, not just more tabs to open.
Run evaluate-delivery.md after synthesis to verify the output meets the 4-dimension quality check.
