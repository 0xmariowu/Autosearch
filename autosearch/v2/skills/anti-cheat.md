---
name: anti-cheat
description: "Use after scoring and before accepting results to reject novelty collapse and other score-gaming patterns."
---

# Purpose

A higher score is not enough if the bundle is gaming the judge.
Run this skill before accepting any candidate result set, especially in multi-round loops.

# Inputs

Compare the candidate bundle to the previously accepted bundle when possible.
Look at bundle-level metrics, not isolated anecdotes.
At minimum, inspect:

- `novelty_ratio`
- `new_unique_urls`
- `source_diversity`
- `source_concentration`
- `query_concentration`

Also inspect domain concentration and title repetition when the bundle feels suspicious.

# Hard Fail Rules

Reject the candidate bundle immediately if either condition is true:

- `novelty_ratio < 0.01`
- `new_unique_urls == 0`

These mean the loop is mostly recycling known URLs instead of discovering meaningfully new evidence.

# Warning Rules

Do not hard-fail on warnings alone, but treat them as serious pressure to diversify:

- `source_diversity < 0.15`
- `source_concentration > 0.82`
- `query_concentration > 0.70`

Warnings mean the bundle may be overfit to one provider or one query frame even if it technically found something new.

# How To Interpret The Metrics

`novelty_ratio` asks whether the round added new URLs relative to the accepted bundle.
`new_unique_urls` asks whether any genuinely new evidence appeared at all.
`source_diversity` is Simpson diversity across sources.
`source_concentration` reveals whether one source dominates the bundle.
`query_concentration` reveals whether one query contributed too much of the bundle.
Title repetition and domain concentration catch near-duplicate spam that URL dedupe alone can miss.

# Response Strategy

If there is a hard fail:

- reject the candidate bundle
- do not treat the round as progress
- mutate toward novelty, not more of the same

If there are warnings:

- accept only if the score improvement is real and the bundle is still materially useful
- carry the warnings into the next round plan
- diversify providers, domains, or query families immediately

# Typical Fixes

Use warning patterns to choose the next action:

- low novelty -> new query family, not just a modifier
- low source diversity -> add a different provider class
- high source concentration -> cap overproductive providers
- high query concentration -> widen the query set
- high title repetition -> force stricter dedupe and different framing

# Recording

Carry the metric values and any failures or warnings into the worklog or reflection record.
A future session should be able to see whether the loop was healthy, not just whether it scored well.

# Quality Bar

This skill protects against false progress.
If the bundle is only inflating count, relevance, or diversity mechanically, reject it and search differently.
