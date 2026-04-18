<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
---
name: valid_tool
description: Use for reusable HTTP fetch helpers shared across channels.
version: 1
methods:
  - id: fetch_json
    impl: impl.py
    requires: [binary:curl]
fallback_chain: [fetch_json]
quality_hint:
  typical_yield: unknown
  chinese_native: false
---

This tool skill exposes a single primitive and does not need routing hints.
