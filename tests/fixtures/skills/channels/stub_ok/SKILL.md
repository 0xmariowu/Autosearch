# Self-written, plan autosearch-0418-channels-and-skills.md § F001
---
name: stub_ok
description: "Stub channel with one always-available echo method."
version: 1
languages: [en]
methods:
  - id: echo
    impl: methods/echo.py
    requires: []
fallback_chain: [echo]
when_to_use:
  query_languages: [en]
  query_types: [technical]
  avoid_for: []
quality_hint:
  typical_yield: low
  chinese_native: false
---
