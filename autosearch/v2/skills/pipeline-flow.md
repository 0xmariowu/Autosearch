---
name: pipeline-flow
description: "Use at the start of every AutoSearch session to follow the correct 5-phase pipeline. Ensures Claude-first architecture, gap-driven search, and quality delivery."
---

# Purpose

This skill defines the 5-phase pipeline that makes AutoSearch produce results better than native Claude. Follow these phases in order.

# Phase 1: Recall + Plan (Claude's knowledge leads)

1. Run `systematic-recall.md` — 9-dimension knowledge scan with confidence levels
2. Load `knowledge-map.md` if prior session data exists for this topic
3. Run `research-mode.md` — define scope (in/out/done) and budget (speed/balanced/deep)
4. If topic is complex: run `decompose-task.md` to break into sub-questions
5. Run `select-channels.md` — pick 5-10 channels from 30+ available
6. Run `gene-query.md` in gap-driven mode — queries only for GAPs and LOW confidence items

After Phase 1, you should have:
- A knowledge backbone (60-70% of the final report content)
- A list of specific gaps to fill
- Selected channels and targeted queries

# Phase 2: Incremental Search (only search what Claude doesn't know)

Generate a queries JSON array for search_runner.py:

```json
[
  {"channel": "zhihu", "query": "自进化 AI agent 框架", "max_results": 10},
  {"channel": "github-repos", "query": "self-evolving agent", "max_results": 15},
  {"channel": "producthunt", "query": "AI agent 2026", "max_results": 10}
]
```

Execute all searches in one Bash call:

```bash
python autosearch/v2/search_runner.py 'THE_JSON_ARRAY' > results.jsonl
```

search_runner.py handles: parallel execution, URL normalization, dedup, date extraction.
All channels searched simultaneously in 5-15 seconds.

After search_runner returns, read results.jsonl. Use `fetch-webpage.md` for high-value pages needing full content. Use `follow-links.md` for awesome-lists.

Key principles:
- Do NOT search for things you already know with HIGH confidence
- Focus search budget on: fresh content, real-time data, community voice, verification
- Let search_runner.py do the mechanical work. Claude decides WHAT to search.

After Phase 2, you should have clean, deduplicated search results.

# Phase 3: Evaluate (quality control)

search_runner.py already did normalization, dedup, and date extraction. Claude only needs to:

1. Run `llm-evaluate.md` — relevance judgment + gap detection on search results
   - Do NOT evaluate own-knowledge items (they are relevant by definition)
   - Focus on: is this result genuinely new? Does it add something Claude doesn't know?
   - Tag each result: metadata.llm_relevant + metadata.llm_reason
2. Identify remaining gaps — what did the search NOT find?

Do NOT re-run normalize or extract-dates — search_runner.py already handled those.

After Phase 3, you should have evaluated search results ready for synthesis.

# Phase 4: Synthesize + Deliver

1. Run `synthesize-knowledge.md` to produce the delivery:
   - Blend knowledge backbone (Phase 1) with search discoveries (Phase 2-3)
   - Organize by concept, not by source
   - Mark each item's provenance: [knowledge] vs [discovered] vs [verified]
   - Include citations for all discovered items
   - Flag what AutoSearch found that native Claude would miss
2. Run `evaluate-delivery.md` — 4-dimension quality check
   - If fails: revise and re-check
3. Present to user

The delivery should clearly show AutoSearch's incremental value:
- "AutoSearch discovered N items not in Claude's training data"
- "Verified M items with real-time data (star counts, funding, etc.)"
- "Searched N platforms including [Chinese platforms / video / commercial]"

# Phase 5: Learn

1. Save updated knowledge map via `knowledge-map.md`
2. Record which channels produced incremental discoveries
3. Record which query patterns worked best
4. Append patterns to `state/patterns-v2.jsonl`

This data makes the next session on the same topic faster and better.

# Time Budget

| Phase | Target time | Notes |
|-------|------------|-------|
| Phase 1 | 30-60 seconds | Claude recalls from memory, fast |
| Phase 2 | 10-20 seconds | search_runner.py parallel execution |
| Phase 3 | 30-60 seconds | Evaluation of search results only |
| Phase 4 | 1-2 minutes | Synthesis |
| Phase 5 | 10 seconds | Write state files + auto-evolve |
| **Total** | **2-4 minutes** | 3x faster than native Claude |

# Quality Bar

The pipeline is working when:
- Phase 1 produces 30+ knowledge items before any search
- Phase 2 searches only GAPs (fewer queries than search-first mode)
- Phase 4 delivery clearly shows incremental value over native Claude
- Total time is under 10 minutes
