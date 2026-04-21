# Wave 3 Completion Summary

> Date: 2026-04-22
> Status: wave 3 **auto-mode portion complete**. PR E + W3.2 externals remain boss-gated.
> Prior docs:
>   - `docs/proposals/2026-04-21-v2-tool-supplier-architecture.md` (the v2 plan)
>   - `docs/proposals/2026-04-22-wave-2-status-and-wave-3-plan.md` (wave 3 outline)
>   - `docs/proposals/2026-04-22-w3-3-pipeline-removal-plan.md` (W3.3 A→E plan)
>   - `docs/migration/legacy-research-to-tool-supplier.md` (migration guide)
>   - `docs/bench/gate-12-augment-vs-bare.md` (new Gate 12 framing)

## TL;DR

Across one mega-session, autosearch migrated from a legacy end-to-end pipeline to a v2 **tool-supplier** architecture. The runtime AI (Claude Code / Cursor / Zed) now drives research directly by invoking three discoverable MCP tools. The legacy pipeline is deleted in source (4 modules gone, 2 stubbed to `NotImplementedError`) and the 9 m3/m7 prompts that powered it are removed. 25 PRs landed. 437 unit tests green.

## What Shipped

### v2 Tool-Supplier Trio (operational today)

- **`list_skills(group?, domain?, include_deprecated?)`** → discover 43 autosearch skills (31 channel + 7 tool + 4 meta + 1 router) with frontmatter metadata (`layer / domains / scenarios / model_tier / auth_required / cost / deprecated`).
- **`run_clarify(query, mode_hint?)`** → structured clarify envelope: `{need_clarification, question, verification, rubrics, mode, query_type, channel_priority, channel_skip}`.
- **`run_channel(channel_name, query, rationale?, k?)`** → raw Evidence (slim-dict) from a single channel; no synthesis, no compaction.

### New Skills (v2 additions)

- **7 tool skills**: `fetch-jina`, `fetch-crawl4ai`, `fetch-playwright` (docs-only to @playwright/mcp), `mcporter` (free MCP router), `video-to-text-groq`, `video-to-text-openai`, `video-to-text-local`.
- **5 meta skills (advisory)**: `autosearch:router` + 14 group index files, `autosearch:model-routing`, `autosearch:tikhub-fallback`, `autosearch:experience-capture`, `autosearch:experience-compact`.
- **8 workflow skill candidates**: `delegate-subtask`, `trace-harvest`, `reflective-search-loop`, `perspective-questioning`, `citation-index`, `graph-search-plan`, `recent-signal-fusion`, `context-retention-policy`.
- **31 channel SKILL.md files**: backfilled v2 frontmatter (`layer: leaf / domains / scenarios / model_tier: Fast / experience_digest`).

### Legacy Pipeline Removal (W3.3)

Per the 5-PR plan in `docs/proposals/2026-04-22-w3-3-pipeline-removal-plan.md`:

- **PR A** (#233): `research()` MCP tool defaults to deprecation response; `AUTOSEARCH_LEGACY_RESEARCH=1` preserves legacy for emergency backward-compat.
- **PR B** (#234): 22 orphan pipeline-only test files deleted.
- **PR C** (#235): 9 m3/m7 prompt markdowns deleted; module-level `load_prompt` calls in 3 callers replaced with empty-string sentinels.
- **PR D** (#236): 4 pipeline-internal modules deleted (`iteration.py`, `context_compaction.py`, `delegation.py`, `synthesis/section.py`); `Pipeline.run()` + `ReportSynthesizer.synthesize()` raise `NotImplementedError`.
- **PR E** (pending): delete `autosearch/core/pipeline.py` + `autosearch/synthesis/report.py` entirely and remove `Pipeline` imports from `mcp/server.py` / `cli/main.py` / `server/main.py`. **Boss sign-off required** per plan — ~20 files to update, risk not justified for auto-mode.

### Bench Infrastructure

- `scripts/bench/judge.py` — pairwise judge CLI (Anthropic Claude, position-randomized, graceful degrade on API error / malformed JSON).
- `docs/bench/gate-12-augment-vs-bare.md` — new Gate 12 framing spec: `claude -p + autosearch skills` (A) vs `claude -p bare` (B). Implementation pending E2B plugin loading verification.

### Migration

- `docs/migration/legacy-research-to-tool-supplier.md` — complete migration guide with minimum / quick-research / deep-research patterns + cost comparison + FAQ.
- Runtime `DeprecationWarning` on `research()` MCP tool invocation (visible to integrators via MCP telemetry).

## 25-PR Timeline

```
94e104d  refactor(legacy): W3.3 PR D — gut pipeline internals              (#236)
f28a302  chore(prompts):   W3.3 PR C — delete 9 m3/m7 prompt markdowns     (#235)
be325f8  chore(tests):     W3.3 PR B — delete 22 orphan pipeline tests     (#234)
02c1f99  feat(mcp):        W3.3 PR A — freeze research() to deprecation    (#233)
30c1967  docs(proposals):  W3.3 pipeline-removal multi-PR plan (A→E)       (#232)
2bf48ef  feat(mcp):        DeprecationWarning on research() + migration    (#231)
fcb4c97  docs(skills):     8 new workflow skill candidates (W3.6)          (#230)
d9cec9a  feat(mcp):        run_clarify tool (W3.1 trio complete)           (#229)
be2b74b  feat(mcp):        run_channel tool (W3.1)                         (#228)
c6fe551  feat(mcp):        list_skills tool (W3.1)                         (#227)
9d9675c  feat(bench):      pairwise judge CLI (W3.2 prereq)                (#226)
dfb8f36  docs(skill):      experience-capture + experience-compact (W3.5)  (#225)
c7f7408  docs(wave2):      deprecation + Gate 12 bench spec + W3 plan      (#224)
c370000  docs(skill):      autosearch:tikhub-fallback meta skill           (#223)
78c8ffa  docs(skill):      backfill v2 frontmatter to 31 channels          (#222)
026dbaf  docs(skill):      autosearch:model-routing meta skill             (#221)
fb2af18  docs(router):     autosearch:router + 14 group index              (#220)
cadd838  docs(skill):      mcporter routing skill                          (#219)
4d44492  docs(skill):      fetch-playwright routing skill                  (#218)
d000c59  feat(fetch):      fetch-crawl4ai skill                            (#217)
5ffc502  feat(transcribe): video-to-text-local                             (#216)
b64343b  feat(transcribe): video-to-text-openai                            (#215)
12f6459  feat(transcribe): video-to-text-groq                              (#214)
268f15c  chore(deps):      add yt-dlp                                      (#213)
f180813  feat(v2):         tool supplier architecture + fetch-jina         (#212)
```

## Test Health

- 437 unit tests pass (excluding perf + e2b which need external resources).
- 22 orphan pipeline-only test files deleted in PR B.
- New v2 test coverage: `test_list_skills.py` (11), `test_run_channel.py` (7), `test_run_clarify.py` (6), `test_research_deprecation.py` (4), `test_pipeline_removed.py` (8), `test_judge.py` (11) = 47 new v2 tests.

## What's Deferred (External Decisions)

### W3.2 Select-Channels Rewrite

`autosearch:select-channels` skill source lives in the plugin marketplace, not in this repo. To rewrite it group-first, boss needs to either locate the upstream source or accept a re-creation in `autosearch/skills/meta/` as the new canonical version.

### W3.2 Augment-vs-Bare Bench Runner

`scripts/bench/bench_augment_vs_bare.py` requires verifying that `claude -p --dangerously-skip-permissions` loads plugin skills in an E2B sandbox. A 10-second manual test (harness blocks nested `claude -p` from me) is the prerequisite. Boss runs:

```bash
claude -p --dangerously-skip-permissions \
  "List up to 5 skill names you have access to that start with 'autosearch:'. Output only a JSON array."
```

If it returns names → bench runner is viable. If empty / errors → bench needs `--allowedTools` injection or skill-context pre-load.

### W3.3 PR E — Delete Pipeline Class

Per the W3.3 plan, PR E is explicitly optional and boss-gated. Scope: delete `autosearch/core/pipeline.py` + `autosearch/synthesis/report.py`; remove `Pipeline` imports from `autosearch/mcp/server.py`, `autosearch/cli/main.py`, `autosearch/server/main.py`; update ~15 test files that still reference Pipeline for legacy-path coverage.

Under PR D, these files already raise `NotImplementedError` at runtime — behavior is identical whether the stub classes exist or not. PR E is a cosmetic cleanup, not a correctness requirement. Safe to defer.

### W3.4 First Augment-vs-Bare Bench Run

Depends on W3.2 runner + `ANTHROPIC_API_KEY` + target topic matrix. Estimated cost: $5-12 per full run (15 topics × K=5 × 2 variants). Target: win rate ≥ 50% for v1.0 tag per `docs/bench/gate-12-augment-vs-bare.md`.

## Operational Guidance for Runtime AI

**How to drive autosearch today (no `research()` needed)**:

```python
# 1. Discover
skills = list_skills(group="channels", domain="chinese-ugc")

# 2. Clarify (if query is ambiguous)
clarify = run_clarify(query="XGP 香港服和国服区别", mode_hint="fast")
if clarify.need_clarification:
    # Ask user clarify.question, enrich query
    ...

# 3. Execute (parallel if runtime supports it)
evidence = []
for channel in clarify.channel_priority[:5]:
    resp = run_channel(channel_name=channel, query=query, k=10)
    if resp.ok:
        evidence.extend(resp.evidence)

# 4. Synthesize — runtime AI's own capability
# autosearch no longer writes the report; Claude does it directly
# from the evidence list + rubrics
```

See `docs/migration/legacy-research-to-tool-supplier.md` for quick / deep-research patterns and the cost comparison.

## Lessons Captured

`~/.claude/standards/lessons.md`:

1. Codex prompts must enumerate project commit gates (e.g. `scripts/committer`).
2. Codex sandbox cannot write `.git/` → default Codex writes files / Claude Code commits.
3. Large destructive refactors (>10 test files, multiple core modules) need explicit plan.md + multi-PR sequence; auto-mode loop is not the right place.

## Summary

Waves 1-3 of the v2 tool-supplier architecture have landed to the extent auto-mode can safely deliver. The runtime AI has a complete, discoverable, non-destructive path to drive research. The legacy pipeline is structurally deleted — only thin stubs remain for import-compat, and even those raise `NotImplementedError` if anyone tries to run them.

Final remaining work (W3.3 PR E cleanup, W3.2 externals, W3.4 bench run) is explicitly external-or-boss-gated and will not be auto-attempted. Loop stops here for real.
