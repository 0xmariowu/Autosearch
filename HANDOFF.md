# AutoSearch Handoff

## feat/v2.2-unified-architecture

**Last session**: 2026-03-29 — v2.2 built, PR #14 open, needs validation + merge

### What is v2.2

V1's proven capabilities (LLM scoring, gene pool, 14 connectors, goal system, anti-cheat, outcome tracking) restored as evolvable skills in superpowers format (name + description, free-form body). Agent autonomy per AVO paper §3 (not pipeline). 29 skills, 7-dimension judge, 378 migrated V1 data entries.

### What's done

F000-F005 + F007 complete. 4 commits on branch. 16/16 judge tests passing. 194/194 V1 tests passing.

### What the new session needs to do

1. **F006: End-to-end validation** — Run `/autosearch "find open-source self-evolving AI agent frameworks and research"` and compare output quality to the native Claude benchmark at `~/self-evolving-agents-research.md`. Key checks:
   - Does llm-evaluate.md filter irrelevant results? (v2.0 gave 0.993 relevance to junk)
   - Does use-own-knowledge.md contribute foundational works? (STaR, Reflexion, Voyager)
   - Does synthesize-knowledge.md produce conceptual framework? (not platform-organized list)
   - Are migrated V1 patterns read during search? (state/patterns.jsonl has 32 entries)
   - Does judge.py output 7 dimensions including latency?

2. **Merge PR #14** after validation passes

3. **Fix any issues found during validation** — skill quality may need refinement after first real run

### Key files

| File | What it is |
|------|-----------|
| `autosearch/v2/PROTOCOL.md` | Agent protocol (106 lines, read this first) |
| `autosearch/v2/judge.py` | 7-dimension scorer (only Python code) |
| `autosearch/v2/skills/` | 29 skills, flat directory |
| `autosearch/v2/state/` | config + migrated V1 data |
| `docs/exec-plans/active/autosearch-0328-v2.2-unified-architecture.md` | Full plan with design rationale |
| `~/self-evolving-agents-research.md` | Native Claude benchmark to compare against |

### Critical context

- Python 3.11+ required for judge.py (`uv run --python 3.11`)
- ddgs package needs Python 3.11+ for SSL
- Pre-push hook auto-rebases on main and runs 194 V1 tests
- v2.0 skill-spec.md was deleted — format is now just name + description
- Meta-skills (create-skill, observe-user, extract-knowledge, interact-user, discover-environment) are IMMUTABLE by AVO

### Experience note

Full session findings at `AIMD/experience/autosearch/2026-03-29-v2.2-unified-architecture.md`. Key lesson: v2.0 was an amputation — removing V1's computational capabilities was the opposite of bitter lesson.

## main

V1 (12,760 lines Python) + V2.0 (PR #12 merged). V2.2 on feature branch (PR #14).
