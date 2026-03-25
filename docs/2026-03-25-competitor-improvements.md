# AutoSearch Improvement Catalog — Competitor Analysis

> Date: 2026-03-25
> Status: active
> Sources: fireplexity, deep-research, node-deepresearch, open_deep_research, swirl-search
> Purpose: Concrete, 1:1 copyable improvements for autosearch, with implementation details and source code references.

## How to Read This Document

Each improvement has:
- **What**: one-sentence description
- **Why**: what autosearch is missing
- **Source**: exact repo, file, line range, GitHub permalink
- **Principle**: how the technique works at algorithm level
- **Port**: Python pseudocode for autosearch implementation
- **Target file**: which autosearch file(s) to modify

---

## Phase 1 — Search Quality (Small Changes, High Impact)

### 1. Embedding-Based Query Deduplication

**What**: Before executing a query, check if a semantically similar query was already run (this session or previous sessions). Skip if cosine similarity > threshold.

**Why**: autosearch has no query dedup. The gene pool generates many similar queries (e.g., "Claude agent framework" vs "Claude AI agent tool") that waste API calls and produce duplicate results.

**Source**: Jina node-deepresearch

- **Dedup function**: [`src/tools/jina-dedup.ts` L9-L77](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/jina-dedup.ts#L9-L77)
- **Threshold constant**: [`src/tools/jina-dedup.ts` L6](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/jina-dedup.ts#L6) — `SIMILARITY_THRESHOLD = 0.86`
- **Called during search action**: [`src/agent.ts` L806](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L806)
- **Called during reflect action**: [`src/agent.ts` L774](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L774)

**Principle**:

1. Embed all new candidate queries and all previously-executed queries using the same embedding model.
2. For each new query, compute cosine similarity against every existing query embedding.
3. Also compare new queries against each other (to catch duplicates within the same batch).
4. If similarity ≥ 0.86, mark as duplicate and skip.
5. Use `task: "retrieval.query"` embedding mode (optimized for short queries, not passages).

Core logic from Jina's implementation:

```typescript
// jina-dedup.ts L42-L66
for (let i = 0; i < newQueries.length; i++) {
    let isUnique = true;
    // Check against existing (already-run) queries
    for (let j = 0; j < existingQueries.length; j++) {
        const similarity = cosineSimilarity(newEmbeddings[i], existingEmbeddings[j]);
        if (similarity >= SIMILARITY_THRESHOLD) { isUnique = false; break; }
    }
    // Check against already-accepted new queries (intra-batch dedup)
    if (isUnique) {
        for (const usedIndex of usedIndices) {
            const similarity = cosineSimilarity(newEmbeddings[i], newEmbeddings[usedIndex]);
            if (similarity >= SIMILARITY_THRESHOLD) { isUnique = false; break; }
        }
    }
    if (isUnique) { uniqueQueries.push(newQueries[i]); usedIndices.add(i); }
}
```

**Port**:

```python
# New file: autosearch/query_dedup.py
import numpy as np
from typing import list

SIMILARITY_THRESHOLD = 0.86

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

async def dedup_queries(
    new_queries: list[str],
    existing_queries: list[str],
    embed_fn  # async (texts: list[str]) -> list[list[float]]
) -> list[str]:
    if not new_queries:
        return []

    all_texts = new_queries + existing_queries
    all_embeddings = await embed_fn(all_texts)
    new_embs = all_embeddings[:len(new_queries)]
    existing_embs = all_embeddings[len(new_queries):]

    unique = []
    used_indices = set()

    for i, emb in enumerate(new_embs):
        is_unique = True
        # Check against existing
        for ex_emb in existing_embs:
            if cosine_similarity(emb, ex_emb) >= SIMILARITY_THRESHOLD:
                is_unique = False
                break
        # Check against already-accepted new queries
        if is_unique:
            for j in used_indices:
                if cosine_similarity(emb, new_embs[j]) >= SIMILARITY_THRESHOLD:
                    is_unique = False
                    break
        if is_unique:
            unique.append(new_queries[i])
            used_indices.add(i)

    return unique
```

**Target files**: New `query_dedup.py` + integrate into `engine.py` SearchEngine._run_round() before platform dispatch.

**Embedding provider options**: Jina Embeddings API (free tier: 1M tokens/month), or local sentence-transformers. Jina uses `jina-embeddings-v3` with `dimensions: 1024`.

---

### 2. URL Dedup Before Scoring (Not After)

**What**: Before evaluating search results, check URLs against a session-wide set. Skip already-seen URLs immediately.

**Why**: autosearch deduplicates only in post-mortem (Phase 3). This means LLM evaluation tokens are wasted on URLs already seen in earlier rounds.

**Source**: Swirl

- **Field-based dedup processor**: [`swirl/processors/dedupe.py` L77-L97](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/dedupe.py#L77-L97)
- **Similarity-based dedup**: [`swirl/processors/dedupe.py` L101-L150](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/dedupe.py#L101-L150)
- **Config constants**: [`swirl/processors/dedupe.py` L16-L18](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/dedupe.py#L16-L18)

**Also**: LangChain open_deep_research deduplicates URLs before summarization:
- **Tavily search dedup**: [`src/open_deep_research/utils.py` L43-L136](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L43-L136)

**Principle**:

Swirl uses two layers:
1. **Exact URL match** (fast, O(1) per lookup): maintain a `dict[str, bool]` of seen URLs. Check before any processing.
2. **Semantic similarity** (slower, catches near-dupes): compare `title + body` using spaCy NLP similarity. Threshold: 0.95.

LangChain's approach is simpler — dedup by URL before parallel summarization:

```python
# open_deep_research/utils.py — concept
unique_results = {}
for result in all_results:
    url = result["url"]
    if url not in unique_results:
        unique_results[url] = result
# Only summarize unique results
```

**Port**:

```python
# In engine.py, add to SearchEngine class:
class SearchEngine:
    def __init__(self, ...):
        self.seen_urls: set[str] = set()

    def _dedup_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove results with URLs already seen this session."""
        unique = []
        for r in results:
            normalized = r.url.rstrip('/').lower()
            if normalized not in self.seen_urls:
                self.seen_urls.add(normalized)
                unique.append(r)
        return unique

    def _run_round(self, ...):
        # ... after collecting results from all platforms ...
        results = self._dedup_results(results)  # <-- add here, BEFORE LLM evaluation
        # ... then send to LLMEvaluator ...
```

**Target file**: `engine.py`, SearchEngine class — add `seen_urls` set and filter before `evaluate_round()`.

---

### 3. Per-Platform Query Transformation

**What**: Transform each query to match the platform's optimal syntax before sending. GitHub gets `stars:>100`, Reddit gets `sort:relevance`, HN gets quoted product names.

**Why**: autosearch sends the same raw query to all 11 platforms. The patterns.jsonl already knows that Reddit needs `sort:relevance` and HN needs quoted names, but this knowledge isn't applied programmatically.

**Source**: Swirl

- **AdaptiveQueryProcessor**: [`swirl/processors/adaptive.py` L15-L128](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/adaptive.py#L15-L128)
- **Connector's process_query step**: [`swirl/connectors/connector.py` L165-L197](https://github.com/swirlai/swirl-search/blob/main/swirl/connectors/connector.py#L165-L197)

**Principle**:

Swirl's approach:
1. Each SearchProvider has a `query_mappings` config string (e.g., `"DATE_SORT=sort=date,PAGE=start=RESULT_INDEX,NOT_CHAR=-"`).
2. The `AdaptiveQueryProcessor` parses these mappings and rewrites the query accordingly.
3. Tag-based routing: if query contains `tag:value` pairs (e.g., `code:python error`), only providers tagged with `code` receive the tagged content.
4. NOT operator translation: `NOT term` → `-term` (Google), `NOT term` (Elastic), etc.

For autosearch, a simpler config-driven approach is better (we don't need tag routing):

**Port**:

```python
# New file: autosearch/config/query_transforms.json
{
  "github_repos": {
    "prefix": "",
    "suffix": " stars:>50",
    "quote_entities": false,
    "sort_param": null
  },
  "github_issues": {
    "prefix": "",
    "suffix": "",
    "quote_entities": true,
    "sort_param": null
  },
  "reddit_exa": {
    "prefix": "",
    "suffix": "",
    "quote_entities": false,
    "sort_param": "sort:relevance"
  },
  "hn_exa": {
    "prefix": "",
    "suffix": "",
    "quote_entities": true,
    "sort_param": null
  },
  "hn_algolia": {
    "prefix": "",
    "suffix": "",
    "quote_entities": true,
    "sort_param": null
  }
}

# In engine.py:
import json

TRANSFORMS = json.load(open("config/query_transforms.json"))

def transform_query(query: str, platform: str, entities: list[str]) -> str:
    t = TRANSFORMS.get(platform, {})
    q = query

    # Quote known entities for platforms that benefit from exact match
    if t.get("quote_entities") and entities:
        for entity in entities:
            if entity in q and f'"{entity}"' not in q:
                q = q.replace(entity, f'"{entity}"')

    if t.get("prefix"):
        q = f"{t['prefix']} {q}"
    if t.get("suffix"):
        q = f"{q} {t['suffix']}"

    return q
```

**Target files**: New `config/query_transforms.json` + modify `engine.py` PlatformConnector dispatch methods.

---

### 4. Intelligent Content Extraction (Keyword-Scored Paragraphs)

**What**: When extracting content from a page, split into paragraphs, score each by keyword overlap with the query, and keep only the most relevant paragraphs plus intro/conclusion.

**Why**: autosearch's `fit_markdown` in `evidence/models.py` does a naive 1200-char substring. This loses important content that appears later in the page and includes irrelevant boilerplate from the intro.

**Source**: Fireplexity

- **`selectRelevantContent()` full function**: [`lib/content-selection.ts` L1-L46](https://github.com/firecrawl/fireplexity/blob/main/lib/content-selection.ts#L1-L46)
- **Called in search route**: [`app/api/fireplexity/search/route.ts` L210-L219](https://github.com/firecrawl/fireplexity/blob/main/app/api/fireplexity/search/route.ts#L210-L219)

**Principle**:

```
Input: full page content + original query + max_chars limit

1. Split content into paragraphs (by double newline or <br>)
2. Extract keywords from query:
   - Lowercase, split by whitespace
   - Remove short words (< 4 chars)
   - Remove stop words: what, when, where, which, how, why, does, with, from, about
3. Always keep: first 2 paragraphs (intro) + last paragraph (conclusion)
4. For remaining paragraphs:
   - Score = count of query keywords found in paragraph (case-insensitive)
   - Filter: keep only paragraphs with score > 0
   - Sort by score descending
   - Take top 3
   - Re-sort by original position (maintain reading order)
5. Concatenate: intro + top-scored + conclusion
6. Truncate to max_chars
```

Original TypeScript:

```typescript
// lib/content-selection.ts L5-L42
const paragraphs = content.split(/\n\n+/).filter(p => p.trim().length > 0)
if (paragraphs.length <= 5) return content.substring(0, maxLength)

const keywords = query.toLowerCase()
    .split(/\s+/)
    .filter(word => word.length > 3)
    .filter(word => !['what','when','where','which','how','why',
                      'does','with','from','about'].includes(word))

const intro = paragraphs.slice(0, 2)
const conclusion = paragraphs.slice(-1)

const relevantParagraphs = paragraphs.slice(2, -2)
    .map((paragraph, index) => ({
      text: paragraph,
      score: keywords.filter(keyword =>
        paragraph.toLowerCase().includes(keyword)
      ).length,
      index
    }))
    .filter(p => p.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .sort((a, b) => a.index - b.index)
    .map(p => p.text)

const selectedContent = [...intro, ...relevantParagraphs, ...conclusion].join('\n\n')
return selectedContent.substring(0, maxLength)
```

**Port**:

```python
# New function in evidence/models.py or a new evidence/content_selection.py

STOP_WORDS = {'what','when','where','which','how','why','does','with','from','about',
              'the','and','for','are','this','that','have','has','been','will','can'}

def select_relevant_content(content: str, query: str, max_chars: int = 2000) -> str:
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

    if len(paragraphs) <= 5:
        return content[:max_chars]

    keywords = [
        w for w in query.lower().split()
        if len(w) > 3 and w not in STOP_WORDS
    ]

    intro = paragraphs[:2]
    conclusion = paragraphs[-1:]

    middle = paragraphs[2:-1]
    scored = []
    for i, para in enumerate(middle):
        para_lower = para.lower()
        score = sum(1 for kw in keywords if kw in para_lower)
        if score > 0:
            scored.append((i, score, para))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:3]
    top.sort(key=lambda x: x[0])  # restore reading order

    selected = intro + [p for _, _, p in top] + conclusion
    result = '\n\n'.join(selected)
    return result[:max_chars]
```

**Target file**: `evidence/models.py` — replace `fit_markdown` logic with `select_relevant_content()`.

---

### 5. Information-Density Prompting for Evidence Extraction

**What**: When LLM evaluates search results, require extracted learnings to include concrete entities, numbers, and dates. Reject vague summaries.

**Why**: autosearch's LLMEvaluator (`engine.py:146-210`) asks only "is this relevant? yes/no + reason". The extracted evidence is often vague ("this repo has useful patterns") instead of specific ("Jina's node-deepresearch uses 0.86 cosine threshold for query dedup, implemented in jina-dedup.ts").

**Source**: dzhng/deep-research

- **`processSerpResult()` prompt**: [`src/deep-research.ts` L81-L118](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L81-L118)
- **Learning extraction schema**: [`src/deep-research.ts` L106-L113](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L106-L113)

**Principle**:

The key is in the prompt phrasing (from deep-research.ts L96-L105):

```
"Extract learnings from the content. Each learning should be unique, concise, and
information-dense. Include specific entities (people, companies, products), metrics,
numbers, and dates whenever present. Make them actionable for further research."
```

Combined with a structured output schema that forces an array of strings:

```typescript
// deep-research.ts L106-L113
schema: z.object({
  learnings: z.array(z.string()).describe(
    `List of learnings, max of ${numLearnings}`
  ),
  followUpQuestions: z.array(z.string()).describe(
    `List of follow-up questions to research the topic further, max of ${numFollowUpQuestions}`
  ),
})
```

This produces output like:
- "Jina uses SIMILARITY_THRESHOLD=0.86 for semantic query dedup (jina-dedup.ts)"
- "Fireplexity limits content to 2000 chars per source with keyword-scored paragraph selection"

Instead of:
- "This repo has useful query dedup functionality"
- "Content extraction is handled well"

**Port**:

```python
# In engine.py, modify LLMEvaluator.evaluate_round() prompt:

EVALUATION_PROMPT = """You are evaluating search results for the following target:
{target_spec}

For each result, determine:
1. Is it relevant? (yes/no)
2. Extract 1-3 concrete learnings. Each learning MUST include:
   - Specific entities (product names, company names, people)
   - Numbers, metrics, or thresholds when present
   - Dates or version numbers when present
   - The specific technique or pattern (not just "it has a good approach")

   BAD: "This repo has useful error handling"
   GOOD: "swirl-search uses spaCy cosine similarity > 0.95 threshold for semantic dedup across title+body fields (dedupe.py L101-150)"

3. Generate 1-2 follow-up queries that would deepen research on this topic.

Results:
{results_json}

Return JSON:
{{
  "results": [
    {{
      "index": 0,
      "relevant": true,
      "learnings": ["specific learning 1", "specific learning 2"],
      "follow_up_queries": ["query 1"]
    }}
  ]
}}"""
```

**Target file**: `engine.py` LLMEvaluator class — modify the evaluation prompt.

---

## Phase 2 — Research Depth (goal_bundle_loop Upgrade)

### 6. FIFO Gap Queue (Replace Dimension Cycling)

**What**: Replace goal_bundle_loop's dimension-based cycling with a FIFO queue of "gap questions". New gaps discovered during research are added to the queue. Original question is re-added after each cycle.

**Why**: Dimension cycling is rigid — it forces a fixed rotation through predefined dimensions even when some are already well-covered. A gap queue is adaptive: the system focuses on actual knowledge gaps.

**Source**: Jina node-deepresearch

- **Gap array init**: [`src/agent.ts` L476](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L476)
- **Round-robin selection**: [`src/agent.ts` L526](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L526)
- **Adding new gaps from reflect**: [`src/agent.ts` L778-L786](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L778-L786)
- **Removing solved gaps**: [`src/agent.ts` L771](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L771)

**Principle**:

```
Initialize: gaps = [original_question]

Each step:
  current_q = gaps[step % len(gaps)]     # round-robin through all gaps
  action = LLM.decide(current_q, knowledge)

  if action == "reflect":
    new_gaps = LLM.identify_gaps(current_q, knowledge)
    new_gaps = dedup(new_gaps, all_questions)  # embedding-based
    gaps.extend(new_gaps)

  if action == "answer" and eval.pass:
    gaps.remove(current_q)               # gap is filled

  if action == "answer" and not eval.pass:
    # keep gap in queue, will revisit
```

Compared to dimension cycling:
- Dimensions are predefined; gaps are discovered.
- Dimensions have fixed weights; gaps have implicit priority (earlier = more revisits via round-robin).
- Answered gaps are removed; dimensions cycle forever.

**Port**:

```python
# In goal_bundle_loop.py, replace dimension cycling:

class ResearchLoop:
    def __init__(self, original_question: str):
        self.gaps: list[str] = [original_question]
        self.all_questions: list[str] = [original_question]
        self.knowledge: list[dict] = []
        self.step = 0

    def current_question(self) -> str:
        return self.gaps[self.step % len(self.gaps)]

    def add_gaps(self, new_gaps: list[str]):
        # Dedup against all known questions (use embedding dedup from #1)
        for gap in new_gaps:
            if gap not in self.all_questions:  # or use embedding similarity
                self.gaps.append(gap)
                self.all_questions.append(gap)

    def resolve_gap(self, question: str):
        if question in self.gaps:
            self.gaps.remove(question)

    def is_done(self) -> bool:
        return len(self.gaps) == 0
```

**Target file**: `goal_bundle_loop.py` — replace the dimension/round cycling logic.

---

### 7. Recursive Deep Search with Breadth Halving

**What**: For each query, generate N sub-queries and execute in parallel. For each sub-query's results, recursively generate N/2 deeper sub-queries. Stop when depth reaches 0.

**Why**: autosearch's goal_bundle_loop runs fixed rounds with fixed breadth. It can't go deeper on promising threads while staying shallow on exhausted ones.

**Source**: dzhng/deep-research

- **`deepResearch()` function**: [`src/deep-research.ts` L176-L294](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L176-L294)
- **Breadth halving**: [`src/deep-research.ts` L230](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L230)
- **Research goal preservation**: [`src/deep-research.ts` L251-L254](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L251-L254)

**Principle**:

```
deepResearch(query, learnings=[], visited=set(), breadth=4, depth=2):

  # Generate sub-queries informed by accumulated learnings
  queries = LLM.generate_queries(query, learnings, num=breadth)

  # Execute all queries in parallel (with concurrency cap)
  all_results = parallel_execute(queries, concurrency=ConcurrencyLimit(2))

  for query_result in all_results:
    # Extract learnings from each result
    new_learnings = LLM.extract_learnings(query_result, num_followup=ceil(breadth/2))
    learnings.extend(new_learnings.learnings)
    visited.update(new_learnings.urls)

    # Recurse with halved breadth
    if depth > 0:
      next_query = f"""
        Previous goal: {query_result.research_goal}
        Follow-up directions: {new_learnings.follow_up_questions}
      """
      sub_results = deepResearch(
        next_query, learnings, visited,
        breadth=ceil(breadth/2),  # <-- halving prevents explosion
        depth=depth-1
      )
      learnings.extend(sub_results.learnings)
      visited.update(sub_results.visited)

  return {
    learnings: deduplicate(learnings),
    visited: visited
  }
```

Total queries at each level: breadth → breadth/2 → breadth/4 → ... converges to ~2×breadth total. With breadth=4, depth=3: approximately 4 + 2 + 1 = 7 queries per branch.

**Port**:

```python
# New function in goal_bundle_loop.py or a separate deep_search.py

import asyncio
import math

async def deep_search(
    query: str,
    learnings: list[str] = None,
    visited_urls: set[str] = None,
    breadth: int = 4,
    depth: int = 2,
    llm_eval = None,
    search_fn = None,
    concurrency: int = 3
) -> dict:
    learnings = learnings or []
    visited_urls = visited_urls or set()
    sem = asyncio.Semaphore(concurrency)

    # Step 1: Generate sub-queries
    queries = await llm_eval.generate_queries(query, learnings, num=breadth)

    # Step 2: Execute in parallel
    async def run_query(q):
        async with sem:
            return await search_fn(q.query)

    results = await asyncio.gather(*[run_query(q) for q in queries])

    # Step 3: Extract learnings + recurse
    all_learnings = list(learnings)
    all_urls = set(visited_urls)

    for q, result in zip(queries, results):
        new_breadth = math.ceil(breadth / 2)
        extracted = await llm_eval.extract_learnings(
            q.query, result, num_followup=new_breadth
        )
        all_learnings.extend(extracted.learnings)
        all_urls.update(r.url for r in result)

        if depth > 0 and extracted.follow_up_questions:
            next_query = (
                f"Previous goal: {q.research_goal}\n"
                f"Follow-ups: {', '.join(extracted.follow_up_questions)}"
            )
            sub = await deep_search(
                next_query, all_learnings, all_urls,
                breadth=new_breadth, depth=depth - 1,
                llm_eval=llm_eval, search_fn=search_fn,
                concurrency=concurrency
            )
            all_learnings.extend(sub["learnings"])
            all_urls.update(sub["visited_urls"])

    return {
        "learnings": list(set(all_learnings)),
        "visited_urls": all_urls
    }
```

**Target file**: New `deep_search.py` or integrate into `goal_bundle_loop.py`.

---

### 8. Token Budget with Beast Mode Fallback

**What**: Set a total token budget for a research session. Use 85% for normal iteration. Reserve 15% for a "beast mode" — force the LLM to produce the best possible answer with whatever knowledge has been accumulated.

**Why**: autosearch uses `max_rounds` (fixed at 15) as the only termination condition. This means: (a) simple topics waste rounds, (b) complex topics may hit the limit with no useful output.

**Source**: Jina node-deepresearch

- **Budget split**: [`src/agent.ts` L498-L499](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L498-L499)
- **Main loop condition**: [`src/agent.ts` L518-L519](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L518-L519)
- **Beast mode trigger**: [`src/agent.ts` L1036-L1076](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L1036-L1076)
- **Beast mode prompt**: [`src/agent.ts` L197-L131](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L197-L131)

**Principle**:

```
token_budget = 1_000_000  # configurable
regular_budget = token_budget * 0.85
beast_budget = token_budget * 0.15

while token_usage < regular_budget:
    action = LLM.decide_action(...)
    execute(action)
    token_usage += action.tokens

# If no final answer yet:
if not has_final_answer:
    # Beast mode: disable all actions except "answer"
    # Use aggressive prompt: "PRODUCE YOUR BEST ANSWER NOW"
    answer = LLM.force_answer(all_knowledge, budget=beast_budget)
```

The key insight: beast mode disables search/reflect/read actions. The LLM can ONLY produce an answer. The prompt is deliberately aggressive to overcome the model's tendency to hedge.

**Port**:

```python
# In goal_bundle_loop.py:

class BudgetManager:
    def __init__(self, total_budget: int = 500_000):
        self.total = total_budget
        self.regular = int(total_budget * 0.85)
        self.beast = int(total_budget * 0.15)
        self.used = 0

    def can_continue(self) -> bool:
        return self.used < self.regular

    def track(self, tokens: int):
        self.used += tokens

    def beast_mode_budget(self) -> int:
        return self.total - self.used
```

**Target file**: `goal_bundle_loop.py` — replace `max_rounds` with `BudgetManager`.

---

### 9. Dynamic Action Disabling

**What**: At each step, enable/disable available actions based on current state. Don't let the LLM choose "search" when it has 50+ unread URLs. Don't let it "answer" when knowledge is empty.

**Why**: autosearch's goal_bundle_loop doesn't constrain the LLM's action space. The LLM sometimes loops (searching when it should read, answering when it hasn't searched).

**Source**: Jina node-deepresearch

- **Initial action flags**: [`src/agent.ts` L484-L488](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L484-L488)
- **Dynamic rules table**: See below
- **Schema generation from flags**: [`src/utils/schemas.ts` L268](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/schemas.ts#L268)

**Principle**:

Jina's complete action disabling rules (from agent.ts):

| Rule | Line | Logic |
|------|------|-------|
| Reflect capped by gap count | [L524](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L524) | `allow_reflect = len(gaps) <= MAX_REFLECT` |
| Read requires URLs | [L566](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L566) | `allow_read = len(urls) > 0` |
| Search disabled when 50+ URLs | [L568](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L568) | `allow_search = len(urls) < 50` |
| Answer disabled after failed eval | [L744](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L744) | `allow_answer = False` |
| Reflect disabled after reflecting | [L803](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L803) | `allow_reflect = False` |
| Search disabled after searching | [L927](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L927) | `allow_search = False` |
| All reset each iteration start | [L605-L609](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L605-L609) | All flags = True |

The flags are passed to `getAgentSchema()` which generates a Zod schema that physically excludes disabled actions from the LLM's output space. The LLM literally cannot choose a disabled action because it's not in the schema.

**Port**:

```python
# In goal_bundle_loop.py:

@dataclass
class ActionFlags:
    allow_search: bool = True
    allow_read: bool = True
    allow_answer: bool = True
    allow_reflect: bool = True

    def reset(self):
        self.allow_search = True
        self.allow_read = True
        self.allow_answer = True
        self.allow_reflect = True

    def apply_state_rules(self, urls_count: int, gaps_count: int,
                          knowledge_count: int, last_action: str):
        self.allow_read = urls_count > 0
        self.allow_search = urls_count < 50
        self.allow_answer = knowledge_count > 0
        self.allow_reflect = gaps_count <= 10

        # Prevent immediate repeat of same action type
        if last_action == "search":
            self.allow_search = False
        elif last_action == "reflect":
            self.allow_reflect = False

    def available_actions(self) -> list[str]:
        actions = []
        if self.allow_search: actions.append("search")
        if self.allow_read: actions.append("read")
        if self.allow_answer: actions.append("answer")
        if self.allow_reflect: actions.append("reflect")
        return actions
```

**Target file**: `goal_bundle_loop.py` — add action control before each LLM call.

---

### 10. Diary Context (Step-by-Step Execution History)

**What**: After each step, record a narrative log entry ("At step 3, searched for X, found Y"). Pass all diary entries to the LLM as context for the next step.

**Why**: autosearch writes to `evolution.jsonl` only after a session ends. The LLM has no visibility into what it already tried within a session, leading to repeated strategies.

**Source**: Jina node-deepresearch

- **Diary init**: [`src/agent.ts` L482](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L482)
- **Diary passed to prompt**: [`src/agent.ts` L571-L572](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L571-L572)
- **Rendered as `<context>` block**: [`src/agent.ts` L135-L143](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L135-L143)
- **After search**: [`src/agent.ts` L899-L903](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L899-L903)
- **After failed answer**: [`src/agent.ts` L705-L716](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L705-L716)
- **Diary reset on failure**: [`src/agent.ts` L745](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L745)

**Principle**:

```
diary = []

# After each action:
diary.append(f"Step {step}: action={action}, query='{query}', "
             f"found {len(results)} results, top score={top_score}")

# In system prompt:
"""
You have conducted the following actions:
<context>
{diary.join('\n')}
</context>
"""
```

On critical failure (answer rejected by evaluator), the diary is reset to prevent the LLM from fixating on failed approaches:

```typescript
// agent.ts L745
diaryContext = [];  // Reset diary, start fresh
```

**Port**:

```python
# In goal_bundle_loop.py or engine.py:

class SessionDiary:
    def __init__(self):
        self.entries: list[str] = []

    def log_search(self, step: int, query: str, results_count: int, top_score: float):
        self.entries.append(
            f"Step {step}: searched '{query}', found {results_count} results, "
            f"top score={top_score:.1f}"
        )

    def log_reflect(self, step: int, new_gaps: list[str]):
        self.entries.append(
            f"Step {step}: reflected, identified {len(new_gaps)} gaps: "
            f"{', '.join(new_gaps[:3])}"
        )

    def log_answer_failed(self, step: int, reason: str):
        self.entries.append(
            f"Step {step}: attempted answer but evaluator rejected: {reason}"
        )

    def log_answer_accepted(self, step: int, question: str):
        self.entries.append(
            f"Step {step}: answered '{question[:50]}...' — accepted"
        )

    def reset(self):
        self.entries = []

    def to_context(self) -> str:
        if not self.entries:
            return ""
        return "<context>\n" + "\n".join(self.entries) + "\n</context>"
```

**Target file**: `goal_bundle_loop.py` — add diary tracking and inject into LLM prompts.

---

## Phase 3 — Execution Efficiency

### 11. Async Parallel Platform Search

**What**: Execute all platform searches for a query concurrently using `asyncio.gather`, with a semaphore to cap concurrency.

**Why**: autosearch runs platforms sequentially in `engine.py`. A round with 6 platforms × 2s latency = 12s. Parallel execution = ~2s.

**Source**: LangChain open_deep_research + dzhng/deep-research

- **LangChain parallel research tasks**: [`src/open_deep_research/deep_researcher.py` L288-L305](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py#L288-L305)
- **LangChain parallel search queries**: [`src/open_deep_research/utils.py` L138-L173](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L138-L173)
- **deep-research concurrency control**: Uses `p-limit` library (Node.js equivalent of asyncio.Semaphore)

**Principle**:

LangChain's pattern:

```python
# open_deep_research/deep_researcher.py L288-L305
research_tasks = [
    researcher_subgraph.ainvoke({...}, config)
    for tool_call in allowed_conduct_research_calls
]
tool_results = await asyncio.gather(*research_tasks)
```

The key addition: cap concurrency to avoid rate limits and resource exhaustion.

**Port**:

```python
# In engine.py, modify SearchEngine._run_round():

import asyncio

class SearchEngine:
    async def _run_round_async(self, queries: list[str], platforms: list[dict]) -> list[SearchResult]:
        sem = asyncio.Semaphore(5)  # Max 5 concurrent API calls

        async def search_one(query: str, platform: dict) -> list[SearchResult]:
            async with sem:
                try:
                    return await asyncio.wait_for(
                        self._search_platform_async(query, platform),
                        timeout=10.0  # Per-platform timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout: {platform['name']} for '{query[:30]}'")
                    return []  # Partial results OK

        tasks = [
            search_one(q, p)
            for q in queries
            for p in platforms
        ]
        results = await asyncio.gather(*tasks)
        return [r for batch in results for r in batch]  # flatten
```

**Note**: This requires converting PlatformConnector methods from sync to async. Start with platforms that use HTTP APIs (Exa, Tavily, Reddit) which are naturally async-friendly. Keep gh CLI calls sync via `asyncio.to_thread()`.

**Target file**: `engine.py` — add async variants of search methods.

---

### 12. Timeout with Partial Results

**What**: Set a per-platform timeout. If a platform doesn't respond in time, continue with whatever results are available from other platforms.

**Why**: autosearch blocks on each platform. If Twitter xreach hangs (known issue in patterns.jsonl), the entire round waits.

**Source**: Swirl

- **Celery timeout dispatch**: [`swirl/search.py` L201-L224](https://github.com/swirlai/swirl-search/blob/main/swirl/search.py#L201-L224)
- **Timeout config**: [`swirl_server/settings.py` L256-L257](https://github.com/swirlai/swirl-search/blob/main/swirl_server/settings.py#L256-L257) — `SWIRL_TIMEOUT = 10`
- **Partial status handling**: [`swirl/search.py` L259-L266](https://github.com/swirlai/swirl-search/blob/main/swirl/search.py#L259-L266)

**Principle**:

```python
# Swirl's approach (simplified from search.py L201-224):
from celery import group

tasks = [federate_task.s(provider_id) for provider_id in providers]
results = group(*tasks).delay()

try:
    results = results.get(timeout=SWIRL_TIMEOUT)  # 10 seconds
except CeleryTimeoutError:
    logger.warning("Timeout — continuing with partial results")
    # Whatever providers finished before timeout have already
    # saved their results to the database. Post-processing
    # proceeds with available data.
```

For autosearch (no Celery), use `asyncio.wait` with `timeout`:

**Port**:

```python
# Uses the async infrastructure from #11

async def search_with_timeout(
    queries: list[str],
    platforms: list[dict],
    timeout: float = 10.0
) -> tuple[list[SearchResult], list[str]]:
    """Returns (results, timed_out_platforms)."""
    tasks = {
        asyncio.create_task(search_one(q, p)): (q, p["name"])
        for q in queries for p in platforms
    }

    done, pending = await asyncio.wait(
        tasks.keys(), timeout=timeout
    )

    # Collect completed results
    results = []
    for task in done:
        results.extend(task.result())

    # Cancel and log timed-out tasks
    timed_out = []
    for task in pending:
        q, platform_name = tasks[task]
        timed_out.append(platform_name)
        task.cancel()

    if timed_out:
        logger.warning(f"Timed out: {set(timed_out)}")

    return results, timed_out
```

**Target file**: `engine.py` — wrap async search dispatch with `asyncio.wait`.

---

### 13. Parallel URL Summarization

**What**: When extracting evidence from multiple URLs, summarize all of them concurrently instead of one-by-one.

**Why**: autosearch's evidence extraction in `acquisition/fetch_pipeline.py` processes URLs sequentially. 10 URLs × 3s each = 30s. Parallel = ~5s.

**Source**: LangChain open_deep_research

- **Parallel summarization**: [`src/open_deep_research/utils.py` L100-L110](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L100-L110)
- **`summarize_webpage` with timeout**: [`src/open_deep_research/utils.py` L175-L213](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L175-L213)

**Principle**:

```python
# open_deep_research/utils.py L100-L110
summarization_tasks = [
    summarize_webpage(model, result['raw_content'][:max_chars])
    for result in unique_results.values()
]
summaries = await asyncio.gather(*summarization_tasks)
```

Each `summarize_webpage` call has a 60-second timeout. Use a lighter model (e.g., Haiku) for summarization to save cost.

**Port**:

```python
# In evidence/models.py or acquisition/fetch_pipeline.py:

async def parallel_summarize(
    urls: list[str],
    query: str,
    model: str = "claude-haiku-4-5-20251001",
    max_concurrent: int = 5,
    timeout: float = 30.0
) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrent)

    async def summarize_one(url: str) -> dict:
        async with sem:
            try:
                content = await asyncio.wait_for(
                    fetch_and_extract(url), timeout=timeout
                )
                relevant = select_relevant_content(content, query, max_chars=2000)
                summary = await llm_summarize(relevant, query, model=model)
                return {"url": url, "summary": summary, "status": "ok"}
            except Exception as e:
                return {"url": url, "summary": "", "status": f"error: {e}"}

    return await asyncio.gather(*[summarize_one(url) for url in urls])
```

**Target file**: `acquisition/fetch_pipeline.py` + `evidence/models.py`.

---

## Phase 4 — Scoring & Evaluation Upgrades

### 14. Composite URL Ranking

**What**: Rank URLs using multiple signals: appearance frequency, domain frequency, URL path patterns, and semantic relevance. Not just engagement + LLM binary.

**Why**: autosearch's scoring is `0.4 × engagement + 0.6 × LLM_relevance`. This misses structural signals: a URL found by 3 different queries is more valuable than one found by 1.

**Source**: Jina node-deepresearch

- **`rankURLs` function**: [`src/utils/url-tools.ts` L250-L349](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/url-tools.ts#L250-L349)
- **Score weights**: [`src/utils/url-tools.ts` L252-L261](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/url-tools.ts#L252-L261)
- **Composite formula**: [`src/utils/url-tools.ts` L330-L348](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/url-tools.ts#L330-L348)
- **Per-hostname diversity cap**: [`src/utils/url-tools.ts` L451-L472](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/url-tools.ts#L451-L472)

**Principle**:

Jina's scoring formula (from url-tools.ts L330-L348):

```
finalScore = clamp(
    hostnameBoost + pathBoost + freqBoost + jinaRerankBoost,
    min=0, max=5
)

where:
  freqBoost     = (times_url_appeared / total_urls) × 0.5
  hostnameBoost = (hostname_frequency / total_hostnames) × 0.5 × decay^path_depth
  pathBoost     = (path_frequency / total_paths) × 0.4
  jinaRerankBoost = jina_reranker_score × 0.8    # heaviest weight
```

Plus a diversity cap: `keepKPerHostname(results, k=2)` — max 2 URLs per domain.

**Port**:

```python
# New file: autosearch/url_ranking.py

from dataclasses import dataclass
from collections import Counter
from urllib.parse import urlparse

@dataclass
class RankedURL:
    url: str
    title: str
    freq_boost: float = 0.0
    hostname_boost: float = 0.0
    path_boost: float = 0.0
    relevance_boost: float = 0.0
    final_score: float = 0.0

def rank_urls(
    urls: list[dict],  # [{url, title, snippet, query}]
    query: str,
    freq_factor: float = 0.5,
    hostname_factor: float = 0.5,
    path_factor: float = 0.4,
    relevance_factor: float = 0.8,
    decay: float = 0.8,
    max_per_hostname: int = 2
) -> list[RankedURL]:
    total = len(urls)
    if total == 0:
        return []

    # Count frequencies
    url_counts = Counter(u["url"] for u in urls)
    hostname_counts = Counter(urlparse(u["url"]).hostname for u in urls)
    path_counts = Counter(urlparse(u["url"]).path for u in urls)

    seen = set()
    ranked = []
    for u in urls:
        if u["url"] in seen:
            continue
        seen.add(u["url"])

        parsed = urlparse(u["url"])
        depth = len([p for p in parsed.path.split('/') if p])

        freq_boost = (url_counts[u["url"]] / total) * freq_factor
        hostname_boost = (hostname_counts[parsed.hostname] / total) * hostname_factor * (decay ** depth)
        path_boost = (path_counts[parsed.path] / total) * path_factor
        relevance_boost = u.get("relevance_score", 0) * relevance_factor

        final = max(0, min(5,
            freq_boost + hostname_boost + path_boost + relevance_boost
        ))

        ranked.append(RankedURL(
            url=u["url"], title=u.get("title", ""),
            freq_boost=freq_boost, hostname_boost=hostname_boost,
            path_boost=path_boost, relevance_boost=relevance_boost,
            final_score=final
        ))

    # Sort by score
    ranked.sort(key=lambda r: r.final_score, reverse=True)

    # Diversity cap: max K per hostname
    hostname_seen = Counter()
    diverse = []
    for r in ranked:
        host = urlparse(r.url).hostname
        if hostname_seen[host] < max_per_hostname:
            diverse.append(r)
            hostname_seen[host] += 1

    return diverse
```

**Target file**: New `url_ranking.py` + integrate into `engine.py` after result collection.

---

### 15. Cross-Platform Score Normalization (Cosine + Length)

**What**: Normalize relevancy scores across platforms using cosine similarity with field-weight adjustment and length normalization, so scores from different platforms are comparable.

**Why**: autosearch's `0.4 × engagement + 0.6 × LLM_relevance` produces incomparable scores across platforms. A Reddit post with 100 upvotes scores differently than a GitHub repo with 100 stars, even if equally relevant.

**Source**: Swirl

- **Scoring formula**: [`swirl/processors/relevancy.py` L437-L452](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/relevancy.py#L437-L452)
- **Relevancy config**: [`swirl_server/settings.py` L265-L275](https://github.com/swirlai/swirl-search/blob/main/swirl_server/settings.py#L265-L275)

**Principle**:

Swirl's formula (from relevancy.py L437-L452):

```
swirl_score += (weight × cosine_similarity) × (match_length²) × len_adjust × qlen_adjust × rank_adjust

where:
  weight       = field weight (title: 1.5, body: 1.0)
  cosine_sim   = spaCy embedding similarity between query and field text
  match_length² = length of matching term, squared (favors longer matches)
  len_adjust   = median(all_field_lengths) / this_field_length  (normalizes for content length)
  qlen_adjust  = median(query_lengths) / provider_query_length
  rank_adjust  = 1.0 + 1.0 / sqrt(provider_rank)  (boost for higher-ranked results)
```

The `len_adjust` is the critical piece: it prevents long-form content (articles) from automatically scoring higher than short-form (tweets) just because there are more terms to match.

**Port**:

```python
# In engine.py, add to scoring logic:

import math
from statistics import median

FIELD_WEIGHTS = {
    "title": 1.5,
    "body": 1.0,
    "description": 1.2,
}

def normalize_score(
    result: SearchResult,
    query: str,
    all_results: list[SearchResult],
    cosine_fn  # (text_a, text_b) -> float
) -> float:
    score = 0.0

    # Compute median lengths for normalization
    title_lengths = [len(r.title) for r in all_results if r.title]
    body_lengths = [len(r.body) for r in all_results if r.body]
    med_title = median(title_lengths) if title_lengths else 1
    med_body = median(body_lengths) if body_lengths else 1

    for field, weight in FIELD_WEIGHTS.items():
        text = getattr(result, field, "") or ""
        if not text:
            continue

        sim = cosine_fn(query, text)
        if sim < 0.3:  # minimum similarity threshold
            continue

        med = med_title if field == "title" else med_body
        len_adjust = med / max(len(text), 1)
        rank_adjust = 1.0 + 1.0 / math.sqrt(max(result.rank or 1, 1))

        score += weight * sim * len_adjust * rank_adjust

    return score
```

**Target file**: `engine.py` — add as scoring method alongside existing engagement + LLM scoring.

---

### 16. Multi-Dimensional Answer Evaluation

**What**: Before evaluating a research answer, classify what type of evaluation it needs: definitive (one right answer), freshness (needs current data), plurality (needs multiple answers), completeness (must cover all aspects), or attribution (must cite sources). Then run type-specific evaluation.

**Why**: autosearch's evaluation is binary (relevant/not). A research answer about "best AI frameworks in 2026" needs freshness + plurality + completeness checks, not just relevance.

**Source**: Jina node-deepresearch

- **`EvaluationType` enum**: [`src/types.ts` L76](https://github.com/jina-ai/node-DeepResearch/blob/main/src/types.ts#L76)
- **`evaluateQuestion()` classifier**: [`src/tools/evaluator.ts` L560-L595](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L560-L595)
- **`evaluateAnswer()` sequential fail-fast**: [`src/tools/evaluator.ts` L622-L671](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L622-L671)
- **Evaluation prompt for each type**:
  - strict: [`src/tools/evaluator.ts` L11](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L11)
  - definitive: [`src/tools/evaluator.ts` L49](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L49)
  - freshness: [`src/tools/evaluator.ts` L156](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L156)
  - completeness: [`src/tools/evaluator.ts` L221](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L221)
  - plurality: [`src/tools/evaluator.ts` L312](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L312)
- **Eval retry budget decrement**: [`src/agent.ts` L688-L703](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L688-L703)

**Principle**:

Two-phase evaluation:

```
Phase 1 (once, at session start):
  eval_types = classify_question(question)
  # Returns: ["freshness", "plurality", "completeness"]

Phase 2 (each time an answer is attempted):
  for eval_type in eval_types:
    result = run_eval(eval_type, question, answer)
    if not result.pass:
      return fail(result.reason)  # fail-fast on first failure
  return pass()
```

Each eval type has a different prompt:
- **definitive**: "Does this answer provide a clear, specific response?"
- **freshness**: "Does this answer use data current as of {today}?"
- **plurality**: "Does this answer cover multiple valid perspectives/options?"
- **completeness**: "Does this answer address all aspects of the question?"
- **strict**: "Find ANY reason to reject this answer" (the hardest check)

Retry budget: each eval type starts with `numEvalsRequired = 2`. On failure, decrement. When all reach 0, give up and enter beast mode.

**Port**:

```python
# New file: autosearch/evaluator.py

from enum import Enum
from dataclasses import dataclass

class EvalType(Enum):
    DEFINITIVE = "definitive"
    FRESHNESS = "freshness"
    PLURALITY = "plurality"
    COMPLETENESS = "completeness"
    ATTRIBUTION = "attribution"

@dataclass
class EvalResult:
    passed: bool
    eval_type: EvalType
    reason: str

EVAL_PROMPTS = {
    EvalType.DEFINITIVE: "Does this answer provide a clear, specific, non-hedging response to the question? Answer: {answer}",
    EvalType.FRESHNESS: "Does this answer contain data current as of {date}? Are there any outdated claims? Answer: {answer}",
    EvalType.PLURALITY: "Does this answer present multiple valid options/perspectives where appropriate? Answer: {answer}",
    EvalType.COMPLETENESS: "Does this answer cover all major aspects of the question? What's missing? Answer: {answer}",
    EvalType.ATTRIBUTION: "Does this answer cite specific sources for its claims? Are citations verifiable? Answer: {answer}",
}

async def classify_question(question: str, llm) -> list[EvalType]:
    """Determine which evaluation types apply to this question."""
    response = await llm.generate(
        f"Classify this question. Which checks apply?\n"
        f"- definitive: has one clear answer\n"
        f"- freshness: needs current/recent data\n"
        f"- plurality: needs multiple options\n"
        f"- completeness: needs comprehensive coverage\n"
        f"- attribution: must cite sources\n"
        f"\nQuestion: {question}\n"
        f"Return JSON: {{\"types\": [\"definitive\", ...]}}"
    )
    return [EvalType(t) for t in response["types"]]

async def evaluate_answer(
    question: str,
    answer: str,
    eval_types: list[EvalType],
    llm
) -> EvalResult:
    """Sequential fail-fast evaluation."""
    for et in eval_types:
        prompt = EVAL_PROMPTS[et].format(answer=answer, date="2026-03-25")
        result = await llm.generate(
            f"{prompt}\n\nReturn JSON: {{\"pass\": true/false, \"reason\": \"...\"}}"
        )
        if not result["pass"]:
            return EvalResult(passed=False, eval_type=et, reason=result["reason"])
    return EvalResult(passed=True, eval_type=eval_types[-1], reason="All checks passed")
```

**Target file**: New `evaluator.py` + integrate into `goal_bundle_loop.py`.

---

### 17. SERP Result Clustering

**What**: After collecting search results, cluster them by semantic similarity. Each cluster generates an automatic insight. Transforms scattered results into structured findings.

**Why**: autosearch treats each search result independently. If 5 different results all discuss "query rewriting", this pattern is invisible. Clustering surfaces these themes.

**Source**: Jina node-deepresearch (referenced in architecture but not a standalone function — Jina uses embedding clustering inline)

**Also relevant**: Swirl's mixer architecture groups results by source, but Jina's approach groups by content similarity.

**Principle**:

```
1. Embed all result titles + snippets
2. Compute pairwise cosine similarity matrix
3. Cluster using simple threshold-based grouping:
   - For each unassigned result, create new cluster
   - Assign any unassigned result with similarity > 0.7 to same cluster
4. For each cluster with 2+ items:
   - Generate cluster label (common topic)
   - Generate cluster insight (what these results collectively tell us)
5. Return clusters as structured findings
```

**Port**:

```python
# New file: autosearch/clustering.py

from dataclasses import dataclass

@dataclass
class ResultCluster:
    label: str
    insight: str
    results: list[dict]  # [{url, title, snippet}]
    avg_similarity: float

async def cluster_results(
    results: list[dict],
    embed_fn,
    similarity_threshold: float = 0.7,
    min_cluster_size: int = 2
) -> list[ResultCluster]:
    if len(results) < 2:
        return []

    # Embed all result texts
    texts = [f"{r['title']} {r.get('snippet', '')}" for r in results]
    embeddings = await embed_fn(texts)

    # Simple greedy clustering
    assigned = [False] * len(results)
    clusters = []

    for i in range(len(results)):
        if assigned[i]:
            continue
        cluster_indices = [i]
        assigned[i] = True

        for j in range(i + 1, len(results)):
            if assigned[j]:
                continue
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= similarity_threshold:
                cluster_indices.append(j)
                assigned[j] = True

        if len(cluster_indices) >= min_cluster_size:
            cluster_results_list = [results[idx] for idx in cluster_indices]
            clusters.append(ResultCluster(
                label="",  # filled by LLM
                insight="",  # filled by LLM
                results=cluster_results_list,
                avg_similarity=0.0  # compute if needed
            ))

    return clusters
```

**Target file**: New `clustering.py` + integrate into `engine.py` after result collection, before LLM evaluation.

---

## Appendix: Source Repository Summary

| Repo | Stars | Language | Key Innovation | Best For |
|------|-------|----------|---------------|----------|
| [firecrawl/fireplexity](https://github.com/firecrawl/fireplexity) | — | TypeScript | Content selection algorithm | #4 (paragraph scoring) |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) | 10K+ | TypeScript | Recursive depth-first + breadth halving | #5 #7 (learnings + recursion) |
| [jina-ai/node-deepresearch](https://github.com/jina-ai/node-deepresearch) | 5K+ | TypeScript | Token budget + action disabling + multi-eval | #1 #6 #8 #9 #10 #14 #16 (most techniques) |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | — | Python | Parallel async + hierarchical compression | #11 #13 (async patterns, already Python) |
| [swirlai/swirl-search](https://github.com/swirlai/swirl-search) | 2K+ | Python | Federated search + cross-source normalization | #2 #3 #12 #15 (multi-source infrastructure) |

### Technique Origin Map

| Technique | Jina | dzhng | LangChain | Swirl | Fireplexity |
|-----------|------|-------|-----------|-------|-------------|
| 1. Embedding query dedup | **primary** | | | | |
| 2. URL dedup before scoring | | | secondary | **primary** | |
| 3. Per-platform query transform | | | | **primary** | |
| 4. Keyword paragraph selection | | | | | **primary** |
| 5. Info-density prompting | | **primary** | | | |
| 6. FIFO gap queue | **primary** | | | | |
| 7. Recursive deep search | | **primary** | | | |
| 8. Token budget + beast mode | **primary** | | | | |
| 9. Dynamic action disabling | **primary** | | | | |
| 10. Diary context | **primary** | | | | |
| 11. Async parallel search | | secondary | **primary** | secondary | |
| 12. Timeout + partial results | | | | **primary** | |
| 13. Parallel URL summarization | | | **primary** | | |
| 14. Composite URL ranking | **primary** | | | | |
| 15. Cross-platform score normalization | | | | **primary** | |
| 16. Multi-dimensional evaluation | **primary** | | | | |
| 17. SERP clustering | **primary** | | | | |
