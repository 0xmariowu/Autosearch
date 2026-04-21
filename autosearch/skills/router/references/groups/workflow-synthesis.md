---
name: workflow-synthesis
description: Synthesis — assemble-context, extract-knowledge, knowledge-map, synthesize-knowledge, evaluate-delivery, interact-user.
layer: group
domains: [workflow, synthesis]
scenarios: [context-assembly, knowledge-extraction, final-report, delivery-evaluation]
model_tier: Best
experience_digest: experience.md
---

# Workflow: Synthesis

Turn evidence into knowledge and a delivered report. Highest-value, highest-tier workflow stage.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `assemble-context` | Compress / dedupe / budget evidence for the synthesis model | Standard | free |
| `extract-knowledge` | Pull reusable knowledge from high-quality results | Standard | free |
| `knowledge-map` | Build / load structured knowledge maps across sessions | Best | free |
| `synthesize-knowledge` | Produce conceptual frameworks, patterns, risks — not a link list | Best | free |
| `evaluate-delivery` | Self-check the delivery for coverage gaps and shallow citations | Best | free |
| `interact-user` | Ask clarifying questions / show intermediate findings / collect feedback | Standard | free |

## Routing notes

- Autosearch v2 **does not own the final LLM synthesis pass** — the runtime AI synthesizes using the transcripts, snippets, and structured context autosearch provides. These skills exist to prepare material, not replace Claude's judgment.
- `synthesize-knowledge` and `evaluate-delivery` are the Best-tier "key 1-2 steps" the boss called out — they shape the whole deliverable, so use the best model.
- `knowledge-map` is the cross-session memory layer — load before a session to see what's already known on the topic, save at session end.
