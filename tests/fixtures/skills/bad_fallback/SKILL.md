<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
---
name: bad_fallback
description: Contains a fallback reference that does not exist.
version: 1
methods:
  - id: primary
    impl: impl.py
fallback_chain: [primary, secondary]
---

The loader should reject unknown fallback method ids.
