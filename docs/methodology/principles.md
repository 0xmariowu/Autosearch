---
title: Evidence Principles — What We Trust and Why
date: 2026-03-23
project: search-methodology
type: principles
tags: [evidence, reliability, methodology, decision-framework]
status: active
---

# Evidence Principles

## Core Rule

**Only trust evidence. Only trust recent evidence.**

- For tool/framework/model selection: evidence must be from **2025-06-01 or later**
- For methodology/principles/patterns: no time limit, but must verify it still holds today
- "I heard" / "people say" / "it's common knowledge" = not evidence

---

## Evidence Channels

Three independent channels. Each has a reliability hierarchy.

### Channel 1: Papers & Articles

Published analysis with methodology and data.

**Reliability tiers:**

| Tier | Source | Weight | Example |
|------|--------|--------|---------|
| **A — Authoritative** | Top venues (NeurIPS, ICML, ACL, EMNLP) + official publications from Anthropic, OpenAI, Google DeepMind, Meta AI, Microsoft Research | Primary evidence | Anthropic's "Constitutional AI" paper |
| **B — Credible** | Lesser-known academic papers, established tech blogs (Simon Willison, Lilian Weng, Chip Huyen), well-known engineering blogs (Stripe, Vercel, Supabase) | Supporting evidence | A pre-print on arXiv with solid methodology |
| **C — Supplementary** | Unknown authors, personal blogs, Medium posts, tutorials | Supplement only — never sole basis for a decision | Random dev.to post about "my experience with X" |

**Evaluation criteria:**
1. Does it show methodology, not just conclusions?
2. Are results reproducible?
3. Does the author have skin in the game (selling something)?

### Channel 2: Tool Chains

Open-source tools, libraries, frameworks on GitHub, HuggingFace, npm, PyPI.

**Reliability tiers:**

| Tier | Signal | Weight | Example |
|------|--------|--------|---------|
| **A — Established** | 1K+ stars + active maintenance (commits in last 30 days) + real issues being addressed | Primary evidence | LangChain, Pydantic AI, tldraw |
| **B — Emerging** | 100-1K stars, OR backed by known org, OR solves unique problem no A-tier covers | Supporting evidence | A new framework by ex-Google engineers with 300 stars |
| **C — Experimental** | <100 stars, solo maintainer, no production users visible | Supplement only — evaluate code quality directly | Random GitHub repo with interesting approach |

**Evaluation criteria:**
1. Stars alone are unreliable — check: recent commit frequency, issue response time, contributor count
2. A repo with 5K stars and no commits in 6 months < a repo with 200 stars and weekly releases
3. Check dependents: who actually uses this in production?

### Channel 3: User Feedback

Community discussions, complaints, success stories.

**Reliability tiers:**

| Tier | Source | Weight | Example |
|------|--------|--------|---------|
| **A — Detailed** | Specific experience with reproducible details, engagement > 50 | Primary evidence | "After 6 months with X, here's what broke: [specific list]" with 200 upvotes |
| **B — Corroborated** | Multiple independent users reporting the same thing, even without detail | Supporting evidence | 5 different Reddit posts about the same bug |
| **C — Anecdotal** | Single user, no details, or low engagement | Supplement only | "X sucks" with 3 upvotes |

**Evaluation criteria:**
1. Specificity: "it doesn't work" < "it fails when context exceeds 50K tokens on multi-file edits"
2. Independence: 5 people in the same thread agreeing ≠ 5 independent reports
3. Recency: community sentiment shifts fast — check dates

---

## Reliability Formula

```
Reliability = Channel_Count × Evidence_Quality

Channel_Count:
  1 channel  → supplement only (don't base decisions on this)
  2 channels → credible (can act on this with caution)
  3 channels → high confidence (act on this)

Evidence_Quality (per channel):
  A-tier evidence → weight 3
  B-tier evidence → weight 2
  C-tier evidence → weight 1

Score = sum of weights across channels
  ≥ 7 → strong evidence (act confidently)
  4-6 → moderate evidence (act with noted caveats)
  1-3 → weak evidence (explore further before acting)
```

### Examples

**Strong (score 9):** Anthropic paper says X (A=3) + LangChain implements X with 5K stars (A=3) + Reddit top post confirms X works (A=3)

**Moderate (score 5):** arXiv pre-print says X (B=2) + new tool implements X with 200 stars (B=2) + one HN comment mentions X (C=1)

**Weak (score 3):** Blog post says X (C=1) + GitHub repo with 50 stars (C=1) + one Reddit complaint (C=1) → explore further, don't decide yet

---

## Anti-Patterns: What Is NOT Evidence

| Trap | Why It Fails | What To Do Instead |
|------|-------------|-------------------|
| **Appeal to popularity** | 10K GitHub stars ≠ best solution. TensorFlow > JAX in stars, but many frontier labs use JAX | Check what the top practitioners actually use, not what's most popular |
| **Appeal to recency** | "Just released" ≠ better. New tools often have undiscovered bugs | Wait for Channel 3 feedback before adopting |
| **Appeal to authority** | "Google uses X" ≠ X is right for us. Google's scale ≠ our scale | Evaluate if their constraints match ours |
| **Survivorship bias** | "X worked for company Y" ignores all companies where X failed | Search for failure reports, not just success stories |
| **Single-source trust** | One great blog post ≠ truth. The author may be wrong or selling | Cross-validate with Channel 2 (does working code exist?) and Channel 3 (do real users confirm?) |
| **Outdated evidence** | A benchmark from 2024 is almost certainly wrong for 2026 models | Check date. If tools/models: must be post 2025-06-01 |

---

## Decision Framework

When choosing between options (tool A vs B, approach X vs Y):

### Step 1: Gather evidence from all 3 channels

For each option, search:
- Papers/articles: what do researchers/authors say?
- Tool chains: what exists? how active? who uses it?
- User feedback: what do practitioners report?

### Step 2: Score each option

Use the reliability formula. Compare scores.

### Step 3: Check for disqualifiers

A single **strong negative** can outweigh many positives:
- Security vulnerability with no fix → disqualify
- Maintainer abandoned project → disqualify
- Fundamental architecture mismatch with our stack → disqualify

### Step 4: Present with evidence

Never recommend without showing the evidence chain:
```
RECOMMENDATION: X
- Paper: [source] says X outperforms Y by 30% on [benchmark]
- Tool: X has 2K stars, 15 contributors, weekly releases
- Users: 3 independent Reddit posts confirm X works for [our use case]
- Score: 8/9 (strong)

ALTERNATIVE: Y
- Paper: no direct comparison found
- Tool: Y has 500 stars, 2 contributors, last commit 45 days ago
- Users: 1 blog post, positive but no details
- Score: 4/9 (moderate)
```

---

## When Evidence Is Absent

Sometimes there's no evidence for any option. This is common for emerging techniques.

**Protocol:**
1. Acknowledge the gap explicitly: "No evidence found for X in any channel"
2. Check Armory (`search_patterns`) — maybe prior art exists under a different name
3. If still nothing: propose a small-scale test (pilot with 50 cases, not 5000)
4. If test is not feasible: flag as Ocean-scope (see CLAUDE.md § Completeness Principle)

**Never fill an evidence gap with AI speculation.** "I think X would work because..." is not evidence. It's a hypothesis — label it as such.

---

## Maintenance

- This file is the **highest authority** in the search-methodology directory
- Changes require **user approval** — AI proposes, user decides
- When new evidence channels emerge, append to § Evidence Channels
- When anti-patterns are discovered, append to § Anti-Patterns
- Annual review: revisit the time threshold in § Core Rule. Current value: 2025-06-01. Update when model/tool landscape has shifted significantly
