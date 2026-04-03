---
name: citation-graph
description: "Finds papers that cite a given seed paper using Semantic Scholar citation graph data."
categories: [academic]
platform: semanticscholar.org
api_key_required: false
aliases: []
---

## Content types

Citing papers linked to a specific seed paper. This is not topic search; it is downstream citation search over Semantic Scholar graph relationships.

## Language

Best in English because the seed paper matching and citation graph coverage are strongest there. In practice the cited and citing literature is mostly English-language metadata.

## Best for

Questions like "what papers cite X," tracing research lineages, and finding derivative or follow-on work after a known paper. It is useful once you already have a seed paper and want to move forward through the literature.

## Blind spots

It does not work as a general topic search and is weak if the seed paper cannot be resolved cleanly. Coverage is limited to what Semantic Scholar knows, so missing links or incomplete graph data can hide relevant papers.

## Quality signals

The seed paper match is the first quality gate. After that, citation count of the citing papers, recognizable authors, and publication year help prioritize which follow-on papers are worth opening first.
