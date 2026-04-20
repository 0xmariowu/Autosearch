---
name: m3_search_reflection
phase: M3
description: Identify fresh research gaps immediately after a single batch of searches.
---
Review only the newest batch of search results and identify the most important gaps that are still
visible right now.

<Original user query>
{query}
</Original user query>

<Batch subqueries just executed>
{batch_subqueries}
</Batch subqueries just executed>

<Evidence from this batch only>
{batch_evidence_context}
</Evidence from this batch only>

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
- Return an empty list if this batch already covers its narrow objective well enough
- Focus on what is still missing after this batch, not the entire iteration
- Prefer concrete follow-up angles that can be searched directly
- Do not repeat information that is already covered in the batch evidence
