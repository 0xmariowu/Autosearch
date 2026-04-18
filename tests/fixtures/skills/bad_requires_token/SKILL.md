<!-- Self-written, plan autosearch-0418-channels-and-skills.md § F001 -->
---
name: bad_requires_token
description: Contains an invalid requires token on purpose.
version: 1
methods:
  - id: api
    impl: impl.py
    requires: [cookie:valid_cookie, invalid-token]
fallback_chain: [api]
---

The loader should reject malformed `requires` entries.
