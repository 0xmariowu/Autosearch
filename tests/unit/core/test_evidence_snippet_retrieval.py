# Self-written, plan v2.3 § 13.5
from datetime import datetime

from autosearch.core.evidence import (
    EvidenceProcessor,
    retrieve_for_section,
    split_all_evidence,
    split_into_snippets,
)
from autosearch.core.models import Evidence, EvidenceSnippet

NOW = datetime(2026, 4, 20, 12, 0, 0)


def make_evidence(
    url: str = "https://example.com/source",
    title: str = "Example source",
    *,
    snippet: str | None = None,
    content: str | None = None,
) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel="web",
        fetched_at=NOW,
    )


def make_snippet(
    evidence_id: str,
    text: str,
    offset: int = 0,
    source_url: str = "https://example.com/source",
    source_title: str = "Example source",
) -> EvidenceSnippet:
    return EvidenceSnippet(
        evidence_id=evidence_id,
        text=text,
        offset=offset,
        source_url=source_url,
        source_title=source_title,
    )


def _words(count: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


def test_split_into_snippets_short_text_one_chunk() -> None:
    text = _words(50)
    evidence = make_evidence(content=text)

    snippets = split_into_snippets(evidence)

    assert len(snippets) == 1
    assert snippets[0].text == text
    assert snippets[0].offset == 0


def test_split_into_snippets_long_text_multiple_chunks() -> None:
    evidence = make_evidence(content=_words(600))

    snippets = split_into_snippets(evidence, window_tokens=200, overlap_tokens=40)

    assert 3 <= len(snippets) <= 5
    assert [snippet.offset for snippet in snippets] == sorted(
        snippet.offset for snippet in snippets
    )


def test_split_into_snippets_offsets_strictly_increasing() -> None:
    evidence = make_evidence(content=_words(600))

    snippets = split_into_snippets(evidence, window_tokens=200, overlap_tokens=40)

    assert all(
        left.offset < right.offset for left, right in zip(snippets, snippets[1:], strict=False)
    )


def test_split_into_snippets_cjk_character_based() -> None:
    evidence = make_evidence(content="中" * 500)

    snippets = split_into_snippets(evidence, window_tokens=200, overlap_tokens=40)

    assert len(snippets) >= 3
    assert all(len(snippet.text) <= 200 for snippet in snippets)
    assert snippets[0].offset == 0
    assert snippets[1].offset > snippets[0].offset


def test_split_into_snippets_empty_content_returns_empty() -> None:
    evidence = make_evidence(content="", snippet="")

    assert split_into_snippets(evidence) == []


def test_split_into_snippets_uses_snippet_when_content_empty() -> None:
    fallback = _words(20, prefix="fallback")
    evidence = make_evidence(content="", snippet=fallback)

    snippets = split_into_snippets(evidence)

    assert len(snippets) == 1
    assert snippets[0].text == fallback


def test_split_into_snippets_preserves_source_url_and_title() -> None:
    evidence = make_evidence(
        url="https://example.com/preserved",
        title="Preserved title",
        content=_words(300),
    )

    snippets = split_into_snippets(evidence, window_tokens=200, overlap_tokens=40)

    assert snippets
    assert all(snippet.source_url == evidence.url for snippet in snippets)
    assert all(snippet.source_title == evidence.title for snippet in snippets)


def test_split_into_snippets_missing_url_generates_stable_id() -> None:
    evidence = make_evidence(url="", title="Stable id", content=_words(30))

    first = split_into_snippets(evidence)
    second = split_into_snippets(evidence)

    assert len(first) == 1
    assert first[0].evidence_id
    assert first[0].evidence_id == second[0].evidence_id


def test_retrieve_for_section_returns_top_k() -> None:
    snippets = [
        make_snippet(f"snippet-{index}", f"python async guide {index}", offset=index)
        for index in range(10)
    ]

    ranked = retrieve_for_section("python async", snippets, top_k=3)

    assert len(ranked) == 3


def test_retrieve_for_section_empty_query_returns_empty() -> None:
    snippets = [make_snippet("snippet-1", "python async guide")]

    assert retrieve_for_section("   ", snippets) == []


def test_retrieve_for_section_empty_snippets_returns_empty() -> None:
    assert retrieve_for_section("python async", []) == []


def test_retrieve_for_section_score_order() -> None:
    snippets = [
        make_snippet("a", "python async await event loop coroutine", offset=0),
        make_snippet("b", "database transactions and indexing", offset=1),
        make_snippet("c", "frontend css layout animation", offset=2),
        make_snippet("d", "python packaging guide", offset=3),
        make_snippet("e", "message queues and workers", offset=4),
    ]

    ranked = retrieve_for_section("python async", snippets, top_k=5)

    assert ranked[0].evidence_id == "a"


def test_retrieve_for_section_single_snippet_no_crash() -> None:
    snippet = make_snippet("only", "python async guide")

    assert retrieve_for_section("python async", [snippet]) == [snippet]


def test_retrieve_for_section_cjk_query() -> None:
    snippets = [
        make_snippet("async", "Python异步编程使用协程和事件循环"),
        make_snippet("db", "数据库索引优化和事务隔离"),
        make_snippet("ui", "前端布局与动画设计"),
    ]

    ranked = retrieve_for_section("异步编程协程", snippets, top_k=3)

    assert ranked[0].evidence_id == "async"


def test_retrieve_for_section_top_k_zero_returns_all() -> None:
    snippets = [
        make_snippet("a", "python async guide", offset=0),
        make_snippet("b", "database indexing guide", offset=1),
        make_snippet("c", "css animation guide", offset=2),
    ]

    ranked = retrieve_for_section("guide", snippets, top_k=0)

    assert len(ranked) == len(snippets)


def test_split_all_evidence_flattens() -> None:
    evidences = [
        make_evidence(
            url=f"https://example.com/{index}",
            title=f"Evidence {index}",
            content=_words(250, prefix=f"e{index}"),
        )
        for index in range(3)
    ]

    snippets = split_all_evidence(evidences, window_tokens=200, overlap_tokens=0)

    assert len(snippets) == 6


def test_evidence_processor_methods_delegate() -> None:
    processor = EvidenceProcessor()
    evidence = make_evidence(content=_words(300))
    module_snippets = split_into_snippets(evidence, window_tokens=200, overlap_tokens=40)
    method_snippets = processor.split_into_snippets(
        evidence,
        window_tokens=200,
        overlap_tokens=40,
    )

    assert method_snippets == module_snippets
    assert processor.retrieve_for_section("word1 word2", module_snippets, top_k=2) == (
        retrieve_for_section("word1 word2", module_snippets, top_k=2)
    )
