---
name: decompose-task
description: "Use when a research task is too broad or multi-dimensional for a single query strategy to cover well. Breaks complex questions into independent sub-questions."
---

# Purpose

Some tasks are too broad for gene-query.md alone.
"Find self-evolving AI agent frameworks" has at least 5 sub-dimensions: open-source projects, academic papers, commercial products, design patterns, and risks.
A single query strategy covers 1-2 dimensions well and misses the rest.

Decomposition turns one broad task into 3-5 focused sub-tasks, each with its own search strategy.

# When To Decompose

Decompose when:

- the task has multiple distinct dimensions that require different query types
- the task spans multiple content types (repos AND papers AND products)
- a single search round consistently misses known dimensions
- the task would benefit from different platform choices per sub-question

Do NOT decompose when:

- the task is narrow and specific ("find the GitHub repo for project X")
- the task is factual and single-answer ("when was Reflexion published?")
- decomposition would produce overlapping sub-questions
- you are already in a focused sub-search from a prior decomposition

# Knowledge-First Decomposition (Claude-First Mode)

Before decomposing into search sub-questions, run systematic-recall.md first.
Use the knowledge map to decompose SMARTER:

1. Run systematic-recall.md → get knowledge map with confidence levels
2. Identify which dimensions have HIGH confidence (Claude already knows) → no search needed
3. Identify which dimensions have MEDIUM/LOW confidence → verify and enrich
4. Identify GAP dimensions → discover through search
5. Generate sub-questions ONLY for MEDIUM/LOW/GAP dimensions
6. Assign platforms per sub-question based on what you need to find

This means: if Claude already knows 60% of the answer with HIGH confidence, only 40% needs searching.
The knowledge map IS the decomposition input.

# How To Decompose (General)

1. Read the task statement
2. List the distinct dimensions of a complete answer (max 5)
3. For each dimension, write a focused sub-question
4. Check independence: would the same search results answer two sub-questions? If yes, merge them.
5. Assign platform preferences per sub-question (e.g., papers → arXiv + web, repos → GitHub, products → web)

# Example

Task: "Find self-evolving AI agent frameworks and research"

Sub-questions:
1. "What open-source self-evolving agent frameworks exist?" → GitHub + web
2. "What academic papers define the foundations of self-evolving agents?" → arXiv + own-knowledge
3. "What commercial products use self-evolving agent technology?" → web
4. "What design patterns are used in self-evolving agent architectures?" → own-knowledge + web + GitHub
5. "What are the known risks and limitations?" → papers + blogs

# Merge Strategy

After searching each sub-question:
- Normalize all results (normalize-results.md)
- Deduplicate across sub-questions (same URL found by different sub-questions counts once)
- Merge evidence into one bundle for scoring and synthesis
- Tag each result with which sub-question found it (useful for gap analysis)

# Limits

- Maximum 5 sub-questions per task
- Each sub-question should be answerable with 3-5 queries
- Total query budget = research-mode budget (speed/balanced/deep)
- Decomposition adds overhead — only use when the task genuinely has multiple dimensions

# Quality Bar

Good decomposition produces sub-questions where:
- each sub-question covers evidence the others would miss
- no two sub-questions produce >30% overlapping results
- the union of all sub-results covers the task comprehensively
