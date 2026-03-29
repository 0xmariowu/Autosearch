---
name: fetch-webpage
description: "Use when snippets are insufficient and you need the full content of an article, README, documentation page, or post for deeper reading and knowledge extraction."
---

# Purpose

Search snippets are often enough to rank, but not enough to learn.
Use this skill when you need the full page content so `extract-knowledge.md` can mine it properly.

# When To Use It

Fetch the full page when:

- the snippet suggests high relevance but lacks detail
- you need the actual argument, method, code example, or limitation section
- a README or docs page likely contains implementation detail not visible in search results
- two sources appear to contradict each other and the snippet is too shallow to resolve it

Do not fetch everything.
Fetch the pages whose full text is likely to change your understanding.

# Retrieval Methods

Prefer the best available method in the current environment:

- a native WebFetch tool if available in Claude Code
- Jina Reader via `https://r.jina.ai/{url}`
- `curl` plus readability-style extraction when other options are unavailable

Choose the path that yields clean readable content with minimal noise.

# Output Shape

Aim to produce clean markdown or similarly readable text.
Preserve the important structure:

- title
- headings
- paragraphs
- lists
- code blocks when they matter

Strip obvious navigation chrome, unrelated UI text, and duplicate boilerplate where possible.

# What To Store

Store the fetched content in a durable working artifact so later skills can reuse it without refetching.
Keep enough metadata to trace provenance:

- source URL
- fetch method
- fetch time
- cleaned content

Make the stored content easy for `extract-knowledge.md` to process.

# How It Interacts With Other Skills

Use this after search skills identify promising URLs.
Pass the cleaned content into `extract-knowledge.md`.
Use the extracted lessons to inform `synthesize-knowledge.md`.

# Failure Modes

Do not confuse raw HTML with usable content.
Do not fetch a page, glance at the first paragraph, and call the job done.
Do not let boilerplate or layout noise pollute downstream extraction.

# Quality Bar

This skill is successful when a previously shallow result becomes readable enough to support real understanding, citation, or extraction.
