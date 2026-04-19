<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
# Channel Skills

This directory holds per-channel search skill sources.
Each child directory represents one search surface such as a site, platform, or API.
Startup code compiles these `SKILL.md` files into runtime channel objects and metadata.
Use this layer for channel-specific descriptions, routing hints, and method declarations.

Expected contents:
- One subdirectory per channel.
- Each channel directory contains a `SKILL.md`.
- Method implementation modules usually live under `methods/`.
- Frontmatter defines languages, methods, fallback chains, and selection hints.
- Body prose records search strategy and operator notes only.

Format and validation rules live in [docs/skill-format.md](../../docs/skill-format.md).
