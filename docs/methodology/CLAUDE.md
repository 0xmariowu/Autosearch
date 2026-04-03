# Search Methodology — AI Operations Manual

> Read this before any search-related work.
> This directory holds the **principles, methods, and platform knowledge** for finding high-quality resources.
> It is knowledge, not code. AutoSearch code lives in this repository.

---

## What This Is

A self-improving knowledge base for resource discovery. Three layers:

1. **Principles** — what counts as evidence, how to judge reliability
2. **Methods** — specific techniques for finding resources (e.g., reverse fingerprint search)
3. **Platforms** — per-platform patterns validated through actual use

---

## Directory Structure

```
search-methodology/
├── CLAUDE.md              ← this file (AI operations manual)
├── INDEX.jsonl            ← grep-able index of all files
├── CHANGELOG.md           ← what changed, when, why
├── principles.md          ← evidence standards + reliability framework
├── methods/               ← search techniques (one file per method)
│   └── {YYYY-MM-DD}-{name}.md
├── platforms/             ← per-platform validated patterns
│   └── {platform-name}.md
└── _archive/              ← superseded files, never delete
```

---

## Truth Hierarchy

```
principles.md              ← HIGHEST: governs all search decisions
methods/*.md               ← specific techniques, must align with principles
platforms/*.md             ← execution knowledge, feeds back into methods
INDEX.jsonl                ← derived index (update after every write)
CHANGELOG.md               ← derived log (update after every write)
```

When principles conflict with a method or platform pattern, principles win. Update the method/platform, not the principles (unless new evidence warrants a principles revision — which requires user approval).

---

## Read Protocol: Before Any Search Task

1. Read `principles.md` — know what counts as reliable evidence
2. Scan `INDEX.jsonl` — check if a relevant method already exists
3. Read the relevant `methods/*.md` — don't reinvent
4. Read relevant `platforms/*.md` — know what works on each platform

**Do NOT skip step 1.** Principles override everything.

---

## Write Protocol: Adding a New Method

**Trigger**: AI discovers a new search technique that produces results not achievable with existing methods.

### Step 1: Create the file

**Path**: `methods/{YYYY-MM-DD}-{method-name}.md`

**Frontmatter** (all fields required):

```yaml
---
title: descriptive title
date: YYYY-MM-DD
project: search-methodology
type: method
platforms: [github, reddit, exa, ...]  # which platforms this method uses
precision: high | medium | low         # false positive rate
yield: high | medium | low             # volume of useful results
tags: [relevant, keywords]
status: active | draft | superseded
---
```

### Step 2: Write the content

**Required sections** (follow this structure):

```markdown
## Problem
What existing search methods cannot find, and why.

## Core Insight
The non-obvious idea that makes this method work. One paragraph max.

## Method
Step-by-step instructions. Include actual search queries.
Must be specific enough that an AI can execute it without asking questions.

## Results
What this method found. Include numbers: repos found, unique users, data volume.
Compare against baseline (what you'd get without this method).

## Limitations
False positive rate, rate limits, ethical considerations, decay risk.

## Appendix: Full Query List (if applicable)
Copy-pasteable commands.
```

### Step 3: Update indexes

1. **Append to INDEX.jsonl**:
```json
{"date":"YYYY-MM-DD","type":"method","name":"method-name","platforms":["github"],"precision":"high","yield":"high","tags":["tag1","tag2"],"status":"active","file":"methods/YYYY-MM-DD-method-name.md","summary":"one-line description"}
```

2. **Prepend to CHANGELOG.md**:
```markdown
## YYYY-MM-DD
### New Method: {title}
- **Added**: `methods/{filename}`
- **Why**: {what gap this fills}
- **Impact**: {what new resources this unlocks}
```

3. Update any repo-local index that tracks this methodology directory.

### Step 4: Cross-update

- If the method involves a platform not yet documented → create `platforms/{name}.md`
- If the method changes how we evaluate reliability → flag for `principles.md` review (do NOT auto-update principles)

---

## Write Protocol: Updating Platform Knowledge

**Trigger**: AutoSearch session produces new patterns, or manual search reveals platform-specific insight.

### Step 1: Edit the platform file

**Path**: `platforms/{platform-name}.md`

Append new findings to the `## Validated Patterns` section with date.

### Step 2: Update indexes

1. **If new file**: append to INDEX.jsonl
2. **Always**: prepend to CHANGELOG.md
3. **If new file**: update any repo-local index that tracks this methodology directory

### Step 3: Source tracking

Every platform pattern MUST include:
- **Date validated**: when this was tested
- **How validated**: what search produced this finding
- **Confidence**: single test / multiple tests / systematic (AutoSearch post-mortem)

Unvalidated tips are not patterns. They go in a `## Unvalidated` section until tested.

---

## Write Protocol: Updating Principles

**This requires user approval.** AI may propose changes but MUST NOT auto-commit.

Process:
1. AI identifies new evidence that challenges or extends current principles
2. AI presents the evidence and proposed change to user
3. User approves → AI updates `principles.md` + CHANGELOG.md
4. User rejects → AI records the discussion in CHANGELOG.md for future reference

---

## AI Behavior Rules

### Automatic (do these without asking)

| Trigger | Action |
|---------|--------|
| Starting any search task | Read `principles.md` first |
| AutoSearch session completes | Check if `platforms/*.md` needs update based on new `patterns.jsonl` entries |
| Found a resource | Evaluate against principles.md reliability framework before recommending |
| New search technique discovered | Write `methods/` file + update indexes |
| Method produces zero results 3x | Add `## Known Failures` section with dates and queries tried |

### Requires User Approval

| Trigger | Action |
|---------|--------|
| Evidence contradicts `principles.md` | Present evidence, propose change, wait for approval |
| Method should be superseded | Propose moving to `_archive/`, wait for approval |
| New evidence channel discovered | Propose adding to `principles.md` channels |

---

## Staleness Rules

| Content | Stale after | Action |
|---------|-------------|--------|
| Platform patterns | 30 days without re-validation | Mark `[STALE]`, re-test before trusting |
| Methods | 60 days without use | Review — the platform may have changed |
| Principles | Never auto-stale | Only user can revise |
| CLAUDE.md (ops manual) | Never auto-stale | Only user can revise (same governance as principles) |
| INDEX.jsonl entries | Derived — matches source files | If mismatch, source file wins |

---

## Do NOT

- Auto-update `principles.md` without user approval — principles are governance, not data
- Store search results or raw findings here — keep this directory focused on methodology docs
- Duplicate AutoSearch code documentation — keep code-level docs with the code they describe
- Delete any file — supersede to `_archive/` instead
- Skip index updates — INDEX.jsonl and CHANGELOG.md are how future sessions find your work
- Write unvalidated patterns as if they were validated — use `## Unvalidated` sections
- Trust platform patterns older than 30 days without re-testing
