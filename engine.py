#!/usr/bin/env python3
"""
AutoSearch Engine — self-evolving search core.

Reusable module with two modes:
  - Manual: AI fills genes/platforms/target_spec, runs focused search
  - Daily: reads queries.json as seed genes, broad discovery (F001.S2)

3 phases:
  Phase 1: EXPLORE — find best queries (pattern injection + LLM evaluation)
  Phase 2: HARVEST — collect findings with winning queries
  Phase 3: POST-MORTEM — analyze what worked/failed, write back to patterns.jsonl
"""

import json
import os
import random
import re
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from project_experience import get_provider_decision
from source_capability import get_source_decision


# ============================================================
# DATA TYPES
# ============================================================

@dataclass
class SearchResult:
    """Standardized result from any platform."""
    title: str = ""
    url: str = ""
    eng: int = 0  # engagement score (0 for platforms that don't provide it)
    created: str = ""
    body: str = ""
    source: str = ""


@dataclass
class PlatformSearchOutcome:
    """Search execution result for one provider attempt."""
    provider: str
    results: list[SearchResult] = field(default_factory=list)
    error_alias: str = ""


@dataclass
class Experiment:
    """One query execution record."""
    round: int
    query: str
    query_family: str = "unknown"
    new: int = 0
    score: int = 0
    adjusted_score: int = 0
    source: str = "gene"
    sample_titles: list = field(default_factory=list)
    harvested_urls: list = field(default_factory=list)
    session: str = ""


@dataclass
class EngineConfig:
    """Engine configuration."""
    genes: dict = field(default_factory=lambda: {
        "entity": [], "pain_verb": [], "object": [],
        "symptom": [], "context": [],
    })
    platforms: list = field(default_factory=list)
    target_spec: str = ""
    task_name: str = "autosearch"
    output_path: str = "/tmp/autosearch-findings.jsonl"
    run_id: str = "autosearch"
    query_family_map: dict = field(default_factory=dict)
    query_family_word_map: dict = field(default_factory=dict)
    experience_policy: dict = field(default_factory=dict)
    capability_report: dict = field(default_factory=dict)

    # Search tuning
    max_stale: int = 5
    max_rounds: int = 15
    queries_per_round: int = 15
    harvest_since: str = "2025-10-01"

    # Query source ratios
    llm_ratio: float = 0.20
    pattern_ratio: float = 0.20
    gene_ratio: float = 0.60

    # LLM model (daily=sonnet, manual=haiku for cost)
    llm_model: str = "claude-haiku-4-5-20251001"


# ============================================================
# PATTERN STORE
# ============================================================

class PatternStore:
    """Manages patterns.jsonl — accumulated search intelligence."""

    def __init__(self, path: Path):
        self.path = path
        self.use_patterns: list[dict] = []
        self.avoid_patterns: list[dict] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            p = json.loads(line)
            finding = p.get("finding", "")
            if any(w in finding.lower() for w in
                   ["fail", "don't", "never", "avoid", "unreliable", "empty"]):
                self.avoid_patterns.append(p)
            else:
                self.use_patterns.append(p)

    def append(self, patterns: list[dict]):
        with open(self.path, "a") as f:
            for p in patterns:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

    def total_count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for line in self.path.read_text().splitlines()
                   if line.strip())


# ============================================================
# LLM EVALUATOR
# ============================================================

class LLMEvaluator:
    """Calls Anthropic API for relevance evaluation."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.enabled = bool(self.api_key)

    def evaluate_round(self, results: list[SearchResult],
                       target_spec: str) -> Optional[dict]:
        """Evaluate top results for relevance. Returns parsed JSON or None."""
        if not results or not self.enabled:
            return None

        items = []
        for i, r in enumerate(results[:10]):
            body_preview = r.body[:200].replace("\n", " ")
            items.append(f'{i}. "{r.title}" | {body_preview}')

        prompt = f"""You are evaluating search results for relevance.

TARGET: {target_spec}

Results:
{chr(10).join(items)}

Respond ONLY with JSON (no markdown, no code fences):
{{"results": [{{"index": 0, "relevant": true, "reason": "..."}}], "next_queries": ["search term 1", "search term 2"]}}

Rules:
- Mark relevant=true ONLY if the result directly matches the TARGET
- Suggest 2-3 next_queries that would find MORE results matching TARGET
- next_queries should be concrete search terms, not descriptions"""

        return self._call_api(prompt)

    def _call_api(self, prompt: str, max_tokens: int = 1024) -> Optional[dict]:
        if not self.api_key:
            return None
        try:
            body = json.dumps({
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            text = resp.get("content", [{}])[0].get("text", "")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return None
        except Exception as e:
            print(f"    [LLM] Error: {e}")
            return None


# ============================================================
# PLATFORM CONNECTORS
# ============================================================

class PlatformConnector:
    """Unified interface to all search platforms.

    Supports both AutoSearch-style (direct API) and Scout-style (mcporter/xreach)
    connectors. The `method` field in platform config selects the approach.
    """

    @staticmethod
    def search(platform: dict, query: str) -> PlatformSearchOutcome:
        name = platform["name"]
        dispatch = {
            "searxng": PlatformConnector._searxng,
            "ddgs": PlatformConnector._ddgs,
            "reddit": PlatformConnector._reddit_api,
            "reddit_exa": PlatformConnector._reddit_exa,
            "hn": PlatformConnector._hn_algolia,
            "hn_exa": PlatformConnector._hn_exa,
            "exa": PlatformConnector._exa,
            "tavily": PlatformConnector._tavily,
            "huggingface_datasets": PlatformConnector._huggingface_datasets,
            "github_code": PlatformConnector._github_code,
            "github_issues": PlatformConnector._github_issues,
            "github_repos": PlatformConnector._github_repos,
            "twitter_exa": PlatformConnector._twitter_exa,
            "twitter_xreach": PlatformConnector._twitter_xreach,
            # Legacy aliases (backwards compat with run-template.py)
            "github": PlatformConnector._github_issues,
        }
        fn = dispatch.get(name)
        if not fn:
            print(f"    [Platform] Unknown: {name}")
            return PlatformSearchOutcome(provider=name)
        return fn(platform, query)

    @staticmethod
    def _outcome(provider: str, results: list[SearchResult] | None = None,
                 error_alias: str = "") -> PlatformSearchOutcome:
        return PlatformSearchOutcome(
            provider=provider,
            results=list(results or []),
            error_alias=error_alias,
        )

    @staticmethod
    def _github_error_alias(stderr: str) -> str:
        lowered = (stderr or "").lower()
        if any(token in lowered for token in ["not logged", "authentication", "login", "auth"]):
            return "gh_auth_error"
        return "github_repo_error"

    @staticmethod
    def _xreach_error_alias(stderr: str) -> str:
        lowered = (stderr or "").lower()
        if any(token in lowered for token in ["auth", "login", "cookie", "unauthorized"]):
            return "xreach_auth_error"
        return "xreach_auth_error"

    # --- Reddit: direct API ---
    @staticmethod
    def _reddit_api(platform: dict, query: str) -> PlatformSearchOutcome:
        sub = platform.get("sub", "all")
        limit = platform.get("limit", 20)
        url = (f"https://www.reddit.com/r/{sub}/search.json?"
               f"q={urllib.parse.quote(query)}&restrict_sr=on"
               f"&limit={limit}&sort=relevance&t=all")
        req = urllib.request.Request(
            url, headers={"User-Agent": "autosearch-engine/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            return PlatformConnector._outcome("reddit", [
                SearchResult(
                    title=p["data"].get("title", ""),
                    url="https://www.reddit.com" + p["data"].get("permalink", ""),
                    eng=p["data"].get("score", 0) + p["data"].get("num_comments", 0),
                    created=datetime.fromtimestamp(
                        p["data"].get("created_utc", 0)
                    ).strftime("%Y-%m-%d"),
                    body=p["data"].get("selftext", "")[:500],
                    source="reddit",
                )
                for p in data.get("data", {}).get("children", [])
            ])
        except Exception:
            return PlatformConnector._outcome("reddit")

    # --- Reddit: via Exa (Scout-style) ---
    @staticmethod
    def _reddit_exa(platform: dict, query: str) -> PlatformSearchOutcome:
        return PlatformConnector._exa_with_site(
            "reddit.com", query, "reddit", platform.get("name", "reddit_exa"),
            limit=platform.get("limit", 5),
        )

    # --- HN: Algolia API ---
    @staticmethod
    def _hn_algolia(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 20)
        url = (f"https://hn.algolia.com/api/v1/search?"
               f"query={urllib.parse.quote(query)}&tags=story"
               f"&hitsPerPage={limit}")
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            return PlatformConnector._outcome("hn", [
                SearchResult(
                    title=h.get("title", ""),
                    url=f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
                    eng=h.get("points", 0) + h.get("num_comments", 0),
                    created=h.get("created_at", "")[:10],
                    source="hn",
                )
                for h in data.get("hits", [])
            ])
        except Exception:
            return PlatformConnector._outcome("hn")

    # --- HN: via Exa (Scout-style) ---
    @staticmethod
    def _hn_exa(platform: dict, query: str) -> PlatformSearchOutcome:
        return PlatformConnector._exa_with_site(
            "news.ycombinator.com", query, "hn", platform.get("name", "hn_exa"),
            limit=platform.get("limit", 5),
        )

    # --- Exa: semantic web search ---
    @staticmethod
    def _exa(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 10)
        try:
            escaped = query.replace('"', '\\"')
            cmd = [
                "mcporter", "call",
                f'exa.web_search_exa(query: "{escaped}", numResults: {limit})',
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                cwd=os.path.expanduser("~"),
            )
            if result.returncode != 0:
                return PlatformConnector._outcome("exa", error_alias="exa_unavailable")

            # mcporter outputs text blocks, not JSON — parse Title/URL/etc
            return PlatformConnector._outcome(
                "exa",
                PlatformConnector._parse_exa_text(result.stdout, "exa"),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return PlatformConnector._outcome("exa", error_alias="exa_unavailable")

    @staticmethod
    def _searxng(platform: dict, query: str) -> PlatformSearchOutcome:
        base_url = str(os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")).rstrip("/")
        limit = int(platform.get("limit", 10) or 10)
        params = {
            "q": str(platform.get("query") or query or "").strip(),
            "format": "json",
            "language": str(platform.get("language") or "en"),
        }
        if limit > 0:
            params["pageno"] = "1"
        url = f"{base_url}/search?{urllib.parse.urlencode(params)}"
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "autosearch/1.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in list(data.get("results") or [])[:limit]:
                url_value = str(item.get("url") or "").strip()
                title = str(item.get("title") or "").strip()
                if not url_value and not title:
                    continue
                body = str(item.get("content") or item.get("snippet") or "")[:500]
                results.append(SearchResult(
                    title=title,
                    url=url_value,
                    body=body,
                    source="searxng",
                ))
            return PlatformConnector._outcome("searxng", results)
        except Exception:
            return PlatformConnector._outcome("searxng", error_alias="searxng_unavailable")

    @staticmethod
    def _ddgs(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = int(platform.get("limit", 10) or 10)
        backend = str(platform.get("backend_name") or "auto")
        try:
            module = __import__("ddgs")
            ddgs_class = getattr(module, "DDGS", None)
            if ddgs_class is None:
                return PlatformConnector._outcome("ddgs", error_alias="ddgs_unavailable")
            with ddgs_class() as client:
                rows = list(client.text(query, max_results=limit, backend=backend) or [])
            results = []
            for item in rows[:limit]:
                url_value = str(item.get("href") or item.get("url") or "").strip()
                title = str(item.get("title") or "").strip()
                if not url_value and not title:
                    continue
                body = str(item.get("body") or item.get("snippet") or "")[:500]
                results.append(SearchResult(
                    title=title,
                    url=url_value,
                    body=body,
                    source="ddgs",
                ))
            return PlatformConnector._outcome("ddgs", results)
        except Exception:
            return PlatformConnector._outcome("ddgs", error_alias="ddgs_unavailable")

    @staticmethod
    def _tavily(platform: dict, query: str) -> PlatformSearchOutcome:
        api_key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not api_key:
            return PlatformConnector._outcome("tavily", error_alias="tavily_unavailable")

        limit = int(platform.get("limit", 10) or 10)
        payload = {
            "query": str(platform.get("query") or query or "").strip(),
            "search_depth": str(platform.get("search_depth") or "basic"),
            "topic": str(platform.get("topic") or "general"),
            "max_results": limit,
            "include_answer": False,
            "include_raw_content": False,
        }
        if platform.get("include_domains"):
            payload["include_domains"] = list(platform.get("include_domains") or [])
        request = urllib.request.Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "autosearch/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = []
            for item in data.get("results", []) or []:
                url = str(item.get("url") or "").strip()
                title = str(item.get("title") or "").strip()
                if not url and not title:
                    continue
                score = item.get("score", 0) or 0
                body = str(item.get("content") or item.get("raw_content") or "")[:500]
                results.append(SearchResult(
                    title=title,
                    url=url,
                    eng=int(float(score) * 100),
                    body=body,
                    source="tavily",
                ))
            return PlatformConnector._outcome("tavily", results)
        except Exception:
            return PlatformConnector._outcome("tavily", error_alias="tavily_unavailable")

    @staticmethod
    def _huggingface_query_terms(query: str, max_terms: int = 2) -> str:
        tokens = [
            token
            for token in re.split(r"\s+", (query or "").strip())
            if token and any(ch.isalnum() for ch in token)
        ]
        cleaned: list[str] = []
        for token in tokens:
            word = re.sub(r"[^a-zA-Z0-9\\-]+", "", token).lower()
            if len(word) < 3:
                continue
            if word not in cleaned:
                cleaned.append(word)
            if len(cleaned) >= max_terms:
                break
        return " ".join(cleaned[:max_terms])

    @staticmethod
    def _huggingface_datasets(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = int(platform.get("limit", 10) or 10)
        search = str(platform.get("query") or query or "").strip()
        hf_query = PlatformConnector._huggingface_query_terms(search)
        if not hf_query:
            return PlatformConnector._outcome("huggingface_datasets")

        params = urllib.parse.urlencode({
            "search": hf_query,
            "sort": "downloads",
            "direction": "-1",
            "limit": limit,
        })
        url = f"https://huggingface.co/api/datasets?{params}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "agent-reach/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = []
            for item in payload:
                dataset_id = str(item.get("id") or "")
                if not dataset_id:
                    continue
                tags = [str(tag) for tag in item.get("tags", [])[:8] if str(tag).strip()]
                body_parts = []
                if item.get("description"):
                    body_parts.append(str(item.get("description") or ""))
                if tags:
                    body_parts.append("tags: " + ", ".join(tags))
                results.append(SearchResult(
                    title=dataset_id,
                    url=f"https://huggingface.co/datasets/{dataset_id}",
                    eng=int(item.get("downloads", 0) or 0) + int(item.get("likes", 0) or 0),
                    created=str(item.get("createdAt") or "")[:10],
                    body=" | ".join(body_parts)[:500],
                    source="huggingface_datasets",
                ))
            return PlatformConnector._outcome("huggingface_datasets", results)
        except Exception:
            return PlatformConnector._outcome("huggingface_datasets")

    # --- GitHub Issues: via gh CLI ---
    @staticmethod
    def _github_issues(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 10)
        repo = platform.get("repo")
        try:
            cmd = [
                "gh", "search", "issues", query,
                "--sort", "comments", "--limit", str(limit),
                "--json", "title,url,commentsCount,body,createdAt",
            ]
            if repo:
                cmd.extend(["--repo", repo])
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return PlatformConnector._outcome(
                    "github_issues",
                    error_alias=PlatformConnector._github_error_alias(result.stderr),
                )
            issues = json.loads(result.stdout)
            return PlatformConnector._outcome("github_issues", [
                SearchResult(
                    title=i.get("title", ""),
                    url=i.get("url", ""),
                    eng=i.get("commentsCount", 0),
                    created=i.get("createdAt", "")[:10],
                    body=(i.get("body") or "")[:500],
                    source="github_issues",
                )
                for i in issues
            ])
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError):
            return PlatformConnector._outcome("github_issues", error_alias="github_repo_error")

    # --- GitHub Code: via gh CLI ---
    @staticmethod
    def _github_code(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 10)
        repo = platform.get("repo")
        try:
            cmd = [
                "gh", "search", "code", query,
                "--limit", str(limit),
                "--json", "repository,path,url,textMatches",
            ]
            if repo:
                cmd.extend(["--repo", repo])
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20)
            if result.returncode != 0:
                return PlatformConnector._outcome(
                    "github_code",
                    error_alias=PlatformConnector._github_error_alias(result.stderr),
                )
            matches = json.loads(result.stdout)
            results = []
            for item in matches:
                repo_info = item.get("repository") or {}
                repo_name = str(repo_info.get("nameWithOwner") or "")
                path = str(item.get("path") or "")
                text_matches = item.get("textMatches") or []
                fragments = []
                for match in text_matches[:2]:
                    fragment = str(match.get("fragment") or "").strip()
                    if fragment:
                        fragments.append(fragment.replace("\n", " "))
                results.append(SearchResult(
                    title=f"{repo_name}:{path}" if repo_name and path else (path or repo_name),
                    url=str(item.get("url") or repo_info.get("url") or ""),
                    eng=len(text_matches),
                    body=" | ".join(fragments)[:500],
                    source="github_code",
                ))
            return PlatformConnector._outcome("github_code", results)
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError):
            return PlatformConnector._outcome("github_code", error_alias="github_repo_error")

    # --- GitHub Repos: via gh CLI (Scout-style) ---
    @staticmethod
    def _github_repos(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 5)
        min_stars = platform.get("min_stars", 100)
        try:
            cmd = [
                "gh", "search", "repos", query,
                "--sort=stars", "--limit", str(limit),
                "--json",
                "name,owner,description,stargazersCount,url,createdAt,updatedAt",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return PlatformConnector._outcome(
                    "github_repos",
                    error_alias=PlatformConnector._github_error_alias(result.stderr),
                )
            repos = json.loads(result.stdout)
            return PlatformConnector._outcome("github_repos", [
                SearchResult(
                    title=f"{r['owner']['login']}/{r['name']}",
                    url=r.get("url", ""),
                    eng=r.get("stargazersCount", 0),
                    created=r.get("createdAt", "")[:10],
                    body=(r.get("description") or ""),
                    source="github_repos",
                )
                for r in repos
                if r.get("stargazersCount", 0) >= min_stars
            ])
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError):
            return PlatformConnector._outcome("github_repos", error_alias="github_repo_error")

    # --- Twitter: via Exa ---
    @staticmethod
    def _twitter_exa(platform: dict, query: str) -> PlatformSearchOutcome:
        return PlatformConnector._exa_with_site(
            "x.com", query, "twitter", platform.get("name", "twitter_exa"),
            limit=platform.get("limit", 10),
        )

    # --- Twitter: via xreach CLI (Scout-style) ---
    @staticmethod
    def _twitter_xreach(platform: dict, query: str) -> PlatformSearchOutcome:
        limit = platform.get("limit", 10)
        try:
            cmd = ["xreach", "search", query, "-n", str(limit), "--json"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return PlatformConnector._outcome(
                    "twitter_xreach",
                    error_alias=PlatformConnector._xreach_error_alias(result.stderr),
                )
            data = json.loads(result.stdout)
            results = []
            for item in data.get("items", []):
                text = item.get("text", "")
                # Extract non-twitter URLs from tweet text
                urls = re.findall(r'https?://[^\s")\]]+', text)
                urls = [u for u in urls
                        if "x.com" not in u and "twitter.com" not in u]
                if urls:
                    results.append(SearchResult(
                        title=text[:500],
                        url=urls[0],
                        eng=item.get("likeCount", 0) + item.get("retweetCount", 0),
                        created=item.get("createdAt", ""),
                        source="twitter",
                    ))
            return PlatformConnector._outcome("twitter_xreach", results)
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError):
            return PlatformConnector._outcome("twitter_xreach", error_alias="xreach_auth_error")

    # --- Shared: Exa with site: filter ---
    @staticmethod
    def _exa_with_site(site: str, query: str, source_name: str,
                       provider_name: str, limit: int = 5) -> PlatformSearchOutcome:
        error_alias = {
            "reddit_exa": "reddit_exa_error",
            "hn_exa": "hn_exa_error",
        }.get(provider_name, "exa_unavailable")
        try:
            full_query = f"{query} site:{site}"
            escaped = full_query.replace('"', '\\"')
            cmd = [
                "mcporter", "call",
                f'exa.web_search_exa(query: "{escaped}", numResults: {limit})',
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                cwd=os.path.expanduser("~"),
            )
            if result.returncode != 0:
                return PlatformConnector._outcome(provider_name, error_alias=error_alias)
            parsed = PlatformConnector._parse_exa_text(
                result.stdout, source_name)
            # Filter: only keep URLs matching the site
            return PlatformConnector._outcome(
                provider_name,
                [r for r in parsed if site in r.url],
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return PlatformConnector._outcome(provider_name, error_alias=error_alias)

    @staticmethod
    def _parse_exa_text(text: str, source_name: str) -> list[SearchResult]:
        """Parse mcporter's text output.

        Format:
          Title: ...
          URL: ...
          Published: ...
          Author: ...
          Highlights:
          ...body content...
        """
        results = []
        current = None
        in_highlights = False
        body_lines: list[str] = []

        for line in text.split("\n"):
            if line.startswith("Title:"):
                # Save previous entry
                if current and current.url:
                    if body_lines:
                        current.body = "\n".join(body_lines).strip()[:500]
                    results.append(current)
                current = SearchResult(
                    title=line[6:].strip(), source=source_name)
                in_highlights = False
                body_lines = []
            elif current is not None:
                if line.startswith("URL:"):
                    current.url = line[4:].strip()
                    in_highlights = False
                elif line.startswith("Published Date:") or line.startswith("Published:"):
                    date_part = line.split(":", 1)[1].strip()
                    current.created = date_part[:10]
                    in_highlights = False
                elif line.startswith("Author:"):
                    in_highlights = False
                elif line.startswith("Highlights:"):
                    in_highlights = True
                elif in_highlights:
                    body_lines.append(line)

        # Don't forget the last entry
        if current and current.url:
            if body_lines:
                current.body = "\n".join(body_lines).strip()[:500]
            results.append(current)
        return results


# ============================================================
# QUERY GENERATOR
# ============================================================

class QueryGenerator:
    """Generates queries from gene pool + LLM suggestions + past patterns."""

    def __init__(self, config: EngineConfig, patterns: PatternStore):
        self.config = config
        self.patterns = patterns
        self.llm_suggestions: list[str] = []
        self.seed_queries: list[str] = []  # never capped, rotated per round

    def add_llm_suggestions(self, suggestions: list[str]):
        self.llm_suggestions.extend(suggestions)
        # Recency cap — only for runtime LLM suggestions
        self.llm_suggestions = self.llm_suggestions[-30:]

    def add_seed_queries(self, queries: list[str]):
        """Add seed queries (from queries.json). Not subject to recency cap.

        Seeds are sampled each round to ensure full topic coverage
        across multiple rounds.
        """
        seen = set(self.seed_queries)
        for q in queries:
            if q not in seen:
                self.seed_queries.append(q)
                seen.add(q)

    def generate(self, n: Optional[int] = None) -> tuple[list[str], dict[str, str]]:
        """Generate n queries. Returns (queries, {query: source_tag})."""
        n = n or self.config.queries_per_round
        queries = []
        sources: dict[str, str] = {}

        n_llm = int(n * self.config.llm_ratio)
        n_pattern = int(n * self.config.pattern_ratio)

        # LLM bucket draws from both seed_queries and runtime llm_suggestions
        llm_pool = self.seed_queries + self.llm_suggestions
        if llm_pool:
            for q in random.sample(
                llm_pool,
                min(n_llm, len(llm_pool)),
            ):
                if q and q not in sources:
                    queries.append(q)
                    sources[q] = "llm"

        # 20% from past winning patterns
        if self.patterns.use_patterns:
            for p in random.sample(
                self.patterns.use_patterns,
                min(n_pattern, len(self.patterns.use_patterns)),
            ):
                finding = p.get("finding", "")
                cats = [k for k, v in self.config.genes.items() if v]
                if cats:
                    gene = random.choice(
                        self.config.genes[random.choice(cats)])
                    keywords = [w for w in finding.split() if len(w) > 4]
                    if keywords:
                        q = f"{random.choice(keywords)} {gene}"
                        if q not in sources:
                            queries.append(q)
                            sources[q] = "pattern"

        # 60% from gene pool
        attempts = 0
        while len(queries) < n and attempts < n * 3:
            q = self._gen_from_genes()
            if q and q not in sources:
                queries.append(q)
                sources[q] = "gene"
            attempts += 1

        return queries[:n], sources

    def _gen_from_genes(self) -> str:
        cats = [k for k, v in self.config.genes.items() if v]
        if len(cats) < 2:
            return ""
        parts = [
            random.choice(self.config.genes[random.choice(cats)])
            for _ in range(random.randint(2, 3))
        ]
        return " ".join(parts)


# ============================================================
# SCORER
# ============================================================

class Scorer:
    """Scores search results with dedup and confidence."""

    def __init__(self):
        self.seen: set[str] = set()
        self.all_scores: list[int] = []

    def score_results(
        self, results: list[SearchResult]
    ) -> tuple[int, int, list[SearchResult]]:
        """Score with dedup. Returns (new_count, raw_score, new_results)."""
        new_results = [r for r in results if r.url not in self.seen]
        if not new_results:
            return 0, 0, []
        for r in new_results:
            self.seen.add(r.url)

        # Only count engagement from sources that provide it
        eng_results = [r for r in new_results if r.eng > 0]
        avg_eng = (sum(r.eng for r in eng_results) / len(eng_results)
                   if eng_results else 0)

        return len(new_results), int(len(new_results) * avg_eng), new_results

    @staticmethod
    def compute_adjusted_score(raw_score: int,
                               relevance_ratio: float) -> int:
        """40% engagement + 60% relevance."""
        normalized_eng = min(raw_score / 10000, 1.0) if raw_score > 0 else 0
        return int((0.4 * normalized_eng + 0.6 * relevance_ratio) * 10000)

    def mad_confidence(self) -> Optional[float]:
        """MAD-based confidence (from pi-autoresearch)."""
        if len(self.all_scores) < 3:
            return None
        median = statistics.median(self.all_scores)
        mad = statistics.median(
            [abs(s - median) for s in self.all_scores])
        if mad == 0:
            return None
        best = max(self.all_scores)
        return round((best - median) / mad, 1)


# ============================================================
# SESSION DOCUMENT
# ============================================================

class SessionDoc:
    """Writes session document (atomic writes)."""

    def __init__(self, path: Path):
        self.path = path

    def init(self, config: EngineConfig, llm_enabled: bool):
        content = (
            f"# AutoSearch Session: {config.task_name}\n\n"
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"**Target**: {config.target_spec}\n"
            f"**Platforms**: "
            f"{', '.join(p['name'] for p in config.platforms)}\n"
            f"**LLM evaluation**: {'ON' if llm_enabled else 'OFF'}\n"
            f"**Genes**: {json.dumps(config.genes, ensure_ascii=False)}\n\n"
            f"---\n\n## Phase 1: Exploration\n\n"
        )
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(self.path)

    def append(self, text: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text)


# ============================================================
# ENGINE — orchestrates all 3 phases
# ============================================================

class Engine:
    """AutoSearch engine. Call run() to execute all 3 phases."""

    def __init__(self, config: EngineConfig, base_dir: Path):
        self.config = config
        self.base_dir = base_dir
        self.patterns = PatternStore(base_dir / "patterns.jsonl")
        self.evolution_path = base_dir / "evolution.jsonl"
        self.llm = LLMEvaluator(model=config.llm_model)
        self.query_gen = QueryGenerator(config, self.patterns)
        self.scorer = Scorer()
        self.session_doc = SessionDoc(
            base_dir / f"{config.task_name}.md")

        # State accumulated during run
        self.all_experiments: list[Experiment] = []
        self.search_events: list[dict[str, Any]] = []

    def run(self) -> dict:
        """Execute all 3 phases. Returns summary dict."""
        self.session_doc.init(self.config, self.llm.enabled)

        top_queries = self._phase1_explore()
        harvest_count = self._phase2_harvest(top_queries)
        postmortem = self._phase3_postmortem()

        summary = {
            "run_id": self.config.run_id,
            "experiments": len(self.all_experiments),
            "unique_urls": len(self.scorer.seen),
            "harvested": harvest_count,
            "patterns_written": postmortem["patterns_written"],
            "confidence": self.scorer.mad_confidence(),
            "session_doc": str(self.session_doc.path),
        }

        print(f"\n{'=' * 60}")
        print("DONE. Next run will read these patterns and start smarter.")
        print(f"  Session doc: {self.session_doc.path}")
        print(f"{'=' * 60}")

        return summary

    # --- Phase 1: Explore ---

    def _phase1_explore(self) -> list[Experiment]:
        print("=" * 60)
        print("PHASE 1: Query Exploration")
        print(f"  Past patterns loaded: {len(self.patterns.use_patterns)} "
              f"positive, {len(self.patterns.avoid_patterns)} negative")
        print(f"  LLM evaluation: "
              f"{'ON' if self.llm.enabled else 'OFF (no ANTHROPIC_API_KEY)'}")
        print(f"  Platforms: "
              f"{', '.join(p['name'] for p in self.config.platforms)}")
        print("=" * 60)

        history_best_raw = 0
        history_best_relevance = 0.0
        stale = 0

        for rnd in range(1, self.config.max_rounds + 1):
            queries, query_sources = self.query_gen.generate()
            round_best_raw = 0
            round_new_total = 0
            round_all_results: list[SearchResult] = []

            for q in queries:
                query_family = self._query_family_for_query(q)
                results = self._search_all_platforms(q, query_family)
                new_count, raw_score, new_results = (
                    self.scorer.score_results(results))
                round_new_total += new_count
                round_all_results.extend(new_results)

                exp = Experiment(
                    round=rnd, query=q, query_family=query_family,
                    new=new_count, score=raw_score,
                    source=query_sources.get(q, "gene"),
                    sample_titles=[r.title[:60] for r in new_results[:3]],
                )
                self.all_experiments.append(exp)
                self.scorer.all_scores.append(raw_score)
                if raw_score > round_best_raw:
                    round_best_raw = raw_score

            # LLM evaluation
            relevance_ratio = 0.0
            llm_suggestions: list[str] = []
            llm_result = None
            if round_all_results:
                top10 = sorted(
                    round_all_results, key=lambda r: r.eng, reverse=True
                )[:10]
                llm_result = self.llm.evaluate_round(
                    top10, self.config.target_spec)
                if llm_result:
                    relevant_count = sum(
                        1 for r in llm_result.get("results", [])
                        if r.get("relevant"))
                    total_evaluated = len(llm_result.get("results", []))
                    relevance_ratio = (
                        relevant_count / max(total_evaluated, 1))
                    llm_suggestions = llm_result.get("next_queries", [])
                    self.query_gen.add_llm_suggestions(llm_suggestions)

            # Adjusted score
            round_adjusted = Scorer.compute_adjusted_score(
                round_best_raw, relevance_ratio)
            for e in self.all_experiments:
                if e.round == rnd:
                    e.adjusted_score = Scorer.compute_adjusted_score(
                        e.score, relevance_ratio)

            # Stale tracking
            llm_succeeded = self.llm.enabled and llm_result is not None
            if llm_succeeded:
                rel_delta = ((relevance_ratio - history_best_relevance)
                             / max(history_best_relevance, 0.01))
                if relevance_ratio > history_best_relevance:
                    history_best_relevance = relevance_ratio
                stale = stale + 1 if rel_delta < 0.1 else 0
            else:
                raw_delta = ((round_best_raw - history_best_raw)
                             / max(history_best_raw, 1))
                if round_best_raw > history_best_raw:
                    history_best_raw = round_best_raw
                stale = stale + 1 if raw_delta < 0.1 else 0

            conf = self.scorer.mad_confidence() or "n/a"
            rel_str = (f"rel={relevance_ratio:.0%} "
                       if self.llm.enabled else "")
            print(
                f"  R{rnd:2d}: adj={round_adjusted:6d} "
                f"raw={round_best_raw:6d} "
                f"new={round_new_total:3d} "
                f"seen={len(self.scorer.seen):4d} "
                f"stale={stale}/{self.config.max_stale} "
                f"{rel_str}conf={conf}"
            )

            # Session doc
            llm_line = (f"\n- LLM suggestions: {llm_suggestions}"
                        if llm_suggestions else "")
            self.session_doc.append(
                f"### Round {rnd}\n"
                f"- Queries: {len(queries)} | New URLs: {round_new_total}"
                f" | Raw best: {round_best_raw}"
                f" | Adjusted: {round_adjusted}\n"
                f"- Relevance: {relevance_ratio:.0%}"
                f" | Stale: {stale}/{self.config.max_stale}\n"
                f"- Top query: `{queries[0] if queries else 'n/a'}`"
                f"{llm_line}\n\n"
            )

            if stale >= self.config.max_stale:
                print(f"  >>> EARLY STOP after {rnd} rounds")
                self.session_doc.append(
                    f"**EARLY STOP** after {rnd} rounds "
                    f"(stale={stale})\n\n")
                break

        top_queries = sorted(
            self.all_experiments,
            key=lambda x: x.adjusted_score, reverse=True,
        )[:20]

        print(f"\nTop 5 queries:")
        for q in top_queries[:5]:
            src_tag = (f" [{q.source}]" if q.source != "gene" else "")
            print(f"  score={q.score:6d} new={q.new:2d}"
                  f"{src_tag:9s} | {q.query[:50]}")

        self.session_doc.append(
            "## Top Queries\n\n"
            "| # | Query | Score | New | Source |\n"
            "|---|-------|-------|-----|--------|\n"
            + "\n".join(
                f"| {i+1} | {q.query[:50]} | {q.score} "
                f"| {q.new} | {q.source} |"
                for i, q in enumerate(top_queries[:10])
            )
            + "\n\n"
        )

        return top_queries

    # --- Phase 2: Harvest ---

    def _phase2_harvest(self, top_queries: list[Experiment]) -> int:
        print(f"\n{'=' * 60}")
        print("PHASE 2: Harvest")
        print(f"{'=' * 60}")

        harvest_seen: set[str] = set()
        total_harvested = 0

        for q_entry in top_queries[:15]:
            results = self._search_all_platforms(q_entry.query, q_entry.query_family)
            new = 0
            for r in results:
                if r.url in harvest_seen:
                    continue
                if r.created and r.created < self.config.harvest_since:
                    continue
                if r.eng < 5 and r.source not in ("exa", "twitter"):
                    continue
                harvest_seen.add(r.url)
                with open(self.config.output_path, "a") as f:
                    f.write(json.dumps({
                        "url": r.url,
                        "title": r.title[:150],
                        "engagement": r.eng,
                        "created": r.created,
                        "body": r.body[:500],
                        "query": q_entry.query,
                        "query_family": q_entry.query_family,
                        "source": r.source,
                        "collected": datetime.now().strftime("%Y-%m-%d"),
                    }, ensure_ascii=False) + "\n")
                q_entry.harvested_urls.append(r.url)
                new += 1
            total_harvested += new

        print(f"  Harvested: {total_harvested} findings "
              f"-> {self.config.output_path}")

        self.session_doc.append(
            f"## Phase 2: Harvest\n\n"
            f"- Queries used: {min(len(top_queries), 15)}\n"
            f"- Findings harvested: {total_harvested}\n"
            f"- Output: `{self.config.output_path}`\n\n"
        )

        return total_harvested

    # --- Phase 3: Post-mortem ---

    def _phase3_postmortem(self) -> dict:
        print(f"\n{'=' * 60}")
        print("PHASE 3: Post-Mortem (self-evolution)")
        print(f"{'=' * 60}")

        winners = [e for e in self.all_experiments if e.score > 0]
        losers = [e for e in self.all_experiments if e.score == 0]

        print(f"  Total experiments: {len(self.all_experiments)}")
        print(f"  Winners: {len(winners)} "
              f"({len(winners) * 100 // max(len(self.all_experiments), 1)}%)")
        print(f"  Losers: {len(losers)} "
              f"({len(losers) * 100 // max(len(self.all_experiments), 1)}%)")

        # Source performance
        def _source_stats(tag):
            exps = [e for e in self.all_experiments if e.source == tag]
            wins = [e for e in exps if e.score > 0]
            rate = len(wins) / max(len(exps), 1)
            return len(wins), len(exps), rate

        llm_w, llm_t, llm_rate = _source_stats("llm")
        pat_w, pat_t, pat_rate = _source_stats("pattern")
        gen_w, gen_t, gen_rate = _source_stats("gene")

        print(f"\n  Source performance:")
        print(f"    LLM:     {llm_w}/{llm_t} ({llm_rate:.0%})")
        print(f"    Pattern: {pat_w}/{pat_t} ({pat_rate:.0%})")
        print(f"    Gene:    {gen_w}/{gen_t} ({gen_rate:.0%})")

        # Extract winning/losing words
        word_in_winners: dict[str, int] = {}
        word_in_losers: dict[str, int] = {}
        for e in winners:
            for w in e.query.lower().split():
                if len(w) > 3:
                    word_in_winners[w] = word_in_winners.get(w, 0) + 1
        for e in losers:
            for w in e.query.lower().split():
                if len(w) > 3:
                    word_in_losers[w] = word_in_losers.get(w, 0) + 1

        winning_words = [
            (w, c) for w, c in word_in_winners.items()
            if c >= 3 and c > word_in_losers.get(w, 0) * 2
        ]
        losing_words = [
            (w, c) for w, c in word_in_losers.items()
            if c >= 3 and word_in_winners.get(w, 0) == 0
        ]

        # Write new patterns
        new_patterns = []
        timestamp = datetime.now().strftime("%Y-%m-%d")

        if winning_words:
            top_winning = sorted(
                winning_words, key=lambda x: x[1], reverse=True)[:5]
            new_patterns.append({
                "pattern": f"winning_words_{timestamp}",
                "platform": "all",
                "finding": ("Words that correlate with high-scoring queries: "
                            + ", ".join(w for w, c in top_winning)),
                "impact": "Use these words when generating queries",
                "validated": timestamp,
                "auto_generated": True,
            })

        if losing_words:
            top_losing = sorted(
                losing_words, key=lambda x: x[1], reverse=True)[:5]
            new_patterns.append({
                "pattern": f"losing_words_{timestamp}",
                "platform": "all",
                "finding": ("Words that ONLY appear in failed queries: "
                            + ", ".join(w for w, c in top_losing)
                            + ". Avoid these."),
                "impact": "These words don't produce results",
                "validated": timestamp,
                "auto_generated": True,
            })

        # LLM win rate pattern
        if self.llm.enabled and llm_t > 0:
            new_patterns.append({
                "pattern": f"llm_win_rate_{timestamp}",
                "platform": "all",
                "finding": (
                    f"LLM-suggested queries win rate: "
                    f"{llm_rate:.0%} ({llm_w}/{llm_t}). "
                    f"Pattern: {pat_rate:.0%} ({pat_w}/{pat_t}). "
                    f"Gene: {gen_rate:.0%} ({gen_w}/{gen_t})."
                ),
                "impact": "Adjust LLM query quota based on performance",
                "validated": timestamp,
                "auto_generated": True,
            })

        # Session stats
        conf_final = self.scorer.mad_confidence()
        new_patterns.append({
            "pattern": f"session_stats_{timestamp}",
            "platform": "all",
            "finding": (
                f"Session: {len(self.all_experiments)} queries, "
                f"{len(winners)} winners "
                f"({len(winners) * 100 // max(len(self.all_experiments), 1)}%), "
                f"{len(self.scorer.seen)} unique URLs, "
                f"confidence={conf_final}"
            ),
            "impact": "Baseline for next session comparison",
            "validated": timestamp,
            "auto_generated": True,
        })

        self.patterns.append(new_patterns)

        print(f"\n  NEW PATTERNS WRITTEN ({len(new_patterns)}):")
        for p in new_patterns:
            print(f"    [{p['pattern']}] {p['finding'][:70]}")

        # Evolution log
        with open(self.evolution_path, "a") as f:
            for e in self.all_experiments:
                e.session = timestamp
                f.write(json.dumps({
                    "round": e.round, "query": e.query,
                    "query_family": e.query_family,
                    "new": e.new, "score": e.score,
                    "adjusted_score": e.adjusted_score,
                    "source": e.source,
                    "sample_titles": e.sample_titles,
                    "harvested_urls": e.harvested_urls,
                    "session": e.session,
                }, ensure_ascii=False) + "\n")

        total_patterns = self.patterns.total_count()
        print(f"\n  Total patterns in library: {total_patterns}")

        # Session doc
        ww_str = (", ".join(
            w for w, c in sorted(
                winning_words, key=lambda x: x[1], reverse=True)[:10])
            if winning_words else "None")
        lw_str = (", ".join(
            w for w, c in sorted(
                losing_words, key=lambda x: x[1], reverse=True)[:10])
            if losing_words else "None")

        self.session_doc.append(
            f"## Phase 3: Post-Mortem\n\n"
            f"### Experiment Classification\n"
            f"- Total: {len(self.all_experiments)} | "
            f"Winners: {len(winners)} "
            f"({len(winners) * 100 // max(len(self.all_experiments), 1)}%)"
            f" | Losers: {len(losers)}\n\n"
            f"### Source Performance\n\n"
            f"| Source | Winners | Total | Win Rate |\n"
            f"|--------|---------|-------|----------|\n"
            f"| LLM | {llm_w} | {llm_t} | {llm_rate:.0%} |\n"
            f"| Pattern | {pat_w} | {pat_t} | {pat_rate:.0%} |\n"
            f"| Gene | {gen_w} | {gen_t} | {gen_rate:.0%} |\n\n"
            f"### Winning Words\n{ww_str}\n\n"
            f"### Losing Words\n{lw_str}\n\n"
            f"### New Patterns Written\n"
            + "\n".join(
                f'- [{p["pattern"]}] {p["finding"][:80]}'
                for p in new_patterns)
            + f"\n\n### Stats\n"
            f"- Unique URLs: {len(self.scorer.seen)}\n"
            f"- MAD Confidence: {conf_final}\n"
            f"- Patterns in library: {total_patterns}\n"
        )

        return {"patterns_written": len(new_patterns)}

    # --- Helpers ---

    def _query_family_for_query(self, query: str) -> str:
        exact = str((self.config.query_family_map or {}).get(query, ""))
        if exact:
            return exact

        word_map = self.config.query_family_word_map or {}
        hits: dict[str, int] = {}
        for word in query.lower().split():
            for family in word_map.get(word, []):
                hits[family] = hits.get(family, 0) + 1
        if hits:
            return max(hits, key=hits.get)
        return "unknown"

    def _ordered_platforms(self, query_family: str) -> list[dict[str, Any]]:
        ranked: list[tuple[tuple[int, str], dict[str, Any]]] = []
        for platform in self.config.platforms:
            provider = str(platform.get("name") or "")
            capability = get_source_decision(
                self.config.capability_report,
                provider,
            )
            decision = get_provider_decision(
                self.config.experience_policy,
                provider,
                query_family,
            )
            ranked.append(((capability["priority"], decision["priority"], provider), platform))
        return [platform for _, platform in sorted(ranked, key=lambda item: item[0])]

    def _record_search_event(
        self,
        *,
        provider: str,
        query_family: str,
        attempts: int,
        results: int,
        new_urls: int,
        errors: int,
    ) -> None:
        self.search_events.append({
            "aspect": "search",
            "run_id": self.config.run_id,
            "timestamp": datetime.now().astimezone().isoformat(),
            "provider": provider,
            "query_family": query_family,
            "attempts": attempts,
            "results": results,
            "new_urls": new_urls,
            "errors": errors,
        })

    def _search_all_platforms(self, query: str, query_family: str) -> list[SearchResult]:
        all_results: list[SearchResult] = []
        query_seen = set(self.scorer.seen)
        for plat in self._ordered_platforms(query_family):
            provider = str(plat.get("name") or "")
            capability = get_source_decision(
                self.config.capability_report,
                provider,
            )
            if capability["should_skip"]:
                continue
            decision = get_provider_decision(
                self.config.experience_policy,
                provider,
                query_family,
            )
            if decision["should_skip"]:
                continue

            outcome = PlatformConnector.search(plat, query)
            if outcome.error_alias:
                self._record_search_event(
                    provider=outcome.error_alias,
                    query_family=query_family,
                    attempts=1,
                    results=0,
                    new_urls=0,
                    errors=1,
                )
                time.sleep(0.15)
                continue

            new_urls = 0
            for result in outcome.results:
                if result.url and result.url not in query_seen:
                    query_seen.add(result.url)
                    new_urls += 1
            self._record_search_event(
                provider=provider,
                query_family=query_family,
                attempts=1,
                results=len(outcome.results),
                new_urls=new_urls,
                errors=0,
            )
            all_results.extend(outcome.results)
            time.sleep(0.15)
        return all_results
