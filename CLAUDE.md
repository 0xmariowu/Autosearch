# AutoSearch — Project Rules

> Behavioral rules for AI working in this codebase. Extends global CLAUDE.md.

## What this is

A self-improving search system. The human provides intent. The AI does everything else: understand the goal, generate strategies, run them across all platforms, score results, reflect, iterate, and harvest.

## Search rules

1. Don't skip platforms. Instead, run every configured platform on every search. Because: each platform surfaces different content types — skipping one creates blind spots that compound across sessions. Exception: a platform is explicitly disabled in `standard.json`.

2. Don't rank by engagement alone. Instead, use LLM relevance scoring to separate signal from popularity. Because: a 10-like post with a specific rule violation is more valuable than a 1000-like cheatsheet — engagement measures attention, not goal-match.

3. Don't just score results and move on. Instead, after each round, reflect: what patterns appear in high-scoring queries? What angles haven't produced results? What failed? Because: reflection is what turns random search into directed search — without it, the system never learns within a session.

4. Don't skip Phase 3 (post-mortem). Instead, let the engine write winning/losing patterns to `patterns.jsonl` after every session. Because: the outer loop is what makes this system self-improving — skipping it means next session starts no smarter than this one.

5. Don't hardcode queries. Instead, generate every query from the methodology (entities, pain verbs, objects, symptoms extracted from the user's requirement). Because: hardcoded queries can't adapt to new goals, and they bypass the gene pool that enables cross-session learning. Exception: seed genes in `queries.json` that bootstrap the first round.

6. Don't start searching before defining the target spec. Instead, answer three questions first: (a) what are we looking for? (b) what does a useful finding look like, concretely? (c) what output will findings become? Because: without a target spec, scoring is arbitrary and harvest produces unfocused results.

7. Don't keep the same query mix ratio forever. Instead, track win rates by source (LLM / pattern / gene) and let the ratio adjust across sessions. Because: the optimal ratio depends on the problem space — a mature topic with many patterns needs fewer genes; a novel topic needs more exploration.

## Data rules

8. Don't delete `patterns.jsonl`. Instead, treat it as append-only accumulated intelligence. Because: each entry represents a validated learning from a real search session — deleting it resets the system to zero.

9. Don't delete `evolution.jsonl`. Instead, treat it as the append-only experiment log. Because: it's the raw data that enables cross-session analysis and debugging.

10. Don't edit files in `Armory/scripts/scout/autosearch/`. Instead, edit the canonical copy here (`~/Projects/autosearch/`). Because: the Armory copy is a sync artifact from launchd rsync — edits there get overwritten silently.

11. Don't run the legacy `run-template.py` for actual searches. Instead, use `pipeline.py` or `cli.py`. Because: the legacy script predates the modular engine and lacks LLMEvaluator, PatternStore, and newer connectors.

## Cross-directory relationships

```
search-methodology (principles + methods + platform knowledge)
       | guides
autosearch (execution code)
       | finds repos
Armory (analyzes + indexes)
       | stores docs
AIMD
```

- **From search-methodology**: Read `autosearch/docs/methodology/principles.md` for evidence standards. Read `platforms/*.md` for per-platform patterns. These guide how queries are designed.
- **To search-methodology**: After each session, check if `patterns.jsonl` findings should sync to `autosearch/docs/methodology/platforms/*.md`.
- **Depends on Armory/scripts/scout/**: `pipeline.py` calls `score-and-stage.js`, `auto-intake.sh`, `send-email.sh` from `/Volumes/4TB/Armory/scripts/scout/`. It also reads `queries.json` (seed genes) and `state.json` (dedup state) from there. Don't remove these dependencies without updating pipeline.py. Because: pipeline.py fails silently without them.
- **Canonical copy**: `~/Projects/autosearch/` is the source of truth.
- **Findings to Armory**: Valuable repos/articles found during search go to `/Volumes/4TB/AIMD/recs/master.md` (not directly to Armory). Because: Armory intake has its own review protocol.
- **Findings to AIMD**: Session analysis docs go to AIMD under the relevant project.
- **From Armory**: Before searching, check `/Volumes/4TB/Armory/when-blocks.jsonl` for existing knowledge on the topic. Because: re-searching what Armory already knows wastes API calls and produces duplicates.

## After completing a search session

1. Verify Phase 3 (post-mortem) ran — `patterns.jsonl` should have new entries.
2. Verify `evolution.jsonl` has new session entries.
3. If findings are Armory-worthy, append to `/Volumes/4TB/AIMD/recs/master.md`.
4. If the session produced a design/analysis doc, store in AIMD.
5. Check if new `patterns.jsonl` entries should sync to `autosearch/docs/methodology/platforms/*.md` — new validated patterns get added, failed patterns get added to Known Failures.
6. If a new search technique was discovered, write an `autosearch/docs/methodology/methods/` file per its CLAUDE.md write protocol.
7. Write experience note to `experience/{YYYY-MM-DD}-{topic}.md`.
8. Update `AIMD/experience/INDEX.jsonl` (path relative to Dev/ root).
9. If anything changed beyond search runs (code, rules, architecture): prepend entry to `CHANGELOG.md`.

---

For methodology details, algorithm documentation, and system architecture, see `docs/` or inline comments in `engine.py`.
