---
name: auto-evolve
description: "Use after check-rubrics to run one AVO evolution step: diagnose failed rubrics, modify one skill or config, commit the change, and record the evolution for future verification."
---

# Purpose

This is the AVO core evolution skill.
Run it after each search session to make the system slightly better for the next session.
Do one targeted improvement, not a rewrite.

The loop is:
measure failure, diagnose the weakest point, change one file, commit it, and record what should improve next time.
The goal is controlled adaptation that can be verified later.

# When To Use

Use immediately after `check-rubrics.md` has written:
- `autosearch/v2/evidence/checked-rubrics-{topic-slug}.jsonl`
- the matching rubric summary in `autosearch/v2/state/rubric-history.jsonl` if it exists

Run exactly once per session.
Use the same `topic-slug` and session identifier as the delivery and rubric check.
Verification of prior evolutions is mandatory before proposing a new change when prior data exists.

# Evolution Logic

## Scope

This skill performs ONE evolution step per session.
One step means one diagnosis, one file modified at most, one commit, one appended evolution record.
Do not turn a weak session into a multi-file cleanup.

## Step 0: Verify Prior Evolutions First

Before making a new change, read `autosearch/v2/state/evolution-log.jsonl` if it exists.
Look for prior entries on the same topic or a clearly similar topic.

If a prior entry has `expected_flips` that appear in the current session's rubrics:
- check whether each expected rubric flipped from failed to passed
- if a rubric flipped, record that the prior evolution was validated
- if a rubric did not flip, record that the prior evolution failed verification

If a prior evolution modified `state/channel-scores.jsonl`:
- Check whether the affected channel's results improved in the current session
- Compare: did the channel return more relevant results this time?
- If yes, mark the evolution as validated
- If no (channel still underperforming), consider reverting the score change

If a prior change had no verified positive effect, consider `git revert` for that commit before making a new change.
Only revert when the evidence is clear and the revert will not undo unrelated work.
Record the verification result in the new evolution entry.

## Step 1: Read Failures

Read `autosearch/v2/evidence/checked-rubrics-{topic-slug}.jsonl`.
Find every rubric with `passed: false`.

Get `pass_rate` from the latest matching summary in `autosearch/v2/state/rubric-history.jsonl` when available.
If that summary does not exist yet, compute `pass_rate` from the checked rubrics file.

If `pass_rate >= 0.90`, skip evolution.
Still append a skip entry to `autosearch/v2/state/evolution-log.jsonl` with the topic, timestamp, pass rate, failed rubric ids, and reason: `skip: pass rate already >= 0.90`.
Do not modify any skill or config file in this case.

## Step 2: Aggregate By Category

Group failed rubrics by `category`.
Use the rubric history summary when available to compare category pass rates.
Identify the weakest category as the one with the lowest pass rate.

If two categories tie, break the tie in this order:
1. more failed `high` priority rubrics
2. more total failed rubrics
3. the category with the clearest single root cause

## Step 3: Select Target Rubrics

From the weakest category, select the top 3 failed rubrics.
Prefer `high` priority first, then `medium`, then `low`.
If fewer than 3 failed rubrics exist in that category, use all of them.

These target rubrics define the only improvement scope for this session.
Do not optimize for failures outside the target set unless the same one-file change obviously helps them too.

## Step 4: Diagnose Root Cause

For each target rubric, determine why it failed.
Do not guess from the rubric text alone.
Read the relevant mutable skill or state file first so the diagnosis reflects current behavior.

Diagnosis map:

| Category failed | Root cause | First action (data) | Second action (skill rule) |
|---|---|---|---|
| information-recall: wrong channels | channel-scores.jsonl outdated | Update `state/channel-scores.jsonl` — increase/decrease scores | Add topic→channel rule in `select-channels.md` |
| information-recall: query missed | Missing query type | Add mandatory query rule in `gene-query.md` | Add pattern to `state/patterns-v2.jsonl` |
| information-recall: found but not synthesized | Synthesis dropped results | Add citation enforcement rule in `synthesize-knowledge.md` | — |
| analysis: insufficient depth | Missing analysis template | Add analysis requirement in `synthesize-knowledge.md` | — |
| presentation: URL missing | Citation rules too weak | Strengthen citation rules in `synthesize-knowledge.md` | — |

Write a one-line diagnosis that names the concrete failure mode.
Good diagnosis: `product topics were not forcing Product Hunt, so commercial launch coverage was missing`.
Bad diagnosis: `search quality was low`.

## Step 5: Apply ONE Modification

Choose the single most impactful change that could flip the target rubrics.
Allowed change types:
- add a rule or heuristic to one skill file
- update weights in `autosearch/v2/state/channel-scores.jsonl`
- add one pattern entry to `autosearch/v2/state/patterns-v2.jsonl`
- add analysis or presentation instructions to `autosearch/v2/skills/synthesize-knowledge.md`

### Evolution priority order

When multiple changes could fix the target rubrics, prefer:
1. **Data file update** (`state/channel-scores.jsonl`, `state/patterns-v2.jsonl`) — most precise, easiest to verify and revert
2. **Specific rule addition** (add one heuristic/rule to a skill) — targeted, testable
3. **Structural change** (rewrite a skill section) — last resort, hardest to verify

Data-driven evolution > rule-based evolution > structural evolution.

Rules:
- modify only ONE file
- make the SMALLEST change likely to flip the target rubrics
- prefer a local heuristic over a broad rewrite
- keep the evaluation function stable

Do NOT modify:
- `autosearch/v2/skills/auto-evolve.md`
- `autosearch/v2/skills/create-skill.md`
- `autosearch/v2/skills/observe-user.md`
- `autosearch/v2/skills/extract-knowledge.md`
- `autosearch/v2/skills/interact-user.md`
- `autosearch/v2/skills/discover-environment.md`
- `autosearch/v2/skills/generate-rubrics.md`
- `autosearch/v2/skills/check-rubrics.md`
- `autosearch/v2/judge.py`
- `autosearch/v2/PROTOCOL.md`

If multiple files appear responsible, pick the earliest upstream file that offers the cleanest leverage.
If no single-file change is credible, record that the session is blocked by diagnosis ambiguity and do not make a random edit.

## Step 6: Commit

Commit the change with `git commit`.
Never amend.

Use this exact message format:

```text
avo: [action summary]

Failed rubrics: [r003, r015]
Diagnosis: [one-line diagnosis]
Modified: [file path]
Expected flips: [r003, r015]
```

The commit should correspond to exactly one file change for the evolution step.

## Step 7: Record

Append one JSON object to `autosearch/v2/state/evolution-log.jsonl`.
Use append-only logging.
Do not rewrite prior entries.

Base schema:

```json
{
  "session": "2026-04-01-self-evolving-agents",
  "timestamp": "2026-04-01T10:05:00Z",
  "topic": "self-evolving-agents",
  "rubric_pass_rate": 0.72,
  "failed_rubrics": ["r003", "r007", "r012", "r015", "r019", "r022", "r025"],
  "weakest_category": "information-recall",
  "target_rubrics": ["r003", "r015", "r019"],
  "diagnosis": "producthunt channel not selected for product-related topics",
  "action": "added producthunt to select-channels.md for product-type topics",
  "modified_file": "autosearch/v2/skills/select-channels.md",
  "commit_hash": "abc1234",
  "expected_flips": ["r003", "r015"]
}
```

Also include when applicable:
- `verification`: validated or failed results for prior `expected_flips`
- `skip_reason`: for pass-rate skips
- `stall_detected`: true or false
- `stall_reason`: short explanation
- `reverted_commit`: commit hash if a revert was performed

## Step 8: Stall Detection

Check the last 3 evolution entries with verification data.
If all 3 show 0 rubric flips verified, the system is stalled.

When stalled:
1. review the last 3 diagnoses
2. if they target the same root cause, assume the diagnosis is wrong and choose a different cause
3. if they target different causes, assume the changes were too small and allow a somewhat larger structural change in one file

Log stall detection explicitly in the new evolution entry.
Do not keep repeating the same tiny fix if verification shows no movement.

## Decision Standard

Prefer changes that are:
- traceable from failed rubric to root cause
- small enough to isolate
- likely to flip specific rubric ids next session
- easy to verify later

Avoid:
- vague quality tweaks
- multi-file "cleanup"
- changing the judge or rubric generator to make scores easier
- edits that cannot plausibly explain the failed rubrics

# Quality Bar

This skill is working when each session produces one of two outcomes:
- a logged skip because quality is already high enough
- one small, defensible change with a clear diagnosis, a clean commit, and an append-only evolution record

A good evolution step is falsifiable.
Another session should be able to verify whether the expected rubrics flipped.
If the change cannot be verified later, the evolution was too vague.
