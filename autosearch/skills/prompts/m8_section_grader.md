---
name: m8_section_grader
phase: M8
description: Grade a report section against its topic, rubrics, and supporting evidence.
---
Review a report section relative to the specified topic:

<Report topic>
{topic}
</Report topic>

<section topic>
{section_topic}
</section topic>

<section content>
{section}
</section content>

<quality rubrics>
{rubrics}
</quality rubrics>

<supporting evidence>
{evidence_context}
</supporting evidence>

<task>
Evaluate whether the section content adequately addresses the section topic.
Use the rubrics and supporting evidence as the grading standard.
If the section content does not adequately address the section topic, generate
{number_of_follow_up_gaps} follow-up gaps that describe the missing research needed.
</task>

<format>
Respond in valid JSON with these exact keys:
- "grade": "pass" or "fail"
- "follow_up_gaps": a list of objects with exact keys "topic" and "reason"

Rules:
- Return "pass" only when the section materially covers the topic and rubrics.
- Return an empty "follow_up_gaps" list when grade is "pass".
- When grade is "fail", return at least one follow-up gap.
- Focus follow-up gaps on missing research, missing evidence, or missing comparisons.
</format>
