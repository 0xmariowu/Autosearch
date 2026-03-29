---
name: synthesize
type: strategy
version: "1.0"
requires: [python3]
triggers: [synthesize, report, deliver, summarize, compile]
cost: free
platforms: []
dimensions: []
---
## Purpose
Turn deduplicated search evidence into the final delivery artifact when the runner needs a report format matched to the user’s task type.

## When to Use
- Use after evidence collection, deduplication, and optional scoring are complete and a human-readable deliverable is required.
- Supports `IN` for evidence JSONL, `TASK_SPEC` for task classification, and `RUN_ID` for deterministic report paths.
- Prefer this skill when the output must cite evidence URLs and include scope, caveats, and methodology in one markdown artifact.
- Do not use it before deduplication if the evidence set still contains obvious duplicates.

## Execute
1. Define inputs, defaults, and the report output path.
```bash
IN="${IN:-/tmp/deduplicated-evidence.jsonl}"
QUERY="${QUERY:-discover ai agent tools}"
TASK_SPEC="${TASK_SPEC:-$QUERY}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
GENERATION_COUNT="${GENERATION_COUNT:-1}"
JUDGE_SCORES="${JUDGE_SCORES:-{}}"
SEARCH_SCOPE="${SEARCH_SCOPE:-auto}"
DELIVERY_DIR="${DELIVERY_DIR:-delivery}"
OUT="${OUT:-$DELIVERY_DIR/${RUN_ID}-report.md}"
export IN QUERY TASK_SPEC RUN_ID GENERATION_COUNT JUDGE_SCORES SEARCH_SCOPE DELIVERY_DIR OUT
mkdir -p "$DELIVERY_DIR"
```
2. Classify the task, format the matching report template, and write markdown to `$OUT`.
```bash
python3 - <<'PY'
import json
import os
import re
from collections import defaultdict

def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()

def score_value(item):
    metadata = item.get("metadata", {})
    return (
        metadata.get("stars", 0)
        + metadata.get("points", 0)
        + metadata.get("score", 0)
        + metadata.get("upvotes", 0)
        + metadata.get("comments", 0)
        + metadata.get("num_comments", 0)
    )

def classify(task):
    lowered = task.lower()
    if " vs " in lowered or "compare" in lowered or "alternatives" in lowered:
        return "comparison"
    if "how to" in lowered or "setup" in lowered or "guide" in lowered:
        return "tutorial"
    if "find" in lowered or "discover" in lowered or "what exists" in lowered:
        return "research-survey"
    return "discovery-list"

def bullet_link(item):
    title = clean(item.get("title")) or item.get("url")
    return f"[{title}]({item.get('url')})"

def evidence_note(item):
    snippet = clean(item.get("snippet"))
    source = item.get("source", "unknown")
    return f"{bullet_link(item)} ({source})" + (f" - {snippet}" if snippet else "")

task = clean(os.getenv("TASK_SPEC", os.getenv("QUERY", "")))
query = clean(os.getenv("QUERY", ""))
rows = read_jsonl(os.getenv("IN", "/tmp/deduplicated-evidence.jsonl"))
rows.sort(key=score_value, reverse=True)
template = classify(task)
sources = sorted({row.get("source", "unknown") for row in rows})
scope = os.getenv("SEARCH_SCOPE", "auto")
if scope == "auto":
    scope = ", ".join(sources) if sources else "no sources"

try:
    judge_scores = json.loads(os.getenv("JUDGE_SCORES", "{}"))
except json.JSONDecodeError:
    judge_scores = {"raw": os.getenv("JUDGE_SCORES", "")}

body_lines = []
top_rows = rows[:8]

if template == "comparison":
    candidates = top_rows[:4]
    headers = ["Evaluation dimension"] + [clean(item.get("title"))[:40] or item.get("url") for item in candidates]
    body_lines.append("## Comparison")
    body_lines.append("| " + " | ".join(headers) + " |")
    body_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    dimensions = [
        ("Source", lambda item: item.get("source", "unknown")),
        ("Evidence", lambda item: bullet_link(item)),
        ("Freshness", lambda item: item.get("metadata", {}).get("published_at") or item.get("metadata", {}).get("updated_at") or item.get("found_at", "unknown")),
        ("Strength", lambda item: clean(item.get("snippet"))[:60] or "No snippet"),
        ("Caveat", lambda item: item.get("metadata", {}).get("dedup_note") or "Needs manual validation"),
    ]
    for label, fn in dimensions:
        row = [label] + [fn(item).replace("\n", " ") for item in candidates]
        body_lines.append("| " + " | ".join(row) + " |")
elif template == "tutorial":
    body_lines.append("## How-To Steps")
    for index, item in enumerate(top_rows[:6], start=1):
        body_lines.append(f"{index}. Use {bullet_link(item)} as evidence for this step.")
        snippet = clean(item.get("snippet"))
        if snippet:
            body_lines.append(f"   Evidence: {snippet}")
elif template == "research-survey":
    grouped = defaultdict(list)
    for item in top_rows:
        grouped[item.get("source", "unknown")].append(item)
    body_lines.append("## Survey")
    for source in sorted(grouped):
        body_lines.append(f"### {source.title()}")
        for item in grouped[source][:4]:
            body_lines.append(f"- {evidence_note(item)}")
    body_lines.append("## Key Findings")
    for item in top_rows[:3]:
        body_lines.append(f"- {clean(item.get('title'))}: {clean(item.get('snippet')) or 'Evidence available at linked source.'}")
    body_lines.append("## Gap Analysis")
    body_lines.append(f"- Coverage favors: {', '.join(sources) if sources else 'none'}")
    body_lines.append("- Missing or weak areas: official docs, recency validation, and direct benchmarking should be checked if absent from the evidence set.")
else:
    body_lines.append("## Ranked Findings")
    for index, item in enumerate(top_rows, start=1):
        why = clean(item.get("snippet")) or "Relevant supporting evidence."
        body_lines.append(f"{index}. {bullet_link(item)}")
        body_lines.append(f"   Why it matters: {why}")
        body_lines.append(f"   Source: {item.get('source', 'unknown')}")

footer_scores = ", ".join(
    f"{key}={value}" for key, value in sorted(judge_scores.items())
) if judge_scores else "unavailable"

lines = [
    f"# Report: {task or query}",
    "",
    "## Search Scope",
    f"- Objective: {task or query}",
    f"- Scope: {scope}",
    f"- Evidence count: {len(rows)}",
    "",
]
lines.extend(body_lines)
lines.extend([
    "",
    "## Delivery Notes",
    f"- Judge scores: {footer_scores}",
    f"- Generation count: {os.getenv('GENERATION_COUNT', '1')}",
    "- Caveats and gaps: conclusions depend on the supplied evidence set; missing timestamps, official sources, or benchmarks should be called out explicitly.",
    "- Methodology note: report generated from deduplicated JSONL evidence with template selection based on task wording.",
    "",
])

with open(os.getenv("OUT", "/tmp/report.md"), "w", encoding="utf-8") as out:
    out.write("\n".join(lines))
PY
```

## Parse
Write a markdown report to `$OUT`, defaulting to `autosearch/v2/delivery/{RUN_ID}-report.md`. The expected file structure is:
`# Report: <task objective>`
`## Search Scope`
`## Comparison | ## How-To Steps | ## Survey | ## Ranked Findings`
`## Delivery Notes`
The body section must reference evidence URLs directly, and the footer must include judge scores, generation count, caveats or gaps, and a methodology note.

## Score Hints
- `relevance`: every major claim in the report body should point back to at least one evidence URL.
- `diversity`: survey and discovery outputs are stronger when they cite more than one source family rather than repeating the same platform.
- `efficiency`: the report should compress the evidence into a usable artifact without restating every row verbatim.
- Extra signal: a good synthesis makes gaps explicit instead of implying confidence the evidence set does not support.

## Known Limitations
- Template selection is keyword-based, so ambiguous tasks may need an explicit `TASK_SPEC` to choose the right format.
- The comparison template uses top-ranked evidence rows as candidates and may need manual refinement when multiple rows refer to the same product.
- Judge scores are passed through from `JUDGE_SCORES`; invalid JSON falls back to a raw string and may reduce structure in the footer.
- If the evidence file is empty, the report still renders but will mainly document missing coverage rather than findings.

## Evolution Notes
- Tune: task-type classification keywords, candidate extraction for comparison tables, and report length caps.
- Tried: keep a shared header and footer so all templates expose scope, caveats, and methodology consistently.
- Next: add richer source-aware grouping and stronger comparison-candidate clustering from titles and metadata.
