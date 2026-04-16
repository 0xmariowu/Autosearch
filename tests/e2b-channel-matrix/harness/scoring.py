from __future__ import annotations

import math
from typing import Literal


def wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0

    p = successes / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (center - margin) / denom)


def grade(
    ci_lower: float,
    avg_content_len: int,
    median_latency_ms: float,
    sample_size: int,
) -> Literal["GREEN", "YELLOW", "RED", "INSUFFICIENT"]:
    if sample_size < 60:
        return "INSUFFICIENT"
    if ci_lower >= 0.75 and avg_content_len >= 200 and median_latency_ms < 5000:
        return "GREEN"
    if ci_lower >= 0.4:
        return "YELLOW"
    return "RED"
