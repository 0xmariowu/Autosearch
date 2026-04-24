# AutoSearch Handoff

> **更新**：2026-04-24 session N（million-user readiness Batches 1/2/3 全部合并，已发 v2026.04.24.2）
>
> **当前 main HEAD**：`600e155`（npm-publish idempotency follow-up）
> **最新 release**：`v2026.04.24.2` — PyPI + GitHub Release ✅ / npm `autosearch-ai@2026.4.24`（intra-day 未重发，正常）

---

## 关键入口（新 session 先做）

1. **先读**：`docs/million-user-product-readiness-plan.md` — 这份 plan 是当前真相来源，本 session 的所有工作都在对它
2. **再读**：这个文件下方的"当前状态对照 plan"表
3. **验证 main 干净**：
   ```
   ./scripts/release-gate.sh           # 应该全 PASS，847 tests
   .venv/bin/autosearch doctor --json  # 应该 40 channels
   .venv/bin/autosearch mcp-check      # 应该 10 required v2 tools
   ```

---

## 当前状态对照 plan

| Plan 项 | 状态 | 证据 / 相关 PR |
|---|---|---|
| **P0-1** secrets 注入 runtime | ✅ DONE | `core.secrets_store.inject_into_env()` + MCP/CLI 启动时调用；#324 |
| **P0-2** doctor 报 missing impl | ✅ DONE | `doctor.scan_channels` 加 `impl_missing` unmet；10 个 ghost method 删除；#324 |
| **P0-3** run_channel not_configured | ✅ DONE | `RunChannelResponse.status/unmet_requires/fix_hint`；#324 |
| **P0-4** MCP 响应 redact | ✅ DONE | `core.redact` shared；run_channel/run_clarify/experience 都过 redact；#325 |
| **P0-5** ChannelHealth 持久 | ✅ DONE | `core.channel_runtime.ChannelRuntime` singleton；#326 |
| **P0-6** rate_limit 强制 | ✅ DONE | `core.rate_limiter.RateLimiter` per-(channel,method) 滑窗；#326 |
| **P1-3** configure 隐藏输入 | ✅ DONE | 默认 hidden prompt + `--stdin` + `--replace` + chmod 0600；#325 |
| **P1-5** health() 结构化 | ✅ DONE | 返回 dict 含 version/tool counts/channels/secrets key names/health snapshot；#326 |
| **P2-3** experience 原 query | ✅ 部分 DONE | append_event 对 string 字段过 redact；#325。硬规则（hash/opt-in raw）未做 |
| **P1-1** docs v1 叙事 | 🛑 **老板 hold**："叙事不改" | README / install.md / mcp-clients.md 仍 v1 |
| **P1-2** matrix-extensions/w1w4-bench 旧契约 | ❌ TODO | `tests/e2b/matrix-extensions.yaml` + `matrix-w1w4-bench.yaml` 没扫 |
| **P1-4** research tool 默认列出 | ❌ TODO | 计划：`AUTOSEARCH_LEGACY_RESEARCH=1` 才注册 |
| **P1-6** delegate_subtask 绕过 run_channel | ❌ TODO | 需抽 `run_channel_core()` 共享语义 |
| **P1-7** install.sh mutable main | ❌ TODO | 需加 `--dry-run`/`--no-init`/`--version` |
| **P1-8** npm postinstall | ❌ TODO | 需删 postinstall，让 `npx autosearch-ai` 显式 launcher |
| **P1-10** Windows CI 用旧 path | ❌ TODO | `cross-platform.yml` 要设 `AUTOSEARCH_EXPERIENCE_DIR` |
| **P2-1** wheel 含 legacy modules | ❌ TODO | `autosearch/core/pipeline.py` + `server/` + `synthesis/` 仍在 wheel |
| **P2-2** experience seed 路径 | ❌ TODO | 两种 seed 路径共存（`<skill>/experience.md` vs `<skill>/experience/experience.md`）|
| **Gates A-G** 6 个 release-gate test | ⚠️ 部分 | A/B/C/D 对应 test 已存在但没接进 `scripts/release-gate.sh`；需做 Gate E/F/G + 汇总 wire |

---

## 架构一屏图（v2 正在 actually honest 的版本）

```
用户的 AutoSearch
  ├─ CLI entry (cli/main.py app.callback)
  │    └─ inject_into_env()  ← secrets 文件 → os.environ
  │
  ├─ MCP server (mcp/server.py create_server)
  │    └─ inject_into_env()  ← 同上，MCP 启动时
  │    └─ ChannelRuntime singleton (core.channel_runtime)
  │         ├─ registry (ChannelRegistry with attached health + limiter)
  │         ├─ health: ChannelHealth（进程级，cooldown 状态持久）
  │         ├─ limiter: RateLimiter（滑窗 per channel+method）
  │         └─ channels: list[Channel] (available() 过滤后)
  │
  ├─ MCP tools
  │    ├─ doctor() — scan_channels 用 impl_missing 严检
  │    ├─ mcp-check — required v2 tool 名单
  │    ├─ run_channel — 用 runtime；status={ok|not_configured|unknown_channel|channel_error|rate_limited}
  │    ├─ run_clarify — reason 过 redact
  │    ├─ health() — 结构化 snapshot（不再是 "ok"）
  │    └─ research() — 仍默认注册（Plan §P1-4 说应该隐藏）
  │
  ├─ 40 渠道（discourse_forum 新加）
  │    └─ rate_limit metadata → 现在真被 enforce
  │
  └─ Safety
       ├─ core.redact — MCP 响应 / experience event 都过
       └─ core.secrets_store — configure 写的文件 → runtime 真读到
```

---

## 本 session 合并的 PR（按顺序）

- **#324** Batch 1 — runtime truth（P0-1/2/3）
- **#325** Batch 2 — safety boundaries（P0-4/P1-3/P2-3）
- **#326** Batch 3 — runtime reliability（P0-5/6/P1-5）
- **#327** bump version 2026.04.24.2
- **#328** release.yml npm idempotency follow-up

---

## 硬约束（下 session 必记）

1. **commit gate**：`scripts/committer "<msg>" <file>...`；直接 `git commit` 被 husky 拒绝
2. **push gate**：Don't push directly to `main` — 永远走 PR。Hook 会拦
3. **Release flow**：`scripts/bump-version.sh` → PR → merge → `git tag vYYYY.MM.DD.N && git push --tags` → release.yml 自动 PyPI + npm + GitHub release
4. **版本映射**：pyproject `YYYY.MM.DD.N` → npm `YYYY.M.DD`（daily counter 不进 npm）。`scripts/validate/check_version_consistency.py:derive_npm_version` 是单一来源
5. **Auto-merge**：PR CI 过且 `enable` job OK → 自动 squash merge。`auto-merge.yml` 需 `contents: write` permission（已设）
6. **Cross-repo push denied by hook**：不能 force-push 到外部 fork；push to main 也被拦。只有 trusted origin branch push 允许
7. **`tests/conftest.py` autouse fixture**：每个 test 前后 `reset_channel_runtime()`。任何测试改 `_build_channels` 或直接 `install_test_runtime(...)` 都要注意 singleton
8. **CLAUDE.md § "叙事不改"**：README / install.md / mcp-clients.md 的 v1 措辞（"deep research alternative" / "39 channels"）**禁止动**（老板 explicit hold）。但 40 channels 事实更新 OK
9. **Plan 真相源**：`docs/million-user-product-readiness-plan.md` 是 audit 文件。**不要 overclaim** "plan 全做完了" —— 对照它核验

---

## 下一步候选（按影响 × 代价）

按 plan 里剩余项的 user-impact 排序：

1. **P1-2 扫其余 e2b matrix**（S，30 min）— 把 `test_e2b_matrix_contract.py` parametrize 到 `matrix-extensions.yaml` + `matrix-w1w4-bench.yaml`；按出错数清理旧契约
2. **P1-4 research tool 默认不注册**（S-M）— env flag `AUTOSEARCH_LEGACY_RESEARCH=1` 才注册；mcp-check profile 显式验；减少 LLM 误选
3. **Gates A-G 接进 release-gate.sh**（S-M）— 新 test file `test_runtime_secrets_contract.py` / `test_doctor_impl_availability.py` / `test_mcp_run_channel_not_configured.py` / `test_mcp_error_redaction.py` / `test_channel_rate_limit.py` / `test_mcp_runtime_health_persistence.py` 都已存在但 release-gate.sh 没显式跑它们；是 release 前安全网
4. **P1-8 npm postinstall**（M）— `npm install -g autosearch-ai` 会自动跑 install.sh；安全角度 P0，但破坏性改动，可能要出 npm major bump
5. **P1-6 delegate_subtask 共享 run_channel_core**（M-L）— 抽出 `run_channel_core(channel_name, query, k) -> dict` 给 run_channel + delegate_subtask 共用；影响面广但是架构清理
6. **P1-7 install.sh flags**（S）— 加 `--dry-run` / `--no-init` / `--version` 
7. **P2-1 wheel legacy modules**（S）— 决定 `pipeline.py` / `server/` / `synthesis/` 要不要进 wheel；可能需要 `[project.optional-dependencies].legacy`

---

## 关键文件

| 文件 | 用途 |
|---|---|
| `docs/million-user-product-readiness-plan.md` | **真相文档** — 每批工作对照它核 |
| `CHANGELOG.md` | 用户视角变更 |
| `scripts/release-gate.sh` | 发版前一键验；接进 release.yml |
| `scripts/validate/check_version_consistency.py` | 5 文件版本一致性；含 `derive_npm_version` |
| `scripts/committer` | 所有 commit 必须走它 |
| `scripts/bump-version.sh` | pyproject + plugin + marketplace + npm + CHANGELOG 一键 bump |
| `autosearch/core/secrets_store.py` | `inject_into_env` / `load_secrets` / `resolve_env_value` / `available_env_keys` |
| `autosearch/core/channel_runtime.py` | singleton 管理 registry + health + limiter |
| `autosearch/core/rate_limiter.py` | 滑窗限流 |
| `autosearch/core/redact.py` | 共享 redact 入口 |
| `autosearch/cli/mcp_config_writers.py` | Claude/Cursor/Zed 各自 schema writer |
| `autosearch/cli/diagnostics.py` | `autosearch diagnostics --redact` |

---

## 用户侧环境变量

```bash
# Secrets file (autosearch configure 写这个；runtime 也读这个)
AUTOSEARCH_SECRETS_FILE=~/.config/ai-secrets.env  # override 可选

# Experience runtime dir (~/.autosearch/experience 默认；$XDG_DATA_HOME 也支持)
AUTOSEARCH_EXPERIENCE_DIR=~/.autosearch/experience

# Dummy mode for tests (跳过真实 channel/LLM)
AUTOSEARCH_LLM_MODE=dummy

# Signing Worker（可选）
AUTOSEARCH_SIGNSRV_URL=https://autosearch-signsrv.autosearch-dev.workers.dev
AUTOSEARCH_SERVICE_TOKEN=as_xxx

# Per-channel secrets (configure 会写到 SECRETS_FILE；runtime inject 进 env)
OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY / YOUTUBE_API_KEY
TIKHUB_API_KEY / SEARXNG_URL / XHS_A1_COOKIE / ...
```
