# Self-written, plan v2.3 § 13.5
import re
from datetime import UTC, datetime

from autosearch.core import context_compaction as context_compaction_module
from autosearch.core.context_compaction import ContextCompactor
from autosearch.core.models import Evidence, EvidenceDigest, FetchedPage
from autosearch.persistence.session_store import SessionStore

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


class FakeLLMClient:
    def __init__(self, result: EvidenceDigest | Exception) -> None:
        self.result = result
        self.calls = 0
        self.prompts: list[str] = []

    async def complete(self, prompt: str, response_model: type[EvidenceDigest]) -> EvidenceDigest:
        self.calls += 1
        self.prompts.append(prompt)
        _ = response_model
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class RecordingLogger:
    def __init__(self) -> None:
        self.warning_calls: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kwargs: object) -> None:
        _ = (event, kwargs)

    def info(self, event: str, **kwargs: object) -> None:
        _ = (event, kwargs)

    def warning(self, event: str, **kwargs: object) -> None:
        self.warning_calls.append((event, kwargs))


class ExplodingStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def store_artifact(
        self,
        *,
        session_id: str,
        kind: str,
        payload: object,
    ) -> int:
        _ = payload
        self.calls.append((session_id, kind))
        raise RuntimeError("artifact write failed")


def make_digest() -> EvidenceDigest:
    return EvidenceDigest(
        topic="Cold evidence digest",
        key_findings=[
            "Finding one",
            "Finding two",
            "Finding three",
            "Finding four",
            "Finding five",
        ],
        source_urls=["https://placeholder.example/digest"],
        evidence_count=1,
        compressed_at=NOW,
        token_count_before=1,
        token_count_after=1,
    )


def make_evidence(
    index: int,
    *,
    tokens: int,
    with_source_page: bool = False,
    content: str | None = None,
) -> Evidence:
    page = None
    if with_source_page:
        page = FetchedPage(
            url=f"https://example.com/{index}",
            status_code=200,
            fetched_at=NOW,
            html="<html>" + ("H" * 5000) + "</html>",
            cleaned_html="<article>" + ("C" * 5000) + "</article>",
            markdown="# Page\n\n" + ("M" * 5000),
        )
    return Evidence(
        url=f"https://example.com/{index}",
        title=f"Evidence {index}",
        snippet=f"Snippet {index}",
        content=content or f"[TOKENS={tokens}] Content {index}",
        source_channel="test",
        fetched_at=NOW,
        source_page=page,
    )


def fake_estimate_tokens(text: str) -> int:
    marker = re.search(r"\[TOKENS=(\d+)\]", text)
    if marker is not None:
        return int(marker.group(1))
    return max(len(text.split()), 1) if text else 0


async def test_no_compaction_when_under_budget(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [
        make_evidence(1, tokens=150),
        make_evidence(2, tokens=175),
        make_evidence(3, tokens=175),
    ]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=16000, client=client)

    hot, digest = await compactor.compact(evidence, "budget test")

    assert hot == evidence
    assert digest is None
    assert client.calls == 0


async def test_compaction_triggered_when_over_threshold(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 21)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=16000, client=client)

    hot, digest = await compactor.compact(evidence, "over threshold")

    assert hot == evidence[10:]
    assert digest is not None
    assert digest.evidence_count == 10
    assert client.calls == 1


async def test_hot_set_preserves_chronological_order(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=900) for index in range(1, 16)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=10000, hot_set_size=4, client=client)

    hot, _ = await compactor.compact(evidence, "order test")

    assert [item.url for item in hot] == [item.url for item in evidence[-4:]]


async def test_skip_compaction_when_evidence_count_less_than_hot_set(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=3000) for index in range(1, 6)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=10000, hot_set_size=10, client=client)

    hot, digest = await compactor.compact(evidence, "small evidence list")

    assert hot == evidence
    assert digest is None
    assert client.calls == 0


def test_does_not_include_source_page_in_token_count(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    compactor = ContextCompactor()
    plain = make_evidence(1, tokens=250)
    with_page = make_evidence(1, tokens=250, with_source_page=True)

    assert compactor._count_tokens(plain) == compactor._count_tokens(with_page)


async def test_does_not_include_source_page_in_summarize_prompt(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    visible_content = "Important visible content"
    evidence = [
        make_evidence(1, tokens=800, with_source_page=True, content=visible_content),
        make_evidence(2, tokens=800),
        make_evidence(3, tokens=800),
    ]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=1000, hot_set_size=1, client=client)

    _, digest = await compactor.compact(evidence, "prompt test")

    assert digest is not None
    assert client.calls == 1
    assert visible_content in client.prompts[0]
    assert evidence[0].source_page is not None
    assert evidence[0].source_page.html not in client.prompts[0]


async def test_llm_error_fallback_returns_original(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1500) for index in range(1, 12)]
    client = FakeLLMClient(RuntimeError("llm unavailable"))
    compactor = ContextCompactor(token_budget=10000, client=client)
    logger = RecordingLogger()
    monkeypatch.setattr(compactor, "logger", logger)

    hot, digest = await compactor.compact(evidence, "llm error")

    assert hot == evidence
    assert digest is None
    assert logger.warning_calls == [
        (
            "compaction_skipped_llm_error",
            {"error": "llm unavailable"},
        )
    ]


async def test_digest_captures_source_urls(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=10000, hot_set_size=2, client=client)

    _, digest = await compactor.compact(evidence, "urls test")

    assert digest is not None
    assert digest.source_urls == [item.url for item in evidence[:-2]]


async def test_token_count_before_after_recorded(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=10000, hot_set_size=2, client=client)

    _, digest = await compactor.compact(evidence, "token accounting")

    assert digest is not None
    expected_before = sum(compactor._count_tokens(item) for item in evidence[:-2])
    expected_after = fake_estimate_tokens(compactor._render_digest_for_count(digest))
    assert digest.token_count_before == expected_before
    assert digest.token_count_after == expected_after


async def test_empty_evidence_list_no_op(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(client=client)

    hot, digest = await compactor.compact([], "empty")

    assert hot == []
    assert digest is None
    assert client.calls == 0


async def test_hot_set_size_zero_compacts_everything(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1200) for index in range(1, 6)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=1000, hot_set_size=0, client=client)

    hot, digest = await compactor.compact(evidence, "compact everything")

    assert hot == []
    assert digest is not None
    assert digest.evidence_count == len(evidence)


async def test_compaction_persists_digest_when_store_and_session_id_set(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    store = await SessionStore.open(tmp_path / "context-compaction.sqlite")

    try:
        await store.create_session("session-1", "persist digest", "deep")
        compactor = ContextCompactor(
            token_budget=10000,
            hot_set_size=2,
            client=client,
            store=store,
            session_id="session-1",
        )

        _, digest = await compactor.compact(evidence, "persist digest")
        persisted = await store.load_digests(session_id="session-1")
    finally:
        await store.close()

    assert digest is not None
    assert persisted == [digest]


async def test_compaction_persists_evicted_evidence(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    store = await SessionStore.open(tmp_path / "evicted-evidence.sqlite")

    try:
        await store.create_session("session-1", "persist evicted evidence", "deep")
        compactor = ContextCompactor(
            token_budget=10000,
            hot_set_size=2,
            client=client,
            store=store,
            session_id="session-1",
        )

        await compactor.compact(evidence, "persist evicted evidence")
        artifacts = await store.load_artifacts(
            session_id="session-1",
            kind="evicted_evidence",
        )
    finally:
        await store.close()

    assert len(artifacts) == len(evidence[:-2])
    restored = [Evidence.model_validate_json(artifact["payload_json"]) for artifact in artifacts]
    assert restored == evidence[:-2]


async def test_compaction_without_store_no_persistence(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    compactor = ContextCompactor(token_budget=10000, hot_set_size=2, client=client)

    hot, digest = await compactor.compact(evidence, "no store")

    assert hot == evidence[-2:]
    assert digest is not None
    assert client.calls == 1


async def test_compaction_store_error_is_best_effort(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    evidence = [make_evidence(index, tokens=1000) for index in range(1, 13)]
    client = FakeLLMClient(make_digest())
    store = ExplodingStore()
    compactor = ContextCompactor(
        token_budget=10000,
        hot_set_size=2,
        client=client,
        store=store,
        session_id="session-1",
    )
    logger = RecordingLogger()
    monkeypatch.setattr(compactor, "logger", logger)

    hot, digest = await compactor.compact(evidence, "store error")

    assert hot == evidence[-2:]
    assert digest is not None
    assert store.calls == [("session-1", "evicted_evidence")] * 10 + [
        ("session-1", "compacted_digest")
    ]
    assert logger.warning_calls == [
        (
            "compaction_artifact_store_failed",
            {"kind": "evicted_evidence", "error": "artifact write failed"},
        )
    ] * 10 + [
        (
            "compaction_artifact_store_failed",
            {"kind": "compacted_digest", "error": "artifact write failed"},
        )
    ]
