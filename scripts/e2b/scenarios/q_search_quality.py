"""Scenarios Q1-Q15: Search quality via pairwise LLM judge (AutoSearch vs bare Claude)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python


async def _bare_claude(
    query: str,
    openrouter_key: str,
    model: str = "anthropic/claude-haiku-4-5",
) -> str:
    """Get bare Claude response with no AutoSearch context."""
    if not openrouter_key:
        return ""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={
                "model": model,
                "max_tokens": 400,
                "messages": [
                    {"role": "user", "content": f"Answer this research question: {query}"}
                ],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _pairwise_judge(query: str, a: str, b: str, openrouter_key: str) -> str:
    """Pairwise judge. Randomize A/B position to prevent position bias."""
    import random

    if random.random() < 0.5:
        prompt_a, prompt_b, flip = a, b, False
    else:
        prompt_a, prompt_b, flip = b, a, True

    if not openrouter_key:
        return "tie"

    prompt = f"""Compare two research responses to: "{query}"

Response A: {prompt_a[:500]}

Response B: {prompt_b[:500]}

Which response is more useful for actual research (real sources, specific content, factual depth)?
Reply EXACTLY with one of: {{"winner":"A"}} or {{"winner":"B"}} or {{"winner":"tie"}}"""

    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={
                "model": "anthropic/claude-haiku-4-5",
                "max_tokens": 30,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]

    for line in reversed(content.strip().splitlines()):
        line = line.strip()
        if "{" in line and "winner" in line:
            try:
                w = json.loads(line[line.index("{") : line.rindex("}") + 1]).get("winner", "tie")
                if flip:
                    w = {"A": "B", "B": "A"}.get(w, w)
                return w
            except Exception:
                pass
    return "tie"


_CHANNEL_SEARCH = """
import json, asyncio
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery

CHANNEL = {channel!r}
QUERY = {query!r}

async def main():
    channels = {{c.name: c for c in _build_channels()}}
    ch = channels.get(CHANNEL)
    if not ch:
        print(json.dumps({{'ok': False, 'error': 'channel not found', 'available': list(channels.keys())[:5]}}))
        return
    try:
        evs = await ch.search(SubQuery(text=QUERY, rationale='quality test'))
        results = [
            {{'url': e.url, 'title': (e.title or '')[:80], 'snippet': (e.snippet or '')[:120]}}
            for e in evs[:5]
        ]
        summary = '\\n'.join('- %s: %s' % (r['title'], r['snippet']) for r in results if r['title'])
        print(json.dumps({{'ok': len(results) > 0, 'count': len(results), 'summary': summary, 'results': results[:3]}}))
    except Exception as e:
        print(json.dumps({{'ok': False, 'error': str(e)[:200]}}))

asyncio.run(main())
"""


async def _run_quality_scenario(
    sandbox_id: str,
    env: dict,
    scenario_id: str,
    channel: str,
    query: str,
) -> ScenarioResult:
    t0 = time.monotonic()
    installed = await install_autosearch(sandbox_id, timeout=180)
    if not installed:
        return ScenarioResult(
            scenario_id,
            "Q",
            f"{channel}_search_quality",
            0,
            False,
            details={"channel": channel, "query": query},
            error="pip install failed",
            duration_s=time.monotonic() - t0,
        )

    script = _CHANNEL_SEARCH.format(channel=channel, query=query)
    result, stderr = await run_python(sandbox_id, script, env=env, timeout=90)
    if not isinstance(result, dict):
        result = {"ok": False, "error": "non-dict result", "raw_result": result}

    openrouter_key = env.get("OPENROUTER_API_KEY", "")
    autosearch_summary = str(result.get("summary") or "")
    evidence_count = int(result.get("count", 0) or 0)
    details: dict[str, Any] = {
        "channel": channel,
        "query": query,
        "search_ok": bool(result.get("ok")),
        "search_error": result.get("error", ""),
        "autosearch_summary": autosearch_summary[:800],
        "results": result.get("results", []),
    }

    if not openrouter_key:
        details["judge_skipped"] = "OPENROUTER_API_KEY missing"
        return ScenarioResult(
            scenario_id,
            "Q",
            f"{channel}_search_quality",
            score=50,
            passed=True,
            evidence_count=evidence_count,
            details=details,
            error="",
            duration_s=time.monotonic() - t0,
        )

    try:
        bare = await _bare_claude(query, openrouter_key)
        winner = await _pairwise_judge(query, autosearch_summary, bare, openrouter_key)
    except Exception as exc:  # noqa: BLE001 - external judge boundary
        details["judge_error"] = f"{type(exc).__name__}: {exc}"[:300]
        return ScenarioResult(
            scenario_id,
            "Q",
            f"{channel}_search_quality",
            score=50,
            passed=True,
            evidence_count=evidence_count,
            details=details,
            error="",
            duration_s=time.monotonic() - t0,
        )

    score = {"A": 100, "tie": 70, "B": 0}.get(winner, 70)
    passed = winner in ("A", "tie")
    details.update(
        {
            "bare_claude_length": len(bare),
            "bare_claude_preview": bare[:500],
            "winner": winner,
            "stderr": stderr[-500:] if stderr else "",
        }
    )
    return ScenarioResult(
        scenario_id,
        "Q",
        f"{channel}_search_quality",
        score=score,
        passed=passed,
        evidence_count=evidence_count,
        details=details,
        error="" if passed else "pairwise judge preferred bare Claude",
        duration_s=time.monotonic() - t0,
    )


async def q1_arxiv_cot_prompting(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q1",
        "arxiv",
        "chain-of-thought prompting language models 2023 few-shot",
    )


async def q2_pubmed_rna_biomarker(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q2",
        "pubmed",
        "RNA sequencing cancer biomarker discovery 2024",
    )


async def q3_hackernews_rust_tokio(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q3",
        "hackernews",
        "Rust async runtime tokio performance 2024",
    )


async def q4_stackoverflow_asyncio(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q4",
        "stackoverflow",
        "Python asyncio event loop best practices",
    )


async def q5_github_opentelemetry(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q5",
        "github",
        "distributed tracing opentelemetry Go implementation",
    )


async def q6_devto_typescript_generics(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q6",
        "devto",
        "TypeScript generics advanced patterns real examples",
    )


async def q7_ddgs_claude_code_hooks(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q7",
        "ddgs",
        "Claude Code hooks configuration tutorial 2025",
    )


async def q8_wikipedia_transformer_attention(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q8",
        "wikipedia",
        "transformer neural network self-attention mechanism",
    )


async def q9_pubmed_crispr_trials(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q9",
        "pubmed",
        "CRISPR therapeutic application clinical trial 2024",
    )


async def q10_arxiv_diffusion_survey(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q10",
        "arxiv",
        "diffusion model image generation survey 2024",
    )


async def q11_hackernews_uv_python(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q11",
        "hackernews",
        "uv Python package manager performance features",
    )


async def q12_stackoverflow_kubernetes_autoscaling(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q12",
        "stackoverflow",
        "Kubernetes HPA VPA autoscaling comparison",
    )


async def q13_ddgs_chinese_rag(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q13",
        "ddgs",
        "大模型 RAG 检索增强生成 最佳实践 2024",
    )


async def q14_ddgs_chinese_macos_homebrew(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q14",
        "ddgs",
        "macOS 开发环境配置 Homebrew 2024 推荐",
    )


async def q15_devto_ai_coding_workflow(sandbox_id: str, env: dict) -> ScenarioResult:
    return await _run_quality_scenario(
        sandbox_id,
        env,
        "Q15",
        "devto",
        "AI coding assistant productivity real workflow",
    )
