---
name: search-github-code
description: "Use when the task needs concrete implementation examples, API usage patterns, configuration snippets, or real-world code references from GitHub code search."
---

# Platform

GitHub code search through `gh search code`.
This is a free platform skill.

# When To Choose It

Choose this when you need:

- usage examples of an API or library
- implementation patterns across repositories
- config file examples
- evidence for how people actually wire a tool into projects

This is a code-level source, not a repository-ranking source.
Use it when you care about how something is implemented, not just which repo is popular.

# API Surface

This restores the V1 GitHub code connector through GitHub CLI search.

Think in terms of file-level retrieval:

- matched file path
- repository name
- code result URL
- snippet context if available
- branch or default file location context

File path relevance matters as much as textual match.
A hit in `examples/`, `docs/`, `src/`, or framework-specific integration folders is often more useful than a random test file.

# What It Is Good For

GitHub code search is best for:

- finding implementation examples
- learning naming conventions used in the wild
- discovering integration hotspots
- validating whether a technique is common or niche

It is weaker for ranking projects by quality and weaker than issue search for pain-point analysis.

# Quality Signals

Prioritize results with:

- strong repository context, including stars and project credibility
- file paths that indicate real usage, such as `src/`, `examples/`, `integrations/`, or framework adapters
- snippets that show the target API in meaningful context
- repositories whose domain clearly matches the task

Down-rank results when:

- the file path is obviously peripheral, generated, or vendored
- the repo is obscure and low-trust unless the code match is exceptionally precise
- the result appears only in tests without production usage

# Known V1 Patterns

No connector-specific V1 pattern is saved for code search.
Carry over the broader GitHub lesson that direct topic anchors tend to outperform vague prose.
Prefer concrete identifiers, API names, config keys, and filenames over abstract descriptions.

# Rate Limits And Requirements

Requirements:

- GitHub CLI available
- authentication preferred for search stability

Code search is subject to GitHub search limits and can be noisier than repo search.
Keep the query set compact and specific.

# Output Expectations

Return file-shaped evidence.
Each result should normally preserve:

- repository name
- file path
- URL
- short code-context note
- optional repo stars if available from follow-up enrichment

Expect output that helps downstream synthesis answer "how is this actually implemented in practice?"
