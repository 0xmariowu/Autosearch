# Self-written, plan autosearch-0418-channels-and-skills.md § F001
---
name: stub_cookie
description: "Stub channel whose only method requires a cookie."
version: 1
languages: [en]
methods:
  - id: fake
    impl: methods/fake.py
    requires: [cookie:stub_cookie]
fallback_chain: [fake]
when_to_use:
  query_languages: [en]
  query_types: [experience-report]
  avoid_for: []
quality_hint:
  typical_yield: low
  chinese_native: false
---
