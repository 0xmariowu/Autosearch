---
name: m7_section_write_v2
phase: M7
description: Write a report section using only the provided per-section snippets and inline citations.
---
Write the body content for this report section using only the provided snippets.

<Research topic>
{topic}
</Research topic>

<Section heading>
{section_heading}
</Section heading>

<Local section outline>
{section_outline}
</Local section outline>

<Snippet list>
{snippets_context}
</Snippet list>

Respond in valid JSON with this exact schema:
{{
  "content": "plain markdown section body"
}}

Rules:
- Write the section on {section_heading} using only the provided snippets
- Use the local section outline for context, but only write this section body
- Use inline citations like [1], [2], ... where N matches the snippet number
- Do NOT cite snippets you did not use
- Do NOT invent content that is not grounded in the snippets
- Target length: 2-4 paragraphs unless the available content is sparse
- Do not include the section heading line itself in the content
- Do not add a references section
