---
name: workflow-planning
description: Planning and intent shaping — clarify, systematic-recall, use-own-knowledge, decompose-task, gene-query, consult-reference, select-channels, research-mode, observe-user, discover-environment, provider-health.
layer: group
domains: [workflow, planning]
scenarios: [task-intake, clarify-intent, decompose, query-generation, channel-selection]
model_tier: Standard
experience_digest: experience.md
---

# Workflow: Planning

Before searching, shape the task: clarify ambiguity, recall what we already know, decompose, generate queries, and pick channels.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `clarify` | Query is ambiguous; ask 4 targeted questions | Best | free |
| `systematic-recall` | Before any search, enumerate what autosearch already knows | Best | free |
| `use-own-knowledge` | Decide whether Claude's parametric knowledge is sufficient | Standard | free |
| `decompose-task` | Break a multi-part question into sub-questions | Best | free |
| `gene-query` | Combine entity × pain-verb × object × symptom × context into queries | Standard | free |
| `consult-reference` | Check prior work / Armory / Agent-Reach before inventing locally | Standard | free |
| `select-channels` | Pick 5-10 relevant channels from 41 leaf search skills | Standard | free |
| `research-mode` | Choose speed vs. balanced vs. deep | Standard | free |
| `observe-user` | Infer user preferences from conversation and env | Standard | free |
| `discover-environment` | Probe available keys / tools / runtime capabilities | Fast | free |
| `provider-health` | Skip cooling-down platforms; prefer fresh channels | Fast | free |

## Routing notes

- Always run `discover-environment` first if env state is unknown — wasted calls to a missing provider are pure overhead.
- `clarify` and `decompose-task` are the two most important upstream steps and must use `Best` tier (incorrect clarification cascades to the whole session).
- For simple one-shot queries, skip this group and go straight to a channel group.
