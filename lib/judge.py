from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_WEIGHTS = {
    "rubric_pass_rate": 0.30,
    "groundedness": 0.20,
    "relevant_yield": 0.15,
    "content_depth": 0.15,
    "source_diversity": 0.10,
    "quantity": 0.10,
}
WORD_RE = re.compile(r"\w+")
HTML_CITATION_RE = re.compile(
    r'<li\b[^>]*\bid="ref-\d+"[^>]*>[\s\S]*?<a\b[^>]*\bhref="([^"]+)"',
    re.IGNORECASE,
)
MARKDOWN_CITATION_RE = re.compile(r"\[(\d+)\]\((https?://[^)\s]+)\)")
# [N] Title — URL  (common in AutoSearch .md deliveries)
MARKDOWN_PLAIN_CITATION_RE = re.compile(
    r"^\[(\d+)\]\s+.+?\s+—\s+(https?://\S+)", re.MULTILINE
)
NEUTRAL_DIMENSION_SCORE = 0.5


def clamp_score(value: float) -> float:
    return max(0.0, min(value, 1.0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_file")
    parser.add_argument("--target", type=int, default=30)
    parser.add_argument("--weights")
    return parser.parse_args()


def candidate_state_dirs(evidence_file: str | Path | None) -> list[Path]:
    candidates: list[Path] = []
    if evidence_file is not None:
        evidence_path = Path(evidence_file)
        candidates.append(evidence_path.parent / "state")
        if evidence_path.parent.name == "evidence":
            candidates.append(evidence_path.parent.parent / "state")
    candidates.append(Path(__file__).with_name("state"))

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(candidate)
    return unique_candidates


def load_state_json(evidence_file: str | Path | None, filename: str) -> dict | None:
    for state_dir in candidate_state_dirs(evidence_file):
        path = state_dir / filename
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def load_state_jsonl(evidence_file: str | Path | None, filename: str) -> list[dict]:
    for state_dir in candidate_state_dirs(evidence_file):
        path = state_dir / filename
        try:
            with path.open(encoding="utf-8") as handle:
                rows: list[dict] = []
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        rows.append(payload)
        except OSError:
            continue
        return rows
    return []


def coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_scoring_config(evidence_file: str | Path | None = None) -> dict[str, object]:
    config = load_state_json(evidence_file, "config.json") or {}
    scoring = config.get("scoring") if isinstance(config, dict) else {}
    if not isinstance(scoring, dict):
        scoring = {}

    weights = DEFAULT_WEIGHTS.copy()
    configured_weights = scoring.get("dimension_weights")
    if isinstance(configured_weights, dict):
        for name in weights:
            if name in configured_weights:
                weights[name] = coerce_float(configured_weights[name], weights[name])

    return {"dimension_weights": weights}


def load_default_weights(evidence_file: str | Path | None = None) -> dict[str, float]:
    return load_scoring_config(evidence_file)["dimension_weights"].copy()


def load_results(path: Path) -> list[dict]:
    results = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON line {line_no}", file=sys.stderr)
                continue
            if isinstance(item, dict):
                results.append(item)
    return results


def parse_date(value: object) -> dt.datetime | None:
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def score_rubric_pass_rate(evidence_file: str) -> float:
    history = load_state_jsonl(evidence_file, "rubric-history.jsonl")
    if not history:
        return 0.0

    latest_entry: dict | None = None
    latest_timestamp: dt.datetime | None = None
    for entry in history:
        parsed = parse_date(entry.get("timestamp"))
        if parsed is None:
            continue
        if latest_timestamp is None or parsed > latest_timestamp:
            latest_timestamp = parsed
            latest_entry = entry

    if latest_entry is None:
        return 0.0

    if "pass_rate" in latest_entry:
        return clamp_score(coerce_float(latest_entry.get("pass_rate"), 0.0))

    total = coerce_float(latest_entry.get("total"), 0.0)
    passed = coerce_float(latest_entry.get("passed"), 0.0)
    if total <= 0:
        return 0.0
    return clamp_score(passed / total)


def candidate_delivery_dirs(evidence_file: str | Path) -> list[Path]:
    evidence_path = Path(evidence_file)
    candidates = [
        evidence_path.parent.parent / "delivery",
        evidence_path.parent.parent.parent / "delivery",
        evidence_path.parent / "delivery",
    ]

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(candidate)
    return unique_candidates


def find_latest_delivery_file(evidence_file: str | Path) -> Path | None:
    evidence_name = Path(
        evidence_file
    ).stem  # e.g. "20260404-ai-code-review-tools-results"
    # Strip common suffixes to get the session slug
    session_slug = evidence_name
    for suffix in ("-results", "-claims", "-search-errors"):
        if session_slug.endswith(suffix):
            session_slug = session_slug[: -len(suffix)]
            break

    # First pass: try to match by session slug prefix
    for delivery_dir in candidate_delivery_dirs(evidence_file):
        if not delivery_dir.is_dir():
            continue
        for path in delivery_dir.iterdir():
            if not path.is_file():
                continue
            if path.stem.startswith(session_slug):
                return path

    # Fallback: most recently modified file
    latest_file: Path | None = None
    latest_mtime = -1.0
    for delivery_dir in candidate_delivery_dirs(evidence_file):
        if not delivery_dir.is_dir():
            continue
        for path in delivery_dir.iterdir():
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = path
    return latest_file


def extract_citation_urls(delivery_file: Path) -> list[str]:
    try:
        content = delivery_file.read_text(encoding="utf-8")
    except OSError:
        return []

    urls = HTML_CITATION_RE.findall(content)
    urls.extend(match[1] for match in MARKDOWN_CITATION_RE.findall(content))
    urls.extend(match[1] for match in MARKDOWN_PLAIN_CITATION_RE.findall(content))
    return urls


def score_groundedness(evidence_file: str, results: list[dict]) -> float:
    delivery_file = find_latest_delivery_file(evidence_file)
    if delivery_file is None:
        return 0.0

    citation_urls = extract_citation_urls(delivery_file)
    if not citation_urls:
        return 0.0

    evidence_urls = {item.get("url") for item in results if item.get("url")}
    grounded_count = sum(1 for url in citation_urls if url in evidence_urls)
    return clamp_score(grounded_count / len(citation_urls))


def score_content_depth(results: list[dict]) -> float:
    total_results = len(results)
    if total_results == 0:
        return 0.0

    with_content = 0
    for item in results:
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        extracted_content = metadata.get("extracted_content")
        if isinstance(extracted_content, str) and extracted_content.strip():
            with_content += 1
    return clamp_score(with_content / total_results)


def score_relevant_yield(results: list[dict]) -> float:
    total_results = len(results)
    if total_results == 0:
        return 0.0

    queries = {
        str(item.get("query", "")).strip()
        for item in results
        if str(item.get("query", "")).strip()
    }
    query_words = {word.lower() for query in queries for word in WORD_RE.findall(query)}

    relevant_count = 0
    for item in results:
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        if "llm_relevant" in metadata:
            if metadata.get("llm_relevant") is True:
                relevant_count += 1
            continue

        haystack_words = {
            word.lower()
            for word in WORD_RE.findall(
                f"{item.get('title', '')} {item.get('snippet', '')}"
            )
        }
        if query_words and haystack_words.intersection(query_words):
            relevant_count += 1
    return clamp_score(relevant_count / total_results)


def score_source_diversity(results: list[dict]) -> float:
    if not results:
        return 0.0

    has_llm_relevant = False
    relevant_results: list[dict] = []
    for item in results:
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        if "llm_relevant" in metadata:
            has_llm_relevant = True
            if metadata.get("llm_relevant") is True:
                relevant_results.append(item)

    scored_results = relevant_results if has_llm_relevant else results
    platforms = [
        str(item.get("source", "")).lower()
        for item in scored_results
        if item.get("source")
    ]
    total_results = len(platforms)
    if total_results <= 1:
        return 0.0

    counts = Counter(platforms)
    if len(counts) <= 1:
        return 0.0

    numerator = sum(count * (count - 1) for count in counts.values())
    return clamp_score(1.0 - (numerator / (total_results * (total_results - 1))))


def score_results(
    results: list[dict],
    evidence_file: str,
    target: int = 30,
    weights: dict[str, float] | None = None,
    now: dt.datetime | None = None,
) -> dict:
    scoring_config = load_scoring_config(evidence_file)
    weights = weights or scoring_config["dimension_weights"]
    now = now or dt.datetime.now(dt.timezone.utc)

    total_results = len(results)
    unique_urls = {item.get("url") for item in results if item.get("url")}
    queries = {
        str(item.get("query", "")).strip()
        for item in results
        if str(item.get("query", "")).strip()
    }
    platforms = [
        str(item.get("source", "")).lower() for item in results if item.get("source")
    ]
    counts = Counter(platforms)

    dimensions = {
        "rubric_pass_rate": score_rubric_pass_rate(evidence_file),
        "groundedness": score_groundedness(evidence_file, results),
        "relevant_yield": score_relevant_yield(results),
        "content_depth": score_content_depth(results),
        "source_diversity": score_source_diversity(results),
        "quantity": clamp_score(min(len(unique_urls) / max(target, 1), 1.0)),
    }
    weight_sum = sum(float(weights.get(name, 0.0)) for name in dimensions)
    total = (
        sum(dimensions[name] * float(weights.get(name, 0.0)) for name in dimensions)
        / weight_sum
        if weight_sum > 0
        else 0.0
    )
    return {
        "total": clamp_score(total),
        "dimensions": {name: clamp_score(value) for name, value in dimensions.items()},
        "meta": {
            "total_results": total_results,
            "unique_urls": len(unique_urls),
            "platforms": sorted(counts),
            "target": target,
            "queries_used": len(queries),
            "evidence_file": evidence_file,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        weights = (
            json.loads(args.weights)
            if args.weights
            else load_default_weights(args.evidence_file)
        )
        results = load_results(Path(args.evidence_file))
        payload = score_results(
            results, args.evidence_file, target=args.target, weights=weights
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
