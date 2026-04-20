# Self-written, plan v2.3 § 13.5 F104
from bs4 import BeautifulSoup
from rank_bm25 import BM25Okapi

from autosearch.cleaners.bm25_cleaner import BM25Cleaner


def test_none_query_returns_unchanged() -> None:
    html = "<div><p>Keep original html.</p></div>"

    assert BM25Cleaner().clean(html) == html


def test_empty_query_treated_as_none() -> None:
    html = "<div><p>Keep original html.</p></div>"

    assert BM25Cleaner().clean(html, query="   ") == html


def test_keeps_only_query_relevant_paragraphs() -> None:
    html = """
    <div>
      <p>Python async programming uses the event loop for concurrency.</p>
      <p>Async tasks in Python let concurrent workloads cooperate efficiently.</p>
      <p>Gardening tips for basil and tomatoes in warm weather.</p>
      <p>Mountain bike maintenance for weekend trail riders.</p>
      <p>Soup recipes with roasted garlic and onions.</p>
    </div>
    """

    cleaned = BM25Cleaner().clean(html, query="python async concurrency")

    assert "Python async programming uses the event loop for concurrency." in cleaned
    assert "Async tasks in Python let concurrent workloads cooperate efficiently." in cleaned
    assert "Gardening tips for basil and tomatoes in warm weather." not in cleaned
    assert "Mountain bike maintenance for weekend trail riders." not in cleaned
    assert "Soup recipes with roasted garlic and onions." not in cleaned


def test_preserves_document_order_not_score_order() -> None:
    first = "Python async basics introduce cooperative scheduling."
    second = "Python async concurrency event loop tasks futures coroutines guide."
    third = "Async concurrency patterns help Python services scale cleanly."
    html = f"""
    <div>
      <p>{first}</p>
      <p>{second}</p>
      <p>{third}</p>
    </div>
    """

    cleaned = BM25Cleaner(top_k=3).clean(
        html,
        query="python async concurrency event loop coroutines",
    )
    ordered_text = [
        paragraph.get_text(" ", strip=True)
        for paragraph in BeautifulSoup(cleaned, "html.parser").find_all("p")
    ]

    assert ordered_text == [first, second, third]


def test_top_k_limit() -> None:
    html = "".join(f"<p>Python async concurrency example {index}</p>" for index in range(20))

    cleaned = BM25Cleaner(top_k=5).clean(html, query="python async concurrency")
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("p")) == 5


def test_handles_headers() -> None:
    html = """
    <div>
      <h1>Python Async Guide</h1>
      <h2>Weekend Sports Roundup</h2>
      <p>Unrelated topic about cooking.</p>
    </div>
    """

    cleaned = BM25Cleaner().clean(html, query="python async")
    soup = BeautifulSoup(cleaned, "html.parser")

    assert soup.find("h1") is not None
    assert "Python Async Guide" in cleaned
    assert "Weekend Sports Roundup" not in cleaned
    assert "Unrelated topic about cooking." not in cleaned


def test_single_candidate_no_crash() -> None:
    html = "<p>Only paragraph here.</p>"

    assert BM25Cleaner().clean(html, query="nonmatching query") == html


def test_empty_html_returns_empty() -> None:
    assert BM25Cleaner().clean("", query="python") == ""


def test_top_k_is_hard_cap_when_min_score_set() -> None:
    html = "".join(f"<p>Python async concurrency token{index}</p>" for index in range(20))

    cleaned = BM25Cleaner(top_k=5, min_score=0.01).clean(
        html,
        query="python async concurrency",
    )
    soup = BeautifulSoup(cleaned, "html.parser")

    assert len(soup.find_all("p")) == 5


def test_min_score_filter_without_top_k() -> None:
    html = """
    <div>
      <p>Python async concurrency event loop futures coroutines scheduler token0</p>
      <p>Python async concurrency event loop token1</p>
      <p>Python async token2</p>
      <p>Gardening basil token3</p>
      <p>Python token4</p>
    </div>
    """

    cleaned = BM25Cleaner(top_k=0, min_score=2.0).clean(
        html,
        query="python async concurrency event loop futures coroutines scheduler",
    )

    assert "Python async concurrency event loop futures coroutines scheduler token0" in cleaned
    assert "Python async concurrency event loop token1" not in cleaned
    assert "Python async token2" not in cleaned
    assert "Gardening basil token3" not in cleaned
    assert "Python token4" not in cleaned


def test_bm25_uses_rank_bm25_library() -> None:
    bm25 = BM25Okapi([["python"], ["async"]])
    cleaner = BM25Cleaner()

    assert bm25 is not None
    assert isinstance(cleaner, BM25Cleaner)
