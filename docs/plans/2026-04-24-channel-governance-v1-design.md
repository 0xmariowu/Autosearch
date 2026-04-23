# Channel Governance V1

## Goal

Make channel onboarding and channel runtime governance derive from the same declared metadata instead of drifting across:

- `SKILL.md` frontmatter
- selector routing
- doctor diagnostics
- tiered channel docs / tables

The immediate target is not a full policy engine. It is a bounded V1 that removes the highest-value sources of drift.

## Problems This Change Fixes

1. Channel routing membership was manually hardcoded in the selector, so adding a channel required editing code tables.
2. `doctor` inferred capability tiers from env variable names, even when a channel had already declared its own tier and fix path.
3. `init --check-channels` and `generate_channels_table.py` used a different tier model from `doctor`, which produced user-visible contradictions.
4. The new `discourse_forum` channel exposed the gap between search discovery and best-effort full-content enrichment, but that behavior was not well-covered by regression tests.

## V1 Decisions

### 1. Skill frontmatter is the governance source of truth

Channel metadata loaded into runtime now includes:

- `layer`
- `domains`
- `scenarios`
- `model_tier`
- `tier`
- `fix_hint`
- `when_to_use.domain_hints`

These fields remain declared in `SKILL.md`, then compiled into runtime metadata.

### 2. Selector is metadata-driven for membership

The selector no longer owns a hardcoded `group -> channels` table.

Instead it:

- scans channel `SKILL.md` files
- derives domain membership from frontmatter
- scores channels using declared `domains`, `scenarios`, `query_types`, and `domain_hints`
- keeps a small alias / keyword layer only for query understanding, not for membership ownership

This means adding a new channel to an existing domain does not require updating selector membership tables.

### 3. Declared tier overrides inferred tier

If a channel declares:

- `tier`
- `fix_hint`

then:

- `doctor`
- `init --check-channels`
- generated channel tables

must all respect that declaration before falling back to heuristics.

This is required because login-gated channels like `xueqiu` cannot be modeled correctly by generic env-name inference alone.

### 4. Tier semantics are unified

V1 tier meanings:

- `t0`: always-on
- `t1`: env/API gated
- `t2`: login/cookie gated
- `scaffold`: template exists but no shipped implementation

These semantics replace the older mixed interpretation where some surfaces treated tier 2 as “paid”.

### 5. Full-content enrichment is regression-covered

`discourse_forum` now has explicit regression coverage for:

- canonical topic URL construction
- API failure to site-search fallback
- fallback search to Jina reader full-content enrichment
- populated `source_page` metadata

## Non-Goals

- No dynamic routing based on live success-rate telemetry yet.
- No cost-aware policy engine yet.
- No automatic detail-fetch policy for every channel yet.
- No rewrite of the MCP `list_skills` catalog path yet.

## Next Step

V2 should add a lightweight policy layer that can consume:

- declared metadata
- recent channel health
- cost / auth mode
- detail-fetch capability

and make routing decisions with the same vocabulary already introduced here.
