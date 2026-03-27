#!/usr/bin/env bash
# AutoLoop — continuous self-improvement loop
# Usage: ./autoloop/run_loop.sh [max_iterations]
# Runs until interrupted (Ctrl+C) or max_iterations reached.
# Each iteration: AI modifies search_program.py → run → score → keep/discard

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

MAX_ITER="${1:-0}"  # 0 = infinite
ITER=0
BEST_SCORE=0

LOG_DIR="autoloop"
RESULTS="$LOG_DIR/results.tsv"
PROGRAM="$LOG_DIR/search_program.py"
PREPARE="$LOG_DIR/prepare.py"

# Colors
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'
BOLD='\033[1m'; DIM='\033[0;90m'; NC='\033[0m'

info()  { printf "${GREEN}[loop]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[loop]${NC} %s\n" "$*"; }
fail()  { printf "${RED}[loop]${NC} %s\n" "$*"; }

# Get current best score from results.tsv
if [[ -f "$RESULTS" ]]; then
    BEST_SCORE=$(awk -F'\t' 'NR>1 && $3=="keep" {if($2+0>max) max=$2+0} END{print max+0}' "$RESULTS")
fi
info "starting autoloop — best score so far: $BEST_SCORE"

# Run baseline if no keep entries exist
if [[ "$BEST_SCORE" -eq 0 ]]; then
    info "running baseline..."
    BASELINE_JSON=$(python3 "$PREPARE" 2>/dev/null) || { fail "baseline run failed"; exit 1; }
    BEST_SCORE=$(echo "$BASELINE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['score'])")
    COMMIT=$(git rev-parse --short HEAD)
    printf "%s\t%s\tbaseline\tinitial program\n" "$COMMIT" "$BEST_SCORE" >> "$RESULTS"
    info "baseline score: $BEST_SCORE"
fi

while true; do
    ITER=$((ITER + 1))
    if [[ "$MAX_ITER" -gt 0 && "$ITER" -gt "$MAX_ITER" ]]; then
        info "reached max iterations ($MAX_ITER)"
        break
    fi

    printf "\n${BOLD}=== Iteration $ITER (best: $BEST_SCORE) ===${NC}\n"

    # Step 1: AI modifies search_program.py
    info "asking AI to modify search_program.py..."

    # Build context for the AI: last run's keyword misses + results history
    LAST_RUN_JSON=$(python3 "$PREPARE" 2>/dev/null) || { fail "pre-check run failed, skipping"; continue; }
    LAST_SCORE=$(echo "$LAST_RUN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['score'])")
    KEYWORD_SUMMARY=$(echo "$LAST_RUN_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
dims = sorted(d['dimension_scores'].items(), key=lambda x: x[1])
for dim_id, score in dims:
    detail = d['keyword_detail'].get(dim_id, {})
    hits = detail.get('hits', [])
    misses = detail.get('misses', [])
    print(f'{dim_id}={score}/20: hits={hits[:3]} misses={misses[:5]}')
")
    # Build list of previously failed queries to prevent repeats
    FAILED_QUERIES=$(awk -F'\t' 'NR>1 && $3!="keep" {print $4}' "$RESULTS" 2>/dev/null | tail -10)
    RESULTS_TAIL=$(tail -10 "$RESULTS" 2>/dev/null || echo "(no history)")

    # Use codex exec to modify search_program.py
    codex exec --full-auto -C "$REPO_ROOT" --ephemeral "$(cat <<PROMPT
You are optimizing autoloop/search_program.py to maximize the search score.

Current score: $LAST_SCORE / 100 (best ever: $BEST_SCORE)

Dimensions sorted by score (LOWEST FIRST — fix these first):
$KEYWORD_SUMMARY

Previously failed experiments (DO NOT repeat these):
$FAILED_QUERIES

Full experiment log:
$RESULTS_TAIL

Rules:
- ONLY modify autoloop/search_program.py
- Change ONE thing: add a query, reword a query, remove a bad query, or change providers
- PRIORITY: fix the dimension with the LOWEST score first (shown at top of list above)
- Do NOT repeat a query or approach that already failed (see failed list above)
- Try DIFFERENT search angles: different wording, different providers, different keyword combinations
- Search engines find concrete things: library names, project names, technique names work better than abstract phrases
- Do NOT modify any other file

Read autoloop/search_program.py, make ONE change, save.
PROMPT
)" 2>/dev/null

    # Check if file was actually modified
    if git diff --quiet "$PROGRAM" 2>/dev/null; then
        warn "no changes made, skipping iteration"
        continue
    fi

    # Step 2: Commit
    DESCRIPTION=$(git diff "$PROGRAM" | head -20 | grep '^+[^+]' | head -3 | sed 's/^+//' | tr '\n' ' ' | cut -c1-80)
    git add "$PROGRAM"
    PROJECT_COMMITTER=1 git commit -m "chore: exp $DESCRIPTION" --no-verify 2>/dev/null || {
        warn "commit failed, resetting"
        git checkout -- "$PROGRAM" 2>/dev/null
        continue
    }
    COMMIT=$(git rev-parse --short HEAD)

    # Step 3: Run
    info "running experiment $COMMIT..."
    RUN_JSON=$(python3 "$PREPARE" 2>/dev/null) || {
        fail "run crashed"
        printf "%s\t0\tcrash\t%s\n" "$COMMIT" "$DESCRIPTION" >> "$RESULTS"
        git reset HEAD~1 --hard 2>/dev/null
        continue
    }
    NEW_SCORE=$(echo "$RUN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['score'])")

    # Step 4: Keep / Discard
    if [[ "$NEW_SCORE" -gt "$BEST_SCORE" ]]; then
        BEST_SCORE="$NEW_SCORE"
        printf "%s\t%s\tkeep\t%s\n" "$COMMIT" "$NEW_SCORE" "$DESCRIPTION" >> "$RESULTS"
        info "$(printf "${GREEN}KEEP${NC} score=$NEW_SCORE (new best!) — $DESCRIPTION")"

        # Show what improved
        echo "$RUN_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for dim, detail in d['keyword_detail'].items():
    ds = d['dimension_scores'].get(dim, 0)
    if detail['hits']:
        print(f'  {dim}={ds}: hits={detail[\"hits\"][:4]}')
"
    else
        printf "%s\t%s\tdiscard\t%s\n" "$COMMIT" "$NEW_SCORE" "$DESCRIPTION" >> "$RESULTS"
        warn "$(printf "DISCARD score=$NEW_SCORE (best=$BEST_SCORE) — $DESCRIPTION")"
        git reset HEAD~1 --hard 2>/dev/null
    fi

    # Step 5: Check if we hit 100
    if [[ "$BEST_SCORE" -ge 100 ]]; then
        info "$(printf "${GREEN}${BOLD}SCORE 100 REACHED!${NC}")"
        break
    fi
done

info "final best score: $BEST_SCORE"
info "results: $RESULTS"
