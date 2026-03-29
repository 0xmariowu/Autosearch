# AutoSearch v2.1 — Self-Evolving Search Agent

## Positioning

AutoSearch is a self-evolving agent that finds, understands, and delivers information — getting better with every use. Search is the first capability, not the product.

One AVO. One agent. It autonomously decides what to consult, what to change, and what to test. The only fixed things are the scoring contract and the skill format.

## Design Sources

- **AVO paper** (arXiv:2603.24517) §3: `Vary(P_t) = Agent(P_t, K, f)`. Agent IS the variation operator. Not a pipeline — a self-directed autonomous loop.
- **Superpowers** (obra/superpowers): Skill format standard. name + description frontmatter, free-form body, description-based dispatch.
- **Vercel Skills** (vercel-labs/skills): Agent-agnostic skill ecosystem. SKILL.md format, auto-discovery, package management.
- **Bitter lesson**: Don't hand-design what AVO can learn. Provide mechanisms, not prescriptions.

## AVO Formalization (faithful to paper §3)

```
Vary(P_t) = Agent(P_t, K, f)

P_t = state/         — full lineage: worklog.jsonl, patterns.jsonl, config.json
K   = skills/         — domain knowledge: all SKILL.md files
f   = judge.py        — fixed scoring function
```

The agent is NOT confined to a pipeline. Within a single variation step, it may:
- Read multiple skills from K
- Consult prior results in P_t
- Implement changes (modify config, create/edit skills, change strategy)
- Test changes (run search, invoke judge.py)
- Diagnose failures (analyze why score didn't improve)
- Repair and retry (edit-evaluate-diagnose cycle, §3.2)
- Commit or discard (git commit if improves, git revert if not)

Self-supervision (§3.3): detect stall or unproductive cycles → redirect exploration.

### v2.0 mistake corrected

v2.0 encoded AVO as a rigid pipeline: PLAN→SEARCH→SCORE→DIAGNOSE→EVOLVE→RECORD. This is exactly what the AVO paper argues AGAINST — "confining the LLM to candidate generation within a prescribed pipeline fundamentally limits what the LLM can discover" (§1). v2.1 gives the agent autonomy.

## Skill Format (following superpowers/vercel standard)

### v2.0 format (wrong)
```yaml
---
name: github
type: platform
version: "1.0"
requires: [gh]
triggers: [github, repo, ...]
cost: free
platforms: [github]
dimensions: []
---
## Purpose (required)
## When to Use (required)
## Execute (required — step-by-step bash)
## Parse (required — exact JSON schema)
## Score Hints (required)
## Known Limitations (required)
## Evolution Notes (required)
```
8 frontmatter fields, 7 required sections, bash templates. Over-specified.

### v2.1 format (correct — following superpowers/vercel)
```yaml
---
name: github
description: "Search GitHub for repos and issues when looking for code, frameworks, libraries, or open-source tools."
---
```
2 frontmatter fields. Body is free-form markdown.

**Rules (from superpowers + vercel standards):**
- `name`: required, lowercase with hyphens, unique across skills/
- `description`: required, tells the agent WHEN to use this skill. This IS the dispatch mechanism.
- Body: free-form. Strategy, tools, signals, constraints, examples — whatever the agent needs. No required sections.
- Skills are GUIDES for a capable agent, not step-by-step templates for a dumb executor.
- A skill can be 10 lines or 300 lines.

**Dispatch**: Agent reads all skill descriptions, matches against current task. Superpowers' 1% rule: "If there is even a 1% chance a skill might apply, you ABSOLUTELY MUST invoke the skill."

## Architecture

```
autosearch/v2/
├── PROTOCOL.md        ← agent operating protocol (fixed, ~100 lines)
├── judge.py           ← scoring function f (fixed)
├── skills/            ← knowledge base K (flat directory, AVO evolves)
│   ├── github.md
│   ├── hackernews.md
│   ├── query-expand.md
│   ├── create-skill.md
│   ├── observe-user.md
│   ├── ...
│   └── (AVO creates more)
└── state/             ← lineage P_t (AVO writes)
    ├── config.json
    ├── worklog.jsonl
    ├── patterns.jsonl
    └── (AVO creates more as needed)
```

No subdirectories in skills/. No type hierarchy. Flat.

## PROTOCOL.md (simplified)

v2.0 PROTOCOL.md was 345 lines with a rigid 6-step pipeline. v2.1 should be ~100 lines:

1. **Identity**: You are AutoSearch. You are the AVO variation operator (§3). You autonomously search, learn, and improve.
2. **Inputs**: P_t (state/), K (skills/), f (judge.py). Read them.
3. **Startup**: Read worklog.jsonl. If last entry is an incomplete search_run (no following reflection for same session), resume from that generation's evidence. Otherwise start fresh.
4. **The loop**: Each iteration is one variation step. You decide what to do. Read skills for capabilities, read state for history, make changes, run judge.py, commit if better, revert if not.
5. **Constraints**: judge.py is fixed. worklog/patterns are append-only. Changes go through git. Don't modify PROTOCOL.md, judge.py, or meta-skills (create-skill, observe-user, extract-knowledge, interact-user, discover-environment).
6. **Self-supervision**: If stuck (3 flat generations), redirect. If unproductive (3 reverts in a row), try a different approach entirely.
7. **Delivery**: When score meets threshold or budget exhausted, deliver best result.

The protocol tells the agent WHAT it has access to and WHAT rules to follow. It does NOT tell the agent HOW to search — that's in skills.

## Five Meta-Skills

Following superpowers' pattern: `writing-skills` and `using-superpowers` are skills that give the agent meta-capabilities. AutoSearch needs five:

### create-skill.md
```yaml
---
name: create-skill
description: "Use when you discover a new data source, tool, or capability that would benefit future searches. Creates a new SKILL.md file."
---
```
Teaches AVO: you can write new .md files to gain new capabilities. Follows superpowers' `writing-skills` pattern. Includes quality criteria: new skill must be tested (TDD approach from superpowers).

### observe-user.md
```yaml
---
name: observe-user
description: "Use at the start of every search session to understand the user's context, tech stack, role, and current task."
---
```
Teaches AVO: you can read CLAUDE.md, project files, git history, conversation context. Store observations in state/. Use them to improve search relevance.

### extract-knowledge.md
```yaml
---
name: extract-knowledge
description: "Use after scoring to deeply read high-quality search results and extract reusable knowledge for future searches."
---
```
Teaches AVO: you can fetch full content from URLs, extract facts/patterns/relationships, store in state/. Use accumulated knowledge in future searches.

### interact-user.md
```yaml
---
name: interact-user
description: "Use when you need user input: clarify ambiguous search intent, show intermediate results, or collect feedback on delivery quality."
---
```
Teaches AVO: you can ask the user questions, present options, show progress, collect explicit feedback. Not every search needs interaction — AVO decides when it's worth it.

### discover-environment.md
```yaml
---
name: discover-environment
description: "Use at session start to scan available tools, MCP servers, API keys, and models in the runtime environment."
---
```
Teaches AVO: you can check what's installed (gh, curl, jq, pandoc), what MCP servers are connected, what API keys exist, what models are available. Use create-skill.md to make skills for discovered tools.

## judge.py Changes

### Current (v2.0): 5 dimensions
quantity, diversity, relevance, freshness, efficiency

### v2.1: Add 2 dimensions
- **latency**: `1.0 - min(elapsed_seconds / budget_seconds, 1.0)`. Budget from config.
- **adoption**: Signal from user interaction. Default 0.5 if no signal. Updated cross-session when interact-user.md provides feedback.

### Implementation
- **latency**: deterministic (timer). Agent writes `state/timing.json` with `{"start_ts": "...", "end_ts": "..."}` before calling judge.py. judge.py reads this file, computes elapsed seconds, scores against `config.scoring.latency_budget_seconds` (default 120).
- **adoption**: Agent writes `state/adoption.json` with `{"score": 0.5}` (default). interact-user.md updates this file with real feedback when available. judge.py reads `state/adoption.json` and uses the score value. Fallback: if file missing, adoption = 0.5.
- Both files are read by judge.py alongside the evidence file. judge.py's interface becomes: `python3 judge.py <evidence-file> [--target N]` (unchanged CLI, but reads state/ files internally).

## Seed Skills (initial K)

### Search platforms (rewrite from v2.0 in new format)
- `github.md` — gh CLI search for repos and issues
- `web-ddgs.md` — DuckDuckGo web search
- `reddit.md` — Reddit public JSON API
- `hackernews.md` — HN Algolia API
- `arxiv.md` — arXiv search API

### Search strategies (rewrite from v2.0 in new format)
- `query-expand.md` — turn vague input into multiple search queries
- `score-guide.md` — how to interpret judge.py dimensions for planning
- `deduplicate.md` — remove duplicate results across platforms
- `synthesize.md` — generate delivery artifact from evidence

### Tools (new)
- `fetch-webpage.md` — fetch URL content as markdown (Jina Reader or curl)
- `convert-to-markdown.md` — transform HTML/PDF to clean markdown

### Meta (see above)
- `create-skill.md`, `observe-user.md`, `extract-knowledge.md`, `interact-user.md`, `discover-environment.md`

Total: 16 seed skills. AVO creates more as needed.

## Migration from v2.0

### Skills rewrite
All 14 v2.0 skills get rewritten in new format:
- Strip 8-field frontmatter → 2 fields (name + description)
- Strip 7 required sections → free-form body
- Change bash templates → strategy guides
- Flatten from skills/{platforms,strategies,avo}/ → skills/

### State preservation
- worklog.jsonl: carry forward (append-only)
- patterns.jsonl: carry forward (append-only)
- config.json: simplify (remove fields that were only needed by rigid pipeline)
- evidence/: carry forward

### Protocol rewrite
- PROTOCOL.md: rewrite from 345 lines to ~100 lines
- Remove pipeline steps, add agent autonomy
- Keep constraints section

### skill-spec.md → DELETE
The spec is now the superpowers/vercel standard: name + description frontmatter, free-form body. This doesn't need a separate spec file — it's simple enough to state in PROTOCOL.md.

---

## Execution Plan

### F001: New PROTOCOL.md + skill format migration
- [ ] S0: Update CLAUDE.md rule 13 — replace v2.0 immutability rules with v2.1 rules BEFORE any files are deleted or rewritten. This is a prerequisite, not cleanup.
- [ ] S1: Write new PROTOCOL.md (~100 lines, AVO paper faithful). Include: crash recovery ("read worklog.jsonl on startup, if last entry is incomplete search_run, resume from that generation's evidence"), constraints (judge.py/PROTOCOL.md/meta-skills immutable), skill format (name + description, free-form body).
- [ ] S2: Flatten skills/ directory (remove subdirs)
- [ ] S3: Rewrite all 14 existing skills in new format (name + description frontmatter, free-form body, strategy-oriented content)
- [ ] S4: Delete skill-spec.md (format is now trivial, stated in PROTOCOL.md)
- [ ] S5: Simplify config.json (remove pipeline-specific fields)

Verify: all skills have correct 2-field frontmatter, PROTOCOL.md is under 120 lines, no references to old directory structure, CLAUDE.md rule 13 matches new file layout

### F002: judge.py expansion
- [ ] S1: Add latency dimension (timer-based, budget from config)
- [ ] S2: Add adoption dimension (default 0.5, updatable via worklog)
- [ ] S3: Update config.json dimension_weights for 7 dimensions
- [ ] S4: Update + add tests for new dimensions
- [ ] S5: Verify all existing tests still pass

Verify: judge.py outputs 7 dimensions, 14+ tests pass, Python 3.11

### F003: Five meta-skills
- [ ] S1: Write create-skill.md (following superpowers writing-skills pattern)
- [ ] S2: Write observe-user.md
- [ ] S3: Write extract-knowledge.md
- [ ] S4: Write interact-user.md
- [ ] S5: Write discover-environment.md

Verify: each skill has name + description frontmatter, body provides clear meta-capability guidance

### F004: Seed tool skills
- [ ] S1: Write fetch-webpage.md (Jina Reader or curl + readability)
- [ ] S2: Write convert-to-markdown.md (pandoc or python extraction)

Verify: each skill's approach works when agent follows it

### F005: End-to-end validation
- [ ] S1: Run a search session under new PROTOCOL.md — verify agent autonomy works
- [ ] S2: Verify observe-user.md reads user context and influences search
- [ ] S3: Verify extract-knowledge.md stores knowledge after search
- [ ] S4: Run second search on same topic — verify knowledge improves results
- [ ] S5: Verify discover-environment.md detects available tools
- [ ] S6: Verify judge.py scores 7 dimensions including latency

Verify: worklog contains records of ≥2 different types between consecutive search_run entries (proving non-rigid ordering), all search_run records have 7 dimension keys in score object

### F006: Documentation + cleanup
- [ ] S1: Update CLAUDE.md with v2.1 rules
- [ ] S2: Update CHANGELOG.md
- [ ] S3: Update HANDOFF.md
- [ ] S4: Update /autosearch Claude Code skill

## Dependency Graph

```
F001 (protocol + migration) ──→ F003 (meta-skills) ──→ F005 (validation)
        │                                                     │
        └──→ F002 (judge.py) ───────────────────────────→ F005
                                                              │
                                   F004 (tool skills) ───→ F005
                                                              │
                                                              ↓
                                                        F006 (docs)
```

**Critical ordering**: F001 and F002 must BOTH complete before F005. F003 depends on F001 (needs new format). F004 only depends on F003-S5 (discover-environment.md), not all of F003 — can start as soon as S5 is done.

## Reviewer Issues Addressed

From v2.1 plan review (8 issues):

| Issue | Resolution |
|-------|-----------|
| C1: meta-skill immutability not in PROTOCOL.md | F001-S1: new PROTOCOL.md states constraints clearly |
| C2: skill selection "win rate" doesn't exist | Removed. Description-based dispatch (superpowers pattern) replaces algorithmic selection |
| C3: adoption timing (cross-session only) | Clarified in judge.py section. Default 0.5 within session. |
| C4: tool skills have no valid type | Removed type field entirely. Superpowers format has no type. |
| I5: F001 verify too weak | Strengthened verify clauses |
| I6: Parse contract contradicts anti-prescription | Removed Parse requirement. Free-form body. |
| I7: F003-M5 must precede F004 | Noted in dependency graph |
| I8: F001+F002 must complete atomically | Noted in critical ordering |

## Open Questions

- Q1: Should PROTOCOL.md itself be a skill? (It IS instructions for the agent, just like a skill.)
- Q2: How does AVO distinguish "I should create a new skill" vs "I should modify an existing one" vs "I should just change config"? Currently this is left to agent judgment.
- Q3: Cross-session state: when AutoSearch runs in different Claude Code sessions, how does the agent resume from where it left off? worklog.jsonl crash recovery logic from v2.0 was useful.
- Q4: Should we adopt vercel-labs' `skills add/remove` package management for community skills?

## Decision Log

- 2026-03-28: Skill format follows superpowers/vercel standard (name + description, free-form body). Replaces v2.0's 8-field/7-section rigid format.
- 2026-03-28: PROTOCOL.md rewritten from 345-line pipeline to ~100-line agent autonomy protocol, faithful to AVO paper §3.
- 2026-03-28: Removed skill-spec.md. Format is trivial enough to state in PROTOCOL.md.
- 2026-03-28: Five meta-skills provide complete evolution primitives: create-skill, observe-user, extract-knowledge, interact-user, discover-environment.
- 2026-03-28: Description-based dispatch replaces trigger arrays and type enums.
- 2026-03-28: AVO is NOT a pipeline. Agent autonomously decides what to do within each variation step.
- 2026-03-28: judge.py expanded to 7 dimensions (+latency, +adoption).
- 2026-03-28: All prior discussion decisions (one AVO, everything is skill, everything is state, session runtime first) preserved.
