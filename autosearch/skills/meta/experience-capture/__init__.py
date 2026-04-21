"""autosearch:experience-capture meta skill package marker.

Appends a single event to the per-skill experience/patterns.jsonl file after
a leaf skill executes. Append-only, runtime AI does NOT read patterns.jsonl
directly — it only reads the compacted experience.md digest. This skill runs
every time (Fast tier, no LLM required).
"""
