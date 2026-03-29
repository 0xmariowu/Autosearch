# /autosearch — Self-Evolving Research Agent

Run an AutoSearch v2.2 research session. Read `autosearch/v2/PROTOCOL.md` as your operating system.

## Arguments

$ARGUMENTS — the research task (e.g., "find AI agent frameworks", "research vector databases", "comprehensive survey of self-evolving agents")

If no arguments provided, ask the user what to research.

## Execution

1. Read `autosearch/v2/PROTOCOL.md` — follow it as your operating protocol
2. Follow the protocol's startup sequence (crash recovery, patterns, discover-environment, observe-user)
3. You are the AVO variation operator — you decide what to do, which skills to use, when to score, when to deliver
4. You are Claude — your training knowledge is a source alongside search results (read use-own-knowledge.md)
5. Deliver conceptual frameworks and insights, not URL lists (read synthesize-knowledge.md)
6. Use Python 3.11+ for judge.py

## Key constraints

- judge.py is the only evaluator — run it, never self-assess
- State files are append-only
- Config/skill changes go through git commit/revert
- Read the relevant skill before executing any capability
