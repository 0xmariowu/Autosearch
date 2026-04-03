---
name: check-rubrics
description: "Use after delivery to evaluate each rubric as pass/fail with evidence. Produces checked-rubrics.jsonl and summary scores by category."
---

# Model Recommendation

Rubric pass/fail checking is a structured classification task. Use Haiku when possible. When spawning an agent for rubric checking, set `model: "haiku"`.

# Purpose
This skill performs the strict post-delivery audit.
It checks whether the synthesized delivery actually satisfies the rubric contract defined earlier.
The goal is not to reward effort or partial coverage.
The goal is to produce a binary record of what the delivery demonstrably achieved.
Without this step, rubric generation is theoretical.
With this step, the system can measure completeness from the delivery text itself and track quality over time.

# When To Use
Use after `synthesize-knowledge.md` produces the delivery, before auto-evolve.
Run this on the final delivery text that would be shown to the user, not on notes, search results, or the evidence bundle.
Process every rubric before writing the history record.

# Required Inputs
Read:
- the full delivery text
- `evidence/rubrics-{topic-slug}.jsonl`
Do not judge from memory, search results, or outside knowledge.
The delivery text is the only scoring surface.

# Output Contract
Write one checked rubric per line to:
`evidence/checked-rubrics-{topic-slug}.jsonl`
Each line must be one JSON object:

```json
{
  "id": "r001",
  "category": "information-recall",
  "rubric": "Lists at least 5 foundational methods (e.g., STaR, Reflexion, Voyager)",
  "priority": "high",
  "passed": true,
  "evidence": "Report mentions STaR, Reflexion, Voyager, DSPy, ADAS, FunSearch in the Foundational Methods section"
}
```
Required fields:
- `id`
- `category`
- `rubric`
- `priority`
- `passed`
- `evidence`
After all rubrics are checked, append one summary JSON object to:
`state/rubric-history.jsonl`
Summary shape:
```json
{
  "topic": "self-evolving-agents",
  "timestamp": "2026-04-01T10:00:00Z",
  "total_rubrics": 25,
  "passed": 18,
  "failed": 7,
  "pass_rate": 0.72,
  "by_category": {
    "information-recall": {"total": 15, "passed": 10, "rate": 0.67},
    "analysis": {"total": 7, "passed": 6, "rate": 0.86},
    "presentation": {"total": 3, "passed": 2, "rate": 0.67}
  },
  "failed_rubrics": ["r003", "r007", "r012", "r015", "r019", "r022", "r025"]
}
```
# Checking Process
1. Read the delivery text in full before judging individual rubrics.
2. Read every rubric from `rubrics-{topic-slug}.jsonl`.
3. Evaluate each rubric against the delivery text only.
4. Decide `passed: true` only when the delivery clearly satisfies the full requirement.
5. Write evidence that points to the exact passage, section, items, or absence that drove the decision.
6. Output every checked rubric to `checked-rubrics-{topic-slug}.jsonl`.
7. Compute totals, category pass rates, and failed rubric ids.
8. Append the summary object to `state/rubric-history.jsonl`.
Do not skip low-priority rubrics.
Do not stop early because the delivery already looks strong or weak.

# Pass/Fail Rules
Binary means binary:
- pass only if the delivery clearly satisfies the rubric
- partial coverage is fail
- implied coverage is fail
- likely true but not stated is fail
- satisfied in source material but missing from delivery is fail
Use this test:
If a skeptical reviewer read only the delivery, would they confidently mark the rubric satisfied?
If not, mark fail.

# Evidence Rules
Evidence is mandatory for every rubric.
Never write empty, vague, or generic evidence.
Good evidence:
- quotes or near-quotes from the delivery
- named items counted explicitly
- section references tied to specific claims
- direct statement that the required element is missing
Bad evidence:
- "the report covers this"
- "mentioned throughout"
- "supported by the research"
For failed rubrics, explain exactly what was missing:
- missing count threshold
- missing comparison
- missing tradeoff
- missing citation
- missing section or heading

# How To Judge Common Rubric Types
## Count-Based Rubrics
For rubrics like "at least N items":
- count explicitly
- list the exact items found
- pass only if the count meets or exceeds the threshold
- fail if duplicates, vague references, or borderline matches were needed to reach N
## Analysis Rubrics
Check that the delivery performs the analysis, not merely names the topic.
A pass requires explicit reasoning in the delivery, such as:
- comparison with stated differences
- tradeoffs with consequences
- recommendation with rationale
- trend explanation with causal logic
If the text only says a topic exists, that is fail.
## Presentation Rubrics
Check visible delivery structure, not hidden intent.
Typical checks include:
- headings or sections exist
- citations are present where required
- gaps or unknowns are explicitly declared
- tables or resource indexes are actually present if required
If the structure is only partially there, fail.

# Summary Computation
After checking all rubrics, compute:
- `total_rubrics`
- `passed`
- `failed`
- `pass_rate` as `passed / total_rubrics`
- `by_category` totals, passed counts, and rates
- `failed_rubrics` as a list of rubric ids with `passed: false`
- `timestamp` in UTC ISO 8601 format
Do not round pass/fail counts.
Rates may be rounded sensibly, but keep the counting exact.

# Storage Rules
Use the same `topic-slug` convention as `generate-rubrics.md`.
Write JSONL, one object per line.
Do not wrap outputs in a JSON array.
If `rubric-history.jsonl` does not exist yet, create it and append the first summary line.

# Anti-Patterns
Avoid:
- rubber-stamping most rubrics as pass
- failing to process every rubric
- using search evidence instead of delivery evidence
- accepting "close enough" on count thresholds
- writing evidence so vague another reviewer could not audit it
- confusing topic mention with real analysis

# Quality Bar
This skill is working correctly when:
- every rubric receives a strict binary verdict
- every verdict includes concrete delivery-based evidence
- count-based rubrics show explicit item counts
- analysis rubrics require actual reasoning, not keyword overlap
- presentation rubrics verify visible structure and citations
- the checked rubric file and rubric history summary are both written

A strong result from this skill makes weak delivery obvious.
If an incomplete report can still pass most rubrics, the checking was too lenient.
