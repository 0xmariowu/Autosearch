"""Regression test for PruningCleaner over-prune fallback (F105 finding)."""

from __future__ import annotations

from autosearch.cleaners.pruning_cleaner import PruningCleaner


def test_over_prune_fallback_returns_minimally_cleaned_html() -> None:
    """When the heuristic scorer wipes most of the content (SPA-heavy sites),
    the cleaner must fall back to minimally-processed HTML rather than return
    empty. Simulates a dev.to-style layout where content sits in generic divs
    the tag-weight table cannot score positively.
    """
    cleaner = PruningCleaner()
    html = """<html><body>
        <div class="wrapper">
          <div class="col">
            <div>Paragraph one about BM25 ranking algorithm and how it works.</div>
            <div>Paragraph two with more specific details on term frequency saturation.</div>
            <div>Paragraph three about inverse document frequency weighting.</div>
            <div>Paragraph four about length normalization and the b parameter.</div>
          </div>
        </div>
    </body></html>"""

    cleaned = cleaner.clean(html)

    # Content should survive even though container divs have neutral tag weights.
    assert "BM25 ranking algorithm" in cleaned
    assert "length normalization" in cleaned


def test_normal_article_is_pruned_cleanly() -> None:
    """Baseline — articles with <article>/<main>/<nav>/<footer> must still have
    their negative parts removed by the primary path, not triggering fallback.
    """
    cleaner = PruningCleaner()
    html = """<html><body>
        <nav class="site-nav">Home About Contact</nav>
        <header>Site Header</header>
        <article>
          <p>BM25 is a ranking function used in information retrieval systems.</p>
          <p>It builds on TF-IDF with term frequency saturation and length normalization.</p>
        </article>
        <aside class="sidebar">Ads here</aside>
        <footer>Site Footer</footer>
    </body></html>"""

    cleaned = cleaner.clean(html)

    assert "BM25 is a ranking function" in cleaned
    assert "Site Header" not in cleaned
    assert "Home About Contact" not in cleaned
    assert "Ads here" not in cleaned
