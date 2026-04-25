# AutoSearch Channel Research Final Playbook

> Date: 2026-04-19
> Coverage: mcpmarket.com research + hands-on testing + TikHub paid API integration
> Positioning: This is the **final master guide**. The previously scattered docs (`mcp-channel-research.md` / `mcp-test-plan.md` / `mcp-test-results.md` / `mcp-no-cookie-inventory.md` / `mcp-final-summary.md` / `tikhub-smoke-test.md`) are consolidated here. All future channel decisions should start from this document.

---

## TL;DR

**Three-tier conclusion**:

1. **Free and usable without cookies**: Sogou WeChat, open-websearch (4 engines), Paper Search MCP (21 academic sources), PullPush (Reddit history), direct RSS reads, Jina Reader (some sites), and 13 official APIs.
2. **5 of 8 hard targets were unblocked through paid TikHub**: Xiaohongshu, Weibo, Zhihu, Twitter/X, and Douyin. The remaining 3 (flaky Weibo upstream, Instagram/LinkedIn parameters not fully tuned) were not fully solved in this round.
3. **Final architecture**: AutoSearch uses BYOK (users provide their own TikHub key) and declares dependencies with `requires: [env:TIKHUB_API_KEY]`. The base URL is read from an env var so environments can switch cleanly.

**Cost anchor**: TikHub measured average cost is **$0.0036/request**. 1000 research-grade calls cost about $3.6/month.

---

## Part 1: No-Cookie Usable Inventory (41)

### A. Hands-On PASS in This Round (9)

| Option | Platform/Capability | Auth | Notes |
|---|---|---|---|
| **Sogou WeChat SERP** | WeChat Official Accounts | 🟢 None | `weixin.sogou.com/weixin?type=2&query=<q>` |
| **open-websearch fetch-web + readability** | Any page -> clean markdown | 🟢 None | Cleaned with the Mozilla Readability algorithm |
| **open-websearch csdn** | CSDN technical blogs | 🟢 None | Native Chinese content |
| **open-websearch duckduckgo** | DuckDuckGo | 🟢 None | Backup general search |
| **open-websearch startpage** | Startpage (Google proxy) | 🟢 None | Backup general search |
| **Paper Search MCP** | arXiv + PubMed + Semantic Scholar + OpenAlex + 17 other sources | 🟢 None | One-command access to 21 academic sources, MIT |
| **PullPush** | Reddit history from 2005 to present | 🟢 None | Full-text `q=` search is broken; subreddit/time filtering works |
| **Substack RSS** | Substack / Medium / independent blogs | 🟢 None | All sites expose `/feed` |
| **Jina Reader** | Bilibili / weak anti-scraping sites | 🟢 None | Zhihu, Xiaohongshu, and Weibo are blocked |

### B. Official APIs Known to Work (13, Integrated in AutoSearch or One-Line Integration)

| Platform | Access Method | Limit |
|---|---|---|
| HackerNews Algolia | Official API | Unlimited |
| Reddit public JSON | `/r/<sub>.json` | No login |
| Stack Exchange API | Official | 300/day without key |
| GitHub Public Search | Official API | 10/min without token |
| Dev.to | Public API | No key |
| npm / PyPI registry | Official | No key |
| OpenReview API | Official | No key |
| arXiv API | Official | No key |
| Xueqiu / 36kr / InfoQ Chinese | Their web/API surfaces | No key |
| Xiaoyuzhou | RSS / public pages | No key |
| Bilibili public search API | Official | No login |
| YouTube transcript | yt-dlp + whisper (local) | No key |
| Crunchbase public pages | Public search | Limited |

### C. New Categories Found on mcpmarket (AutoSearch Gaps) (11)

| Option | Capability | Priority |
|---|---|---|
| [Wikipedia MCP](https://mcpmarket.com/server/wikipedia-1) | Full encyclopedia + summaries | 🔴 Highest |
| [Wikidata](https://mcpmarket.com/server/wikidata) | SPARQL + entities | 🔴 Highest |
| [Google Trends Explorer](https://mcpmarket.com/server/google-trends-explorer) | Trend signals | 🔴 Highest |
| [Google News Trends](https://mcpmarket.com/es/server/google-news-trends) | News + trending terms | 🔴 High |
| [USPTO](https://mcpmarket.com/server/uspto) | U.S. patents + trademarks | 🟡 As needed |
| [Google Patents](https://mcpmarket.com/server/google-patents) | Global patents | 🟡 As needed |
| [EPSS](https://mcpmarket.com/server/epss) | CVE + vulnerability scoring | 🟡 As needed |
| [Cybersecurity CVE](https://mcpmarket.com/es/server/cybersecurity-2) | NVD database | 🟡 As needed |
| [OpenStreetMap](https://mcpmarket.com/server/openstreetmap) | Maps + POI | 🟢 As needed |
| [CoinGecko](https://mcpmarket.com/server/coingecko) | Cryptocurrency | 🟢 As needed |
| [Open Meteo](https://mcpmarket.com/tools/skills/open-meteo-weather) | Global weather | 🟢 As needed |

### D. Existing Channel Reinforcements (8)

| Option | Reinforces | Notes |
|---|---|---|
| [Package Version](https://mcpmarket.com/ja/server/package-version) | npm/PyPI/Maven/Go/Swift/Docker Hub and 9 registries total | One MCP covers 9 registries |
| [GitLab MCP](https://mcpmarket.com/server/gitlab) | Complements GitHub | Public repos need no token |
| [Newsfeed](https://mcpmarket.com/server/newsfeed) | `search-rss` preset categories | Free |
| [Trend Radar](https://mcpmarket.com/tools/skills/trend-radar) | HN + GitHub signal aggregation | Free |
| [Steam Context](https://mcpmarket.com/server/steam-context) | Games category | Steam API key is free |
| [Zillow](https://mcpmarket.com/server/zillow) | Real-estate category | Mostly no key |
| [AI Job Hunting Agent](https://mcpmarket.com/es/server/ai-job-hunting-agent) | Indeed + Remotive jobs | Free |
| Sogou WeChat MCP wrappers ([ptbsare](https://github.com/ptbsare/sogou-weixin-mcp-server) / [fancyboi999](https://github.com/fancyboi999/weixin_search_mcp)) | Official Accounts | Same underlying Sogou SERP |

---

## Part 2: Hard-Target Breakthrough Matrix

### 🔴 Integrated (Paid TikHub, 5/8)

| Platform | TikHub endpoint | Measured Data |
|---|---|---|
| Xiaohongshu | `GET /api/v1/xiaohongshu/web/search_notes?keyword=<q>` | Claude 4.7 found 20 notes, including title/author/likes |
| Zhihu | `GET /api/v1/zhihu/web/fetch_article_search_v3?keyword=<q>` | LLM agent found 20 high-quality Q&A results |
| Douyin | `GET /api/v1/douyin/web/fetch_video_search_result_v2?keyword=<q>` | DeepSeek found 12 results, highest with 540K likes |
| Twitter/X | `GET /api/v1/twitter/web/fetch_search_timeline?keyword=<q>&search_type=Top` | 19 results, full fields (favorites/views/retweets) |
| Bilibili | `GET /api/v1/bilibili/web/fetch_general_search?keyword=<q>&order=totalrank&page=1&page_size=10` | 8 videos + play counts |

### ⚠️ Not Fully Solved in This Round (3/8)

| Platform | Status | Debug Direction |
|---|---|---|
| **Weibo** | TikHub upstream is flaky: `web/fetch_search` returns ok=1 but `cards` is intermittently empty; `web_v2/fetch_realtime_search` 400; `app/fetch_search_all` 422 | Ask support in TikHub Discord; try `web_v2/fetch_ai_smart_search` |
| **Instagram** | `v2/general_search` returns 200 OK but all zeroes | Try `v2/search_hashtags` or targeted keywords (#hashtag / @username) |
| **LinkedIn** | `web/search_jobs` returns 400, even with geocode | Check TikHub docs for demo parameters; may require a special geocode format |

### 🟢 Truly Impossible Without Cookies

**Facebook / Instagram public personal pages / Xiaohongshu private-account content / Twitter private accounts**: even TikHub requires account support. These are not core to the research scenario, so do not invest for now.

---

## Part 3: TikHub Field Notes

### Basic Information

- **Homepage**: https://tikhub.io · **API base**: `https://api.tikhub.io/api/v1/`
- **Auth**: `Authorization: Bearer $TIKHUB_API_KEY`
- **OpenAPI spec**: `GET https://api.tikhub.io/openapi.json` (1058 endpoints)
- **Billing**: pay-per-request, average **$0.0036/request** (official marketing says starts at $0.001; measured cost is 3-4x higher)
- **Free quota**: Daily check-in gives a small amount of free credit

### Platform Coverage (Confirmed Working)

16 platforms, 1000+ tools:
```
TikTok (204) · Douyin (247) · Instagram (82) · Xiaohongshu (71)
Weibo (64)  · Bilibili (41) · YouTube (37)   · Kuaishou (33)
Zhihu (32)  · LinkedIn (25) · Reddit (24)    · WeChat · Twitter
Threads · TikHub Utilities · Other
```

### Key Pitfalls (In the Order Encountered)

1. **Registration requires email verification**. Without verification, every endpoint returns 403 "email not verified".
2. **The free tier covers only some endpoints**. Xiaohongshu/Weibo/Twitter/Douyin all return 402 (Payment Required) until paid balance is > 0. Zhihu and Bilibili are covered by the free tier.
3. **Do not use `web_v3` for Xiaohongshu**. `/xiaohongshu/web_v3/fetch_search_notes` returns 400. Use the older `/xiaohongshu/web/search_notes`.
4. **Do not use `app/v3` for Douyin**. `/douyin/app/v3/fetch_video_search_result` returns 400. Use `/douyin/web/fetch_video_search_result_v2`; data is under `data.business_data[i].data` (two nested layers).
5. **Weibo endpoints are unstable across versions**. `web_v2/fetch_realtime_search` returns 400; `app/fetch_search_all` returns 422; `web/fetch_search` returns 200 but `cards` fluctuates.
6. **400 = upstream scraping failure, not necessarily bad parameters**. TikHub's 400 body says "please check docs and parameters", but in practice TikHub itself failed to scrape the target site. This kind of 400 **is not billed** (Only pay for successful requests).
7. **Twitter structure is already flattened**. `data.timeline` is a list, not the original GraphQL-style nested `instructions` structure. Iterate it directly. Fields: `screen_name / text / favorites / views / retweets / replies / created_at / tweet_id / lang`.

### 🚨 Security Note: The Key Is Echoed in Error Responses

**TikHub 400 / 403 / 422 response bodies echo the full request headers, including auth information**. Integration must:

```python
# BAD — printing the response body directly leaks the key
except httpx.HTTPStatusError as e:
    log.error("TikHub failed", body=e.response.text)  # ❌

# GOOD — sanitize before logging
def sanitize(data: dict) -> dict:
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        detail.pop("headers", None)
        for k in list(detail.keys()):
            if "auth" in k.lower() or "token" in k.lower():
                detail[k] = "<redacted>"
    return data

except httpx.HTTPStatusError as e:
    log.error("TikHub failed", body=sanitize(e.response.json()))  # ✅
```

Tests must include: **assert exception string does not contain "Bearer"**.

### MCP vs API Choice

TikHub officially provides 4 transports: Stdio / SSE / Streamable HTTP / Curl(API).

**For AutoSearch**: **choose direct Curl/API calls**, not MCP.

Reasons:
- AutoSearch is a Python plugin installed with `pip install`. Using MCP would require users to additionally install Node.js + `mcp-remote` + the TikHub MCP server (3 dependencies)
- AutoSearch channels are already "tools"; calling MCP from inside a tool is tool-calling-a-tool, and JSON-RPC over stdio adds a useless serialization layer
- Enabling the full TikHub MCP exposes 1000+ tool schemas and injects roughly 400K tokens into Claude context, which is untenable
- Even selecting only the 6 hard-target platforms still exposes ~470 tools (~190K tokens), which is still not ideal

**Good fit for Stdio MCP**: ad hoc calls where a user in a Claude Code session wants to directly search Xiaohongshu, and this is for the user to install TikHub MCP themselves; it is unrelated to AutoSearch.

---

## Part 4: Final AutoSearch Integration Architecture

### BYOK (Bring Your Own Key) Is the Only Reasonable Plan

**Do not**:
- ❌ Hardcode a TikHub key into the release build (a pip package exposes plaintext)
- ❌ Share one key across all users (violates ToS and drains the balance)

**Do**:
- ✅ Users register and top up at `tikhub.io` themselves
- ✅ `export TIKHUB_API_KEY=<your-key>`, and AutoSearch reads the env var
- ✅ SKILL.md declares `requires: [env:TIKHUB_API_KEY]`; without a key, the channel is automatically marked unavailable while other channels continue running

### Channel Structure (Validated by Pilot)

```
autosearch/lib/
└── tikhub_client.py              # Generic client + error redaction + 5xx retries

autosearch/skills/channels/zhihu/
├── SKILL.md                      # frontmatter declares via_tikhub method
└── methods/
    └── via_tikhub.py             # maps /zhihu/web/fetch_article_search_v3 to Evidence

tests/lib/test_tikhub_client.py   # client unit tests, including redaction assertion
tests/channels/zhihu/test_via_tikhub.py  # method unit tests
```

**fallback_chain order**: `[via_tikhub, api_search, api_answer_detail]` — prefer TikHub when a key is present; fall back to the original path when no key exists.

### Leave Room for a Future Proxy

`tikhub_client.py` reads the base URL from an env var:

```python
base_url = os.getenv("TIKHUB_BASE_URL", "https://api.tikhub.io")
```

If the upstream needs to be changed later, such as to a self-hosted proxy or mirror, users only need to change two env vars with zero code changes:

```bash
export TIKHUB_BASE_URL=https://your-proxy.example.com/tikhub
export TIKHUB_API_KEY=<your-proxy-token>
```

### 5 Channels Pending Integration (Priority Order)

| Priority | Channel | Endpoint | Status |
|---|---|---|---|
| 1 | **zhihu** | `zhihu/web/fetch_article_search_v3` | ✅ pilot complete (branch `feat/tikhub-channels`) |
| 2 | **xiaohongshu** | `xiaohongshu/web/search_notes` | Pending expansion |
| 3 | **twitter** | `twitter/web/fetch_search_timeline` | Pending expansion |
| 4 | **douyin** | `douyin/web/fetch_video_search_result_v2` | Pending expansion |
| 5 | **bilibili** | `bilibili/web/fetch_general_search` | Pending expansion |

After the pilot is validated, have Codex write the remaining 4 adapters in parallel from the same template. Each should be < 50 lines.

---

## Appendix

### A. Test Command Quick Reference (Copy-Paste Ready)

```bash
# Sogou WeChat + readability cleanup = full-text Official Account search
cd /tmp/mcp-smoke/ows
node build/index.js fetch-web \
  "https://weixin.sogou.com/weixin?type=2&query=<KEYWORD>" \
  --readability --spawn --json

# open-websearch multi-engine
node build/index.js search "<query>" --engine duckduckgo --limit 5 --spawn --json
node build/index.js search "<query>" --engine csdn --limit 5 --spawn --json

# Paper Search MCP academic search
cd /tmp/mcp-smoke/paper-search-mcp
python3 -c "
import sys; sys.path.insert(0,'.')
from paper_search_mcp.academic_platforms.arxiv import ArxivSearcher
s = ArxivSearcher()
for p in s.search('<query>', max_results=5):
    print(p.title, p.url)
"

# PullPush Reddit history
curl -s "https://api.pullpush.io/reddit/search/submission/?subreddit=<NAME>&after=<TS>&before=<TS>&size=10"

# Jina Reader for any URL
curl -sL "https://r.jina.ai/<URL>"

# Any TikHub endpoint, with redacted result inspection
curl -sS -H "Authorization: Bearer $TIKHUB_API_KEY" \
  "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3?keyword=<q>" \
  -o /tmp/t.json
python3 -c "
import json
d = json.load(open('/tmp/t.json'))
detail = d.get('detail', {})
if isinstance(detail, dict): detail.pop('headers', None)
print(json.dumps(d, indent=2, ensure_ascii=False)[:1000])
"
rm -f /tmp/t.json  # Key point: remove temp file that may contain echoed key data
```

### B. External Links

- mcpmarket.com — research source for this round
- tikhub.io — paid platform API
- github.com/Aas-ee/open-webSearch — 8-engine free SERP
- github.com/openags/paper-search-mcp — 21 academic sources
- github.com/jacklenzotti/pullpush-mcp — Reddit history
- r.jina.ai — free URL -> markdown via Jina Reader

### C. Related Docs (Before This Round)

Consolidated into this playbook, so **you no longer need to read them day to day**:
- `mcp-channel-research.md` — initial research
- `mcp-channel-test-plan.md` — test plan
- `mcp-test-results.md` — first round of hands-on tests
- `mcp-no-cookie-inventory.md` — no-cookie inventory
- `mcp-final-summary.md` — phase summary
- `tikhub-smoke-test.md` — detailed TikHub smoke test

Keep them archived for traceability, but in daily use, **this playbook + `tikhub-smoke-test.md`** is enough.

### D. Cost Ledger (As of 2026-04-19)

- TikHub: **$0.053** (19 smoke requests)
- Other: $0 (all free options)

---

**Maintenance rule**: When a new channel is integrated or a new hard target is unblocked, update the corresponding table in this playbook to keep it as the single source of truth.

---

## Appendix E. 2026-04-19 Supplemental Scan (New No-Key + No-Cookie Options)

This deeper mcpmarket.com pass found **12 fully no-key and no-cookie categories** missed earlier. Ranked by research value:

### 🔴 High Value (Strongly Recommended)

| MCP | Capability | Auth | Tested | Why It Matters |
|---|---|---|---|---|
| [FRED](https://mcpmarket.com/server/fred) · [Fredapi](https://mcpmarket.com/server/fredapi) · [FRED Macro Data](https://mcpmarket.com/server/fred-macroeconomic-data) | U.S. Federal Reserve economic data, 800K+ time series | 🟢 No key | Not tested | Essential macro signal for AI/startup research |
| [World Bank Data](https://mcpmarket.com/server/world-bank-data) | Global economic indicators | 🟢 No key | Not tested | Core need for country-comparison research |
| [Public APIs Directory](https://mcpmarket.com/es/server/public-apis) ([repo](https://github.com/zazencodes/public-apis-mcp)) | Free API directory semantic search | 🟢 No key | **✅ 04-19** | **Metatool** — future engine for AutoSearch to discover new channels |
| [Open Library / Books](https://mcpmarket.com/server/books) · [OpenLibrary](https://mcpmarket.com/server/openlibrary) | ISBN lookup, full book catalog | 🟢 No auth | Not tested | Foundation for academic/publishing research |
| [Word of the Day](https://mcpmarket.com/server/word-of-the-day) | Free Dictionary API with definitions, pronunciation, and examples | 🟢 No key | Not tested | Basic fact-checking utility |
| [Dash Docset](https://mcpmarket.com/server/dash) · [Enhanced Dash](https://mcpmarket.com/server/enhanced-dash) | Local Dash docset query | 🟢 Local | Not tested | Instant technical-doc lookup |
| [Hugging Face MCP](https://mcpmarket.com/tools/skills/hugging-face-mcp) | Hub model/dataset search | 🟢 Public search without key | **✅ 04-19** | Foundation for AI research |
| Wikipedia API (official) | Encyclopedia search + summaries | 🟢 No key | **✅ 04-19** | Foundation for fact checking and encyclopedia enrichment |
| Wikidata SPARQL (official) | Structured entities + graph queries | 🟢 No key | **✅ 04-19** | Entity relationship queries |
| Google Trends via `pytrends` | Keyword trend time series | 🟢 No key | **✅ 04-19** | Topic heat and brand-comparison signals |

### 🟡 Integrate As Needed

| MCP | Capability | Auth | Scenario |
|---|---|---|---|
| [Flightradar24](https://mcpmarket.com/server/flightradar24-1) · [Flight (ADS-B)](https://mcpmarket.com/server/flight) | Real-time flight tracking | 🟢 Partly no key | Travel / supply-chain research |
| [Etherscan MCP](https://mcpmarket.com/server/etherscan-2) · [Dune Analytics](https://mcpmarket.com/tools/skills/dune-analytics-on-chain-data) | Ethereum on-chain data | 🟢 Etherscan free key / 🟡 Dune paid | Web3 research |
| [Ethereum JSON-RPC](https://mcpmarket.com/server/eth-1) | Native JSON-RPC chain query | 🟢 Public nodes | Deep DeFi research |
| [TMDB](https://mcpmarket.com/server/tmdb) · [IMDb](https://mcpmarket.com/es/server/imdb-1) · [OMDB](https://mcpmarket.com/es/server/omdb) | Movie/TV data | 🟢 TMDB/OMDB free key | Content/entertainment research |
| [Last.fm (ScrobblerContext)](https://mcpmarket.com/es/server/scrobblercontext) | Music data | 🟢 Free key | Content analysis |
| [OpenFoodFacts](https://mcpmarket.com/server/openfoodfacts) | Global food database | 🟢 No key | Consumer goods / health research |

### 🟢 Basic Utilities (Occasional Use)

| MCP | Capability | Auth |
|---|---|---|
| [Whois Lookup](https://mcpmarket.com/server/whois) · [Domain Lookup](https://mcpmarket.com/server/domain-lookup) | WHOIS / RDAP lookup | 🟢 No key |
| [DeepL MCP](https://mcpmarket.com/server/deepl) | Translation | 🟡 Free tier requires key |
| [Pexels MCP](https://mcpmarket.com/es/server/pexels) | Free stock images | 🟡 Free key |

### mcpmarket Has No Coverage for These Categories

- **Toutiao / Baijiahao / NetEase Hao** (Chinese news aggregators)
- **Reuters / TechCrunch / Bloomberg** (professional news, RSS only)
- **Coursera / edX / Khan Academy / MOOC**
- **Chinese government open data** (National Bureau of Statistics, customs)
- **ESPN / sports data**
- **Air quality / environmental data / real-time carbon emissions**

These can only be covered through RSS + Exa `site:`, or by waiting for future mcpmarket additions.

### 2026-04-19 Hands-On Verification (5 Core MCPs)

Smoke tests were run against the underlying APIs for the 5 most important MCPs for "basic facts / trends / AI Hub / metatools." All passed:

| MCP | Underlying API | Smoke Test | Sample |
|---|---|---|---|
| **Wikipedia** | `en.wikipedia.org/w/api.php?action=query&list=search&srsearch=<q>` | Search `Claude AI` -> 5 results | Claude (language model) · Anthropic · OpenAI Codex · Artificial intelligence · Project Maven |
| **Wikidata** | `query.wikidata.org/sparql` (SPARQL) | `P31 wd:Q11660` query for AI entities -> 5 results | AlphaFold · Lee Luda · Intelligent Autonomous Systems |
| **Google Trends** | `pytrends` Python library (unofficial, simulated requests) | 7 days hourly `Claude AI` vs `ChatGPT` -> **169 rows** | Latest hour Claude AI=3, ChatGPT=45, making the brand-awareness gap obvious |
| **Hugging Face Hub** | `huggingface.co/api/models?search=<q>` | Search `llama` -> 5 results | meta-llama/Llama-3.1-8B-Instruct, 9.36M downloads · Llama-3.3-70B-Instruct, 490K downloads |
| **Public APIs Directory** | Local `datastore/index.json` (1426 full APIs) | Full load + filter auth=No -> **668 no-key APIs** | 1426 APIs across dozens of categories including Animals/Crypto/Finance/Transport/Security |

**Key clarification**: Public APIs Directory MCP ([zazencodes/public-apis-mcp](https://github.com/zazencodes/public-apis-mcp)) **does not depend on the now-dead `api.publicapis.org` at all**. Its data is built-in JSON (1426 entries), and the embedding index is built locally (.npz file). So even though the old API domain now fails DNS resolution, the MCP works correctly.

**Pitfall warning — Google Trends**: pytrends is an unofficial simulated-request library. Google occasionally changes cookie/token mechanics and breaks it. Integration must include **retries + error tolerance** and must not treat it as a hard dependency. It is much more fragile than the other 4 official APIs.

**Integration recommendation (lightest path)**: The first 4 can all be called directly through Python `httpx` against HTTP APIs; there is no need to start an MCP process. Public APIs Directory can have its `index.json` copied into AutoSearch and parsed locally. A 1426-row JSON file is small, and embeddings can be computed locally. This keeps AutoSearch free of new external process dependencies.

---

### Updated AutoSearch Priority After the Scan

On top of the 6 "strongly recommended" basics in Part 1 section C, **add 3 highest-priority items**:

1. **FRED + World Bank** (macroeconomic signals, no key and no cookie in one step)
2. **Public APIs Directory** (metatool; lets AutoSearch automatically discover new channels)
3. **Open Library** (foundation for academic/publishing research)

In total, AutoSearch should now add **9 channels** to become the "only full-coverage research system in the market":

```
Wikipedia + Wikidata          # encyclopedia       ✅ verified
Google Trends                 # trends             ✅ verified (flaky risk)
Hugging Face Hub              # AI models          ✅ verified
Public APIs Directory         # metatool           ✅ verified
Google Patents                # patents            not verified
CVE/NVD                       # security           not verified
FRED + World Bank             # macroeconomics     not verified
Open Library                  # books              not verified
```

All are 🟢 zero-key and zero-cookie. The implementation cost is small and the payoff is high.

**First integration batch (4 already verified)**: Wikipedia, Wikidata, Hugging Face, Public APIs Directory — Codex can write channel adapters immediately, each < 30 lines of Python + httpx code.

**Second integration batch (5 not yet smoke-tested)**: Google Trends, Google Patents, CVE/NVD, FRED, Open Library — proceed by research-scenario priority, and run a smoke test against the underlying API before each integration.
