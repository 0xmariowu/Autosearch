"""Tests for scripts/bench/bench_augment_vs_bare.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
import yaml


def _load_runner() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "bench" / "bench_augment_vs_bare.py"
    module_name = "_bench_augment_vs_bare_under_test"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _anthropic_text(text: str) -> dict[str, object]:
    return {"content": [{"type": "text", "text": text}]}


def test_load_topics_list_form(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.yaml"
    yaml.safe_dump(
        [
            {"name": "topic1", "query": "What is X?"},
            {"name": "topic2", "query": "What is Y?"},
        ],
        topics_file.open("w", encoding="utf-8"),
    )

    topics = RUNNER.load_topics(topics_file)

    assert topics == [
        {"name": "topic1", "query": "What is X?"},
        {"name": "topic2", "query": "What is Y?"},
    ]


def test_load_topics_dict_wrapped(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.yaml"
    yaml.safe_dump(
        {"topics": [{"name": "topic1", "query": "q1"}]},
        topics_file.open("w", encoding="utf-8"),
    )

    topics = RUNNER.load_topics(topics_file)

    assert topics == [{"name": "topic1", "query": "q1"}]


def test_load_topics_rejects_missing_fields(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.yaml"
    yaml.safe_dump([{"query": "no name here"}], topics_file.open("w", encoding="utf-8"))

    with pytest.raises(ValueError, match="'name' and 'query'"):
        RUNNER.load_topics(topics_file)


def test_load_topics_rejects_non_list(tmp_path: Path) -> None:
    topics_file = tmp_path / "topics.yaml"
    yaml.safe_dump("not a list", topics_file.open("w", encoding="utf-8"))

    with pytest.raises(ValueError, match="must contain a list"):
        RUNNER.load_topics(topics_file)


def test_call_claude_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == RUNNER.ANTHROPIC_API_URL
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json=_anthropic_text("test report body"))

    with _client(handler) as client:
        ok, text = RUNNER.call_claude(
            query="What?",
            system_prompt="You are test.",
            api_key="test-key",
            model="claude-sonnet-4-6",
            max_tokens=100,
            http_client=client,
        )

    assert ok is True
    assert text == "test report body"


def test_call_claude_api_error_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server down")

    with _client(handler) as client:
        ok, text = RUNNER.call_claude(
            query="What?",
            system_prompt="You are test.",
            api_key="test-key",
            model="claude-sonnet-4-6",
            max_tokens=100,
            http_client=client,
        )

    assert ok is False
    assert "api_error" in text
    assert "500" in text


def test_call_claude_non_json_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with _client(handler) as client:
        ok, text = RUNNER.call_claude(
            query="What?",
            system_prompt="You are test.",
            api_key="test-key",
            model="claude-sonnet-4-6",
            max_tokens=100,
            http_client=client,
        )

    assert ok is False
    assert "non_json" in text


def test_call_claude_empty_content_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    with _client(handler) as client:
        ok, text = RUNNER.call_claude(
            query="What?",
            system_prompt="You are test.",
            api_key="test-key",
            model="claude-sonnet-4-6",
            max_tokens=100,
            http_client=client,
        )

    assert ok is False
    assert "empty content" in text


def test_augmented_system_prompt_includes_trio_tool_names() -> None:
    """The augmented system prompt must mention the v2 trio tools so runtime AI knows them."""
    assert "list_skills" in RUNNER.AUGMENTED_SYSTEM_PROMPT
    assert "run_clarify" in RUNNER.AUGMENTED_SYSTEM_PROMPT
    assert "run_channel" in RUNNER.AUGMENTED_SYSTEM_PROMPT
    assert "AutoSearch" in RUNNER.AUGMENTED_SYSTEM_PROMPT


def test_augmented_system_prompt_includes_channel_groups() -> None:
    """The augmented prompt must enumerate channel groups so the runtime can reason about them."""
    expected_groups = [
        "channels-chinese-ugc",
        "channels-academic",
        "channels-code-package",
        "channels-video-audio",
        "tools-fetch-render",
    ]
    for group in expected_groups:
        assert group in RUNNER.AUGMENTED_SYSTEM_PROMPT, (
            f"group {group} missing from augmented system prompt"
        )


def test_bare_system_prompt_does_not_mention_autosearch() -> None:
    """The bare prompt must NOT leak autosearch details — that's what makes it bare."""
    assert "autosearch" not in RUNNER.BARE_SYSTEM_PROMPT.lower()
    assert "list_skills" not in RUNNER.BARE_SYSTEM_PROMPT
    assert "run_channel" not in RUNNER.BARE_SYSTEM_PROMPT
    assert "channels-" not in RUNNER.BARE_SYSTEM_PROMPT
