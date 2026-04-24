from __future__ import annotations

import html
import asyncio
from importlib import import_module
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import structlog

from autosearch.core.models import Evidence, FetchedPage, SubQuery

try:
    from ddgs import DDGS
except ImportError:
    DDGS = import_module("duckduckgo_search").DDGS

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="discourse_forum")

DEFAULT_SITE_KEY = "linux_do"
HTTP_TIMEOUT = 15.0
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
USER_AGENT = "AutoSearch/1.0 (+https://github.com/0xmariowu/Autosearch)"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
JINA_READER_PREFIX = "https://r.jina.ai/"

SITE_PRESETS: dict[str, dict[str, str]] = {
    "linux_do": {
        "base_url": "https://linux.do",
        "search_endpoint": "/search.json",
        "source_channel": "discourse_forum:linux_do",
        "title_suffix": " - LINUX DO",
    }
}


def _normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _clean_text(value: object) -> str:
    text = HTML_TAG_RE.sub(" ", str(value or ""))
    return _normalize_whitespace(html.unescape(text))


def _truncate_on_word_boundary(text: str, *, max_length: int) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _clean_site_search_title(title: str, *, site: Mapping[str, str]) -> str:
    """Strip a site-specific forum suffix from fallback search result titles."""
    cleaned = title.strip()
    title_suffix = site.get("title_suffix", "").strip()
    if title_suffix and cleaned.endswith(title_suffix):
        cleaned = cleaned[: -len(title_suffix)].strip()
    return cleaned


def _reader_url(url: str) -> str:
    return f"{JINA_READER_PREFIX}{url}"


def _topic_url(post: Mapping[str, object], *, site: Mapping[str, str]) -> str | None:
    topic_id = str(post.get("topic_id") or "").strip()
    if not topic_id:
        return None

    slug = str(post.get("slug") or post.get("topic_slug") or "").strip().strip("/")
    if slug:
        return f"{site['base_url']}/t/{slug}/{topic_id}"
    return f"{site['base_url']}/t/{topic_id}"


def _to_evidence(
    post: Mapping[str, object],
    *,
    site: Mapping[str, str],
    fetched_at: datetime,
) -> Evidence | None:
    url = _topic_url(post, site=site)
    if not url:
        return None

    title = (
        _clean_text(post.get("topic_title_headline"))
        or _clean_text(post.get("title"))
        or _clean_text(post.get("fancy_title"))
    )
    if not title:
        return None

    content = _clean_text(post.get("blurb")) or None
    snippet = (
        _truncate_on_word_boundary(content, max_length=MAX_SNIPPET_LENGTH) if content else None
    )

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel=site["source_channel"],
        fetched_at=fetched_at,
        score=0.0,
    )


def _site_search_query(site: Mapping[str, str], query: str) -> str:
    domain = urlparse(site["base_url"]).netloc
    return f"site:{domain} {query}"


def _same_origin(url: str, base_url: str) -> bool:
    """Require exact scheme and host equality before trusting a fallback result URL."""
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return parsed_url.scheme == parsed_base.scheme and parsed_url.netloc == parsed_base.netloc


def _to_site_search_evidence(
    result: Mapping[str, object],
    *,
    site: Mapping[str, str],
    fetched_at: datetime,
) -> Evidence | None:
    href = str(result.get("href") or "").strip()
    if not _same_origin(href, site["base_url"]):
        return None
    parsed = urlparse(href)
    if "/t/" not in parsed.path:
        return None

    title = _clean_site_search_title(str(result.get("title") or "").strip(), site=site)
    if not title:
        return None

    content = _normalize_whitespace(str(result.get("body") or "").strip()) or None
    snippet = (
        _truncate_on_word_boundary(content, max_length=MAX_SNIPPET_LENGTH) if content else None
    )

    return Evidence(
        url=href,
        title=title,
        snippet=snippet,
        content=content,
        source_channel=f"{site['source_channel']}:site_search",
        fetched_at=fetched_at,
        score=0.0,
    )


def _clean_jina_markdown(markdown: str) -> str:
    cleaned = markdown.strip()
    marker = "Markdown Content:"
    if marker in cleaned:
        cleaned = cleaned.split(marker, maxsplit=1)[1].strip()
    return cleaned


async def _fetch_topic_markdown(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> str | None:
    """Fetch topic markdown via the Jina reader and normalize the payload."""
    reader_url = _reader_url(url)
    try:
        if http_client is not None:
            response = await http_client.get(reader_url, headers={"User-Agent": USER_AGENT})
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(reader_url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception:
        return None

    markdown = _clean_jina_markdown(response.text)
    return markdown or None


async def _enrich_evidence(
    evidence: Evidence,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Evidence:
    """Hydrate one evidence item with full topic markdown when available."""
    markdown = await _fetch_topic_markdown(evidence.url, http_client=http_client)
    if not markdown:
        return evidence

    source_page = FetchedPage(
        url=evidence.url,
        status_code=200,
        markdown=markdown,
        metadata={"reader_url": _reader_url(evidence.url), "title": evidence.title},
    )
    snippet = _truncate_on_word_boundary(
        _normalize_whitespace(markdown),
        max_length=MAX_SNIPPET_LENGTH,
    )

    return evidence.model_copy(
        update={
            "snippet": snippet or evidence.snippet,
            "content": markdown,
            "source_page": source_page,
        }
    )


async def _search_site(query: SubQuery, *, site: Mapping[str, str]) -> list[Evidence]:
    """Fallback to site-limited DDGS search when the forum API is blocked."""
    results = await asyncio.to_thread(
        lambda: list(DDGS().text(_site_search_query(site, query.text), max_results=MAX_RESULTS))
    )
    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    seen_urls: set[str] = set()

    for result in results:
        if not isinstance(result, Mapping):
            continue
        evidence = _to_site_search_evidence(result, site=site, fetched_at=fetched_at)
        if evidence is None or evidence.url in seen_urls:
            continue
        seen_urls.add(evidence.url)
        evidences.append(evidence)
        if len(evidences) >= MAX_RESULTS:
            break

    return evidences


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
    site_key: str = DEFAULT_SITE_KEY,
) -> list[Evidence]:
    """Search a public Discourse forum and enrich matched topics with full text."""
    if http_client is None:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            return await search(query, http_client=client, site_key=site_key)

    site = SITE_PRESETS[site_key]
    try:
        params = {"q": query.text}
        url = f"{site['base_url']}{site['search_endpoint']}"
        response = await http_client.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
        )

        response.raise_for_status()
        payload = response.json()
        posts = payload.get("posts")
        if not isinstance(posts, list):
            raise ValueError("invalid posts payload")
    except Exception as exc:
        try:
            evidences = await _search_site(query, site=site)
        except Exception as fallback_exc:
            LOGGER.warning(
                "discourse_forum_search_failed",
                reason=str(exc),
                fallback_reason=str(fallback_exc),
            )
            return []
        return await asyncio.gather(
            *[_enrich_evidence(evidence, http_client=http_client) for evidence in evidences]
        )

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    seen_topic_ids: set[str] = set()

    for post in posts:
        if not isinstance(post, Mapping):
            continue

        topic_id = str(post.get("topic_id") or "").strip()
        if topic_id and topic_id in seen_topic_ids:
            continue

        evidence = _to_evidence(post, site=site, fetched_at=fetched_at)
        if evidence is None:
            continue

        if topic_id:
            seen_topic_ids.add(topic_id)
        evidences.append(evidence)
        if len(evidences) >= MAX_RESULTS:
            break

    return await asyncio.gather(
        *[_enrich_evidence(evidence, http_client=http_client) for evidence in evidences]
    )
