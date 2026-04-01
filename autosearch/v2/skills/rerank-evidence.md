---
name: rerank-evidence
description: "Use after LLM evaluation to rank relevant results by importance and select the top-K for synthesis. Orders evidence by task relevance, not just binary relevant/not-relevant."
---

# Purpose

llm-evaluate.md produces a binary filter: relevant or not.
But among relevant results, some are far more important than others.
A foundational paper is more important than a blog post summarizing it.
A 10K-star framework is more important than a 50-star toy project.

Reranking orders the relevant results so synthesis focuses on the best evidence.

# When To Use

Use after llm-evaluate.md has set `metadata.llm_relevant` on all results.
Use before assemble-context.md selects the final evidence bundle.

# Ranking Criteria

Rank by these factors, in roughly this priority:

## 1. Task Relevance (highest weight)
How directly does this result address the core question?
- Primary source (original framework, paper, product) > Secondary source (blog summary, news article)
- Specific to the topic > Generally related
- Answers a gap in current evidence > Duplicates existing coverage

## 2. Evidence Quality
How trustworthy and substantive is this result?
- Peer-reviewed paper > preprint > blog post
- Official documentation > third-party tutorial
- Result with fetched full content > snippet-only result
- Result with verifiable claims > opinion piece

## 3. Source Authority
How credible is the source?
- Well-known research lab or company > unknown author
- High-star GitHub repo > low-star repo
- Conference paper (NeurIPS, ICLR, ICML) > workshop paper > arXiv-only
- Domain expert blog > generic tech blog

## 4. Freshness (when relevant)
More recent is better when the field is evolving quickly.
But foundational works (STaR, Reflexion, Voyager) should rank high regardless of age.

## 5. Diversity Bonus
A result from an underrepresented platform or content type gets a boost.
If the bundle is 80% GitHub repos, a blog post or paper should rank higher than another repo.

# How To Rank

You are Claude. You can read all the results and judge their relative importance.
No external embedding API is needed.

Process:
1. Read all results where `metadata.llm_relevant = true`
2. For each result, mentally score it on the 5 criteria above
3. Sort by overall importance
4. Output the ranked list for assemble-context.md to use

For large result sets (>50 relevant results), rank in batches of 20.
Compare top results across batches to produce a final ranking.

# Output

Add `metadata.rank` (integer, 1 = most important) to each relevant result.
Or simply reorder the evidence JSONL file by importance.

# Quality Bar

A good ranking puts foundational works, canonical tools, and primary sources at the top.
A bad ranking is dominated by secondary sources, duplicative content, or popularity-biased ordering.
