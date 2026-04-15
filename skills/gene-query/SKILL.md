---
name: gene-query
description: "Use when you need to expand a task into diverse search queries, perform query expansion, or generate search terms by combining entity, pain_verb, object, symptom, and context gene dimensions into targeted keyword research phrases."
---

# Workflow

1. **Extract genes** — Parse the task into six dimensions (entity, pain_verb, object, symptom, context, content_type).
2. **Check knowledge map** — If systematic-recall.md produced a map, identify GAP/LOW/MEDIUM items to target.
3. **Build gene pool** — Gather candidates from the task, winning history, query performance data, and your own judgment.
4. **Generate queries** — Combine 2-3 dimensions per query following the mix ratio (60% gene combos, 15% LLM, 15% patterns, 10% proven winners).
5. **Apply mandatory rules** — Ensure topic-specific required queries are included (academic, tool/product, freshness).
6. **Adapt language** — Translate queries for Chinese-language channels; keep English for all others.
7. **Deduplicate and cap** — Remove queries sharing 60%+ content words; stay within `max_total_queries`.
8. **Output JSON** — Emit the final array for search_runner.py.

# Model Recommendation

Use Haiku when possible — query generation is a structured expansion task that runs effectively at lower cost. Set `model: "haiku"` when spawning an agent.

# The Six Dimensions

- `entity` — WHO is involved
- `pain_verb` — ACTION or failure mode
- `object` — WHAT artifact, tool, concept, or target
- `symptom` — HOW the problem appears
- `context` — WHERE or under what condition
- `content_type` — WHAT KIND of result (repo, paper, blog, tutorial, company, video, awesome-list, conference-workshop, company-product, comparison)

Good queries need only 2-3 dimensions. Do not cram all six into every query.

Use `content_type` to steer toward underrepresented evidence. If the bundle is heavy on repos, target missing types explicitly (e.g., "self-evolving agent tutorial", "self-improving AI startup company").

# Gap-Driven Generation

When systematic-recall.md has produced a knowledge map, generate queries from GAPS, not from the task text.

- **GAP / LOW confidence** — Convert to a specific search query targeting the platform most likely to fill it.
  Example: GAP in "commercial players" → `"self-evolving AI agent startup 2026"` on web-ddgs
- **MEDIUM confidence** — Generate a verification query.
  Example: MEDIUM on "STOP framework" → `"STOP self-taught optimizer latest"` on arxiv/web
- **HIGH confidence** — Skip. Already covered by own-knowledge.

**Minimum query floor**: ALWAYS generate at least 4 queries regardless of confidence levels. Search adds timeliness (post-cutoff developments), specificity (concrete companies, repos, data points), and verification (HIGH confidence does not mean correct).

If all dimensions are HIGH, generate 4 freshness-check queries: topic + "2026" / "latest" / "new" across selected channels.

# Mandatory Query Rules

## Academic/research topics

- At least 1 query with `content_type=conference-workshop` (e.g., "topic workshop NeurIPS ICML 2025")
- At least 1 query targeting `arxiv` or `semantic-scholar`

## Tool/product topics

- At least 1 query with `content_type=company-product` (e.g., "topic startup company funding")
- At least 1 query targeting `producthunt` or `crunchbase`
- At least 1 query targeting enterprise/non-GitHub alternatives (e.g., "GitLab Duo", "AWS CodeGuru") when topic involves developer tools
- At least 1 query with `content_type=comparison` including "pricing" or "deployment" (e.g., "topic pricing free tier enterprise")

## Any topic

- At least 1 query targeting `twitter` for recent announcements
- At least 1 Chinese-language query if any Chinese channel is selected
- At least 2 freshness queries with explicit year markers (e.g., "topic 2026") for Standard or Deep depth — target arxiv for one, web-ddgs for the other

# Input Sources

Build the gene pool from four places:

1. **Task** — entities, artifacts, constraints, and pain language from the user or goal case
2. **Winning history** — patterns from `state/patterns.jsonl` (filter to `winning_pattern` and `platform_insight` types only) and proven queries from `state/outcomes.jsonl`
3. **Query performance** — from `state/query-outcomes.jsonl`. Boost queries with `relevant_rate >= 0.7` AND `results_count >= 3`. Suppress queries matching patterns with `relevant_rate <= 0.2` OR `results_count == 0` for the same `topic_type`.
4. **Your judgment** — missing synonyms, domain terms, and alternate framings not yet in state

# Mix Ratio

- 60% gene combinations
- 15% LLM suggestions
- 15% winning patterns (from state/patterns.jsonl)
- 10% high-performing queries (from state/query-outcomes.jsonl)

Keep the ratio in spirit, not as rigid bookkeeping. Backfill from other sources if one is exhausted.

# Combination Rule

For each gene-combination query:

- Pick 2 or 3 dimensions
- Pick exactly 1 value from each chosen dimension
- Join into a terse search phrase

Example shapes: `entity + object`, `pain_verb + object`, `entity + symptom + context`, `pain_verb + object + context`.

# Query Construction Heuristics

- One **anchor term** binding the topic + one **discriminator** changing what results appear. Add a third term only when it meaningfully sharpens retrieval.
- Target **3-5 words** for most channels. Academic channels (arxiv, semantic-scholar, google-scholar) may use up to 7. Split overlength queries into two shorter ones.
- Prefer concrete tokens over generic prose, symptoms over emotional adjectives, observable failures over abstract aspirations.
- Use winning query patterns from state when they clearly transfer. Keep seed queries from the task or config even if not gene-generated.

# Diversity and Dedup

Vary the dimension mix: some entity-led, some pain-led, some object-led, some context-led. Avoid a pool where every query starts from the same noun phrase.

Deduplicate semantically, not only by exact string. Final dedup pass: if two queries share 60%+ content words, keep the more specific one. The final set MUST NOT exceed `max_total_queries` from config.json.

# Freshness and Time

Do not hard-cap all queries by recency. Add time qualifiers only when the task explicitly needs freshness or the prior round showed stale retrieval.

# Output Format

JSON array compatible with search_runner.py:

```json
[
  {"channel": "github-repos", "query": "self-evolving agent", "max_results": 15},
  {"channel": "zhihu", "query": "自进化 AI agent 框架", "max_results": 10},
  {"channel": "web-ddgs", "query": "self-evolving agent startup 2026", "max_results": 10}
]
```

Each entry needs: `channel` (from select-channels output), `query` (search text), `max_results` (optional, default 10).

# Language Adaptation Rules

| Channel | Query language | Example |
|---|---|---|
| zhihu, bilibili, csdn, juejin, 36kr, infoq-cn, weibo, xueqiu, xiaoyuzhou, xiaohongshu, douyin, wechat | Chinese | "AI智能体自进化框架" |
| All other channels | English | "self-evolving AI agent framework" |

Translate the core search intent, don't just transliterate. Keep proper nouns (project names, paper titles) in original language on all channels.

# Quality Bar

The goal is not "many queries."
The goal is a compact set of queries that attack the task from different angles and produce non-overlapping evidence.
