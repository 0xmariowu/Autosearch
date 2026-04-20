# Self-written for task F204
from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup
from markdownify import markdownify

from autosearch.cleaners.pruning_cleaner import PruningCleaner
from autosearch.core.models import FetchedPage, LinkRef, MediaRef, TableData

LOGGER = structlog.get_logger(__name__).bind(component="html_scraper")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 15.0


class HtmlFetchError(RuntimeError):
    """Sanitized fetch failure (status_code + url)."""

    def __init__(self, url: str, *, status_code: int | None = None, reason: str) -> None:
        self.url = url
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"html fetch failed: {reason} (url={url}, status={status_code})")


async def fetch_html(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch HTML with a browser-like UA; raise HtmlFetchError on non-2xx or transport error.

    Caller-provided http_client is used for injection in tests; otherwise a new AsyncClient is built.
    """
    final_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        final_headers.update(headers)

    async def _fetch(client: httpx.AsyncClient) -> str:
        try:
            response = await client.get(url, params=params, headers=final_headers)
        except httpx.HTTPError as exc:
            raise HtmlFetchError(url, reason=str(exc)) from exc

        if response.status_code >= 400:
            raise HtmlFetchError(url, status_code=response.status_code, reason="http_error")
        return response.text

    if http_client is not None:
        return await _fetch(http_client)

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        return await _fetch(client)


async def fetch_page(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    run_prune: bool = True,
) -> FetchedPage:
    raw_html = await fetch_html(url, http_client=client, timeout_seconds=timeout)
    # TODO: fetch_html only returns the response body today; return response metadata to preserve
    # the real status code here instead of assuming 200 on success.
    status_code = 200
    soup = BeautifulSoup(raw_html, "html.parser")
    cleaned_html = PruningCleaner().clean(raw_html) if run_prune else raw_html
    markdown = markdownify(
        cleaned_html,
        heading_style="ATX",
        strip=["script", "style"],
    ).strip()

    return FetchedPage(
        url=url,
        status_code=status_code,
        html=raw_html,
        cleaned_html=cleaned_html,
        markdown=markdown,
        links=_extract_links(soup, base_url=url),
        metadata=_extract_metadata(soup),
        tables=_extract_tables(soup),
        media=_extract_media(soup, base_url=url),
    )


def _extract_metadata(soup: BeautifulSoup) -> dict[str, str]:
    metadata: dict[str, str] = {}
    interesting_meta_keys = {
        "author",
        "description",
        "keywords",
        "og:description",
        "og:image",
        "og:locale",
        "og:site_name",
        "og:title",
        "og:type",
        "og:url",
        "robots",
        "twitter:description",
        "twitter:title",
        "viewport",
    }

    for meta_tag in soup.find_all("meta"):
        content = meta_tag.get("content")
        if not content:
            continue

        meta_key = meta_tag.get("property") or meta_tag.get("name")
        if not meta_key:
            continue

        normalized_key = meta_key.strip().lower()
        if normalized_key not in interesting_meta_keys:
            continue

        metadata[normalized_key] = content.strip()
        if normalized_key == "og:title":
            metadata.setdefault("title", content.strip())

    title_tag = soup.find("title")
    if title_tag is not None:
        title_text = title_tag.get_text(strip=True)
        if title_text:
            metadata.setdefault("title", title_text)

    for link_tag in soup.find_all("link", href=True):
        rel_values = link_tag.get("rel", [])
        if isinstance(rel_values, str):
            rel_tokens = {rel_values.lower()}
        else:
            rel_tokens = {str(value).lower() for value in rel_values}

        if "canonical" in rel_tokens:
            metadata["canonical"] = link_tag["href"].strip()
            break

    return metadata


def _extract_links(soup: BeautifulSoup, *, base_url: str) -> list[LinkRef]:
    parsed_base_url = urlparse(base_url)
    links: list[LinkRef] = []

    for anchor in soup.find_all("a", href=True):
        raw_href = anchor["href"].strip()
        if not raw_href:
            continue

        lower_href = raw_href.lower()
        if raw_href.startswith("#") or lower_href.startswith(("javascript:", "mailto:")):
            continue

        resolved_href = urljoin(base_url, raw_href)
        parsed_href = urlparse(resolved_href)
        links.append(
            LinkRef(
                href=resolved_href,
                text=anchor.get_text(strip=True)[:200],
                internal=not parsed_href.netloc or parsed_href.netloc == parsed_base_url.netloc,
            )
        )

    return links


def _extract_tables(soup: BeautifulSoup) -> list[TableData]:
    tables: list[TableData] = []

    for table_tag in soup.find_all("table"):
        rows = table_tag.find_all("tr")
        headers: list[str] = []
        data_rows: list[dict[str, str]] = []
        header_row_index: int | None = None

        for index, row in enumerate(rows):
            header_cells = row.find_all("th")
            if not header_cells:
                continue

            headers = [cell.get_text(strip=True) for cell in header_cells]
            header_row_index = index
            break

        if header_row_index is None and rows:
            header_row_index = 0
            headers = [cell.get_text(strip=True) for cell in rows[0].find_all(["td", "th"])]

        if header_row_index is not None:
            for row in rows[header_row_index + 1 :]:
                cell_values = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                if not cell_values:
                    continue
                data_rows.append(dict(zip(headers, cell_values, strict=False)))

        if not headers and not data_rows:
            continue

        tables.append(TableData(headers=headers, rows=data_rows))

    return tables


def _extract_media(soup: BeautifulSoup, *, base_url: str) -> list[MediaRef]:
    media: list[MediaRef] = []

    for image in soup.find_all("img", src=True):
        src = image["src"].strip()
        if not src:
            continue

        media.append(
            MediaRef(
                src=urljoin(base_url, src),
                alt=image.get("alt", ""),
                kind="image",
            )
        )

    for video in soup.find_all("video"):
        video_src = video.get("src")
        if isinstance(video_src, str) and video_src.strip():
            media.append(
                MediaRef(
                    src=urljoin(base_url, video_src.strip()),
                    kind="video",
                )
            )

        for source in video.find_all("source", src=True):
            source_src = source["src"].strip()
            if not source_src:
                continue
            media.append(MediaRef(src=urljoin(base_url, source_src), kind="video"))

    return media
