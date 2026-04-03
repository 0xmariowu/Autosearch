---
name: generate-rubrics
description: "Use before search to define binary rubrics that specify what a complete answer must contain. Outputs 20-30 topic-specific rubrics for post-delivery evaluation."
---

# Model Recommendation

Rubric generation is a structured output task — binary rubrics with fixed schema. Use Haiku when possible. When spawning an agent for rubric generation, set `model: "haiku"`.

# Purpose
This skill defines the success criteria before any search begins.
It turns a vague research goal into 20-30 binary rubrics that answer one question: what must the final delivery contain to count as complete?
Without rubrics, evaluation becomes subjective and drifts toward "looks good."
With rubrics, the system can measure coverage, insight, and presentation from the delivery text alone.
# When To Use
Use immediately after receiving the topic, before Phase 1 (recall).
Run this before `systematic-recall.md`, `decompose-task.md`, or any search channel selection.
The rubrics become the contract for the whole session:
- recall should anticipate them
- search should fill the missing ones
- synthesis should organize around them
- evaluation should score delivery against them
# Output Contract
Each rubric is one JSON object:
```json
{
  "id": "r001",
  "category": "information-recall",
  "rubric": "Lists at least 5 foundational methods (e.g., STaR, Reflexion, Voyager)",
  "priority": "high"
}
```
Required fields:
- `id`: sequential, zero-padded, starting at `r001`
- `category`: one of `information-recall`, `analysis`, `presentation`
- `rubric`: one binary, delivery-checkable requirement
- `priority`: one of `high`, `medium`, `low`
Write 20-30 total rubrics.
Target mix:
- 60% `information-recall`
- 30% `analysis`
- 10% `presentation`
Do not force exact math if the topic needs slight adjustment, but stay close to this ratio.
# Generation Logic
Generate rubrics from the topic itself, not from a static template.
First infer what a strong answer on this specific topic would need to cover:
- what entities matter
- what methods or products define the space
- what timelines or milestones matter
- what decisions or tradeoffs the user will likely care about
- what presentation constraints make the answer auditable
Then convert those needs into binary checks.
Every rubric must be answerable with yes or no by reading the final delivery only.
Good pattern:
- "Lists at least 4 benchmark datasets used to evaluate coding agents"
- "Compares at least 3 memory architectures and states one tradeoff for each"
Bad pattern:
- "The report is comprehensive"
- "The answer is insightful"
# Category Design
## 1. information-recall
This category asks: did we find the key information?
These rubrics should be concrete, countable, and verifiable.
Common targets:
- key players
- foundational methods
- tools or products
- important papers
- benchmark datasets
- timelines or milestones
- quantitative data points
- geographic or market coverage if relevant
Use thresholds that reflect the topic:
- counts: "at least 3", "at least 5", "at least 1 per segment"
- presence checks: "names the leading open-source framework by stars"
- temporal checks: "includes a timeline covering 2023-2026"
## 2. analysis
This category asks: did we produce value beyond collection?
These rubrics should test reasoning that the delivery explicitly contains.
Common targets:
- comparisons
- tradeoffs
- trends over time
- causal reasoning
- segmentation or taxonomy
- recommendations
- decision rules
- risks and limitations
Examples:
- "Compares at least 3 approaches and identifies one tradeoff for each"
- "States a recommendation for which option fits startups vs enterprises"
- "Explains at least 2 reasons the field shifted in the last 12 months"
## 3. presentation
This category asks: is the delivery easy to audit and use?
These rubrics should test output quality that is visible in the final text.
Common targets:
- citation completeness
- structure clarity
- gap declaration
- source diversity
- distinction between verified facts and uncertainty
Examples:
- "Every major recommendation is supported by at least 1 citation"
- "Includes an explicit section for gaps or unknowns"
- "Uses sources from at least 3 distinct source types"
# Writing Rules
1. Every rubric must be binary.
2. Every rubric must be specific.
3. Every rubric must be verifiable from the delivery text alone.
4. Rubrics must be generated from the topic, not copied from a fixed checklist.
5. `information-recall` rubrics should emphasize players, methods, tools, papers, data points, and timelines.
6. `analysis` rubrics should emphasize comparisons, tradeoffs, trends, causal reasoning, and recommendations.
7. `presentation` rubrics should emphasize citation completeness, structure clarity, gap declaration, and source diversity.
8. Output 20-30 rubrics total. Do not explode into 60+ micro-rubrics.
9. Use `high` for must-have information, `medium` for meaningful depth, `low` for nice-to-have extras.
Practical test:
- if two reviewers read the delivery, they should reach the same yes/no judgment on most rubrics
- if a rubric needs outside knowledge to score, rewrite it
- if a rubric can be satisfied by a trivial mention, tighten it
# Priority Assignment
Use `high` for items that would make the answer materially incomplete if missing:
- core methods
- leading players
- crucial timeline points
- essential comparisons
- must-have recommendations
Use `medium` for depth that materially improves usefulness:
- second-order tradeoffs
- segmentation by use case
- ecosystem patterns
- supporting quantitative evidence
Use `low` for useful but non-essential extras:
- edge cases
- niche subsegments
- secondary presentation polish
Do not mark everything `high`.
If more than half the rubrics are `high`, the set is probably not prioritized enough.
# Storage
Store rubrics at:
`evidence/rubrics-{topic-slug}.jsonl`
One JSON object per line.
Do not wrap the file in a JSON array.
Generate `topic-slug` as:
- lowercase only
- replace spaces and separators with hyphens
- remove punctuation except hyphens
- collapse repeated hyphens
- trim leading and trailing hyphens
- max 50 characters
Example:
- `AI agents for software engineering in 2026` -> `ai-agents-for-software-engineering-in-2026`
# Anti-Patterns
Avoid:
- generic rubrics that fit any topic, such as "report has introduction"
- rubrics that require external verification, such as "all URLs are valid"
- rubrics so weak they are trivially satisfied, such as "mentions the word AI"
- duplicate rubrics that test the same requirement with different wording
Also avoid hidden overlap.
If one rubric requires "lists 5 key companies" and another requires "mentions leading vendors," merge or sharpen them so each checks a distinct thing.
# Quality Bar
This skill is working correctly when the rubric file:
- contains 20-30 topic-specific JSONL entries
- stays close to the 60/30/10 category ratio
- uses binary, specific, delivery-checkable language throughout
- clearly distinguishes must-have coverage from added depth
- gives downstream phases a concrete definition of completeness
A good rubric set makes weak delivery obvious.
If the final answer could miss major substance and still pass most rubrics, the rubric generation was too generic.
