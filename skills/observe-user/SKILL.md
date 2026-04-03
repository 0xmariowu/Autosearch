---
name: observe-user
description: "Use at startup and whenever context shifts to learn the user's preferences, current project state, and likely success criteria from local context and conversation."
---

# Purpose

You can understand the user by reading the artifacts around the task, not just the last prompt.
This is how you infer what kind of answer, platform choice, and delivery style will actually satisfy them.

This is an immutable meta-skill.
It defines how user context is learned, so do not modify it during normal AVO operation.

# What To Read

Read whatever local context is most likely to sharpen your model of the user, including:

- `CLAUDE.md` for role, preferences, project rules, output expectations, and workflow norms
- the relevant project directory to infer stack, architecture, priorities, and current work shape
- recent git history to see what changed recently and what the user may be focused on
- the current conversation to recover intent, constraints, corrections, and unstated quality bar

Do not assume all of these matter equally every time.
Choose the observations that help the current task.

# What To Look For

Observe for signals such as:

- what the user is trying to achieve right now
- how technical or concise the response should be
- whether they prefer breadth, synthesis, implementation detail, or speed
- which platforms, sources, or tools fit the repo and the user's habits
- whether the project values experimentation, rigor, low cost, freshness, or coverage

This skill does not prescribe a fixed checklist of observations.
Figure out what would actually improve the next decision.

# How To Store Observations

Write reusable observations into `state/` files when they may matter beyond the current turn.
Store them in a form that future generations can reuse without rereading the whole session.

Good stored observations are:

- concise
- attributable to a source such as `CLAUDE.md`, git history, or user message
- actionable for future routing or delivery decisions
- stable enough to reuse until contradicted

Ephemeral trivia does not need persistence.

# How To Use Observations

Use observed context to influence:

- platform selection
- query strategy
- research depth
- source trust thresholds
- delivery format and level of synthesis
- when to ask clarifying questions versus acting immediately

The goal is not to build a biography of the user.
The goal is to choose better actions.

# Updating The Model

Treat user understanding as revisable.
When the user corrects you, changes direction, or reacts strongly to an output style, update your internal model and any persistent notes that should change.

Do not let stale assumptions dominate later rounds.

# Quality Bar

This skill is working if it changes behavior in useful ways:

- better source choice
- fewer unnecessary questions
- more relevant synthesis
- delivery in a format the user actually uses

If reading context does not influence action, you did not really observe the user.
