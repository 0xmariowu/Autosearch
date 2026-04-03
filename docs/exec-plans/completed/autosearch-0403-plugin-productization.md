# AutoSearch Plugin 产品化

## Goal

把 AutoSearch 从 prototype 变成可发布到 Claude Code marketplace 的 Plugin。用户 `claude plugin install autosearch` 即可使用。

## 背景

- 当前 repo 混杂 V1（12,760 行 Python）和 V2（skills + channels）代码
- V2 是实际产品，V1 是历史代码（194 个 tests 还在跑）
- Plugin 需要符合 Claude Code plugin 标准（.claude-plugin/plugin.json + commands/ + agents/ + skills/ + hooks/）
- 目标用户：Claude Code 用户，通过 marketplace 安装

## Features

### F001: Repo 清理 — 分离 V1 和 plugin — todo

当前 repo 根目录有大量 V1 文件（engine.py, goal_*.py, pipeline.py 等 15,000+ 行）。这些不属于 plugin，需要移走。

#### Steps
- [ ] S1: 创建 `legacy/` 目录，把 V1 代码全部移入（engine.py, goal_*.py, pipeline.py, avo.py, cli.py, daily.py, interface.py, orchestrator*.py, outcomes.py, run-template.py, selector.py, source_capability.py, embeddings.py, evaluation_harness.py, api_contract.py, control_plane.py, doctor.py, query_dedup.py, project_experience.py, evidence_records.py）← verify: 根目录没有 V1 .py 文件
- [ ] S2: 移动 V1 相关目录到 legacy/（acquisition/, autoloop/, capabilities/, control/, evidence_index/, genome/, goal_cases/, rerank/, research/, search_mesh/, sources/, watch/）← verify: 根目录只剩 autosearch/, docs/, tests/, legacy/, scripts/, .github/
- [ ] S3: 移动 V1 数据文件（evolution.jsonl, outcomes.jsonl, patterns.jsonl, playbook-final.jsonl, standard.json, platforms.md, program.md, data-links.md）到 legacy/ ← verify: 根目录干净
- [ ] S4: 更新 V1 tests import paths 指向 legacy/，验证 `pytest tests/ -x -q` 仍然通过 ← verify: 所有 tests 通过
- [ ] S5: 更新 .gitignore 排除 __pycache__/, .DS_Store, .venv/, .ruff_cache/, .pytest_cache/ ← verify: `git status` 不显示这些文件

### F002: Plugin 结构搭建 — todo

按照 Claude Code plugin 标准创建 plugin 结构。

#### Steps
- [ ] S1: 创建 `.claude-plugin/plugin.json`:
```json
{
  "name": "autosearch",
  "version": "1.0.0",
  "description": "Self-evolving research agent. Searches 32+ channels, synthesizes research reports better than native Claude.",
  "author": {"name": "0xmariowu"},
  "license": "MIT",
  "homepage": "https://github.com/0xmariowu/autosearch",
  "repository": "https://github.com/0xmariowu/autosearch",
  "keywords": ["search", "research", "RAG", "self-evolving", "agent"]
}
```
← verify: 文件存在，JSON 合法

- [ ] S2: 创建 `commands/autosearch.md` — 主搜索命令（用户输入 `/autosearch "topic"`），内容从现有 skill autosearch 命令迁移，加入用户交互流程 ← verify: 文件存在
- [ ] S3: 创建 `commands/setup.md` — `/autosearch:setup` 命令，创建 venv 并安装依赖 ← verify: 文件存在
- [ ] S4: 创建 `agents/researcher.md` — 搜索 agent 定义，描述 AutoSearch 的能力和工具 ← verify: 文件存在
- [ ] S5: 把 `autosearch/v2/skills/` 移到 `skills/` 下，每个 skill 变成 `skills/{name}/SKILL.md` 格式（Claude Code plugin 要求目录格式）← verify: `ls skills/*/SKILL.md | wc -l` >= 30
- [ ] S6: 把 `autosearch/v2/channels/` 移到 plugin 根目录 `channels/` ← verify: `ls channels/*/search.py | wc -l` >= 30
- [ ] S7: 把 `autosearch/v2/search_runner.py` 和 `autosearch/v2/judge.py` 移到 `lib/` ← verify: `ls lib/search_runner.py lib/judge.py`
- [ ] S8: 把 `autosearch/v2/state/` 移到 `state/` ← verify: state 目录在根目录
- [ ] S9: 把 `autosearch/v2/PROTOCOL.md` 移到根目录 ← verify: 文件存在
- [ ] S10: 更新所有 import paths（search_runner.py, channels/*.py 里的 `from autosearch.v2.xxx` → 相对 import 或 plugin 内 path）← verify: `PYTHONPATH=. python lib/search_runner.py --help` 无 import 错误

### F003: 依赖管理（setup 命令 + venv）— todo

实现 `/autosearch:setup` 和运行时依赖检测。

#### Steps
- [ ] S1: 创建 `requirements.txt`:
```
ddgs>=9.12.0
httpx>=0.27.0
```
← verify: 文件存在

- [ ] S2: 创建 `scripts/setup.sh`:
```bash
#!/bin/bash
VENV_DIR="$HOME/.autosearch/venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q -r "$(dirname "$0")/../requirements.txt"
echo "AutoSearch setup complete. Venv at $VENV_DIR"
```
← verify: `bash scripts/setup.sh` 成功创建 venv

- [ ] S3: 创建 `scripts/run_search.sh` — wrapper 脚本，用 venv Python 执行 search_runner.py:
```bash
#!/bin/bash
VENV_PYTHON="$HOME/.autosearch/venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "AutoSearch not set up. Run /autosearch:setup first." >&2
    exit 1
fi
"$VENV_PYTHON" "$(dirname "$0")/../lib/search_runner.py" "$@"
```
← verify: setup 后 `bash scripts/run_search.sh '[{"channel":"hn","query":"test"}]'` 返回结果

- [ ] S4: 创建 `hooks/hooks.json` — SessionStart hook 检查 venv 是否存在，不存在时提示 setup:
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "[ -d \"$HOME/.autosearch/venv\" ] || echo '[AutoSearch] Run /autosearch:setup to install dependencies'",
        "timeout": 5
      }]
    }]
  }
}
```
← verify: hook 文件合法

- [ ] S5: 在 `commands/setup.md` 中写完整的 setup 流程：检测 Python 版本、创建 venv、安装依赖、验证 channels 加载、输出成功消息 ← verify: `/autosearch:setup` 跑通

### F004: 用户交互流程 — todo

实现搜索前 3 问 + 搜索后 1 确认。

#### Steps
- [ ] S1: 在 `commands/autosearch.md` 中实现搜索前交互流程。使用 AskUserQuestion 工具：

**Question 1 — 搜索深度**:
```
搜索深度？
1. ⚡ 快速扫描 (2分钟, 5渠道)
2. ⚖️ 标准研究 (5分钟, 10渠道) [默认]
3. 🔬 深度研究 (10+分钟, 15+渠道)
```

**Question 2 — 关注维度**:
```
最关注哪些方面？(输入编号，可多选，如 "1,3,5")
1. 开源工具/框架
2. 学术论文/研究
3. 商业产品/公司
4. 社区评价/经验
5. 中文内容
6. 视频/教程
7. 全面覆盖 [默认]
```

**Question 3 — 输出格式**:
```
报告形式？
1. 📋 执行摘要 (1页要点)
2. 📊 对比报告 (表格为主)
3. 📖 全面报告 [默认]
4. 📑 资源清单 (链接+描述)
```

← verify: 3 个 AskUserQuestion 调用在 command 里定义

- [ ] S2: 搜索深度→配置映射：

| 深度 | 渠道数 | max_results/渠道 | 总 query 数上限 |
|---|---|---|---|
| 快速 | 5 | 5 | 8 |
| 标准 | 10 | 10 | 15 |
| 深度 | 15+ | 15 | 25 |

写入 `skills/pipeline/SKILL.md` ← verify: 配置映射写入 skill

- [ ] S3: 关注维度→渠道映射：整合到 select-channels skill 的 Rule 2 ← verify: 用户选择能正确映射到渠道
- [ ] S4: 输出格式→合成模板：在 synthesize-knowledge skill 中加 4 种输出模板 ← verify: 每种格式有对应模板
- [ ] S5: 搜索后确认交互 — 展示结果分布，问用户继续/补搜/取消 ← verify: AskUserQuestion 在搜索后调用

### F005: Native Claude 对比实验框架 — todo

搭建自动化对比框架，不跑全部 20 topics，先跑 5 个验证方法论。

#### Steps
- [ ] S1: 创建 `tests/benchmark/` 目录和 `benchmark_runner.py`:
  - 输入：topic 列表 + rubrics
  - 对每个 topic 跑两次：AutoSearch pipeline / native Claude（纯 LLM 回答）
  - 用同一套 rubrics 给两个报告打分
  - 输出对比表
  ← verify: 文件存在

- [ ] S2: 定义 5 个 pilot topics（从之前讨论的 20 个里选，每类 1 个）:
  - 学术：self-evolving AI agents（有基线数据）
  - 工具：vector databases for RAG（有基线数据）
  - 商业：AI coding assistant market 2026
  - 中文：中国大模型生态
  - 实操：building production RAG systems
  ← verify: topics.json 存在

- [ ] S3: 跑 5 个 pilot topics，收集数据 ← verify: 每个 topic 有 AutoSearch 和 native Claude 两份报告 + 两份 rubric 评分

- [ ] S4: 分析对比结果，生成 `tests/benchmark/results.md`:
  - 每个 topic 的 pass rate 对比
  - AutoSearch 赢在哪些维度
  - Native Claude 赢在哪些维度
  - 总结 AutoSearch 的增量价值
  ← verify: 分析报告存在

### F006: 发布准备 — todo

README、LICENSE、marketplace 发布。

#### Steps
- [ ] S1: 重写 README.md — 面向用户，不是面向开发者。内容：
  - 一句话说明：什么是 AutoSearch
  - 安装：`claude plugin install autosearch`
  - 使用：`/autosearch "your research topic"`
  - 特性：32 渠道、中英文、自进化、引用锁定
  - 对比 native Claude 的数据（来自 F005）
  - Architecture 简图
  ← verify: README.md 重写完成

- [ ] S2: 确认 LICENSE（MIT）← verify: LICENSE 文件存在
- [ ] S3: 创建 .npmrc 或 marketplace 配置（取决于 Claude Code marketplace 的发布流程）← verify: 配置文件存在
- [ ] S4: 清理 .github/workflows — 保留 CI、Gitleaks、Semgrep，删除不需要的 ← verify: CI 在 plugin 结构下仍能跑
- [ ] S5: 最终全量测试 — 从干净环境安装 plugin，跑一次完整搜索 ← verify: 端到端成功

## 依赖关系

```
F001 (repo 清理) ──→ F002 (plugin 结构) ──→ F003 (依赖管理)
                                          ├── F004 (用户交互)
                                          └── F005 (对比实验，可并行)
                                                     ↓
                                               F006 (发布准备)
```

F001 必须先做（清理后才能搭 plugin 结构）。F002 做完后 F003/F004/F005 可以并行。F006 等所有完成后。

## 最终 Plugin 目录结构

```
autosearch/
├── .claude-plugin/
│   └── plugin.json               # 插件清单
├── commands/
│   ├── autosearch.md             # /autosearch — 主搜索命令
│   └── setup.md                  # /autosearch:setup — 安装依赖
├── agents/
│   └── researcher.md             # 搜索 agent 定义
├── skills/
│   ├── pipeline-flow/SKILL.md    # 7-phase pipeline
│   ├── synthesize-knowledge/SKILL.md
│   ├── gene-query/SKILL.md
│   ├── select-channels/SKILL.md
│   ├── llm-evaluate/SKILL.md
│   ├── check-rubrics/SKILL.md
│   ├── auto-evolve/SKILL.md
│   └── ... (30+ skills)
├── channels/
│   ├── STANDARD.md               # 渠道规范
│   ├── __init__.py               # 渠道 loader
│   ├── _engines/                 # 共享搜索引擎
│   │   ├── baidu.py
│   │   └── ddgs.py
│   ├── github-repos/
│   │   ├── SKILL.md
│   │   └── search.py
│   ├── zhihu/
│   │   ├── SKILL.md
│   │   └── search.py
│   └── ... (32 渠道目录)
├── lib/
│   ├── search_runner.py          # 搜索引擎（149 行）
│   └── judge.py                  # 评估函数
├── state/                         # 运行时状态（append-only）
│   ├── patterns-v2.jsonl
│   ├── rubric-history.jsonl
│   ├── channel-scores.jsonl
│   └── evolution-log.jsonl
├── hooks/
│   └── hooks.json                # SessionStart 依赖检查
├── scripts/
│   ├── setup.sh                  # venv 创建 + 依赖安装
│   └── run_search.sh             # 用 venv Python 执行搜索
├── tests/
│   ├── test_channel_loader.py
│   └── benchmark/                # native Claude 对比框架
├── legacy/                        # V1 代码（不打包进 plugin）
├── docs/
├── PROTOCOL.md
├── CLAUDE.md
├── README.md
├── LICENSE
├── requirements.txt
└── .gitignore
```

## Decision Log
- 2026-04-03: Plugin 名称 — AutoSearch
- 2026-04-03: 发布目标 — Claude Code 官方 marketplace
- 2026-04-03: 依赖策略 — `~/.autosearch/venv/` 专用 venv，`/autosearch:setup` 安装
- 2026-04-03: V1 代码 — 移到 `legacy/` 保留但不打包进 plugin
- 2026-04-03: 用户交互 — 搜索前 3 问（深度/维度/格式）+ 搜索后 1 确认
- 2026-04-03: 对比实验 — 5 pilot topics 先验证方法论，再扩展到 20

## Open Questions
- Claude Code marketplace 的发布流程是什么？需要审核吗？有 size 限制吗？
- Plugin 的 state/ 文件放哪里？用户项目目录还是 ~/.autosearch/？跨项目共享 patterns 还是每项目独立？
- V1 tests（194 个）要保留还是归档？它们测的是 V1 代码，plugin 用不到。
- `legacy/` 目录要放进 .gitignore 还是保留在 repo 里作为历史参考？
