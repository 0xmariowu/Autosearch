# Discourse Forum Channel Design

Date: 2026-04-24

## Goal

Add a reusable forum-search capability for public Discourse communities, with Linux DO as the first built-in source, and validate it with TDD before pitching the change.

## Why

AutoSearch already covers multiple community surfaces such as Reddit, Hacker News, Tieba, and V2EX. It does not yet cover Discourse-based communities, which are common in developer and AI product ecosystems.

Linux DO is a strong first target because it contains high-signal Chinese discussions around AI tools, developer workflows, and product troubleshooting. Implementing this as a reusable Discourse capability is more valuable than a one-off Linux DO scraper.

## Scope

In scope:

- Add a new channel at `autosearch/skills/channels/discourse_forum/`
- Support a built-in `linux_do` site preset
- Query the public Discourse search endpoint and map results into `Evidence`
- Add focused channel tests and run the repo's required fast test suite

Out of scope for v1:

- Login-required or private Discourse forums
- Multi-site runtime configuration
- Ranking by likes/replies/views beyond basic result mapping
- Live validation that depends on network paths unavailable in the current environment

## Design

### Channel shape

Create a single new channel named `discourse_forum`.

The implementation will keep a small site registry in Python, with `linux_do` as the first preset. The search method will choose the preset internally for now, keeping the external channel surface simple and compatible with the current registry model.

### Search flow

1. Receive `SubQuery`
2. Build a request to the public Discourse search endpoint for the `linux.do` preset
3. Parse topic-oriented search results from JSON
4. If the site blocks anonymous API search, fall back to site-limited public search
5. Normalize each item into `Evidence`
6. Return an empty list only if both paths fail

### Evidence mapping

Each result should include:

- Canonical topic URL on `linux.do`
- Non-empty title
- Snippet/body excerpt when available
- `source_channel="discourse_forum:linux_do"`
- Stable fetch timestamp

Items missing enough information to build a canonical URL should be skipped.

## Testing Strategy

TDD order:

1. Add failing tests for successful mapping
2. Add failing tests for malformed payloads and transport failures
3. Implement the minimum logic to make tests pass
4. Run the repo's required fast unit suite

Initial coverage:

- Search returns evidence from a valid Discourse payload
- Missing title falls back sensibly when possible
- Missing URL-building fields are skipped
- HTTP failures degrade to `[]`
- Invalid payload shape degrades to `[]`

## Risks

- Discourse search payloads can vary across versions or site settings
- The current environment may not be able to reach `linux.do` for live verification

These risks are contained because the failure mode is an empty result set and the tests will lock the expected parsing behavior.

## Success Criteria

- New channel compiles from `SKILL.md`
- New channel tests pass
- Required fast unit suite passes
- Final pitch can show: design, tests, implementation, and validation evidence
