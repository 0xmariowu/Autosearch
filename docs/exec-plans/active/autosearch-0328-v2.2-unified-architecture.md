# AutoSearch v2.2 — V1 Capabilities + V2 Evolvability

## Positioning

AutoSearch is a self-evolving research agent. V1 had the computation (LLM scoring, gene pool, 14 connectors, goal system, anti-cheat, 290 sessions of accumulated learning). V2 had the evolvability (skills architecture, AVO autonomy, meta-capabilities). V2.2 unifies both: V1's proven capabilities restored as evolvable skills, plus V2's meta-capabilities and agent autonomy.

**V2.2 = V1's brain + V2's skeleton + new meta-capabilities.**

## Design Sources

- **AVO paper** §3: `Vary(P_t) = Agent(P_t, K, f)`. Agent IS the variation operator.
- **Superpowers/Vercel**: Skill format — name + description frontmatter, free-form body.
- **V1 codebase**: 12,760 lines of proven search capabilities to restore as skills.
- **Bitter lesson**: Computation wins. V2 removed computation (LLM scoring → keyword counting). V2.2 restores it.
- **V2.0-V2.1 discussion**: Agent autonomy, five meta-skills, agent's own knowledge as source, knowledge synthesis.

## Architecture

```
autosearch/v2/
├── PROTOCOL.md             ← agent protocol (~100 lines, fixed)
├── judge.py                ← scoring function f (fixed, 7 dimensions)
├── skills/                 ← knowledge base K (flat, AVO evolves)
│   ├── [V1 restored skills]
│   ├── [V2 meta-skills]
│   └── [AVO creates more]
└── state/                  ← lineage P_t (AVO writes)
    ├── config.json
    ├── worklog.jsonl
    ├── patterns.jsonl       ← migrated: 27 V1 patterns
    ├── evolution.jsonl      ← migrated: 290 V1 entries
    ├── outcomes.jsonl       ← migrated: 31 V1 entries
    └── [AVO creates more]
```

Skill format: superpowers standard (name + description, free-form body). No type enum, no required sections.

## Complete Skill Inventory

### Category A: V1 Capabilities Restored as Skills

Each skill restores a proven V1 capability. The body contains strategy, not bash templates. The agent (Claude) has judgment — skills guide decisions, not dictate steps.

#### A1: `llm-evaluate.md` — LLM-based result scoring
```yaml
---
name: llm-evaluate
description: "Score individual search results for relevance using LLM judgment. Use after collecting raw results, before final scoring. Replaces keyword matching with semantic understanding."
---
```
Restores: V1's `LLMEvaluator` (engine.py:173-258). Haiku API scores each result's relevance to the task spec. Returns relevant/not-relevant + reason + suggested next queries. V2's judge.py only counted keywords — this is the missing "brain" that distinguishes "found it" from "found the right thing."

Key V1 logic to preserve:
- Top 10 results per evaluation batch
- Prompt: TARGET spec + result titles/previews → JSON {relevant, reason, next_queries}
- next_queries feed back into query generation (closed loop)
- 3-level JSON extraction fallback (raw → strip markdown → regex)

#### A2: `gene-query.md` — 5-dimensional query generation
```yaml
---
name: gene-query
description: "Generate search queries by combining genes from 5 dimensions: entity, pain_verb, object, symptom, context. Use when expanding a search task into diverse, targeted queries."
---
```
Restores: V1's `QueryGenerator` (engine.py:931-1013). The 5-dimensional decomposition produces queries like "ignores CLAUDE.md context" that targeted search terms can't match.

Key V1 logic to preserve:
- Gene categories: entity (WHO), pain_verb (ACTION), object (WHAT), symptom (HOW), context (WHERE)
- Mix ratio: 20% LLM suggestions, 20% winning patterns, 60% gene combinations
- Gene combination: sample 2-3 categories, pick 1 value each, join
- Seed queries from config, never recency-capped

#### A3-A16: Platform connector skills (14 total)

Each restores one V1 connector. 8 free, 6 paid (AVO can choose based on available API keys).

| # | Skill name | V1 source | API | Free? |
|---|------------|-----------|-----|-------|
| A3 | `search-github-repos.md` | engine.py:739-779 | gh CLI | Yes |
| A4 | `search-github-issues.md` | engine.py:781-822 | gh CLI | Yes |
| A5 | `search-github-code.md` | engine.py:824-865 | gh CLI | Yes |
| A6 | `search-ddgs.md` | engine.py:477-530 | ddgs Python | Yes |
| A7 | `search-reddit.md` | engine.py:330-363 | Reddit API | Yes |
| A8 | `search-hackernews.md` | engine.py:378-402 | Algolia API | Yes |
| A9 | `search-huggingface.md` | engine.py:922-978 | HF Hub API | Yes |
| A10 | `search-searxng.md` | engine.py:445-475 | Local HTTP | Yes |
| A11 | `search-exa.md` | engine.py:417-442 | Exa API | Paid |
| A12 | `search-reddit-exa.md` | engine.py:366-374 | Exa API | Paid |
| A13 | `search-hn-exa.md` | engine.py:405-413 | Exa API | Paid |
| A14 | `search-tavily.md` | engine.py:531-563 | Tavily API | Paid |
| A15 | `search-twitter-exa.md` | engine.py:867-875 | Exa API | Paid |
| A16 | `search-twitter-xreach.md` | engine.py:877-920 | XReach API | Paid |

#### A17: `goal-loop.md` — Goal-driven research cycle
```yaml
---
name: goal-loop
description: "Run a multi-round research cycle against a specific goal with rubric-based evaluation. Use for focused research tasks where you have clear success criteria and dimensions to cover."
---
```
Restores: V1's goal system (goal_loop.py + goal_judge.py + goal_runtime.py). Multi-round search with dimension-based rubric, mutation strategy (append missing terms to best query), and stop conditions (target score reached OR 2 rounds no improvement OR max rounds).

Key V1 logic to preserve:
- Goal case structure: {problem, providers, seed_queries, rubric with weighted dimensions, target_score}
- Heuristic scoring: keyword matching with concept aliasing per rubric dimension
- Query mutation: top missing terms appended to best-performing query
- Bundle evaluation: cumulative evidence against multiple dimensions

#### A18: `anti-cheat.md` — Score gaming detection
```yaml
---
name: anti-cheat
description: "Validate search results for gaming patterns before accepting them. Use after scoring to detect novelty collapse, source concentration, or query concentration that inflates scores artificially."
---
```
Restores: V1's evaluation_harness.py:64-132 + selector.py:147-182.

Key V1 thresholds to preserve:
- Hard fail: novelty_ratio < 0.01 OR new_unique_urls == 0
- Warning: source_diversity < 0.15, source_concentration > 0.82, query_concentration > 0.70
- Metrics: Simpson diversity, domain concentration, title repetition (3-word prefix)

#### A19: `provider-health.md` — Platform health tracking
```yaml
---
name: provider-health
description: "Track which search platforms are working well, which are failing, and auto-reorder platform priority. Use at session start to skip broken platforms and prioritize reliable ones."
---
```
Restores: V1's project_experience.py:153-443.

Key V1 logic to preserve:
- Provider statuses: cooldown (error_rate ≥ 0.70 + no new URLs), preferred (0 errors + new_url_rate ≥ 0.08), active (everything else)
- Per-query-family ordering (academic → Exa preferred, code → GitHub preferred)
- Health summary with cooldown list and top providers ranked

#### A20: `outcome-tracker.md` — Query-to-value feedback loop
```yaml
---
name: outcome-tracker
description: "Track which search queries led to results that were actually used (intaked into Armory, produced WHEN/USE blocks). Use periodically to boost queries that produce real value."
---
```
Restores: V1's outcomes.py:1-312.

Key V1 logic to preserve:
- Two phases: record_intakes (after intake) + track_outcomes (weekly)
- Provenance: query → harvested URLs → repo → when_use_count
- Outcome boost: highest-outcome queries written back to patterns.jsonl
- 31 existing outcome entries to migrate

#### A21: `research-mode.md` — Speed/balanced/deep mode selection
```yaml
---
name: research-mode
description: "Select research depth mode based on task urgency and complexity. Speed mode for quick lookups, balanced for standard research, deep for comprehensive surveys."
---
```
Restores: V1's research/modes.py:1-146.

Key V1 configurations to preserve:
- Speed: no planning, 1 branch depth, 3 queries max, no page fetching
- Balanced: planning enabled, 3 branch depth, 5 queries, 2 page fetches
- Deep: full planning, 5 branch depth, 7 queries, 4 page fetches, prefer acquired text

### Category B: V2 Meta-Skills (new capabilities V1 didn't have)

#### B1: `create-skill.md` — Create new skills
```yaml
---
name: create-skill
description: "Create a new skill when you discover a data source, tool, or capability that would benefit future searches. Follow superpowers standard: name + description frontmatter, free-form body."
---
```

#### B2: `observe-user.md` — Understand user context
```yaml
---
name: observe-user
description: "Read user context at session start — CLAUDE.md, project files, git history, conversation context. Store observations in state/ for personalizing search."
---
```

#### B3: `extract-knowledge.md` — Learn from search results
```yaml
---
name: extract-knowledge
description: "After scoring, deeply read high-quality results to extract reusable knowledge — facts, patterns, relationships, entities. Store in state/ for future searches."
---
```

#### B4: `interact-user.md` — Dialogue with user
```yaml
---
name: interact-user
description: "Communicate with the user during search — clarify ambiguous intent, show intermediate results, collect feedback on delivery quality."
---
```

#### B5: `discover-environment.md` — Scan available tools
```yaml
---
name: discover-environment
description: "Scan runtime environment for available tools, MCP servers, API keys, and models. Use create-skill to make skills for discovered tools."
---
```

### Category C: New skills (gaps identified from V1-vs-Claude comparison)

#### C1: `use-own-knowledge.md` — Agent's training knowledge as source
```yaml
---
name: use-own-knowledge
description: "Use your own training knowledge as a search source alongside API results. You already know foundational works, key projects, and domain concepts — don't wait to 'search' for things you already know."
---
```
Addresses: native Claude beat AutoSearch because Claude used training knowledge (STaR, Reflexion, Voyager) that no API search found.

#### C2: `synthesize-knowledge.md` — Conceptual framework generation
```yaml
---
name: synthesize-knowledge
description: "After collecting results, synthesize them into a conceptual framework — categorize by dimensions, identify design patterns, analyze risks, map the landscape. Don't just list what you found; explain what it means."
---
```
Addresses: native Claude organized by concept (6 evolution dimensions, 7 design patterns, risk analysis). AutoSearch organized by platform (GitHub results, arXiv results).

#### C3: `fetch-webpage.md` — Fetch full URL content
```yaml
---
name: fetch-webpage
description: "Fetch and extract readable content from a URL. Use when search snippets are insufficient and you need the full article, README, or documentation."
---
```

**Total: 26 seed skills** (21 V1 restored + 5 meta-skills from V2)
Plus C1-C3 as new capabilities = **29 skills**.

## PROTOCOL.md (v2.2)

~100 lines. Agent autonomy, not pipeline.

1. **Identity**: You are AutoSearch, a self-evolving research agent. You are the AVO variation operator. You autonomously search, learn, synthesize, and improve.
2. **Inputs**: P_t = state/ (history, patterns, knowledge). K = skills/ (capabilities). f = judge.py (scoring).
3. **Startup**: Read worklog.jsonl for crash recovery. Read patterns.jsonl and evolution.jsonl for accumulated learning. Run discover-environment.md. Run observe-user.md.
4. **The loop**: Each iteration is one autonomous variation step. You decide what to do — which skills to use, what to search, how to synthesize, when to deliver. Read skill descriptions to find relevant capabilities.
5. **Your own knowledge**: You are Claude. Your training knowledge is a source alongside search results. Use use-own-knowledge.md. Don't limit yourself to what API searches return.
6. **Constraints**: judge.py is fixed. worklog/patterns/evolution/outcomes are append-only. Skill and config changes go through git commit (improve → commit, regress → revert). Don't modify PROTOCOL.md or judge.py.
7. **Self-supervision**: 3 flat generations → redirect strategy. 3 consecutive reverts → try different approach. Read anti-cheat.md before accepting results.
8. **Delivery**: Score meets threshold OR budget exhausted → run synthesize-knowledge.md → deliver. Never deliver a list — deliver a framework with insight.

## judge.py v2.2

### Dimensions (7 total)

| Dimension | Source | What it measures |
|-----------|--------|------------------|
| quantity | V1 | unique URLs / target |
| diversity | V1 | Simpson index on source platforms |
| relevance | **V1 LLM** | LLM-scored relevance (restored from V1, replaces keyword matching) |
| freshness | V1 | results within 6 months |
| efficiency | V1 | unique URLs / queries used |
| latency | V2.1 new | time to delivery vs budget |
| adoption | V2.1 new | user feedback signal (cross-session) |

**Critical change**: `relevance` switches from V2's keyword counting to V1's LLM-based scoring. This is the single biggest quality improvement — it's the difference between "found URLs with matching words" and "found URLs that are actually relevant to the task."

### Implementation
- relevance: agent runs llm-evaluate.md, writes per-result scores to evidence JSONL metadata. judge.py reads `metadata.llm_relevant` field. relevance = count(llm_relevant=true) / total.
- latency: agent writes state/timing.json. judge.py reads it.
- adoption: agent writes state/adoption.json. judge.py reads it. Default 0.5.

## Data Migration

### From V1 → V2.2 state/

| V1 file | V2.2 destination | Entries | Action |
|---------|-----------------|---------|--------|
| patterns.jsonl | state/patterns.jsonl | 27 | Copy, convert format if needed |
| evolution.jsonl | state/evolution.jsonl | 290 | Copy as historical reference |
| outcomes.jsonl | state/outcomes.jsonl | 31 | Copy for outcome-tracker.md |
| playbook-final.jsonl | state/playbook.jsonl | 30 | Copy as additional patterns |

### What NOT to migrate
- V1 Python code — replaced by skills
- V1 genome/ — replaced by config.json + skills
- V1 capabilities/ — replaced by platform skills

---

## Execution Plan

### F000: Pre-requisites
- [ ] S1: Update CLAUDE.md — replace V2.0 rules with V2.2 rules BEFORE any file changes
- [ ] S2: Migrate V1 data files to state/ (patterns, evolution, outcomes, playbook)

Verify: CLAUDE.md mentions v2.2, state/ has 4 migrated files with correct entry counts

### F001: PROTOCOL.md + infrastructure
- [ ] S1: Write new PROTOCOL.md (~100 lines, agent autonomy, V1+V2 unified)
- [ ] S2: Flatten skills/ directory
- [ ] S3: Delete skill-spec.md
- [ ] S4: Update config.json (add latency_budget, adoption_default, V1 provider weights)
- [ ] S5: Delete old V2.0 skills (will be rewritten)

Verify: PROTOCOL.md under 120 lines, skills/ is flat, no V2.0 skill files remain

### F002: judge.py v2.2
- [ ] S1: Add latency dimension
- [ ] S2: Add adoption dimension
- [ ] S3: Change relevance from keyword matching to reading metadata.llm_relevant field
- [ ] S4: Update config dimension_weights for 7 dimensions
- [ ] S5: Update + add tests

Verify: judge.py outputs 7 dimensions, relevance reads llm_relevant from metadata, all tests pass

### F003: V1 core skills (A1-A2, A17-A21)
- [ ] S1: Write llm-evaluate.md (V1 LLMEvaluator logic as strategy guide)
- [ ] S2: Write gene-query.md (V1 5-dimensional decomposition)
- [ ] S3: Write goal-loop.md (V1 goal system)
- [ ] S4: Write anti-cheat.md (V1 evaluation harness)
- [ ] S5: Write provider-health.md (V1 experience layer)
- [ ] S6: Write outcome-tracker.md (V1 WHEN/USE feedback)
- [ ] S7: Write research-mode.md (V1 speed/balanced/deep)

Verify: each skill captures key V1 logic, uses superpowers format

### F004: Platform skills (A3-A16)
- [ ] S1-S8: Write 8 free platform skills (github-repos, github-issues, github-code, ddgs, reddit, hackernews, huggingface, searxng)
- [ ] S9-S14: Write 6 paid platform skills (exa, reddit-exa, hn-exa, tavily, twitter-exa, twitter-xreach)

Verify: each skill has correct API reference, free/paid status clear, 14 total

### F005: Meta-skills + new capabilities (B1-B5, C1-C3)
- [ ] S1: Write create-skill.md
- [ ] S2: Write observe-user.md
- [ ] S3: Write extract-knowledge.md
- [ ] S4: Write interact-user.md
- [ ] S5: Write discover-environment.md
- [ ] S6: Write use-own-knowledge.md
- [ ] S7: Write synthesize-knowledge.md
- [ ] S8: Write fetch-webpage.md

Verify: each meta-skill describes capability without prescribing exact implementation

### F006: End-to-end validation
- [ ] S1: Run same task as comparison test ("self-evolving AI agent resources") — verify output quality closer to native Claude
- [ ] S2: Verify llm-evaluate.md filters irrelevant results (relevance should be real, not 0.993)
- [ ] S3: Verify gene-query.md produces diverse queries from 5 dimensions
- [ ] S4: Verify anti-cheat catches score gaming
- [ ] S5: Verify synthesize-knowledge.md produces conceptual framework (not platform-organized list)
- [ ] S6: Verify use-own-knowledge.md contributes foundational works (STaR, Reflexion, etc.)
- [ ] S7: Verify migrated patterns/evolution data is read during PLAN

Verify: delivery report has conceptual categories, risk analysis, and foundational works. judge relevance score is realistic (not inflated). Migrated patterns appear in worklog.

### F007: Documentation
- [ ] S1: Update CHANGELOG.md
- [ ] S2: Update HANDOFF.md
- [ ] S3: Update /autosearch Claude Code skill
- [ ] S4: Move v2.0 and v2.1 plans to completed/

## Dependency Graph

```
F000 (prereqs) ──→ F001 (protocol) ──→ F003 (core skills) ──→ F006 (validation)
                        │                     │                      │
                        └──→ F002 (judge) ────┘                      │
                                                                     │
                             F004 (platforms, parallel w/ F003) ──→ F006
                             F005 (meta-skills, parallel w/ F003) → F006
                                                                     │
                                                                     ↓
                                                               F007 (docs)
```

F003, F004, F005 can run in parallel after F001+F002 complete.

## What V2.2 Fixes from the Comparison

| Native Claude won because | V2.2 answer |
|---------------------------|-------------|
| Claude used training knowledge | use-own-knowledge.md — agent's knowledge is a source |
| Organized by concept, not platform | synthesize-knowledge.md — produce frameworks, not lists |
| LLM judgment on relevance | llm-evaluate.md — restored V1's Haiku-based scoring |
| No protocol overhead | PROTOCOL.md ~100 lines, agent autonomy, no pipeline |
| Covered risk/commercial/foundational | extract-knowledge.md + use-own-knowledge.md + synthesize-knowledge.md |
| 40+ projects with star counts | 14 platform connectors (restored from V1), 8 free + 6 paid |

## What V2.2 Has That Native Claude Doesn't

| Capability | Why it matters |
|------------|---------------|
| Cross-session learning (patterns.jsonl) | 50th search is better than 1st |
| Provider health tracking | Auto-skip broken platforms |
| Anti-cheat | Detect when scores are gamed |
| Outcome tracking | Know which queries produce REAL value |
| Goal-driven research cycles | Multi-round focused research with rubric |
| AVO self-evolution | System improves itself over time |
| Skill creation | Agent can create new capabilities |

## Open Questions

- Q1: Should V1's genome system (JSON genome + vary.py mutations) be restored as a skill, or is config.json + AVO sufficient?
- Q2: V1's paid connectors (Exa, Tavily, XReach) — should these be seed skills or let AVO discover them via discover-environment.md + create-skill.md?
- Q3: V1's reranking system (lexical.py + hybrid reranking) — restore as skill or let AVO evolve its own?
- Q4: How to handle the Anthropic API key for llm-evaluate.md? It runs inside Claude Code (which IS Claude), so can it use itself as evaluator instead of a separate API call?

## Decision Log

- 2026-03-28: V2.2 = V1 capabilities + V2 evolvability + new meta-capabilities
- 2026-03-28: V2 was an amputation, not simplification. LLM scoring, gene pool, 14 connectors, goal system, anti-cheat, outcome tracking — all need to come back as skills.
- 2026-03-28: Skill format follows superpowers standard. V2.0's 8-field/7-section rigid format was wrong.
- 2026-03-28: Agent autonomy from v2.1 preserved. AVO is NOT a pipeline.
- 2026-03-28: Native Claude comparison proved: keyword-based relevance scoring is useless. LLM-based scoring is essential.
- 2026-03-28: "Don't just list, synthesize" — synthesize-knowledge.md is a core skill, not a nice-to-have.
- 2026-03-28: Agent's own training knowledge is a valid source. Not using it is leaving value on the table.
- 2026-03-28: V1 data migration preserves 290 evolution entries + 27 patterns + 31 outcomes + 30 playbook entries. Starting from zero wastes accumulated intelligence.
