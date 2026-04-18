<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
---
description: Missing the required name field on purpose.
version: 1
methods:
  - id: primary
    impl: impl.py
fallback_chain: [primary]
---

The loader should reject this frontmatter because `name` is required.
