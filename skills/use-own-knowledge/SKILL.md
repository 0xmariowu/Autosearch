---
name: use-own-knowledge
description: "Use when the topic includes foundational ideas, established literature, or durable design patterns that Claude already knows and can contribute without waiting on search."
---

# Purpose

You are Claude.
Your training knowledge is a real research source, especially for foundational works, durable concepts, and older context that search APIs may surface poorly.

Do not wait to "search" for things you already know well.
Use your own knowledge to accelerate framing, gap detection, and synthesis.

# When To Use It

Use this whenever the topic touches established areas where prior knowledge is likely to be strong, including:

- foundational papers and methods
- well-known researchers and labs
- long-running design patterns
- classic failure modes
- durable conceptual frameworks

Examples include topics around STaR, Reflexion, Voyager, DSPy, agent evaluation, prompting patterns, and similar well-established material.

# Core Strategy

Start by listing what you already know about the topic from training.
Do this before or alongside external search so you have a working map of the field.

Then identify what you do not know or should not trust from memory alone, such as:

- recent projects
- newly released models or tools
- current community discussion
- fresh benchmarks
- time-sensitive adoption signals

Search for those unknowns.
Do not waste search budget rediscovering background concepts you can already explain.

# How To Use Your Knowledge Well

Use internal knowledge to:

- propose initial entities, terms, and hypotheses
- recognize seminal work that newer blogs may omit
- connect concepts across domains
- spot when search results are shallow, derivative, or missing key history
- frame the field in a way that supports decision-making

Be explicit about the boundary between durable background knowledge and time-sensitive claims.
If a fact could have changed recently, verify it externally.

# Merging With Search

The final output should blend both sources:

- your knowledge provides framework, continuity, and older foundations
- search provides freshness, specific evidence, and current developments

Use each for what it is best at.

# Failure Modes

Do not let memory replace verification for unstable facts.
Do not produce a confident list of classics and then ignore what recent evidence says.
Do not flatten the answer into a generic survey when the user needs current actionable insight.

# Quality Bar

This skill is working when your report has both depth and freshness:

- depth from internal knowledge
- freshness from search
- synthesis from combining them instead of treating them as separate tracks
