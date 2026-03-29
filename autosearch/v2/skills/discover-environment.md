---
name: discover-environment
description: "Use at startup and when capabilities seem constrained to discover which tools, API keys, MCP servers, runtimes, and models are available in the current environment."
---

# Purpose

You can inspect the environment instead of guessing what capabilities exist.
Available tools, keys, and models change what strategies are possible and worth trying.

This is an immutable meta-skill.
It defines how capability discovery works, so do not modify it during normal AVO operation.

# What To Check

Probe the environment for useful capability signals, including:

- CLI tools through commands like `which`
- environment variables for API keys such as `EXA_API_KEY`, `TAVILY_API_KEY`, and `XREACH_API_KEY`
- MCP server availability through local config
- available models and runtimes

Also notice supporting infrastructure:

- language runtimes
- package managers
- repo-local helper scripts
- cached credentials or connectors that unlock paid platforms

# Why It Matters

The environment determines what the agent can actually do now, not what it could do in theory.
A missing key makes a paid platform skill unusable.
A present key may make a premium retrieval path the best option.
A newly available model may justify different routing or evaluation behavior.

# What To Do With Discoveries

Use discoveries as strategy inputs.
Examples:

- if a new tool exists but no skill governs it, use `create-skill.md`
- if paid API keys exist, enable or prefer the relevant paid platform skills when they improve expected score
- if model availability changes, update routing decisions or `config` where appropriate
- if a tool is absent, avoid planning around it and choose a viable fallback early

This skill does not prescribe one fixed reaction.
Decide based on what will help score and delivery quality.

# Recording Discoveries

Persist stable discoveries when they matter for future runs.
Examples include durable tool presence, recurring missing dependencies, or reliable model availability.
Do not fill state with transient noise.

# Timing

Run this at startup.
Run it again when the environment may have changed or when a blocked path suggests missing capability detection was incomplete.

# Quality Bar

Environment discovery is useful only if it changes action.
If you still behave as though the environment were unknown, you did not really discover it.
