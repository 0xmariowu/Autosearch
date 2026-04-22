"""Scenarios E1-E2: Clarify / 追问 flow tests."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, run_python

_ENV_DUMMY = {"AUTOSEARCH_LLM_MODE": "dummy"}


async def e1_ambiguous_triggers_clarify(sandbox_id: str, env: dict) -> ScenarioResult:
    """E1: Ambiguous query → need_clarification=True + question_options populated."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.mcp.server import create_server, ClarifyToolResponse

class _MockClarifier:
    async def clarify(self, req, *a, **kw):
        from autosearch.core.models import ClarifyResult, SearchMode
        return ClarifyResult(
            need_clarification=True,
            question='你想了解哪个区的 XGP 订阅？',
            question_options=['香港区', '国服', '香港 vs 国服对比'],
            rubrics=[],
            mode=SearchMode.FAST,
        )

async def main():
    from unittest.mock import patch
    with patch('autosearch.mcp.server.Clarifier', return_value=_MockClarifier()), \
         patch('autosearch.mcp.server.LLMClient'), \
         patch('autosearch.mcp.server._build_channels', return_value=[]):
        server = create_server()
        resp = await server._tool_manager.call_tool('run_clarify', {'query': 'XGP 怎么买'})
        print(json.dumps({
            'ok': resp.need_clarification is True and len(resp.question_options) >= 2,
            'need_clarification': resp.need_clarification,
            'question': resp.question,
            'question_options': resp.question_options,
            'question_options_count': len(resp.question_options),
        }))

asyncio.run(main())
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "E1",
        "E",
        "ambiguous_triggers_clarify",
        score=100 if ok else (50 if result.get("need_clarification") else 0),
        passed=ok,
        details=result,
        duration_s=dur,
    )


async def e2_clear_query_skips_clarify(sandbox_id: str, env: dict) -> ScenarioResult:
    """E2: Clear query → need_clarification=False → channel_priority populated."""
    t0 = time.monotonic()
    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.mcp.server import create_server

class _ClearClarifier:
    async def clarify(self, req, *a, **kw):
        from autosearch.core.models import ClarifyResult, SearchMode
        return ClarifyResult(
            need_clarification=False,
            verification='Clear query, proceeding with github + stackoverflow',
            rubrics=[],
            mode=SearchMode.FAST,
            channel_priority=['github', 'stackoverflow'],
            channel_skip=[],
        )

async def main():
    from unittest.mock import patch
    with patch('autosearch.mcp.server.Clarifier', return_value=_ClearClarifier()), \
         patch('autosearch.mcp.server.LLMClient'), \
         patch('autosearch.mcp.server._build_channels', return_value=[]):
        server = create_server()
        resp = await server._tool_manager.call_tool(
            'run_clarify',
            {'query': 'DuckDB HNSW vector index memory limitations GitHub issues'}
        )

        # Scope wizard: with no params provided, all 4 questions appear
        from autosearch.core.scope_clarifier import ScopeClarifier
        questions = ScopeClarifier().questions_for({})
        scope_fields = [q.field for q in questions]

        print(json.dumps({
            'ok': (
                resp.need_clarification is False and
                len(resp.question_options) == 0 and
                'github' in resp.channel_priority
            ),
            'need_clarification': resp.need_clarification,
            'channel_priority': resp.channel_priority,
            'question_options_empty': len(resp.question_options) == 0,
            'scope_questions_count': len(questions),
            'scope_fields': scope_fields,
        }))

asyncio.run(main())
""",
        env=_ENV_DUMMY,
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "E2",
        "E",
        "clear_query_skips_clarify",
        score=100 if ok else 40,
        passed=ok,
        details=result,
        duration_s=dur,
    )
