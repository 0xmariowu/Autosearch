# AutoSearch — Project Rules

> Behavioral rules for AI working in this codebase. Extends global CLAUDE.md.

## What this is

A self-improving search system. The human provides intent. The AI does everything else: understand the goal, generate strategies, run them across all platforms, score results, reflect, iterate, and harvest.

## Session Checklist

1. If working on AVO/skills → read § AVO rules below
2. If working on search quality → read `PRINCIPLES.md`

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

3. Don't just score results and move on. Instead, after each round, write a reflection block to the session log: (a) top 3 patterns from high-scoring queries, (b) angles that returned zero results, (c) one hypothesis for next round. Because: reflection is what turns random search into directed search — without it, the system never learns within a session.

4. Don't skip Phase 3 (post-mortem). Instead, let the engine write winning/losing patterns to `patterns.jsonl` after every session. Because: the outer loop is what makes this system self-improving — skipping it means next session starts no smarter than this one.

5. Don't hardcode queries. Instead, generate every query from the methodology (entities, pain verbs, objects, symptoms extracted from the user's requirement). Because: hardcoded queries can't adapt to new goals, and they bypass the gene pool that enables cross-session learning. Exception: seed genes in `queries.json` that bootstrap the first round.

6. Don't start searching before defining the target spec. Instead, answer three questions first: (a) what are we looking for? (b) what does a useful finding look like, concretely? (c) what output will findings become? Because: without a target spec, scoring is arbitrary and harvest produces unfocused results.

7. Don't keep the same query mix ratio forever. Instead, track win rates by source (LLM / pattern / gene) and let the ratio adjust across sessions. Because: the optimal ratio depends on the problem space — a mature topic with many patterns needs fewer genes; a novel topic needs more exploration.

## Data rules

8. Don't delete `patterns.jsonl`. Instead, treat it as append-only accumulated intelligence. Because: each entry represents a validated learning from a real search session — deleting it resets the system to zero.

9. Don't delete `evolution.jsonl`. Instead, treat it as the append-only experiment log. Because: it's the raw data that enables cross-session analysis and debugging.

10. Architecture: `PROTOCOL.md` + `skills/` + `lib/search_runner.py`.

## Session Protocol — After completing a search session

1. Verify `patterns.jsonl` and `evolution.jsonl` have new entries (Phase 3 ran).
2. Save any durable findings or analysis in repo-local artifacts, not external personal directories.
3. Sync patterns to platform channel SKILL.md files: win_rate ≥ 0.6 across 3+ sessions → add; win_rate = 0 across 3+ sessions → Known Failures.
4. If this repo maintains an active `experience/` log, write `experience/{YYYY-MM-DD}-{topic}.md` and update its index.
5. CHANGELOG.md is release-only — update it during release (`bump-version.sh`), not on every PR. GitHub release notes auto-generate from PR titles using `.github/release-notes-instructions.md`.

## AVO rules (self-evolution)

14. Don't modify `judge.py` or `PROTOCOL.md` without explicit user authorization. These are the fixed contracts. judge.py is the scoring function. PROTOCOL.md is the operating protocol. Because: if AVO can change its own evaluation or rules, behavior becomes unpredictable. Exception: adding new scoring dimensions requires explicit user authorization per instance. AVO MUST NOT modify judge.py on its own.

15. Don't modify meta-skills: `create-skill`, `observe-user`, `extract-knowledge`, `interact-user`, `discover-environment`. These define HOW to evolve, not WHAT to evolve. AVO can modify all OTHER skills. Because: meta-skills are the "DNA replication machinery" — evolution changes genes, not the replication mechanism.

16. Don't delete or rewrite lines in append-only state files: `worklog.jsonl`, `patterns.jsonl`, `evolution-v1.jsonl`, `outcomes.jsonl`. Because: the AVO loop learns from history — deleting entries resets accumulated intelligence.

17. Skill changes during AVO go through `git commit`. Failed changes get `git revert`. Because: git history IS the lineage P_t that AVO uses to learn from failures.

18. Skill format: `skills/{name}/SKILL.md`, one directory per skill. Name: lowercase a-z, 0-9, hyphens, max 64 chars, matches the directory name. Frontmatter: `name` + `description` (first sentence = WHEN to use, not what it does). Body: strategy guide, max 500 lines, ends with `# Quality Bar`. Full spec: `docs/skill-format-standard.md`. Because: without format constraints, AVO drifts toward bad names and 2000-line monsters.

19. Use Python 3.10+ to run `lib/judge.py` and tests. System python3 may be 3.9 which lacks union type syntax (`X | None` requires 3.10+).

20. Platform skills can use free OR paid APIs. AVO discovers what's available via `discover-environment` and selects accordingly.

21. Every validation run MUST include a native Claude baseline comparison. Run the same query with native Claude (no AutoSearch skills/protocol), then compare in a table: result count by type, conceptual framework depth, content coverage gaps. Because: AutoSearch's value proposition is "better than native Claude at research" — if it's not, the system hasn't earned its complexity.

22. AVO self-evolution MUST be validated separately from search quality. Search quality tests (like F006) prove the pipeline works. Evolution tests prove the system improves itself. An evolution test requires: (a) baseline score, (b) agent-initiated skill modification, (c) re-score showing improvement, (d) git commit on improvement, (e) git revert on regression, (f) pattern written to state. Without this test passing, AutoSearch is a search agent, not a self-evolving search agent.

Architecture: `PROTOCOL.md` + `skills/` + `lib/search_runner.py`.

## Release Workflow

Version format: **CalVer `YYYY.MM.DD.N`** (e.g., `2026.04.04.1`). N is the daily sequence number (1, 2, 3...).

Version lives in 3 files (kept in sync by `scripts/bump-version.sh`):
- `.claude-plugin/plugin.json` — Claude Code reads this to detect updates
- `.claude-plugin/marketplace.json` — marketplace catalog
- `CHANGELOG.md` — user-facing release notes

### How to release

1. `scripts/bump-version.sh` — auto-bumps to today's date
2. `scripts/committer "chore: bump version to X.Y.Z" .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md`
3. `git tag vX.Y.Z`
4. `git push && git push --tags` — triggers `release.yml` → creates GitHub Release

### How users update

- Manual: `claude plugin update autosearch@autosearch`
- Auto: `/plugin` → Marketplaces tab → autosearch → Enable auto-update
- Re-install: `curl -fsSL https://raw.githubusercontent.com/0xmariowu/autosearch/main/scripts/install.sh | bash`

### Guardrails

- **Pre-push hook**: blocks push if source files changed but version not bumped
- **CI**: posts PR comment warning if version drift detected
- **release.yml**: validates tag matches plugin.json version

## Lessons Learned

- Pre-commit hook must verify git author email is noreply and name is 0xmariowu before every commit. Rules in CLAUDE.md alone are not enough — they get forgotten under task pressure. The hook is the enforcement. Because: 2026-04-04 incident — 56 commits with PII (real name + Tailscale email) in public git history, required full history rewrite.
- Detection config files (.gitleaks.toml) must use generic regex patterns, never literal PII values. `[a-z]+mac` not `vimalamac`. Because: the detection file itself became a PII leak.
- Don't version-bump in each parallel PR. Bump once after the merge batch on main. Because: 7 PRs each bumped to .8, creating empty CHANGELOG entries and merge noise.
- Pre-commit hook must grep staged files for internal project codenames (Armory/AIMD/atoms/kalami/alaya-os). Because: internal refs leaked into public docs despite CLAUDE.md rules.
- bump-version.sh should warn if the previous version section in CHANGELOG.md has no content. Because: empty version entries are user-visible bugs.
