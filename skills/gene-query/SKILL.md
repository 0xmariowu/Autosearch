---
name: gene-query
description: "Use when you need to expand a task into diverse search queries built from entity, pain_verb, object, symptom, and context genes."
---

# Model Recommendation

Query generation is a structured expansion task. Use Haiku when possible — it generates diverse queries effectively at lower cost. When spawning an agent for query generation, set `model: "haiku"`.

# Purpose

Generate queries from five gene dimensions instead of improvising all search text from scratch.
This restores a reusable query grammar that turns vague tasks into targeted searches.

# The Six Dimensions

- `entity` = WHO is involved
- `pain_verb` = ACTION or failure mode
- `object` = WHAT artifact, tool, concept, or target is involved
- `symptom` = HOW the problem appears
- `context` = WHERE or under what condition it happens
- `content_type` = WHAT KIND of result you want (repo, paper, blog, tutorial, company, video, awesome-list, conference-workshop, company-product, comparison)

Good queries usually need only 2 or 3 dimensions.
Do not cram all six into every query.

Use `content_type` to steer queries toward underrepresented evidence.
If the current bundle is heavy on repos and light on papers or blogs, generate queries that explicitly target the missing types.
Examples: "self-evolving agent tutorial", "self-improving AI startup company", "self-evolving agent survey paper".

# Gap-Driven Query Generation (Claude-First Mode)

When systematic-recall.md has produced a knowledge map, generate queries from GAPS, not from the task text.

For each GAP or LOW confidence item in the knowledge map:
- Convert the gap into a specific search query
- Target the platform most likely to fill that gap
- Example: GAP in "commercial players" → query "self-evolving AI agent startup 2026" on web-ddgs

For each MEDIUM confidence item:
- Generate a verification query
- Example: MEDIUM on "STOP framework" → query "STOP self-taught optimizer latest" on arxiv/web

Do NOT generate queries for HIGH confidence items — those are already in the evidence bundle from own-knowledge.

This is the most efficient use of search budget: every query targets a known gap.

# Mandatory Query Rules

Certain topic types MUST generate specific query types to avoid systematic coverage gaps.

## Academic/research topics

- MUST generate at least 1 query with `content_type=conference-workshop` (e.g., "topic workshop NeurIPS ICML 2025")
- MUST generate at least 1 query targeting `arxiv` or `semantic-scholar` channel

## Tool/product topics

- MUST generate at least 1 query with `content_type=company-product` (e.g., "topic startup company funding")
- MUST generate at least 1 query targeting `producthunt` or `crunchbase` channel
- MUST generate at least 1 query targeting enterprise/non-GitHub alternatives (e.g., "GitLab Duo", "AWS CodeGuru", "Atlassian Bitbucket AI") when the topic involves developer tools. Because: AVO found r003/r006 consistently fail without enterprise platform queries.
- MUST generate at least 1 query with `content_type=comparison` that includes "pricing" or "deployment" (e.g., "topic pricing free tier enterprise"). Because: AVO found r008 (pricing/deployment info) fails without explicit pricing queries.

## Any topic

- MUST generate at least 1 query targeting `twitter` channel for recent announcements
- MUST generate at least 1 Chinese-language query if any Chinese channel is selected

These rules exist because AVO analysis found that r005 (commercial companies) and r013 (conference info) consistently fail when these query types are missing.

# Input Sources (General)

Build the gene pool from three places:

- The task itself: entities, artifacts, constraints, and pain language from the user or goal case
- Winning history: patterns from `state/patterns.jsonl` (filter to `winning_pattern` and `platform_insight` types only — ignore `session_stats`, `outcome_boost`, and `winning_words` entries, which are statistical noise that does not inform query strategy) and proven queries from `state/outcomes.jsonl`
- Your own judgment: missing synonyms, domain terms, and alternate framings not yet present in state

# Mix Ratio

Generate candidate queries with this mix:

- 20% LLM suggestions
- 20% winning patterns
- 60% gene combinations

Keep the ratio in spirit, not as rigid bookkeeping.
If one source is exhausted, backfill from the others without collapsing into a single style.

# Combination Rule

For each gene-combination query:

- pick 2 or 3 dimensions
- pick exactly 1 value from each chosen dimension
- join them into a terse search phrase

Examples of the shape:

- `entity + object`
- `pain_verb + object`
- `entity + symptom + context`
- `pain_verb + object + context`

Prefer specific combinations that narrow meaning without becoming long natural-language sentences.

# Query Construction Heuristics

Keep one anchor term that strongly binds the topic.
Add one discriminator that changes what results appear.
Add a third term only when it meaningfully sharpens retrieval.

Prefer concrete tokens over generic prose.
Prefer symptoms over emotional adjectives.
Prefer observable failures over abstract aspirations.

Use winning query patterns from state when they clearly transfer.
Boost queries whose words or families have proven outcomes.
Keep seed queries from the task or config in the set even if they are not gene-generated.

# Diversity Rules

Do not emit many trivial variations of the same query.
Vary the dimension mix across the set:

- some entity-led
- some pain-led
- some object-led
- some context-led

Avoid a pool where every query starts from the same noun phrase.
Deduplicate semantically, not only by exact string match.
After generating all candidate queries, run a final dedup pass: if two queries share 60% or more of their content words, keep the more specific one and drop the other.
The final query set after dedup MUST NOT exceed `max_total_queries` from config.json.

# Freshness And Time

Do not hard-cap all generated queries by recency.
Add time qualifiers only when the task explicitly needs freshness or the prior round showed stale retrieval.

# Output Format

Output a JSON array compatible with search_runner.py:

```json
[
  {"channel": "github-repos", "query": "self-evolving agent", "max_results": 15},
  {"channel": "zhihu", "query": "自进化 AI agent 框架", "max_results": 10},
  {"channel": "web-ddgs", "query": "self-evolving agent startup 2026", "max_results": 10}
]
```

Each entry needs: `channel` (from select-channels output), `query` (the search text), `max_results` (optional, default 10).

# Language Adaptation Rules

| Channel | Query language | Example |
|---|---|---|
| zhihu, bilibili, csdn, juejin, 36kr, infoq-cn, weibo, xueqiu, xiaoyuzhou, xiaohongshu, douyin, wechat | Chinese | "AI智能体自进化框架" |
| All other channels | English | "self-evolving AI agent framework" |

Translate the core search intent, don't just transliterate. Keep proper nouns (project names, paper titles) in original language on all channels.

# Quality Bar

The goal is not "many queries."
The goal is a compact set of queries that attack the task from different angles and produce non-overlapping evidence.
