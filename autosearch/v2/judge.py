import argparse
from collections import Counter
import datetime as dt
import json
import re
import sys
from pathlib import Path


DEFAULT_WEIGHTS = {
    "quantity": 0.2,
    "diversity": 0.2,
    "relevance": 0.3,
    "freshness": 0.15,
    "efficiency": 0.15,
}
WORD_RE = re.compile(r"\w+")
DATE_FIELDS = ("published_at", "created_utc", "updated_at")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_file")
    parser.add_argument("--target", type=int, default=30)
    parser.add_argument("--weights")
    return parser.parse_args()


def load_default_weights() -> dict[str, float]:
    config_path = Path(__file__).with_name("state").joinpath("config.json")
    try:
        with config_path.open(encoding="utf-8") as handle:
            config = json.load(handle)
        return config["scoring"]["dimension_weights"]
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_WEIGHTS.copy()


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


def score_results(
    results: list[dict],
    evidence_file: str,
    target: int = 30,
    weights: dict[str, float] | None = None,
    now: dt.datetime | None = None,
) -> dict:
    weights = weights or load_default_weights()
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
    query_words = {word.lower() for query in queries for word in WORD_RE.findall(query)}

    quantity = min(len(unique_urls) / max(target, 1), 1.0)
    if total_results <= 1:
        diversity = 0.0
    else:
        numerator = sum(count * (count - 1) for count in counts.values())
        diversity = 1.0 - (numerator / (total_results * (total_results - 1)))

    match_count = 0
    for item in results:
        haystack_words = {
            word.lower()
            for word in WORD_RE.findall(
                f"{item.get('title', '')} {item.get('snippet', '')}"
            )
        }
        if query_words and haystack_words.intersection(query_words):
            match_count += 1
    relevance = match_count / total_results if total_results else 0.0

    fresh_cutoff = now - dt.timedelta(days=183)
    fresh_count = 0
    for item in results:
        metadata = item.get("metadata") or {}
        parsed = None
        for name in DATE_FIELDS:
            parsed = parse_date(metadata.get(name))
            if parsed:
                break
        if parsed and parsed >= fresh_cutoff:
            fresh_count += 1
    freshness = fresh_count / total_results if total_results else 0.0

    efficiency = min(len(unique_urls) / max(len(queries) * 3, 1), 1.0)
    dimensions = {
        "quantity": quantity,
        "diversity": diversity,
        "relevance": relevance,
        "freshness": freshness,
        "efficiency": efficiency,
    }
    weight_sum = sum(float(weights.get(name, 0.0)) for name in dimensions)
    total = (
        sum(dimensions[name] * float(weights.get(name, 0.0)) for name in dimensions)
        / weight_sum
        if weight_sum > 0
        else 0.0
    )
    return {
        "total": max(0.0, min(total, 1.0)),
        "dimensions": {
            name: max(0.0, min(value, 1.0)) for name, value in dimensions.items()
        },
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
        weights = json.loads(args.weights) if args.weights else load_default_weights()
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
