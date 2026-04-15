---
name: rerank-evidence
description: "Prioritize results, rank findings, or select the most relevant evidence after evaluation. Use when you need to filter top results from a scored set, order search hits by importance, or pick the best sources for a final answer."
---

# Purpose

After llm-evaluate.md marks results as relevant or not, rerank the relevant set so the strongest evidence rises to the top. This ensures synthesis focuses on primary sources and high-quality findings rather than treating all relevant results equally.

# When To Use

- User asks to "prioritize results", "rank findings", "filter top results", or "select most relevant"
- After llm-evaluate.md has set `metadata.llm_relevant` on all results
- Before assemble-context.md selects the final evidence bundle
- When a large relevant set needs to be narrowed to the top-K items for synthesis

# Ranking Criteria

Score each result on six weighted criteria. Each criterion is scored 0-10.

| # | Criterion | Weight | What to assess |
|---|-----------|--------|----------------|
| 1 | **Task Relevance** | 30% | Primary source vs. secondary; topic-specific vs. tangential; fills a gap vs. duplicates coverage |
| 2 | **Evidence Quality** | 25% | Peer-reviewed > preprint > blog; official docs > third-party tutorial; full content > snippet-only; verifiable claims > opinion |
| 3 | **Source Authority** | 20% | Known research lab/company > unknown author; high-star repo > low-star; top conference (NeurIPS, ICLR, ICML) > workshop > arXiv-only |
| 4 | **Freshness** | 10% | More recent is better in fast-moving fields. Foundational works (STaR, Reflexion, Voyager) keep high scores regardless of age |
| 5 | **Diversity Bonus** | 10% | Underrepresented platform or content type gets a boost. If the bundle is 80% GitHub repos, a paper or blog ranks higher than another repo |
| 6 | **Cross-Source Convergence** | 5% | Appears on multiple platforms (`also_on` non-empty). Confirmed across Reddit, HN, and Twitter signals a canonical finding |

**Composite score formula:**

```
score = (relevance * 0.30) + (quality * 0.25) + (authority * 0.20)
      + (freshness * 0.10) + (diversity * 0.10) + (convergence * 0.05)
```

# Workflow

1. **Load**: Read all results where `metadata.llm_relevant = true`
2. **Score**: For each result, assign 0-10 on each of the six criteria and compute the composite score
3. **Rank**: Sort by composite score descending. Assign `metadata.rank` (1 = most important)
4. **Validate**: Check the top 5 — confirm no duplicates, at least two distinct source types, and that the top result is a primary source. If validation fails, adjust scores and re-sort
5. **Output**: Write ranked results for assemble-context.md to consume

For large result sets (>50 relevant results), rank in batches of 20. Compare top results across batches to produce a final ranking.

# Example

**Input** (3 relevant JSONL results):

```jsonl
{"title": "Voyager: An Open-Ended Embodied Agent", "url": "https://arxiv.org/abs/2305.16291", "source": "arxiv", "metadata": {"llm_relevant": true, "also_on": ["github", "hackernews"]}}
{"title": "Summary of Voyager paper", "url": "https://blog.example.com/voyager-summary", "source": "blog", "metadata": {"llm_relevant": true, "also_on": []}}
{"title": "voyager-minecraft GitHub repo", "url": "https://github.com/MineDojo/Voyager", "source": "github", "metadata": {"llm_relevant": true, "stars": 5200, "also_on": ["arxiv"]}}
```

**Scoring:**

| Result | Relevance | Quality | Authority | Freshness | Diversity | Convergence | Composite |
|--------|-----------|---------|-----------|-----------|-----------|-------------|-----------|
| Voyager paper (arxiv) | 10 | 9 | 9 | 8 | 7 | 10 | **9.15** |
| Voyager repo (github) | 9 | 7 | 8 | 8 | 5 | 8 | **7.70** |
| Blog summary | 6 | 4 | 3 | 7 | 8 | 0 | **4.90** |

**Output** (ranked):

```jsonl
{"title": "Voyager: An Open-Ended Embodied Agent", "url": "https://arxiv.org/abs/2305.16291", "source": "arxiv", "metadata": {"llm_relevant": true, "also_on": ["github", "hackernews"], "rank": 1, "rerank_score": 9.15}}
{"title": "voyager-minecraft GitHub repo", "url": "https://github.com/MineDojo/Voyager", "source": "github", "metadata": {"llm_relevant": true, "stars": 5200, "also_on": ["arxiv"], "rank": 2, "rerank_score": 7.70}}
{"title": "Summary of Voyager paper", "url": "https://blog.example.com/voyager-summary", "source": "blog", "metadata": {"llm_relevant": true, "also_on": [], "rank": 3, "rerank_score": 4.90}}
```

# Quality Bar

A good ranking puts foundational works, canonical tools, and primary sources at the top. The top 5 should include at least two distinct source types and no duplicates. A bad ranking is dominated by secondary sources, duplicative content, or popularity-biased ordering.
