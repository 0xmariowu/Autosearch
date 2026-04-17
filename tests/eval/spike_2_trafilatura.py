# Source: storm/knowledge_storm/utils.py:L685-L711 (adapted)
from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import trafilatura
import yaml

USER_AGENT = "Mozilla/5.0 (compatible; autosearch-spike2)"
TIMEOUT_SECONDS = 15.0
BATCH_SIZE = 10
MIN_EXTRACT_LEN = 200
JS_ONLY_HTML_BYTES = 2 * 1024
ANTIBOT_MARKERS = ("verify you are human", "captcha", "访问验证")


def batched(items: list[tuple[str, str]], batch_size: int) -> list[list[tuple[str, str]]]:
    return [
        items[index : index + batch_size]
        for index in range(0, len(items), batch_size)
    ]


def extract_text(html: str) -> str:
    extracted = trafilatura.extract(
        html,
        include_tables=False,
        include_comments=False,
        output_format="txt",
    )
    return extracted.strip() if extracted else ""


def classify_result(status_code: int | None, html_size: int, html: str, extracted: str) -> str:
    if status_code is None or status_code < 200 or status_code >= 300:
        return "http_error"

    lowered_html = html.casefold()
    if any(marker in lowered_html for marker in ANTIBOT_MARKERS):
        return "antibot"

    # Tiny HTML shells are more likely JS-only stubs than genuine empty pages.
    if html_size < JS_ONLY_HTML_BYTES:
        return "js_only"

    extracted_len = len(extracted)
    if extracted_len == 0:
        return "empty_extract"
    if extracted_len < MIN_EXTRACT_LEN:
        return "short_extract"
    return "ok"


async def fetch_and_extract(
    client: httpx.AsyncClient,
    site: str,
    url: str,
) -> dict[str, Any]:
    status_code: int | None = None
    html_size = 0
    html = ""
    extracted = ""

    try:
        response = await client.get(url)
        status_code = response.status_code
        html = response.text
        html_size = len(response.content)
        if 200 <= response.status_code < 300:
            extracted = extract_text(html)
    except httpx.HTTPError:
        pass

    fail_reason = classify_result(status_code, html_size, html, extracted)
    extracted_len = len(extracted)

    return {
        "site": site,
        "url": url,
        "status_code": status_code,
        "html_size": html_size,
        "extracted_len": extracted_len,
        "pass": fail_reason == "ok",
        "fail_reason": fail_reason,
    }


def load_site_urls(urls_path: Path) -> dict[str, list[str]]:
    payload = yaml.safe_load(urls_path.read_text(encoding="utf-8"))
    sites = payload["sites"]
    return {str(site): list(urls) for site, urls in sites.items()}


def build_summary(
    site_names: list[str],
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}

    for site in site_names:
        site_details = [detail for detail in details if detail["site"] == site]
        pass_count = sum(1 for detail in site_details if detail["pass"])
        fail_count = len(site_details) - pass_count
        fail_reason_counts = Counter(
            detail["fail_reason"]
            for detail in site_details
            if detail["fail_reason"] != "ok"
        )

        output[site] = {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": round(pass_count / len(site_details), 4) if site_details else 0.0,
            "fail_reason_counts": dict(sorted(fail_reason_counts.items())),
        }

    output["details"] = details
    return output


async def main() -> None:
    base_dir = Path(__file__).resolve().parent
    urls_path = base_dir / "spike_2_urls.yaml"
    results_path = base_dir / "spike_2_results.json"

    site_urls = load_site_urls(urls_path)
    ordered_sites = list(site_urls)
    work_items = [
        (site, url)
        for site, urls in site_urls.items()
        for url in urls
    ]

    headers = {"User-Agent": USER_AGENT}
    timeout = httpx.Timeout(TIMEOUT_SECONDS)

    details: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=headers,
        timeout=timeout,
    ) as client:
        for batch in batched(work_items, BATCH_SIZE):
            batch_results = await asyncio.gather(
                *(fetch_and_extract(client, site, url) for site, url in batch)
            )
            details.extend(batch_results)

    payload = build_summary(ordered_sites, details)
    results_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
