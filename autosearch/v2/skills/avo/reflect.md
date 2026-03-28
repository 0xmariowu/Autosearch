---
name: reflect
type: avo
version: "1.0"
requires: [python3]
triggers: [reflect, review, analyze round]
cost: free
platforms: []
dimensions: []
---
## Purpose
Reflect on the latest scored generation after evolution so the runner records reusable wins, losses, and next moves before the next loop iteration.

## When to Use
- Use in `PROTOCOL.md` Step 6 after `search_run` exists and any diagnosis or evolution decision for the same generation is already recorded.
- Prefer this skill when the runner needs to compare the current generation against the previous one and turn score deltas into concrete patterns.
- Requires append access to `state/worklog.jsonl` and `state/patterns.jsonl`.
- Do not use it to mutate search strategy files; AVO skills are fixed protocol and must remain immutable.

## Execute
1. Define runtime paths, defaults, and temporary files.
```bash
WORKLOG="${WORKLOG:-state/worklog.jsonl}"
PATTERNS="${PATTERNS:-state/patterns.jsonl}"
CONFIG="${CONFIG:-state/config.json}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SESSION_ID="${SESSION_ID:-}"
GENERATION="${GENERATION:-}"
SUMMARY="$(mktemp)"
export WORKLOG PATTERNS CONFIG NOW SESSION_ID GENERATION SUMMARY
```
2. Read the current generation's `search_run` record, compare it to the previous generation if one exists, and summarize score deltas plus the likely changed levers.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

worklog_path = Path(os.environ["WORKLOG"])
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
    raise SystemExit("reflect.md: no search_run found for the requested generation")

session_id = session_id or current.get("session_id", "")
previous = None
for record in search_runs:
    if record.get("generation", -1) < generation:
        if previous is None or record.get("generation", -1) > previous.get("generation", -1):
            previous = record

diagnoses = [r for r in records if r.get("type") == "diagnosis" and r.get("session_id") == session_id and r.get("generation") == generation]
evolutions = [r for r in records if r.get("type") == "evolution" and r.get("session_id") == session_id and r.get("generation") == generation]
latest_diagnosis = diagnoses[-1] if diagnoses else {}
latest_evolution = evolutions[-1] if evolutions else {}

dimensions = current.get("score", {}).get("dimensions", {}) or {}
previous_dimensions = previous.get("score", {}).get("dimensions", {}) if previous else {}
current_total = float(current.get("score", {}).get("total", 0.0))
previous_total = float(previous.get("score", {}).get("total", 0.0)) if previous else None

current_plan = current.get("plan", {}) or {}
previous_plan = previous.get("plan", {}) if previous else {}
current_platforms = current_plan.get("platform_plan", {}) or {}
previous_platforms = previous_plan.get("platform_plan", {}) or {}

def platform_change_notes():
    notes = []
    added = sorted(set(current_platforms) - set(previous_platforms))
    removed = sorted(set(previous_platforms) - set(current_platforms))
    if added:
        notes.append("platforms added: " + ", ".join(added))
    if removed:
        notes.append("platforms removed: " + ", ".join(removed))
    for platform in sorted(set(current_platforms) & set(previous_platforms)):
        before = previous_platforms.get(platform, {})
        after = current_platforms.get(platform, {})
        if before.get("limit") != after.get("limit"):
            notes.append(f"{platform} limit {before.get('limit')}->{after.get('limit')}")
        if before.get("queries") != after.get("queries"):
            notes.append(f"{platform} query set changed")
        if before.get("weight") != after.get("weight"):
            notes.append(f"{platform} weight {before.get('weight')}->{after.get('weight')}")
    return notes

change_notes = []
if latest_diagnosis:
    fix = latest_diagnosis.get("fix", {})
    if fix:
        change_notes.append(f"diagnosis fix {fix.get('kind')} at {fix.get('path')}={fix.get('value')}")
if latest_evolution:
    for item in latest_evolution.get("changes", []):
        change_notes.append(f"evolution changed {item}")
change_notes.extend(platform_change_notes())
if current_plan.get("strategy") != previous_plan.get("strategy"):
    change_notes.append("query strategy changed")

winning = []
losing = []
for dimension, value in dimensions.items():
    before = float(previous_dimensions.get(dimension, 0.0)) if previous else None
    if before is None:
        continue
    delta = round(float(value) - before, 6)
    if delta > 0:
        reason = change_notes[0] if change_notes else "current plan outperformed the prior plan"
        winning.append({
            "dimension": dimension,
            "delta": delta,
            "effect": f"{dimension} up by {delta:.3f}",
            "pattern": reason,
        })
    else:
        if latest_diagnosis:
            reason = latest_diagnosis.get("hypothesis", "score stayed flat or regressed")
        else:
            reason = "no clear winning change detected"
        losing.append({
            "dimension": dimension,
            "delta": delta,
            "effect": f"{dimension} {'flat' if delta == 0 else 'down by ' + format(abs(delta), '.3f')}",
            "pattern": reason,
        })

platform_insights = []
for platform, plan in current_platforms.items():
    limit_value = plan.get("limit")
    queries = plan.get("queries", [])
    if limit_value:
        platform_insights.append({
            "platform": platform,
            "pattern": f"{platform} ran {len(queries)} queries with limit {limit_value}",
            "effect": "use together with score delta during later planning",
            "evidence": f"generation {generation}",
        })

trajectory = "single-generation baseline"
if previous_total is not None:
    if current_total > previous_total:
        trajectory = "improving"
    elif current_total == previous_total:
        trajectory = "flat"
    else:
        trajectory = "declining"

config = {}
config_path = Path(os.environ["CONFIG"])
if config_path.exists():
    config = json.loads(config_path.read_text(encoding="utf-8"))
threshold = int(config.get("avo_params", {}).get("tier_escalation_after", 3))
recent_reflections = [
    r for r in records
    if r.get("type") == "reflection"
    and r.get("session_id") == session_id
    and r.get("generation", 0) < generation
]
recent_tail = recent_reflections[-max(0, threshold - 1):]
flat_tail = all(not item.get("improved", False) for item in recent_tail) if recent_tail else False
tier_escalation_justified = trajectory != "improving" and flat_tail

what_worked = []
what_failed = []
for item in winning:
    what_worked.append(f"{item['dimension']}: {item['pattern']} ({item['effect']})")
for item in losing:
    what_failed.append(f"{item['dimension']}: {item['pattern']} ({item['effect']})")
if not what_worked and current_total > 0:
    what_worked.append("current generation establishes the first scored baseline")
if not what_failed and previous is None:
    what_failed.append("no previous generation exists for a regression comparison")

next_moves = []
if tier_escalation_justified:
    next_moves.append("escalate evolution tier before the next generation")
weak_dimensions = sorted(losing, key=lambda item: (item["delta"], item["dimension"]))
for item in weak_dimensions[:2]:
    if item["dimension"] == "diversity":
        next_moves.append("shift weight toward underrepresented platforms")
    elif item["dimension"] == "relevance":
        next_moves.append("tighten queries around exact task entities")
    elif item["dimension"] == "freshness":
        next_moves.append("apply a recency window and prefer fresher platforms")
    elif item["dimension"] == "quantity":
        next_moves.append("increase per-platform limits or broaden one query family")
    elif item["dimension"] == "efficiency":
        next_moves.append("remove overlapping queries and keep the highest-yield wording")
if not next_moves:
    next_moves.append("carry forward the current settings and look for a small Tier 1 improvement")

summary = {
    "session_id": session_id,
    "generation": generation,
    "score_total": current_total,
    "previous_total": previous_total,
    "improved": previous_total is None or current_total > previous_total,
    "what_worked": what_worked,
    "what_failed": what_failed,
    "next_moves": next_moves[:3],
    "winning_patterns": winning,
    "losing_patterns": losing,
    "platform_insights": platform_insights,
    "tier_escalation_justified": tier_escalation_justified,
}

with open(os.environ["SUMMARY"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
3. Append the `reflection` record to `state/worklog.jsonl` and append reusable `winning_pattern`, `losing_pattern`, and `platform_insight` records to `state/patterns.jsonl`.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["SUMMARY"], encoding="utf-8"))
now = os.environ["NOW"]
worklog_path = os.environ["WORKLOG"]
patterns_path = os.environ["PATTERNS"]

reflection = {
    "type": "reflection",
    "ts": now,
    "session_id": summary["session_id"],
    "generation": summary["generation"],
    "score_total": summary["score_total"],
    "improved": summary["improved"],
    "what_worked": summary["what_worked"],
    "what_failed": summary["what_failed"],
    "next_moves": summary["next_moves"],
}

with open(worklog_path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(reflection, ensure_ascii=False) + "\n")

pattern_rows = []
for item in summary["winning_patterns"]:
    pattern_rows.append({
        "type": "winning_pattern",
        "ts": now,
        "session_id": summary["session_id"],
        "generation": summary["generation"],
        "platform": "all",
        "pattern": item["pattern"],
        "effect": item["effect"],
        "evidence": f"generation score {summary['previous_total']}->{summary['score_total']}",
    })
for item in summary["losing_patterns"]:
    pattern_rows.append({
        "type": "losing_pattern",
        "ts": now,
        "session_id": summary["session_id"],
        "generation": summary["generation"],
        "platform": "all",
        "pattern": item["pattern"],
        "effect": item["effect"],
        "evidence": f"generation score {summary['previous_total']}->{summary['score_total']}",
    })
for item in summary["platform_insights"]:
    pattern_rows.append({
        "type": "platform_insight",
        "ts": now,
        "session_id": summary["session_id"],
        "generation": summary["generation"],
        "platform": item["platform"],
        "pattern": item["pattern"],
        "effect": item["effect"],
        "evidence": item["evidence"],
    })

with open(patterns_path, "a", encoding="utf-8") as fh:
    for row in pattern_rows:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
PY
```
4. Print the newly written reflection so the runner can inspect what will guide the next generation.
```bash
tail -n 1 "$WORKLOG"
```

## Parse
Append one UTF-8 JSON object line to `state/worklog.jsonl` with this exact schema:
```json
{"type":"reflection","ts":"ISO8601","session_id":"string","generation":1,"score_total":0.0,"improved":true,"what_worked":["string"],"what_failed":["string"],"next_moves":["string"]}
```
Also append zero or more UTF-8 JSON object lines to `state/patterns.jsonl` with one of these exact logical schemas:
```json
{"type":"winning_pattern","ts":"ISO8601","session_id":"string","generation":1,"platform":"all|platform-name","pattern":"string","effect":"string","evidence":"string"}
{"type":"losing_pattern","ts":"ISO8601","session_id":"string","generation":1,"platform":"all|platform-name","pattern":"string","effect":"string","evidence":"string"}
{"type":"platform_insight","ts":"ISO8601","session_id":"string","generation":1,"platform":"platform-name","pattern":"string","effect":"string","evidence":"string"}
```

## Score Hints
- Favor reflections that tie each improved dimension to an explicit change in query wording, platform mix, or config rather than vague intuition.
- Favor losses that isolate one likely cause per weak dimension because those records are later used for diagnosis and planning.
- `relevance`, `freshness`, and `efficiency` are most useful when the reflection points to a concrete next move instead of a generic complaint.
- Platform insights are strongest when they mention the platform, the query style or limit used, and the score movement they accompanied.

## Known Limitations
- Reflection quality depends on how much of the plan and diagnosis history was recorded in the same session.
- The comparison is generation-level; it cannot prove that any single query or platform caused the score change.
- If only one generation exists, the output is a baseline reflection rather than a true delta analysis.
- If worklog lines are malformed or missing, repair the append-only files before trusting the reflection.

## Evolution Notes
- Tune: none in this file; `reflect.md` is an immutable AVO protocol skill and must not be modified by AVO.
- Tried: compare against the immediately previous generation and infer change levers from diagnosis, evolution, and platform plan deltas.
- Next: keep pattern language concrete so future planning can reuse it without reinterpretation.
