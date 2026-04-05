from lib.search_runner import (
    dedup_results,
    extract_date,
    make_result,
    normalize_url,
)


def test_normalize_url_strips_tracking():
    url = (
        "https://example.com/path?"
        "utm_source=newsletter&utm_medium=email&fbclid=abc123&q=search"
    )
    assert normalize_url(url) == "https://example.com/path?q=search"


def test_normalize_url_preserves_non_tracking():
    url = "https://example.com/search?q=search&page=2"
    assert normalize_url(url) == "https://example.com/search?q=search&page=2"


def test_normalize_url_github_tree_strip():
    url = "https://github.com/user/repo/tree/main"
    assert normalize_url(url) == "https://github.com/user/repo"


def test_normalize_url_github_blob_master():
    url = "https://github.com/user/repo/blob/master"
    assert normalize_url(url) == "https://github.com/user/repo"


def test_normalize_url_trailing_slash():
    url = "https://example.com/path/"
    assert normalize_url(url) == "https://example.com/path"


def test_normalize_url_lowercases_netloc():
    url = "https://GITHUB.COM/user/repo"
    assert normalize_url(url) == "https://github.com/user/repo"


def test_normalize_url_invalid():
    assert normalize_url("not a url") == "not a url"


def test_extract_date_iso():
    assert extract_date("Released 2025-03-15 today") == "2025-03-15T00:00:00Z"


def test_extract_date_url_path():
    assert (
        extract_date("article", url="https://example.com/2025/03/15/article")
        == "2025-03-15T00:00:00Z"
    )


def test_extract_date_month_name():
    assert extract_date("Published Mar 15, 2025") == "2025-03-01T00:00:00Z"


def test_extract_date_year_in_parens():
    assert extract_date("Some title (2025)") == "2025-01-01T00:00:00Z"


def test_extract_date_none():
    assert extract_date("no date here") is None


def test_make_result_basic():
    result = make_result(
        url="https://example.com/path/",
        title="  Example Title  ",
        snippet="  Example snippet  ",
        source="web",
        query="example query",
    )

    assert result == {
        "url": "https://example.com/path",
        "title": "Example Title",
        "snippet": "Example snippet",
        "source": "web",
        "query": "example query",
        "metadata": {},
    }


def test_make_result_snippet_truncation():
    snippet = "a" * 2000
    result = make_result(
        url="https://example.com",
        title="Title",
        snippet=snippet,
        source="web",
        query="query",
    )

    assert len(result["snippet"]) == 1500
    assert result["snippet"] == "a" * 1500


def test_make_result_date_extraction():
    result = make_result(
        url="https://example.com/post",
        title="Title",
        snippet="Published 2025-06-01 in the article body",
        source="web",
        query="query",
    )

    assert result["metadata"]["published_at"] == "2025-06-01T00:00:00Z"


def test_make_result_extra_metadata():
    result = make_result(
        url="https://example.com/post",
        title="Title",
        snippet="Snippet",
        source="web",
        query="query",
        extra_metadata={"stars": 100},
    )

    assert result["metadata"] == {"stars": 100}


def test_dedup_results_same_url():
    results = [
        {
            "url": "https://example.com/post",
            "title": "First",
            "snippet": "One",
            "source": "web",
            "query": "query",
            "metadata": {},
        },
        {
            "url": "https://example.com/post",
            "title": "Second",
            "snippet": "Two",
            "source": "web",
            "query": "query",
            "metadata": {"published_at": "2025-01-01T00:00:00Z", "stars": 100},
        },
    ]

    deduped = dedup_results(results)

    assert len(deduped) == 1
    assert deduped[0] == results[1]


def test_dedup_results_empty_url():
    results = [
        {
            "url": "",
            "title": "Empty",
            "snippet": "Dropped",
            "source": "web",
            "query": "query",
            "metadata": {},
        },
        {
            "url": "https://example.com/post",
            "title": "Keep",
            "snippet": "Kept",
            "source": "web",
            "query": "query",
            "metadata": {},
        },
    ]

    deduped = dedup_results(results)

    assert deduped == [results[1]]


def test_dedup_results_normalized():
    results = [
        {
            "url": "https://example.com/post?utm_source=newsletter",
            "title": "First",
            "snippet": "One",
            "source": "web",
            "query": "query",
            "metadata": {},
        },
        {
            "url": "https://example.com/post",
            "title": "Second",
            "snippet": "Two",
            "source": "web",
            "query": "query",
            "metadata": {"stars": 100},
        },
    ]

    deduped = dedup_results(results)

    assert len(deduped) == 1
    assert deduped[0] == results[1]
