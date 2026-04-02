from __future__ import annotations

import re
import sys
from datetime import datetime

import httpx
from lxml import html as lxml_html

from autosearch.v2.search_runner import DEFAULT_TIMEOUT, make_result

BASE_URL = "https://scholar.google.com/scholar"
PAGE_SIZE = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def _extract_text(nodes: object) -> str:
    if nodes is None:
        return ""
    if isinstance(nodes, list):
        parts: list[str] = []
        for node in nodes:
            if hasattr(node, "text_content"):
                parts.append(node.text_content())
            elif isinstance(node, str):
                parts.append(node)
        return " ".join(part.strip() for part in parts if part and part.strip()).strip()
    if hasattr(nodes, "text_content"):
        return nodes.text_content().strip()
    if isinstance(nodes, str):
        return nodes.strip()
    return ""


def _parse_gs_a(text: str | None) -> tuple[list[str], str, str, datetime | None]:
    if not text:
        return [], "", "", None

    segments = text.split(" - ")
    authors = segments[0].split(", ")
    publisher = segments[-1]
    if len(segments) != 3:
        return authors, "", publisher, None

    journal_year = segments[1].split(", ")
    if len(journal_year) > 1:
        journal = ", ".join(journal_year[:-1])
        if journal == "…":
            journal = ""
    else:
        journal = ""

    try:
        published_at = datetime.strptime(journal_year[-1].strip(), "%Y")
    except ValueError:
        published_at = None

    return authors, journal, publisher, published_at


def _build_metadata(
    pub_type: str,
    authors: list[str],
    journal: str,
    publisher: str,
    published_at: datetime | None,
    cited_by: str,
    html_url: str,
    pdf_url: str,
) -> dict:
    metadata = {
        "type": pub_type,
        "authors": authors,
        "journal": journal,
        "publisher": publisher,
        "cited_by": cited_by,
        "html_url": html_url,
        "pdf_url": pdf_url,
    }
    if published_at is not None:
        metadata["published_at"] = published_at.isoformat()
    return metadata


async def search(query: str, max_results: int = 10) -> list[dict]:
    results: list[dict] = []
    total_pages = max(1, (max_results + PAGE_SIZE - 1) // PAGE_SIZE)

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        ) as client:
            for page in range(total_pages):
                response = await client.get(
                    BASE_URL,
                    params={
                        "q": query,
                        "hl": "en",
                        "ie": "UTF-8",
                        "oe": "UTF-8",
                        "start": page * PAGE_SIZE,
                        "as_sdt": "2007",
                        "as_vis": "0",
                    },
                )

                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location", "")
                    if "/sorry/index?continue" in location:
                        print(
                            "[google-scholar] access denied: unusual traffic detected",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"[google-scholar] redirect blocked: {location.split('?')[0]}",
                            file=sys.stderr,
                        )
                    return []

                response.raise_for_status()
                dom = lxml_html.fromstring(response.text)

                if dom.xpath("//form[@id='gs_captcha_f']"):
                    print("[google-scholar] captcha encountered", file=sys.stderr)
                    return []

                page_items = dom.xpath("//div[@data-rp]")
                if not page_items:
                    break

                for item in page_items:
                    title = _extract_text(item.xpath(".//h3[1]//a"))
                    if not title:
                        continue

                    urls = item.xpath(".//h3[1]//a/@href")
                    url = urls[0].strip() if urls else ""
                    if not url:
                        continue

                    pub_type = _extract_text(item.xpath(".//span[@class='gs_ctg2']"))
                    if pub_type.startswith("[") and pub_type.endswith("]"):
                        pub_type = pub_type[1:-1].lower()

                    content = _extract_text(item.xpath(".//div[@class='gs_rs']"))
                    authors, journal, publisher, published_at = _parse_gs_a(
                        _extract_text(item.xpath(".//div[@class='gs_a']"))
                    )
                    if publisher and publisher in url:
                        publisher = ""

                    cited_by = _extract_text(
                        item.xpath(
                            ".//div[@class='gs_fl']/a[starts-with(@href,'/scholar?cites=')]"
                        )
                    )

                    doc_urls = item.xpath(".//div[@class='gs_or_ggsm']/a/@href")
                    doc_url = doc_urls[0].strip() if doc_urls else ""
                    doc_type = _extract_text(item.xpath(".//div[@class='gs_or_ggsm']//span[@class='gs_ctg2']"))
                    if not doc_type:
                        doc_type = _extract_text(item.xpath(".//span[@class='gs_ctg2']"))
                    pdf_url = doc_url if doc_type == "[PDF]" else ""
                    html_url = "" if doc_type == "[PDF]" else doc_url

                    results.append(
                        make_result(
                            url=url,
                            title=title,
                            snippet=content,
                            source="google-scholar",
                            query=query,
                            extra_metadata=_build_metadata(
                                pub_type=pub_type,
                                authors=authors,
                                journal=journal,
                                publisher=publisher,
                                published_at=published_at,
                                cited_by=cited_by,
                                html_url=html_url,
                                pdf_url=pdf_url,
                            ),
                        )
                    )
                    if len(results) >= max_results:
                        return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        print(f"[google-scholar] search failed: {exc}", file=sys.stderr)
        return []
