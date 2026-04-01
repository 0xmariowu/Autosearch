# AutoSearch v2.2 Skill Gap Analysis

> 1,009 skills from 16 projects → deduplicated into 25 capability clusters → ranked by AutoSearch impact

## Method

1. Collected 1,009 atomic skills from 16 open-source search/research projects
2. Clustered by semantic function into 25 capability groups
3. Compared against AutoSearch v2.2's 29 existing skills
4. Scored impact (1-5) based on: F006 weak dimensions, AVO evolution needs, delivery quality
5. Subtracted what AutoSearch already covers or what Claude Code provides natively

## AutoSearch v2.2 Current Skills (29)

- **Meta (5, immutable)**: create-skill, observe-user, extract-knowledge, interact-user, discover-environment
- **Platform (14)**: search-ddgs, search-exa, search-github-{repos,issues,code}, search-hackernews, search-hn-exa, search-huggingface, search-reddit, search-reddit-exa, search-searxng, search-tavily, search-twitter-{exa,xreach}
- **Core (10)**: llm-evaluate, use-own-knowledge, synthesize-knowledge, gene-query, goal-loop, anti-cheat, outcome-tracker, provider-health, fetch-webpage, research-mode

---

## Tier 1: Critical Gaps (Impact 5/5)

These directly address F006 failures or enable AVO evolution.

### 1. Result Normalization & Deduplication
**What it is**: Standardize result format across platforms, merge duplicates, normalize URLs.
**F006 problem**: Results from different platforms had inconsistent formats. No cross-platform dedup.
**Who has it**: searxng (normalize_result_fields, merge_duplicate_results, filter_result_urls), ddgs (normalize_result_fields, aggregate_results), swirl-search (map_provider_fields, auto_map_payload_fields, dedupe_cross_provider_results), node-deepresearch (normalize_urls, normalize_hostnames)
**AutoSearch has**: Nothing. Each platform skill outputs its own format.
**Recommendation**: New skill `normalize-results.md` — define a canonical evidence schema, normalize all platform outputs into it, deduplicate by URL + title similarity.
**Impact**: 5/5 — fixes diversity scoring (judge counts platforms by `source` field) and enables cross-platform dedup.

### 2. Date/Freshness Extraction
**What it is**: Extract publication/update dates from results, normalize to ISO 8601.
**F006 problem**: freshness scored 0.076 because 92.4% of results lacked date metadata.
**Who has it**: swirl-search (extract_date_fields), ddgs (normalize_news_dates), node-deepresearch (guess_content_datetime)
**AutoSearch has**: Just added instructions to ddgs and github-repos skills (F006 fix), but no dedicated capability.
**Recommendation**: New skill `extract-dates.md` — post-processing step that extracts dates from title patterns ("2025-*"), snippet text, GitHub API fields, arXiv IDs, HTTP headers.
**Impact**: 5/5 — directly fixes the 0.076 freshness score. Estimated improvement: freshness 0.076 → ~0.6.

### 3. Content Extraction (Beyond Basic Fetch)
**What it is**: Fetch full page content, convert to clean text/markdown, handle anti-bot, PDF, etc.
**F006 problem**: fetch-webpage.md is too basic. No structured extraction, no fallback, no anti-bot.
**Who has it**: crawl4ai (35 skills! — run_single_crawl, sanitize_dom_content, generate_markdown, extract_pdf_document, detect_antibot_block, fallback_fetch), gpt-researcher (scrape_html_page, extract_page_text, clean_html_content, scrape_pdf_document), node-deepresearch (fetch_reader_content, screen_blocked_content)
**AutoSearch has**: fetch-webpage.md (1 basic skill)
**Recommendation**: Expand fetch-webpage.md into a richer skill with: markdown conversion, blocked content detection, PDF handling, fallback strategies. Don't need all 35 crawl4ai skills — pick the 5 most impactful.
**Impact**: 5/5 — full content access enables better LLM evaluation (snippets are often truncated/misleading).

### 4. Context Assembly & Token Management
**What it is**: Merge evidence from multiple sources into a coherent context window, manage token budget.
**F006 problem**: No explicit context management. 105 results might overflow or be poorly structured for synthesis.
**Who has it**: gpt-researcher (compress_query_context, trim_context_word_budget, filter_context_by_embeddings), open_deep_research (compress_research_trace, trim_context_on_token_limit), openperplex (merge_search_snippets, semantic_chunk_text, concatenate_contexts), deep-research (trim_context, split_text)
**AutoSearch has**: Nothing explicit. Relies on Claude's context window.
**Recommendation**: New skill `assemble-context.md` — before synthesis, organize evidence by relevance, deduplicate content, trim to token budget, preserve source attribution.
**Impact**: 5/5 — directly improves synthesis quality and prevents context overflow on large result sets.

---

## Tier 2: High Impact (Impact 4/5)

Would significantly improve delivery quality or search effectiveness.

### 5. Citation & Reference Management
**What it is**: Link claims in synthesis to source evidence, produce footnotes/inline citations.
**Who has it**: node-deepresearch (align_answer_citations, inject_footnote_citations), MindSearch (renumber_citation_refs, merge_graph_references), gpt-researcher (append_reference_links, curate_source_set), Vane (parse_inline_citations), fireplexity (render_citation_markdown, normalize_citation_tokens)
**AutoSearch has**: Nothing. synthesize-knowledge.md doesn't mention citations.
**Recommendation**: Add citation guidance to synthesize-knowledge.md. Every claim in delivery should link to a source from the evidence bundle.
**Impact**: 4/5 — makes delivery verifiable and trustworthy.

### 6. Follow-up Query Generation (From Evidence Gaps)
**What it is**: After evaluating results, generate targeted follow-up queries based on what's MISSING.
**Who has it**: deep-research (formulate_followups, compose_next_query — learnings-as-state pattern), node-deepresearch (decompose_question_gaps, rewrite_search_queries, analyze_failed_steps), gpt-researcher (generate_subqueries, generate_followup_questions)
**AutoSearch has**: llm-evaluate.md generates `next_queries` per batch, goal-loop.md does mutation. Partially covered.
**Recommendation**: Strengthen by adding explicit gap detection: after each round, diff evidence against a rubric to identify structural gaps (missing content types, missing perspectives, missing time periods).
**Impact**: 4/5 — makes the search loop smarter, directly helps AVO evolution.

### 7. Semantic Reranking
**What it is**: Use embeddings or LLM to rerank results by true relevance, not just keyword match.
**Who has it**: openperplex (rerank_contexts_jina, rerank_contexts_cohere), node-deepresearch (rerank_documents, compute_cosine_similarity, fallback_jaccard_ranking), gpt-researcher (filter_context_by_embeddings, retrieve_vector_matches), open_deep_research (rerank_source_chunks)
**AutoSearch has**: llm-evaluate.md does binary relevant/not-relevant. No embedding-based ranking.
**Recommendation**: New skill `rerank-evidence.md` — after LLM evaluation, rank results by embedding similarity to the task spec. Useful for selecting top-K evidence for synthesis.
**Impact**: 4/5 — improves relevance beyond binary filter, helps synthesis focus on best evidence.

### 8. Multi-Hop Query Decomposition
**What it is**: Break complex research questions into sub-questions, search each independently, merge.
**Who has it**: MindSearch (generate_graph_code, add_subquery_node — graph-based decomposition), gpt-researcher (plan_research_outline, generate_subtopics), open_deep_research (plan_report_sections, delegate_research_topic), node-deepresearch (decompose_question_gaps)
**AutoSearch has**: gene-query.md generates diverse queries but doesn't decompose the QUESTION itself.
**Recommendation**: New skill `decompose-task.md` — for complex research tasks, break into 3-5 sub-questions, search each, then synthesize across sub-results.
**Impact**: 4/5 — would significantly improve coverage on complex topics. Benchmark had 12 paper sub-categories because native Claude naturally decomposed.

### 9. Deep Crawling / Link Following
**What it is**: Follow links from discovered pages to find connected resources.
**Who has it**: crawl4ai (traverse_breadth_first, traverse_depth_first, traverse_best_first, filter_candidate_urls, score_candidate_urls), node-deepresearch (harvest_outlinks, rank_candidate_urls, diversify_hostnames)
**AutoSearch has**: Nothing. Current skills only search, don't follow links.
**Recommendation**: New skill `follow-links.md` — from high-value results, extract outlinks, score for relevance, fetch promising ones. Especially useful for awesome-lists and survey papers that link to many resources.
**Impact**: 4/5 — the benchmark found awesome-lists that link to dozens of projects. Following those links is high-yield.

---

## Tier 3: Medium Impact (Impact 3/5)

Useful improvements that enhance robustness and efficiency.

### 10. Caching & Dedup Across Sessions
**Who has it**: crawl4ai (read_write_cache, validate_cache_freshness), search_with_lepton (replay_cached_result), gpt-researcher (cache_mcp_results, reuse_cached_mcp_context)
**AutoSearch has**: patterns.jsonl persists across sessions, but no result caching.
**Recommendation**: Could add result URL dedup against prior sessions' worklog. Low urgency.
**Impact**: 3/5

### 11. Provider-Specific Quality Signals
**Who has it**: searxng (fetch_engine_traits, inject_engine_traits — per-engine quality metadata), swirl-search (score_result_relevancy per provider)
**AutoSearch has**: provider-health.md tracks availability but not quality signals.
**Recommendation**: Track per-platform hit rates in outcome-tracker.md. Which platforms produce the most relevant results for which topic types?
**Impact**: 3/5

### 12. Parallel Search Execution
**Who has it**: MindSearch (schedule_parallel_search_nodes), open_deep_research (spawn_parallel_researchers, cap_parallel_research_units), gpt-researcher (generate_parallel_images, bound_concurrent_queries)
**AutoSearch has**: Sequential search. F006 latency was 180s (0/5 on latency dimension).
**Recommendation**: Parallelize platform searches where tools allow. Mainly a protocol-level concern rather than a skill.
**Impact**: 3/5 — would improve latency score but Claude Code tool calls are somewhat sequential.

### 13. Answer Quality Evaluation
**Who has it**: node-deepresearch (evaluate_answer_definitiveness, evaluate_answer_freshness, evaluate_answer_plurality, evaluate_answer_completeness, enforce_strict_answer_review), open_deep_research (score_overall_quality, score_relevance, score_structure, score_correctness, score_groundedness)
**AutoSearch has**: judge.py scores the evidence bundle, but nothing evaluates the DELIVERY quality.
**Recommendation**: Add post-synthesis self-evaluation. After writing delivery, score it against the benchmark dimensions: coverage, depth, framework quality, actionability.
**Impact**: 3/5

### 14. Research Planning / Scope Setting
**Who has it**: open_deep_research (clarify_scope, derive_research_brief, verify_scope_readiness), gpt-researcher (plan_research_outline), scira (plan_extreme_research)
**AutoSearch has**: research-mode.md (speed/balanced/deep), goal-loop.md (rubric-based). Partially covered.
**Recommendation**: Strengthen research-mode.md with explicit scope definition: what's in scope, what's out, what does "done" look like.
**Impact**: 3/5

### 15. Image/Media Search
**Who has it**: ddgs (search_images, search_videos), scira (search_youtube, search_spotify), Vane (search_images, search_videos), fireplexity (transform_image_results)
**AutoSearch has**: Nothing. Text-only.
**Recommendation**: Low priority unless the research task specifically needs media.
**Impact**: 2/5

---

## Tier 4: Low Impact for AutoSearch (Impact 1-2/5)

Present across many projects but not critical for AutoSearch's mission.

### 16. Streaming / Progress UI (2/5)
Many projects have elaborate streaming. AutoSearch runs in Claude Code CLI — not needed.

### 17. Chat / Session Management (1/5)
Chat history, session persistence. AutoSearch is task-based, not conversational.

### 18. Authentication / OAuth (1/5)
MCP auth, Microsoft OAuth, bearer tokens. Claude Code handles auth natively.

### 19. Frontend Rendering (1/5)
React components, citation popovers, chart widgets. AutoSearch delivers markdown, not UI.

### 20. Docker / Deployment (1/5)
Container management, health checks. Not relevant to skill-based agent.

### 21. Multi-Agent Orchestration (2/5)
Graph-based planning, parallel agents. AVO is intentionally single-agent by design.

### 22. Document Upload / RAG (2/5)
File upload, PDF extraction, embedding search. Could be useful but not core to web research.

### 23. Sandbox Execution (1/5)
Code sandbox, browser automation. AutoSearch doesn't execute code.

### 24. Widget / Rich Data (2/5)
Weather, stocks, currency, flight tracking. Domain-specific, not general research.

### 25. Localization / i18n (1/5)
Language detection, translation. AutoSearch outputs in task language naturally.

---

## Priority Implementation Order

Based on impact score and implementation complexity:

| Priority | Capability | New/Expand | Estimated Complexity | Addresses |
|----------|-----------|------------|---------------------|-----------|
| **P0** | Result normalization & dedup | New skill | Medium | diversity score, data quality |
| **P0** | Date/freshness extraction | New skill | Low | freshness 0.076 → ~0.6 |
| **P0** | Context assembly & token mgmt | New skill | Medium | synthesis quality |
| **P1** | Content extraction (rich fetch) | Expand fetch-webpage.md | Medium | evidence depth |
| **P1** | Citation management | Expand synthesize-knowledge.md | Low | delivery trust |
| **P1** | Multi-hop decomposition | New skill | Medium | coverage on complex topics |
| **P2** | Semantic reranking | New skill | Medium | relevance refinement |
| **P2** | Follow-up from gaps | Strengthen llm-evaluate.md | Low | search loop quality |
| **P2** | Deep crawling / link following | New skill | Medium | yield from awesome-lists |
| **P3** | Answer quality eval | New skill | Low | delivery self-check |
| **P3** | Parallel search | Protocol concern | Low | latency score |
| **P3** | Provider quality signals | Expand outcome-tracker.md | Low | platform selection |

## Cross-Project Unique Patterns Worth Adopting

These aren't individual skills but architectural patterns discovered across the 16 projects:

1. **Learnings-as-state recursion** (deep-research) — each round's learnings become the next round's input. AutoSearch's patterns.jsonl does this across sessions; should also do it within sessions.

2. **Graph-based query planning** (MindSearch) — emit executable code that builds a search graph. Overkill for AutoSearch but the CONCEPT of treating queries as a graph (with dependencies) is valuable.

3. **Block-based delivery** (Vane) — deliver results as typed blocks (sources, analysis, synthesis, citations) not one monolithic document. Could improve AutoSearch delivery structure.

4. **Evaluator rejection loop** (node-deepresearch) — agent must survive rejection from evaluator before finalizing. AutoSearch has anti-cheat.md but it's post-hoc. Making it a gate before delivery is stronger.

5. **Pro-mode behavior switching** (openperplex) — one flag changes the entire pipeline depth. AutoSearch has research-mode.md which is similar. Could be strengthened.

---

## Summary

- **1,009 skills** → **25 clusters** after deduplication
- **4 critical gaps** (P0): normalization, dates, context management, content extraction
- **5 high-impact gaps** (P1-P2): citations, decomposition, reranking, link following, gap-based queries
- **~16 clusters** already covered by AutoSearch or irrelevant to its mission
- **5 architectural patterns** worth adopting from the research

Implementing P0 alone would raise the estimated F006 score from 0.676 to ~0.85.
Implementing P0+P1 would make AutoSearch competitive with native Claude on most dimensions.
