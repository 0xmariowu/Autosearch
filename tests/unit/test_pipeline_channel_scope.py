# Self-written for F103 pipeline channel scope filtering
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from autosearch.core.models import Evidence, SearchMode, SubQuery
from autosearch.core.pipeline import Pipeline
from autosearch.core.search_scope import SearchScope

NOW = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)


class DummyClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls = 0
        self.cost_tracker = None

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        _ = prompt
        payload = self.payloads[self.calls]
        self.calls += 1
        return response_model.model_validate(payload)


class FakeChannel:
    def __init__(self, name: str, languages: list[str]) -> None:
        self.name = name
        self.languages = languages
        self.calls = 0
        self.queries: list[str] = []

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.calls += 1
        self.queries.append(query.text)
        return [
            Evidence(
                url=f"https://example.com/{self.name}/{query.text.replace(' ', '-')}",
                title=f"{self.name} evidence",
                snippet=f"{self.name} snippet",
                content=f"{self.name} content for {query.text}",
                source_channel=self.name,
                fetched_at=NOW,
            )
        ]


def _pipeline_payloads() -> list[dict[str, object]]:
    return [
        {"known_facts": [], "gaps": []},
        {
            "need_clarification": False,
            "question": "",
            "verification": "Proceed with research.",
            "rubrics": ["Use evidence."],
            "mode": "fast",
        },
        {
            "subqueries": [
                {
                    "text": "pipeline channel scope filter",
                    "rationale": "exercise the active channel set",
                }
            ]
        },
        {"gaps": []},
        {"headings": ["Overview"]},
        {"headings": ["Overview"]},
        {"content": "Scoped channels returned evidence [1].", "ref_ids": [1]},
        {"grade": "pass", "follow_up_gaps": []},
    ]


def _make_pipeline(
    channels: list[FakeChannel],
    *,
    on_event=None,
) -> Pipeline:
    return Pipeline(
        llm=DummyClient(_pipeline_payloads()),
        channels=channels,
        on_event=on_event,
    )


@pytest.mark.asyncio
async def test_pipeline_filters_channels_by_scope_zh_only() -> None:
    en_a = FakeChannel("en-a", ["en"])
    en_b = FakeChannel("en-b", ["en", "mixed"])
    zh_a = FakeChannel("zh-a", ["zh"])
    zh_b = FakeChannel("zh-b", ["zh", "mixed"])

    pipeline = _make_pipeline([en_a, en_b, zh_a, zh_b])

    result = await pipeline.run(
        "Which channels run?",
        mode_hint=SearchMode.FAST,
        scope=SearchScope(channel_scope="zh_only"),
    )

    assert result.delivery_status == "ok"
    assert en_a.calls == 0
    assert en_b.calls == 0
    assert zh_a.calls == 1
    assert zh_b.calls == 1


@pytest.mark.asyncio
async def test_pipeline_keeps_all_channels_when_scope_is_all() -> None:
    channels = [
        FakeChannel("en-a", ["en"]),
        FakeChannel("en-b", ["en", "mixed"]),
        FakeChannel("zh-a", ["zh"]),
        FakeChannel("zh-b", ["zh", "mixed"]),
    ]
    pipeline = _make_pipeline(channels)

    result = await pipeline.run(
        "Which channels run?",
        mode_hint=SearchMode.FAST,
        scope=SearchScope(channel_scope="all"),
    )

    assert result.delivery_status == "ok"
    assert [channel.calls for channel in channels] == [1, 1, 1, 1]


@pytest.mark.asyncio
async def test_pipeline_falls_back_when_scope_filter_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channels = [
        FakeChannel("en-a", ["en"]),
        FakeChannel("en-b", ["en", "mixed"]),
    ]
    warnings: list[tuple[tuple[object, ...], dict[str, object]]] = []
    pipeline = _make_pipeline(channels)

    monkeypatch.setattr(
        pipeline.logger,
        "warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )

    result = await pipeline.run(
        "Which channels run?",
        mode_hint=SearchMode.FAST,
        scope=SearchScope(channel_scope="zh_only"),
    )

    assert result.delivery_status == "ok"
    assert [channel.calls for channel in channels] == [1, 1]
    assert warnings == [
        (
            ("channel_scope_filter_empty",),
            {"channel_scope": "zh_only", "original_count": 2},
        )
    ]


@pytest.mark.asyncio
async def test_pipeline_emits_channels_filtered_event() -> None:
    events: list[dict[str, object]] = []
    channels = [
        FakeChannel("en-a", ["en"]),
        FakeChannel("en-b", ["en", "mixed"]),
        FakeChannel("zh-a", ["zh"]),
        FakeChannel("zh-b", ["zh", "mixed"]),
    ]
    pipeline = _make_pipeline(channels, on_event=events.append)

    await pipeline.run(
        "Which channels run?",
        mode_hint=SearchMode.FAST,
        scope=SearchScope(channel_scope="zh_only"),
    )

    assert {
        "type": "channels_filtered",
        "scope": "zh_only",
        "before": 4,
        "after": 2,
    } in events
