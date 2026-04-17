# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

from autosearch.core.models import Evidence
from autosearch.persistence.session_store import SessionStore


def _make_evidence() -> Evidence:
    return Evidence(
        url="https://example.com/durable-evidence",
        title="Durable Evidence",
        snippet="Short snippet",
        content="Evidence that should still exist after reopening the on-disk database.",
        source_channel="web",
        fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        score=0.75,
    )


async def test_session_store_persists_data_across_reopen(tmp_path) -> None:
    db_path = tmp_path / "autosearch-test.db"
    session_id = "session-durable"

    store = await SessionStore.open(db_path)
    try:
        await store.create_session(session_id, "durable query", "deep")
        await store.add_evidence(session_id, 1, _make_evidence())
        await store.finish_session(session_id, "ok", "markdown text", 0.5)
    finally:
        await store.close()

    reopened_store = await SessionStore.open(db_path)
    try:
        session = await reopened_store.fetch_session(session_id)
    finally:
        await reopened_store.close()

    assert session is not None
    assert session["id"] == session_id
    assert session["status"] == "ok"
    assert session["markdown"] == "markdown text"
    assert session["cost"] == 0.5
    assert session["evidence"]
    assert session["evidence"][0]["url"] == "https://example.com/durable-evidence"
    assert db_path.exists()
    assert db_path.stat().st_size > 0
