---
description: "Run an AutoSearch research session on any topic"
argument-hint: "research topic (e.g., 'AI agent frameworks', 'vector databases for RAG')"
user-invocable: true
---

# AutoSearch — Self-Evolving Research Agent

## Task
$ARGUMENTS

## Before Starting

Ask the user 3 questions using AskUserQuestion:

### Question 1: Search Depth
"搜索深度？\n1. ⚡ 快速扫描 (2分钟, 5渠道)\n2. ⚖️ 标准研究 (5分钟, 10渠道) [默认]\n3. 🔬 深度研究 (10+分钟, 15+渠道)\n\n输入 1/2/3（默认 2）"

### Question 2: Focus Areas
"最关注哪些方面？(输入编号，可多选如 '1,3,5')\n1. 开源工具/框架\n2. 学术论文/研究\n3. 商业产品/公司\n4. 社区评价/经验\n5. 中文内容\n6. 视频/教程\n7. 全面覆盖 [默认]\n\n输入编号（默认 7）"

### Question 3: Output Format
"报告形式？\n1. 📋 执行摘要 (1页要点)\n2. 📊 对比报告 (表格为主)\n3. 📖 全面报告 [默认]\n4. 📑 资源清单 (链接+描述)\n\n输入 1/2/3/4（默认 3）"

## Execution

1. Read `${CLAUDE_SKILL_DIR}/../PROTOCOL.md` — follow it as your operating protocol
2. Read `${CLAUDE_SKILL_DIR}/../skills/pipeline-flow/SKILL.md` — follow the 7-phase pipeline
3. Map user answers to search configuration:
   - Depth 1→5 channels, Depth 2→10 channels, Depth 3→15+ channels
   - Focus areas→channel selection in select-channels skill
   - Output format→synthesis template in synthesize-knowledge skill
4. Execute the pipeline phases
5. After search completes, show results summary and ask: "继续合成报告？(yes/补搜某方向/取消)"
6. Synthesize and deliver

## Search Execution

Use the search runner script:
```bash
bash ${CLAUDE_SKILL_DIR}/../scripts/run_search.sh 'JSON_QUERIES_ARRAY'
```

## Key Constraints

- judge.py is the only evaluator — run it, never self-assess
- State files are append-only
- Use Haiku for scoring/rubric tasks, Sonnet for synthesis
- Every citation must come from search results (two-stage citation lock)
