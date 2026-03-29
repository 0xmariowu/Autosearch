---
name: provider-health
description: "Use at session start and after provider runs to skip cooling-down platforms and prioritize providers that are producing fresh URLs cleanly."
---

# Purpose

Track which providers are healthy enough to trust right now.
Provider choice should respond to recent outcomes, not stay fixed.

# State File

Write append-only records to `state/provider-health.jsonl`.
Do not rewrite history.

Each record should capture enough context to explain the status:

- timestamp
- provider name
- query family if known
- attempts
- errors
- error rate
- new unique URLs
- new URL rate
- assigned status
- short reason

# Status Rules

Use these exact status conditions:

- `cooldown` if `error_rate >= 0.70` and no new URLs were produced
- `preferred` if there were `0` errors and `new_url_rate >= 0.08`
- `active` otherwise

Treat status as recent operational guidance, not eternal truth.

# How To Use Status

At session start:

- skip `cooldown` providers unless the task requires them or no viable alternative exists
- prioritize `preferred` providers early in the run
- use `active` providers as normal backup capacity

After each provider run, append a fresh health record so routing can improve within the same session.

# Scope Of Health

Track health globally first.
If query-family behavior is obviously different, record it separately rather than flattening everything into one number.
A provider can be excellent for code discovery and weak for discussion discovery.

# What Counts As A Failure

Count actual operational failures:

- request errors
- auth failures
- empty or malformed responses
- zero-yield runs caused by provider malfunction

Do not confuse "provider returned relevant but few results" with "provider is broken."
Health is about reliability plus incremental discovery, not just score contribution.

# Routing Heuristics

Preferred providers should usually receive the first query budget.
Active providers fill the rest of the portfolio.
Cooldown providers should be probed sparingly and only when needed for coverage, freshness, or unique source type.

If two providers are equally healthy, favor the one that matches the query family and recent winning patterns.

# Recovery

Cooldown is not permanent.
Probe a cooling-down provider later if:

- enough time has passed
- credentials changed
- the task specifically needs that provider class
- other providers are saturating

When a cooldown provider starts producing clean new URLs again, let recent evidence lift it back to `active` or `preferred`.

# Quality Bar

Provider selection should become more efficient over time.
Do not waste rounds retrying a provider that is both error-prone and failing to add new evidence.
