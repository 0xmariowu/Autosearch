# /autosearch — Self-Evolving Search

Run a complete AutoSearch v2 session. Read and follow `autosearch/v2/PROTOCOL.md` as your operating system.

## Arguments

$ARGUMENTS — the search task (e.g., "find AI agent frameworks", "research vector databases", "discover new MCP servers")

If no arguments provided, ask the user what to search for.

## Execution

1. Read `autosearch/v2/PROTOCOL.md` in full
2. Read `autosearch/v2/state/config.json` for current parameters
3. Follow the protocol exactly:
   - Create task_spec from the user's input
   - Run the AVO loop: PLAN → SEARCH → SCORE → DIAGNOSE → EVOLVE → RECORD
   - Use Python 3.11+ to run `judge.py` (system python3 may be 3.9)
   - Deliver when score meets threshold or generations exhausted
4. Report results with evidence

## Key constraints

- `judge.py` is the only evaluator — never self-assess quality
- All search APIs are free (gh, curl, ddgs)
- State files are append-only (worklog.jsonl, patterns.jsonl)
- Config/skill changes go through git commit/revert
- Read the relevant skill file before executing any capability
