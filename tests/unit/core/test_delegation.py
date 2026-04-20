from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from autosearch.core.delegation import EvidenceDelegator
from autosearch.core.models import Evidence, EvidenceDigest
from autosearch.persistence.session_store import SessionStore

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.asyncio


class FakeLLMClient:
    def __init__(
        self,
        *,
        delay_seconds: float = 0.0,
        fail_on_prompt_substrings: set[str] | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.fail_on_prompt_substrings = fail_on_prompt_substrings or set()
        self.calls = 0
        self.prompts: list[str] = []
        self.max_concurrent_calls = 0
        self._active_calls = 0
        self._lock = asyncio.Lock()

    async def complete(self, prompt: str, response_model: type[EvidenceDigest]) -> EvidenceDigest:
        _ = response_model
        async with self._lock:
            self.calls += 1
            call_number = self.calls
            self.prompts.append(prompt)
            self._active_calls += 1
            self.max_concurrent_calls = max(self.max_concurrent_calls, self._active_calls)

        try:
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)
            for marker in self.fail_on_prompt_substrings:
                if marker in prompt:
                    raise RuntimeError(f"forced failure for {marker}")
            return EvidenceDigest(
                topic=f"Digest {call_number}",
                key_findings=[f"Finding {call_number}.1", f"Finding {call_number}.2"],
                source_urls=[f"https://placeholder.example/{call_number}"],
                evidence_count=1,
                compressed_at=NOW,
                token_count_before=1,
                token_count_after=1,
            )
        finally:
            async with self._lock:
                self._active_calls -= 1


def make_evidence(index: int) -> Evidence:
    return Evidence(
        url=f"https://example.com/{index}",
        title=f"Evidence {index}",
        snippet=f"Snippet {index}",
        content=f"Content {index}",
        source_channel="web",
        fetched_at=NOW,
    )


async def test_delegate_empty_evidence_returns_empty() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client)

    digests = await delegator.delegate([], "empty")

    assert digests == []
    assert client.calls == 0


async def test_delegate_below_slice_size_returns_single_digest() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=15)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 6)], "query")

    assert len(digests) == 1
    assert digests[0].evidence_count == 5
    assert client.calls == 1


async def test_delegate_splits_into_multiple_slices() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=15, max_workers=4)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 41)], "query")

    assert len(digests) == 3
    assert [digest.evidence_count for digest in digests] == [15, 15, 10]


async def test_delegate_respects_max_workers_cap() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=15, max_workers=4)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 101)], "query")

    assert len(digests) == 4
    assert [digest.evidence_count for digest in digests] == [25, 25, 25, 25]


async def test_delegate_runs_concurrently() -> None:
    client = FakeLLMClient(delay_seconds=0.05)
    delegator = EvidenceDelegator(client=client, slice_size=10, max_workers=4)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 41)], "query")

    assert len(digests) == 4
    assert client.max_concurrent_calls >= 2


async def test_delegate_partial_failure_returns_successful() -> None:
    client = FakeLLMClient(fail_on_prompt_substrings={"https://example.com/11"})
    delegator = EvidenceDelegator(client=client, slice_size=10, max_workers=4)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 31)], "query")

    assert len(digests) == 2
    assert [digest.evidence_count for digest in digests] == [10, 10]
    assert [digest.source_urls[0] for digest in digests] == [
        "https://example.com/1",
        "https://example.com/21",
    ]


async def test_delegate_preserves_source_url_across_digests() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=10, max_workers=4)
    evidence = [make_evidence(index) for index in range(1, 26)]

    digests = await delegator.delegate(evidence, "query")

    collected_urls = [url for digest in digests for url in digest.source_urls]
    assert collected_urls == [item.url for item in evidence]


async def test_delegate_persists_artifacts_when_store_set(tmp_path) -> None:
    client = FakeLLMClient()
    store = await SessionStore.open(tmp_path / "delegation.sqlite")

    try:
        await store.create_session("session-1", "query", "deep")
        delegator = EvidenceDelegator(
            client=client,
            slice_size=10,
            max_workers=4,
            store=store,
            session_id="session-1",
        )

        digests = await delegator.delegate(
            [make_evidence(index) for index in range(1, 41)], "query"
        )
        artifacts = await store.load_artifacts(
            session_id="session-1",
            kind="compacted_digest",
        )
    finally:
        await store.close()

    assert len(digests) == 4
    assert len(artifacts) == 4
    persisted = [
        EvidenceDigest.model_validate_json(artifact["payload_json"]) for artifact in artifacts
    ]
    assert persisted == digests


async def test_delegate_with_meta_single_slice_returns_none_meta() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=15)

    digests, meta_digest = await delegator.delegate_with_meta(
        [make_evidence(index) for index in range(1, 6)],
        "query",
    )

    assert len(digests) == 1
    assert meta_digest is None
    assert client.calls == 1


async def test_delegate_with_meta_multi_slice_returns_meta_digest() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=10, max_workers=4)

    digests, meta_digest = await delegator.delegate_with_meta(
        [make_evidence(index) for index in range(1, 41)],
        "query",
    )

    assert len(digests) == 4
    assert meta_digest is not None
    assert meta_digest.evidence_count == sum(digest.evidence_count for digest in digests)
    assert set(meta_digest.source_urls) == {
        item.url for item in [make_evidence(index) for index in range(1, 41)]
    }
    assert client.calls == 5


async def test_delegate_empty_query_still_works() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=10)

    digests = await delegator.delegate([make_evidence(index) for index in range(1, 11)], "")

    assert len(digests) == 1
    assert digests[0].evidence_count == 10


async def test_delegate_hot_set_size_zero_forces_full_compaction() -> None:
    client = FakeLLMClient()
    delegator = EvidenceDelegator(client=client, slice_size=15, token_budget_per_slice=6000)

    digests = await delegator.delegate([make_evidence(1)], "query")

    assert len(digests) == 1
    assert digests[0].evidence_count == 1
    assert client.calls == 1
