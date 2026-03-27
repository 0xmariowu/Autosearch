# Deep Research Tool Patterns Analysis

> Research date: 2026-03-27
> Purpose: Extract concrete architectural patterns from 6 deep research tools for AutoSearch integration.

---

## 1. GPT-Researcher (assafelovic/gpt-researcher)

**The most mature and feature-complete deep research tool. Python, LangGraph-based.**

### Architecture
- **Two-tier system**: Standard single-agent mode + multi-agent mode (LangGraph StateGraph)
- **Standard flow**: Query -> Agent Selection (LLM picks role) -> ResearchConductor -> SubQuery decomposition -> Parallel processing -> Context compression -> Report generation
- **Multi-agent flow**: ChiefEditorAgent orchestrates 8 specialized agents: Human, Chief Editor, Researcher, Editor, Reviewer, Revisor, Writer, Publisher

### Query Generation
- `plan_research()` does initial web search to understand the topic, then calls `plan_research_outline()` LLM to generate 3-5 sub-queries
- Sub-queries processed in parallel via `asyncio.gather()`
- Deep Research mode: generates multiple search queries at each depth level, recursively spawns new `GPTResearcher` instances per sub-query

### Tool Orchestration
- **Retriever factory pattern**: `get_retriever(name)` maps string names to retriever classes via match/case
- Registration: add case to factory + import in `__init__.py`
- Selection priority: request header `retrievers` > header `retriever` > `cfg.retrievers` > `cfg.retriever` > default
- Supports: Tavily, Google, DuckDuckGo, Bing, arXiv, Semantic Scholar, CustomRetriever, MCPRetriever

### Progress Tracking / Completion
- **Standard mode**: No adaptive completion. Runs all sub-queries to completion.
- **Deep Research mode**: Fixed parameters control termination: `deep_research_breadth` (default 4), `deep_research_depth` (default 2), `deep_research_concurrency` (default 2)
- Proposed but not implemented: LLM-based quality evaluator that assesses coverage/depth/relevance/accuracy

### Result Aggregation
- Each sub-query: MCP retrieval + Web search + URL scraping + **Similarity search via embeddings** (compression step)
- `ContextManager.get_similar_content_by_query()` uses embeddings to filter only relevant passages from scraped content
- All sub-contexts concatenated into final context string

### Scoring/Ranking
- **SourceCurator** class: LLM evaluates and ranks sources by relevance, credibility, reliability
- Uses `create_chat_completion` with curate_sources prompt, returns JSON-ranked list
- Falls back to original sources on error

### Self-Improvement
- None. No learning from past searches.

### Autonomous Continuation
- Deep Research mode runs autonomously with fixed depth/breadth
- `asyncio.Semaphore` limits concurrent operations
- MCP strategy: "fast" (once, cached), "deep" (per sub-query), "disabled"

### Patterns to Steal
1. **Retriever factory with priority cascade** (header > config > default)
2. **Embedding-based context compression** after scraping (critical for token management)
3. **Multi-agent review-revision loop**: Reviewer returns `None` to accept, feedback to revise. Loop until accepted.
4. **Two-state LangGraph pattern**: `ResearchState` (global) + `DraftState` (per-subtopic) with parallel section processing
5. **Source curator as separate LLM call** post-retrieval

---

## 2. MindSearch (InternLM/MindSearch)

**Most innovative architecture: LLM generates Python code to build a search DAG in real-time.**

### Architecture
- `MindSearchAgent` with `WebSearchGraph` - the LLM literally writes Python code to construct a directed graph of search operations
- `GRAPH_PROMPT` provides the `WebSearchGraph` API documentation to the LLM
- `ExecutionAction` class executes the generated Python code
- `InterpreterParser` interprets LLM output as executable Python

### Query Generation
- LLM receives the question + graph API docs and generates code like:
  ```python
  graph.add_root_node("main question", "root")
  graph.add_node("sub1", "specific sub-question 1")
  graph.add_node("sub2", "specific sub-question 2")
  graph.add_edge("root", "sub1")
  graph.add_edge("root", "sub2")
  ```
- Sub-queries are generated organically by the LLM's understanding of the problem
- The LLM can iteratively add more nodes based on search results from previous nodes

### Tool Orchestration
- `WebSearchGraph.add_node()` triggers search automatically when called
- `WebBrowser` tool configured with search engine (BingSearch, DuckDuckGoSearch)
- `searcher_cfg` dictionary contains LLM config, plugins, and prompt templates

### Progress Tracking / Completion
- `max_turn` parameter limits iterations
- `finish_condition` checks if `add_response_node()` was called by the LLM
- The LLM decides when enough information has been gathered by calling `graph.add_response_node()`

### Result Aggregation
- `_generate_references_from_graph` iterates non-root/non-response nodes
- Extracts `ref2url` mapping from agent memory for each search node
- Compiles references into formatted string + dictionary

### Scoring/Ranking
- No explicit scoring. LLM implicitly decides relevance during graph construction.

### Self-Improvement
- None.

### Autonomous Continuation
- Iterative loop with LLM control. Runs until `add_response_node()` or `max_turn`.
- SSE streaming for real-time progress to frontend.

### Patterns to Steal
1. **Code-generation-as-planning**: LLM writes executable code to build a search graph. Extremely flexible.
2. **WebSearchGraph as explicit state machine**: nodes = questions, edges = dependencies, methods = actions
3. **LLM-controlled termination**: The agent itself decides when to stop by calling a specific method
4. **`searcher_input_template`**: Separates "current problem" from "final problem" - the searcher always knows both the immediate sub-question AND the original question

---

## 3. Deep-Research (dzhng/deep-research)

**Elegant recursive design. TypeScript, Firecrawl-powered. Most copied pattern in the space.**

### Architecture
- Single recursive function `deepResearch(query, breadth, depth, learnings, visitedUrls)`
- Uses Firecrawl for search + scraping, Vercel AI SDK for LLM with Zod structured output
- Three-stage pipeline per iteration: generateSerpQueries -> processSerpResult -> recurse

### Query Generation
- `generateSerpQueries(query, learnings, numQueries)`: LLM generates array of `{query, researchGoal}` objects
- Uses accumulated `learnings` from prior iterations to evolve queries
- On recursion: `nextQuery` = previous research goal + follow-up directions from `processSerpResult`

### Tool Orchestration
- Single tool: Firecrawl (`FirecrawlApp.search()`)
- `p-limit` for concurrency control on API calls
- No tool registry pattern - hardcoded to Firecrawl

### Progress Tracking / Completion
- **Fixed depth/breadth parameters** - no adaptive stopping
- `depth <= 0` = base case (stop recursing)
- Breadth halved at each level: `Math.ceil(breadth / 2)` to prevent exponential growth
- Total work = breadth * (breadth/2) * (breadth/4) * ... for depth levels

### Result Aggregation
- `Promise.all` for concurrent query execution
- All `learnings` arrays flattened across branches
- `visitedUrls` deduplicated via `new Set()`
- Learnings are "concise, information-dense strings" extracted by LLM

### Scoring/Ranking
- None explicitly. Relevance determined by LLM during `processSerpResult`.

### Self-Improvement
- **Implicit via learnings accumulation**: Each recursive call receives all prior learnings, enabling the LLM to avoid redundant searches and build on previous findings
- No persistent learning across sessions

### Autonomous Continuation
- Fully autonomous once started. Fixed depth/breadth means predictable runtime.
- Optional `onProgress` callback for status updates

### Patterns to Steal
1. **Learnings-as-state pattern**: Extract concise learnings from each search, pass forward. Simple and effective.
2. **Breadth halving**: `Math.ceil(breadth / 2)` at each depth level prevents exponential explosion while maintaining depth
3. **Zod schema for every LLM call**: `generateSerpQueries` returns `{queries: [{query, researchGoal}]}`, `processSerpResult` returns `{learnings: string[], followUpQuestions: string[]}`, etc. Structured output everywhere.
4. **`trimPrompt` utility**: Uses `RecursiveCharacterTextSplitter` to manage token limits
5. **Research goal threading**: Each query carries a `researchGoal` that explains WHY this search is happening, not just WHAT to search

---

## 4. Node-DeepResearch (jina-ai/node-deepresearch)

**Most sophisticated evaluation system. Token-budget-based termination. Best scoring/ranking.**

### Architecture
- Single-agent loop: Search -> Read -> Reason -> repeat until budget exceeded
- Actions: `search`, `visit`, `reflect`, `answer`, `coding`
- Gap-tracking queue: maintains list of unanswered sub-questions
- "Beast Mode": when token budget exceeded, force-generate final answer

### Query Generation
- **`query-rewriter.ts`**: Extraordinary prompt engineering. Uses 7 "cognitive personas":
  1. Expert Skeptic (edge cases, counter-evidence)
  2. Detail Analyst (precise specs, reference data)
  3. Historical Researcher (evolution, legacy issues)
  4. Comparative Thinker (alternatives, trade-offs)
  5. Temporal Context (current date-aware recency)
  6. Globalizer (search in most authoritative language for the domain - German for BMW, Japanese for anime)
  7. Reality-Hater-Skepticalist (contradicting evidence, "why is X false?")
- Also includes "intent mining" with 7 layers: Surface, Practical, Emotional, Social, Identity, Taboo, Shadow intent

### Tool Orchestration
- Tools are individual files in `src/tools/`: `jina-search.ts`, `brave-search.ts`, `serper-search.ts`, `read.ts`, `code-sandbox.ts`, `embeddings.ts`, `jina-rerank.ts`, `jina-dedup.ts`, `jina-latechunk.ts`, `cosine.ts`
- Search provider configurable: Jina, Brave, Serper
- **`build-ref.ts`**: Reference building with URL scoring
- **`reducer.ts`**: Content reduction/compression

### Progress Tracking / Completion
- **Token budget-based**: Runs until token budget exceeded, then enters "Beast Mode" for final answer
- Gap queue: `reflect` action generates sub-questions, added to gap queue with dedup
- **Disabling mechanism**: If an action type yields no new results, it's temporarily disabled for next step (prevents loops)

### Result Aggregation
- `KnowledgeItem` objects accumulate: `{question, answer, references, type: 'qa'|'side-info'|'chat-history'|'url'|'coding'}`
- Knowledge items passed to evaluator as context
- Intermediate answers stored as knowledge for later use

### Scoring/Ranking
- **Multi-dimensional evaluation system** (the best in any of these repos):
  - `evaluateQuestion()` first classifies what checks are needed: `definitive`, `freshness`, `plurality`, `completeness`
  - `evaluateAnswer()` then runs applicable checks sequentially, failing fast on first failure
  - **Definitiveness check**: Is the answer clear and confident? Rejects "I don't know", "might be", hedging
  - **Freshness check**: Massive table mapping question types to max-age-days (Financial=0.1 days, Breaking News=1, Software Info=30, Historical=365, Factual=infinity)
  - **Plurality check**: Does the answer provide the right number of items? (Table mapping "few"=2-4, "several"=3-7, "comprehensive"=10+, etc.)
  - **Completeness check**: Does the answer cover all explicitly mentioned aspects?
  - **Strict mode**: "Ruthless and picky" evaluator that argues AGAINST the answer first, then FOR, then synthesizes improvement plan
- `BoostedSearchSnippet` type: `freqBoost`, `hostnameBoost`, `pathBoost`, `jinaRerankBoost`, `finalScore`

### Self-Improvement
- **Error analysis**: `error-analyzer.ts` performs `{recap, blame, improvement}` analysis on failed attempts
- Bad answers stored with context, preventing repeated failures
- No cross-session learning

### Autonomous Continuation
- Fully autonomous via token budget. Can run 2-42+ steps.
- `STEP_SLEEP` config for rate limiting between steps
- "Beast Mode" guarantees an answer even when budget runs out

### Patterns to Steal
1. **Multi-dimensional answer evaluation** (definitiveness + freshness + plurality + completeness + strict)
2. **Freshness table**: Concrete max-age-days for every question category (steal the entire table)
3. **7-persona query expansion**: Generate 7 diverse queries from different cognitive angles per search
4. **Token budget as termination mechanism** instead of fixed depth/breadth
5. **Gap queue with dedup**: Maintain explicit list of unanswered questions, add via `reflect` action
6. **Action disabling on empty results**: Temporarily disable search/visit/reflect if they produce nothing
7. **Beast Mode**: When resources exhausted, force-synthesize best-effort answer from accumulated knowledge
8. **Intent mining layers**: Surface -> Practical -> Emotional -> Social -> Identity -> Taboo -> Shadow
9. **BoostedSearchSnippet scoring**: Multi-factor URL ranking (frequency, hostname authority, path structure, rerank score)
10. **`research-planner.ts`**: Decomposes into N orthogonal sub-problems with explicit overlap validation (<20% overlap target)

---

## 5. Open Deep Research (langchain-ai/open_deep_research)

**Best supervisor-worker pattern. LangGraph nested StateGraphs. Formal tool schemas.**

### Architecture
- Three nested LangGraph `StateGraph` instances:
  1. `deep_researcher` (top-level): clarify -> brief -> supervisor -> final report
  2. `supervisor_subgraph`: supervisor <-> supervisor_tools loop
  3. `researcher_subgraph`: researcher <-> researcher_tools -> compress_research
- Pydantic models for all state: `AgentState`, `SupervisorState`, `ResearcherState`

### Query Generation
- Supervisor uses `think_tool` (no I/O, just reflection) to plan strategy before each `ConductResearch` call
- `ConductResearch` tool schema: `{research_topic: str}` - topic must be "at least a paragraph"
- Researcher generates search queries based on assigned topic + `research_system_prompt`
- Iterative refinement: researcher uses `think_tool` after each search to reflect and plan next query

### Tool Orchestration
- **Supervisor tools**: `ConductResearch`, `ResearchComplete`, `think_tool`
- **Researcher tools**: search tool (tavily_search, web_search), `think_tool`, `ResearchComplete`, MCP tools
- `get_all_tools(config)` assembles tool set based on configuration
- Parallel `ConductResearch` dispatch: supervisor can spawn multiple researchers simultaneously
- `max_concurrent_research_units` config limits parallelism

### Progress Tracking / Completion
- **Two-level termination**:
  - Supervisor: `ResearchComplete` tool call OR `max_researcher_iterations` exceeded OR no tool calls
  - Researcher: `ResearchComplete` tool call OR `max_react_tool_calls` exceeded OR no tool calls
- `custom override_reducer` for state management (append or replace lists)

### Result Aggregation
- `compress_research` node: Uses `compression_model` to distill researcher findings into clean, cited summary
- Retry logic: up to 3 attempts, removes older messages on token limit errors
- `raw_notes`: concatenation of all tool and AI messages from researcher
- Final report synthesizes all `notes` from all researchers

### Scoring/Ranking
- External evaluation only: Deep Research Bench
- No internal quality scoring during research

### Self-Improvement
- `think_tool` provides structured reflection points, but no persistent learning

### Autonomous Continuation
- Fully autonomous within iteration limits
- `allow_clarification` config: can optionally ask user one clarifying question at start

### Patterns to Steal
1. **Nested StateGraph pattern**: top-level -> supervisor -> researcher. Clean separation of concerns.
2. **`think_tool` pattern**: A tool that does nothing but record reflection. Forces the LLM to think before acting.
3. **`ConductResearch` as a tool call**: Supervisor spawns researchers via tool calls, not direct function calls. Makes the delegation explicit and traceable.
4. **`compress_research` with retry**: Compression model + 3-attempt retry + message pruning on token errors
5. **`override_reducer`**: Custom reducer that can either append to or replace state lists
6. **Clarification step**: Optional user interaction before research begins
7. **Separate models per stage**: `research_model`, `summarization_model`, `compression_model`, `final_report_model`

---

## 6. Fireplexity (firecrawl/fireplexity)

**Simplest architecture. Good as baseline reference for single-query search-and-answer.**

### Architecture
- Next.js app with single API route: `POST /api/fireplexity/search`
- Flow: Query -> Firecrawl v2 search (web + news + images) -> selectRelevantContent -> Groq LLM -> streaming response
- No multi-step research. Single search, single answer.

### Query Generation
- None. Passes user query directly to Firecrawl.
- Follow-up questions generated via separate `generateText` call after main answer.

### Tool Orchestration
- Single tool: Firecrawl v2 API (`https://api.firecrawl.dev/v2/search`)
- Searches three source types simultaneously: web, news, images
- Scraping options: `onlyMainContent: true`, 24-hour cache

### Progress Tracking / Completion
- Single-shot. No iteration.

### Result Aggregation
- Three arrays: web sources (URL, title, description, markdown, favicon), news results (date, source, image), image results (thumbnail, dimensions)
- `selectRelevantContent`: Extracts up to 2000 chars of relevant content from each source's markdown
- Formats with source titles and URLs for LLM context

### Scoring/Ranking
- Preserves Firecrawl's result order. Inline citations `[1], [2]` by position.

### Self-Improvement
- None.

### Autonomous Continuation
- Not applicable (single-shot).

### Patterns to Steal
1. **`selectRelevantContent` utility**: Simple 2000-char extraction per source. Good baseline.
2. **Three-source-type parallel search**: web + news + images in single Firecrawl call
3. **Streaming architecture**: `createUIMessageStream` with transient (status) + persistent (sources) data parts
4. **Error code mapping**: Friendly messages for 401/402/429/504 Firecrawl errors

---

## Cross-Repo Synthesis: Best Pattern for Each Capability

### 1. Architecture Pattern
**Winner: LangChain's nested StateGraph (open_deep_research)**

Three-level hierarchy: Orchestrator -> Supervisor -> Researcher. Each level is its own StateGraph with its own state model. Clean, testable, extensible. GPT-Researcher's multi-agent is similar but less cleanly separated.

**For AutoSearch**: Adopt the nested graph pattern but with our own state types. The supervisor dispatches `ConductResearch` tool calls that spawn researcher subgraphs.

### 2. Query Generation
**Winner: Jina's 7-persona cognitive expansion (node-deepresearch)**

Nobody else comes close. The 7 cognitive personas (Skeptic, Analyst, Historian, Comparator, Temporal, Globalizer, Contrarian) generate genuinely diverse search queries. The intent mining layers add another dimension. dzhng's research-goal threading is a good complement.

**For AutoSearch**: Steal the 7-persona pattern wholesale. Also steal dzhng's `{query, researchGoal}` pairing so every search carries intent context.

### 3. Tool Orchestration
**Winner: GPT-Researcher's retriever factory with priority cascade**

String-name-to-class factory with clear priority chain (header > config > default). Supports multiple retrievers per query. Easy to add new retrievers.

**For AutoSearch**: Implement retriever factory pattern. Register tools by name, select by config with override hierarchy.

### 4. Progress Tracking / Completion
**Winner: Jina's token-budget + gap-queue (node-deepresearch)**

Token budget is the most natural stopping criterion - it maps directly to cost. The gap queue ensures completeness by tracking unanswered sub-questions. The action-disabling mechanism prevents loops. Beast Mode guarantees output.

**Runner-up**: dzhng's breadth-halving is elegant for fixed-budget scenarios.

**For AutoSearch**: Token budget as primary mechanism, gap queue for completeness tracking, Beast Mode for guaranteed output.

### 5. Result Aggregation
**Winner: GPT-Researcher's embedding-based context compression**

Using embeddings to similarity-search the most relevant passages from scraped content is the right approach. LangChain's `compress_research` node (LLM-based compression) is complementary for final synthesis.

**For AutoSearch**: Two-stage: (1) Embedding similarity for initial filtering, (2) LLM compression for final synthesis.

### 6. Scoring/Ranking
**Winner: Jina's multi-dimensional evaluation (node-deepresearch), by a mile**

The only repo with real answer quality evaluation. The freshness table, definitiveness check, plurality check, and completeness check are concrete, implementable, and independently useful. The `BoostedSearchSnippet` multi-factor URL scoring is also unique.

**For AutoSearch**: Steal the entire evaluation framework: question classification -> applicable checks -> sequential eval with fast-fail. Steal the freshness table verbatim. Steal the `BoostedSearchSnippet` scoring factors.

### 7. Self-Improvement
**Winner: None (nobody does this well)**

dzhng has implicit improvement via learnings accumulation within a session. Jina has error analysis. Nobody has cross-session learning. This is the biggest gap in the space.

**For AutoSearch**: This is our opportunity. We already have Armory for knowledge persistence. Concrete approach: save successful search strategies (query patterns that led to high-scored results) keyed by question type. Use them as few-shot examples for future query generation.

### 8. Autonomous Continuation
**Winner: Jina's token-budget approach (node-deepresearch)**

Token budget maps to cost, which is the actual constraint users care about. MindSearch's LLM-controlled termination is second-best (most intelligent but less predictable). dzhng's fixed depth/breadth is simplest.

**For AutoSearch**: Token budget with configurable limits per research type. LLM can request early termination via tool call. Hard ceiling prevents runaway costs.

---

## Priority Implementation Order for AutoSearch

1. **Evaluation framework** (Jina's multi-dimensional checks) - Highest ROI, no existing competitors do this well
2. **7-persona query expansion** (Jina) - Dramatically improves search diversity
3. **Learnings accumulation** (dzhng) + cross-session persistence (our addition) - The differentiator
4. **Nested StateGraph architecture** (LangChain) - Foundation for multi-step research
5. **Token budget termination** (Jina) + breadth halving (dzhng) - Resource management
6. **Embedding-based context compression** (GPT-Researcher) - Token efficiency
7. **Retriever factory** (GPT-Researcher) - Tool extensibility

## Key Quantitative Reference Data

| Repo | Stars | Language | Multi-step | Multi-agent | Eval System | Learning |
|------|-------|----------|------------|-------------|-------------|----------|
| gpt-researcher | 18k+ | Python | Yes (recursive) | Yes (8 agents) | Source curator only | No |
| MindSearch | 5k+ | Python | Yes (DAG) | Yes (planner+searcher) | No | No |
| dzhng/deep-research | 12k+ | TypeScript | Yes (recursive) | No | No | Within-session |
| node-deepresearch | 4k+ | TypeScript | Yes (loop) | No | Yes (5 dimensions) | Error analysis |
| open_deep_research | 3k+ | Python | Yes (nested graphs) | Yes (supervisor+workers) | External bench only | No |
| fireplexity | 1k+ | TypeScript | No (single-shot) | No | No | No |
