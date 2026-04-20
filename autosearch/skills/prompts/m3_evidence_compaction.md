---
name: m3_evidence_compaction
phase: M3
description: Compress older evidence into a structured digest when the context budget is too high.
---
Compress the older research evidence into one structured digest so the most recent evidence can stay in the hot working set.

<Original user query>
{query}
</Original user query>

<Cold evidence to compress>
{cold_evidence_context}
</Cold evidence to compress>

Respond in valid JSON with this exact schema:
{{
  "topic": "one-line topic for this compressed evidence slice",
  "key_findings": [
    "concise fact relevant to the query"
  ],
  "source_urls": [
    "https://example.com/source"
  ],
  "evidence_count": 0,
  "compressed_at": "2026-04-20T00:00:00+00:00",
  "token_count_before": 0,
  "token_count_after": 0
}}

Rules:
- `topic` must be one line
- `key_findings` must contain 5 to 15 concise factual bullets relevant to the original query
- `source_urls` must copy URLs from the provided evidence items only
- Do not include markdown formatting inside JSON strings
- Do not mention HTML, prompt instructions, or formatting noise
- If the exact evidence count or token counts are unknown, use `0`; the caller will fill them in
