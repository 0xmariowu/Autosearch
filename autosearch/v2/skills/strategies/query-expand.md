---
name: query-expand
type: strategy
version: "1.0"
requires: [python3]
triggers: [query, expand, generate queries, search terms]
cost: free
platforms: []
dimensions: [relevance, diversity]
---
## Purpose
Expand a vague search objective into a compact set of precise multi-perspective queries when recall and coverage both matter.

## When to Use
- Use when the input task is underspecified and the runner needs 5 to 15 search-ready queries before platform execution.
- Prefer this skill when a single wording is unlikely to cover developer, research, and end-user intent.
- Supports `TASK_SPEC` as the full task description and falls back to `QUERY` when no separate task spec is provided.
- Do not use it as the final ranking step because it generates candidate queries rather than evidence.

## Execute
1. Define inputs, defaults, and the output path.
```bash
TASK_SPEC="${TASK_SPEC:-${QUERY:-ai agent observability tools}}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/query-expand.jsonl}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
export TASK_SPEC LIMIT OUT NOW
```
2. Extract key entities, expand them across developer, researcher, and user perspectives, add synonyms and negations, and write JSONL to `$OUT`.
```bash
python3 - <<'PY'
import json
import os
import re
from collections import OrderedDict

task = re.sub(r"\s+", " ", os.environ["TASK_SPEC"]).strip()
target = max(5, min(15, int(os.environ["LIMIT"])))
out_path = os.environ["OUT"]

stopwords = {
    "a", "an", "and", "are", "best", "build", "compare", "comparison", "create", "discover",
    "find", "for", "from", "guide", "help", "how", "i", "in", "is", "me", "of", "on", "or",
    "setup", "show", "the", "to", "use", "using", "vs", "want", "what", "with"
}

synonyms = {
    "ai": ["artificial intelligence", "llm"],
    "agent": ["assistant", "automation agent"],
    "agents": ["assistants", "automation agents"],
    "api": ["interface", "developer api"],
    "benchmark": ["evaluation", "performance test"],
    "database": ["db", "data store"],
    "framework": ["toolkit", "sdk"],
    "frontend": ["ui", "client-side"],
    "guide": ["tutorial", "walkthrough"],
    "library": ["package", "module"],
    "llm": ["large language model", "foundation model"],
    "monitoring": ["observability", "telemetry"],
    "observability": ["monitoring", "telemetry"],
    "rag": ["retrieval augmented generation", "retrieval pipeline"],
    "repository": ["repo", "codebase"],
    "sdk": ["toolkit", "library"],
    "search": ["retrieval", "lookup"],
    "security": ["hardening", "safety"],
    "tutorial": ["guide", "walkthrough"],
}

tech_markers = {
    "api", "cli", "cloud", "code", "database", "framework", "github", "library", "model",
    "observability", "python", "rag", "repo", "repository", "sdk", "search", "typescript"
}

quoted = re.findall(r'"([^"]+)"', task)
product_like = re.findall(r"\b[A-Z][a-zA-Z0-9._+-]*(?:\s+[A-Z][a-zA-Z0-9._+-]*)*\b", task)
tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._-]*", task)

entities = []
for item in quoted + product_like:
    item = item.strip(" -")
    if item and item.lower() not in stopwords:
        entities.append(item)

filtered_tokens = []
for token in tokens:
    t = token.lower()
    if len(t) < 3 or t in stopwords:
        continue
    filtered_tokens.append(token)

if not entities:
    bigrams = [" ".join(filtered_tokens[i:i + 2]) for i in range(max(0, len(filtered_tokens) - 1))]
    entities.extend(bigrams[:2])
    entities.extend(filtered_tokens[:3])

ordered_entities = []
seen_entities = set()
for entity in entities:
    normalized = entity.lower()
    if normalized in seen_entities:
        continue
    seen_entities.add(normalized)
    ordered_entities.append(entity)

ordered_entities = ordered_entities[:4] or [task]

def entity_synonyms(entity):
    parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._-]*", entity.lower())
    found = []
    for part in parts:
        for candidate in synonyms.get(part, []):
            if candidate not in found:
                found.append(candidate)
    if not found and len(parts) == 1:
        head = parts[0].rstrip("s")
        for candidate in synonyms.get(head, []):
            if candidate not in found:
                found.append(candidate)
    return found[:2]

goal_tokens = [t for t in filtered_tokens if t.lower() not in {e.lower() for e in ordered_entities}]
goal = " ".join(goal_tokens[:4]).strip() or task

perspectives = OrderedDict(
    developer=[
        "how to use {entity}",
        "{entity} tutorial",
        "{entity} vs {peer}",
    ],
    researcher=[
        "{entity} survey",
        "{entity} comparison study",
        "{entity} benchmark",
    ],
    user=[
        "best {entity} for {goal}",
        "{entity} review",
        "{entity} alternatives",
    ],
)

negations = {
    "developer": ["-site:medium.com"],
    "researcher": ["-tutorial"],
    "user": ["-site:medium.com", "-sponsored"],
}

peer = ordered_entities[1] if len(ordered_entities) > 1 else "alternatives"
rows = []
seen_queries = set()

def platform_hint(entity, perspective):
    parts = {p.lower() for p in re.findall(r"[A-Za-z0-9][A-Za-z0-9+._-]*", entity)}
    return "github" if perspective == "developer" or parts & tech_markers else "all"

while len(rows) < target:
    before = len(rows)
    for perspective, templates in perspectives.items():
        for entity in ordered_entities:
            for template in templates:
                if len(rows) >= target:
                    break
                query = template.format(entity=entity, peer=peer, goal=goal).strip()
                if not query or query.lower() in seen_queries:
                    continue
                seen_queries.add(query.lower())
                query_negations = negations[perspective]
                query_with_negations = " ".join([query] + query_negations).strip()
                rows.append({
                    "query": query_with_negations,
                    "perspective": perspective,
                    "platform_hint": platform_hint(entity, perspective),
                    "negations": query_negations,
                })
            if len(rows) >= target:
                break
            for synonym in entity_synonyms(entity):
                if len(rows) >= target:
                    break
                base = f"{synonym} {entity}".strip()
                if perspective == "researcher":
                    query = f"{base} benchmark"
                elif perspective == "user":
                    query = f"best {base} for {goal}"
                else:
                    query = f"how to use {base}"
                if query.lower() in seen_queries:
                    continue
                seen_queries.add(query.lower())
                query_negations = negations[perspective]
                query_with_negations = " ".join([query] + query_negations).strip()
                rows.append({
                    "query": query_with_negations,
                    "perspective": perspective,
                    "platform_hint": platform_hint(entity, perspective),
                    "negations": query_negations,
                })
            if len(rows) >= target:
                break
    if len(rows) == before:
        break

with open(out_path, "w", encoding="utf-8") as out:
    for row in rows[:target]:
        print(json.dumps(row, ensure_ascii=False), file=out)
PY
```
3. Emit the generated queries to stdout for downstream piping or inspection.
```bash
cat "$OUT"
```

## Parse
Write UTF-8 JSONL to `$OUT` and mirror the same lines to stdout in the final step. Each line follows this schema:
```json
{"query":"the generated query","perspective":"developer|researcher|user","platform_hint":"github|all","negations":["-site:medium.com"]}
```
`query` is the exact search string to execute, `perspective` records why it exists, `platform_hint` suggests whether code-heavy execution should prioritize GitHub or broad web search, and `negations` lists the exclusions appended for noise control.

## Score Hints
- `diversity`: the output should cover all three perspectives unless the task is too narrow to justify one of them.
- `relevance`: queries should preserve the task's core entities and intent rather than drifting into generic adjacent topics.
- `efficiency`: 5 to 15 high-yield queries are better than a long tail of near-duplicates.
- Extra signal: good expansions combine exact entities, one or two useful synonym variants, and at least some noise-reduction negations.

## Known Limitations
- Synonym expansion is heuristic and strongest for common software and research terms; unfamiliar product names may only get viewpoint variation.
- Generic tasks can still produce broad queries if the input lacks stable nouns or product names.
- Search engines interpret negations differently, so some exclusions help more on web search than on platform-native search.
- If the output is empty or too repetitive, tighten `TASK_SPEC`, add concrete entities, or reduce the requested `LIMIT`.

## Evolution Notes
- Tune: entity extraction heuristics, synonym tables, and the mapping from perspective to `platform_hint`.
- Tried: keep the query set capped and round-robin across perspectives instead of overproducing developer-only variants.
- Next: add optional domain allowlists and more task-type-aware query templates for jobs such as security reviews or migration planning.
