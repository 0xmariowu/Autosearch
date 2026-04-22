---
name: dockerhub
description: Use for Docker image and container registry searches when query involves Docker images, containers, or deployment artifacts.
version: 1
languages: [en]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 20, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [code, deployment, infrastructure, container]
  avoid_for: [academic, news, social-media]
quality_hint:
  typical_yield: medium
  chinese_native: false
layer: leaf
domains: [code-package, infrastructure]
scenarios: [docker-image, container, devops, deployment]
model_tier: Fast
---

## Overview

Docker Hub public registry search. Free, no auth. Returns image name, description, pull count, and star count. Useful for finding official and community Docker images.

## When to Choose It

- User is looking for Docker images, base images, or container deployment artifacts
- Infrastructure-as-code or DevOps queries about containerized software
- Comparing popular images for a specific service

## How To Search

Uses `hub.docker.com/v2/search/repositories/` REST endpoint.
