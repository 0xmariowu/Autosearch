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

For each selected channel:
1. Read the channel's skill file
2. Execute the search using the gap-driven queries
3. Collect raw results

Key principles:
- Do NOT search for things you already know with HIGH confidence
- Focus search budget on: fresh content, real-time data, community voice, verification
- Use `fetch-webpage.md` for high-value pages that need full content
- Use `follow-links.md` for awesome-lists and survey pages

After Phase 2, you should have raw search results from 5-10 channels.

# Phase 3: Clean + Evaluate (quality control)

1. Run `normalize-results.md` — canonical format, URL dedup, cross-platform merge
2. Run `extract-dates.md` — freshness metadata from all available signals
3. Run `llm-evaluate.md` — relevance judgment + gap detection on search results only
   - Do NOT evaluate own-knowledge items (they are relevant by definition)
   - Focus evaluation on search-discovered items
4. If AVO is running: check `anti-cheat.md`

After Phase 3, you should have clean, evaluated evidence.

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
| Phase 2 | 2-5 minutes | Depends on channel count and query count |
| Phase 3 | 30-60 seconds | Evaluation of search results only |
| Phase 4 | 1-2 minutes | Synthesis |
| Phase 5 | 10 seconds | Write state files |
| **Total** | **4-8 minutes** | Should be faster than native Claude (17 min in T1 test) |

# Quality Bar

The pipeline is working when:
- Phase 1 produces 30+ knowledge items before any search
- Phase 2 searches only GAPs (fewer queries than search-first mode)
- Phase 4 delivery clearly shows incremental value over native Claude
- Total time is under 10 minutes
