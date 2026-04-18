<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
# Tool Skills

This directory holds reusable primitives shared by channels and pipeline stages.
Tool skills describe capabilities such as cookie access, rate limiting, fetch helpers, or normalization.
They are compiled or imported as building blocks instead of being routed to directly as channels.
Use this layer when logic should be reusable across multiple channel skills.

Expected contents:
- One subdirectory per tool skill.
- Each tool skill directory contains a `SKILL.md`.
- Optional implementation modules can live beside the markdown source.
- Frontmatter captures method metadata, requirements, and fallback ordering.
- Body prose explains operator guidance without embedding executable logic.

Format and validation rules live in [docs/skill-format.md](../../docs/skill-format.md).
