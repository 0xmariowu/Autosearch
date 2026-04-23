# AutoSearch Handoff

> **更新**：2026-04-23 session 5（百万用户化 G1-G7 全部完成）
>
> **当前 main HEAD**：`2e6cb72`（v2026.04.23.2 发布）
> **PR open**：#277 outline.py tech debt（auto-merge pending）

---

## 当前发布状态

| 项目 | 状态 |
|---|---|
| CalVer tag | `v2026.04.23.2` ✅ GitHub Release 已发布 |
| main CI | ✅ passing |
| 渠道数量 | **39 个**（+xueqiu, +linkedin）|
| E2B Phase 1 | **96.3/100 🟢 READY** |
| E2B Phase 2 | **84.3/100 🟢 READY** |
| Cloudflare Worker | ✅ 线上 / TOKENS_KV 6 个 token（1 测试 + 5 备用）|

---

## 架构一屏图

```
用户的 AutoSearch
  ├─ MCP 工具（22个）
  │    ├─ list_skills / list_modes / list_channels / doctor
  │    ├─ run_clarify(query)     → 模式检测 + channel 推荐
  │    ├─ run_channel(ch, q, k) → search → URL去重+SimHash+BM25
  │    ├─ delegate_subtask       → 并行多渠道
  │    ├─ consolidate_research  → 压缩 evidence 防 context 溢出
  │    ├─ loop_init/update/gaps → 深度研究循环
  │    └─ citation_create/add/export
  │
  ├─ 渠道（37个）
  │    ├─ 免费（21）：arxiv/pubmed/ddgs/hackernews/github/bilibili(直接WBI)...
  │    └─ TikHub付费（16）：douyin/xiaohongshu/weibo/twitter/instagram/wechat_channels...
  │
  ├─ Signing Worker（CF）
  │    ├─ POST /sign/bilibili  → WBI签名（KV缓存salt，cron刷新）
  │    └─ POST /sign/xhs       → TikHub sign + 本地 X-s-common
  │
  ├─ 动态搜索模式（5个内置）
  │    academic/news/chinese_ugc/developer/product + 自动检测
  │
  └─ 视频转录
       video-to-text-bcut（Bilibili Bcut API，免费，字级时间戳）
       video-to-text-groq/openai/local（yt-dlp + Whisper）
```

---

## 质量证明

| 测试 | 结果 |
|---|---|
| pytest 全套 | 725 passed（live/perf 除外）|
| E2B Phase 1 | 96.3/100 🟢 READY |
| E2B Phase 2 | 84.3/100 🟢 READY |
| Bilibili 实测 | 20 条（直接 WBI 或 Worker）|
| XHS 实测 | 22 条（TikHub 两步签名）|
| Douyin 实测 | 16 条（TikHub POST）|
| Twitter 实测 | 20 条（扁平 timeline）|
| Instagram 实测 | 20 条 |
| WeChat Channels | 12 条 |

---

## 硬约束（下 session 必记）

1. **commit gate**：`scripts/committer "<msg>" <file...>`，直接 `git commit` 被 husky 拒绝
2. **Codex 派活**：prompt 必须含"使用 scripts/committer"
3. **版本三件套**：CalVer，`scripts/bump-version.sh`，tag 必须 `v2026.MM.DD.N`
4. **auto-merge 已开启**：PR CI 通过后自动合并
5. **bilibili api_search.py**：Worker 优先，本地 WBI 兜底（`AUTOSEARCH_SIGNSRV_URL` + `AUTOSEARCH_SERVICE_TOKEN`）
6. **XHS a1 cookie**：via_signsrv 需用户提供真实 `XHS_A1_COOKIE`，否则自动跳过走 TikHub
7. **E2B parallel=20**：P 类 desktop 场景自己创建沙盒，不占 headless 配额（`_DESKTOP_CATEGORIES = {"P"}`）
8. **Worker KV 命名**：`USAGE_KV`（计数 + WBI salt），`TOKENS_KV`（token 注册），别搞混

---

## ⚠️ 已知问题（不能忽略）

### via_signsrv 账号异常检测（code=300011）

**现象**：XHS 对异常账号执行两层拦截：
1. 无签名/假签名 → `code=300011, msg=当前账号存在异常，请切换账号后重试`
2. 有正确签名 → `code=0, 成功` 但 `items=[]`（静默空结果，不报错）

**根因**：账号被 XHS 标记为异常。测试账号 `小红薯60F83C0D` 因大量 API 调用触发了风控。

**影响范围**：
- via_signsrv search → ❌（账号异常时静默返回空）
- via_tikhub search → ✅（TikHub 用自己的账号，不受影响）
- homefeed/profile → ✅（部分接口对异常账号仍放行）

**处理**：
1. 用正常使用中的 XHS 账号运行 `autosearch login xhs` 重新提取 cookie
2. 正常账号 + 正确签名 → via_signsrv search 应该工作
3. **必须加检测**：via_signsrv 搜索结果为空时，应主动调 `/api/sns/web/v2/user/me` 验证账号状态，如返回 code=300011 则提示用户重新登录

**待做**（P1）：`via_signsrv.py` 加账号健康检查，返回空时自动诊断是账号异常还是真的没有结果

---

## 本次 session 完成（G1-G7 百万用户化）

| # | 内容 | PR | 状态 |
|---|---|---|---|
| G1 | `install.md` + init MCP snippet | #290 | ✅ merged |
| G2 | doctor 分层 + fix_hint | #290 | ✅ merged |
| G3 | login 7 平台 + --from-string | #291 | ✅ merged |
| G5-python | TikhubBudgetExhausted graceful fallback | #291 | ✅ merged |
| G7 | Evidence.to_context_dict() 60% token | #292 | ✅ merged |
| G4 | xueqiu + linkedin 渠道 | #293 | ✅ merged |
| G6 | FailureCategory circuit breaker | #293 | ✅ merged |
| G5-worker | per-user IP 配额（50/day）| autosearch-signsrv | ✅ deployed |

---

## 待办（按真实状态）

| 优先级 | 内容 | 阻塞原因 |
|---|---|---|
| **P1** | **via_signsrv 账号健康检查** | **见下方 ⚠️，code=300011 检测已实现** |
| P1 | XHS via_signsrv 真实验证（正常账号）| 用正常账号重跑 `autosearch login xhs` |
| P1 | E2B 自定义模板 Python 3.12 | ✅ 已完成（PR #279）|
| P1 | Worker Custom Domain | 需告知域名 |
| P3 | State/Context 分离（LangGraph）| 需设计讨论 |
| P3 | 颗粒化 SSE 事件流 | 需定义事件 spec |
| P3 | 图片多模态 | 需确认注入方向 |
| ~~P2~~ | ~~Douyin via Worker~~ | ❌ 关闭：window.bdms，TikHub 是永久方案 |
| ~~P2~~ | ~~WeChat Channels 视频转录~~ | ❌ 关闭：需 WeChat session，无可行路径 |

---

## 关键文件

- 经验笔记：`experience/2026-04-23-mega-e2b-channels-signsrv-session.md`
- 主计划：`docs/exec-plans/active/autosearch-master-plan-2026-04.md`
- Worker repo：`~/Projects/autosearch-signsrv/`
- Worker 部署：`https://autosearch-signsrv.autosearch-dev.workers.dev`
- Worker token（测试用）：`as_14cec8a1d495e3ff34470abb0f37c2ea`（日限 1000）

---

## 环境变量（用户侧）

```bash
# Signing Worker（可选，有则优先走 Worker）
AUTOSEARCH_SIGNSRV_URL=https://autosearch-signsrv.autosearch-dev.workers.dev
AUTOSEARCH_SERVICE_TOKEN=as_xxx

# XHS 原生 API（可选，有则走 Worker+直接 API）
XHS_A1_COOKIE=...

# TikHub 兜底（付费，最可靠）
TIKHUB_API_KEY=...
```
