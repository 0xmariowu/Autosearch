---
name: m3_perspective_labels
phase: M3
description: Generate short perspective labels from the user query.
---
Generate {num_perspectives} short perspective labels for the research query below.

<Original user query>
{query}
</Original user query>

Respond in valid JSON with this exact schema:
{{
  "labels": [
    "short perspective label"
  ]
}}

Rules:
- Return exactly {num_perspectives} labels when possible
- Each label must be 2 to 5 words
- Each label should describe a distinct lens or angle on the query
- Keep labels concrete and search-useful
- Do not include numbering, explanations, or prose outside the JSON
