# History Exposure Assessment

> Last assessed: 2026-04-25 (end of public-repo-hygiene plan execution).
> Reassessment cadence: whenever a hygiene gate fires on `main`, or when
> any new evidence of PII / secret leakage surfaces.

## Purpose

Public git history of this repository is permanent unless rewritten with
`git filter-repo` (or equivalent) and force-pushed. History rewrite is
disruptive — it breaks every clone, fork, open PR, and tag reference.
This document classifies *what* leaked into history, *how severe* each
leak is, and *whether* a history rewrite is justified.

## Severity tiers

- **P0** — real secret / credential / PII / regulated data in any commit
  that has been pushed to a public branch. Always justifies a history
  rewrite **after** the credential has been rotated.
- **P1** — unredacted personal contributor identity (real name,
  non-public email, internal hostname) in commit metadata or file
  content. History rewrite is the right answer if the metadata is
  stable; rotate the affected accounts first.
- **P2** — internal-only narrative content (process notes, architectural
  drafts, plan numbering, internal codenames, "boss" voice, etc.) with
  no real-world security cost. HEAD removal is sufficient; history
  rewrite is **not** justified by the disruption-to-readers tradeoff.

Anything that does not fit P0/P1/P2 is **not a leak** — close the
finding without action.

## Current assessment

As of 2026-04-25, after running the hygiene plan (batches 1–3) and
this assessment exercise:

| Tier | Finding | Action taken |
|---|---|---|
| **P0** | None found. Repo-wide grep for the standard credential patterns (`sk-...{20,}`, `sk-ant-...{20,}`, `ghp_...{36}`, `AIzaSy...{33}`, `Bearer ...{20,}`, etc.) returns only test placeholders and clearly-fake example values. **No real secret has been confirmed in tracked content.** | None required. Continue running gitleaks on every PR + push. |
| **P1** | A prior incident leaked a contributor's real name and a non-public hostname into ~56 commits in 2026-04-04. That history was rewritten at the time and the affected accounts were rotated. The lesson became a hard pre-commit gate (author email must be the noreply address; author name must be the public pseudonym; `.gitleaks.toml` patterns reject literal hostname strings). | Closed in 2026-04-04. The pre-commit hook and gitleaks rule prevent recurrence. |
| **P2** | Internal exec plans, architectural drafts, channel reconnaissance logs, session handoff state, "boss" voice in skill READMEs, and dated validation / bench reports were all present in HEAD as of 2026-04-25. None contained real secrets — the cost was misleading public readers, not credential exposure. | Removed from HEAD across hygiene-plan batches 1–3. Enforcement layers (`.gitignore`, `scripts/committer`, `.husky/pre-commit`, `.gitleaks.toml`, `public_repo_hygiene.py`, `.github/workflows/public-hygiene.yml`) prevent reentry. **No history rewrite performed for this tier.** |

## Why no history rewrite for the P2 tier

Three reasons:

1. **No real secret was leaked.** The content is internal narrative —
   plans, proposals, postmortems. Reading old commits exposes process,
   not credentials. There is no rotation work that an attacker could
   skip by reading history.
2. **History rewrite has high collateral cost.** Every fork, clone,
   open PR, and tag reference breaks. CI workflows that pin SHAs
   become invalid. External contributors are left with "your branch
   has diverged" errors and no clean recovery. For P2 content this
   cost dominates.
3. **HEAD removal is the correct floor.** External readers land on
   `main` first; the GitHub UI surfaces the current tree. Old commits
   are visible but require deliberate spelunking. The disclosure
   surface that matters is HEAD, and HEAD is now clean.

## When a history rewrite **is** justified

History rewrite is the right call when **any** of the following is true:

1. A real secret has been confirmed in any pushed commit. Rotate the
   credential first, then rewrite.
2. Personally identifying information (legal name, real email,
   private hostname) of a contributor or any user has been
   committed and is not retractable through normal means.
3. Regulated data (PHI, PII subject to GDPR / HIPAA / similar) has
   entered any commit, regardless of whether it is currently in HEAD.
4. A contributor or external party with legal standing requests
   removal of their content under a takedown policy and the request
   meets the project's stated policy.

If none of these apply, **do not** run `git filter-repo` and **do not**
force-push to `main`. Open a follow-up hygiene plan instead.

## Procedure if a P0 / P1 finding surfaces later

1. **Rotate first, rewrite second.** Whatever credential / identity is
   exposed must be invalidated upstream before history is touched.
2. **Snapshot.** Tag the current `main` HEAD with a dated tag
   (`pre-rewrite-YYYY-MM-DD`) and push it to a private mirror.
3. **Plan the rewrite as its own document.** A separate exec-plan
   listing the affected SHAs, the redaction strategy, the
   force-push timeline, and the contributor communication plan.
4. **Coordinate with all open-PR authors.** They will need to rebase
   or recreate their branches against the new history.
5. **Execute `git filter-repo`** with the planned redaction. Verify
   the rewritten history no longer contains the leak.
6. **Force-push** to `main` and to all live release branches. Update
   tags. Notify forks via the project's normal channels.
7. **Document the incident** in `CLAUDE.md`'s Lessons Learned and
   update the gate that should have caught it.

This document does **not** itself execute a `git filter-repo`; that
command runs only inside a dedicated rewrite plan after Steps 1–4 of
the procedure above.

## Reassessment triggers

Re-evaluate this document when:

- A hygiene gate fires on `main` (committer block, gitleaks fail,
  public-hygiene workflow fail).
- An external party reports a finding through `SECURITY.md`'s
  disclosure channel.
- A contributor's identity or credential changes (rotation,
  account migration).
- Any new content category enters the public repository that did
  not exist at the time of the previous assessment.
