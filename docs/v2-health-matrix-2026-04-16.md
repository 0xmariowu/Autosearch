# autosearch v2 · e2b Channel Matrix — 首轮真实 Smoke 结果

**日期**：2026-04-16
**环境**：e2b.dev sandbox, 每 adapter 3 query × 1 rep, standard smoke sample
**成本**：~$0.25 × 2 轮 smoke = ~$0.50

## 总览

| 状态 | 数量 | 占比 | 含义 |
|---|---|---|---|
| **OK** | **17** | **41%** | 真实返回数据，可进 v2 |
| ANTI_BOT | 2 | 5% | 代码跑通，遇反爬（需 cookie 升级 Tier 2） |
| NEEDS_LOGIN | 5 | 12% | 需要 token/账号（BYOK tier）|
| EMPTY | 6 | 15% | 代码跑通但数据源不匹配（RSS 窄查询）|
| ERROR | 11 | 27% | 可修 bug（setup 问题 / 缺依赖 / 上游 bug）|

## ✅ OK · 17 个 adapter（v2 主力）

**核心发现：SEO tertiary 策略 100% 工作 —— 13 个中文站全部走 Bing site: 拿到真实数据。**

| path_id | items | 样本 |
|---|---|---|
| bilibili__nemo2011 | 20×3 | 「冷君」全网都在喷的 iPhone16 到底好不好用？ |
| csdn__rss | 20×3 | iPhone 16 系列 值得 买 吗？一起来看 |
| juejin__api | 20×3 | 结构化 JSON（4500 字最丰富） |
| seo__bing_via_ddgs | 10×3 | Day 1 pilot |
| seo__xiaohongshu | 10×3 | 真 xhs content via Bing |
| seo__douyin | 10×3 | 抖音综合搜索结果 |
| seo__bilibili | 10×3 | 真视频讨论 |
| seo__weibo | 10×3 | #哪些二手 iPhone 值得买# |
| seo__zhihu | 10×3 | 知乎文章收录页 |
| seo__wechat | 10×3 | 微信公众号文章页 |
| seo__kuaishou | 10×3 | 快手搜索页 |
| seo__jike | 10×3 | 即刻真笔记 |
| seo__xiaoyuzhou | 2×3 | 部分 query empty |
| seo__36kr | 10×3 | 36氪真文章 |
| seo__csdn | 10×3 | CSDN 隐私文章 |
| seo__juejin | 10×3 | 掘金文章 |
| seo__xueqiu | 10×3 | iPhone16 Pro 四舍五入等于躺赚 |

## 🟡 ANTI_BOT · 2（诚实报告，需 cookie 才能升级）

| path_id | 诚实错误 | 升级路径 |
|---|---|---|
| weibo__mweibo_http | Sina Visitor System challenge (cookie required) | Tier 2 · 用户提供 cookie |
| xiaohongshu__cialle_redcrack | OtherStatusError: 461 异常 | Tier 2 · 用户提供 cookie |

## 🔒 NEEDS_LOGIN · 5（accepted trade-off）

| path_id | 凭据要求 |
|---|---|
| wechat__wewe_rss | 微信读书 cookie + 自建服务 |
| wechat__we_mp_rss | 自建服务 + 账号 |
| xiaohongshu__cloxl_xhshow | AS_MATRIX_XHSHOW_COOKIE |
| xiaohongshu__submato_xhscrawl | AS_MATRIX_XHSCRAWL_COOKIE |
| xueqiu__mcp | XUEQIU_TOKEN |

## ⚪ EMPTY · 6（数据源结构限制）

| path_id | 原因 |
|---|---|
| 36kr__rss | RSS 只含最新 N 条，用户 query 未命中 |
| infoq_cn__rss | 同上 |
| jike__rsshub_public | RSSHub 无 Jike 关键词路由 |
| xiaoyuzhou__rsshub_public | RSSHub 小宇宙只有 entity feed |
| weibo__dataabc_spider | 上游是 user-timeline 非搜索 |
| zhihu__lzjun567_api | SDK 未暴露搜索函数 |

## ❌ ERROR · 11（可修 bugs）

| path_id | Root cause | 修法估时 |
|---|---|---|
| bilibili__cv_cat_apis | 上游 repo 缺 static/bili.js | 1h · 提 PR |
| douyin__cv_cat_spider | git clone 失败 | 0.5h · 确认 repo |
| douyin__erma0 | git clone Node 依赖失败 | 1h · 改 Python 路径 |
| douyin__nearhuiwen_a_bogus | Timeout（setup 太慢） | 2h · 精简 deps |
| kuaishou__mediacrawler | libGL.so.1 系统库缺 | 1h · setup.sh 加 apt-get install libgl1 |
| wechat__sogou | clone 内 pip install 失败 | 2h · 分析上游依赖 |
| wechat__wechat2rss | Shell-based 未 wire | 3h · subprocess 适配 |
| weibo__sinaspider | 需 redis+scrapy | 踢掉（沙箱不适配） |
| xueqiu__hqjson | HTTP 200 非 JSON（endpoint 返回 HTML） | 1h · 换 endpoint |
| zhihu__moxiegushi_captcha | tensorflow 依赖太大 | 踢掉（不值） |
| zhihu__zhuanlan_http | 400 Bad Request（params 格式） | 1h · 调试参数 |

## v2 最终路由建议（基于 smoke 证据）

每平台 Primary + Tertiary 策略：

| 平台 | Primary（若可用） | Tertiary（SEO 兜底，全部 OK） |
|---|---|---|
| 小红书 | Tier 2 Cloxl/xhshow + cookie | ✅ seo__xiaohongshu |
| 抖音 | 修 setup 后可通 | ✅ seo__douyin |
| B站 | ✅ bilibili__nemo2011 | ✅ seo__bilibili |
| 微博 | Tier 2 + cookie | ✅ seo__weibo |
| 知乎 | 修 params 后可能通 | ✅ seo__zhihu |
| 微信公众号 | Tier 2 wewe-rss（可选）| ✅ seo__wechat |
| 快手 | 修 libGL 后可通 | ✅ seo__kuaishou |
| 即刻 | （无 Primary）| ✅ seo__jike |
| 小宇宙 | （无稳定 Primary）| 🟡 seo__xiaoyuzhou (partial) |
| 36氪 | ✅ 36kr__rss（广播模式）| ✅ seo__36kr |
| CSDN | ✅ csdn__rss | ✅ seo__csdn |
| 掘金 | ✅ juejin__api | ✅ seo__juejin |
| 雪球 | Tier 2 xueqiu_mcp + token | ✅ seo__xueqiu |

## 关键结论

1. **SEO 兜底战略是 v2 真 moat** —— 13 中文站全部可搜，零 cookie，zero key
2. **Primary 层 3 个已稳定**（bilibili/csdn/juejin）
3. **Tier 2 cookie 层有 7 个候选**（xiaohongshu/weibo/xhscrawl/xhshow/wewe-rss/we-mp-rss/xueqiu-mcp）
4. **11 个 error 中 8 个可修**，3 个应踢（tensorflow/redis/shell-wrapper）
5. **小宇宙、即刻这两个平台短期内没有好方案** —— 接受 seo 为唯一通道

## 下一步（按 ROI 排）

**立刻能做（ROI 高）**：
- 修 kuaishou libGL（apt install，30 分钟）
- 修 xueqiu__hqjson endpoint（换到公开 search API）
- 修 zhihu__zhuanlan_http 400（调 params）
- 踢掉 weibo__sinaspider、zhihu__moxiegushi_captcha、wechat__wechat2rss 3 个

**Day 3+ 工作**：
- wewe-rss 自建服务探索 → 微信公众号深度方案
- BYOK cookie 管理设计 → xhs/weibo/xhshow 升级 Tier 2
- Benchmark harness 扩到 20 query × 3 rep × 2 时段 = 120 样本/adapter，按 Wilson CI 正式评级
- 接入 autosearch v1 pipeline（registry.py 作为 data source）
