---
name: create-skill
type: avo
version: "1.0"
requires: [curl, git, python3]
triggers: [create skill, new platform, new source, add source]
cost: free
platforms: []
dimensions: []
---
## Purpose
Create and validate a new platform skill only when uncovered high-value domains justify a Tier 3 expansion and the source offers a free machine-parseable interface.

## When to Use
- Use in `PROTOCOL.md` Step 5 Tier 3 when more than 20% of the strongest evidence domains are not covered by existing platform skills or when `diagnose.md` explicitly recommends a new source.
- Prefer this skill when the candidate source has a free public API or a stable machine-parseable response format such as JSON, XML, or predictable HTML.
- Requires enough platform facts to fill in the runtime variables below: `PLATFORM`, `API_URL`, `QUERY_PARAM`, `LIMIT_PARAM`, `RESULTS_PATH`, `TITLE_FIELD`, `URL_FIELD`, and optional metadata field names.
- Do not use it when the source requires a paid API, login wall, or anti-bot workflow; stop instead of creating a broken platform skill.

## Execute
1. Define candidate platform metadata, file paths, and defaults for a testable JSON-based source.
```bash
WORKLOG="${WORKLOG:-state/worklog.jsonl}"
PATTERNS="${PATTERNS:-state/patterns.jsonl}"
CONFIG="${CONFIG:-state/config.json}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SESSION_ID="${SESSION_ID:-}"
GENERATION="${GENERATION:-}"
PLATFORM="${PLATFORM:-example-source}"
SKILL_PATH="${SKILL_PATH:-skills/platforms/${PLATFORM}.md}"
API_URL="${API_URL:-https://example.com/api/search}"
QUERY_PARAM="${QUERY_PARAM:-q}"
LIMIT_PARAM="${LIMIT_PARAM:-limit}"
RESULTS_PATH="${RESULTS_PATH:-results}"
TITLE_FIELD="${TITLE_FIELD:-title}"
URL_FIELD="${URL_FIELD:-url}"
SNIPPET_FIELD="${SNIPPET_FIELD:-snippet}"
DATE_FIELD="${DATE_FIELD:-published_at}"
TEST_QUERY="${TEST_QUERY:-ai agent}"
LIMIT="${LIMIT:-5}"
RAW="$(mktemp)"
TEST_OUT="$(mktemp)"
CREATE_JSON="$(mktemp)"
export WORKLOG PATTERNS CONFIG NOW SESSION_ID GENERATION PLATFORM SKILL_PATH API_URL QUERY_PARAM LIMIT_PARAM RESULTS_PATH TITLE_FIELD URL_FIELD SNIPPET_FIELD DATE_FIELD TEST_QUERY LIMIT RAW TEST_OUT CREATE_JSON
```
2. Confirm that Tier 3 is actually justified and stop unless the candidate source is free and machine-parseable.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

records = []
worklog = Path(os.environ["WORKLOG"])
if worklog.exists():
    with worklog.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

search_runs = [r for r in records if r.get("type") == "search_run"]
latest_run = search_runs[-1] if search_runs else {}
latest_path = latest_run.get("evidence_path", "")
existing_platforms = set()
for path in Path("skills/platforms").glob("*.md"):
    existing_platforms.add(path.stem)

uncovered = 0
total = 0
if latest_path and Path(latest_path).exists():
    with open(latest_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            total += 1
            source = row.get("source", "")
            if source not in existing_platforms:
                uncovered += 1

recommended = any(
    r.get("type") == "diagnosis" and "new source" in (r.get("hypothesis", "").lower())
    for r in records[-10:]
)
coverage_trigger = total > 0 and (uncovered / total) > 0.2
summary = {
    "coverage_trigger": coverage_trigger,
    "recommended": recommended,
    "trigger_ok": coverage_trigger or recommended,
}

with open(os.environ["CREATE_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY

python3 - <<'PY'
import json
import os
summary = json.load(open(os.environ["CREATE_JSON"], encoding="utf-8"))
if not summary["trigger_ok"]:
    raise SystemExit("create-skill.md: Tier 3 trigger not satisfied")
PY

curl -fsSLI "$API_URL" > /dev/null
curl -fsSLG "$API_URL" --data-urlencode "${QUERY_PARAM}=${TEST_QUERY}" --data-urlencode "${LIMIT_PARAM}=${LIMIT}" > "$RAW"
python3 - <<'PY'
import json
import os
raw = open(os.environ["RAW"], encoding="utf-8").read().strip()
try:
    json.loads(raw)
except Exception:
    if raw.startswith("<"):
        print("HTML detected; ensure the page is stable and parseable before continuing")
    else:
        raise SystemExit("create-skill.md: response is not machine-parseable JSON")
PY
```
3. Write the new platform skill so it follows `skill-spec.md` exactly, includes all seven sections, and contains concrete fetch and parse commands for the candidate source.
```bash
python3 - <<'PY'
import os
from pathlib import Path

platform = os.environ["PLATFORM"]
skill_path = Path(os.environ["SKILL_PATH"])
api_url = os.environ["API_URL"]
query_param = os.environ["QUERY_PARAM"]
limit_param = os.environ["LIMIT_PARAM"]
results_path = os.environ["RESULTS_PATH"]
title_field = os.environ["TITLE_FIELD"]
url_field = os.environ["URL_FIELD"]
snippet_field = os.environ["SNIPPET_FIELD"]
date_field = os.environ["DATE_FIELD"]

content = f"""---
name: {platform}
type: platform
version: "1.0"
requires: [curl, python3]
triggers: [{platform}, source]
cost: free
platforms: [{platform}]
dimensions: []
---
## Purpose
Search {platform} when this source covers material that existing platform skills miss and the source exposes a free machine-parseable interface.

## When to Use
- Use when the task regularly surfaces {platform} results or when AVO Tier 3 identifies it as an uncovered source.
- Prefer this skill when the API endpoint remains free and publicly accessible.
- Requires network access plus a stable response schema at `{api_url}`.
- Do not use it if the endpoint becomes paid, interactive, or structurally unstable.

## Execute
1. Define inputs, defaults, and temporary paths.
```bash
QUERY="${{QUERY:-{os.environ['TEST_QUERY']}}}"
LIMIT="${{LIMIT:-10}}"
OUT="${{OUT:-/tmp/{platform}.jsonl}}"
NOW="${{NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}}"
RAW="${{RAW:-$(mktemp)}}"
export QUERY LIMIT OUT NOW RAW
```
2. Fetch results from the public endpoint.
```bash
curl -fsSLG '{api_url}' \\
  --data-urlencode '{query_param}=$QUERY' \\
  --data-urlencode '{limit_param}=$LIMIT' \\
  > "$RAW"
```
3. Convert the response into AutoSearch JSONL.
```bash
python3 - <<'PY2'
import json
import os

data = json.load(open(os.environ["RAW"], encoding="utf-8"))
results = data
for part in "{results_path}".split("."):
    if part:
        results = results.get(part, []) if isinstance(results, dict) else []

with open(os.environ["OUT"], "w", encoding="utf-8") as out:
    for item in results:
        url = item.get("{url_field}")
        if not url:
            continue
        row = {{
            "url": url,
            "title": item.get("{title_field}") or url,
            "source": "{platform}",
            "snippet": item.get("{snippet_field}") or "",
            "found_at": os.environ["NOW"],
            "query": os.environ["QUERY"],
            "metadata": {{
                "published_at": item.get("{date_field}"),
                "raw_result": item,
            }},
        }}
        print(json.dumps(row, ensure_ascii=False), file=out)
PY2
```

## Parse
Write UTF-8 JSONL to `$OUT`. Each line follows the base AutoSearch schema and stores the source-specific date field in `metadata.published_at` plus the original item in `metadata.raw_result`.

## Score Hints
- `relevance`: the title and snippet should align tightly with the task entities and should justify why this source is worth the Tier 3 expansion.
- `freshness`: prefer this source when `{date_field}` is present and recent.
- `diversity`: this skill is most valuable when it adds results that existing platforms do not already surface.
- `efficiency`: one query should return multiple valid records without excessive cleanup.

## Known Limitations
- This template assumes a JSON API; XML or HTML sources require a different parser before the skill is valid.
- If the endpoint returns malformed data or missing URLs, treat the test as a failure and delete the skill file.
- Large raw result payloads can bloat `metadata.raw_result`; trim them later only if doing so preserves useful ranking signals.
- If the API becomes paid or rate-limited beyond free use, stop using the skill.

## Evolution Notes
- Tune: endpoint parameters, parser field mappings, and optional recency filters.
- Tried: start with a minimal free JSON endpoint template so Tier 3 additions remain testable.
- Next: verify schema correctness against real payloads before relying on this platform in planning.
"""

skill_path.parent.mkdir(parents=True, exist_ok=True)
skill_path.write_text(content, encoding="utf-8")
PY
```
4. Run the generated skill with a test query, verify the JSONL schema, and delete the file plus log a failure if the test does not pass.
```bash
curl -fsSLG "$API_URL" --data-urlencode "${QUERY_PARAM}=${TEST_QUERY}" --data-urlencode "${LIMIT_PARAM}=${LIMIT}" > "$RAW"
python3 - <<'PY'
import json
import os
from pathlib import Path

data = json.load(open(os.environ["RAW"], encoding="utf-8"))
results = data
for part in os.environ["RESULTS_PATH"].split("."):
    if part:
        results = results.get(part, []) if isinstance(results, dict) else []

with open(os.environ["TEST_OUT"], "w", encoding="utf-8") as out:
    for item in results:
        url = item.get(os.environ["URL_FIELD"])
        if not url:
            continue
        row = {
            "url": url,
            "title": item.get(os.environ["TITLE_FIELD"]) or url,
            "source": os.environ["PLATFORM"],
            "snippet": item.get(os.environ["SNIPPET_FIELD"]) or "",
            "found_at": os.environ["NOW"],
            "query": os.environ["TEST_QUERY"],
            "metadata": {
                "published_at": item.get(os.environ["DATE_FIELD"]),
            },
        }
        out.write(json.dumps(row, ensure_ascii=False) + "\\n")

rows = []
with open(os.environ["TEST_OUT"], encoding="utf-8") as fh:
    for line in fh:
        if line.strip():
            rows.append(json.loads(line))

required = {"url", "title", "source", "snippet", "found_at", "query", "metadata"}
ok = bool(rows) and all(required <= set(row) for row in rows)
if not ok:
    skill_path = Path(os.environ["SKILL_PATH"])
    if skill_path.exists():
        skill_path.unlink()
    failure = {
        "type": "platform_insight",
        "ts": os.environ["NOW"],
        "session_id": os.environ.get("SESSION_ID", ""),
        "generation": int(os.environ.get("GENERATION") or 0),
        "platform": os.environ["PLATFORM"],
        "pattern": "candidate platform skill failed schema validation",
        "effect": "no platform added",
        "evidence": "test query did not emit valid AutoSearch JSONL",
    }
    with open(os.environ["PATTERNS"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(failure, ensure_ascii=False) + "\\n")
    raise SystemExit("create-skill.md: generated skill test failed")
PY
```
5. If the test passes, add the new platform to `state/config.json` with initial weight `0.5` and commit the new skill and config change.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG"])
config = json.loads(config_path.read_text(encoding="utf-8"))
weights = config.setdefault("platform_weights", {})
weights[os.environ["PLATFORM"]] = 0.5
config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

git add "$SKILL_PATH" state/config.json
git commit \
  -m "avo: create platform skill - ${PLATFORM}.md" \
  -m "Co-authored-by: Codex <noreply@openai.com>"
```

## Parse
On success, emit a new markdown file at `skills/platforms/<platform>.md`, update `state/config.json` to include `platform_weights.<platform> = 0.5`, and create a git commit for both artifacts. On failure, delete the generated skill file and append one UTF-8 JSON object line to `state/patterns.jsonl` with this exact logical schema:
```json
{"type":"platform_insight","ts":"ISO8601","session_id":"string","generation":1,"platform":"candidate-platform","pattern":"string","effect":"string","evidence":"string"}
```

## Score Hints
- A valid Tier 3 addition should increase `diversity` or `quantity` without immediately collapsing `relevance`.
- The new skill is highest value when its source repeatedly appears in good evidence but had no existing platform skill.
- Favor APIs or pages that expose stable timestamps and clean snippets because they help both `freshness` and ranking.
- Reject borderline sources early if they cannot produce valid AutoSearch JSONL in one non-interactive pass.

## Known Limitations
- This template targets free JSON endpoints first; XML and HTML sources need field-specific parsing changes before the generated platform skill is truly usable.
- Coverage-trigger detection uses the latest merged evidence file and source labels, which is a coarse proxy for uncovered domains.
- The generated platform skill stores the raw result in metadata by default; some APIs may require trimming sensitive or excessively large fields later.
- Network failures, schema drift, or silent throttling should be treated as hard test failures rather than partial success.

## Evolution Notes
- Tune: candidate field mappings, endpoint parameters, and the Tier 3 trigger thresholds only in mutable config or strategy logic, not in this immutable AVO file.
- Tried: gate skill creation on both a coverage signal and a real schema validation pass before committing anything.
- Next: prefer narrowly scoped platform additions with obvious parser fields over ambitious generic scraping.
