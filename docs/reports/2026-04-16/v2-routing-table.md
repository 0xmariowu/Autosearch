# v2 SourceRouter 选型表（基于 2026-04-16 full e2b smoke）

> 源数据：`tests/e2b-channel-matrix/reports/2026-04-16/health-matrix.md`
> 78 adapter × 3 query × 1 rep = 234 runs

## 总体判断

1. **Bing SEO tertiary 是 v2 的实际护城河**：13 个中文平台里，每平台都配了 `seo__<platform>`（Bing site: 查询），全部 OK。这是唯一"零摩擦零登录"可规模化的方案。竞品（Perplexity/ChatGPT）不做这种分 site 路由。
2. **免 cookie 真平台方案极度稀缺**：13 个平台里只有 3 个（B站/CSDN/掘金）有可用开源方案免登录真返数据。
3. **BYOK cookie 是最大杠杆**：16 个 needs_login adapter（尤其小红书 x4、微信公众号 x3、即刻 x2），BYOK 一次性解锁后可达率从 3 涨到 19。

## 每平台路由推荐

### 🟢 A 级（有免 cookie 真方案）

| 平台 | Primary | Secondary | Tertiary | 备注 |
|------|---------|-----------|----------|------|
| B 站 | `bilibili__nemo2011` ✅ | — | `seo__bilibili` | 20 items 真返，3.8k Python SDK 最稳 |
| CSDN | `csdn__rss` ✅ | `csdn__ds19991999_spider`（需 cookie） | `seo__csdn` | RSS 20 items |
| 掘金 | `juejin__api` ✅ | `juejin__official_rss`（empty） | `seo__juejin` | 官方 API 4648 字最丰富 |

### 🟡 B 级（只能靠 Bing tertiary + BYOK 才能扩）

| 平台 | Tertiary (零 cookie) | BYOK 候选（needs_login） |
|------|-----|-----|
| 小红书 | `seo__xiaohongshu` | cloxl_xhshow / cv_cat_spider_xhs / reajason_xhs / submato_xhscrawl |
| 微信公众号 | `seo__wechat` | wewe_rss / we_mp_rss / wnma3mz_wechat_articles |
| 抖音 | `seo__douyin` | shilonglee_crawler |
| 知乎 | `seo__zhihu` | syaning_zhihu_api（JS SDK 需 Node） |
| 雪球 | `seo__xueqiu` | 1dot75cm / mcp |
| 快手 | `seo__kuaishou` | ogslp / shilonglee |
| 即刻 | `seo__jike` | cypggs / midnightdarling_skill（扫码登录） |

### 🔴 C 级（Bing 是唯一出路，无 BYOK 候选或候选全挂）

| 平台 | Tertiary | 说明 |
|------|-----|-----|
| 微博 | `seo__weibo` | Primary 3 个全 empty（user-id oriented，不支持 keyword） |
| 36 氪 | `seo__36kr` | Primary RSS empty，Java 项目 JVM required，hot_hub empty |
| InfoQ 中文 | `seo__<none>` | 只有自写 RSS（empty） |
| 小宇宙 | `seo__xiaoyuzhou` | 所有 non-SEO 都 error/empty（download_only scope） |

## BYOK 设计建议（下一步工作）

按优先级排：

1. **小红书 4 个候选 cookie**（回报最高，内容最多）：
   - `AS_MATRIX_XHSHOW_COOKIE` → cloxl_xhshow
   - `AS_MATRIX_CV_CAT_XHS_COOKIE` → cv_cat_spider_xhs
   - `AS_MATRIX_REAJASON_XHS_COOKIE` → reajason_xhs
   - `AS_MATRIX_XHSCRAWL_COOKIE` → submato_xhscrawl

2. **微信公众号 wewe-rss**（9.2k star，微信读书 cookie 一次永久）
3. **雪球 MCP**：`XUEQIU_TOKEN`
4. **雪球 1dot75cm**：`XUEQIU_COOKIE` / `XUEQIU_COOKIE_FILE`
5. **抖音 shilonglee** + **快手 shilonglee**（同一仓，同一 cookie 覆盖两平台）

## Disqualified 建议踢的 adapter（error 31 个里）

JVM required（4）—— 踢：
- `36kr__jiangqqlmj_crawler`
- `36kr__ldh2068vip_crawler`
- `bilibili__czp3009_bilibili_api`
- `xueqiu__decaywood_superspider`

Repo 已死 / README-only / py2（~10）—— 踢：
- `xiaohongshu__xhs996_xhs_spider`
- `douyin__nearhuiwen_tiktok_crawler`
- `bilibili__cv_cat_apis`（apis/bili_apis.py FileNotFoundError）
- `kuaishou__yuncaiji_api`
- `kuaishou__sh_moranliunian_cobweb`
- `zhihu__liuroy_zhihu_spider`（urlencode import py2 遗留）
- `juejin__iderekli_helper`
- `juejin__sanfengliao_vue_juejin`
- `juejin__lm_rebooter_booklet`
- `xueqiu__rockyzsu_xueqiu`
- `csdn__schrodingersbug_search`
- `csdn__kaixindelele_pageviews`

依赖太重 / 不兼容 sandbox（4）—— 踢：
- `zhihu__littlepai_unofficial`（tensorflow）
- `xiaoyuzhou__fueny_ptt_cpu`（transcription too expensive）
- `xiaoyuzhou__ychenjk_transcription`（同上）
- `xiaohongshu__xpzouying_mcp`（Go runtime，对照组已确认"不适合 e2b"）

小问题能修（~4）：
- `xiaoyuzhou__anfushuang_download`：只缺 `pip install bs4`
- `xiaoyuzhou__donlon_xyz_fetcher`：只缺 `pip install api`
- `kuaishou__mediacrawler`：**libGL 修复失败**，e2b 不允许 apt-get，需要换 template 或用 `LD_LIBRARY_PATH` trick
- `xiaohongshu__cialle_redcrack`：461 anti_bot（signing 对但没 cookie），可尝试加 cookie 降级到 needs_login

## 接入 autosearch v1 pipeline 建议

v1 `SourceRouter` 需要按 query 分类挑 adapter：

```python
# pseudo
if platform_has_A_grade(platform):
    use_primary()  # B站/CSDN/掘金
elif user_has_cookie(platform):
    use_byok_secondary()  # 小红书/微信/雪球 etc.
else:
    use_tertiary_bing_seo()  # 全平台兜底
```

Tertiary（Bing SEO）永远跑，Primary/Secondary 按可用性叠加。
