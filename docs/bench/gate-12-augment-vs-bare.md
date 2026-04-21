# Gate 12 New Bench Framing — Augment vs. Bare Runtime

> Status: **spec** (wave 2 item #16). Implementation deferred until prerequisite `scripts/bench/judge.py` is ported back to main.
> Author: v2 architecture pivot, 2026-04-22.
> Supersedes: the old autosearch-vs-native head-to-head bench (which was mathematically unwinnable under v2 architecture — autosearch is no longer a runtime's competitor).

## Problem with the Old Framing

Under the legacy pipeline, Gate 12 compared:

- **A**: `autosearch research "<topic>"` CLI end-to-end output (runs the full pipeline: clarify → decompose → channel search → m3 compaction → m7 synthesis)
- **B**: `claude -p "<topic>"` — bare `claude -p` with no autosearch assistance

Measured pairwise over 15 topics × K=5. Result: **post-W1-W6 v3 = 0 / 62 losses** against bare `claude -p`. The pipeline strictly under-performed the bare runtime, which is expected under the v2 diagnosis — wrapping runtime AI in a pipeline strips its best faculties (judgment, synthesis, WebSearch).

This bench *cannot improve* without architecture change, because:

- A's synthesis quality is capped by autosearch's m7 synthesizer.
- B's synthesis quality is runtime AI's best effort, unconstrained.
- With all else equal, pipeline wrapping only subtracts quality.

## New Framing (v2 Tool Supplier)

Reframe Gate 12 as an **augmentation measurement**, not an adversarial one:

- **A**: `claude -p --dangerously-skip-permissions "<topic>"` with autosearch **skill bundle installed** (so the runtime AI can optionally call autosearch tools — channel skills, fetch tools, video-to-text, TikHub fallback, etc.)
- **B**: `claude -p --dangerously-skip-permissions "<topic>"` with **no autosearch skills** — bare runtime

Both sides use the same runtime model. Only difference: A has autosearch's toolbox available, B does not.

Measured pairwise over the same 15 topics × K=5 using the existing `scripts/bench/judge.py` pairwise judge (to be ported back to main before running).

### Hypothesis

A should beat B on topics that involve:

- Chinese UGC (bilibili, weibo, xiaohongshu, zhihu, douyin, xiaoyuzhou podcasts) — runtime AI's WebSearch does not reach these surfaces natively.
- Video / audio content that needs transcription — runtime AI does not transcribe.
- Deep academic tasks — autosearch has 11 academic channels; runtime AI has only generic web search.

A should tie B on topics that are already well-served by the runtime AI's own WebSearch:

- English tech news, Stack Overflow Q&A, GitHub surface.

A should NOT lose to B — the worst case is runtime ignores autosearch and defaults to its own search.

### Success Criteria

- **A win rate ≥ 50%** over 15-topic × K=5 matrix: v2 architecture delivers real user value; v1.0 tag unblocked.
- **A win rate 30-50%**: mixed value — useful where runtime is weak, noise where runtime is strong. Still v1.0-worthy but positioning should emphasize "augment for specific surfaces" not "universally better".
- **A win rate < 30%**: autosearch skill discovery or routing has a problem — runtime AI isn't reaching for the tools. Diagnose router / SKILL.md trigger keywords.

## Prerequisites

1. **`claude -p --dangerously-skip-permissions` loads plugin skills in headless mode**: must be verified before running the bench. A 10-second manual check:

   ```bash
   claude -p --dangerously-skip-permissions \
     "List up to 5 skill names you have access to that start with 'autosearch:'. Output only a JSON array."
   ```

   - Returns `autosearch:*` names → bench is valid.
   - Returns empty / errors → need to inject skills via `--allowedTools autosearch:*` or equivalent. Bench script must adapt.

2. **`scripts/bench/judge.py` on main**: the pairwise judge the HANDOFF references is currently branch-local. Must be ported to main before a v4 bench run. The judge accepts two report directories and outputs `{winner: a|b|tie, reason}` per pair.

3. **Same 15-topic set used in the last v3 bench**: stored in `scripts/e2b/<matrix>` config; reuse so results are directly comparable to historical baselines.

4. **Bench orchestrator**: the existing `scripts/e2b/bench_variance.py` drives the old framing. New framing needs a wrapper that:

   - Spins up two E2B sandboxes per topic per K run.
   - In sandbox A, runs `claude -p --dangerously-skip-permissions "<topic>"` with autosearch plugin preinstalled (`claude plugin install autosearch@autosearch`).
   - In sandbox B, runs `claude -p --dangerously-skip-permissions "<topic>"` with no autosearch plugin installed.
   - Collects the A and B reports.
   - Feeds both into `judge.py pairwise` with A/B ordering randomized per pair.

## Bench Script (sketch, to be implemented in wave 3)

```bash
# Pseudo-code; real script lives at scripts/bench/bench_augment_vs_bare.py
python scripts/bench/bench_augment_vs_bare.py \
  --topics scripts/e2b/matrix-w1w4-bench.yaml \
  --runs-per-topic 5 \
  --output reports/2026-XX-XX-gate12-augment-vs-bare \
  --parallel 15

python scripts/bench/judge.py pairwise \
  --a-dir reports/2026-XX-XX-gate12-augment-vs-bare/a \
  --b-dir reports/2026-XX-XX-gate12-augment-vs-bare/b \
  --a-label augmented --b-label bare \
  --output-dir reports/2026-XX-XX-gate12-judge-augmented-vs-bare \
  --parallel 8
```

## Cost Estimate

Same order of magnitude as the old v3 bench: 15 parallel E2B sandboxes × 2 (A + B) × 5 K = 150 runs per matrix × ~$0.02-0.06 / run ≈ $3-10 per bench. Plus judge LLM cost: 62 × 2 × ~$0.01 ≈ $1.50. Total: **~$5-12 per full A-vs-B run**. Cheap enough to run every time a wave-3 milestone lands.

## Risk and Mitigation

- **Plugin install in E2B sandbox might fail / differ from local**: validate `claude plugin install autosearch@autosearch` works in a fresh E2B sandbox before running full matrix.
- **Runtime AI might decline to call autosearch skills**: if A's tool-call logs show low invocation rate, the problem is skill-discovery (SKILL.md description / trigger keywords), not the architecture. Fix and re-run.
- **Results drift across `claude -p` versions**: pin the Claude CLI version in bench orchestrator metadata so regressions are attributable.
- **Judge bias**: the pairwise judge should randomize A/B ordering per pair; also run a sanity check where A and B are swapped copies of the same report (expected: 50/50 tie rate). If the judge is strongly biased toward "A", framing is invalid.

## Relationship to Wave 3

This spec defines Gate 12's new success criterion. Wave 3 will:

1. Port `scripts/bench/judge.py` back to main.
2. Write `scripts/bench/bench_augment_vs_bare.py` per this spec.
3. Run the first full augment-vs-bare matrix once the tool-supplier entry points are available in a stable E2B-installable plugin.
4. Publish results in a release-gate report similar to `reports/2026-04-21-post-merge/RELEASE-READINESS.md`, gating v1.0 tag on the outcome.

## Not in Scope

- Comparing autosearch to other deep-research systems (open_deep_research, gpt-researcher, etc.) — separate exercise.
- Measuring individual skill quality — that is the per-skill experience/patterns.jsonl job (wave 3 experience-capture / experience-compact skills).
- Cost / latency comparisons — orthogonal to quality gate.
