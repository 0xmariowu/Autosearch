# Self-written for F102
import pytest

from autosearch.lib.html_scraper import HtmlFetchError, fetch_page


def stub_fetch_html(
    monkeypatch: pytest.MonkeyPatch,
    *,
    html: str | None = None,
    error: Exception | None = None,
) -> None:
    async def fake_fetch_html(*args, **kwargs) -> str:
        if error is not None:
            raise error
        return html or ""

    monkeypatch.setattr("autosearch.lib.html_scraper.fetch_html", fake_fetch_html)


@pytest.mark.asyncio
async def test_fetch_page_basic_html(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <html>
          <head><title>Example Page</title></head>
          <body>
            <article>
              <p>Meaningful body content stays visible.</p>
              <a href="/about">About</a>
            </article>
          </body>
        </html>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert page.url == "https://example.com/page"
    assert page.status_code == 200
    assert page.markdown
    assert len(page.links) == 1
    assert page.metadata["title"] == "Example Page"


@pytest.mark.asyncio
async def test_fetch_page_extracts_og_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <html>
          <head>
            <meta property="og:title" content="OG Title" />
            <meta property="og:description" content="OG Description" />
            <meta name="twitter:description" content="Tweet Description" />
          </head>
        </html>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert page.metadata["og:title"] == "OG Title"
    assert page.metadata["og:description"] == "OG Description"
    assert page.metadata["twitter:description"] == "Tweet Description"


@pytest.mark.asyncio
async def test_fetch_page_classifies_internal_vs_external_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <article>
          <a href="https://example.com/about">About</a>
          <a href="https://external.example.org/post">Source</a>
        </article>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert [link.internal for link in page.links] == [True, False]


@pytest.mark.asyncio
async def test_fetch_page_skips_anchor_javascript_mailto_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <article>
          <a href="#top">Top</a>
          <a href="javascript:alert('x')">JS</a>
          <a href="mailto:test@example.com">Mail</a>
          <a href="/keep">Keep</a>
        </article>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert [link.href for link in page.links] == ["https://example.com/keep"]


@pytest.mark.asyncio
async def test_fetch_page_extracts_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <table>
          <tr><th>A</th><th>B</th></tr>
          <tr><td>1</td><td>2</td></tr>
        </table>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert page.tables[0].headers == ["A", "B"]
    assert page.tables[0].rows[0] == {"A": "1", "B": "2"}


@pytest.mark.asyncio
async def test_fetch_page_collects_images_and_videos(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <article>
          <img src="/one.png" alt="One" />
          <img src="https://cdn.example.com/two.png" alt="Two" />
          <video src="/demo.mp4"></video>
        </article>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert len(page.media) == 3
    assert [item.kind for item in page.media] == ["image", "image", "video"]


@pytest.mark.asyncio
async def test_fetch_page_markdown_contains_heading_and_paragraph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <article>
          <h1>Page Title</h1>
          <p>Body paragraph.</p>
        </article>
        """,
    )

    page = await fetch_page("https://example.com/page", run_prune=False)

    assert "# Page Title" in page.markdown
    assert "Body paragraph." in page.markdown


@pytest.mark.asyncio
async def test_fetch_page_prune_removes_nav_footer_from_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <html>
          <body>
            <nav>menu links</nav>
            <article>
              <p>real content here in article for readers</p>
            </article>
            <footer>foot links</footer>
          </body>
        </html>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert "menu links" not in page.markdown
    assert "foot links" not in page.markdown
    assert "real content here in article for readers" in page.markdown


@pytest.mark.asyncio
async def test_fetch_page_with_run_prune_false_keeps_nav(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <html>
          <body>
            <nav>menu links</nav>
            <article>
              <p>real content here in article for readers</p>
            </article>
            <footer>foot links</footer>
          </body>
        </html>
        """,
    )

    page = await fetch_page("https://example.com/page", run_prune=False)

    assert "menu links" in page.markdown


@pytest.mark.asyncio
async def test_fetch_page_relative_urls_absolutized(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(
        monkeypatch,
        html="""
        <article>
          <a href="/about">About</a>
        </article>
        """,
    )

    page = await fetch_page("https://example.com/page")

    assert page.links[0].href == "https://example.com/about"


@pytest.mark.asyncio
async def test_fetch_page_empty_html_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_fetch_html(monkeypatch, html="")

    page = await fetch_page("https://example.com/page")

    assert page.markdown == ""
    assert page.links == []
    assert page.metadata == {}


@pytest.mark.asyncio
async def test_fetch_page_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    error = HtmlFetchError("https://example.com/page", status_code=502, reason="http_error")
    stub_fetch_html(monkeypatch, error=error)

    with pytest.raises(HtmlFetchError) as exc_info:
        await fetch_page("https://example.com/page")

    assert exc_info.value is error
