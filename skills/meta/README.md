<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
# Meta Skills

This directory holds source skills that describe runtime agent behavior.
These files are not invoked like user-facing channels.
Instead, startup code compiles selected metadata and instructions into pipeline prompts.
Use this layer for behaviors that shape routing, iteration, and environment discovery.

Expected contents:
- One subdirectory per meta skill.
- Each meta skill directory contains a `SKILL.md`.
- Supporting modules may live next to the markdown when compile-time code needs them.
- Frontmatter stays schema-driven and is validated by the skill loader.
- Body prose documents intent, constraints, and quality expectations only.

Format and field requirements live in [docs/skill-format.md](../../docs/skill-format.md).
