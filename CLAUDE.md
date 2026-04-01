# AutoSearch — Project Rules

> Behavioral rules for AI working in this codebase. Extends global CLAUDE.md.

## What this is

A self-improving search system. The human provides intent. The AI does everything else: understand the goal, generate strategies, run them across all platforms, score results, reflect, iterate, and harvest.

## Session Checklist

1. If working on v2.2 AVO/skills → read § v2.2 rules below
2. If working on search quality → read `docs/methodology/principles.md`
3. If touching genome → read § Genome rules below

## Workflow

- Branch: `feature/{desc}`, `fix/{desc}` — don't develop on main
- Commit: `{type}: {description}` (feat/fix/refactor/test/docs/chore)
- One commit = one logical change. Commit sequence: source code first, tests second, docs/config third. Don't batch. Because: reviewers need to verify tests cover exactly the code that changed.
- Feature commits without corresponding test commits will not pass review. Because: untested features are untested assumptions.
- Don't stage the entire repo (`git add .` / `git add -A`). Stage specific files only. Because: prevents accidental inclusion of debug files, env changes, or unrelated edits.
- Don't stage `.env*`, credentials, `node_modules/`, `__pycache__/`, or `.git/` internals. Because: these files contain secrets or generated content that must not enter version control.
- Don't modify linter or formatter config to suppress errors. Fix the code, not the config. Because: suppressing errors hides real problems and compounds technical debt.
- Run `ruff check && ruff format --check` before commit. Because: pushing lint failures wastes CI time and blocks other PRs.
- Tests: `pytest -x -q` must pass before push.
- PR stays under 5 commits. Larger → split into smaller PRs first. Because: oversized PRs don't get meaningful review.
- PR requires review before merge — don't self-merge. Because: self-review misses what a second pair of eyes catches.

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

## Genome rules

12. Don't manually edit files in `genome/evolved/`. Those are AVO output. Because: manual edits break the lineage chain in evolution.jsonl — AVO can't trace what changed or why.

13. Don't put new strategy decisions in Python code. Instead, add them to `genome/defaults/*.json`. Because: Python changes require code review; genome JSON changes are instantly evolvable by AVO.

14. Don't delete `genome/evolved/` files without checking evolution.jsonl. Because: JSONL records reference genome file paths — deleting breaks load_best_genome().

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
5. Check if new `patterns.jsonl` entries should sync to `docs/methodology/platforms/*.md` — new validated patterns get added, failed patterns get added to Known Failures.
6. If a new search technique was discovered, write a `docs/methodology/methods/` file per its CLAUDE.md write protocol.
7. Write experience note to `experience/{YYYY-MM-DD}-{topic}.md`.
8. Update `AIMD/experience/INDEX.jsonl` (path relative to Dev/ root).
9. If anything changed beyond search runs (code, rules, architecture): prepend entry to `CHANGELOG.md`.

## v2.2 rules (unified architecture: V1 capabilities + V2 evolvability)

12. Don't modify `judge.py` or `PROTOCOL.md` without explicit user authorization. These are the fixed contracts. judge.py is the scoring function f (AVO paper §3.1). PROTOCOL.md is the operating protocol. Because: if AVO can change its own evaluation or rules, behavior becomes unpredictable. Exception: judge.py was authorized to add `knowledge_growth` dimension on 2026-03-31 to enable multi-session cumulative evaluation. AVO still MUST NOT modify judge.py on its own.

13. Don't modify meta-skills: `create-skill.md`, `observe-user.md`, `extract-knowledge.md`, `interact-user.md`, `discover-environment.md`. These define HOW to evolve, not WHAT to evolve. AVO can modify all OTHER skills. Because: meta-skills are the "DNA replication machinery" — evolution changes genes, not the replication mechanism.

14. Don't delete or rewrite lines in append-only state files: `worklog.jsonl`, `patterns.jsonl`, `evolution-v1.jsonl`, `outcomes.jsonl`. Because: the AVO loop learns from history — deleting entries resets accumulated intelligence.

15. Skill changes during AVO go through `git commit`. Failed changes get `git revert`. Because: git history IS the lineage P_t that AVO uses to learn from failures.

16. Skill format standard (compatible with Claude Code Agent Skills spec + superpowers). AVO MUST follow these rules when creating or modifying skills:

**File**: `autosearch/v2/skills/{name}.md` — one file per skill, flat directory.

**Name rules** (enforced, not optional):
- Lowercase a-z, 0-9, hyphens only. Regex: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Max 64 characters
- No consecutive hyphens (`--`), no leading/trailing hyphens
- Name must match the filename (without `.md`)
- Bad: `My_Skill.md`, `UPPERCASE.md`, `search tool.md`. Good: `normalize-results.md`, `llm-evaluate.md`

**Frontmatter** (YAML between `---` markers, required):
```yaml
---
name: skill-name
description: "When to use this skill. Front-load the trigger condition. Max 250 chars for the key sentence."
---
```
- `name`: required, must match filename
- `description`: required, max 1024 chars. First sentence must state WHEN to use the skill, not WHAT it does internally. Because: description IS the dispatch mechanism — Claude reads it to decide whether to load the skill.

**Body** (free-form markdown):
- Strategy guide for a capable agent, not bash template for a dumb executor
- Max 500 lines recommended. If longer, the skill is trying to do too much — split it.
- Must have a `# Quality Bar` section at the end defining what "working correctly" looks like
- No required sections beyond that — structure serves the content, not a template

**What skills are NOT**:
- Not executable scripts (Claude reads them, not a parser)
- Not config files (use state/config.json for parameters)
- Not documentation (use docs/ for that)

Because: without format constraints, AVO will drift — creating skills with bad names, empty descriptions, 2000-line monsters, or files that are half code half prose. The constraints keep skills small, discoverable, and evolvable.

17. Use Python 3.11+ to run `judge.py` and tests. System python3 may be 3.9 which lacks union type syntax.

18. Platform skills can use free OR paid APIs. AVO discovers what's available via `discover-environment.md` and selects accordingly. Because: V1 had 14 connectors (8 free, 6 paid) — restricting to free-only was V2.0's mistake.

19. Every validation run MUST include a native Claude baseline comparison. Run the same query with native Claude (no AutoSearch skills/protocol), then compare in a table: result count by type, conceptual framework depth, content coverage gaps. Because: AutoSearch's value proposition is "better than native Claude at research" — if it's not, the system hasn't earned its complexity.

20. AVO self-evolution MUST be validated separately from search quality. Search quality tests (like F006) prove the pipeline works. Evolution tests prove the system improves itself. An evolution test requires: (a) baseline score, (b) agent-initiated skill modification, (c) re-score showing improvement, (d) git commit on improvement, (e) git revert on regression, (f) pattern written to state. Without this test passing, AutoSearch is a search agent, not a self-evolving search agent.

---

For V1 code reference, see `engine.py`, `goal_judge.py`, `goal_loop.py`, `outcomes.py`.
For v2.2 architecture, see `autosearch/v2/PROTOCOL.md` (the protocol) and `autosearch/v2/skills/` (flat skill directory).
