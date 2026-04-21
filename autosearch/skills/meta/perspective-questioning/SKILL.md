---
name: autosearch:perspective-questioning
description: Generate questions from 3-6 stakeholder / expert personas to expand coverage before searching. Complements decompose-task (which splits by task structure) by splitting by viewpoint. Borrowed from STORM's pre-writing research pattern — asking "what would an investor / a security researcher / an end-user / a maintainer" each want to know.
version: 0.1.0
layer: meta
domains: [workflow, planning]
scenarios: [broaden-coverage, stakeholder-analysis, product-research, competitive-research]
trigger_keywords: [perspective, persona, viewpoint, stakeholder, angle]
model_tier: Best
auth_required: false
cost: free
experience_digest: experience.md
---

# Perspective Questioning — Multi-Persona Question Generation

Before searching, enumerate 3-6 relevant personas for the research topic and ask each persona "what would you want to know?". The union of those questions becomes the research scope.

STORM originally used this for Wikipedia-style article generation. autosearch uses it to widen the coverage of a query before decomposition / channel selection.

## Persona Catalog (starting points)

Runtime AI picks 3-6 from the list that match the query's domain:

- **End user** — what does it feel like? what's the most common pain point?
- **Power user** — edge cases, advanced features, integration patterns.
- **Maintainer** — design tradeoffs, known issues, roadmap.
- **Security researcher** — attack surface, CVEs, hardening.
- **Investor / business analyst** — market position, funding, revenue model.
- **Regulator / compliance** — licensing, data handling, disclosure.
- **Competitor** — differentiation, feature comparison, pricing.
- **New user** — onboarding friction, docs clarity.
- **Journalist** — recent events, controversies, PR statements.
- **Academic** — published research, theoretical basis, citations.

## Output

```yaml
perspectives:
  - persona: "security researcher"
    rationale: "Query involves a new ML framework; attack surface is non-trivial."
    questions:
      - "What authentication mechanism does X use?"
      - "Are there known CVEs or advisories for X?"
      - "Does X have a security policy and disclosure channel?"
  - persona: "end user"
    rationale: "Users are the primary audience of the final report."
    questions:
      - "What's X's learning curve?"
      - "What are the most-complained-about workflows?"
  # ... 1-4 more personas
union_questions: list[str]   # deduped merge of all persona questions
```

## Usage Policy

- Minimum 3 personas, maximum 6. Fewer than 3 → fall back to `decompose-task`. More than 6 → cost not justified for most tasks.
- Skip personas whose rationale is weak. Don't force "Journalist" onto a pure code-architecture query just because the catalog has it.
- **Do NOT generate persona answers here** — this skill only generates the question set. Channel calls + synthesis happen downstream.

## When to Use

- Research topic where the audience has multiple stakeholders with different priorities.
- Product comparison where different user types weight features differently.
- Security / compliance / regulatory topics (where "what would a regulator ask" is genuinely distinct from "what would a user ask").
- New technology assessment (where investor / engineer / researcher perspectives diverge).

## When NOT to Use

- Single-perspective factual queries ("what year was X released?"). Overkill.
- Code / API documentation lookups. One persona (developer) is sufficient.
- Time-critical simple searches — perspective generation costs Best-tier LLM time.

## Cost

Single Best-tier LLM call for persona selection + question generation. Expected latency: 3-6 seconds. Expected token cost: ~1K input / ~1.5K output per run.

## Interactions

- Feeds into → `decompose-task` (combine stakeholder questions with task structure).
- Feeds into → `gene-query` (use persona questions as seed for query variants).
- Complements ← `consult-reference` (run after, to check prior answered persona questions).

## Boss Rules Applied

- `systematic-recall` first — don't ask "what would a security researcher ask about X" if autosearch already knows the canonical security angles for X.
- Best tier only when query complexity justifies it; `research-mode: fast` tasks skip perspective generation.
