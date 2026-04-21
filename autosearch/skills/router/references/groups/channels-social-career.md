---
name: channels-social-career
description: Social and professional — Twitter/X (Exa semantic + XReach direct), LinkedIn (profile, company, jobs).
layer: group
domains: [social, career, professional]
scenarios: [social-signal, expert-opinion, hiring-signal, company-pulse]
model_tier: Fast
experience_digest: experience.md
---

# Social & Career Channels

Professional network signals, expert opinions, company hiring behaviour.

## Leaf skills

| Leaf | When to use | Tier | Auth |
|---|---|---|---|
| `search-twitter-exa` | Twitter/X semantic search via Exa (site:twitter.com) | Fast | free |
| `search-twitter-xreach` | Direct X connector via XReach | Fast | XReach key (paid) |
| `search-linkedin` | Profile / company page / job search | Fast | free (public) + mcporter MCP for deeper fields |

## Routing notes

- X native search is weak; always prefer `search-twitter-exa` for the semantic recall. Only use `search-twitter-xreach` when you specifically need live timeline data and a key is configured.
- LinkedIn public pages can be read via `search-linkedin`; deeper fields (profile detail, jobs) go through the `mcporter` skill if the user has the LinkedIn MCP installed.
- For Chinese career signal, combine with `channels-chinese-ugc` (`search-zhihu`).
