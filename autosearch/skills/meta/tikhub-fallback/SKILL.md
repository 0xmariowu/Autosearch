---
name: autosearch:tikhub-fallback
description: Decision tree for when to escalate from free native Chinese channels (bilibili / weibo / xiaohongshu / douyin / zhihu) to the paid TikHub fallback. ~$0.0036 per request; 5 platforms covered. Tells the runtime AI when the cost is worth paying vs. when the free paths are enough.
version: 0.1.0
layer: meta
domains: [meta, chinese-ugc, cost-routing]
scenarios: [paid-fallback-decision, chinese-anti-bot, rate-limit-recovery]
trigger_keywords: [tikhub, 付费兜底, 中文反爬, paid fallback, when to use tikhub]
model_tier: Standard
auth_required: true
auth_env: TIKHUB_API_KEY
cost: paid
experience_digest: experience.md
---

# TikHub Fallback Decision Tree — Advisory

**Cost anchor**: TikHub averages **$0.0036 per request** (per `docs/mcp-channels-playbook.md` measurement). A research session with 1000 TikHub calls costs about $3.60/month. Cheap per call, but accumulates fast if every query defaults to paid.

**Boss rule**: Free paths first; TikHub is the paid cushion, not the default.

## Covered Platforms (5)

| Platform | Free native skill | TikHub endpoint | Free path reliability |
|---|---|---|---|
| Xiaohongshu | `search-xiaohongshu` (requires cookie) | `xiaohongshu/web/search_notes` | Low — reliably gated; TikHub is usually required |
| Weibo | `search-weibo` (free API) | `web/fetch_search` | Medium — free works but TikHub upstream is **flaky** |
| Douyin | `search-douyin` (free native) | TikHub + `mcporter`-routed free MCP | Medium — free works, TikHub more complete |
| Zhihu | `search-zhihu` (free native) | TikHub endpoint | Low — Zhihu blocks aggressive scraping |
| Twitter / X | `search-twitter-exa` | `search-twitter-xreach` (XReach) | Medium — Exa covers public, XReach covers deeper signal |

Other hard Chinese platforms **not covered by TikHub** (do not escalate, degrade gracefully):

- WeChat Mini Programs
- Private Xiaohongshu accounts
- Facebook / Instagram private pages
- Any account-gated content

## Decision Tree

Apply per query, not per session:

```
1. Try the free native channel skill first.
   ├─ Returns usable results? → DONE (do not escalate).
   └─ Blocked / empty / flaky? → step 2.

2. If `TIKHUB_API_KEY` is not set in env:
   ├─ Try the mcporter free MCP if applicable (Weibo, Douyin).
   └─ Otherwise report to user: "no free path, no TikHub key — gracefully degraded."

3. If `TIKHUB_API_KEY` is set AND the platform is one of the 5 covered:
   ├─ If query is research-critical (user explicitly asked or Best-tier step) → escalate to TikHub.
   ├─ If query is exploratory / fan-out → skip TikHub, try a different channel instead.
   └─ After 3 failed TikHub requests on the same session / same query shape → stop, do not retry a 4th time (rate-limit or upstream regression signal).

4. Bundle call patterns to reduce cost:
   ├─ Dedupe queries across channels before calling TikHub.
   └─ Prefer single calls that return rich payloads over multiple narrow calls.
```

## Per-Platform Notes

- **Xiaohongshu**: Free scraping needs cookie that expires; TikHub is usually the primary practical path.
- **Weibo**: Free path works for recent hot topics; TikHub upstream has returned `ok=1 but cards empty` occasionally — ~20% flake. Pair with `search-wechat` for long-form verification.
- **Douyin**: Free `mcporter` MCP usable if user has cookie configured; TikHub as paid fallback when MCP 403s.
- **Zhihu**: Free path rate-limits after ~30 queries/session. Escalate to TikHub on rate-limit.
- **Twitter/X**: Prefer `search-twitter-exa` (free, Exa semantic site: query); only reach `search-twitter-xreach` (XReach paid) when a fresh timeline read is mandatory.

## What This Skill Is Not

- Not a wrapper around the TikHub client (that's `autosearch/lib/tikhub_client.py`).
- Not a replacement for the channel skill's own `fallback_chain`. The channel skills carry `fallback_chain: [via_tikhub, api_search, api_video_detail]` in frontmatter — that is the per-channel sequence. This skill is the **meta** policy deciding whether the runtime AI should even reach into the fallback chain for the TikHub hop.

## Boss Rules

- **Do not default to TikHub**. Free paths first, always.
- **Do not flip global policy from a single failure**. If a free channel failed once, retry with a different query shape before escalating. Only a repeated pattern (3+ failures on same query shape) or a known upstream block (Xiaohongshu) justifies escalating immediately.
- **Budget-aware runtime AI** should warn the user when TikHub spend crosses a session threshold (~$1 equivalent = ~280 requests).

## Related Skills

- `autosearch:router` — picks the channel group first.
- `autosearch:model-routing` — picks model tier (orthogonal to cost).
- `mcporter` — the free-MCP fallback path (Weibo / Douyin alternatives without TikHub).
- Individual channel SKILL.md frontmatters already list `via_tikhub` in their `fallback_chain`.

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
