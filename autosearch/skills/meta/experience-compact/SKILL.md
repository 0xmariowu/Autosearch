---
name: autosearch:experience-compact
description: Promote recurring patterns from `experience/patterns.jsonl` into the compact `experience.md` digest (≤120 lines, read by runtime AI before calling the skill). Triggers on N-events / file-size / user-feedback / session-end. Guards against single-success noise and pollution via promotion thresholds.
version: 0.1.0
layer: meta
domains: [meta, self-adaptive]
scenarios: [pattern-promotion, experience-digest-update, skill-evolution]
trigger_keywords: [compact experience, promote rules, update digest]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# experience-compact — Per-Skill Digest Updater

Reads a skill's `experience/patterns.jsonl` + existing `experience.md`, promotes recurring patterns to the digest, prunes stale rules, and rotates raw events if the file is getting large.

## Trigger Conditions

Run compact when ANY of:

1. ≥10 new events added to `patterns.jsonl` since last compact.
2. `patterns.jsonl` > 64 KB.
3. Last event carried explicit user feedback (`user_feedback: accepted` or `rejected`).
4. Session ending and this skill was used at least once during the session.

Runtime AI (or a cron on long-running instances) calls this skill per trigger.

## Promotion Rules

A candidate rule is extracted from `patterns.jsonl` when the same `winning_pattern` string or `good_query` template recurs. To **promote** it into the Active Rules section of `experience.md`:

- `seen >= 3` (appeared in at least 3 distinct events)
- `success >= 2` (at least 2 of those events have `outcome: success`)
- `last_verified <= 30 days` (most recent appearance within the last 30 days)

Each promoted rule carries a metadata footer:

```
seen=5, success=4, last_verified=2026-04-21
```

## Anti-Pollution Rules

- **Single success never promotes.** Even if an event looks great, one instance is noise — requires 3 occurrences.
- **User-rejected / rubric-failed / low-relevance events go only into Failure Modes**, never Active Rules.
- **User corrections** (explicit "no, that's wrong") always promote to Failure Modes with high weight.
- **Cold rules expire.** Any Active Rule with `last_verified > 30 days` moves to a "pending revalidation" bucket; if not re-verified in another 30 days, removed entirely.

## experience.md Template

```markdown
# <skill-name> experience

## Active Rules        # ≤ 20 entries
- <rule> — seen=5, success=4, last_verified=2026-04-21
- <rule> — seen=3, success=3, last_verified=2026-04-19

## Failure Modes       # ≤ 15 entries
- <failure pattern> — seen=4, last_verified=2026-04-20
- <user correction> — seen=1, last_verified=2026-04-18

## Good Query Patterns # ≤ 20 templates
- `{brand} {feature} 翻车 {year}` — seen=7
- `{category} 避雷 小红书 最近` — seen=5

## Last Compacted
- 2026-04-22, from 37 events, promoted 3 rules, archived raw events before 2026-03-22.
```

Hard ceiling: **120 lines total** across all sections. If exceeded after promotion, drop oldest Failure Modes first, then lowest-seen Active Rules, then lowest-seen Good Query Patterns.

## Rotation

When `patterns.jsonl` > 1 MB:

1. Rename current file to `experience/archive/YYYY-MM.jsonl` (month of first event in the file).
2. Create fresh empty `patterns.jsonl`.
3. Update `experience.md` `## Last Compacted` line with rotation note.

Archives are permanent — never delete. They serve as the lineage trail for AVO self-evolution audits.

## AVO Safety Boundaries

This skill **writes** `experience.md`. That's the promotion layer. It does **not**:

- Modify the skill's `SKILL.md` body (that's `auto-evolve`'s domain, which must commit via `scripts/committer` and be reversible via `git revert`).
- Modify `judge.py` or `PROTOCOL.md` (boss rule, hard constraint).
- Delete or rewrite `patterns.jsonl` (append-only; only rotation is allowed).

## Invocation Pattern

Runtime AI calls compact via a sync tool:

```python
compact_experience("search-xiaohongshu")
```

Implementation (Standard tier LLM call):

1. Read `autosearch/skills/channels/search-xiaohongshu/experience/patterns.jsonl`.
2. Read existing `autosearch/skills/channels/search-xiaohongshu/experience.md` (if exists).
3. Group events by `winning_pattern` / `good_query` template; count `seen` and `success`.
4. Apply promotion thresholds; drop events older than 30 days for rule evaluation.
5. Build new `experience.md` body: keep old Active Rules that still pass threshold; add new ones that newly qualify; move expired ones to Failure Modes or drop; refresh `## Last Compacted` line.
6. Write the new `experience.md`.
7. If `patterns.jsonl` > 1 MB, rotate.

Latency target: < 10 seconds, one LLM call for rule grouping if the patterns.jsonl is large.

## What This Skill Is NOT

- Not a summarizer of the skill's purpose (that's the SKILL.md body).
- Not a decision-maker for which skills to call (that's the router + group-index layer).
- Not a replacement for AVO's `auto-evolve` (which can edit `SKILL.md` with human / automated review).

It is a **safe, bounded, reversible digest writer** that turns append-only event logs into a short, runtime-visible rule list.

## Relationship to Other Skills

- Reads ← `<leaf>/experience/patterns.jsonl` (from `experience-capture`).
- Writes → `<leaf>/experience.md`.
- Feeds → runtime AI (which reads `experience.md` before calling the skill).
- Feeds → `auto-evolve` (which uses the rule history as input when proposing SKILL.md edits).

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
