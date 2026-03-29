---
name: stuck
type: avo
version: "1.0"
requires: [python3]
triggers: [stuck, stagnation, no progress, plateau]
cost: free
platforms: []
dimensions: []
---
## Purpose
Detect stagnation from recent generation scores, redirect strategy based on the weakest dimension, and record the self-supervision action required by the protocol.

## When to Use
- Use when recent `search_run` totals suggest a flat or decreasing trajectory and the runner needs to decide whether to switch strategy, escalate to Tier 3, or deliver the best result.
- Prefer this skill for `PROTOCOL.md` Section 5 self-supervision because it converts score windows into concrete redirects.
- Requires `state/config.json`, recent `search_run` records, and any prior `stuck_event` history in `state/worklog.jsonl`.
- Do not use it to edit `skills/avo/`; the redirect must happen through mutable config or through Tier 3 platform creation.

## Execute
1. Define runtime paths, defaults, and a temporary file for the stagnation decision.
```bash
WORKLOG="${WORKLOG:-state/worklog.jsonl}"
CONFIG="${CONFIG:-state/config.json}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SESSION_ID="${SESSION_ID:-}"
GENERATION="${GENERATION:-}"
STUCK_JSON="$(mktemp)"
export WORKLOG CONFIG NOW SESSION_ID GENERATION STUCK_JSON
```
2. Read the last `N` generation scores, detect flat or decreasing stagnation, and identify the weakest dimension from the latest scored run.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

worklog_path = Path(os.environ["WORKLOG"])
config_path = Path(os.environ["CONFIG"])
session_id = os.environ.get("SESSION_ID", "").strip()

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
search_runs = sorted(search_runs, key=lambda item: item.get("generation", 0))

config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
window = int(config.get("avo_params", {}).get("stuck_window", 3))
threshold = float(config.get("avo_params", {}).get("stuck_threshold", 1.01))
recent = search_runs[-window:]
scores = [float(r.get("score", {}).get("total", 0.0)) for r in recent]
flat = bool(scores) and max(scores) <= min(scores) * threshold
decreasing = len(scores) >= 2 and all(scores[i] <= scores[i - 1] for i in range(1, len(scores)))

latest = recent[-1] if recent else {}
dimensions = latest.get("score", {}).get("dimensions", {}) or {}
weakest_dimension = min(dimensions.items(), key=lambda item: (float(item[1]), item[0]))[0] if dimensions else "relevance"
all_dimensions_low = bool(dimensions) and all(float(value) <= 0.35 for value in dimensions.values())

prior_stuck = [
    r for r in records
    if r.get("type") == "stuck_event"
    and (not session_id or r.get("session_id") == session_id)
]

summary = {
    "session_id": session_id or (latest.get("session_id", "") if latest else ""),
    "generation": latest.get("generation", int(os.environ.get("GENERATION") or 0)),
    "window": window,
    "scores": scores,
    "flat": flat,
    "decreasing": decreasing,
    "mode": "flat" if flat else ("decreasing" if decreasing else ""),
    "weakest_dimension": weakest_dimension,
    "all_dimensions_low": all_dimensions_low,
    "prior_action": prior_stuck[-1].get("action", "") if prior_stuck else "",
    "latest_evidence_path": latest.get("evidence_path", ""),
}

with open(os.environ["STUCK_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
3. Exit cleanly when the score window is not stuck; otherwise choose the redirect action using the weakest dimension and any prior stuck handling state.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["STUCK_JSON"], encoding="utf-8"))
if not (summary["flat"] or summary["decreasing"]):
    raise SystemExit(0)

prior_action = summary.get("prior_action", "")
if prior_action == "platform_creation":
    summary["action"] = "deliver"
elif prior_action == "strategy_switch":
    summary["action"] = "platform_creation"
else:
    summary["action"] = "strategy_switch"

with open(os.environ["STUCK_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
4. Apply the redirect to mutable config according to the weakest dimension, or prepare Tier 3 escalation or delivery when strategy switching is exhausted.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

summary = json.load(open(os.environ["STUCK_JSON"], encoding="utf-8"))
if not summary.get("action"):
    raise SystemExit(0)

config_path = Path(os.environ["CONFIG"])
config = json.loads(config_path.read_text(encoding="utf-8"))
weakest = summary["weakest_dimension"]
action = summary["action"]

if action == "strategy_switch":
    if summary.get("all_dimensions_low"):
        config.setdefault("query_strategy", {})["needs_user_clarification"] = True
    elif weakest == "diversity":
        weights = config.setdefault("platform_weights", {})
        dominant = None
        underrepresented = []
        counts = {}
        evidence_path = summary.get("latest_evidence_path")
        if evidence_path and Path(evidence_path).exists():
            with open(evidence_path, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    source = json.loads(line).get("source", "")
                    counts[source] = counts.get(source, 0) + 1
        if counts:
            dominant = max(counts, key=counts.get)
            underrepresented = [name for name in weights if counts.get(name, 0) < counts[dominant]]
        else:
            dominant = max(weights, key=weights.get)
            underrepresented = [min(weights, key=weights.get)]
        if dominant in weights:
            weights[dominant] = round(weights[dominant] / 2.0, 3)
        for name in underrepresented:
            if name in weights:
                weights[name] = round(weights[name] * 2.0, 3)
    elif weakest == "relevance":
        strategy = config.setdefault("query_strategy", {})
        current = strategy.get("expansion_method", "role_perspective")
        strategy["expansion_method"] = "synonym_chain" if current == "role_perspective" else "role_perspective"
    elif weakest == "freshness":
        config.setdefault("query_strategy", {})["default_since_days"] = 180
    elif weakest == "quantity":
        strategy = config.setdefault("query_strategy", {})
        strategy["limit_multiplier"] = max(2, int(strategy.get("limit_multiplier", 1)) * 2)
    elif weakest == "efficiency":
        routing = config.setdefault("model_routing", {})
        if routing.get("search") == "haiku":
            routing["search"] = "sonnet"
elif action == "platform_creation":
    config.setdefault("avo_params", {})["evolution_tier"] = 3
else:
    config.setdefault("avo_params", {})["delivery_reason"] = "stuck after Tier 3"

config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
```
5. Append one `stuck_event` record that captures the score window and the chosen action.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["STUCK_JSON"], encoding="utf-8"))
if not summary.get("action"):
    raise SystemExit(0)

record = {
    "type": "stuck_event",
    "ts": os.environ["NOW"],
    "session_id": summary["session_id"],
    "generation": summary["generation"],
    "window": summary["window"],
    "scores": summary["scores"],
    "mode": summary["mode"],
    "action": summary["action"],
}

with open(os.environ["WORKLOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
PY
```

## Parse
Append one UTF-8 JSON object line to `state/worklog.jsonl` with this exact schema:
```json
{"type":"stuck_event","ts":"ISO8601","session_id":"string","generation":1,"window":3,"scores":[0.0,0.0,0.0],"mode":"flat|decreasing","action":"strategy_switch|platform_creation|deliver"}
```
The skill may also mutate `state/config.json` to apply the redirect that matches the chosen action.

## Score Hints
- `flat` and `decreasing` are protocol-level triggers; do not invent alternative stagnation thresholds when config already supplies them.
- A strong redirect changes the weakest dimension's most direct lever, not a random nearby setting.
- `diversity` and `quantity` redirects should visibly alter platform coverage, while `relevance` and `freshness` redirects should visibly alter query shape or recency bias.
- Delivery is the last resort after both a strategy switch and Tier 3 platform creation fail to move the score window.

## Known Limitations
- The windowed score view can miss slow upward trends if the configured threshold is too strict or too loose for the task.
- Underrepresented platform detection uses recent evidence counts when available; that is still only a proxy for true source quality.
- `query_strategy.limit_multiplier` and `query_strategy.default_since_days` require the planner to honor those config keys on the next generation.
- If all dimensions are weak because the task itself is vague, this skill can only mark the need for clarification; the human still has to provide it.

## Evolution Notes
- Tune: none in this file; `stuck.md` is an immutable AVO protocol skill and must not be modified by AVO.
- Tried: escalate from strategy switch to Tier 3 and only then to delivery so the protocol exhausts cheap redirects first.
- Next: keep stagnation handling tied to score windows and explicit weakest-dimension redirects rather than ad hoc intuition.
