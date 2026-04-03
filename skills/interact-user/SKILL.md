---
name: interact-user
description: "Use when progress depends on dialogue, including clarifying ambiguous intent, showing intermediate findings during long searches, and collecting feedback after delivery."
---

# Purpose

You can communicate with the user during search.
Dialogue is part of the research loop, not a separate layer.

This is an immutable meta-skill.
It defines how user interaction feeds the search process, so do not modify it during normal AVO operation.

# When Interaction Helps

Interaction is useful in at least these cases:

- ambiguous intent: ask one clarifying question
- long or multi-round search: show intermediate results so direction can be corrected early
- after delivery: ask for feedback so the system learns what was adopted or rejected

Do not ask a stack of questions when one will resolve the main ambiguity.
Preserve momentum unless the uncertainty is material.

# Clarifying Questions

When intent is ambiguous, ask exactly one question that most reduces uncertainty.
Make it decision-relevant:

- target definition
- depth or scope
- timeframe
- preferred output shape

Avoid questions whose answers you could infer from context or handle through reasonable defaults.

# Intermediate Updates

During long searches, report progress before the user has to ask.
Show what direction the evidence is taking and what tradeoffs are emerging.
Intermediate updates are not mini-final-answers.
They are checkpoints that let the user redirect early if needed.

# Interpreting Responses

Treat user responses as control signals:

- refinement means direction changed; update queries, scope, or evaluation criteria
- acceptance means stop exploring that branch and move toward completion
- rejection means the approach, source mix, or framing is wrong and should change

Do not argue with the signal.
Use it to improve the next move.

# Feedback Recording

Record useful post-delivery feedback in `state/adoption.json` for `judge.py`.
Capture whether the user adopted, partially adopted, or rejected the output when that signal is available.
Store only what will help later scoring and behavior.

# Style

Keep interaction efficient.
The point is to accelerate convergence, not to create conversational overhead.

# Quality Bar

Interaction is working when it reduces wasted search, sharpens the target, or produces a delivery the user actually adopts.
If dialogue adds latency without changing the plan, it was unnecessary.
