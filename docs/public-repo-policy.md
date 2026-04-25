# Public Repository Policy

> Authoritative list of what may be committed to this repository, what must
> never be committed, and how to handle content that is publishable only
> after redaction. The detailed enforcement layers (gitignore, commit
> hooks, CI workflows) live in [`docs/internal-docs.md`](internal-docs.md);
> this page states the *rules* those layers enforce.

## Rule 1 — Always public

Commit freely:

- Source code under `autosearch/` and `scripts/` (excluding subpaths
  marked private in `.gitignore`).
- Tests under `tests/`.
- Public documentation under `docs/` (install / channels / quickstart /
  introduction / migration / changelog / mcp-clients / security /
  internal-docs / public-repo-policy / testing / roadmap /
  delivery-status / mcp-channels-playbook / local-nightly).
- Top-level project files (`README.md`, `README.zh.md`, `LICENSE`,
  `SECURITY.md`, `CHANGELOG.md`, `pyproject.toml`, `package.json`,
  `commitlint.config.cjs`, `.gitignore`, `.gitleaks.toml`).
- CI workflows under `.github/workflows/` and hooks under `.husky/`.
- Channel skill bundles under `autosearch/skills/`.

## Rule 2 — Never commit

**Never commit** any of the following to this repository, regardless of
intent:

- Real secrets, API keys, tokens, cookies, or session credentials.
  Treat anything that looks like a credential as a credential.
- Internal exec plans (`docs/exec-plans/`), architectural drafts
  (`docs/plans/`), proposals (`docs/proposals/`), spike write-ups
  (`docs/spikes/`), or channel reconnaissance logs
  (`docs/channel-hunt/`).
- Session handoff state (`HANDOFF.md`) or any `*.handoff.md` /
  `*.private.md` draft.
- Runtime experience JSONL files (`experience/`, `**/patterns.jsonl`).
- Per-run reports, benchmarks, or logs (`reports/`).
- macOS metadata (`.DS_Store`).
- Maintainer-private file paths in any committed content
  (e.g. `~/.claude/...` paths that name a single contributor's setup,
  `~/.config/ai-secrets.env`).
- Internal-project codenames belonging to other private projects.
- Personal home-directory paths matching `/Users/<name>` or
  `/home/<name>` outside of clearly placeholder values.
- Internal-voice references like "boss" / "老板" / "未来老板" or other
  approval-flow language naming a specific maintainer.
- The `dangerously-skip-permissions` flag in any user-facing
  documentation. (It exists in test fixtures only.)

These rules are enforced by `.gitignore`, `scripts/committer`,
`.husky/pre-commit`, `.gitleaks.toml`, and the
`.github/workflows/public-hygiene.yml` and gitleaks workflows. If any
gate fires on a legitimate file, add a per-rule allowlist; do not
disable the rule itself.

## Rule 3 — Publishable only after redaction

Some content is publishable in summary form but **must be redacted**
first:

- Validation / benchmark / E2E test reports — strip any maintainer
  paths, secrets references, internal failure narratives, and
  contributor-private setup details. Publish only summary metrics and
  reproducible test recipes (typically as a docs page, not a raw run
  log).
- Experiment write-ups — keep the *finding* (what worked, what didn't,
  why), drop bypass/workaround details that read as adversarial
  guidance against third-party platforms, and drop dated rate-limit
  heuristics that misrepresent stable product capability.
- Migration guides — if they previously linked to internal proposal
  docs, the proposals' factual content must be rewritten inline
  (citing only public sources), and the internal links must be
  removed.

When in doubt, ask: would an external reader find this useful and
representative of stable product behavior? If no on either count, do
not publish.

## Rule 4 — When something slips through

If an internal-only artifact does land in `main`:

1. Open a hygiene PR that removes the file from HEAD and confirms the
   gate that should have caught it. If the gate has a gap, add the
   missing rule (`scripts/committer` deny path, `.gitleaks.toml`
   pattern, or `scripts/validate/public_repo_hygiene.py` rule).
2. Decide whether history rewrite is required. The bar is real
   secrets, real PII, or regulated data — internal narrative alone
   does not justify the disruption of a `git filter-repo`.
3. Document the incident under "Lessons Learned" in `CLAUDE.md` so the
   gate addition is preserved across rewrites.

The triage matrix lives in
`docs/security/history-exposure-assessment.md` (added in a later
hygiene pass).
