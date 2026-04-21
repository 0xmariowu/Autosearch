"""autosearch:experience-compact meta skill package marker.

Promotes recurring patterns from `experience/patterns.jsonl` into the compact
`experience.md` digest (≤120 lines). Triggers on: ≥10 new events, >64KB file
size, user accepted/rejected feedback, or session end. Runs at Standard tier
with a promotion-threshold gate (seen ≥ 3, success ≥ 2, last_verified ≤ 30d).
"""
