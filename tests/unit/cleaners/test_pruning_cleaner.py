# Self-written, plan v2.3 § 13.5 F103
from bs4 import BeautifulSoup

from autosearch.cleaners.pruning_cleaner import PruningCleaner


def test_prunes_nav_footer_while_keeping_article() -> None:
    cleaner = PruningCleaner()
    html = """
    <html>
      <body>
        <nav>Home About Contact</nav>
        <article>
          <p>Real article content stays in place.</p>
          <p>It has enough words to be meaningful.</p>
          <p>The cleaner should keep this section.</p>
        </article>
        <footer>Copyright links and legal text</footer>
      </body>
    </html>
    """

    cleaned = cleaner.clean(html)

    assert "Real article content stays in place." in cleaned
    assert "Home About Contact" not in cleaned
    assert "Copyright links and legal text" not in cleaned


def test_prunes_sidebar_by_class_hint() -> None:
    cleaner = PruningCleaner()
    html = """
    <div class="sidebar">Promoted links and sponsored blocks</div>
    <div class="content">
      Useful content with enough words to remain visible.
    </div>
    """

    cleaned = cleaner.clean(html)

    assert "Promoted links and sponsored blocks" not in cleaned
    assert "Useful content with enough words to remain visible." in cleaned


def test_prunes_low_text_density_link_menu() -> None:
    cleaner = PruningCleaner()
    links = "".join(f"<li><a href='/{index}'>Menu item {index}</a></li>" for index in range(10))
    html = f"<ul>{links}</ul>"

    cleaned = cleaner.clean(html)

    assert "Menu item 0" not in cleaned
    assert cleaned == ""


def test_keeps_code_and_pre_blocks() -> None:
    cleaner = PruningCleaner()
    html = "<pre><code>def foo(): pass</code></pre>"

    cleaned = cleaner.clean(html)

    assert "<pre>" in cleaned
    assert "<code>" in cleaned
    assert "def foo(): pass" in cleaned


def test_threshold_adjustable() -> None:
    html = "<section><p>Useful content for readers with enough words to stay.</p></section>"

    low_threshold = PruningCleaner(threshold=0.1).clean(html)
    high_threshold = PruningCleaner(threshold=0.9).clean(html)

    assert "Useful content for readers with enough words to stay." in low_threshold
    assert high_threshold == ""


def test_empty_html_returns_empty() -> None:
    assert PruningCleaner().clean("") == ""


def test_min_word_count_filter() -> None:
    cleaner = PruningCleaner(min_word_count=3)
    html = """
    <div>
      <p>Hi</p>
      <p>This is a full sentence with meaningful content.</p>
    </div>
    """

    cleaned = cleaner.clean(html)

    assert "Hi" not in cleaned
    assert "This is a full sentence with meaningful content." in cleaned


def test_preserves_html_structure_not_plain_text() -> None:
    cleaner = PruningCleaner()
    html = "<article><p>Structured content remains in HTML form.</p></article>"

    cleaned = cleaner.clean(html)
    soup = BeautifulSoup(cleaned, "html.parser")

    assert "<" in cleaned
    assert ">" in cleaned
    assert soup.find("article") is not None
