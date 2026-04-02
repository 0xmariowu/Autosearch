---
name: github-repos
description: "Use this channel when the query is best answered by GitHub repositories ranked with repo metadata such as stars, language, and update time."
categories: [developer]
platform: github.com
api_key_required: false
aliases: []
---

## When to use

Use when you want open source projects, libraries, frameworks, or example repos on GitHub.

## Quality signals

- High star count with recent updates
- Repository description that matches the query intent
- Language and repo name aligned with the task

## Known limits

- Requires the `gh` CLI to be installed and authenticated
- Ranking is biased toward popular repositories
- Description text can be missing or short
