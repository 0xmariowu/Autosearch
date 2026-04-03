# E1: AVO Evolution Test on v2.4 Skills

## Query
"survey of LLM memory architectures"

## Scores

| Dimension | Gen1 (baseline) | Gen2 (modified skill) | Delta |
|-----------|-----------------|----------------------|-------|
| **total** | **0.709** | **0.734** | **+0.025** |
| quantity | 1.000 | 1.000 | 0.000 |
| diversity | 0.511 | 0.683 | +0.172 |
| relevance | 1.000 | 1.000 | 0.000 |
| freshness | 0.270 | 0.333 | +0.063 |
| efficiency | 1.000 | 0.929 | -0.071 |
| latency | 0.000 | 0.000 | 0.000 |
| adoption | 0.700 | 0.700 | 0.000 |

## What Was Modified

**Skill**: `systematic-recall.md`

**Change**: Added a 9th dimension "Recent Developments (Last 6 Months)" to the systematic recall framework.

The original skill had 8 dimensions covering foundational methods, key people, landmark projects, top-venue papers, design patterns, known risks, commercial players, and controversies. None explicitly directed the agent to prioritize recency.

The new dimension:
- Explicitly asks the agent to recall the newest work from training data
- Requires precise date tagging (month + year minimum)
- Flags the entire dimension as GAP if nothing recent can be recalled, signaling search should prioritize freshness
- Added quality bar guidance: dimension 9 should have 3-5 items for active topics

**Why this target**: Gen1 judge output showed freshness at 0.270 as the weakest actionable dimension (latency=0.000 is architectural, not skill-fixable). The root cause was that systematic-recall's 8 dimensions produced a knowledge map skewed toward foundational/older works, which are HIGH confidence but not fresh.

**Commit**: `13ea5e0`

## Why the Score Improved

1. **Diversity +0.172**: The 9th dimension pushed the agent to recall items from more varied sources. Gen1 had 2 source types (own-knowledge, web-search). Gen2 had 4 source types (arxiv, github, own-knowledge, web-ddgs). The recent items naturally came from arxiv and github rather than pure own-knowledge.

2. **Freshness +0.063**: More items had dates within the 183-day freshness window. The explicit "last 6 months" framing in dimension 9 caused the agent to surface 12 items from Oct 2025-Mar 2026 in Gen2 vs fewer in Gen1.

3. **Efficiency -0.071**: Minor tradeoff from using 14 queries (Gen2) vs 10 (Gen1). The additional queries were gap-filling searches driven by dimension 9 GAPs.

4. **Net result**: The diversity and freshness gains (+0.172 * 0.15 + 0.063 * 0.10 = +0.032) outweighed the efficiency loss (-0.071 * 0.10 = -0.007), producing a net +0.025 total improvement.

## Verdict: Can v2.4 Skills Be Evolved by AVO?

**YES**

Evidence:
1. AVO identified the weakest actionable dimension (freshness=0.270) from Gen1 judge output
2. AVO selected the correct skill to modify (systematic-recall.md, not knowledge-map.md)
3. AVO made a targeted structural change (adding dimension 9 with recency framing)
4. The change produced measurable improvement (+0.025 total, +0.172 diversity, +0.063 freshness)
5. The improvement was committed via git (`13ea5e0`)
6. Patterns were recorded to `state/patterns-v2.jsonl` (p020, p021)

The v2.4 skills (systematic-recall.md, knowledge-map.md) are designed at the right abstraction level for AVO evolution. The dimension set in systematic-recall is a particularly effective evolution target because:
- Each dimension directly shapes what gets recalled and what becomes a search gap
- Changes cascade downstream: recall -> gap detection -> query generation -> evidence quality -> judge score
- The dimensions are orthogonal enough that adding one doesn't destabilize others

## Remaining Observations

- **Latency** (0.000 in both) is not skill-evolvable. It requires architectural changes (parallelization, timing budget adjustment).
- **Freshness** improved but is still below 0.5. Further evolution could modify the confidence tagging rules to more aggressively flag old items as GAP, or adjust knowledge-map.md decay rates.
- **Multi-skill co-evolution** was not tested. Modifying both systematic-recall.md and knowledge-map.md simultaneously might produce synergistic improvements.
- The improvement delta (+0.025) is modest. This is expected for a single-dimension addition. Cumulative evolution over multiple generations should compound.
