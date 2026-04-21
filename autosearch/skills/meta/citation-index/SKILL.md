---
name: autosearch:citation-index
description: Deduplicate URLs across all sources, assign stable citation numbers, and merge citations from multiple subagents / sections into one consistent reference list. Prevents "same URL cited as [3] in one paragraph and [17] in another" and "different URLs merged under [5]" bugs that come from per-section synthesis.
version: 0.1.0
layer: meta
domains: [workflow, synthesis, quality]
scenarios: [report-synthesis, multi-section-citations, subagent-merge, reference-deduplication]
trigger_keywords: [citation, reference, index, dedupe urls, [1] [2], bibliography]
model_tier: Standard
auth_required: false
cost: free
experience_digest: experience.md
---

# Citation Index — Stable URL-to-Number Map

Borrowed from STORM's `StormArticle.url_to_unified_index` + deepagents `research_agent/prompts.py` citation consolidation. Keeps citations stable across report sections and subagent outputs.

## State

```yaml
citation_index:
  entries:
    # URL (canonicalized) → entry
    "https://arxiv.org/abs/2401.12345":
      number: 1
      title: "First paper title"
      first_seen_section: "introduction"
      used_in_sections: ["introduction", "background", "method"]
      source_channel: "search-arxiv"
    "https://github.com/foo/bar/issues/42":
      number: 2
      title: "Issue: memory leak"
      first_seen_section: "implementation-notes"
      used_in_sections: ["implementation-notes"]
      source_channel: "search-github-issues"
  next_number: 3
```

## URL Canonicalization Rules

Before indexing, normalize the URL:

1. **Strip tracking params**: `utm_*`, `gclid`, `fbclid`, `ref=`, `source=`.
2. **Strip fragments** (`#section-1`) unless the URL is an anchor-addressed resource (e.g. docs page).
3. **Lowercase host** but keep path case.
4. **Collapse multiple slashes** (`//` → `/`) except for the scheme.
5. **Platform-specific**:
   - YouTube: `watch?v=ID` form is canonical; strip `list=` playlist params.
   - arXiv: strip version suffix for de-dup (`v2` → `""`); keep title for reference.
   - GitHub issues: canonicalize `githubissues.com/X/Y/Z` to `github.com/X/Y/issues/Z`.

Different URL canonicalizations → different citation numbers. A URL that points to the same resource but failed canonicalization is a bug; log it and merge.

## Write Path

When a subagent / section outputs evidence:

```python
for ev in evidence:
    url = canonicalize(ev.url)
    if url not in index.entries:
        index.entries[url] = Entry(
            number=index.next_number,
            title=ev.title,
            first_seen_section=current_section,
            used_in_sections=[current_section],
            source_channel=ev.source_channel,
        )
        index.next_number += 1
    else:
        if current_section not in index.entries[url].used_in_sections:
            index.entries[url].used_in_sections.append(current_section)
```

## Read Path

When rendering a section body, replace inline citation markers with the assigned number:

- Input from runtime AI: `... as shown in [ref: arxiv.org/abs/2401.12345] ...`
- After indexing: `... as shown in [1] ...`
- References section at end: `[1] Title. URL.`

## Merge Rule (Subagent Consolidation)

When merging N subagent outputs:

1. Collect all evidence URLs across all subagents.
2. Canonicalize and dedupe.
3. Assign numbers in stable order (first-seen wins; use subagent order as tie-break).
4. Rewrite each subagent's inline `[ref: ...]` tags to the final numbers.

## Failure Modes

- Malformed URL in evidence — log and skip; don't crash the whole index.
- Duplicate title with different URLs (e.g. "paper.pdf" published on two mirrors) — keep both; this is user judgment, not ours to merge without data.

## When to Use

- Final report synthesis (always).
- Multi-subagent merge (always).
- Single-section simple answer — skip, overkill.

## Cost

Cheap — mostly bookkeeping. No LLM calls unless resolving ambiguous cases (e.g. "are these two URLs the same resource?"). Runtime AI typically never needs to consult an LLM for citation indexing.

## Interactions

- Fed by → all channel skills + `delegate-subtask` output.
- Feeds → `synthesize-knowledge` (which produces the `[1] [2]` report).
- Feeds → `evaluate-delivery` (which can spot "[5] is referenced but not in the index" bugs).
