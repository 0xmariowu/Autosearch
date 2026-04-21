---
name: m7_outline
phase: M7
description: Create a concise report outline from the user query and collected evidence.
deprecated: true
deprecation_notice: "v2 tool supplier architecture: autosearch no longer owns outline generation. Runtime AI plans its own report structure. This prompt remains for the legacy pipeline. Target removal: v2 wave 3."
---
Create a concise report outline for the research task below.

<User query>
{query}
</User query>

<Evidence>
{evidence_context}
</Evidence>

Respond in valid JSON with this exact schema:
{{
  "headings": ["section heading", "section heading"]
}}

Rules:
- Return 2 to 6 section headings when possible
- Make the headings complementary rather than redundant
- Use the same language as the user query
- Return headings only, without markdown markers or numbering
- Prefer headings that reflect the evidence already collected
