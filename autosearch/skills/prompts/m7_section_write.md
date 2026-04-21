---
name: m7_section_write
phase: M7
description: Write a report section using only the provided evidence and inline citations.
deprecated: true
deprecation_notice: "v2 tool supplier architecture: autosearch no longer owns final synthesis. Runtime AI (Claude / Cursor) writes the report directly from the evidence autosearch provides. This prompt remains so the legacy pipeline keeps running, but new code paths should return evidence + structured context to the runtime AI rather than running this synthesizer. Target removal: v2 wave 3."
---
Write the body content for this report section using only the provided evidence.

<Section heading>
{heading}
</Section heading>

<Evidence list>
{evidence_context}
</Evidence list>

Respond in valid JSON with this exact schema:
{{
  "content": "section body in markdown",
  "ref_ids": [1, 2]
}}

Rules:
- Use inline citations like [1], [2], ... directly in the prose
- The citation number must equal the evidence list index plus 1
- Use only citation numbers that exist in the provided evidence list
- Do not include the section heading line itself in the content
- Do not add a references section
- Return "ref_ids" as the 1-based evidence indexes actually cited in the content
