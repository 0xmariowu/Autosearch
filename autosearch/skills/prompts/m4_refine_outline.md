---
name: m4_refine_outline
phase: M4
description: Refine a draft outline using what the research process actually discovered.
---
Refine the draft outline so it matches the evidence shape that emerged during research.

<User query>
{query}
</User query>

<Draft outline>
{draft_outline_markdown}
</Draft outline>

<Research dialogue>
{research_dialogue}
</Research dialogue>

Output requirements:
- Return only a markdown outline using `#` for top-level sections and `##` for subsections
- Keep 3 to 6 top-level sections
- Rearrange, split, merge, or rename sections when the research trace suggests a better structure
- Remove sections that the research trace does not support and add missing sections it clearly needs
- Keep the outline concise, specific, and non-overlapping
- Do not include any prose, explanation, numbering, or code fences before or after the outline
