# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

import autosearch.persistence.session_store as session_store_module
from autosearch.core.models import Evidence
from autosearch.persistence.session_store import SessionStore


def _make_evidence(url: str, title: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet="Short snippet",
        content="Full content",
        source_channel="web",
        fetched_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
        score=0.9,
    )


async def test_create_session_fetches_started_row() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "find sqlite patterns", "deep")

        session = await store.fetch_session("session-1")
    finally:
        await store.close()

    assert session is not None
    assert session["id"] == "session-1"
    assert session["query"] == "find sqlite patterns"
    assert session["mode"] == "deep"
    assert session["status"] == "started"
    assert session["finished_at"] is None
    assert session["markdown"] is None
    assert session["cost"] == 0.0


async def test_finish_session_updates_markdown_cost_and_finished_at(
    monkeypatch,
) -> None:
    timestamps = iter(
        [
            datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
            datetime(2026, 4, 17, 9, 5, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(session_store_module, "_utc_now", lambda: next(timestamps))
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "fast")
        await store.finish_session("session-1", "completed", "# Report", 1.75)

        session = await store.fetch_session("session-1")
    finally:
        await store.close()

    assert session is not None
    assert session["status"] == "completed"
    assert session["markdown"] == "# Report"
    assert session["cost"] == 1.75
    assert session["finished_at"] == "2026-04-17T09:05:00+00:00"


async def test_add_evidence_is_retrievable_from_session() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        await store.add_evidence(
            "session-1",
            1,
            _make_evidence("https://example.com/evidence", "Evidence Title"),
        )

        session = await store.fetch_session("session-1")
    finally:
        await store.close()

    assert session is not None
    assert session["evidence"] == [
        {
            "session_id": "session-1",
            "rank": 1,
            "url": "https://example.com/evidence",
            "title": "Evidence Title",
            "snippet": "Short snippet",
            "source_channel": "web",
            "score": 0.9,
        }
    ]


async def test_list_recent_returns_reverse_chronological_order(monkeypatch) -> None:
    timestamps = iter(
        [
            datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
            datetime(2026, 4, 17, 9, 10, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(session_store_module, "_utc_now", lambda: next(timestamps))
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "earlier", "fast")
        await store.create_session("session-2", "later", "deep")

        recent = await store.list_recent()
    finally:
        await store.close()

    assert [item["id"] for item in recent] == ["session-2", "session-1"]


async def test_add_query_log_is_retrievable_from_session() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        await store.add_query_log("session-1", "sqlite async pool", "web", 7)

        session = await store.fetch_session("session-1")
    finally:
        await store.close()

    assert session is not None
    assert len(session["query_log"]) == 1
    assert session["query_log"][0]["session_id"] == "session-1"
    assert session["query_log"][0]["subquery"] == "sqlite async pool"
    assert session["query_log"][0]["channel"] == "web"
    assert session["query_log"][0]["results"] == 7
    assert session["query_log"][0]["issued_at"]
