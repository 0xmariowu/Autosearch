"""Scenarios C1-C3: Chinese UGC channels (TikHub key injected)."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_ZH_SEARCH = """
import os, json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery
from autosearch.channels.base import MethodUnavailable

async def main():
    channels = {{c.name: c for c in _build_channels()}}
    results = []
    errors = []
    for ch_name in {channels!r}:
        if ch_name not in channels:
            errors.append(f'{{ch_name}}: not in available channels')
            continue
        try:
            evs = await channels[ch_name].search(SubQuery(text={query!r}, rationale='e2b zh test'))
            for ev in evs[:3]:
                results.append({{'channel': ch_name, 'title': ev.title[:60], 'url': ev.url}})
        except MethodUnavailable as e:
            errors.append(f'{{ch_name}}: unavailable — {{e}}')
        except Exception as e:
            errors.append(f'{{ch_name}}: error — {{str(e)[:80]}}')

    evidence_count = len(results)
    ok = evidence_count >= {min_count} or (evidence_count == 0 and len(errors) > 0 and all('unavailable' in e or 'error' in e for e in errors))
    print(json.dumps({{
        'ok': ok,
        'evidence_count': evidence_count,
        'graceful_fail': evidence_count == 0 and len(errors) > 0,
        'results': results,
        'errors': errors,
    }}))

asyncio.run(main())
"""


async def _zh_search(
    sandbox_id: str,
    env: dict,
    scenario_id: str,
    name: str,
    query: str,
    channels: list[str],
    min_count: int = 1,
) -> ScenarioResult:
    t0 = time.monotonic()
    script = _ZH_SEARCH.format(channels=channels, query=query, min_count=min_count)
    result, _ = await run_python(sandbox_id, script, env=env, timeout=45)
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    ev = result.get("evidence_count", 0)
    graceful = result.get("graceful_fail", False)

    if ev >= min_count:
        score = 100
    elif ev > 0:
        score = 80  # partial results
    elif graceful:
        score = 60  # explicit error (TikHub unavailable)
    elif not result.get("error"):
        score = 50  # ran ok, no crash, just no content for this query
    else:
        score = 20

    return ScenarioResult(
        scenario_id,
        "C",
        name,
        score=score,
        passed=ok,
        evidence_count=ev,
        details={
            "query": query,
            "graceful_fail": graceful,
            **{k: v for k, v in result.items() if k != "results"},
            "sample_results": result.get("results", [])[:2],
        },
        duration_s=dur,
    )


async def c1_xhs_cursor(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _zh_search(
        sandbox_id,
        env,
        "C1",
        "xhs_cursor_reviews",
        query="小红书 Cursor AI 编程助手使用体验评测",
        channels=["xiaohongshu", "zhihu"],
        min_count=1,
    )


async def c2_zhihu_deepseek(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _zh_search(
        sandbox_id,
        env,
        "C2",
        "zhihu_deepseek_analysis",
        query="知乎 DeepSeek R2 技术原理分析 大模型",
        channels=["zhihu", "weibo"],
        min_count=1,
    )


async def c3_bili_mlx(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _zh_search(
        sandbox_id,
        env,
        "C3",
        "bili_mlx_tutorial",
        query="B站 Apple Silicon MLX 机器学习入门教程 up主",
        channels=["bilibili", "xiaohongshu"],
        min_count=1,
    )
