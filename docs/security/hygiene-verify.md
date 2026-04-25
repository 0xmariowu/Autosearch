# Public-Repo Hygiene — Verification Procedure

> Companion to `history-exposure-assessment.md`. This page lists the
> commands that prove the hygiene gates are intact and the published
> tree is clean. Run these on `main` after every hygiene-related PR
> merges, and as part of the release-gate pre-flight.

## Prerequisites

- A current clone of `main` (no in-flight branches mixed in).
- Repo-local virtualenv at `.venv/` for the pytest run.
- `git` (built-in) and `npm` (for the `public:hygiene` script alias).
- Standard Unix `grep`. No external dependencies are required.

## Verification commands

Run all six. Each line ends `→ exit 0` on a clean repo. A non-zero
exit means the corresponding hygiene gate fired and must be addressed
before the next release.

### V1 — High-risk path absence

```bash
git ls-files \
    docs/plans docs/proposals docs/spikes docs/channel-hunt \
    HANDOFF.md \
    autosearch/skills/channels/xiaohongshu/experience/patterns.jsonl \
    autosearch/skills/meta/channel-selection/experience/patterns.jsonl \
    tests/eval/spike_2_results.json tests/eval/spike_2_urls.yaml \
  | tee /tmp/autosearch-public-leftovers.txt
test ! -s /tmp/autosearch-public-leftovers.txt
```

Confirms no internal directory or runtime-experience artifact is in the
tracked tree.

### V2 — Internal-voice / private-path grep

```bash
git grep -n -I -E \
    "老板|\\bboss\\b|dangerously-skip-permissions|~/.claude|~/.config/ai-secrets|/Users/|force-with-lease|reflog" \
    -- README.md README.zh.md docs autosearch/skills CLAUDE.md \
       .github .husky scripts \
  && exit 1 || exit 0
```

Catches "老板" / "boss" / dangerous flags / maintainer-private paths
that may have re-entered published files. The `\bboss\b` word boundary
prevents legitimate substring hits like `in_boss_key` (an upstream
Bilibili API field name) from triggering a false positive — see the
"Known false positives" section below.

### V3 — Credential pattern scan

```bash
git grep -n -I -E \
    "sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|Bearer [A-Za-z0-9._~-]{20,}" \
    -- .
```

Standard credential shapes. Exit 0 with "no matches" is the pass
condition. Any hit must be triaged: real → P0 (rotate first, see
`history-exposure-assessment.md`); fake / placeholder → add an
allowlist entry to `.gitleaks.toml`.

### V4 — Tracked-tree hygiene script

```bash
python scripts/validate/public_repo_hygiene.py --tracked
# or
npm run public:hygiene
```

Runs the path-rule + dangerous-flag content-rule check on all
git-tracked files. Exit 0 on clean. The CI workflow
`.github/workflows/public-hygiene.yml` runs the `--paths-only` form on
every PR and push to main; this command is the maintainer's local
equivalent (with content rules included).

### V5 — Test suite

```bash
.venv/bin/python -m pytest tests/unit/ -x -q -m "not real_llm and not slow and not network"
```

The fast-tier subset that runs in ≤ 10 seconds and confirms no doc
edit or hygiene change broke the product. Full suite runs in CI.

### V6 — Working-tree drift check

```bash
git status --short --ignored | grep -E "docs/.DS_Store|reports/|\\.env|docs/exec-plans" || true
```

Warns about local files that are correctly ignored but whose presence
indicates the developer might be about to stage one of them by
accident. This command is informational — exit code is always 0; the
output is the signal.

## Pass criteria

A run is **green** when:

1. V1 — `/tmp/autosearch-public-leftovers.txt` is empty.
2. V2 — exit 0 (no matches, modulo known false positives below).
3. V3 — no output (no credential shapes anywhere in the tree).
4. V4 — `OK: N tracked files clean — no hygiene violations.`
5. V5 — `N passed` from pytest, no failures.
6. V6 — empty output, or only the maintainer-known transient files.

If any of V1 / V2 / V3 / V4 / V5 fails, the corresponding hygiene gate
fired and the leak must be addressed before the next release. Do not
ship around it.

## Known false positives

| Match | File | Reason | Action |
|---|---|---|---|
| `boss` substring inside `in_boss_key` / `InBossKey` | `autosearch/skills/tools/video-to-text-bcut/transcribe.py` | These are upstream Bilibili B-Cut API field names; the literal strings come from the third-party API contract and cannot be renamed locally. | The V2 grep above uses `\bboss\b` (word boundary) to skip this; if you copy the older non-boundary form of the grep from prior plan revisions, expect false positives here. |
| `~/.local/` paths | various `SKILL.md` files, `tests/e2b/matrix.yaml` | Linux XDG Base-Dir convention; not a Tailscale `.local` domain reference. | `.gitleaks.toml` already has a per-rule allowlist for these paths; no action needed. |

## When verification fails

- **V1 or V4 fails**: a path-level rule fired. Either remove the file
  from HEAD or, if it is a legitimate addition, extend the
  `scripts/validate/public_repo_hygiene.py` allowlist (rare).
- **V2 fails on a real leak**: rewrite or remove the offending
  content. Then add a regex / allowlist entry that would have
  blocked it earlier (committer / husky / gitleaks /
  public_repo_hygiene script — pick the layer that should have
  caught it).
- **V3 fails on a real credential**: rotate the credential first, then
  follow `history-exposure-assessment.md` Procedure (steps 1–7).
- **V5 fails**: the doc / hygiene change broke the product. Fix
  forward, do not bypass the hygiene gate.

## Reassessment cadence

Run all six verifications:

- After every PR that modifies any of the hygiene config files
  (`.gitignore`, `.gitleaks.toml`, `.husky/pre-commit`,
  `scripts/committer`, `scripts/validate/public_repo_hygiene.py`,
  `.github/workflows/public-hygiene.yml`,
  `.github/workflows/gitleaks.yml`).
- Before every release tag is pushed.
- When any external party reports a finding through the channel in
  `SECURITY.md`.
