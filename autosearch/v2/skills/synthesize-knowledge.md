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
2. **Evidence tables** — organized by concept, with adoption signals (stars, citations, venue)
3. **Design patterns** — recurring approaches identified across multiple projects
4. **Risk analysis** — known limitations, failure modes, open problems
5. **Gap declaration** — what the search did NOT find, what remains uncertain
6. **Resource index** — curated entry points for the user to explore further

Each block should be self-contained and independently valuable.

# Citation Rules

Every factual claim must link to its source:
- "[Project Name](url) — description" for tools and repos
- "[Paper Title](url) (Venue Year)" for academic work
- "[Author/Org](url)" for blog posts and articles

Do not claim facts that are not in the evidence bundle.
If your training knowledge adds context, mark it explicitly as background knowledge.
Do not mix cited evidence with uncited assertions — the user cannot tell which is grounded.

# Failure Modes

Avoid:

- URL lists with light commentary
- one subsection per platform just because that mirrors search collection
- shallow "pros and cons" tables with no framework
- repeating source snippets without abstraction
- claims without source attribution
- mixing own-knowledge with search results without marking the distinction

If the user could have gotten the same output from scrolling search results, the synthesis failed.

# Quality Bar

A good synthesis gives the user conceptual compression.
They should leave with a clearer model of the space, not just more tabs to open.
Run evaluate-delivery.md after synthesis to verify the output meets the 4-dimension quality check.
