---
name: autosearch:model-routing
description: Advisory skill — three-tier (Fast / Standard / Best) model routing catalog for autosearch skills. Tells the runtime AI which tier each leaf skill needs, and how to escalate or de-escalate. Autosearch does not switch models itself; the runtime AI is the decision-maker.
version: 0.1.0
layer: meta
domains: [meta, model-routing]
scenarios: [model-tier-decision, cost-optimization, quality-vs-speed]
trigger_keywords: [model tier, 模型档, which model, cost, tier decision]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Model Tier Routing — Advisory

**Routing principle**: most steps use the runtime's cheapest model; only the critical 1–2 steps use the best model.

Autosearch stamps every leaf skill with a `model_tier` suggestion. This skill tells the runtime AI what the three tiers mean, which skills default to which tier, and when to escalate or de-escalate.

## Three Tiers

| Tier | Typical runtime pick | When used | Share of skills |
|---|---|---|---|
| **Fast** | Claude Haiku / GPT-5-mini / Gemini 2.5 Flash / Qwen local | Retrieval, normalization, schema checks, URL reading, metadata | ~60% |
| **Standard** | Claude Sonnet / GPT-5.4 / Gemini 2.5 Pro | Semantic ranking, evidence extraction, mid-complexity planning | ~25% |
| **Best** | Claude Opus / GPT-5 / Gemini 2.5 Ultra | Clarify, decompose, synthesize, evaluate delivery, skill evolution — the 1-2 steps that shape everything | ~15% |

## Tier Assignments

Each autosearch skill carries `model_tier: Fast|Standard|Best` in its frontmatter. The runtime AI reads that field before choosing which provider/model to call.

### Best (~13 skills — the critical 1-2 steps per session)

- `clarify` — disambiguate intent (wrong clarification cascades)
- `systematic-recall` — global recall planning (missed angles compound)
- `decompose-task` — breaking a multi-part problem
- `synthesize-knowledge` — produce frameworks, not link lists
- `evaluate-delivery` — quality gate on final output
- `knowledge-map` — cross-evidence relation graph
- `check-rubrics` / `generate-rubrics` — rubric-driven evaluation
- `auto-evolve` / `create-skill` — anything that changes future behavior
- `goal-loop` — multi-round goal convergence
- `graph-search-plan` (when present) — research plan as graph
- `perspective-questioning` (when present) — multi-persona question generation
- `reflective-search-loop` (when present) — explicit gaps / visited / bad-URLs loop

### Standard (~20 skills — semantic judgment, structurable)

- `select-channels` — pick 5-10 channels from 41
- `gene-query` — combinatorial query generation
- `consult-reference` — prior art lookup
- `rerank-evidence` — semantic ranking of results
- `llm-evaluate` — per-item relevance score
- `anti-cheat` — spam / score-gaming detection
- `assemble-context` — token-budgeted context assembly
- `extract-knowledge` — structured extraction from text
- `fetch-crawl4ai` / `fetch-playwright` / `fetch-firecrawl` / `follow-links`
- `experience-compact` — rule promotion
- `observe-user` — user preference inference
- `research-mode` — speed vs. deep choice
- `delegate-subtask` (when present) / `trace-harvest` / `citation-index` / `recent-signal-fusion`
- `interact-user` / `pipeline-flow` / `outcome-tracker`

### Fast (~60 skills — bulk of every session)

- **All 41 channel skills** (`search-*`) — retrieval, not reasoning
- `fetch-jina`, `fetch-webpage` — URL → Markdown
- `yt-dlp` + three video-to-text transcription skills — mechanical extraction
- `mcporter` routing skill
- `discover-environment`, `provider-health` — env probing
- `normalize-results`, `extract-dates` — schema + dedupe
- `autosearch:router` — routing decision, no deep reasoning
- `experience-capture` — append-only event write, often no LLM
- `context-retention-policy` (when present) — keep-last-k rules

## Escalation Rules

Start a step at its default tier. Escalate **only** when:

- Conflicting evidence from multiple sources needs semantic reconciliation → `Standard` from `Fast`.
- Final synthesis or skill-evolution output depends on this step → `Best` from `Standard`.
- User explicitly asks for deeper analysis / higher quality on the topic.

De-escalate when:

- A Standard step is running on highly structured / deterministic input (e.g. `rerank-evidence` on 3 items with clear metadata) → drop to Fast.
- Exploratory / draft iteration loop — first passes can be Fast, final pass Best.

## Runtime Advisory (non-binding)

Autosearch cannot force the runtime to change models. The `model_tier` field is a **suggestion** to help the runtime AI choose a provider/model route that matches the quality bar of the step. The runtime AI may ignore the advisory if it has better information (e.g. user specified a fixed model).

## Hard Rules

- Cost: run the cheapest model that clears the quality bar; reserve the best model for the 1–2 steps that shape the whole session outcome.
- Judge: keep LLM-as-judge (pairwise A/B preference, open_deep_research pattern). Do **not** invent N-dimensional × 0/3/5 numeric rubrics.
- AVO: any `Best`-tier skill that modifies SKILL.md (like `auto-evolve`) must commit via `scripts/committer` and be reversible via `git revert`.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
