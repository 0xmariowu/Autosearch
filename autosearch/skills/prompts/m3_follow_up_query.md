---
name: m3_follow_up_query
phase: M3
description: Convert identified research gaps into focused follow-up search queries.
---
Convert the identified research gaps into focused follow-up search queries.

<Original user query>
{query}
</Original user query>

<Research gaps>
{gap_context}
</Research gaps>

<Collected evidence so far>
{evidence_context}
</Collected evidence so far>

Respond in valid JSON with this exact schema:
{{
  "subqueries": [
    {{
      "text": "search query",
      "rationale": "why this query helps close a specific gap"
    }}
  ]
}}

Rules:
- Return at most one subquery per gap
- Keep the queries specific, concrete, and non-redundant
- Use date terms only when the gap is clearly time-sensitive
- Make each rationale concise and directly tied to a gap
