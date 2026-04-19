# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

from autosearch.core.iteration import IterationController
from autosearch.core.models import Evidence, SubQuery

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


class EmptyChannel:
    name = "empty"
    languages = ["en", "mixed"]

    def __init__(self, responses: list[list[Evidence]]) -> None:
        self.responses = list(responses)

    async def search(self, query: SubQuery) -> list[Evidence]:
        _ = query
        return self.responses.pop(0)


class FilledChannel:
    name = "filled"
    languages = ["en", "mixed"]

    async def search(self, query: SubQuery) -> list[Evidence]:
        _ = query
        return [
            Evidence(
                url="https://example.com/evidence",
                title="Evidence",
                snippet="Evidence snippet",
                source_channel=self.name,
                fetched_at=NOW,
            )
        ]


class FailingChannel:
    name = "failing"
    languages = ["en", "mixed"]

    async def search(self, query: SubQuery) -> list[Evidence]:
        _ = query
        raise RuntimeError("boom")


class RecordingLogger:
    def __init__(self) -> None:
        self.warning_calls: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.warning_calls.append((event, kwargs))


async def test_channel_empty_result_incremented() -> None:
    controller = IterationController()
    subqueries = [
        SubQuery(text="first query", rationale="seed"),
        SubQuery(text="second query", rationale="follow-up"),
    ]

    await controller._search(
        subqueries=subqueries,
        channels=[EmptyChannel(responses=[[], []])],
        iteration=1,
    )

    assert controller.empty_counts_by_channel() == {"empty": 2}


async def test_channel_empty_result_logged(monkeypatch) -> None:
    controller = IterationController()
    logger = RecordingLogger()
    monkeypatch.setattr(controller, "logger", logger)
    subquery_text = "x" * 120

    await controller._search(
        subqueries=[SubQuery(text=subquery_text, rationale="seed")],
        channels=[EmptyChannel(responses=[[]])],
        iteration=1,
    )

    assert logger.warning_calls == [
        (
            "channel_empty_result",
            {
                "channel": "empty",
                "subquery": subquery_text[:80],
            },
        )
    ]


async def test_channel_with_evidence_not_counted() -> None:
    controller = IterationController()

    result = await controller._search(
        subqueries=[SubQuery(text="query", rationale="seed")],
        channels=[FilledChannel()],
        iteration=1,
    )

    assert len(result) == 1
    assert controller.empty_counts_by_channel().get("filled", 0) == 0


async def test_channel_exception_not_counted_as_empty() -> None:
    controller = IterationController()

    result = await controller._search(
        subqueries=[SubQuery(text="query", rationale="seed")],
        channels=[FailingChannel()],
        iteration=1,
    )

    assert result == []
    assert controller.empty_counts_by_channel().get("failing", 0) == 0
