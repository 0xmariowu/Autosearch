# AutoSearch Improvement Catalog V2 — 16 Repo Analysis

> Date: 2026-03-25
> Status: active
> Supersedes: 2026-03-25-competitor-improvements.md (V1, 5 repos)
> Purpose: 1:1 copyable improvements for autosearch from 16 competitor repos.

## Source Repos

| # | Repo | Focus | Key Contribution |
|---|------|-------|-----------------|
| 1 | [jina-ai/node-deepresearch](https://github.com/jina-ai/node-deepresearch) | Deep research agent | Gap queue, action disabling, beast mode, eval framework, query dedup, late chunking, diary context |
| 2 | [dzhng/deep-research](https://github.com/dzhng/deep-research) | Recursive research | Breadth halving recursion, info-density prompting, research goal preservation |
| 3 | [swirlai/swirl-search](https://github.com/swirlai/swirl-search) | Federated search | Cross-source scoring, timeout+partial, processor chain, cosine+length normalization |
| 4 | [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | Research orchestration | Parallel async, hierarchical compression, think_tool, graceful degradation |
| 5 | [firecrawl/fireplexity](https://github.com/firecrawl/fireplexity) | Search-answer | Keyword paragraph selection, content truncation |
| 6 | [searxng/searxng](https://github.com/searxng/searxng) | Metasearch engine | Harmonic position scoring, engine suspension, category routing |
| 7 | [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Research agent | Embedding filter (0.35), review-revision loop, multi-agent report |
| 8 | [InternLM/MindSearch](https://github.com/InternLM/MindSearch) | Multi-agent search | DAG decomposition, reference pointer arithmetic |
| 9 | [ItzCrazyKns/Vane](https://github.com/ItzCrazyKns/Vane) | Multi-mode search | Speed/balanced/quality modes, classification gating, reasoning preamble |
| 10 | [zaidmukaddam/scira](https://github.com/zaidmukaddam/scira) | Multi-tool search | Search group routing, domain+URL dedup, extreme search agent |
| 11 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | Web extraction | BM25 content filter, memory-adaptive dispatcher, session reuse |
| 12 | [deedy5/ddgs](https://github.com/deedy5/ddgs) | DuckDuckGo client | Multi-engine ThreadPool, provider-aware dedup, browser impersonation |
| 13 | [leptonai/search_with_lepton](https://github.com/leptonai/search_with_lepton) | Search-answer | Stop words for LLM, stream-and-cache, citation via prompt |
| 14 | [fatwang2/search4all](https://github.com/fatwang2/search4all) | Multi-engine | Unified result schema, SQLite KV cache, related questions via function call |
| 15 | [YassKhazzan/openperplex_backend_os](https://github.com/YassKhazzan/openperplex_backend_os) | Search-answer | Semantic chunking trigger, Jina reranker post-aggregation |
| 16 | [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus) | Agent framework | PlanningFlow, ReAct loop, multi-engine fallback chain |

---

## Master Improvement List (25 items, by priority)

### Tier S — Directly Improves Search Quality, Minimal Code Change

#### S1. Embedding-Based Query Dedup

**What**: Skip queries that are semantically similar to already-run queries.

**Why**: Gene pool produces many near-duplicate queries. Wastes API calls.

**Sources**:
- Jina: [`src/tools/jina-dedup.ts` L9-L77](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/jina-dedup.ts#L9-L77) — threshold 0.86
- ddgs: `ResultsAggregator` deduplicates by URL across providers

**Algorithm**:
```
for each new_query:
  embed(new_query)
  for each existing_query in evolution.jsonl:
    if cosine(new_query, existing_query) >= 0.86:
      skip
  for each already_accepted in this_batch:
    if cosine(new_query, already_accepted) >= 0.86:
      skip
  accept(new_query)
```

**Port** → new `query_dedup.py`, call from `engine.py` before platform dispatch.

---

#### S2. URL Dedup Before Scoring

**What**: Check URLs against session-wide set BEFORE LLM evaluation. Skip already-seen.

**Why**: Wastes LLM tokens evaluating duplicate URLs (currently dedup only in post-mortem).

**Sources**:
- Swirl: [`swirl/processors/dedupe.py` L77-L97](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/dedupe.py#L77-L97)
- Scira: domain+URL dual dedup — tracks both `seen_urls` AND `seen_domains`
- LangChain: [`src/open_deep_research/utils.py` L43-L136](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L43-L136)

**Port**:
```python
class SearchEngine:
    seen_urls: set[str] = set()
    seen_domains: set[str] = set()  # from Scira

    def dedup(self, results):
        unique = []
        for r in results:
            url = r.url.rstrip('/').lower()
            domain = urlparse(url).hostname
            if url not in self.seen_urls:  # exact URL dedup
                self.seen_urls.add(url)
                # Optional: domain dedup (max N per domain)
                unique.append(r)
        return unique
```

**Target**: `engine.py` — filter before `evaluate_round()`.

---

#### S3. Per-Platform Query Transform

**What**: Adapt each query to the platform's syntax. GitHub gets `stars:>50`, HN gets quoted names, Reddit gets `sort:relevance`.

**Why**: Same raw query sent to all 11 platforms. patterns.jsonl knows the optimal syntax but it's not applied programmatically.

**Sources**:
- Swirl: [`swirl/processors/adaptive.py` L15-L128](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/adaptive.py#L15-L128)
- SearXNG: per-engine `request()` function transforms query params ([`searx/engines/`](https://github.com/searxng/searxng/tree/master/searx/engines))

**Port** → `config/query_transforms.json` (rules) + `transform_query()` function in `engine.py`.

---

#### S4. Intelligent Content Extraction

**What**: Split page into paragraphs, score by keyword overlap, keep intro + top-scored + conclusion.

**Why**: `fit_markdown` does naive 1200-char substring. Loses important content, includes boilerplate.

**Sources**:
- Fireplexity: [`lib/content-selection.ts` L1-L46](https://github.com/firecrawl/fireplexity/blob/main/lib/content-selection.ts#L1-L46)
- crawl4ai: `BM25ContentFilter` — query-aware extraction using BM25 scoring (better than keyword count)
- openperplex: semantic chunking with `CohereEncoder` + `StatisticalChunker`, triggers only when content > 200 chars

**Best approach**: Combine Fireplexity's simplicity with crawl4ai's BM25:

```python
def select_relevant_content(content: str, query: str, max_chars: int = 2000) -> str:
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    if len(paragraphs) <= 5:
        return content[:max_chars]

    keywords = [w for w in query.lower().split() if len(w) > 3 and w not in STOP_WORDS]
    intro = paragraphs[:2]
    conclusion = paragraphs[-1:]
    middle = paragraphs[2:-1]

    scored = [(i, sum(1 for kw in keywords if kw in p.lower()), p) for i, p in enumerate(middle)]
    scored = [s for s in scored if s[1] > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = sorted(scored[:3], key=lambda x: x[0])  # restore reading order

    return '\n\n'.join(intro + [p for _, _, p in top] + conclusion)[:max_chars]
```

**Target**: `evidence/models.py` — replace `fit_markdown`.

---

#### S5. Info-Density Prompting

**What**: LLM evaluation prompt requires concrete entities, numbers, dates. Rejects vague learnings.

**Why**: Current eval asks only "relevant? yes/no". Extracted evidence is often vague.

**Sources**:
- dzhng: [`src/deep-research.ts` L81-L118](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L81-L118)
- gpt-researcher: LLM-based source curation prioritizes "statistics and concrete data"

**Port**: Modify `LLMEvaluator.evaluate_round()` prompt:
```
"Each learning MUST include: specific entities (product names, companies),
numbers/metrics/thresholds, dates or versions.
BAD: 'This repo has useful patterns'
GOOD: 'swirl-search uses cosine > 0.95 for semantic dedup (dedupe.py L101)'"
```

**Target**: `engine.py` LLMEvaluator prompt.

---

#### S6. Engine Health Tracking + Auto-Suspension

**What**: Track consecutive errors per platform. Auto-suspend platforms after N failures. Auto-resume after cooldown.

**Why**: autosearch has `experience-policy.json` for provider preferences but no automatic suspension. If Twitter xreach hangs, it keeps getting called.

**Sources**:
- SearXNG: `SuspendedStatus` class — tracks `continuous_errors`, `suspend_end_time`, `suspend_reason`. Configurable cooldowns: 429→1hr, 403→24hr. ([`searx/search/processors/`](https://github.com/searxng/searxng/tree/master/searx/search/processors))
- ddgs: Multi-engine fallback — if one engine errors, continues to next

**Port**:
```python
@dataclass
class EngineHealth:
    consecutive_errors: int = 0
    suspended_until: float = 0  # unix timestamp
    suspend_reason: str = ""

    COOLDOWNS = {
        "rate_limit": 3600,     # 1 hour
        "auth_error": 86400,    # 24 hours
        "timeout": 300,         # 5 minutes
        "unknown": 600,         # 10 minutes
    }

    def record_error(self, error_type: str):
        self.consecutive_errors += 1
        if self.consecutive_errors >= 3:
            cooldown = self.COOLDOWNS.get(error_type, 600)
            self.suspended_until = time.time() + cooldown
            self.suspend_reason = error_type

    def record_success(self):
        self.consecutive_errors = 0
        self.suspended_until = 0

    def is_suspended(self) -> bool:
        return time.time() < self.suspended_until
```

**Target**: `engine.py` PlatformConnector + `project_experience.py`.

---

### Tier A — Research Depth (goal_bundle_loop Upgrade)

#### A1. FIFO Gap Queue

**What**: Replace dimension cycling with a queue of gap questions. Gaps discovered during research added to queue, answered gaps removed.

**Sources**:
- Jina: gap init [L476](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L476), round-robin [L526](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L526), add gaps [L778-786](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L778-L786)

**Port**: `gaps = [original_question]`, `current_q = gaps[step % len(gaps)]`, extend on reflect, remove on answer.

---

#### A2. Recursive Deep Search + Breadth Halving

**What**: Generate N sub-queries, execute in parallel, recurse with N/2 sub-queries. Depth counter for termination.

**Sources**:
- dzhng: [`src/deep-research.ts` L176-L294](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L176-L294), breadth halving [L230](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts#L230)

**Total queries**: breadth=4, depth=3 → ~7 per branch. Guaranteed termination.

---

#### A3. DAG-Based Query Decomposition

**What**: Model research as a directed acyclic graph, not a flat list. Sub-questions are nodes, dependencies are edges. Enables parallel execution of independent branches.

**Sources**:
- MindSearch: `WebSearchGraph` with `add_node()`, `add_edge()`, `add_response_node()`. Reference pointer arithmetic for citation renumbering across nodes.

**Key algorithm** — citation renumbering:
```python
ptr = 0  # global reference offset
for node in graph.nodes:
    # Renumber [[1]]→[[ptr+1]], [[2]]→[[ptr+2]]
    node.content = renumber_refs(node.content, offset=ptr)
    ptr += node.ref_count
# Result: all citations globally unique
```

**When to use**: Complex multi-faceted research goals (not daily discovery). Combine with A1 (gap queue for daily) or A2 (recursion for deep dives).

---

#### A4. Token Budget + Beast Mode

**What**: 85% budget for normal iteration, 15% reserved for forced answer.

**Sources**:
- Jina: budget split [L498-499](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L498-L499), beast mode [L1036-1076](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L1036-L1076)

---

#### A5. Dynamic Action Disabling

**What**: Enable/disable actions based on state. Don't let LLM choose "search" with 50+ unread URLs.

**Sources**:
- Jina: flags [L484-488](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L484-L488), rules throughout `agent.ts`
- Vane: optimization modes control tool budgets — Speed: 1-2 tools, Balanced: 6, Quality: 10+

**Key rules**:
| Condition | Disable |
|-----------|---------|
| 50+ unread URLs | search |
| 0 knowledge items | answer |
| 10+ gap questions | reflect |
| Just searched | search (prevent repeat) |
| Just reflected | reflect (prevent repeat) |
| Failed answer eval | answer |

---

#### A6. Reasoning Preamble (Think Before Act)

**What**: Force LLM to output a reasoning step before each tool call. Captures the "why" of each action.

**Sources**:
- Vane: `__reasoning_preamble` tool required before each search in balanced/quality modes
- LangChain: `think_tool` — [`src/open_deep_research/utils.py` L219-L244](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L219-L244)
- OpenManus: ReAct loop (think-act-observe cycle)

**Port**: Add a `think` field to the LLM response schema. Before each action, LLM must output reasoning. Log reasoning to diary context.

---

#### A7. Diary Context

**What**: After each step, record narrative log. Pass all entries as context to next LLM call.

**Sources**:
- Jina: diary [L482](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L482), entries [L899-903](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L899-L903), reset on failure [L745](https://github.com/jina-ai/node-DeepResearch/blob/main/src/agent.ts#L745)

---

#### A8. Optimization Modes (Speed / Balanced / Quality)

**What**: Different modes with different iteration budgets, tool budgets, and prompts.

**Sources**:
- Vane: Speed (2 iter, 1-2 tools), Balanced (6 iter, 6 tools), Quality (25 iter, 10 tools)
- Scira: 12+ search groups with different tool sets and system prompts per group

**Port**:
```python
MODES = {
    "speed": {"max_rounds": 2, "queries_per_round": 5, "llm_model": "haiku"},
    "balanced": {"max_rounds": 5, "queries_per_round": 15, "llm_model": "sonnet"},
    "quality": {"max_rounds": 15, "queries_per_round": 20, "llm_model": "sonnet"},
}
```

**Why this matters**: Daily discovery uses "speed". Goal research uses "quality". Currently everything uses the same config.

---

### Tier B — Execution Efficiency

#### B1. Async Parallel Platform Search

**What**: `asyncio.gather` with semaphore for concurrent platform queries.

**Sources**:
- LangChain: [`deep_researcher.py` L288-L305](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py#L288-L305)
- ddgs: `ThreadPoolExecutor` with provider-aware batching + early termination
- gpt-researcher: `asyncio.Semaphore(concurrency_limit)` + `asyncio.gather()`

**Port**: 6 platforms × 2s → 2s instead of 12s.

---

#### B2. Timeout + Partial Results

**What**: Per-platform timeout. Continue with whatever results arrived.

**Sources**:
- Swirl: [`swirl/search.py` L201-L224](https://github.com/swirlai/swirl-search/blob/main/swirl/search.py#L201-L224)
- ddgs: `concurrent.futures.wait(timeout=self._timeout, return_when="FIRST_EXCEPTION")`

---

#### B3. Parallel URL Summarization

**What**: Summarize multiple URLs concurrently with lighter model.

**Sources**:
- LangChain: [`utils.py` L100-L110](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/utils.py#L100-L110) — parallel summarization with 60s timeout
- gpt-researcher: `asyncio.gather(*tasks)` for parallel scraping + compression

---

#### B4. Multi-Engine Search Fallback Chain

**What**: If primary search engine fails, automatically try the next one.

**Sources**:
- OpenManus: `WebSearch` tool tries Google → Baidu → DuckDuckGo → Bing automatically
- ddgs: backend="auto" tries multiple engines, skips failures
- search4all: `BACKEND` env var selects engine at startup

**Port**:
```python
FALLBACK_CHAIN = ["exa", "tavily", "ddgs", "searxng"]

async def search_with_fallback(query: str) -> list:
    for engine in FALLBACK_CHAIN:
        try:
            results = await search(query, engine)
            if results:
                return results
        except Exception as e:
            logger.warning(f"{engine} failed: {e}")
            continue
    return []
```

---

#### B5. Memory-Adaptive Crawling

**What**: Monitor system memory during bulk crawling. Auto-throttle when memory > 90%.

**Sources**:
- crawl4ai: `MemoryAdaptiveDispatcher` — `memory_threshold_percent=90`, recovery at 85%, critical at 95%. `max_session_permit=10` caps concurrent crawls.

**When**: During Armory intake of many repos.

---

### Tier C — Scoring & Ranking Upgrades

#### C1. Composite URL Ranking

**What**: Score URLs by frequency × hostname × path × semantic relevance.

**Sources**:
- Jina: [`src/utils/url-tools.ts` L250-L349](https://github.com/jina-ai/node-DeepResearch/blob/main/src/utils/url-tools.ts#L250-L349) + diversity cap `keepKPerHostname(k=2)`

---

#### C2. Harmonic Position Scoring

**What**: `score = weight / position`. Result at position 1 scores 2×, position 2 scores 1×, etc. Cross-engine: multiply weight by number of engines that found it.

**Sources**:
- SearXNG: `ResultContainer.calculate_score()` in [`searx/results.py`](https://github.com/searxng/searxng/blob/master/searx/results.py)

**Port**:
```python
def harmonic_score(result, engine_weight=1.0, num_engines_found=1):
    weight = engine_weight * num_engines_found
    score = sum(weight / pos for pos in result.positions)
    return score
```

**Why**: Simple, no ML needed, proven in production by SearXNG (millions of users).

---

#### C3. Cross-Platform Score Normalization

**What**: Cosine similarity × field weight × length normalization × rank boost.

**Sources**:
- Swirl: [`swirl/processors/relevancy.py` L437-L452](https://github.com/swirlai/swirl-search/blob/main/swirl/processors/relevancy.py#L437-L452)

---

#### C4. Embedding Similarity Filtering

**What**: After scraping, filter content chunks by embedding similarity to query. Keep only chunks above threshold.

**Sources**:
- gpt-researcher: `EmbeddingsFilter(similarity_threshold=0.35)` with `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)`. Skip compression if total < 8000 chars.
- Jina: `cherryPick()` — [`src/tools/jina-latechunk.ts` L8-L119](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/jina-latechunk.ts#L8-L119) — sliding window + embedding scoring

**Port**:
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

def filter_relevant_chunks(content: str, query: str, embed_fn, threshold=0.35):
    if len(content) < 8000:
        return content  # skip for short content

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_text(content)
    query_emb = embed_fn(query)
    chunk_embs = [embed_fn(c) for c in chunks]

    relevant = [c for c, emb in zip(chunks, chunk_embs)
                if cosine(query_emb, emb) >= threshold]
    return '\n'.join(relevant)
```

---

#### C5. Multi-Dimensional Answer Evaluation

**What**: Classify question first (definitive/freshness/plurality/completeness/attribution), then run type-specific eval.

**Sources**:
- Jina: [`src/tools/evaluator.ts` L560-L671](https://github.com/jina-ai/node-DeepResearch/blob/main/src/tools/evaluator.ts#L560-L671)

---

#### C6. Jina Reranker Post-Aggregation

**What**: After aggregating results from all platforms, rerank the combined context using a dedicated reranker model.

**Sources**:
- openperplex: `jina-reranker-v2-base-multilingual` applied to aggregated context (snippets + chunks + knowledge graph)
- Jina: `jinaRerankFactor = 0.8` (heaviest weight in composite scoring)

**When**: After S4 (content extraction) and before LLM evaluation. Reranking operates on clean extracted content, not raw HTML.

---

### Tier D — Infrastructure & Architecture

#### D1. Classification-Gated Search Types

**What**: Before searching, LLM classifies the query → enables only relevant platform types.

**Sources**:
- Vane: `classify(query) → {skipSearch, academicSearch, discussionSearch, showWeatherWidget, ...}`. Each search action checks classification before executing.
- Scira: `SearchGroupId` routing — different tool sets per mode

**Port**:
```python
async def classify_query(query: str) -> dict:
    return await llm.generate({
        "type": "classification",
        "prompt": f"Classify: {query}",
        "schema": {
            "needs_code_search": bool,    # → github_repos, github_code
            "needs_discussion": bool,     # → reddit, hn
            "needs_academic": bool,       # → arxiv (future)
            "needs_news": bool,           # → twitter, hn
            "needs_general_web": bool,    # → exa, tavily
        }
    })
```

**Why**: Don't search Reddit for "typescript generics" (code question). Don't search GitHub for "AI industry news" (discussion question).

---

#### D2. Review-Revision Loop for Reports

**What**: After generating a research report, a reviewer agent evaluates it. If rejected, a reviser agent fixes issues. Loop until approved.

**Sources**:
- gpt-researcher: `ReviewerAgent` → `ReviserAgent` → back to `ReviewerAgent` until approved. LangGraph conditional edges.

**When**: For goal_bundle_loop final synthesis, not daily discovery.

---

#### D3. SERP Clustering

**What**: Cluster search results by semantic similarity. Each cluster generates an insight.

**Sources**:
- Jina: embedding-based clustering inline during research

---

#### D4. Provider-Aware Dedup

**What**: Skip engines backed by the same provider. DuckDuckGo = Bing underneath.

**Sources**:
- ddgs: Each engine has a `provider` field. `if engine.provider in seen_providers: skip`.

**Port**: In `source_capability.py`, add `provider` field:
```json
{"name": "ddgs", "provider": "bing"},
{"name": "bing_api", "provider": "bing"},  // same provider = skip one
{"name": "exa", "provider": "exa"}
```

---

## What NOT to Copy

| Technique | Repo | Why Skip |
|-----------|------|----------|
| LangGraph state machine | LangChain | Framework dependency, autosearch's functions are simpler |
| Celery task queue | Swirl | Single-machine CLI, asyncio is enough |
| Django ORM / REST | Swirl | JSONL is better for autosearch |
| Streaming UI | Fireplexity, Lepton, Scira | Batch search, not real-time |
| Playwright visual context | OpenManus | Not doing browser automation |
| MCP dynamic tools | OpenManus | autosearch has fixed tool set |
| Redis resumable streams | Scira | No persistent server |
| Frontend citation rendering | All | No frontend |
| Docker/deployment | All | Local-only tool |

---

## Execution Roadmap

### Phase 1: Search Quality (S-tier, independent changes)

```
S1 Query dedup      → new query_dedup.py + engine.py
S2 URL dedup        → engine.py (add seen_urls set)
S3 Query transform  → new config/query_transforms.json + engine.py
S4 Content extract  → evidence/models.py (replace fit_markdown)
S5 Info-density     → engine.py (modify eval prompt)
S6 Engine health    → engine.py + project_experience.py
```

All 6 are independent. Can do in any order. Each verifiable by running one daily search and comparing output.

### Phase 2: Research Depth (A-tier, goal_bundle_loop rewrite)

```
A1 Gap queue        ─┐
A4 Token budget      │
A5 Action disabling  ├→ goal_bundle_loop.py rewrite
A6 Reasoning tool    │
A7 Diary context     │
A8 Optimization modes┘

A2 Recursive search → new deep_search.py (alternative to A1 for specific use cases)
A3 DAG decomposition → future, for complex multi-faceted goals
```

A1+A4+A5+A6+A7+A8 form a coherent rewrite of goal_bundle_loop. A2 and A3 are alternatives for different use cases.

### Phase 3: Execution Efficiency (B-tier, engine.py async migration)

```
B1 Async parallel   ─┐
B2 Timeout+partial   ├→ engine.py sync→async migration
B3 Parallel summarize┘
B4 Fallback chain   → engine.py (add fallback logic per platform)
B5 Memory-adaptive  → acquisition/ (for bulk intake only)
```

B1+B2+B3 require converting engine.py from sync to async. B4 is independent.

### Phase 4: Scoring (C-tier)

```
C1 Composite URL rank → new url_ranking.py
C2 Harmonic position  → engine.py scoring (simple, can do early)
C3 Cross-platform norm → engine.py scoring
C4 Embedding filter    → evidence/models.py
C5 Multi-dim eval      → new evaluator.py
C6 Jina reranker       → engine.py post-aggregation
```

C2 is trivially simple (one formula) and could be done in Phase 1.

### Phase 5: Architecture (D-tier, when ready)

```
D1 Classification gating → engine.py (pre-search LLM call)
D2 Review-revision loop  → goal_bundle_loop.py
D3 SERP clustering       → new clustering.py
D4 Provider-aware dedup  → source_capability.py
```

---

## Quick Wins (< 30 lines of code each)

If you want to start small, these take minutes:

1. **S2 URL dedup**: Add `seen_urls: set` to SearchEngine, filter before eval. ~10 lines.
2. **C2 Harmonic scoring**: `score = sum(weight / pos for pos in positions)`. ~5 lines.
3. **S5 Info-density prompt**: Add 3 sentences to eval prompt. ~0 lines of code, just prompt text.
4. **D4 Provider-aware dedup**: Add `provider` field to `sources/catalog.json`. ~15 lines.
5. **S6 Engine health**: Add error counter per platform, skip if 3+ consecutive errors. ~20 lines.

---

## Technique Origin Map

Shows which repo contributed each technique. **Bold** = primary source, regular = also implements.

| # | Technique | Jina | dzhng | Swirl | LangChain | Fire | SearXNG | GPT-R | Mind | Vane | Scira | crawl4ai | ddgs | Lepton | s4a | oPplx | Manus |
|---|-----------|------|-------|-------|-----------|------|---------|-------|------|------|-------|---------|------|--------|-----|-------|-------|
| S1 | Query dedup | **✓** | | | | | | | | | | | ✓ | | | | |
| S2 | URL dedup | | | **✓** | ✓ | | | | | | ✓ | | | | | | |
| S3 | Query transform | | | **✓** | | | ✓ | | | | | | | | | | |
| S4 | Content extract | | | | | **✓** | | | | | | ✓ | | | | ✓ | |
| S5 | Info-density | | **✓** | | | | | ✓ | | | | | | | | | |
| S6 | Engine health | | | | | | **✓** | | | | | | ✓ | | | | |
| A1 | Gap queue | **✓** | | | | | | | | | | | | | | | |
| A2 | Recursive search | | **✓** | | | | | | | | | | | | | | |
| A3 | DAG decomposition | | | | | | | | **✓** | | | | | | | | |
| A4 | Token budget | **✓** | | | | | | | | | | | | | | | |
| A5 | Action disabling | **✓** | | | | | | | | ✓ | | | | | | | |
| A6 | Reasoning tool | | | | **✓** | | | | | **✓** | | | | | | | ✓ |
| A7 | Diary context | **✓** | | | | | | | | | | | | | | | |
| A8 | Opt modes | | | | | | | | | **✓** | ✓ | | | | | | |
| B1 | Async parallel | | ✓ | | **✓** | | | ✓ | | | | | ✓ | | | | |
| B2 | Timeout+partial | | | **✓** | | | | | | | | | ✓ | | | | |
| B3 | Parallel summarize | | | | **✓** | | | ✓ | | | | | | | | | |
| B4 | Fallback chain | | | | | | | | | | | | ✓ | | | | **✓** |
| B5 | Memory-adaptive | | | | | | | | | | | **✓** | | | | | |
| C1 | Composite rank | **✓** | | | | | | | | | | | | | | | |
| C2 | Harmonic score | | | | | | **✓** | | | | | | | | | | |
| C3 | Cross-platform norm | | | **✓** | | | | | | | | | | | | | |
| C4 | Embedding filter | **✓** | | | | | | **✓** | | | | | | | | | |
| C5 | Multi-dim eval | **✓** | | | | | | | | | | | | | | | |
| C6 | Jina reranker | ✓ | | | | | | | | | | | | | | **✓** | |
| D1 | Classification gate | | | | | | | | | **✓** | ✓ | | | | | | |
| D2 | Review-revision | | | | | | | **✓** | | | | | | | | | |
| D3 | SERP clustering | **✓** | | | | | | | | | | | | | | | |
| D4 | Provider dedup | | | | | | | | | | | | **✓** | | | | |

**Top contributors**: Jina (10), Swirl (4), Vane (4), dzhng (3), LangChain (3), SearXNG (2), gpt-researcher (3), ddgs (3)
