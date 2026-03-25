# AutoSearch

Self-improving search system. Finds repos, articles, and tools for Armory intake.

## Quick Lookup

| I need... | Go here |
|----------|---------|
| Current high-level architecture | `docs/2026-03-22-system-architecture.md` |
| Search methodology and platform playbooks | `docs/methodology/` |
| Stable contracts for demand, search, routing handoff, and experience | `standards/` |
| Runtime search code | `engine.py`, `daily.py`, `pipeline.py` |
| Feedback loop and outcome tracking | `outcomes.py`, `outcomes.jsonl` |

## How It Works

3-phase loop: Explore → Harvest → Post-mortem. Each phase uses LLM evaluation (Sonnet 4.6) to score relevance against a target spec. The post-mortem writes patterns to `patterns.jsonl` — accumulated intelligence that makes the next session smarter.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | Core: 3-phase search (explore → harvest → post-mortem), gene pool + LLM eval |
| `daily.py` | Daily mode: reads queries.json as seed genes, 3 rounds |
| `cli.py` | Manual mode: AI fills genes/target/platforms per task |
| `pipeline.py` | Orchestrator: engine → adapter → score-and-stage.js → intake → email |
| `outcomes.py` | Feedback loop: query→repo tracking + WHEN/USE outcome scoring |
| `project_experience.py` | Runtime experience layer: ledger → index → policy → health |
| `source_capability.py` | Static source capability layer: catalog → doctor → latest-capability |
| `control_plane.py` | Current operating program: objective + capability + experience |
| `goal_judge.py` | Goal-specific evaluator with heuristic / OpenRouter modes |
| `goal_loop.py` | Goal-driven search loop with keep/discard by score delta |
| `interface.py` | Stable Python interface for other projects to call goal loops, doctor, and search tasks |
| `standard.json` | Default config (early-stop thresholds, platform list) |
| `patterns.jsonl` | Accumulated search intelligence (winning/losing words, outcome boosts) |
| `evolution.jsonl` | Per-query experiment log across all sessions |
| `outcomes.jsonl` | Query→repo→WHEN/USE outcome tracking |
| `platforms.md` | Platform connector status and capabilities |
| `standards/` | Stable contracts for demand, search, candidate storage, routeable handoff, and experience |
| `tests/` | Minimal regression tests for runtime experience and outcome provenance |

## Commands

```bash
python cli.py "search query"           # manual search
python daily.py                         # daily automated run
python pipeline.py                      # full pipeline (search → score → intake → email)
python doctor.py                        # static source/provider capability report
python goal_loop.py                     # goal-driven loop for one concrete project problem
```

## Python Interface

Other projects can import a stable interface instead of wiring internal modules:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
health = client.doctor()
result = client.run_goal_case("atoms-auto-mining-perfect", max_rounds=1)
```

If another project wants the explicit `搜索员 + 打分员` split, use a session:

```python
from interface import AutoSearchInterface

client = AutoSearchInterface("/path/to/autosearch")
session = client.build_searcher_judge_session("atoms-auto-mining-perfect")
plans = session.searcher_propose()
round_result = session.run_searcher_round()
```

## Dependencies

Pipeline depends on scripts in `Armory/scripts/scout/`:
- `score-and-stage.js` — scoring + dedup + diversity + Chinese translation + daily report
- `auto-intake.sh` — clone high-score repos + generate deep-research + rebuild indexes
- `send-email.sh` — Resend API email delivery
- `queries.json` — 15 topic groups (seed genes)
- `state.json` — persistent state (seen URLs, trends, run history)

## Scheduling

- LaunchAgent: `com.vimala.armory-scout`
- Trigger: `~/.local/bin/armory-scout.sh` → rsync to local → `python pipeline.py`
- Output: `AIMD/recs/{YYYY-MM-DD}.md`

## Search Methodology

Evidence principles, search methods, and per-platform playbooks: `docs/methodology/`
- `principles.md` — evidence reliability framework
- `platforms/*.md` — GitHub, Reddit, HN, Exa, Twitter, HuggingFace patterns
- `methods/*.md` — specific search techniques (e.g., reverse fingerprint search)

Additional research MCP sources can be documented there even before they become runtime providers. Current example: `docs/methodology/platforms/alphaxiv.md`.

## Standards

AutoSearch standards define narrow contracts, not general architecture:

- `standards/demand-standard.md` — how global demand becomes search briefs
- `standards/search-standard.md` — what search owns and what it must preserve
- `standards/content-candidate-standard.md` — the truth layer between findings and admission
- `standards/routeable-map-standard.md` — the final search-side handoff to downstream routing
- `standards/experience-standard.md` — how runtime experience is stored and consumed

## Runtime Experience Files

The runtime experience layer lives under `experience/`:

- `experience/library/experience-ledger.jsonl` — append-only search events
- `experience/library/experience-index.json` — aggregated recent index
- `experience/library/experience-policy.json` — current runtime guidance
- `experience/latest-health.json` — machine-readable provider/query-family health

## Source Capability Files

The static capability layer lives under `sources/`:

- `sources/catalog.json` — source/provider registry
- `sources/latest-capability.json` — machine-readable availability and doctor output

## Control Plane Files

The current operating program lives under `control/`:

- `program.md` — human-readable operating brief
- `control/latest-program.json` — machine-readable merged control plane

## Goal Loop Files

Goal-driven self-improvement lives under `goal_cases/` and the goal loop modules:

- `goal_cases/*.json` — concrete project problems with target score + rubric
- `goal_cases/runs/*.json` — run artifacts for baseline vs goal-judged comparisons
- `goal_judge.py` — independent evaluator
- `goal_loop.py` — iterative search / judge / keep-discard runner
