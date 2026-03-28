---
name: diagnose
type: avo
version: "1.0"
requires: [python3]
triggers: [diagnose, debug, analyze failure, why]
cost: free
platforms: []
dimensions: []
---
## Purpose
Diagnose a non-improving generation by identifying the weakest judge dimension, choosing one corrective action, and recording the retry plan before the protocol reruns search and score.

## When to Use
- Use in `PROTOCOL.md` Step 4 only when the current generation did not improve and generation `1` baseline handling does not apply.
- Prefer this skill when the runner needs one focused fix instead of many simultaneous edits.
- Requires `state/config.json` plus prior `search_run` and `diagnosis` records in `state/worklog.jsonl`.
- Do not use it to rerun search directly; this skill proposes and applies one fix, then the protocol performs the next `SEARCH` and `SCORE`.

## Execute
1. Define runtime paths, defaults, and the output placeholder for the next run id.
```bash
WORKLOG="${WORKLOG:-state/worklog.jsonl}"
CONFIG="${CONFIG:-state/config.json}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SESSION_ID="${SESSION_ID:-}"
GENERATION="${GENERATION:-}"
DIAGNOSIS_JSON="$(mktemp)"
export WORKLOG CONFIG NOW SESSION_ID GENERATION DIAGNOSIS_JSON
```
2. Read the current and previous scores, identify the weakest or regressed dimension, and stop if the generation has already used the maximum retry budget.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

worklog_path = Path(os.environ["WORKLOG"])
config_path = Path(os.environ["CONFIG"])
session_id = os.environ.get("SESSION_ID", "").strip()
generation_raw = os.environ.get("GENERATION", "").strip()

records = []
if worklog_path.exists():
    with worklog_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

search_runs = [r for r in records if r.get("type") == "search_run"]
if session_id:
    search_runs = [r for r in search_runs if r.get("session_id") == session_id]

if generation_raw:
    generation = int(generation_raw)
else:
    generation = max((r.get("generation", 0) for r in search_runs), default=0)

current = None
for record in search_runs:
    if record.get("generation") == generation:
        current = record
if current is None:
    raise SystemExit("diagnose.md: no search_run found for the requested generation")

session_id = session_id or current.get("session_id", "")
previous = None
for record in search_runs:
    if record.get("generation", -1) < generation:
        if previous is None or record.get("generation", -1) > previous.get("generation", -1):
            previous = record

config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
max_retries = int(config.get("avo_params", {}).get("max_diagnosis_retries", 2))
existing_diagnoses = [
    r for r in records
    if r.get("type") == "diagnosis"
    and r.get("session_id") == session_id
    and r.get("generation") == generation
]
attempt = len(existing_diagnoses) + 1
if attempt > max_retries:
    raise SystemExit("diagnose.md: retry limit reached for this generation")

current_dimensions = current.get("score", {}).get("dimensions", {}) or {}
previous_dimensions = previous.get("score", {}).get("dimensions", {}) if previous else {}
regressed = []
for name, value in current_dimensions.items():
    prev = float(previous_dimensions.get(name, value))
    delta = float(value) - prev
    if delta < 0:
        regressed.append((name, float(value), delta))

weakest_dimension = min(
    current_dimensions.items(),
    key=lambda item: (float(item[1]), item[0]),
)[0]
if regressed:
    weakest_dimension = sorted(regressed, key=lambda item: (item[2], item[1]))[0][0]

summary = {
    "session_id": session_id,
    "generation": generation,
    "attempt": attempt,
    "prior_score": float(current.get("score", {}).get("total", 0.0)),
    "weakest_dimension": weakest_dimension,
    "current_dimensions": current_dimensions,
    "previous_dimensions": previous_dimensions,
}

with open(os.environ["DIAGNOSIS_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
3. Choose exactly one corrective action using the required root-cause rules, and prefer the smallest edit that directly addresses the weakest dimension.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["DIAGNOSIS_JSON"], encoding="utf-8"))
dimension = summary["weakest_dimension"]

if dimension == "quantity":
    summary["hypothesis"] = "quantity low: queries are too restrictive, too few are emitted, or platform limits are too small"
    summary["fix"] = {
        "kind": "config_update",
        "path": "query_strategy.max_queries_per_platform",
        "value": "double current value",
    }
elif dimension == "diversity":
    summary["hypothesis"] = "diversity low: one platform is dominating or the same query family is repeated"
    summary["fix"] = {
        "kind": "platform_change",
        "path": "platform_weights",
        "value": "halve dominant platform weight and double one underrepresented platform",
    }
elif dimension == "relevance":
    summary["hypothesis"] = "relevance low: queries are too broad or the expansion method is mismatched to the task"
    summary["fix"] = {
        "kind": "query_change",
        "path": "query_strategy.expansion_method",
        "value": "switch between role_perspective and synonym_chain",
    }
elif dimension == "freshness":
    summary["hypothesis"] = "freshness low: recency filters are missing or old results dominate the plan"
    summary["fix"] = {
        "kind": "config_update",
        "path": "query_strategy.default_since_days",
        "value": 180,
    }
else:
    summary["hypothesis"] = "efficiency low: too many overlapping queries are producing the same evidence"
    summary["fix"] = {
        "kind": "config_update",
        "path": "query_strategy.max_total_queries",
        "value": "reduce by one third",
    }

with open(os.environ["DIAGNOSIS_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
4. Apply the chosen fix to `state/config.json` and leave search reruns to the protocol.
```bash
python3 - <<'PY'
import json
import math
import os
from pathlib import Path

summary = json.load(open(os.environ["DIAGNOSIS_JSON"], encoding="utf-8"))
config_path = Path(os.environ["CONFIG"])
config = json.loads(config_path.read_text(encoding="utf-8"))
fix = summary["fix"]

if fix["kind"] == "config_update" and fix["path"] == "query_strategy.max_queries_per_platform":
    current = int(config.setdefault("query_strategy", {}).get("max_queries_per_platform", 5))
    config["query_strategy"]["max_queries_per_platform"] = max(current + 1, current * 2)
    fix["value"] = config["query_strategy"]["max_queries_per_platform"]
elif fix["kind"] == "platform_change":
    weights = config.setdefault("platform_weights", {})
    if weights:
        dominant = max(weights, key=weights.get)
        underrepresented = min(weights, key=weights.get)
        weights[dominant] = round(max(0.0, weights[dominant] / 2.0), 3)
        weights[underrepresented] = round(weights[underrepresented] * 2.0, 3)
        fix["value"] = {dominant: weights[dominant], underrepresented: weights[underrepresented]}
elif fix["kind"] == "query_change":
    strategy = config.setdefault("query_strategy", {})
    current = strategy.get("expansion_method", "role_perspective")
    strategy["expansion_method"] = "synonym_chain" if current == "role_perspective" else "role_perspective"
    fix["value"] = strategy["expansion_method"]
elif fix["kind"] == "config_update" and fix["path"] == "query_strategy.default_since_days":
    config.setdefault("query_strategy", {})["default_since_days"] = int(fix["value"])
else:
    strategy = config.setdefault("query_strategy", {})
    current = int(strategy.get("max_total_queries", 25))
    strategy["max_total_queries"] = max(3, math.ceil(current * 2 / 3))
    fix["value"] = strategy["max_total_queries"]

config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
summary["fix"] = fix

with open(os.environ["DIAGNOSIS_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
5. Append one `diagnosis` record for this retry attempt so the next `SEARCH` and `SCORE` pass has a concrete, logged corrective action to test.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["DIAGNOSIS_JSON"], encoding="utf-8"))
record = {
    "type": "diagnosis",
    "ts": os.environ["NOW"],
    "session_id": summary["session_id"],
    "generation": summary["generation"],
    "attempt": summary["attempt"],
    "prior_score": summary["prior_score"],
    "weakest_dimension": summary["weakest_dimension"],
    "hypothesis": summary["hypothesis"],
    "fix": summary["fix"],
    "resulting_generation": summary["generation"],
}

with open(os.environ["WORKLOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
PY
```

## Parse
Append one UTF-8 JSON object line to `state/worklog.jsonl` with this exact schema:
```json
{"type":"diagnosis","ts":"ISO8601","session_id":"string","generation":1,"attempt":1,"prior_score":0.0,"weakest_dimension":"quantity|diversity|relevance|freshness|efficiency","hypothesis":"string","fix":{"kind":"config_update|query_change|platform_change","path":"string","value":"json value"},"resulting_generation":1}
```
The skill also mutates `state/config.json` in place for the single chosen corrective action; the protocol then reruns `SEARCH` and `SCORE`.

## Score Hints
- Prefer the dimension with the lowest absolute score, unless another dimension clearly regressed and offers a more diagnostic root cause.
- Fix one thing at a time; a narrow intervention is easier to validate with `judge.py` on the retry.
- `quantity` and `diversity` issues are often planning or platform-mix failures, while `relevance` and `freshness` are often query-shape failures.
- A strong diagnosis explains why the selected fix should move one weak dimension without introducing many uncontrolled changes.

## Known Limitations
- This skill assumes the next `SEARCH` and `SCORE` will happen immediately after the config edit; if not, the diagnosis can become stale.
- `resulting_generation` records the generation number at diagnosis time; the rerun happens in the same generation.
- Some fixes add new config keys such as `query_strategy.default_since_days`; downstream planning must honor them for the correction to matter.
- If the worklog is incomplete, the diagnosis may fall back to the weakest absolute dimension even when the true regression driver is elsewhere.

## Evolution Notes
- Tune: none in this file; `diagnose.md` is an immutable AVO protocol skill and must not be modified by AVO.
- Tried: keep diagnosis edits confined to `state/config.json` so retries stay reversible and easy to compare.
- Next: continue recording one hypothesis and one fix per attempt so later evolution can attribute score changes cleanly.
