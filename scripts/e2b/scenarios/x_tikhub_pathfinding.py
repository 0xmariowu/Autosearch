"""Scenarios X1-X8: TikHub channel pathfinding — find working query formats for each Chinese UGC channel."""

from __future__ import annotations

import json
import time
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult, run_python


_PATHFIND_TEMPLATE = """
import os, json, asyncio
from datetime import UTC, datetime
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

CHANNEL = {channel!r}
QUERIES = {queries!r}
TIKHUB_KEY = os.environ.get('TIKHUB_API_KEY', '')

async def main():
    channels = {{c.name: c for c in _build_channels()}}
    os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
    ch = channels.get(CHANNEL)
    if not ch:
        print(json.dumps({{
            'ok': False,
            'error': 'channel not found: ' + CHANNEL,
            'available': [
                c for c in channels
                if 'bili' in c or 'tik' in c or 'xhs' in c or 'weibo' in c or 'dou' in c
            ],
        }}))
        return

    winning_query = None
    results_by_query = {{}}

    for q in QUERIES:
        try:
            evs = await ch.search(SubQuery(text=q, rationale='pathfinding test'))
            count = len(evs)
            results_by_query[q] = count
            if count >= 2 and winning_query is None:
                winning_query = q
        except Exception as e:
            results_by_query[q] = 'error: ' + str(e)[:80]

    patterns_written = False
    patterns_path = ''
    patterns_error = ''
    if winning_query is not None:
        try:
            import autosearch.skills.experience as exp_mod
            from autosearch.skills.experience import append_event

            skill_dir = exp_mod._find_skill_dir(CHANNEL)
            if skill_dir is not None:
                patterns_path = str(skill_dir / 'experience' / 'patterns.jsonl')
                before = (skill_dir / 'experience' / 'patterns.jsonl').stat().st_size if (skill_dir / 'experience' / 'patterns.jsonl').exists() else 0
            else:
                before = 0

            append_event(CHANNEL, {{
                'skill': CHANNEL,
                'query': winning_query,
                'outcome': 'success',
                'count_returned': results_by_query.get(winning_query, 0),
                'count_total': results_by_query.get(winning_query, 0),
                'winning_pattern': winning_query,
                'tested_queries': QUERIES,
                'scenario': 'tikhub_pathfinding',
                'ts': datetime.now(UTC).isoformat(),
            }})

            if skill_dir is not None:
                pf = skill_dir / 'experience' / 'patterns.jsonl'
                patterns_written = pf.exists() and pf.stat().st_size > before
        except Exception as e:
            patterns_error = str(e)[:120]

    ok = winning_query is not None
    print(json.dumps({{
        'ok': ok,
        'channel': CHANNEL,
        'winning_query': winning_query,
        'results_by_query': results_by_query,
        'total_tried': len(QUERIES),
        'patterns_written': patterns_written,
        'patterns_path': patterns_path,
        'patterns_error': patterns_error,
    }}, ensure_ascii=False))

asyncio.run(main())
"""


_X8_CROSS_PLATFORM_SCRIPT = """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
available = {c.name for c in channels_list}
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

async def main():
    cn_chs = [c for c in ['bilibili','xiaohongshu','weibo'] if c in available]
    if not cn_chs:
        print(json.dumps({'ok': False, 'error': 'no Chinese channels', 'available': sorted(available)[:10]})); return
    with patch('autosearch.mcp.server._build_channels', return_value=channels_list), \
         patch('autosearch.core.channel_bootstrap._build_channels', return_value=channels_list):
        server = create_server()
        tm = server._tool_manager
        result = await tm.call_tool('delegate_subtask', {
            'task_description': 'AI programming tools Chinese community',
            'channels': cn_chs,
            'query': '人工智能 编程工具 2024',
            'max_per_channel': 5,
        })
        by_ch = result.get('evidence_by_channel', {}) if isinstance(result, dict) else {}
        total = sum(len(v) for v in by_ch.values())
        channels_with_results = [c for c, v in by_ch.items() if len(v) > 0]
        ok = total >= 10 or (len(channels_with_results) >= 2)
        print(json.dumps({'ok': ok, 'total': total, 'by_channel': {c: len(v) for c,v in by_ch.items()}, 'channels_with_results': channels_with_results}, ensure_ascii=False))
asyncio.run(main())
"""


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


def _as_dict(result: Any) -> dict[str, Any]:
    return (
        result
        if isinstance(result, dict)
        else {"ok": False, "error": "non-dict result", "raw_result": repr(result)}
    )


def _skip_no_tikhub(scenario_id: str, name: str, t0: float) -> ScenarioResult:
    return ScenarioResult(
        scenario_id,
        "X",
        name,
        score=50,
        passed=True,
        details={"skipped": True, "reason": "no TIKHUB_API_KEY"},
        duration_s=time.monotonic() - t0,
    )


def _counts(result: dict[str, Any]) -> list[int]:
    by_query = result.get("results_by_query", {})
    if not isinstance(by_query, dict):
        return []
    return [v for v in by_query.values() if type(v) is int]


def _evidence_count(result: dict[str, Any]) -> int:
    by_query = result.get("results_by_query", {})
    if not isinstance(by_query, dict):
        return 0
    winning_query = result.get("winning_query")
    if winning_query in by_query and type(by_query[winning_query]) is int:
        return int(by_query[winning_query])
    counts = _counts(result)
    return max(counts, default=0)


def _geo_blocked(result: dict[str, Any], stderr: str) -> bool:
    text = json.dumps(result, ensure_ascii=False).lower() + "\n" + stderr.lower()
    return "region" in text or "blocked" in text


async def _run_pathfinding(
    sandbox_id: str,
    env: dict,
    scenario_id: str,
    name: str,
    channel: str,
    queries: list[str],
    *,
    geo_restriction_pass: bool = False,
) -> ScenarioResult:
    t0 = time.monotonic()
    if not env.get("TIKHUB_API_KEY"):
        return _skip_no_tikhub(scenario_id, name, t0)

    script = _PATHFIND_TEMPLATE.format(channel=channel, queries=queries)
    result, stderr = await run_python(sandbox_id, script, env=_clean_env(env), timeout=90)
    dur = time.monotonic() - t0
    result = _as_dict(result)

    ok = bool(result.get("ok"))
    blocked = geo_restriction_pass and _geo_blocked(result, stderr)
    counts = _counts(result)
    if ok:
        score = 100
        passed = True
    elif blocked:
        score = 60
        passed = True
    elif counts:
        score = 50
        passed = False
    else:
        score = 0
        passed = False

    details = {"queries": queries, **result}
    if blocked:
        details["geo_restriction_pass"] = True
    if stderr:
        details["stderr"] = stderr[:500]

    error = ""
    if not passed and score == 0:
        error = str(result.get("error") or "all queries errored")[:200]

    return ScenarioResult(
        scenario_id,
        "X",
        name,
        score=score,
        passed=passed,
        evidence_count=_evidence_count(result),
        details=details,
        error=error,
        duration_s=dur,
    )


async def x1_bilibili_mlx_tutorial(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X1",
        "bilibili_mlx_tutorial",
        "bilibili",
        [
            "MLX Apple Silicon",
            "MLX 教程 苹果",
            "机器学习 苹果芯片",
            "Apple Silicon 机器学习入门",
            "MLX framework",
            "苹果 M 系列 AI 教程",
            "机器学习 Mac",
            "深度学习 Mac 入门",
        ],
    )


async def x2_bilibili_llm_tutorial(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X2",
        "bilibili_llm_tutorial",
        "bilibili",
        [
            "大模型 教程",
            "RAG 检索增强",
            "向量数据库 入门",
            "LLM 应用开发",
            "ChatGPT 原理",
            "Transformer 讲解",
            "大语言模型",
        ],
    )


async def x3_xiaohongshu_cursor_ide(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X3",
        "xiaohongshu_cursor_ide",
        "xiaohongshu",
        [
            "Cursor IDE 使用",
            "AI 编程助手 cursor",
            "cursor 编程技巧",
            "程序员 AI 工具",
            "cursor 代码补全",
            "AI coding 工具推荐",
            "写代码 AI",
        ],
    )


async def x4_xiaohongshu_python_learning(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X4",
        "xiaohongshu_python_learning",
        "xiaohongshu",
        [
            "Python 学习路线",
            "编程入门 推荐",
            "程序员学习分享",
            "Python 教程推荐",
            "学编程 经验",
        ],
    )


async def x5_weibo_ai_tech(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X5",
        "weibo_ai_tech",
        "weibo",
        [
            "AI 工具 2024",
            "人工智能 最新",
            "大模型 进展",
            "chatgpt 使用",
            "Claude AI",
            "AI 开发者",
            "深度学习 应用",
        ],
    )


async def x6_douyin_programming(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X6",
        "douyin_programming",
        "douyin",
        [
            "编程教程",
            "Python 入门视频",
            "AI 工具使用教程",
            "程序员 经验分享",
            "代码 教学",
            "前端开发 技巧",
        ],
    )


async def x7_tiktok_english_tech(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_pathfinding(
        sandbox_id,
        env,
        "X7",
        "tiktok_english_tech",
        "tiktok",
        [
            "machine learning tutorial",
            "AI coding tools",
            "Python programming tips",
            "software development 2024",
            "tech career advice",
        ],
        geo_restriction_pass=True,
    )


async def x8_tikhub_cross_platform(sandbox_id: str, env: dict) -> ScenarioResult:
    t0 = time.monotonic()
    result, stderr = await run_python(
        sandbox_id,
        _X8_CROSS_PLATFORM_SCRIPT,
        env=_clean_env(env),
        timeout=120,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    total = int(result.get("total", 0) or 0)
    ok = bool(result.get("ok"))

    if ok:
        score = 100
    elif total >= 1:
        score = 60
    elif result.get("error"):
        score = 0
    else:
        score = 40

    details = result
    if stderr:
        details = {**details, "stderr": stderr[:500]}

    return ScenarioResult(
        "X8",
        "X",
        "tikhub_cross_platform",
        score=score,
        passed=ok,
        evidence_count=total,
        details=details,
        error="" if score > 0 else str(result.get("error") or "delegate_subtask failed")[:200],
        duration_s=dur,
    )
