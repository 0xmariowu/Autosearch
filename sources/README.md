# Source Capability

This directory is the static capability layer for AutoSearch.

- `catalog.json` is the declared source/provider registry
- `latest-capability.json` is the latest machine-readable doctor output

This layer answers:

- what sources exist
- which are runtime providers
- which are optional research sources
- whether each one is currently usable

This is intentionally different from `experience/latest-health.json`:

- capability = environment / configuration availability
- experience = recent runtime performance
