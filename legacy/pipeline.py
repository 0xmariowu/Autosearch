#!/usr/bin/env python3
"""
AutoSearch Pipeline — unified daily run.

Chains: engine (daily mode) → format adapter → score-and-stage.js →
        auto-intake.sh → send-email.sh

Single entry point replacing scout.sh for launchd scheduling.

Usage:
  python pipeline.py                     # full daily run
  python pipeline.py --skip-email        # skip email sending
  python pipeline.py --skip-intake       # skip auto-intake
  python pipeline.py --engine-only       # only run engine, skip downstream
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ── Paths ──

HOME = Path.home()


# Support override via env vars (for launchd rsync mode)
ARMORY_ROOT = Path(os.environ.get("ARMORY_ROOT", "/Users/vimala/Armory"))
AIMD_ROOT = Path(os.environ.get("AIMD_ROOT", "/Users/vimala/AIMD"))
SCOUT_DIR = Path(os.environ.get("SCOUT_DIR", str(ARMORY_ROOT / "scripts/scout")))
AUTOSEARCH_DIR = Path(__file__).parent

# score-and-stage.js dependencies
STATE_PATH = SCOUT_DIR / "state.json"
ARMORY_INDEX = ARMORY_ROOT / "armory-index.json"
QUERIES_PATH = SCOUT_DIR / "queries.json"
OUTPUT_DIR = AIMD_ROOT / "ai-recommendations"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Step 1: Run engine (daily mode) ──


def run_engine(skip_health_check: bool = False) -> Path:
    """Run daily.py and return path to findings JSONL."""
    log("Phase 1: Running AutoSearch engine (daily mode)...")

    today = datetime.now().strftime("%Y-%m-%d")
    output = Path(f"/tmp/autosearch-daily-{today}.jsonl")

    cmd = [
        sys.executable,
        str(AUTOSEARCH_DIR / "daily.py"),
        "--output",
        str(output),
    ]
    if skip_health_check:
        cmd.append("--skip-health-check")

    try:
        result = subprocess.run(cmd, cwd=str(AUTOSEARCH_DIR), timeout=1800)
    except subprocess.TimeoutExpired:
        log("ERROR: Engine timed out after 30 minutes")
        sys.exit(1)

    if result.returncode != 0:
        log("ERROR: Engine failed")
        sys.exit(1)

    if not output.exists() or output.stat().st_size == 0:
        log("WARN: Engine produced no findings")
        return output

    count = sum(1 for line in output.read_text().splitlines() if line.strip())
    log(f"  Engine produced {count} findings")
    return output


# ── Step 2: Adapt engine output to score-and-stage format ──


def adapt_findings(findings_path: Path, raw_dir: Path):
    """Convert engine JSONL to per-platform JSONL files for score-and-stage.js.

    Engine format: {url, title, engagement, created, body, query, source, collected}
    Score-and-stage expects per-platform fields. We map `source` to platform
    and synthesize the expected fields.
    """
    log("Phase 2: Adapting findings for score-and-stage...")

    if not findings_path.exists():
        log("  No findings to adapt")
        return

    # Buckets: one JSONL per platform
    buckets: dict[str, list[dict]] = {}

    for line in findings_path.read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        source = item.get("source", "")
        adapted = _adapt_item(item, source)
        if adapted:
            platform = adapted["platform"]
            if platform not in buckets:
                buckets[platform] = []
            buckets[platform].append(adapted)

    # Write per-platform files
    for platform, items in buckets.items():
        outfile = raw_dir / f"{platform}.jsonl"
        with open(outfile, "w") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        log(f"  {platform}: {len(items)} items")


def _adapt_item(item: dict, source: str) -> dict | None:
    """Convert one engine finding to score-and-stage format."""

    url = item.get("url", "")
    title = item.get("title", "")
    eng = item.get("engagement", 0)
    created = item.get("created", "")
    body = item.get("body", "")
    query = item.get("query", "")

    if source in ("github_repos",):
        return {
            "platform": "github",
            "url": url,
            "title": title,  # "owner/name" format from engine
            "description": body,
            "stars": eng,
            "language": "",  # not available from engine harvest
            "created": created,
            "updated": created,  # best approximation
            "archived": False,
            "topic_group": _infer_topic(query),
            "query": query,
        }

    if source in ("github_issues",):
        # GitHub issues → scored as articles (scoreExa in score-and-stage.js
        # uses domain authority + freshness + title quality, no special fields)
        return {
            "platform": "exa",
            "url": url,
            "title": title,
            "author": "",
            "published_date": created,
            "topic_group": _infer_topic(query),
            "query": query,
        }

    if source in ("twitter",):
        return {
            "platform": "twitter",
            "url": url,
            "title": title,
            "likes": eng,
            "retweets": 0,
            "created": created,
            "urls_in_tweet": [url] if url else [],
            "topic_group": _infer_topic(query),
            "query": query,
        }

    if source in ("exa",):
        return {
            "platform": "exa",
            "url": url,
            "title": title,
            "author": "",
            "published_date": created,
            "topic_group": _infer_topic(query),
            "query": query,
        }

    if source in ("reddit",):
        return {
            "platform": "reddit",
            "url": url,
            "title": title,
            "published_date": created,
            "topic_group": _infer_topic(query),
            "query": query,
        }

    if source in ("hn",):
        return {
            "platform": "hackernews",
            "url": url,
            "title": title,
            "published_date": created,
            "topic_group": _infer_topic(query),
            "query": query,
        }

    # Unknown source — map to exa (article) as fallback
    return {
        "platform": "exa",
        "url": url,
        "title": title,
        "author": "",
        "published_date": created,
        "topic_group": _infer_topic(query),
        "query": query,
    }


# Topic inference: match query words to known topic group IDs
_QUERY_MAP: dict[str, str] | None = None
_WORD_MAP: dict[str, list[str]] | None = None


def _load_topic_maps() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Build query->topic and word->topics mappings from queries.json."""
    global _QUERY_MAP, _WORD_MAP
    if _QUERY_MAP is not None:
        return _QUERY_MAP, _WORD_MAP

    _QUERY_MAP = {}
    _WORD_MAP = {}
    try:
        with open(QUERIES_PATH) as f:
            data = json.load(f)
        for group in data.get("topic_groups", []):
            gid = group["id"]
            for _plat, queries in group.get("queries", {}).items():
                for q in queries:
                    _QUERY_MAP[q.lower()] = gid
                    for word in q.lower().split():
                        if len(word) > 3:
                            if word not in _WORD_MAP:
                                _WORD_MAP[word] = []
                            if gid not in _WORD_MAP[word]:
                                _WORD_MAP[word].append(gid)
    except Exception as e:
        log(f"WARN: Could not load queries.json for topic inference: {e}")
    return _QUERY_MAP, _WORD_MAP


def _infer_topic(query: str) -> str:
    """Best-effort topic inference from query.

    Priority: exact query match > word-level vote.
    """
    query_map, word_map = _load_topic_maps()

    # Try exact match first
    ql = query.lower()
    if ql in query_map:
        return query_map[ql]

    # Word-level voting (each word can contribute to multiple topics)
    if not word_map:
        return "unknown"

    hits: dict[str, int] = {}
    for word in ql.split():
        for topic in word_map.get(word, []):
            hits[topic] = hits.get(topic, 0) + 1

    if hits:
        return max(hits, key=hits.get)
    return "unknown"


# ── Step 3: Score and stage ──


def run_score_and_stage(raw_dir: Path):
    """Run score-and-stage.js on adapted findings."""
    log("Phase 3: Scoring & staging...")

    cmd = [
        "node",
        str(SCOUT_DIR / "score-and-stage.js"),
        "--raw-dir",
        str(raw_dir),
        "--state",
        str(STATE_PATH),
        "--armory-index",
        str(ARMORY_INDEX),
        "--output",
        str(OUTPUT_DIR),
        "--queries",
        str(QUERIES_PATH),
    ]

    try:
        result = subprocess.run(cmd, cwd=str(SCOUT_DIR), timeout=300)
    except subprocess.TimeoutExpired:
        log("WARN: score-and-stage timed out after 5 minutes")
        return
    if result.returncode != 0:
        log("WARN: score-and-stage failed")


# ── Step 4: Auto-intake ──


def run_auto_intake():
    """Run auto-intake.sh for high-scoring repos."""
    log("Phase 4: Auto-intake...")

    cmd = ["bash", str(SCOUT_DIR / "auto-intake.sh")]
    try:
        result = subprocess.run(cmd, cwd=str(SCOUT_DIR), timeout=600)
    except subprocess.TimeoutExpired:
        log("WARN: auto-intake timed out after 10 minutes")
        return
    if result.returncode != 0:
        log("WARN: auto-intake failed")


# ── Step 5: Send email ──


def run_outcome_recording():
    """Record query→repo outcome links after auto-intake."""
    log("Phase 4b: Recording outcomes...")
    try:
        from outcomes import record_intakes

        count = record_intakes()
        log(f"  {count} new intake outcomes recorded")
    except Exception as e:
        log(f"WARN: outcome recording failed: {e}")


def run_email():
    """Send daily report email."""
    log("Phase 5: Sending email...")

    today = datetime.now().strftime("%Y-%m-%d")
    report = OUTPUT_DIR / f"{today}.md"

    # Load recipient from Scout .env
    recipient = "dickywum@gmail.com"
    env_file = SCOUT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("SCOUT_EMAIL_TO="):
                recipient = line.split("=", 1)[1].strip()

    cmd = [
        "bash",
        str(SCOUT_DIR / "send-email.sh"),
        str(report),
        recipient,
    ]
    try:
        result = subprocess.run(cmd, cwd=str(SCOUT_DIR), timeout=60)
    except subprocess.TimeoutExpired:
        log("WARN: email sending timed out after 60 seconds")
        return
    if result.returncode != 0:
        log("WARN: email sending failed")


# ── Main ──


def main():
    parser = argparse.ArgumentParser(
        description="AutoSearch Pipeline — unified daily run",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip email sending",
    )
    parser.add_argument(
        "--skip-intake",
        action="store_true",
        help="Skip auto-intake",
    )
    parser.add_argument(
        "--engine-only",
        action="store_true",
        help="Only run engine, skip all downstream",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip platform pre-flight checks",
    )
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    log(f"=== AutoSearch Pipeline: {today} ===")
    log("")

    # Step 1: Run engine
    findings_path = run_engine(skip_health_check=args.skip_health_check)

    if args.engine_only:
        log("Engine-only mode. Done.")
        return

    # Step 2: Adapt findings for score-and-stage
    raw_dir = Path(tempfile.mkdtemp(prefix="autosearch-raw-"))
    try:
        adapt_findings(findings_path, raw_dir)

        # Step 3: Score and stage
        run_score_and_stage(raw_dir)

    finally:
        shutil.rmtree(raw_dir, ignore_errors=True)

    # Step 4: Auto-intake
    if not args.skip_intake:
        run_auto_intake()
        # Record query→repo links for outcome tracking
        run_outcome_recording()

    # Step 5: Email
    if not args.skip_email:
        run_email()

    log("")
    log(f"Done. Report: {OUTPUT_DIR / f'{today}.md'}")


if __name__ == "__main__":
    main()
