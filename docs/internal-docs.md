# Internal Records and the Public Repository

> What this is: a brief contributor-facing note explaining what kinds of
> working files are deliberately kept **out** of the public repository,
> and how that is enforced.

## What stays public

The public repository on GitHub holds material that is useful to anyone
running, integrating, or contributing to AutoSearch:

- Source code under `autosearch/` and `scripts/`
- User documentation under `docs/` (install / channels / quickstart /
  MCP-clients / migration / changelog / security)
- Tests under `tests/`
- Release artifacts (`CHANGELOG.md`, `pyproject.toml`, `package.json`,
  release workflow)
- Channel skill bundles under `autosearch/skills/`

## What stays out of the public repository

Some working files have value during development but no value as
published reference material — they are kept in the contributor's local
working tree (or in private knowledge bases) and never tracked in git:

| Category | Where it lives locally | Why it is not published |
|---|---|---|
| Internal exec plans | `docs/exec-plans/` | Working drafts and status logs; readers without the surrounding context will be misled. |
| Architectural drafts and pre-implementation proposals | `docs/plans/`, `docs/proposals/` | Pre-decision sketches; final results land in real docs once shipped. |
| One-shot experiment write-ups | `docs/spikes/` | Transient harnesses whose conclusions are already encoded in product behavior. |
| Channel reconnaissance logs | `docs/channel-hunt/` | Rate-limit heuristics and anti-bot notes that misrepresent stable product capability. |
| Session handoff state | `HANDOFF.md` | Per-session continuity notes; not user-facing. |
| Runtime experience JSONL | `experience/`, `**/patterns.jsonl` | Live query patterns accumulated during use; user-private by design. |
| Per-run E2B reports | `reports/` | Local bench artifacts, transient. |
| Drafts | `*.private.md`, `*.handoff.md` | Explicitly marked drafts; never publish-ready. |

If a working file becomes publish-worthy, the right move is to
**rewrite it** into a stable doc under `docs/` (or into a `SKILL.md` for
channel-shaped content) — not to copy or rename the working file.

## How it is enforced

Three layers stop internal records from re-entering the public repository:

1. **`.gitignore`** — every category above is ignored at the repo root.
   New files in those paths are never tracked unless someone explicitly
   bypasses the ignore rule.

2. **`scripts/committer` + `.husky/pre-commit`** — local commit gates.
   `committer` refuses to stage internal-doc paths; the `pre-commit`
   hook rejects any commit whose staged paths or content match
   hygiene rules (e.g., `dangerously-skip-permissions`, `HANDOFF.md`).

3. **CI (`gitleaks` + `public-hygiene` workflows)** — server-side gates.
   `gitleaks` scans for secrets and codenames on every PR and main
   push. `public-hygiene` (see `.github/workflows/public-hygiene.yml`)
   runs `scripts/validate/public_repo_hygiene.py` and fails the build
   if any of the above categories appear in the tracked tree.

If any of these gates fires unexpectedly on a legitimate file, the fix
is to add an allowlist entry in the matching config — never to disable
the rule itself.

## Why this matters

Internal-only material is useful, but in the public repository it costs
more than it earns:

- Stale plans look like roadmap and mislead users about what to expect.
- Failed-experiment write-ups misrepresent stable product capability.
- Channel reconnaissance notes can read as adversarial guidance.
- Runtime patterns are user-private; tracking them violates that.

The split keeps the public repository focused on what an external
reader can actually consume, run, or build on.
