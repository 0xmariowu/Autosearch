---
name: score
type: strategy
version: "1.0"
requires: []
triggers: [score, quality, rank, evaluate, assess]
cost: free
platforms: []
dimensions: []
---
## Purpose
Interpret judge scores into planning and diagnosis decisions when the runner needs to understand whether search quality is strong enough to stop, retry, or rebalance.

## When to Use
- Use after `judge.py` has produced scores or whenever the agent needs a rubric for planning the next search iteration.
- Prefer this skill when deciding whether low quality comes from recall, source imbalance, stale evidence, or wasted query budget.
- This skill guides interpretation only; it does not replace `judge.py` or fetch results itself.
- Do not use it as a result-producing search skill because its output is structured analysis text rather than JSONL evidence.

## Execute
1. Evaluate each `judge.py` dimension against these thresholds:
   `quantity`: good when results are at or above target; bad when results are below 50% of target.
   `diversity`: good when Simpson index is greater than 0.7 and at least 3 platforms are represented; bad when one source dominates the set.
   `relevance`: good when more than 60% of results contain task keywords in the title or snippet; bad when fewer than 30% do.
   `freshness`: good when more than 50% of results are from the last 6 months; bad when fewer than 20% are.
   `efficiency`: good when the search yields more than 3 results per query; bad when it yields fewer than 1 result per query.
2. Translate weak dimensions into likely causes and fixes:
   low `quantity` usually means the search is too narrow or platform coverage is too small, so add platforms, increase `LIMIT`, or broaden queries.
   low `diversity` usually means source concentration, so increase the weight of underrepresented platforms or introduce a platform-specific query set.
   low `relevance` usually means the query is too broad or the platform is noisy, so narrow the query, add exact-match terms, or remove noisy platforms.
   low `freshness` usually means the query or source does not bias toward recency, so add `SINCE` and prefer platforms that support recency sorting.
   low `efficiency` usually means the plan over-fragmented the query budget, so reduce query count and merge overlapping queries.
3. Make the planning decision:
   stop when all dimensions are good or when tradeoffs are intentional and documented.
   iterate once more when one or two dimensions are weak and the fixes are cheap.
   redesign the search plan when three or more dimensions are weak because the current query-platform mix is structurally wrong.

## Parse
Emit structured analysis text for planning decisions instead of JSONL. The expected artifact is a plain-text or markdown diagnosis with this exact logical structure:
`Overall verdict: <stop|iterate|redesign>`
`Dimension review: <one line each for quantity, diversity, relevance, freshness, efficiency>`
`Likely causes: <cause list keyed by weak dimensions>`
`Recommended fixes: <ordered next actions>`
The text should preserve the dimension names exactly so downstream planners can map the advice back to `judge.py`.

## Score Hints
- `quantity`: treat missing results as a coverage problem first, not as a ranking problem.
- `diversity`: a healthy score should reflect multiple independent platforms rather than many URLs from one domain.
- `relevance`: title and snippet keyword overlap is the fastest useful proxy, but exact task fit still matters more than raw overlap.
- `freshness`: recency matters most for fast-moving software, APIs, benchmarks, and product comparisons.
- `efficiency`: low yield per query is usually a planning flaw and should push the agent toward fewer, stronger queries.

## Known Limitations
- The thresholds are heuristics and can be too strict for niche domains, archival research, or extremely new topics.
- `freshness` depends on having reliable timestamps; missing publish dates can make the diagnosis pessimistic.
- Strong scores can still hide duplicate evidence if deduplication has not already run.
- If metrics are unavailable or malformed, state which dimensions are unknown and avoid pretending the diagnosis is complete.

## Evolution Notes
- Tune: thresholds for niche domains, archival work, and domains where freshness is intentionally weak.
- Tried: use explicit good and bad cutoffs so planning decisions stay consistent across runs.
- Next: add task-type-specific overrides once enough judge outputs exist to calibrate by workflow.
