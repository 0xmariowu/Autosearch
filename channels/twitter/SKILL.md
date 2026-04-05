---
name: twitter
description: "Finds public Twitter/X posts, threads, and announcement-style updates indexed from the platform."
categories: [social, tech-discussion]
platform: x.com
api_key_required: false  # Enhanced with cookie auth: set TWITTER_AUTH_TOKEN + TWITTER_CT0, or have X logged in via browser
aliases: [x]
---

## Content types

Short social posts, lightweight threads, announcements, launches, reactions, and link sharing from public Twitter/X pages. The content is fast, fragmented, and often valuable mainly because it appeared early.

## Language

Best in English and Chinese. Search works reasonably for both, but short-post ambiguity makes precise matching harder than in long-form sources.

## Best for

Breaking announcements, paper releases, product launches, researcher hot takes, and real-time reaction scanning. This is the right channel when the signal you want is "who posted about this first and how are people reacting now."

## Blind spots

It is weak for long-form explanation, historical retrieval, and stable reference material. Threads are easy to miss, replies are hard to reconstruct, and important context is often outside the indexed tweet text.

## Quality signals

Engagement count helps, especially when paired with a relevant account. Verified or clearly authoritative accounts, linked primary sources, and multi-post threads are usually better signals than isolated low-engagement posts.

When cookie authentication is available (via env vars or browser), results include likes, reposts, replies, and author handles. Without auth, results come from DuckDuckGo site-search with no engagement data.
