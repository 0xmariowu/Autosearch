"""Scenarios E1-E2: Clarify / follow-up question flow tests."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_ENV_DUMMY = {"AUTOSEARCH_LLM_MODE": "dummy"}


async def e1_ambiguous_triggers_clarify(sandbox_id: str, env: dict) -> ScenarioResult:
    """E1: Ambiguous query → need_clarification=True + question populated."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.models import ClarifyResult, SearchMode

class _MockClarifier:
    async def clarify(self, req, *a, **kw):
        kw_args = {}
        # question_options added in PR#263; handle both old and new versions
        import inspect
        sig = inspect.signature(ClarifyResult.__init__)
        if 'question_options' in sig.parameters:
            kw_args['question_options'] = ['香港区', '国服', '香港 vs 国服对比']
        return ClarifyResult(
            need_clarification=True,
            question='你想了解哪个区的 XGP 订阅？',
            rubrics=[],
            mode=SearchMode.FAST,
            **kw_args,
        )

async def main():
    from unittest.mock import patch
    from autosearch.mcp.server import create_server
    with patch('autosearch.mcp.server.Clarifier', return_value=_MockClarifier()), \
         patch('autosearch.mcp.server.LLMClient'), \
         patch('autosearch.mcp.server._build_channels', return_value=[]):
        server = create_server()
        resp = await server._tool_manager.call_tool('run_clarify', {'query': 'XGP 怎么买'})

        question_options = getattr(resp, 'question_options', [])
        ok = (
            resp.need_clarification is True and
            bool(resp.question)
        )
        print(json.dumps({
            'ok': ok,
            'need_clarification': resp.need_clarification,
            'question': resp.question,
            'question_options': question_options,
            'question_options_count': len(question_options),
            'has_question_options_field': hasattr(resp, 'question_options'),
        }))

asyncio.run(main())
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    has_options = result.get("has_question_options_field", False)
    score = 0
    if result.get("need_clarification"):
        score += 50
    if result.get("question"):
        score += 30
    if has_options and result.get("question_options_count", 0) >= 2:
        score += 20
    elif has_options:
        score += 10  # field exists but no options generated yet
    return ScenarioResult(
        "E1",
        "E",
        "ambiguous_triggers_clarify",
        score=score,
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def e2_clear_query_skips_clarify(sandbox_id: str, env: dict) -> ScenarioResult:
    """E2: Clear query → need_clarification=False + scope wizard returns 4 questions."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.models import ClarifyResult, SearchMode

class _ClearClarifier:
    async def clarify(self, req, *a, **kw):
        return ClarifyResult(
            need_clarification=False,
            verification='Clear query, proceeding',
            rubrics=[],
            mode=SearchMode.FAST,
            channel_priority=['github', 'stackoverflow'],
            channel_skip=[],
        )

async def main():
    from unittest.mock import patch
    from autosearch.mcp.server import create_server
    with patch('autosearch.mcp.server.Clarifier', return_value=_ClearClarifier()), \
         patch('autosearch.mcp.server.LLMClient'), \
         patch('autosearch.mcp.server._build_channels', return_value=[]):
        server = create_server()
        resp = await server._tool_manager.call_tool(
            'run_clarify',
            {'query': 'DuckDB HNSW vector index memory limitations GitHub issues'}
        )

    # Scope wizard questions
    from autosearch.core.scope_clarifier import ScopeClarifier
    questions = ScopeClarifier().questions_for({})

    question_options = getattr(resp, 'question_options', [])
    ok = (
        resp.need_clarification is False and
        'github' in resp.channel_priority and
        len(questions) >= 3
    )
    print(json.dumps({
        'ok': ok,
        'need_clarification': resp.need_clarification,
        'channel_priority': resp.channel_priority,
        'question_options_empty': len(question_options) == 0,
        'scope_questions_count': len(questions),
        'scope_fields': [q.field for q in questions],
        'each_scope_question_has_options': all(len(q.options) >= 2 for q in questions if q.field != 'domain_followups'),
    }))

asyncio.run(main())
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 0
    if result.get("need_clarification") is False:
        score += 40
    if "github" in result.get("channel_priority", []):
        score += 20
    if result.get("scope_questions_count", 0) >= 3:
        score += 20
    if result.get("each_scope_question_has_options"):
        score += 20
    return ScenarioResult(
        "E2",
        "E",
        "clear_query_skips_clarify",
        score=score,
        passed=ok,
        details=result,
        duration_s=dur,
    )
