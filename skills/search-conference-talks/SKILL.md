---
name: search-conference-talks
description: "Use when the task needs content from ML/AI conference presentations, workshop talks, or keynotes — especially recent conferences whose papers may not be fully indexed yet."
---

# Platform

Conference talks on YouTube — NeurIPS, ICLR, ICML, ACL, AAAI, and other venues upload talk recordings. These contain explanations, demos, and Q&A not found in papers.

# When To Choose It

Choose this when:

- a paper's abstract is not enough to understand the method
- looking for the author's own explanation of their work
- want to find workshop talks that are not formally published
- searching for keynotes and invited talks on a topic

# How To Search

- `site:youtube.com {conference} {year} {topic}`
- Also search conference channels directly

Example queries:
- `site:youtube.com NeurIPS 2025 self-evolving agent`
- `site:youtube.com ICLR 2026 agent memory architecture`
- `site:youtube.com "ICML 2025" reinforcement learning LLM`

# Standard Output Schema

- `source`: `"conference-talk"`

# Date Metadata

YouTube videos have upload dates. Conference talks can be dated by conference year.

# Quality Bar

This skill is working when it discovers talk content (explanations, demos, Q&A insights) that the paper PDF alone does not provide.
