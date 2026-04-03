"""Control search breadth at each depth level to prevent exponential explosion."""

name = "breadth_control"
description = "Calculate the appropriate search breadth for each depth level in recursive research. Breadth halves at each level: depth 0 = full breadth, depth 1 = half, depth 2 = quarter. Prevents exponential query explosion while maintaining depth."
when = "When planning recursive or multi-depth research. Use to determine how many queries to run at each depth level."
input_type = "config"
output_type = "config"

import math


def run(input_data, **context):
    initial_breadth = context.get("initial_breadth", 8)
    current_depth = context.get("current_depth", 0)
    max_depth = context.get("max_depth", 4)

    # dzhng pattern: Math.ceil(breadth / 2) at each level
    breadth = initial_breadth
    for _ in range(current_depth):
        breadth = math.ceil(breadth / 2)

    # Calculate total work estimate
    total_queries = 0
    b = initial_breadth
    for d in range(max_depth + 1):
        total_queries += b
        b = math.ceil(b / 2)

    return {
        "breadth": breadth,
        "current_depth": current_depth,
        "max_depth": max_depth,
        "initial_breadth": initial_breadth,
        "total_estimated_queries": total_queries,
        "breadth_schedule": [
            {"depth": d, "breadth": math.ceil(initial_breadth / (2**d))}
            for d in range(max_depth + 1)
        ],
    }


def test():
    # depth 0: 8, depth 1: 4, depth 2: 2, depth 3: 1
    r0 = run(None, initial_breadth=8, current_depth=0)
    assert r0["breadth"] == 8

    r1 = run(None, initial_breadth=8, current_depth=1)
    assert r1["breadth"] == 4

    r2 = run(None, initial_breadth=8, current_depth=2)
    assert r2["breadth"] == 2

    r3 = run(None, initial_breadth=8, current_depth=3)
    assert r3["breadth"] == 1

    # Verify schedule
    assert len(r0["breadth_schedule"]) == 5  # depths 0-4
    return "ok"
