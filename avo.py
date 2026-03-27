#!/usr/bin/env python3
"""AVO: Agentic Variation Operators for AutoSearch.

Evolves the orchestrator's search methodology by iteratively
varying the system prompt and measuring search quality.

Formulation from NVIDIA's AVO paper (arXiv:2603.24517):
  Vary(P_t) = Agent(P_t, K, f)
  P_t = population of (prompt, score) pairs
  K   = capabilities manifest + patterns
  f   = multi-dimensional search quality score

Usage:
  python3 avo.py "find 100 AI agent repos" --generations 5
  python3 avo.py "find papers on LLM evaluation" --generations 10 --steps-per-gen 20
"""

import argparse
import json
import sys
import time
from pathlib import Path

EVOLUTION_PATH = Path(__file__).parent / "evolution.jsonl"
AVO_TYPE = "avo_generation"


def load_population(task_spec=""):
    """Load AVO population from evolution.jsonl."""
    if not EVOLUTION_PATH.exists():
        return []
    population = []
    with open(EVOLUTION_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("type") == AVO_TYPE:
                    if not task_spec or entry.get("task_spec", "") == task_spec:
                        population.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue
    return population


def commit_generation(task_spec, generation, prompt, scores, evidence_count):
    """Append AVO generation record to evolution.jsonl."""
    entry = {
        "type": AVO_TYPE,
        "task_spec": task_spec,
        "generation": generation,
        "prompt": prompt[:2000] if prompt else "",
        "scores": scores,
        "evidence_count": evidence_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(EVOLUTION_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def check_stagnation(population, window=3):
    """AVO Supervisor: detect stagnation in score trajectory."""
    if len(population) < window:
        return False, ""
    recent = population[-window:]
    scores = [p.get("scores", {}).get("total", 0) for p in recent]

    # No improvement in last N generations (< 1%)
    if scores and max(scores) <= min(scores) * 1.01:
        return (
            True,
            f"Scores flat for {window} generations: {[round(s, 3) for s in scores]}",
        )

    # Scores declining
    if len(scores) >= 2 and all(
        scores[i] <= scores[i - 1] for i in range(1, len(scores))
    ):
        return True, f"Scores declining: {[round(s, 3) for s in scores]}"

    return False, ""


def run_avo(
    task_spec,
    max_generations=5,
    steps_per_gen=15,
    model="",
):
    """Run AVO evolution loop.

    Each generation:
    1. Vary: generate new orchestrator prompt from lineage
    2. Run: execute orchestrator with new prompt
    3. Evaluate: score the result
    4. Update: commit if improves
    5. Supervise: check for stagnation
    """
    from capabilities import dispatch, manifest_text, load_manifest
    from orchestrator import run_task
    from orchestrator_prompts import SYSTEM_PROMPT

    knowledge = manifest_text()
    population = load_population(task_spec)
    best_score = max(
        (p.get("scores", {}).get("total", 0) for p in population), default=0
    )
    best_prompt = SYSTEM_PROMPT

    print(
        f"[AVO] Starting evolution: {max_generations} generations, {steps_per_gen} steps each",
        file=sys.stderr,
    )
    print(
        f"[AVO] Population: {len(population)} prior generations, best score: {best_score:.4f}",
        file=sys.stderr,
    )
    print(f"[AVO] Capabilities: {len(load_manifest())}", file=sys.stderr)

    for gen in range(max_generations):
        gen_start = time.time()

        # 1. VARY: Generate new prompt from lineage
        vary_result = dispatch(
            "avo_vary",
            None,
            population=population,
            knowledge=knowledge,
            task_spec=task_spec,
            use_llm=True,
        )
        new_prompt = vary_result.get("prompt")
        method = vary_result.get("method", "unknown")

        if new_prompt is None:
            new_prompt = best_prompt

        print(
            f"\n[AVO] === Generation {gen + 1}/{max_generations} (method: {method}) ===",
            file=sys.stderr,
        )

        # 2. RUN: Execute orchestrator with evolved prompt
        result = run_task(
            task_spec,
            max_steps=steps_per_gen,
            model=model,
            system_prompt=new_prompt,
            task_id=f"avo-gen{gen + 1}",
        )

        # 3. EVALUATE: Score the result
        scores = dispatch("avo_score", result, target_count=100)
        gen_time = time.time() - gen_start

        print(
            f"[AVO] Gen {gen + 1}: total={scores['total']:.4f} "
            f"(urls={scores['unique_urls']}, div={scores['diversity']:.2f}, "
            f"eff={scores['efficiency']:.2f}) [{gen_time:.1f}s]",
            file=sys.stderr,
        )

        # 4. UPDATE: Commit generation
        entry = commit_generation(
            task_spec, gen + 1, new_prompt, scores, scores["unique_urls"]
        )
        population.append(entry)

        if scores["total"] > best_score:
            best_score = scores["total"]
            best_prompt = new_prompt
            print(f"[AVO] *** New best! Score: {best_score:.4f} ***", file=sys.stderr)

        # 5. SUPERVISE: Check stagnation (AVO Section 3.3)
        if gen >= 2:
            stagnant, reason = check_stagnation(population)
            if stagnant:
                print(f"[AVO] Supervisor: STAGNATION — {reason}", file=sys.stderr)
                print(
                    "[AVO] Supervisor: forcing template variation for diversity",
                    file=sys.stderr,
                )
                # Force template variation to break out of local optimum
                redirect_result = dispatch(
                    "avo_vary",
                    None,
                    population=population,
                    knowledge=knowledge,
                    task_spec=task_spec,
                    use_llm=False,
                )
                redirect_prompt = redirect_result.get("prompt")
                if redirect_prompt:
                    best_prompt = redirect_prompt

    # Summary
    print(
        f"\n[AVO] Evolution complete. {max_generations} generations.", file=sys.stderr
    )
    print(f"[AVO] Best score: {best_score:.4f}", file=sys.stderr)
    print(f"[AVO] Population size: {len(population)}", file=sys.stderr)

    return {
        "status": "avo_complete",
        "generations": max_generations,
        "best_score": best_score,
        "population_size": len(population),
        "best_prompt_excerpt": best_prompt[:500] if best_prompt else "",
        "score_trajectory": [
            {
                "gen": p.get("generation", "?"),
                "total": p.get("scores", {}).get("total", 0),
            }
            for p in population[-max_generations:]
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="AVO: Agentic Variation Operators for AutoSearch",
    )
    parser.add_argument("task_spec", help="Search task to optimize for")
    parser.add_argument(
        "--generations",
        type=int,
        default=5,
        help="Number of evolution generations (default: 5)",
    )
    parser.add_argument(
        "--steps-per-gen",
        type=int,
        default=15,
        help="Max orchestrator steps per generation (default: 15)",
    )
    parser.add_argument("--model", type=str, default="", help="LLM model override")

    args = parser.parse_args()
    result = run_avo(args.task_spec, args.generations, args.steps_per_gen, args.model)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
