# AutoSearch P0 Deep Scan Report

日期：2026-04-26  
范围：`autosearch` 仓库只读审查  
方式：6 个 agent 分层扫描，主会话复核关键代码和本地 gate  
结论：当前不建议发布。确认 P0 / P0-class 6 个，另有多项 P1。

## 0. 审查说明

本次任务按用户要求只做审查和报告，不做代码修复。

审查期间观察到工作树已有或出现 `uv.lock` 变更：

```text
## feature/xhs-account-restriction-detection...origin/feature/xhs-account-restriction-detection
 M uv.lock
```

该变更未作为修复处理。它被列入发布阻断项，因为当前强发布检查会因此失败。

## 1. Agent 分工

- Agent 1：安全、隐私、凭据泄露面。
- Agent 2：安装、供应链、包发布风险。
- Agent 3：MCP/API/CLI 边界和工具契约。
- Agent 4：核心搜索、渠道、引用、成本路径。
- Agent 5：持久化、session、runtime 数据和本地状态。
- Agent 6：测试、发布 gate、性能、观测。

## 2. 执行摘要

当前 release 风险主要集中在三类：

- 数据外泄：本地文件可能被转录工具上传；E2B/nightly 打包可能上传本地 ignored 私有数据；citation 可能暴露 signed URL。
- 成本和稳定性：`delegate_subtask` 绕过共享 runtime、限流和去重，可能重复调用外部付费渠道。
- 发布系统：release workflow 没有接入强 pre-release gate，且当前仓库 lock 状态不 clean。

建议先暂停正式发布，按 P0 顺序拆小 PR 修复。

## 3. P0 Findings

### P0-1 本地文件可被转录工具上传到第三方

位置：

- `autosearch/skills/tools/video-to-text-openai/transcribe.py`
- `autosearch/skills/tools/video-to-text-groq/transcribe.py`

问题：

`transcribe(url_or_path)` 接受本地路径。当前流程对非音频/视频文件的拒绝不够硬，路径仍可能进入后续上传逻辑，被打开并作为音频 payload 发给 OpenAI/Groq。

影响：

如果该工具被 agent runtime、skill runtime 或未来 MCP tool 暴露，任意本地文件都有外传风险。对百万级用户产品，这是 P0。

建议：

- 默认禁止本地路径输入，只允许显式白名单目录。
- 同时校验 MIME、扩展名、文件头。
- 对 `.env`、SSH key、token 文件、系统路径做硬拒绝。
- 加审计日志，但不能记录敏感内容。
- 测试覆盖：`.env`、文本文件、系统文件路径必须拒绝。

### P0-2 E2B / nightly 打包会上传本地 ignored 私有数据

位置：

- `scripts/e2b/lib/packing.py`
- `scripts/nightly-local.sh`

问题：

E2B 打包只排除 `.git`、`.venv`、缓存等少量路径，没有遵守 `.gitignore`。`nightly-local.sh` 也直接从当前目录打 tarball。

可能被打入包的敏感路径包括：

- `experience/`
- `evidence/`
- `tests/integration/sessions/`
- `.env`
- 本地产物、临时凭据、调试输出

影响：

私有 session、证据文件、token 或调试数据可能被上传到外部执行环境。

建议：

- 用 `git ls-files` 作为打包源，只打包 tracked files。
- 对 secret/session/evidence/report 类目录做硬拒绝。
- 打包前输出 manifest。
- 打包前跑 secret scan。
- 加测试：创建 ignored secret 文件，断言 tarball 不包含它。

### P0-3 Citation MCP 会返回 raw URL，可能泄露 signed URL/token

位置：

- `autosearch/core/citation_index.py`
- `autosearch/mcp/server.py`

问题：

`citation_add` 和 `export_citations` 保存并返回原始 URL。若输入是 signed URL，参数如 `token`、`signature`、`X-Amz-Signature`、`expires` 可能原样进入 MCP 响应或导出内容。

影响：

signed URL 常等价于临时访问凭证。MCP 输出、日志、下游上下文都可能进一步传播该凭证。

建议：

- Citation 内部可保存 raw URL，但必须带敏感标记。
- MCP 对外默认返回 redacted URL。
- 导出默认去除签名和 token 参数。
- 增加 AWS/GCS/Azure signed URL 回归测试。

### P0-4 `delegate_subtask` 绕过共享 runtime，可能打爆付费渠道

位置：

- `autosearch/core/delegate.py`
- `autosearch/mcp/server.py`

问题：

`delegate_subtask` 直接构建 channels 并 `asyncio.gather` 执行，没有复用 MCP shared runtime，没有共享 rate limiter，没有 channel 去重，也没有并发上限。

重复 channel 会重复调用外部付费 API，但结果按 channel name 覆盖，成本统计会偏低。

影响：

- 成本失控。
- 付费渠道配额被打空。
- 运行时健康数据不可信。
- 高并发下可能造成服务级故障。

建议：

- delegate 必须走统一 `ChannelRuntime`。
- channel list 先去重。
- 增加 per-request 和 global concurrency cap。
- 成本统计按实际调用次数累加。
- 测试覆盖重复 channel、预算耗尽、并发限制。

### P0-5 Release workflow 绕过强发布 gate

位置：

- `.github/workflows/release.yml`
- `scripts/release-gate.sh`
- `scripts/validate/pre_release_check.py`

问题：

release workflow 明确没有接入 `pre_release_check.py`，而是运行 `release-gate.sh --quick --pypi`。`--quick` 会跳过完整 unit + smoke 测试。

影响：

本地强 gate 失败时，GitHub release 仍可能继续。对正式发布链路，这是 P0。

建议：

- release workflow 必须运行 `scripts/validate/pre_release_check.py`。
- release 不允许只跑 `--quick`。
- `--allow-stale-gate12` 只能用于人工 emergency，并要求 issue/PR 记录。
- PyPI/npm 发布必须依赖强 gate 成功。

### P0-6 当前 lock/version 状态不是 release-clean

位置：

- `pyproject.toml`
- `uv.lock`

问题：

当前本地强发布检查失败。`uv.lock` 显示 dirty，版本从 `2026.4.25.9` 变到 `2026.4.25.11`。

已验证：

```text
python scripts/validate/pre_release_check.py
# failed: Gate 12 stale + dirty worktree

python scripts/validate/pre_release_check.py --allow-stale-gate12
# failed: dirty worktree, uv.lock modified
```

影响：

当前状态不能作为可复现 release 输入。即使 quick gate 通过，也不能证明可发布。

建议：

- 明确唯一版本源。
- 发布前强制 clean worktree。
- release gate 不应留下 lockfile 变更。
- CI 中前置 lockfile 一致性检查。

## 4. P1 高优先级问题

### MCP 边界可靠性

位置：

- `autosearch/mcp/server.py`
- `autosearch/cli/query_pipeline.py`

问题：

- 多个 MCP tool 缺 request timeout。
- `run_channel` 的后处理异常没有统一结构化返回。
- CLI channel 异常会被吞掉，最终表现为 “No evidence found”。

建议：

- 所有外部 IO tool 增加 timeout。
- MCP 边界统一捕获并返回结构化错误。
- CLI 区分空结果、认证失败、限流失败、schema 失败。

### SSRF 风险

位置：

- `autosearch/skills/tools/fetch-crawl4ai/fetch.py`
- `autosearch/lib/browser_fetcher.py`
- `autosearch/lib/html_scraper.py`
- `autosearch/skills/tools/fetch-firecrawl/methods/scrape.py`

问题：

URL fetch/render 工具接受任意 URL，缺少内网地址、metadata endpoint、redirect 后地址校验。

建议：

- 阻断 localhost、private IP、link-local、metadata endpoint。
- redirect 后重新解析和校验。
- 增加 allowlist/denylist 配置。

### 供应链风险

位置：

- `npm/bin/autosearch-ai.js`
- `scripts/install.sh`
- `pyproject.toml`

问题：

- npm wrapper 拉取 mutable `main` 分支 installer。
- Python runtime deps 缺 upper bounds。
- PyPI 安装路径不使用 `uv.lock`。

建议：

- npm wrapper 固定 tag/commit。
- installer 校验 digest。
- runtime deps 加上保守 upper bounds。
- 发布包生成 SBOM 或 dependency report。

### 持久化和本地状态

位置：

- `autosearch/persistence/session_store.py`
- `autosearch/core/rate_limiter.py`
- `scripts/trace_harvest.py`

问题：

- SQLite 缺 WAL、busy timeout、integrity check。
- secret 文件写入非 atomic。
- rate limiter 偏进程内，多进程部署可绕过。
- trace harvest 可能写入 raw query。

建议：

- SQLite 开 WAL 和 busy timeout。
- secret 写入使用 temp file + fsync + atomic rename。
- 多进程部署使用共享 limiter 后端。
- trace/query 输出统一走 redaction。

### 搜索正确性和引用规范化

位置：

- `autosearch/channels/base.py`
- `autosearch/core/citation_index.py`

问题：

- primary channel 返回空时 fallback 不一定触发。
- comprehensive 模式覆盖面可能比 deep 少。
- citation canonicalizer 全局移除 `source`、`ref`，可能误合并语义不同的 URL。

建议：

- 区分 empty result 和 successful empty。
- comprehensive/deep 的渠道策略写成明确配置。
- 只移除已知 tracking 参数，不全局移除可能有业务含义的参数。

### 观测和成本

位置：

- `autosearch/mcp/server.py`
- `autosearch/core/channel_health.py`

问题：

- 默认 `LLMClient()` 没有明确接入 `CostTracker`。
- `ChannelHealth.history` 无界增长。
- `TikhubBudgetExhausted` 分类不完整。

建议：

- 默认成本追踪必须接入 runtime。
- health history 设置上限。
- budget/quota error 统一归类。

## 5. 本地验证记录

通过：

```text
python -m autosearch.cli.main mcp-check
# 23 tools registered, all 10 required tools present

pytest tests/unit/test_mcp_server.py \
  tests/unit/test_mcp_error_redaction.py \
  tests/unit/test_mcp_runtime_health_persistence.py \
  tests/unit/test_channel_rate_limit.py -q
# 19 passed

pytest tests/unit/test_package_contents.py \
  tests/unit/test_public_repo_hygiene.py \
  tests/unit/test_runtime_secrets_contract.py \
  tests/unit/test_secrets_path_and_replace.py -q
# 34 passed

ruff check autosearch tests/unit tests/smoke scripts/validate
# passed

npm run public:hygiene
# 639 tracked files clean

python scripts/validate/check_version_consistency.py
# passed
```

失败 / 阻断：

```text
python scripts/validate/pre_release_check.py
# failed

python scripts/validate/pre_release_check.py --allow-stale-gate12
# failed because worktree is dirty: uv.lock
```

补充：

```text
bash scripts/release-gate.sh --quick --pypi
# passed, but this quick gate is not sufficient for release confidence
```

## 6. 建议修复顺序

1. 修 P0-1：封本地文件上传外泄。
2. 修 P0-2：重做 E2B/nightly 打包边界。
3. 修 P0-3：citation raw URL redaction。
4. 修 P0-4：delegate 复用 shared runtime、限流、去重、并发控制。
5. 修 P0-5：release workflow 接入强 gate。
6. 修 P0-6：统一版本和 lockfile，保证 clean release。
7. 批量处理 P1：timeout、结构化错误、SSRF、供应链固定、SQLite 和 limiter。

## 7. Release Blocker Checklist

- [ ] Transcription tools cannot upload arbitrary local files.
- [ ] E2B/nightly packages contain only approved tracked files.
- [ ] Citation MCP never returns signed URLs or tokenized URLs raw.
- [ ] `delegate_subtask` uses shared runtime, shared limiter, dedupe, and concurrency caps.
- [ ] GitHub release workflow runs strong pre-release checks.
- [ ] Release workflow does not rely on `--quick` as the only gate.
- [ ] `pre_release_check.py` passes locally on a clean worktree.
- [ ] `uv.lock` and version files are consistent and committed intentionally.

