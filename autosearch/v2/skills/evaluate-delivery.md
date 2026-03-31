---
name: evaluate-delivery
description: "Use after synthesis to self-check delivery quality before presenting to user. Catches coverage gaps, weak citations, and shallow analysis."
---

# Purpose

judge.py scores the evidence bundle.
This skill scores the delivery itself — the synthesis output that the user actually sees.
A high judge score with a shallow delivery means good evidence was wasted on bad synthesis.

# When To Use

Use after synthesize-knowledge.md produces the delivery, before presenting to the user.
Also use when AVO is testing whether a skill modification improved delivery quality (not just evidence quality).

# Four Evaluation Dimensions

## 1. Coverage (does the delivery address all dimensions of the task?)

Check against the task spec or decomposition:
- List each dimension or sub-question from the task
- Verify each has substantive coverage in the delivery (not just a mention)
- Flag dimensions with zero or superficial coverage

Scoring:
- All dimensions covered with substance → pass
- 1 dimension missing or superficial → warn
- 2+ dimensions missing → fail

## 2. Depth (does the delivery go beyond what a quick search would produce?)

Check for:
- Conceptual framework (not just a list of things)
- Design patterns or taxonomy identified
- Tradeoffs and comparisons articulated
- Non-obvious insights (things the user would not find by browsing top search results)

Scoring:
- Framework + patterns + insights → pass
- Has structure but mostly surface-level → warn
- URL list or platform-by-platform dump → fail

## 3. Actionability (can the user make decisions from this delivery?)

Check for:
- Clear "which to choose" guidance (not just "here are options")
- Risk analysis and limitations
- Gaps explicitly identified ("what we did not find")
- Recommended next steps or areas for deeper investigation

Scoring:
- Decision-ready with risk awareness → pass
- Informative but no guidance → warn
- Pure information dump → fail

## 4. Citation Integrity (are claims grounded in evidence?)

Check for:
- Key claims linked to source evidence
- No hallucinated projects, papers, or statistics
- URLs are real and point to the claimed content
- Star counts, dates, and venue names match evidence

Scoring:
- All major claims cited → pass
- Most claims cited, some unsourced → warn
- Significant unsourced claims → fail

# Scoring

Count passes, warns, and fails across the 4 dimensions:
- 4 passes → delivery is ready
- 3 passes + 1 warn → delivery is acceptable, note the weakness
- 2+ warns or any fail → revise delivery before presenting

# Revision Strategy

When a dimension fails or warns:
- Coverage gap → check if evidence bundle has the missing content (if yes, revise synthesis; if no, note as gap)
- Shallow depth → restructure into framework format, extract patterns from evidence
- Low actionability → add "implications" or "recommendations" section
- Citation gap → link claims to evidence URLs, remove unverifiable claims

# Quality Bar

A good delivery makes the user smarter about the topic.
They should leave with a mental model, not just a reading list.
