# Skill Attribution
> Source: self-written, plan `autosearch-0418-channels-and-skills.md` § F002c.

---
name: xiaohongshu
description: Chinese lifestyle + experience-sharing notes with strong product/beauty/travel/food coverage, via TikHub.
version: 1
languages: [zh, mixed]
methods:
  - id: via_signsrv
    impl: methods/via_signsrv.py
    requires: [env:AUTOSEARCH_SIGNSRV_URL, env:AUTOSEARCH_SERVICE_TOKEN, env:XHS_A1_COOKIE]
    rate_limit: {per_min: 60, per_hour: 1000}
  - id: via_tikhub
    impl: methods/via_tikhub.py
    requires: [env:TIKHUB_API_KEY]
    rate_limit: {per_min: 60, per_hour: 1000}
  - id: via_mcporter
    impl: methods/via_mcporter.py
    requires: [mcp:mcporter, cookie:xiaohongshu]
    rate_limit: {per_min: 5, per_hour: 60}
  - id: via_xhs_cli
    impl: methods/via_xhs_cli.py
    requires: [binary:xhs-cli, cookie:xiaohongshu]
    rate_limit: {per_min: 5, per_hour: 60}
fallback_chain: [via_signsrv, via_tikhub, via_mcporter, via_xhs_cli]
when_to_use:
  query_languages: [zh, mixed]
  query_types: [product-review, experience-report, lifestyle, consumer, travel]
  domain_hints: [consumer, beauty, food, travel, parenting]
quality_hint:
  typical_yield: high
  chinese_native: true
layer: leaf
domains: [chinese-ugc]
scenarios: [chinese-native, product-review, lifestyle]
model_tier: Fast
experience_digest: experience.md
---

## Overview

Xiaohongshu is a Chinese lifestyle and consumer discovery platform centered on short notes about products, beauty, food, travel, and day-to-day experience sharing. It is useful when the query needs Chinese-native recommendation content, purchase impressions, or experiential evidence that sits between review media and social chatter.

## Known Quirks

- TikHub access is billed per request at roughly `$0.0036/request`, so `via_tikhub` should stay first in fallback only where the direct API win justifies spend.
- TikHub search does not require local cookies or login state.
- Evidence currently reflects note-body content only; comments are not included in this route.

## ⚠️ Known Issue: via_signsrv Account Restriction (code=300011)

XHS applies two-tier account restriction enforcement:
1. **With valid signing**: restricted accounts return `code=0, 成功` but `items=[]` — silently empty, no error
2. **Without signing**: returns `code=300011, 当前账号存在异常，请切换账号后重试`

**This means**: if `via_signsrv` returns 0 results, it may be a restricted account, not genuinely empty search results.

**Trigger**: New/unverified accounts, or accounts that triggered bot detection from excessive API calls.

**Mitigation** (not yet implemented): When `via_signsrv` returns empty results, call `/api/sns/web/v2/user/me` to check account health. If `code=300011` is returned, surface `AccountRestrictedError` and prompt user to run `autosearch login xhs` with a different account.

**Workaround**: Use `autosearch login xhs` with a normal, actively-used XHS account. `via_tikhub` is unaffected (uses TikHub's own accounts).

# Quality Bar

- Evidence items have non-empty title and url.
- No crash on empty or malformed API response.
- Source channel field matches the channel name.
