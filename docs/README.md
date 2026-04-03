# docs/ — AutoSearch Architecture Docs

> This directory holds broad architecture and methodology docs for AutoSearch.
> AutoSearch code lives at the repository root.
> Search methodology knowledge lives at: `docs/methodology/`
> Stable operational contracts live in the root docs and standards files.

## Files

| File | Type | Status | Summary |
|------|------|--------|---------|
| `2026-03-22-system-architecture.md` | design | active | Complete architecture: engine + pipeline + outcome feedback loop, file inventory, scheduling, ops manual |
| `2026-03-26-interface-contract.md` | contract | active | Public `interface.py` surface, stable return shapes, deep-runtime packet contract, evidence enrichment fields |
| `2026-03-26-dedupe-repair-learnings.md` | methodology | active | What the dedupe debugging pass proved, which fixes were real, and why runtime replay is the likely next bottleneck |
| `2026-03-25-competitor-improvements.md` | research | superseded | V1: 17 improvements from 5 repos (see V2) |
| `2026-03-25-competitor-improvements-v2.md` | research | active | V2 FINAL: 25 improvements from 16 repos, with implementation details, code references, Python ports, execution roadmap |
| `exec-plans/` | plans | mixed | Execution plans, with active work separated from completed historical plans |

## Related

| Path | Type | Summary |
|------|------|---------|
| `docs/methodology/` | methodology | platform playbooks and search principles |
| `PROTOCOL.md` | protocol | operating contract for the plugin root |
