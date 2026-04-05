from __future__ import annotations

from unittest.mock import MagicMock, patch

from lib.content_processing import (
    chunk_with_overlap,
    convert_to_citations,
    filter_relevant_paragraphs,
    is_blocked,
    prune_html,
)


def test_filter_relevant_paragraphs_keeps_relevant() -> None:
    markdown = (
        "Solar battery storage improves grid resilience.\n\n"
        "Celebrity gossip and entertainment rumors.\n\n"
        "Renewable energy storage helps balance peak demand.\n\n"
        "Sports scores from last night's game.\n\n"
        "Battery systems make renewable power more reliable."
    )
    mock_bm25 = MagicMock()
    mock_bm25.get_scores.return_value = [2.4, 0.1, 1.8, 0.0, 1.2]

    with patch("lib.content_processing.BM25Okapi", return_value=mock_bm25):
        filtered = filter_relevant_paragraphs(markdown, "renewable energy storage")

    assert "Solar battery storage improves grid resilience." in filtered
    assert "Renewable energy storage helps balance peak demand." in filtered
    assert "Battery systems make renewable power more reliable." in filtered
    assert "Celebrity gossip and entertainment rumors." not in filtered
    assert "Sports scores from last night's game." not in filtered


def test_filter_relevant_paragraphs_minimum_3() -> None:
    markdown = (
        "First paragraph.\n\n"
        "Second paragraph.\n\n"
        "Third paragraph.\n\n"
        "Fourth paragraph."
    )
    mock_bm25 = MagicMock()
    mock_bm25.get_scores.return_value = [0.2, 0.1, 0.05, 0.01]

    with patch("lib.content_processing.BM25Okapi", return_value=mock_bm25):
        filtered = filter_relevant_paragraphs(markdown, "unmatched query", threshold=10.0)

    assert filtered == "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."


def test_filter_relevant_paragraphs_empty_input() -> None:
    assert filter_relevant_paragraphs("", "topic") == ""


def test_filter_relevant_paragraphs_heading_weight() -> None:
    heading_markdown = (
        "# Async Python\n\n"
        "Plain paragraph.\n\n"
        "Irrelevant paragraph one.\n\n"
        "Irrelevant paragraph two.\n\n"
        "Irrelevant paragraph three.\n\n"
        "Irrelevant paragraph four."
    )
    plain_markdown = heading_markdown.replace("# Async Python", "Async Python")
    mock_bm25 = MagicMock()
    mock_bm25.get_scores.return_value = [0.3, 1.0, 1.4, 1.3, 1.2, 1.1]

    with patch("lib.content_processing.BM25Okapi", return_value=mock_bm25):
        heading_filtered = filter_relevant_paragraphs(
            heading_markdown, "python async tutorial", threshold=10.0
        )

    with patch("lib.content_processing.BM25Okapi", return_value=mock_bm25):
        plain_filtered = filter_relevant_paragraphs(
            plain_markdown, "python async tutorial", threshold=10.0
        )

    assert "# Async Python" in heading_filtered
    assert "Async Python" not in plain_filtered


def test_prune_html_removes_nav_footer() -> None:
    html = (
        "<html><body>"
        "<nav>Navigation links</nav>"
        "<article><h1>Keep me</h1><p>Main body text here.</p></article>"
        "<footer>Footer links</footer>"
        "</body></html>"
    )

    pruned = prune_html(html)

    assert "Keep me" in pruned
    assert "Main body text here." in pruned
    assert "Navigation links" not in pruned
    assert "Footer links" not in pruned


def test_prune_html_empty_input() -> None:
    assert prune_html("") == ""


def test_chunk_with_overlap_short_text() -> None:
    assert chunk_with_overlap("short text", window_size=10, step=8) == ["short text"]


def test_chunk_with_overlap_splits() -> None:
    text = " ".join(f"w{i}" for i in range(9))

    chunks = chunk_with_overlap(text, window_size=4, step=3)

    assert chunks == ["w0 w1 w2 w3", "w3 w4 w5 w6", "w5 w6 w7 w8"]


def test_chunk_with_overlap_last_chunk() -> None:
    text = " ".join(f"w{i}" for i in range(10))

    chunks = chunk_with_overlap(text, window_size=4, step=4)

    assert chunks == ["w0 w1 w2 w3", "w4 w5 w6 w7", "w6 w7 w8 w9"]


def test_convert_to_citations() -> None:
    converted, references = convert_to_citations(
        "See [Example](https://example.com/resource) for details."
    )

    assert converted == "See Example⟨1⟩ for details."
    assert "## References" in references
    assert "⟨1⟩ https://example.com/resource: Example" in references


def test_convert_to_citations_dedup() -> None:
    converted, references = convert_to_citations(
        "See [One](https://example.com) and [Two](https://example.com)."
    )

    assert converted == "See One⟨1⟩ and Two⟨1⟩."
    assert references.count("https://example.com") == 1


def test_is_blocked_cloudflare() -> None:
    html = (
        "<html><body>"
        '<form id="challenge-form" action="/__cf_chl_f_tk=token">'
        "Checking your browser"
        "</form>"
        "</body></html>"
    )

    blocked, reason = is_blocked(200, html)

    assert blocked is True
    assert "Cloudflare" in reason


def test_is_blocked_normal_page() -> None:
    html = (
        "<html><body><article>"
        "<h1>Normal page</h1>"
        "<p>This page has enough visible article text to avoid being treated as a "
        "shell or challenge page during the structural integrity checks.</p>"
        "<p>It also includes multiple content elements so the block detector sees "
        "a normal page rather than an anti-bot response.</p>"
        "</article></body></html>"
    )

    blocked, reason = is_blocked(200, html)

    assert blocked is False
    assert reason == ""


def test_is_blocked_429() -> None:
    blocked, reason = is_blocked(429, "<html><body>Rate limited</body></html>")

    assert blocked is True
    assert reason == "HTTP 429 Too Many Requests"


def test_is_blocked_empty_200() -> None:
    blocked, reason = is_blocked(200, "<html><body></body></html>")

    assert blocked is True
    assert "Near-empty content" in reason
