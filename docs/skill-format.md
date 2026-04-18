<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
# Skill Format

## Overview

`SKILL.md` is the source file for AutoSearch skill metadata.
Each skill lives in its own directory and declares validated frontmatter plus human-readable body prose.
The loader reads the frontmatter at compile time and turns it into typed Python models.
The prose body remains documentation for maintainers and operators.

AutoSearch uses three skill categories:

1. `skills/meta/` for runtime agent behavior that may be compiled into pipeline prompts.
2. `skills/tools/` for reusable primitives such as cookie access, rate limiting, or fetch helpers.
3. `skills/channels/` for per-channel search capabilities compiled at startup.

The important split is compile time versus runtime:

- Compile time means startup code reads `SKILL.md`, validates it, and constructs runtime metadata.
- Runtime means the pipeline executes Python channel and tool code that was selected from that metadata.
- `SKILL.md` is not executable logic.

This document defines the F001 format described in plan `autosearch-0418-channels-and-skills.md`, section `F001`.

## File Layout

Each skill directory should contain:

- `SKILL.md` as the source of truth for metadata and prose guidance.
- Optional Python modules or method files referenced by the frontmatter.
- No generated state files.

Typical channel layout:

```text
skills/channels/arxiv/
├── SKILL.md
└── methods/
    ├── api_search.py
    └── api_detail.py
```

## Frontmatter Rules

Frontmatter is YAML placed between two lines containing only `---`.
The loader scans the file for the first such delimiter pair and parses the YAML between them.
Content before the first delimiter may exist only for non-runtime comments such as a repository ownership header.
Content after the closing delimiter is free-form prose.

The frontmatter must parse to a YAML mapping.
Unknown fields are currently passed through pydantic's default behavior for the declared model shape, so authors should stay within the documented schema.
Validation errors stop startup for that skill.

Example frontmatter shell:

```yaml
---
name: example-skill
description: Use for example queries that need one search method.
version: 1
methods:
  - id: search
    impl: methods/search.py
fallback_chain: [search]
---
```

## Field Reference

### `name`

`name` is the canonical skill identifier.
It is required.
It must match the directory name that contains the `SKILL.md`.
This prevents drift between filesystem layout and runtime references.

### `description`

`description` is required.
Keep it short and operational.
It should explain when the skill should be used, not implementation details.

### `version`

`version` is optional and defaults to `1`.
Use it when the schema or intended contract needs an explicit revision marker.
F001 only supports versioned metadata as a numeric field.

### `languages`

`languages` is optional and defaults to an empty list.
Allowed values are `zh`, `en`, and `mixed`.
Tool skills often leave this empty.
Channel skills use it to express language coverage.

### `methods`

`methods` is optional and defaults to an empty list.
Each entry follows the `MethodSpec` schema.
Method order matters because authors usually place the primary method first.

`MethodSpec` fields:

- `id`: required stable identifier for the method.
- `impl`: required relative module path or implementation reference.
- `requires`: optional list of runtime requirements.
- `rate_limit`: optional free-form mapping for channel-specific rate metadata.

### `fallback_chain`

`fallback_chain` is optional and defaults to an empty list.
Each entry must match a method `id` declared in `methods`.
Use it to define preferred fallback order when multiple methods exist.
Validation fails if any fallback entry references a missing method.

### `when_to_use`

`when_to_use` is optional.
It groups routing hints for the planner or future selection logic.
The nested fields are:

- `query_languages`: list of `zh`, `en`, or `mixed`.
- `query_types`: free-form list of query categories.
- `avoid_for`: free-form list of cases where the skill should not be selected.

Tool skills can omit this section.

### `quality_hint`

`quality_hint` is optional.
It records expectation metadata instead of hard behavior.
The nested fields are:

- `typical_yield`: one of `low`, `medium`, `medium-high`, `high`, or `unknown`.
- `chinese_native`: boolean flag that marks strong native Chinese coverage.

### `skill_dir`

`skill_dir` is part of the runtime `SkillSpec` model but is not written in frontmatter.
The loader injects it from the filesystem path after parsing the YAML.
This field lets later code locate implementation files relative to the skill directory.

## Body Convention

Everything after the closing `---` delimiter is prose.
Keep it human-readable and declarative.
Do not place executable logic, shell pipelines, or hidden machine directives in the body.
Good body content includes:

- Search strategy notes.
- Operational caveats.
- Data quality expectations.
- Known failure modes.

The loader in F001 ignores the body completely.
That is intentional.
The body exists for maintainers, future compilers, and review context.

## `requires` Token Syntax

Each `requires` entry must match this pattern:

```text
^(cookie|mcp|env|binary):[a-zA-Z_][a-zA-Z0-9_-]*$
```

Supported prefixes:

- `cookie:` for channel cookies or session artifacts.
- `mcp:` for named MCP servers.
- `env:` for environment variables or capability flags.
- `binary:` for required executables on `PATH`.

Valid examples:

- `cookie:zhihu`
- `mcp:mcporter`
- `env:GITHUB_TOKEN`
- `binary:curl`

Invalid examples:

- `cookie:`
- `http:curl`
- `cookie:123bad`
- `invalid-token`

## Full Example

The following example shows a valid channel skill with two methods, a fallback chain, bilingual routing hints, and quality metadata.

```yaml
---
name: arxiv
description: Use for paper searches and follow-up detail fetches across English or Chinese queries.
version: 1
languages: [zh, en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: [env:ARXIV_TOKEN]
    rate_limit:
      per_min: 30
      per_hour: 500
  - id: api_detail
    impl: methods/api_detail.py
    requires: [binary:curl]
    rate_limit:
      per_min: 10
fallback_chain: [api_search, api_detail]
when_to_use:
  query_languages: [zh, en]
  query_types: [academic-papers, literature-review]
  avoid_for: [real-time-news]
quality_hint:
  typical_yield: medium-high
  chinese_native: false
---

Prefer API search for discovery and use the detail endpoint only after ranking likely matches.
```

## Loader Discovery And Validation

The F001 loader discovers skills by scanning one directory level under a supplied root.
For each child directory:

- If `SKILL.md` exists, the loader reads and validates it.
- If `SKILL.md` is missing, the loader skips the directory and emits a structlog event.
- Returned specs are sorted by `name`.

Validation covers:

- Required fields such as `name` and `description`.
- Literal values for `languages` and `quality_hint.typical_yield`.
- `requires` token syntax.
- `fallback_chain` references that must point at declared method ids.
- Directory name alignment between `name` and the containing folder.

Illustrative usage:

```python
from pathlib import Path

from autosearch.skills.loader import load_all, load_skill

channels_root = Path("skills/channels")
channel_specs = load_all(channels_root)
one_tool = load_skill(Path("skills/tools/fetch-webpage"))
```

The loader raises `SkillLoadError` with a clear message when validation fails.
This keeps startup failures local to the broken skill source.

## Authoring Checklist

- Put one skill in one directory.
- Start with a repository ownership comment if required by repo rules.
- Add YAML frontmatter between `---` lines.
- Keep `name` identical to the directory name.
- Keep method ids stable once referenced by code.
- Use only supported `requires` token prefixes.
- Write prose after the frontmatter, not executable instructions.
- Validate with loader tests before wiring a skill into runtime code.

## Related Files

- `autosearch/skills/loader.py` implements parsing and validation.
- `skills/meta/README.md` describes runtime behavior skills.
- `skills/tools/README.md` describes reusable primitive skills.
- `skills/channels/README.md` describes per-channel search skills.
- Plan reference: `~/.claude/plans/autosearch-0418-channels-and-skills.md` section `F001`.

This document is intentionally compile-time focused.
Later features can extend runtime behavior, registry compilation, and health tracking without changing the core frontmatter contract introduced here.
