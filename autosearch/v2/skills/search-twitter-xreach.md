---
name: search-twitter-xreach
description: "Use when the task explicitly needs the direct XReach Twitter/X connector through mcporter, but treat it as a fragile source and validate its health before trusting it."
---

# Platform

XReach API through `mcporter`.
This is a paid platform skill.

# When To Choose It

Choose this only when you specifically want:

- direct Twitter/X search from the native connector path
- native social retrieval behavior rather than web-indexed Twitter pages

This should not be the default Twitter/X route.
Use it as a probe or fallback only if direct X-specific retrieval is required.

# API Surface

This restores the V1 XReach connector through `mcporter`.

Treat it as native Twitter/X retrieval when healthy.
Expected result shapes may include:

- tweet or post URL
- account identity
- text snippet
- created time
- engagement metadata if the connector provides it

# What It Is Good For

In principle, XReach is good for:

- direct Twitter/X search
- account-level or post-level discovery
- engagement-aware social signal

In practice, V1 evidence says reliability was poor.

# Quality Signals

If the connector is healthy, prioritize results with:

- clear relevance in the text
- recognizable accounts
- recency when the topic is time-sensitive
- engagement metrics when available

Down-rank or reject runs when:

- the connector returns empty results across varied reasonable queries
- results are malformed
- retrieval quality is obviously below the Exa `site:twitter.com` path

# Known V1 Patterns

Pattern already validated in state:

- XReach returned empty results for all tested query types in V1.
- The saved recommendation was to prefer Exa with `site:twitter.com`.

That means this connector starts in a skeptical posture.
Check provider health and be ready to abandon it quickly.

# Rate Limits And Requirements

Requirements:

- `XREACH_API_KEY`
- `mcporter` available

This is a paid API route.
Because reliability is uncertain, keep probing lightweight and do not spend heavily before the connector proves healthy in the current session.

# Output Expectations

Return native social evidence only if the connector is producing real results.
Each result should normally preserve:

- URL
- account
- text snippet
- created time
- engagement if available
- short relevance note

If the connector is empty or unstable, treat that as provider-health evidence and route Twitter/X discovery to `search-twitter-exa.md` instead.
