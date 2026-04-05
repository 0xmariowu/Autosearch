from lib.convergence import _jaccard, _tokenize, cross_source_link


def _make_result(title, source):
    return {
        "url": f"https://example.com/{source}/{title.replace(' ', '-')}",
        "title": title,
        "snippet": "",
        "source": source,
        "metadata": {},
    }


def test_cross_source_link_different_sources():
    results = [
        _make_result("OpenAI launches AI agents platform", "reddit"),
        _make_result("OpenAI launches new AI agents platform", "twitter"),
    ]

    cross_source_link(results)

    assert results[0]["metadata"]["also_on"] == ["twitter"]
    assert results[1]["metadata"]["also_on"] == ["reddit"]


def test_cross_source_link_same_source_skipped():
    results = [
        _make_result("OpenAI launches AI agents platform", "reddit"),
        _make_result("OpenAI launches new AI agents platform", "reddit"),
    ]

    cross_source_link(results)

    assert "also_on" not in results[0]["metadata"]
    assert "also_on" not in results[1]["metadata"]


def test_cross_source_link_below_threshold():
    results = [
        _make_result("OpenAI launches AI agents platform", "reddit"),
        _make_result("Best sourdough bread recipe", "twitter"),
    ]

    cross_source_link(results)

    assert "also_on" not in results[0]["metadata"]
    assert "also_on" not in results[1]["metadata"]


def test_cross_source_link_empty_input():
    results = []

    cross_source_link(results)

    assert results == []


def test_jaccard_identical():
    tokens = _tokenize("OpenAI launches AI agents platform")

    assert _jaccard(tokens, tokens) == 1.0


def test_jaccard_disjoint():
    tokens_a = _tokenize("OpenAI launches AI agents platform")
    tokens_b = _tokenize("Best sourdough bread recipe")

    assert _jaccard(tokens_a, tokens_b) == 0.0


def test_also_on_sorted_and_deduped():
    results = [
        _make_result("OpenAI launches AI agents platform", "reddit"),
        _make_result("OpenAI launches new AI agents platform", "youtube"),
        _make_result("OpenAI launches AI agents platform today", "twitter"),
        _make_result("OpenAI launches AI agents platform update", "twitter"),
    ]

    cross_source_link(results)

    assert results[0]["metadata"]["also_on"] == ["twitter", "youtube"]
