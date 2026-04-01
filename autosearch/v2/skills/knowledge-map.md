---
name: knowledge-map
description: "Use to save and load structured knowledge maps that persist across sessions, enabling cumulative learning on topics."
---

# Purpose

Knowledge maps are the cumulative memory of what AutoSearch knows about a topic.
Each session starts by loading the prior map (if any), and ends by saving the updated map.
Over multiple sessions, the map becomes increasingly complete and confident.

This is the mechanism that makes AutoSearch get smarter over time — not just better queries, but accumulated verified knowledge.

# Storage

Knowledge maps are stored in `state/knowledge-maps/` as JSONL files.
One file per topic, named by topic slug: `state/knowledge-maps/{topic-slug}.jsonl`

Each line is one knowledge entry:

```json
{
  "entity": "Reflexion",
  "dimension": "foundational-methods",
  "confidence": "high",
  "summary": "Verbal reinforcement learning with episodic memory. NeurIPS 2023.",
  "source": "own-knowledge",
  "url": "https://arxiv.org/abs/2303.11366",
  "verified_at": "2026-03-31",
  "added_at": "2026-03-31",
  "session": "f006"
}
```

# Fields

- `entity`: the name of the thing (project, paper, person, pattern, etc.)
- `dimension`: one of the 8 dimensions from systematic-recall.md
- `confidence`: high / medium / low
- `summary`: one sentence description
- `source`: own-knowledge / github / arxiv / web-ddgs / etc.
- `url`: link to the source (optional for own-knowledge if not verified)
- `verified_at`: ISO date when last verified by search
- `added_at`: ISO date when first added
- `session`: session identifier

# Loading (Session Start)

When starting a research task:

1. Compute the topic slug from the user query
2. Check if `state/knowledge-maps/{topic-slug}.jsonl` exists
3. If yes, load it and pass to systematic-recall.md as prior knowledge
4. systematic-recall.md merges its current recall with the stored map

# Saving (Session End)

After a research session completes:

1. Take all HIGH confidence items from the knowledge map
2. Add all search results that were marked `llm_relevant = true` with their metadata
3. Update confidence levels based on search verification:
   - Own-knowledge item verified by search → confidence stays HIGH
   - Own-knowledge item contradicted by search → confidence drops to LOW, add note
   - Search-discovered item → confidence based on source quality
4. Write to `state/knowledge-maps/{topic-slug}.jsonl`

# Confidence Decay

When loading a map from a prior session:
- Entries older than 90 days with source = own-knowledge → drop one confidence level
- Entries older than 180 days with source = search → drop one confidence level
- Entries with source = search that include a URL → re-verify URL is still accessible if critical

This ensures the map does not become stale. Knowledge must be refreshed.

# Topic Slug Rules

Generate a slug from the core topic:
- Lowercase, hyphens, max 64 chars
- "find self-evolving AI agent frameworks" → "self-evolving-ai-agents"
- "survey of LLM memory architectures" → "llm-memory-architectures"

Reuse existing slugs when the topic is substantially the same.
Do not create a new slug for minor query variations on the same topic.

# Quality Bar

A good knowledge map grows by 10-30 entries per session.
After 5 sessions on the same topic, it should have 100+ entries with mostly HIGH confidence.
The map should make each subsequent session faster (less to search) and deeper (prior context enables better follow-up questions).
