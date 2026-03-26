# autosearch/docs/ — AutoSearch Architecture Docs

> This directory holds broad architecture and methodology docs for AutoSearch.
> AutoSearch code lives at: `~/Library/Mobile Documents/com~apple~CloudDocs/Dev/autosearch/`
> Search methodology knowledge lives at: `autosearch/docs/methodology/`
> Stable operational contracts live at: `autosearch/standards/`

## Files

| File | Type | Status | Summary |
|------|------|--------|---------|
| `2026-03-22-system-architecture.md` | design | active | Complete architecture: engine + pipeline + outcome feedback loop, file inventory, scheduling, ops manual |
| `2026-03-26-interface-contract.md` | contract | active | Public `interface.py` surface, stable return shapes, deep-runtime packet contract, evidence enrichment fields |
| `2026-03-26-dedupe-repair-handoff.md` | handoff | active | Current dedupe regression state, verified fixes in `goal_editor.py`, latest run artifacts, and next investigation targets |
| `2026-03-26-dedupe-repair-learnings.md` | methodology | active | What the dedupe debugging pass proved, which fixes were real, and why runtime replay is the likely next bottleneck |
| `2026-03-25-competitor-improvements.md` | research | superseded | V1: 17 improvements from 5 repos (see V2) |
| `2026-03-25-competitor-improvements-v2.md` | research | active | V2 FINAL: 25 improvements from 16 repos, with implementation details, code references, Python ports, execution roadmap |
| `plans/2026-03-25-autosearch-super-search-v3.md` | plan | active | V3: mode/registry/cross-verification/watch super-search plan |
| `plans/2026-03-25-autosearch-super-search-v4.md` | plan | active | V4: 1:1 competitor-port implementation spec with exact runtime objects, files, and acceptance criteria |
| `plans/2026-03-26-autosearch-deep-runtime-v5.md` | plan | active | V5: execution-grade deep-runtime plan mapped to source repo files and AutoSearch implementation tasks |
| `plans/2026-03-26-autosearch-bottleneck-fixes.md` | plan | active | High-level staged plan for accepted artifact consistency, contradiction cleanup, scoring fixes, and hard-goal tuning |
| `plans/2026-03-26-pair-extract-repair-plan.md` | plan | active | Query/control-loop repair plan for lifting `pair_extract` off the token-floor failure mode |
| `plans/2026-03-26-pair-extract-structural-evidence-plan.md` | plan | active | Structural-evidence plan that moved `pair_extract` from keyword scoring toward relation scoring |
| `plans/2026-03-26-dedupe-quality-repair-plan.md` | plan | active | Detailed plan for repairing dedupe regression across focus selection, context pollution, and query reuse |

## Related

| Path | Type | Summary |
|------|------|---------|
| `docs/methodology/` | methodology | platform playbooks and search principles |
| `../standards/` | standards | truth sources, handoff objects, scope boundaries, operational contracts |
