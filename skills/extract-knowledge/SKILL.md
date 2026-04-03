---
name: extract-knowledge
description: "Use after scoring or deep reading to pull reusable knowledge from high-quality results and store it so future searches on the topic become smarter."
---

# Purpose

You can learn from search results, not just cite them.
After good results appear, convert them into reusable knowledge that improves later retrieval, evaluation, and synthesis.

This is an immutable meta-skill.
It defines how evidence turns into retained knowledge, so do not modify it during normal AVO operation.

# When To Use It

Use this after scoring identifies strong results or after fetching full content from especially promising sources.
Prioritize the top results, the diverse results, and the results that changed your understanding of the topic.

Do not spend extraction effort on obvious junk.

# What To Extract

Extract whatever is most useful for future reasoning, such as:

- entities
- relationships
- recurring patterns
- decision criteria
- architectures
- contradictions
- open questions
- missing evidence

This skill does not prescribe a fixed ontology.
Discover what matters in the domain and capture that.

# How To Think About Extraction

Read past the headline.
Look for what the result teaches you about the space:

- who the important actors are
- what mechanisms recur
- where people disagree
- what terms, synonyms, or abstractions unlock better follow-up search
- which gaps remain unresolved

Prefer information that changes future search behavior over information that merely decorates a summary.

# How To Store It

Append reusable findings to appropriate `state/` files so later generations can load them without re-reading every source.
Store knowledge in a way that preserves enough context to trust and reuse it:

- what was learned
- where it came from
- why it matters
- when it may need refreshing

Use append-only habits for historical learning.
Do not erase old lessons just because a new source disagrees; record the contradiction.

# How To Use It Later

Use extracted knowledge to:

- inform future searches on the same topic
- refine queries with better entities and terms
- recognize duplicates or low-value results faster
- build domain expertise over time
- improve final synthesis by grounding it in accumulated structure instead of fresh snippets alone

Extraction is not a post-processing luxury.
It is how the system becomes smarter across iterations.

# Quality Bar

Good extraction changes what you do next.
If the stored knowledge would not affect a later query, reading choice, or synthesis decision, extract something deeper.
