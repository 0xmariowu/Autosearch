# AutoSearch Standards

Standards define stable boundaries for the AutoSearch system.

They are narrower than design docs:

- design docs explain architecture and rationale
- standards define truth sources, handoff objects, scope boundaries, and operational contracts

## Quick Lookup

| I need... | Go here |
|----------|---------|
| How global demand should be modeled before search starts | `standards/demand-standard.md` |
| What search is responsible for, and what it is not | `standards/search-standard.md` |
| What the final search-side handoff should look like | `standards/routeable-map-standard.md` |
| How to store and evolve content candidates before final admission | `standards/content-candidate-standard.md` |
| How reusable machine experience should be stored and consumed | `standards/experience-standard.md` |

## Relationship To Existing Docs

- `docs/2026-03-22-system-architecture.md`
  broad architecture and current operational picture
- `docs/methodology/`
  platform playbooks and search methodology
- `standards/`
  stable contracts for demand, search, routing handoff, candidate storage, and experience

## Deliberate Gap

These standards stop before final knowledge-base admission.

That part should be defined later, after the project agrees on:

- what counts as Armory-worthy vs AIMD-worthy vs project-local
- which destinations are auto-routable
- which steps still require stricter review gates
