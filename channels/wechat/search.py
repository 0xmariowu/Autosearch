from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

import httpx
from lxml import html as lxml_html

from lib.search_runner import DEFAULT_TIMEOUT, make_result

BASE_URL = "https://weixin.sogou.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
PAGE_SIZE = 10


def _text(xpath_result: list) -> str:
    if not xpath_result:
        return ""
    parts: list[str] = []
    for node in xpath_result:
        if hasattr(node, "text_content"):
            parts.append(node.text_content())
        elif isinstance(node, str):
            parts.append(node)
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


async def search(query: str, max_results: int = 10) -> list[dict]:
    results: list[dict] = []
    total_pages = max(1, (max_results + PAGE_SIZE - 1) // PAGE_SIZE)

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for page in range(1, total_pages + 1):
                response = await client.get(
                    f"{BASE_URL}/weixin",
                    params={"query": query, "page": page, "type": 2},
                )
                response.raise_for_status()
                dom = lxml_html.fromstring(response.text)
                items = dom.xpath('//li[contains(@id, "sogou_vr_")]')
                if not items:
                    break

                for item in items:
                    title = _text(item.xpath(".//h3/a"))
                    urls = item.xpath(".//h3/a/@href")
                    url = (urls[0] if urls else "").strip()
                    if url.startswith("/link?url="):
                        url = f"{BASE_URL}{url}"
                    if not title or not url:
                        continue

                    snippet = _text(item.xpath('.//p[@class="txt-info"]'))
                    if not snippet:
                        snippet = _text(
                            item.xpath('.//p[contains(@class, "txt-info")]')
                        )

                    thumbnails = item.xpath('.//div[@class="img-box"]/a/img/@src')
                    thumbnail = (thumbnails[0] if thumbnails else "").strip()
                    if thumbnail.startswith("//"):
                        thumbnail = f"https:{thumbnail}"

                    metadata = {"thumbnail": thumbnail} if thumbnail else {}
                    timestamp_script = _text(
                        item.xpath('.//script[contains(text(), "timeConvert")]')
                    )
                    if timestamp_script:
                        match = re.search(r"timeConvert\('(\d+)'\)", timestamp_script)
                        if match:
                            metadata["published_at"] = datetime.fromtimestamp(
                                int(match.group(1)), tz=timezone.utc
                            ).isoformat()

                    results.append(
                        make_result(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="wechat",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                    if len(results) >= max_results:
                        return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        print(f"[wechat] search failed: {exc}", file=sys.stderr)
        return []
