# AutoLoop — Search Program Optimization

> Instructions for the AI agent. Read this before each experiment.

## Setup

You are optimizing a search program to score 100 on a goal case.

**Files:**
- `autoloop/search_program.py` — the ONE file you modify (queries, providers, strategy)
- `autoloop/prepare.py` — FROZEN. Runs search + scores. Never modify this.
- `autoloop/results.tsv` — experiment log. Append after each run.

**Goal:** Achieve the lowest gap to score 100 by finding search queries that produce evidence matching all dimension keywords.

## How scoring works

The goal case has 5 dimensions, each worth 20 points (total 100):
- `extraction_completeness` — needs 4/8 keyword hits for 20
- `label_separation` — needs 4/8 keyword hits for 20
- `pair_extract` — needs 4/8 keyword hits for 20 (also has structural scoring)
- `validation_release` — needs 3/7 keyword hits for 20
- `dedupe_quality` — needs 4/8 keyword hits for 20

The score output tells you exactly which keywords are HIT and which are MISSED. Use misses to write better queries.

## Experiment loop

Repeat forever:

1. **Read** `search_program.py` and `results.tsv` (past experiments)
2. **Think** about what to change. Focus on missed keywords from the last run.
3. **Edit** `search_program.py` — change ONE thing:
   - Add a query targeting a missed keyword
   - Remove a query that never produces hits
   - Change providers
   - Reword a query to be more searchable
4. **Commit** the change: `git add autoloop/search_program.py && git commit -m "exp: <description>"`
5. **Run**: `cd /Users/dev/Projects/autosearch && python3 autoloop/prepare.py > autoloop/run.log 2>&1`
6. **Read results**: extract score from run.log
7. **Decide**:
   - Score improved → **keep** (advance branch)
   - Score equal or worse → **discard** (`git reset HEAD~1 --hard`)
8. **Log** to `results.tsv`: `commit\tscore\tstatus\tdescription`
9. **Go to 1**

## What you CAN change

- Queries in QUERIES list (add, remove, reword)
- Providers in PROVIDERS list
- PER_QUERY_CAP value

## What you CANNOT change

- `prepare.py` (the evaluation harness)
- `goal_cases/*.json` (the goal case definition)
- Any file outside `autoloop/search_program.py`
- Do not install packages

## Tips

- Read the keyword misses carefully. If "near duplicate" is missed, write a query containing those exact words.
- Search engines respond to specific, concrete terms. "near duplicate detection python library" works better than "dedupe quality".
- If a query produces 0 results, try a more common phrasing.
- If all queries for a dimension are failing, try a completely different angle.
- Look at what HIT — understand why, and find similar queries for missed keywords.
