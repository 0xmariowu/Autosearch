---
name: create-skill
description: "Use when a missing capability blocks progress or a new tool, source, or tactic deserves to become a reusable skill in `skills/`."
---

# Purpose

You can write new `.md` files to gain new capabilities.
Treat skill creation as the main way to turn one-off improvisation into durable leverage for future generations.

This is an immutable meta-skill.
It defines how capability expansion works, so do not modify it during normal AVO operation.

# When To Create A Skill

Create a new skill when:

- you discovered a new data source, platform, API, tool, or workflow that can improve future runs
- existing skills are insufficient, too vague, or force repeated ad hoc behavior
- a useful tactic worked once and should become part of the stable capability set
- a mutable skill has become overloaded and a separate focused skill would make dispatch clearer

Do not create a skill just to narrate obvious behavior the base agent already has.
Create one when the file will increase future score, reliability, speed, or synthesis quality.

# Core Loop

Use a lightweight TDD mindset inspired by writing-skills patterns:

1. Notice the failure.
   The agent tries to solve a problem and stalls, performs poorly, or keeps improvising because no skill covers the need.
2. Define the missing capability.
   Name the capability in a way that will be reusable, not tied to one query.
3. Write the skill.
   Add a new `.md` file in `skills/` with superpowers format.
4. Re-run the task with the new skill in play.
   Confirm the new guidance changes behavior in a useful way.
5. Keep the skill only if the system now succeeds more cleanly than before.

The point is not to write documentation.
The point is to change agent behavior and verify that the change helps.

# Skill Format

Follow the superpowers standard exactly:

- YAML frontmatter
- `name`
- `description`
- free-form markdown body

The description is the dispatch mechanism.
Write it so the agent can tell when the skill is relevant before reading the whole file.

The body is a strategy guide, not a bash template.
Prefer decision rules, heuristics, quality bars, and interactions with other skills over rigid step lists.

# Quality Criteria

A new skill is good when it:

- teaches a capability the agent did not previously have in durable form
- changes future decisions, not just wording
- is narrow enough to dispatch reliably
- is general enough to reuse beyond one task
- improves results when actually exercised

Test before committing.
The minimum bar is behavioral evidence that the skill helped on a real task, replay, or focused evaluation.
If the agent still fails in the same way, the skill is not done.

# Commit Workflow

Route skill evolution through git so lineage stays legible.

If the new skill improves performance or unblocks the task:

- keep the file
- `git commit` the change

If the skill does not improve performance, causes regressions, or fails to help:

- discard it with `git revert`

Do not keep failed speculative skill changes around uncommitted as permanent clutter.
The repository history should show which capability mutations helped and which were rejected.

# Naming Guidance

Name skills by capability, not by one-off task phrasing.
Good names make future dispatch obvious:

- `fetch-webpage`
- `search-arxiv`
- `cluster-findings`

Avoid names that only make sense for one session.

# Interaction With Other Skills

Use `discover-environment.md` to notice new tools worth skillifying.
Use `extract-knowledge.md` to turn repeated findings into durable tactics.
Use `observe-user.md` to decide whether a new skill should optimize for this user's workflows.
After creating a skill, actually read and use it before assuming it works.
