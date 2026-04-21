---
name: channels-code-package
description: Source code, issues, and package registries — GitHub repos / code / issues, npm, PyPI, HuggingFace Hub.
layer: group
domains: [code, packages]
scenarios: [find-repo, find-code, find-package, find-model, find-dataset, issue-research]
model_tier: Fast
experience_digest: experience.md
---

# Code & Package Channels

Source code, repositories, issues, discussions, packages, models, datasets.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-github-repos` | Find repositories by topic / description | Fast | free |
| `search-github-code` | Find code snippets across GitHub | Fast | free |
| `search-github-issues` | Find issues / discussions by symptom | Fast | free |
| `search-npm-pypi` | Find Node / Python packages | Fast | free |
| `search-huggingface` | Find models / datasets on HuggingFace Hub | Fast | free |

## Routing notes

- For real-world usage patterns of an API, `search-github-code` beats docs.
- Bug / error-message queries should route to `search-github-issues` + `search-stackoverflow` (in `channels-community-en`).
- ML model discovery: `search-huggingface` for model cards; pair with `search-papers-with-code` in `channels-academic` for benchmarks.
