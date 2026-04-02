---
name: github-issues
description: "Finds GitHub issue threads with bug reports, feature requests, and repository-specific technical discussions."
categories: [developer]
platform: github.com
api_key_required: false
aliases: []
---

## Content types

GitHub issues and issue-like discussion threads inside repositories. The content is mostly bug reports, feature requests, reproducible errors, maintainer replies, and workaround discussions tied to a specific codebase.

## Language

Mostly English. Other languages appear, but English dominates both titles and discussion, so English error strings and API terms usually work best.

## Best for

Specific error messages, edge cases, regressions, compatibility problems, and implementation questions that are likely to have already been discussed by users or maintainers. It is especially good when the problem mentions a concrete library, tool, or repo.

## Blind spots

It is not a general knowledge source and does not cover topics that were never discussed inside a repository. It also misses solutions that only exist in docs, PRs, commit history, Stack Overflow, or chat platforms.

## Quality signals

Issues in the right repository matter more than raw keyword overlap. Open issues with many comments usually indicate active discussion, while clear reproduction steps, maintainer participation, and references to fixes or workarounds make a result more useful.
