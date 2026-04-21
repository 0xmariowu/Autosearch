# Wave 2 Status + Wave 3 Plan

> Date: 2026-04-22
> Supersedes: nothing (this is the wave handoff document)
> Author: v2 architecture execution, continuing from `docs/proposals/2026-04-21-v2-tool-supplier-architecture.md`

## TL;DR

**Wave 1** closed 100% — 11 PRs merged (#212–#222 + #223 tikhub-fallback meta skill). Architecture proposal, 7 new tools, yt-dlp dep, router + 14 group index + model-routing + tikhub-fallback meta skills, 31 leaf frontmatter backfill.

**Wave 2** partially closed non-destructively (4/6 items done or started):

- ✅ #13 SKILL.md routing rewrite — done via router + 14 group PR.
- ✅ #14 TikHub routing — done via tikhub-fallback meta skill PR.
- ✅ #12 M1 Clarifier on-demand — effectively done via `AUTOSEARCH_BYPASS_CLARIFY` env (PR #200) + clarify already exposed as standalone skill.
- 🟡 #11 Kill m3 / m7 / search_runner — **marked deprecated**, left alive for backward-compat. Full removal is wave 3 (requires tool-supplier entry-point rewrite first).
- 🟡 #16 Gate 12 new bench framing — **spec landed** at `docs/bench/gate-12-augment-vs-bare.md`. Execution deferred (wave 3) because `scripts/bench/judge.py` is not yet on main.
- 🔴 #15 `select-channels` group-first — **not actionable from main**. This skill's source lives in the plugin marketplace distribution, not in `autosearch/skills/`. Deferred to wave 3 after we locate / port it.

**Wave 3** is where the architecture becomes real for end users: tool-supplier entry-point rewrite replaces the legacy pipeline.

## Wave 2 — What Was Actually Shipped

### Deprecation scaffolding (PR #224, this PR)

1. `deprecated: true` + `deprecation_notice` in 4 legacy prompts:
   - `m3_evidence_compaction.md`
   - `m7_section_write.md`
   - `m7_section_write_v2.md`
   - `m7_outline.md`
2. Deprecation header comment in 3 caller modules:
   - `autosearch/core/context_compaction.py` (M3 evidence compactor)
   - `autosearch/core/iteration.py` (M3 reflection / gap loop)
   - `autosearch/synthesis/section.py` (M7 section writer)

No behavior change: legacy pipeline keeps running. New code paths must not call these; wave 3 removes them after tool-supplier entry-points land.

### Gate 12 new bench framing spec (PR #224, this PR)

`docs/bench/gate-12-augment-vs-bare.md` documents the new framing:

- **A**: `claude -p` with autosearch plugin installed.
- **B**: `claude -p` bare.
- Hypothesis: A wins on Chinese UGC + video + academic; ties on English tech news + generic web; never loses.
- Success criterion: A win rate ≥ 50% unblocks v1.0 tag.

Implementation blocked on porting `scripts/bench/judge.py` back to main; scheduled for wave 3.

### TikHub fallback meta skill (PR #223, shipped)

`autosearch:tikhub-fallback` codifies the "free first, TikHub paid only when research-critical" rule. Covered platforms, cost anchors, Weibo flakiness, Zhihu rate-limit boundaries, and the explicit not-covered list.

## Wave 2 — Why #11, #15, #16 Didn't Fully Close

### #11 Pipeline removal — needs entry-point rewrite first

`autosearch/core/context_compaction.py`, `autosearch/core/iteration.py`, and `autosearch/synthesis/section.py` are called by the `research()` MCP tool and `autosearch research` CLI, which real users depend on. Deleting them without a replacement entry point (tool-supplier mode) silently breaks those users.

Wave 3 must:

1. Design a new `research()` MCP tool contract that returns a **skill catalog + clarify result + channel evidence**, not a finished report.
2. Design a new `autosearch query` CLI that prints channel evidence + calls the runtime AI for synthesis (if available).
3. Flip the entry-points to the new contract.
4. **Then** delete `context_compaction.py` / `iteration.py` / `synthesis/section.py` + all `m3_*` / `m7_*` prompts.

### #15 select-channels rewrite — source not on main

`autosearch:select-channels` appears in the runtime's plugin skill catalog (system prompt lists it), but its `SKILL.md` is not in `autosearch/` or `skills/` on the main branch. Likely lives in the marketplace-distributed plugin package, not the public repo. Wave 3 first action: grep the plugin cache (`~/.claude/plugins/cache/autosearch*/`) locate the source, decide whether to inline it into this repo or issue a patch upstream.

### #16 Gate 12 bench — pairwise judge missing

The HANDOFF references `scripts/bench/judge.py`, but the file is not on main (probably branch-local on a merged-but-stripped feature branch). Wave 3 first action: resurrect the judge from git reflog or rewrite as a minimal pairwise prompt → LLM call → `{winner, reason}` returning CLI.

## Wave 3 Plan (proposed)

Order matters — the pipeline-removal step depends on entry-point rewrites being in place.

### W3.1 — Entry-point rewrite (enables #11 and #16)

1. **New MCP `research()` contract**: return `{skill_catalog, clarify_questions_if_any, channel_evidence, suggested_synthesis_prompt}` instead of a finished report. Keep the old report-returning path behind a deprecated `--legacy-pipeline` flag for one release.
2. **New `autosearch query` CLI**: print channel evidence + structured context; runtime AI outside autosearch does the synthesis.
3. **`commands/autosearch.md` slash command**: update to show the runtime AI how to ingest the new tool output.

### W3.2 — Port / rewrite missing infra

1. **`scripts/bench/judge.py`**: pairwise judge CLI. Input: two report dirs. Output: `{pair_id, winner, reason}` per pair. Use Claude API (sonnet) with a minimal pairwise prompt.
2. **`scripts/bench/bench_augment_vs_bare.py`**: per `docs/bench/gate-12-augment-vs-bare.md` spec — spins up two E2B sandboxes per topic, one with autosearch plugin installed, one bare.
3. **Locate `autosearch:select-channels`**: grep plugin cache, decide inline vs upstream patch, rewrite to group-first routing.

### W3.3 — Pipeline removal (after W3.1 is live)

1. Delete `autosearch/core/context_compaction.py`, `autosearch/core/iteration.py`, `autosearch/synthesis/section.py`.
2. Delete `autosearch/skills/prompts/m3_*.md` (6 files), `m7_*.md` (3 files).
3. Delete any dead callers that referenced these (grep once more).
4. Run full test suite; purge tests that exclusively tested the removed paths.
5. Bump a major-ish version (or `0.0.1a1` → `0.0.2a1`) to signal the entry-point change.

### W3.4 — Run first Gate 12 augment-vs-bare bench

1. Headless-plugin-load prerequisite verification (10-sec manual by user or first bench dry-run).
2. Run full 15-topic × K=5 augment-vs-bare matrix (~$5-12).
3. Pairwise judge 225 pairs → augment win rate.
4. Publish results → go / no-go on v1.0 tag per `docs/bench/gate-12-augment-vs-bare.md` success criteria.

### W3.5 — Experience-layer kick-off

1. Implement `experience-capture` and `experience-compact` meta skills (per v2 proposal §3.5).
2. First adopters: `search-xiaohongshu` and `select-channels` (per Codex round-2 report §5.2).
3. Monitor experience.md bloat over 2 weeks; tune thresholds if > 120 lines.

### W3.6 (optional) — 8 new workflow skill candidates

Per v2 proposal §3.7 (from Codex round-2 §4): `delegate-subtask` / `reflective-search-loop` / `perspective-questioning` / `citation-index` / `graph-search-plan` / `recent-signal-fusion` / `context-retention-policy` / `trace-harvest`. Ship the ones that earn their keep in W3.5 experience captures.

## Prerequisites Before Wave 3 Starts

| # | Prereq | Responsible | Blocking |
|---|---|---|---|
| 1 | Boss confirms W3.1 scope (pipeline-entry rewrite) is an acceptable sprint | Boss | Yes |
| 2 | `claude -p --dangerously-skip-permissions` loads plugin skills verified (10-sec test) | Boss manual | W3.4 only |
| 3 | Locate `autosearch:select-channels` source (plugin cache or separate repo) | Claude Code | W3.2 only |
| 4 | Decide `scripts/bench/judge.py` — port from branch or rewrite fresh | Claude Code + Boss | W3.2 only |
| 5 | Confirm no user is actively depending on the legacy `autosearch research` pipeline staying unchanged | Boss | W3.3 only |

## Not in Scope for Wave 2 or Wave 3

- MediaCrawlerPro ingestion (rejected per boss route C decision)
- Firecrawl hosted integration (paid, deferred)
- SearXNG self-hosted search (wave 4)
- Public-facing v1.0 release notes and marketing (post W3.4 only)

## Summary

Wave 1 complete. Wave 2 closed the reachable items (4/6) non-destructively. The remaining 2 items depend on an entry-point rewrite (W3.1) and missing infrastructure (W3.2). No blocking damage to the repo — legacy pipeline still works, deprecation notices tell future readers what is going away and why.
