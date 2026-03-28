---
name: evolve
type: avo
version: "1.0"
requires: [git, python3]
triggers: [evolve, adapt, improve, optimize]
cost: free
platforms: []
dimensions: []
---
## Purpose
Decide whether the current generation's mutable changes should be kept or reverted, apply the appropriate evolution tier, and record the git outcome for Step 5 of the protocol.

## When to Use
- Use in `PROTOCOL.md` Step 5 after the best `search_run` for the generation is known and any diagnosis retries are finished.
- Prefer this skill when the runner must choose `keep` versus `revert` using judge score trajectory instead of intuition.
- Requires a clean understanding of mutable versus append-only assets: only `state/config.json`, `skills/strategies/`, and `skills/platforms/` are revertable.
- Do not use it to modify `skills/avo/`; AVO skills are fixed protocol and are not mutable by AVO.

## Execute
1. Define paths, defaults, and temporary files used to compute the decision.
```bash
WORKLOG="${WORKLOG:-state/worklog.jsonl}"
PATTERNS="${PATTERNS:-state/patterns.jsonl}"
CONFIG="${CONFIG:-state/config.json}"
NOW="${NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
SESSION_ID="${SESSION_ID:-}"
GENERATION="${GENERATION:-}"
DECISION_JSON="$(mktemp)"
GIT_ACTION_FILE="$(mktemp)"
GIT_REF_FILE="$(mktemp)"
printf '%s' "none" > "$GIT_ACTION_FILE"
: > "$GIT_REF_FILE"
export WORKLOG PATTERNS CONFIG NOW SESSION_ID GENERATION DECISION_JSON GIT_ACTION_FILE GIT_REF_FILE
```
2. Read the current score, the previous best score, recent evolution history, and any stuck signal so the tier and keep-or-revert decision are explicit.
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
    raise SystemExit("evolve.md: no search_run found for the requested generation")

session_id = session_id or current.get("session_id", "")
current_score = float(current.get("score", {}).get("total", 0.0))
prior_runs = [r for r in search_runs if r.get("generation", 0) < generation]
previous_best = max((float(r.get("score", {}).get("total", 0.0)) for r in prior_runs), default=0.0)
decision = "keep" if current_score > previous_best else "revert"

config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
current_tier = int(config.get("avo_params", {}).get("evolution_tier", 1))
escalation_after = int(config.get("avo_params", {}).get("tier_escalation_after", 3))

evolution_history = [
    r for r in records
    if r.get("type") == "evolution"
    and r.get("session_id") == session_id
    and r.get("generation", 0) < generation
]

flat_tier1 = 0
for record in reversed(evolution_history):
    if int(record.get("tier", 1)) != 1:
        break
    if float(record.get("score_after", 0.0)) <= float(record.get("score_before", 0.0)):
        flat_tier1 += 1
    else:
        break
if current_tier == 1 and current_score <= previous_best:
    flat_tier1 += 1

stuck_events = [
    r for r in records
    if r.get("type") == "stuck_event"
    and r.get("session_id") == session_id
    and r.get("generation", 0) <= generation
]
latest_stuck = stuck_events[-1] if stuck_events else {}

target_tier = current_tier
if latest_stuck.get("action") in {"platform_creation", "deliver"}:
    target_tier = 3
elif current_tier == 1 and flat_tier1 >= escalation_after:
    target_tier = 2

diagnoses = [
    r for r in records
    if r.get("type") == "diagnosis"
    and r.get("session_id") == session_id
    and r.get("generation") == generation
]
latest_diagnosis = diagnoses[-1] if diagnoses else {}
changes = []
fix = latest_diagnosis.get("fix", {})
if fix:
    changes.append(fix.get("path", "state/config.json"))
if target_tier == 2:
    changes.append("skills/strategies/")
if target_tier == 3:
    changes.append("skills/platforms/")
if not changes:
    changes.append("state/config.json")

summary = {
    "session_id": session_id,
    "generation": generation,
    "score_before": previous_best,
    "score_after": current_score,
    "decision": decision,
    "current_tier": current_tier,
    "target_tier": target_tier,
    "changes": list(dict.fromkeys(changes)),
    "pattern_text": latest_diagnosis.get("hypothesis") or f"generation {generation} score {previous_best}->{current_score}",
}

with open(os.environ["DECISION_JSON"], "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False)
PY
```
3. If the current score beats the previous best, keep the mutable changes, stage only config and mutable skill paths, and commit them with a non-interactive message that includes the required trailer.
```bash
python3 - <<'PY'
import json
import os
summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
if summary["decision"] != "keep":
    raise SystemExit(0)
print("KEEP")
PY

TIER="$(python3 -c "import json,os; print(json.load(open(os.environ['DECISION_JSON']))['target_tier'])")"
git add state/config.json
[ "$TIER" -ge 2 ] && git add skills/strategies/
[ "$TIER" -ge 3 ] && git add skills/platforms/
GEN_VALUE="$(python3 - <<'PY'
import json, os
summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
print(summary["generation"])
PY
)"
WHAT_CHANGED="$(python3 - <<'PY'
import json, os
summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
print(", ".join(summary["changes"])[:120] or "mutable search assets")
PY
)"
SCORE_RANGE="$(python3 - <<'PY'
import json, os
summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
print(f"{summary['score_before']}->{summary['score_after']}")
PY
)"
if ! git diff --cached --quiet; then
  git commit \
    -m "avo: gen ${GENERATION:-$GEN_VALUE} - ${WHAT_CHANGED} - score ${SCORE_RANGE}" \
    -m "Co-authored-by: Codex <noreply@openai.com>"
  printf '%s' "commit" > "$GIT_ACTION_FILE"
  git rev-parse HEAD > "$GIT_REF_FILE"
fi
```
4. If the current score does not beat the previous best, revert only mutable config and strategy or platform files, preserving append-only logs, evidence, and delivery artifacts.
```bash
python3 - <<'PY'
import json
import os
summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
if summary["decision"] != "revert":
    raise SystemExit(0)
print("REVERT")
PY

git diff --quiet -- state/config.json skills/strategies/ skills/platforms/ || \
  git checkout -- state/config.json skills/strategies/ skills/platforms/
printf '%s' "revert" > "$GIT_ACTION_FILE"
git rev-parse HEAD > "$GIT_REF_FILE"
```
5. If tier escalation is required, update `config.avo_params.evolution_tier` and commit that change even if the generation itself was reverted.
```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
config_path = Path(os.environ["CONFIG"])
config = json.loads(config_path.read_text(encoding="utf-8"))
target_tier = int(summary["target_tier"])
current_tier = int(summary["current_tier"])
if target_tier == current_tier:
    raise SystemExit(0)
config.setdefault("avo_params", {})["evolution_tier"] = target_tier
config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
print(f"{current_tier}->{target_tier}")
PY

if ! git diff --quiet -- state/config.json; then
  git add state/config.json
  git commit \
    -m "avo: tier escalation gen ${GENERATION:-0}" \
    -m "Co-authored-by: Codex <noreply@openai.com>"
  printf '%s' "commit" > "$GIT_ACTION_FILE"
  git rev-parse HEAD > "$GIT_REF_FILE"
fi
```
6. Append the `evolution` record to `state/worklog.jsonl` and the matching winning or losing pattern to `state/patterns.jsonl`.
```bash
python3 - <<'PY'
import json
import os

summary = json.load(open(os.environ["DECISION_JSON"], encoding="utf-8"))
now = os.environ["NOW"]
git_action = open(os.environ["GIT_ACTION_FILE"], encoding="utf-8").read().strip() or "none"
git_ref = open(os.environ["GIT_REF_FILE"], encoding="utf-8").read().strip()

evolution = {
    "type": "evolution",
    "ts": now,
    "session_id": summary["session_id"],
    "generation": summary["generation"],
    "tier": summary["target_tier"],
    "decision": summary["decision"],
    "score_before": summary["score_before"],
    "score_after": summary["score_after"],
    "git": {
        "action": git_action,
        "ref": git_ref,
    },
    "changes": summary["changes"],
}

pattern = {
    "type": "winning_pattern" if summary["decision"] == "keep" else "losing_pattern",
    "ts": now,
    "session_id": summary["session_id"],
    "generation": summary["generation"],
    "platform": "all",
    "pattern": summary["pattern_text"],
    "effect": f"score {summary['score_before']}->{summary['score_after']}",
    "evidence": ",".join(summary["changes"]),
}

with open(os.environ["WORKLOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(evolution, ensure_ascii=False) + "\n")

with open(os.environ["PATTERNS"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(pattern, ensure_ascii=False) + "\n")
PY
```

## Parse
Append one UTF-8 JSON object line to `state/worklog.jsonl` with this exact schema:
```json
{"type":"evolution","ts":"ISO8601","session_id":"string","generation":1,"tier":1,"decision":"keep|revert","score_before":0.0,"score_after":0.0,"git":{"action":"commit|revert|none","ref":"string"},"changes":["string"]}
```
Also append one UTF-8 JSON object line to `state/patterns.jsonl` with this logical schema:
```json
{"type":"winning_pattern|losing_pattern","ts":"ISO8601","session_id":"string","generation":1,"platform":"all","pattern":"string","effect":"string","evidence":"string"}
```

## Score Hints
- The primary keep-or-revert boundary is `current score > previous best`; do not soften it with subjective judgment.
- Tier escalation is justified only by trajectory evidence such as repeated flat Tier 1 generations or an explicit stuck signal.
- Good evolution records name the mutable path changed so later reflection can connect score movement to a lever.
- Reverts are correct when they preserve append-only logs and only touch mutable search assets.

## Known Limitations
- `git checkout -- ...` discards uncommitted mutations in the listed mutable paths, so the runner must keep unrelated user work out of those paths before using this skill.
- A reverted generation can still produce a follow-up tier escalation commit if the protocol needs to preserve the new tier value.
- If git is unavailable or the repository is not initialized, the decision can still be logged but the git ref may be blank.
- This skill assumes score comparison happens within the active session unless the runner explicitly supplies a different `SESSION_ID`.

## Evolution Notes
- Tune: none in this file; `evolve.md` is an immutable AVO protocol skill and must not be modified by AVO.
- Tried: separate the revert path from the tier-escalation commit so append-only logs, evidence, and delivery artifacts remain untouched.
- Next: keep all commit and revert commands non-interactive and limited to mutable search assets.
