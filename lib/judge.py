import argparse
from collections import Counter
import datetime as dt
import json
import re
import sys
from pathlib import Path


DEFAULT_WEIGHTS = {
    "quantity": 0.12,
    "diversity": 0.13,
    "relevance": 0.22,
    "freshness": 0.10,
    "efficiency": 0.10,
    "latency": 0.08,
    "adoption": 0.12,
    "knowledge_growth": 0.13,
}
WORD_RE = re.compile(r"\w+")
DATE_FIELDS = ("published_at", "created_utc", "updated_at")
DEFAULT_LATENCY_BUDGET_SECONDS = 120.0
NEUTRAL_DIMENSION_SCORE = 0.5


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

    latency_budget_seconds = coerce_float(
        scoring.get("latency_budget_seconds"), DEFAULT_LATENCY_BUDGET_SECONDS
    )
    if latency_budget_seconds <= 0:
        latency_budget_seconds = DEFAULT_LATENCY_BUDGET_SECONDS

    return {
        "dimension_weights": weights,
        "latency_budget_seconds": latency_budget_seconds,
    }


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


def score_latency(evidence_file: str, budget_seconds: float) -> float:
    timing = load_state_json(evidence_file, "timing.json")
    if not timing:
        return NEUTRAL_DIMENSION_SCORE

    start = parse_date(timing.get("start_ts"))
    end = parse_date(timing.get("end_ts"))
    if not start or not end:
        return NEUTRAL_DIMENSION_SCORE

    elapsed_seconds = max((end - start).total_seconds(), 0.0)
    return 1.0 - min(elapsed_seconds / budget_seconds, 1.0)


def score_adoption(evidence_file: str) -> float:
    adoption = load_state_json(evidence_file, "adoption.json")
    if not adoption:
        return NEUTRAL_DIMENSION_SCORE
    return max(
        0.0,
        min(coerce_float(adoption.get("score"), NEUTRAL_DIMENSION_SCORE), 1.0),
    )


def score_knowledge_growth(evidence_file: str) -> float:
    """Score cumulative knowledge growth across sessions.

    Reads state/knowledge-growth.json with fields:
    - initial_entries: knowledge map size at session start
    - final_entries: knowledge map size at session end
    - initial_gaps: GAP-tagged items at session start
    - remaining_gaps: GAP-tagged items at session end
    - high_confidence: HIGH-tagged items at session end

    Score = weighted combination of:
    - growth_ratio: new entries / max(initial, 1) (capped at 1.0 for 100% growth)
    - gap_closure: (initial_gaps - remaining_gaps) / max(initial_gaps, 1)
    - confidence_ratio: high_confidence / max(final_entries, 1)

    Returns NEUTRAL (0.5) when the file does not exist or has no meaningful data.
    """
    kg = load_state_json(evidence_file, "knowledge-growth.json")
    if not kg:
        return NEUTRAL_DIMENSION_SCORE

    initial = coerce_float(kg.get("initial_entries"), 0)
    final = coerce_float(kg.get("final_entries"), 0)
    initial_gaps = coerce_float(kg.get("initial_gaps"), 0)
    remaining_gaps = coerce_float(kg.get("remaining_gaps"), 0)
    high_confidence = coerce_float(kg.get("high_confidence"), 0)

    # No meaningful data yet — return neutral instead of penalizing
    if initial == 0 and final == 0 and initial_gaps == 0:
        return NEUTRAL_DIMENSION_SCORE

    # Growth: how much did the knowledge map expand?
    growth_ratio = (
        min((final - initial) / max(initial, 1), 1.0) if final > initial else 0.0
    )

    # Gap closure: how many unknowns were resolved?
    gap_closure = (
        (initial_gaps - remaining_gaps) / max(initial_gaps, 1)
        if initial_gaps > remaining_gaps
        else 0.0
    )

    # Confidence: what fraction of knowledge is HIGH confidence?
    confidence_ratio = high_confidence / max(final, 1) if final > 0 else 0.0

    # Weighted combination: gap closure most important, then confidence, then growth
    return 0.4 * gap_closure + 0.35 * confidence_ratio + 0.25 * growth_ratio


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
    query_words = {word.lower() for query in queries for word in WORD_RE.findall(query)}

    quantity = min(len(unique_urls) / max(target, 1), 1.0)
    if total_results <= 1:
        diversity = 0.0
    else:
        numerator = sum(count * (count - 1) for count in counts.values())
        diversity = 1.0 - (numerator / (total_results * (total_results - 1)))

    match_count = 0
    for item in results:
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        if "llm_relevant" in metadata:
            if metadata.get("llm_relevant") is True:
                match_count += 1
            continue

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
        metadata = (
            item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        )
        parsed = None
        for name in DATE_FIELDS:
            parsed = parse_date(metadata.get(name))
            if parsed:
                break
        if parsed and parsed >= fresh_cutoff:
            fresh_count += 1
    freshness = fresh_count / total_results if total_results else 0.0

    efficiency = min(len(unique_urls) / max(len(queries) * 3, 1), 1.0)
    latency = score_latency(evidence_file, scoring_config["latency_budget_seconds"])
    adoption = score_adoption(evidence_file)
    knowledge_growth = score_knowledge_growth(evidence_file)
    dimensions = {
        "quantity": quantity,
        "diversity": diversity,
        "relevance": relevance,
        "freshness": freshness,
        "efficiency": efficiency,
        "latency": latency,
        "adoption": adoption,
        "knowledge_growth": knowledge_growth,
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
