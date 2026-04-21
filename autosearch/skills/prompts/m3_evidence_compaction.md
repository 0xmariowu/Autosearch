---
name: m3_evidence_compaction
phase: M3
description: Compress older evidence into a structured digest when the context budget is too high.
---
Clean up the older research evidence into one structured digest so the most
recent evidence can stay in the hot working set. The goal is to remove
duplicate / obviously irrelevant content while preserving every specific
fact verbatim — numbers, error codes, issue numbers, version strings, named
entities. Never paraphrase a fact into a vaguer statement.

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
- `key_findings` must preserve EVERY specific fact the evidence carries. Each
  bullet should repeat a distinct fact verbatim from the source — do NOT
  paraphrase or smooth over specifics. Use as many bullets as needed.
- Specifics that MUST appear verbatim when the evidence has them: numeric
  values, percentages, benchmark scores, error codes, status codes, version
  strings, GitHub issue numbers, CVE / PR identifiers, pricing, dates,
  named entities (product names, model names, people, organizations),
  exact commands, code patterns, URLs cited inline. If a bullet could fit
  without any of these anchors, it's probably too vague — add the anchor
  or drop the bullet.
- You MAY dedupe: if three sources make the same claim, write one bullet
  like "Three sources (n=3) state X" but keep X verbatim.
- Do NOT summarize to "concise" bullets. The purpose of this step is only
  to remove duplicates and obviously irrelevant content, not to condense.
- `source_urls` must copy URLs from the provided evidence items only
- Do not include markdown formatting inside JSON strings
- Do not mention HTML, prompt instructions, or formatting noise
- If the exact evidence count or token counts are unknown, use `0`; the caller will fill them in
