# AutoSearch Program

This file is the human-readable operating brief for AutoSearch.

It plays a role similar to `program.md` in `karpathy/autoresearch`, but the
domain is different:

- `autoresearch` mutates training code against a fixed evaluation harness
- `autosearch` evolves search behavior against a fixed routing and admission boundary

## Objective

Find external material that advances active work:

- repositories
- articles
- discussions
- papers
- datasets

The search system should bias toward:

- current project demand
- high-signal sources
- strong provenance
- reusable downstream routing

## Fixed Boundaries

Do not treat these as mutable search policy:

- Armory and AIMD truth sources
- final admission standards
- downstream release rules
- core three-phase search architecture unless explicitly revised

## Mutable Surfaces

These are allowed to evolve:

- source capability catalog
- search methodology docs
- patterns and experiment history
- runtime experience policy
- query-family provider playbooks
- control-plane synthesis

## Keep / Discard Logic

A search-side change is worth keeping when it improves at least one of:

- unique useful URLs discovered
- routing readiness
- provenance quality
- provider reliability
- downstream intake or project usefulness

Changes that add opaque complexity without better search outcomes should be discarded.
