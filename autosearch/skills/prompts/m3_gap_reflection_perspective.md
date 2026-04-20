---
name: m3_gap_reflection_perspective
phase: M3
description: Identify remaining research gaps for a specific perspective.
---
Review the current research progress and identify only the most important remaining gaps from the
specified perspective.

<Perspective lens>
{perspective}
</Perspective lens>

<Original user query>
{query}
</Original user query>

<Current iteration>
{iteration} of {max_iterations}
</Current iteration>

<Queries already executed>
{subqueries}
</Queries already executed>

<Collected evidence>
{evidence_context}
</Collected evidence>

Respond in valid JSON with this exact schema:
{{
  "gaps": [
    {{
      "topic": "missing research topic",
      "reason": "why this missing information matters"
    }}
  ]
}}

Rules:
- Return at most 3 gaps
- Return an empty list if the evidence already covers this perspective well enough to draft a report
- Focus on missing evidence, missing comparisons, missing time-sensitive details, or unanswered
  sub-questions
- Keep each topic concrete enough to search directly
- Do not repeat gaps that are already covered by the collected evidence
- Stay within the stated perspective while still serving the original query
