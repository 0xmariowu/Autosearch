"""Tests for the orchestrator module."""

try:
    import pytest
except ImportError:
    pytest = None
from unittest.mock import patch


def test_orchestrator_imports():
    pass


def test_dry_run_without_api_key():
    """Without OPENROUTER_API_KEY, dry_run should return error."""
    import os

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
        from orchestrator import run_task

        result = run_task("test query", dry_run=True)
        assert result["status"] == "error"


def test_summarize_result_list():
    from orchestrator import _summarize_result

    result = _summarize_result(
        [{"title": "A", "url": "a.com"}, {"title": "B", "url": "b.com"}]
    )
    assert "2 items" in result
    assert "A" in result


def test_summarize_result_dict():
    from orchestrator import _summarize_result

    result = _summarize_result({"status": "ok", "count": 5})
    assert "ok" in result


def test_summarize_result_empty():
    from orchestrator import _summarize_result

    result = _summarize_result([])
    assert "0 items" in result


def test_extract_tool_call():
    from orchestrator import _extract_tool_call

    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "t1",
                            "function": {
                                "name": "search_web",
                                "arguments": '{"input": "test"}',
                            },
                        }
                    ]
                }
            }
        ]
    }
    tool = _extract_tool_call(response)
    assert tool["name"] == "search_web"
    assert tool["id"] == "t1"
    assert tool["input"] == {"input": "test"}


def test_extract_tool_call_none():
    from orchestrator import _extract_tool_call

    response = {"choices": [{"message": {}}]}
    assert _extract_tool_call(response) is None


def test_extract_text():
    from orchestrator import _extract_text

    response = {"choices": [{"message": {"content": "Part 1 and Part 2"}}]}
    assert "Part 1" in _extract_text(response)
    assert "Part 2" in _extract_text(response)
