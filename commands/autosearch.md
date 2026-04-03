---
description: "Self-evolving deep research system. Use when the user wants deep research on any topic."
user-invocable: true
---

# /autosearch — Self-Evolving Deep Research System

Run an AutoSearch research session.

## Arguments

$ARGUMENTS — the research task (e.g., "find AI agent frameworks", "research vector databases")

If no arguments provided, ask the user what to research.

## Execution

### Phase A: Configure (runs in current model — cheap)

1. Set working directory to `${CLAUDE_PLUGIN_ROOT}`
2. **Ask the user 3 questions before searching** (use AskUserQuestion, all in one call):
   - **Depth**: Quick (5 channels, 1 round) / Standard (10 channels, 3 rounds) / Deep (15+ channels, 5 rounds)
   - **Focus**: Open source / Academic / Commercial / Chinese / Community / All
   - **Delivery**: Markdown report (.md) / Rich HTML report (tables + diagrams) / Presentation slides (reveal.js)
3. **Auto-determine content structure from Depth** (do not ask the user):
   - Quick → executive summary (1 page, key insights + recommendation)
   - Standard → full report (framework + evidence tables + analysis)
   - Deep → full report + evidence appendix + gap declaration
4. **Auto-detect language from topic**: Chinese topic → Chinese output + prioritize Chinese channels. English topic → English output. Mixed → follow the dominant language.

### Phase B: Research (spawn researcher agent — runs in Sonnet)

5. Spawn the `autosearch:researcher` agent with **`mode: "auto"`** to execute the pipeline. Pass it:
   - The research topic
   - Depth / Focus / Delivery selections
   - Content structure (from step 3)
   - Language (from step 4)
   - Working directory: `${CLAUDE_PLUGIN_ROOT}`
   - **Do NOT use bypassPermissions** — it skips safety checks and causes unpredictable failures
6. The researcher agent reads `PROTOCOL.md` and follows `skills/pipeline-flow/SKILL.md`
7. The researcher uses its own training knowledge alongside search results (`skills/use-own-knowledge/SKILL.md`)
8. The researcher delivers in the user's chosen format (`skills/synthesize-knowledge/SKILL.md`)
9. Use Python 3.10+ for `lib/judge.py`

### Why split?

- Phase A (questions + config) uses few tokens — fine to run in any model
- Phase B (search + synthesis) uses 100K+ tokens — must run in Sonnet (5x cheaper than Opus)
- The `agents/researcher.md` has `model: sonnet` in its frontmatter

## Key constraints

- `lib/judge.py` is the only evaluator — run it, never self-assess
- State files in `state/` are append-only
- Config/skill changes go through git commit/revert
- Read the relevant `skills/*/SKILL.md` before executing any capability
