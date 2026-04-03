---
name: consult-reference
description: "Use before modifying or creating a skill to check how other projects solved the same problem, and after scoring to write structured patterns."
---

# Purpose

You have a reference library of 1,009 skills extracted from 16 open-source search projects.
Use it to make informed skill modifications instead of guessing.
Also use it to write structured patterns that future sessions can actually query.

# When To Use It

Use the reference library when:

- you are about to modify a mutable skill and want to know how others handle the same capability
- you are creating a new skill and want proven heuristics as a starting point
- you scored low on a dimension and want to find techniques to improve it
- you want to verify that a proposed change has precedent in real systems

Use the pattern format when:

- you are about to append a lesson to state files after scoring

# How To Use The Reference Library

The reference library is at `state/skill-reference.jsonl`.
Each line is a skill from a real project with a cluster tag.

Workflow:

1. Identify the capability cluster you need (e.g., `result-normalization`, `date-extraction`, `relevance-scoring`)
2. Grep `skill-reference.jsonl` for that cluster
3. Read the matching entries to see which projects implement it
4. For detailed heuristics, see the channel's `SKILL.md` for implementation details
5. Also check `state/unique-patterns.jsonl` for novel approaches specific to individual projects
6. Extract the applicable heuristics and incorporate them into your skill modification

Do not blindly copy.
Evaluate whether the heuristic fits AutoSearch's architecture (skills-as-strategy-guides, not code templates).
Prefer heuristics that are evolvable and measurable over complex multi-step procedures.

# How To Write Patterns

Write new patterns to `state/patterns-v2.jsonl` using this schema:

```json
{
  "id": "p{NNN}",
  "type": "platform|query|skill|scoring|strategy",
  "platform": "github|reddit|hn|exa|hf|web-ddgs|arxiv|twitter|all",
  "pattern": "short name for the pattern",
  "heuristic": "specific actionable rule that a future session can directly apply",
  "outcome": "win|loss",
  "dimension": "quantity|diversity|relevance|freshness|efficiency|latency|adoption|anti-cheat|all",
  "delta": 0.0,
  "session": "session identifier",
  "source": "where this was discovered"
}
```

Rules for writing patterns:

- `heuristic` must be specific enough to apply without context. "Use better queries" is useless. "Add year qualifier to DDGS queries when stale content dominates" is actionable.
- `delta` is the score change. Positive for wins, negative for losses. null if not measured.
- `type` reflects what the pattern is about: platform behavior, query construction, skill modification, scoring mechanics, or search strategy.
- Every pattern should change future behavior. If it would not affect a later search, it is not worth recording.

Also read `state/patterns.jsonl` for historical patterns from earlier sessions. These use varying formats but contain valuable platform-specific knowledge.

# Reference Library Clusters

The 20 capability clusters used in the reference library:

1. query-generation
2. search-execution
3. content-acquisition
4. result-normalization
5. date-extraction
6. relevance-scoring
7. context-management
8. synthesis-delivery
9. answer-evaluation
10. follow-up-generation
11. link-following
12. caching
13. anti-gaming
14. streaming-progress
15. session-management
16. auth-config
17. mcp-integration
18. multi-agent
19. ui-rendering
20. provider-management

# Quality Bar

A good reference consultation results in a specific, evidence-based skill modification.
A bad consultation is browsing without purpose or adopting a heuristic that does not fit the architecture.
