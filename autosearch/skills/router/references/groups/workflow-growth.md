---
name: workflow-growth
description: Self-adaptive growth — outcome-tracker, auto-evolve, create-skill, pipeline-flow, goal-loop, plus v2 experience layer (experience-capture / experience-compact) and model-routing advisory.
layer: group
domains: [workflow, meta, self-adaptive]
scenarios: [outcome-tracking, skill-evolution, experience-capture, loop-control]
model_tier: Standard
experience_digest: experience.md
---

# Workflow: Growth

The self-adaptive layer. Tracks which queries and channels actually paid off, promotes winning patterns to per-skill experience, and occasionally evolves a skill's SKILL.md (with hard constraints).

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `outcome-tracker` | Record which queries produced results that got used downstream | Standard | free |
| `auto-evolve` | Propose SKILL.md edits from accumulated patterns (reviewed + committed) | Best | free |
| `create-skill` | Scaffold a new skill when a missing capability blocks progress | Best | free |
| `pipeline-flow` | Start every task at the correct pipeline phase | Standard | free |
| `goal-loop` | Multi-round rubric-gated research with stop conditions | Best | free |
| `experience-capture` | Append a session event to per-skill `experience/patterns.jsonl` | Fast | free |
| `experience-compact` | Promote winning / losing patterns to `experience.md` (≤120 lines) | Standard | free |
| `autosearch:model-routing` | Read the tier advisory to decide Fast / Standard / Best per step | Standard | free |

## Routing notes

- `experience-capture` runs automatically after each leaf skill use (fast, no LLM). `experience-compact` fires on threshold (10 events / 64KB / user feedback / session end).
- `auto-evolve` **must** commit via `scripts/committer` and is reversible via `git revert`. Never modifies `judge.py`, `PROTOCOL.md`, or the meta-skills (`create-skill`, `observe-user`, `extract-knowledge`, `interact-user`, `discover-environment`).
- Rule promotion threshold: `seen >= 3 + success >= 2 + last_verified <= 30 days`. Single success never enters Active Rules (pollution defense).
- User corrections and rubric failures go into Failure Modes only — never into Active Rules.
- This group is where autosearch "learns" — keep its activity traceable in `state/evolution-log.jsonl`.
