---
name: huggingface_hub
description: Discover open machine learning models on Hugging Face Hub via the public model search API.
version: 1
languages: [en, mixed]
methods:
  - id: api_search
    impl: methods/api_search.py
    requires: []
    rate_limit: {per_min: 30, per_hour: 500}
fallback_chain: [api_search]
when_to_use:
  query_languages: [en, mixed]
  query_types: [ml-model, dataset, ai-demo, hf-hub]
  domain_hints: [machine-learning, llm, multimodal, model-discovery]
quality_hint:
  typical_yield: high
  chinese_native: false
---

## Overview

Hugging Face Hub provides broad coverage of open machine learning models through a free public search endpoint. It is useful when the query is trying to identify specific models, compare popular model families, or find research-adjacent model artifacts by task, library, and ecosystem tags.

## When to Choose It

- Choose it for model lookup queries like LLM families, embedding models, rerankers, vision models, and diffusion checkpoints.
- Choose it when download counts, likes, pipeline type, and Hub tags are useful ranking signals even if the list endpoint does not expose long descriptions.
- Choose it when the search should stay free and no-auth while still targeting the Hugging Face ecosystem directly.

## How To Search

- `api_search` - Calls `https://huggingface.co/api/models` with `search=<query>` and `limit=10`, then maps public model hits into normalized evidence.
- `api_search` - Uses the model `id` as both canonical title and URL suffix, producing links like `https://huggingface.co/<id>`.
- `api_search` - Synthesizes snippet text from `pipeline_tag`, `library_name`, downloads, likes, and the first five tags because the list endpoint does not provide free-text summaries.

## Known Quirks

- Private or gated models are filtered client-side by skipping items where `private=True`.
- The list endpoint returns no prose description, so snippets are synthesized from tags, task type, library, and popularity metadata.
- Download and like counts can exceed 1M for popular models, so both are formatted with thousand separators for readability.
