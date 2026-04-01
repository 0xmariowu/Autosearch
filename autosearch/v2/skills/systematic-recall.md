---
name: systematic-recall
description: "Use BEFORE any search as the first step of every research task. Systematically extract everything Claude knows about the topic, organized by dimensions with confidence levels."
---

# Purpose

You are Claude. Your training data contains vast knowledge about most research topics.
This skill turns that passive knowledge into an active, structured starting point.

Instead of searching for everything, recall first, then search only for what you do not know or are not sure about.
This is the foundation of the Claude-first architecture: your knowledge leads, search follows.

# When To Use

Use at the very start of every research task, before generating any search queries.
The output of this skill feeds directly into decompose-task.md and gene-query.md.

# The 9 Dimensions

Scan your knowledge along these dimensions for the given topic:

## 1. Foundational Methods
Core techniques, algorithms, frameworks that define the field.
Example: STaR, Reflexion, RLHF, DPO, in-context learning.

## 2. Key People and Institutions
Researchers, labs, and organizations driving the field.
Example: Noah Shinn (Reflexion), Stanford NLP, DeepMind, Tencent AI Lab.

## 3. Landmark Projects
The projects everyone in the field knows about.
Example: Voyager, DSPy, ADAS, AutoGPT.

## 4. Top-Venue Papers
Papers from major conferences in the last 3 years.
Example: NeurIPS 2023 oral papers, ICLR 2025 best papers.

## 5. Design Patterns
Recurring architectural approaches.
Example: Reflection loop, Skill Library, Self-Play, Meta Agent Search.

## 6. Known Risks and Limitations
What can go wrong, what does not work yet.
Example: Reward hacking, catastrophic forgetting, scaffolding ceiling.

## 7. Commercial Players
Companies building products in this space.
Example: Letta, Mem0, Devin, Sierra AI, Sakana AI.

## 8. Controversies and Open Questions
Where experts disagree, what remains unresolved.
Example: "Can prompt/workflow evolution rival weight updates?" debate.

## 9. Recent Developments (Last 6 Months)
The newest work you are aware of from your training data: papers, releases, announcements, benchmarks, or shifts that happened most recently.
Focus specifically on what is NEW — not established classics repackaged, but genuinely recent contributions.
Example: MAGMA (Jan 2026), LifeBench (Mar 2026), ICLR 2026 MemAgents workshop.
Tag these items with the most precise date you can recall (month + year minimum).
If you cannot recall anything from the last 6 months, mark this entire dimension as GAP — it signals the topic may have evolved beyond your training data and search should prioritize freshness.

# Confidence Levels

For each item you recall, tag it with a confidence level:

- **HIGH**: I am confident this is accurate and current. No search needed.
- **MEDIUM**: I know the basics but details may be outdated or incomplete. Search to verify and enrich.
- **LOW**: I vaguely recall this but cannot be specific. Search to confirm or discard.
- **GAP**: I know this dimension exists but have no specific knowledge. Search to discover.

# Output Format

Produce a knowledge map as structured output:

```
## Knowledge Map: {topic}

### 1. Foundational Methods
- [HIGH] STaR (Zelikman et al., 2022) — bootstrapping reasoning with self-generated rationales
- [HIGH] Reflexion (Shinn et al., 2023) — verbal reinforcement learning with episodic memory
- [MEDIUM] STOP — self-taught optimizer, recursive self-improvement. Details fuzzy.
- [GAP] Latest prompt optimization methods beyond DSPy

### 2. Key People and Institutions
- [HIGH] Noah Shinn — Reflexion, Princeton
- [MEDIUM] Shengran Hu — ADAS, possibly UBC? Verify affiliation.
...
```

# What Happens Next

The knowledge map drives everything downstream:

1. **HIGH items** → go directly into the evidence bundle as own-knowledge entries
2. **MEDIUM items** → generate verification queries (e.g., "STOP self-taught optimizer latest results")
3. **LOW items** → generate confirmation queries (e.g., "does X still exist?")
4. **GAP items** → generate discovery queries (e.g., "prompt optimization frameworks 2025 2026")

This means gene-query.md generates queries from GAPS, not from the task text.
Search budget is spent on what you do not know, not on rediscovering what you already know.

# Interaction With Knowledge Maps

If `state/knowledge-maps/` has a prior map for this topic, load it first.
Compare your current recall with the stored map:
- Items in the stored map that you still recall → keep, update confidence if needed
- Items in the stored map that you no longer recall → keep from map (it was verified previously)
- New items you recall that are not in the map → add them

After the search session, save the updated map via knowledge-map.md.

# Quality Bar

A good systematic recall produces 30-60 items across all 9 dimensions with honest confidence tags.
If you produce fewer than 15 items, the topic may be outside your training data — flag this and rely more on search.
If you produce more than 60 items, you know this topic well — search budget should be minimal, focused on freshness and verification.
Dimension 9 (Recent Developments) should have at least 3-5 items if the topic is active. If it has 0 items, search must heavily prioritize freshness.
