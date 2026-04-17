# Self-written, plan v2.3 § 13.5
import pytest

from autosearch.cleaners.trafilatura_cleaner import TrafilaturaCleaner


@pytest.fixture
def cleaner() -> TrafilaturaCleaner:
    return TrafilaturaCleaner()


@pytest.fixture
def long_article_html() -> str:
    body = "Useful body text for extraction. " * 12
    return f"""
    <html>
      <body>
        <article>
          <h1>Long article</h1>
          <p>{body}</p>
        </article>
      </body>
    </html>
    """


@pytest.fixture
def no_body_html() -> str:
    return """
    <html>
      <head>
        <title>Head only</title>
      </head>
    </html>
    """


@pytest.fixture
def short_article_html() -> str:
    return """
    <html>
      <body>
        <p>Short snippet.</p>
      </body>
    </html>
    """


def test_clean_returns_text_when_article_is_long_enough(
    cleaner: TrafilaturaCleaner,
    long_article_html: str,
) -> None:
    cleaned = cleaner.clean(long_article_html, min_chars=200)

    assert cleaned is not None
    assert len(cleaned) >= 200
    assert "Long article" in cleaned
    assert "Useful body text for extraction." in cleaned


def test_clean_returns_none_when_html_has_no_body(
    cleaner: TrafilaturaCleaner,
    no_body_html: str,
) -> None:
    assert cleaner.clean(no_body_html, min_chars=10) is None


def test_clean_returns_none_when_text_is_shorter_than_min_chars(
    cleaner: TrafilaturaCleaner,
    short_article_html: str,
) -> None:
    assert cleaner.clean(short_article_html, min_chars=50) is None
