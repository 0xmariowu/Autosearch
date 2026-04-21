---
name: workflow-quality
description: Evidence quality — normalize-results, rerank-evidence, anti-cheat, extract-dates, llm-evaluate, check-rubrics, generate-rubrics.
layer: group
domains: [workflow, quality]
scenarios: [evidence-normalization, relevance-ranking, spam-filter, date-anchoring, quality-scoring]
model_tier: Standard
experience_digest: experience.md
---

# Workflow: Quality

After channels return results: normalize, dedupe, rerank by relevance, score, and optionally apply rubrics.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `normalize-results` | Standardize into canonical evidence schema + dedupe | Fast | free |
| `rerank-evidence` | Order by task relevance (semantic, not keyword) | Standard | free |
| `anti-cheat` | Reject novelty-collapse / score-gaming patterns | Standard | free |
| `extract-dates` | Extract and normalize publication dates | Fast | free |
| `llm-evaluate` | Semantic relevance judgment per item | Standard | free |
| `check-rubrics` | Post-delivery rubric pass/fail evaluation | Best | free |
| `generate-rubrics` | Define 20-30 binary rubrics for a task | Best | free |

## Routing notes

- `normalize-results` → `extract-dates` → `rerank-evidence` is the standard pipeline order after raw channel output.
- `anti-cheat` should run before any scoring that affects routing, to prevent self-reinforcing bias.
- Rubrics (`generate-rubrics` + `check-rubrics`) are optional — use only when task has clear must-have criteria, not for every session.
- Do not invent N-dim × 0/3/5 rubrics — boss feedback. Use pairwise A/B preference for judgment; rubrics only for binary must-have checks.
