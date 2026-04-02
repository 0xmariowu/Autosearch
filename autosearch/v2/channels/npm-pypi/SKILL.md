---
name: npm-pypi
description: "Use this channel for package discovery across npm and PyPI when libraries, package metadata, versions, and repository links matter more than general web pages."
categories: [developer]
platform: npms.io
api_key_required: false
aliases: []
---

## When to use

Use when the query is about libraries, SDKs, frameworks, or package names and you want direct registry evidence from the JavaScript and Python ecosystems.

## Quality signals

- Package names that closely match the query
- Descriptions, versions, and publish dates that look current
- Homepage or repository links that point to an active upstream project

## Known limits

- Results merge npm and PyPI and are not cross-ecosystem deduplicated
- PyPI metadata is parsed from HTML and can break if markup changes
- Registry ranking may prioritize name overlap over package quality
