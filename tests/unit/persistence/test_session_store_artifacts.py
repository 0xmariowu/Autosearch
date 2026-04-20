# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

from autosearch.core.models import Evidence, EvidenceDigest
from autosearch.persistence.session_store import SessionStore

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def make_digest(index: int = 1) -> EvidenceDigest:
    return EvidenceDigest(
        topic=f"Digest {index}",
        key_findings=[
            f"Finding {index}.1",
            f"Finding {index}.2",
        ],
        source_urls=[f"https://example.com/digest/{index}"],
        evidence_count=index,
        compressed_at=NOW,
        token_count_before=100 * index,
        token_count_after=10 * index,
    )


def make_evidence(index: int) -> Evidence:
    return Evidence(
        url=f"https://example.com/evidence/{index}",
        title=f"Evidence {index}",
        snippet=f"Snippet {index}",
        content=f"Content {index}",
        source_channel="web",
        fetched_at=NOW,
        score=0.5 + (index * 0.1),
    )


async def test_store_and_load_digest_artifact() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        digest = make_digest()

        row_id = await store.store_artifact(
            session_id="session-1",
            kind="compacted_digest",
            payload=digest,
        )
        loaded = await store.load_digests(session_id="session-1")
    finally:
        await store.close()

    assert row_id > 0
    assert loaded == [digest]


async def test_store_multiple_kinds_and_filter() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        for index in range(1, 3):
            await store.store_artifact(
                session_id="session-1",
                kind="compacted_digest",
                payload=make_digest(index),
            )
        for index in range(1, 4):
            await store.store_artifact(
                session_id="session-1",
                kind="evicted_evidence",
                payload=make_evidence(index),
            )

        all_artifacts = await store.load_artifacts(session_id="session-1")
        digest_artifacts = await store.load_artifacts(
            session_id="session-1",
            kind="compacted_digest",
        )
    finally:
        await store.close()

    assert len(all_artifacts) == 5
    assert [artifact["kind"] for artifact in all_artifacts] == [
        "compacted_digest",
        "compacted_digest",
        "evicted_evidence",
        "evicted_evidence",
        "evicted_evidence",
    ]
    assert len(digest_artifacts) == 2
    assert all(artifact["kind"] == "compacted_digest" for artifact in digest_artifacts)


async def test_load_artifacts_empty_session() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")

        artifacts = await store.load_artifacts(session_id="session-1")
    finally:
        await store.close()

    assert artifacts == []


async def test_store_artifact_foreign_key_cascade() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        await store.store_artifact(
            session_id="session-1",
            kind="compacted_digest",
            payload=make_digest(),
        )

        connection = store._connection_or_raise()
        cursor = await connection.execute("PRAGMA foreign_keys")
        try:
            row = await cursor.fetchone()
        finally:
            await cursor.close()

        assert row is not None
        assert row[0] == 1
        await connection.execute("DELETE FROM sessions WHERE id = ?", ("session-1",))
        await connection.commit()
        artifacts = await store.load_artifacts(session_id="session-1")
    finally:
        await store.close()

    assert artifacts == []


async def test_created_at_auto_populated() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        await store.store_artifact(
            session_id="session-1",
            kind="compacted_digest",
            payload=make_digest(),
        )

        artifacts = await store.load_artifacts(session_id="session-1")
    finally:
        await store.close()

    assert len(artifacts) == 1
    assert artifacts[0]["created_at"]


async def test_artifact_payload_roundtrip_for_evidence_digest() -> None:
    store = await SessionStore.open(":memory:")

    try:
        await store.create_session("session-1", "query", "deep")
        digest = make_digest()
        await store.store_artifact(
            session_id="session-1",
            kind="compacted_digest",
            payload=digest,
        )

        artifacts = await store.load_artifacts(
            session_id="session-1",
            kind="compacted_digest",
        )
    finally:
        await store.close()

    assert len(artifacts) == 1
    restored = EvidenceDigest.model_validate_json(artifacts[0]["payload_json"])
    assert restored == digest
