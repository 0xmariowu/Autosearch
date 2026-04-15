---
name: synthesize-knowledge
description: "Use when you need to synthesize research findings, combine search results into a structured report, build a comparison framework, or turn raw evidence into decision-ready analysis. Triggers: 'synthesize', 'analyze findings', 'compare options', 'build a report', 'summarize research', 'what does this mean'."
---

# Workflow

1. **Collect** — Gather search results, fetched full-text, and relevant prior knowledge
2. **Deduplicate** — Resolve overlap across sources; distill shared patterns, keep only meaningful disagreements
3. **Organize** — Choose the axis that best supports the user's decision (mechanism, architecture, maturity, tradeoff, risk, adoption)
4. **Analyze** — Produce at least 3 of the 5 analysis types (see Analysis Requirements below)
5. **Cite** — Lock all URLs to a numbered reference list compiled from search results only
6. **Structure** — Write the delivery using typed blocks (see Delivery Structure)
7. **Verify** — Run the citation completeness check and named-entity coverage check
8. **Evaluate** — Run evaluate-delivery.md to confirm quality bar

# Core Principle

Organize by concept, not by platform. Do not deliver a platform-by-platform dump. Reorganize material into the structure that best explains the field: categorization frameworks, design patterns, risk analysis, landscape maps, or gap analysis.

The right structure depends on the user's decision context, not on how results were retrieved.

# Decision Support

Every synthesis must move beyond "what exists" toward "what this means":
- Which approaches dominate and why
- Where real differentiation lies
- What risks or constraints recur
- What is missing from the market or literature
- Which paths are promising versus fragile

# Analysis Requirements

Every delivery must contain at least 3 of these 5 analysis types:

1. **Comparison** — Compare 3+ approaches head-to-head with concrete tradeoffs (what you gain vs. lose)
2. **Trend** — Identify a directional shift: what changed, when, why, with multi-source evidence
3. **Causal reasoning** — Explain WHY a major pattern occurred; state uncertainty explicitly when cause is unclear
4. **Recommendation** — For a user decision, state which option to choose and why, grounded in evidence
5. **Controversy / open problem** — Where experts disagree or the problem is unsolved; present strongest arguments per side without artificial resolution

# Delivery Structure

Organize output as typed blocks, each self-contained:

1. **Executive framework** — Conceptual model (axes, dimensions, taxonomy)
2. **Evidence tables** — Organized by concept with adoption signals (stars, citations, venue). Use exact quotes and numbers from `evidence`/`data_points` fields
3. **Design patterns** — Recurring approaches across multiple projects
4. **Risk analysis** — Limitations, failure modes, open problems
5. **Gap declaration** — What the search did NOT find; what remains uncertain
6. **Resource index** — Curated entry points for further exploration

## Example: Executive Framework for a CI/CD Tools Synthesis

```markdown
## Executive Framework

CI/CD tools organize along three axes:

| Axis | Spectrum | Examples |
|------|----------|----------|
| Hosting model | Self-hosted ↔ Fully managed | Jenkins ↔ GitHub Actions |
| Config paradigm | Declarative YAML ↔ Programmatic SDK | CircleCI ↔ Dagger |
| Ecosystem lock-in | Vendor-neutral ↔ Platform-native | Tekton ↔ GitLab CI |

**Key finding**: The market is converging on declarative + managed,
but teams with complex build graphs increasingly adopt SDK-based
tools (Dagger, Earthly) to escape YAML complexity [1][3].

**Trend**: Since 2024, "CI as code" (programmatic pipelines) grew
from niche to mainstream — Dagger adoption tripled [2].

**Recommendation**: For teams under 50 engineers on GitHub, start
with GitHub Actions. Switch to Dagger when YAML configs exceed
~500 lines or cross-repo orchestration is needed [4][5].
```

# Content Depth (auto-determined)

- **Quick** — 1 page max. Key insight, 3-5 bullets, one comparison table (max 5 rows), 2-3 next steps.
- **Standard** (default) — Full delivery structure with all 5 analysis types.
- **Deep** — Full report plus appendices: complete evidence table, gap queries, methodology notes.

# Delivery Format (user-selected)

- **Markdown** (default) — Write to `delivery/{date}-{topic-slug}.md`. Standard markdown, `## Sources` at end.
- **Rich HTML** — Write to `delivery/{date}-{topic-slug}.html`. Self-contained with embedded CSS, styled tables, Mermaid.js diagrams, floating TOC, collapsible evidence sections.
- **Slides** — Write to `delivery/{date}-{topic-slug}-slides.html`. reveal.js from CDN. One slide per finding, speaker notes with evidence, title + takeaways + sources slides.

# API Catalog Requirements

When the topic is an API/data-source catalog, always include:

1. **Access model table** — Compare 5+ APIs on: access model (free/registration/paid), data freshness, primary data type
2. **Domain distinction** — Distinguish major API categories by purpose with one developer scenario per category
3. **Developer use cases** — 2-5 concrete applications named specifically (e.g., "transient alert dashboard", "satellite pass tracker")

# Citation Rules

Every factual claim must have an inline citation from search results.

**Format by source type:**
- Tools/repos: `[Project Name](url) — description`
- Papers: `[Paper Title](url) (Venue Year)`
- Articles: `[Author/Org](url)`

**Two-stage citation lock:**
1. Before writing, compile a numbered reference list from search results: `[1] Name — url`
2. During synthesis, cite only by number: `[1]`, `[2]`
3. Append full list as `## Sources`

**URL restriction:** URLs must come from this session's search results. Mark training-data context as `[background knowledge]` — never give it a fake URL.

**Completeness check** — After writing, verify: every tool/paper/data-point has a `[N]` citation, no URL exists outside the reference list, background knowledge is marked.

# Named Entity Coverage

When the query names specific competitors, products, or people, every named entity MUST appear in the delivery. If data is sparse, write a brief status paragraph and note knowledge limits. Never silently omit a named entity.

# Failure Modes

Avoid:
- URL lists with light commentary
- One subsection per platform mirroring search order
- Shallow pros/cons tables without a framework
- Source snippets repeated without abstraction
- Claims without attribution
- Mixing prior knowledge with search results without marking the distinction

If the user could get the same output by scrolling search results, the synthesis failed.

# Quality Bar

A good synthesis gives the user conceptual compression. They should leave with a clearer model of the space, not just more tabs to open. Run evaluate-delivery.md after synthesis to verify the output meets the 4-dimension quality check.
