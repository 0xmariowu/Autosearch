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
    """AVO Supervisor: detect stagnation + diagnose + suggest redirects (Section 3.3)."""
    if len(population) < window:
        return False, "", []
    recent = population[-window:]
    scores = [p.get("scores", {}).get("total", 0) for p in recent]

    stagnant = False
    reason = ""

    if scores and max(scores) <= min(scores) * 1.01:
        stagnant = True
        reason = f"Scores flat for {window} generations: {[round(s, 3) for s in scores]}"
    if len(scores) >= 2 and all(scores[i] <= scores[i - 1] for i in range(1, len(scores))):
        stagnant = True
        reason = f"Scores declining: {[round(s, 3) for s in scores]}"

    if not stagnant:
        return False, "", []

    # Diagnose WHY — analyze per-dimension scores across recent generations
    dims = {"quantity_score": [], "diversity": [], "relevance": [], "efficiency": []}
    for p in recent:
        s = p.get("scores", {})
        for dim in dims:
            dims[dim].append(s.get(dim, 0))
    avg_dims = {dim: sum(vals) / max(len(vals), 1) for dim, vals in dims.items()}
    weakest = min(avg_dims, key=avg_dims.get)

    suggestions = [f"Weakest dimension: {weakest} (avg={avg_dims[weakest]:.2f})"]
    if avg_dims.get("quantity_score", 0) < 0.5:
        suggestions.append("Use search_and_process + deep_discover for more URLs")
    if avg_dims.get("diversity", 0) < 0.6:
        suggestions.append("Use search_all across ALL providers, not just GitHub")
    if avg_dims.get("efficiency", 0) < 0.3:
        suggestions.append("Minimize think/processing steps, maximize search steps")
    suggestions.append("Try persona_expand for completely different query angles")
    suggestions.append("Reframe topic: 'AI agent' → 'autonomous AI tools' or 'LLM orchestration'")

    return True, reason, suggestions


def supervise_with_llm(population, knowledge, task_spec):
    """AVO Supervisor Agent: LLM-based trajectory analysis and redirect (Section 3.3)."""
    import os
    import urllib.request

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key or len(population) < 3:
        return None

    trajectory = []
    for p in population[-5:]:
        s = p.get("scores", {})
        trajectory.append(
            f"Gen {p.get('generation', '?')}: total={s.get('total', 0):.3f} "
            f"urls={s.get('unique_urls', 0)} div={s.get('diversity', 0):.2f} "
            f"eff={s.get('efficiency', 0):.2f}"
        )

    prompt = f"""You are the AVO Supervisor Agent. The search system is stagnating.

Task: {task_spec}

Evolution trajectory (recent):
{chr(10).join(trajectory)}

Available capabilities:
{knowledge[:1000]}

Analyze:
1. WHY is progress stalling? (which dimensions are weak?)
2. What SPECIFIC new strategy should the agent try?

Generate a NEW orchestrator prompt that takes a completely different approach.
Include {{manifest}} placeholder for capabilities list.
Return ONLY the prompt text."""

    payload = json.dumps({
        "model": os.environ.get("OPENROUTER_ORCHESTRATOR_MODEL", "google/gemini-2.5-flash"),
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content and len(content) > 50:
            if "{manifest}" not in content:
                content += "\n\n## Available Capabilities\n{manifest}"
            return content
    except Exception:
        pass
    return None


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
    cumulative_evidence: list[dict] = []

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

        # 2. RUN + DIAGNOSE LOOP (AVO Section 3.2: edit-evaluate-diagnose cycle)
        # Try up to max_retries times within one generation
        max_retries = 2
        for attempt in range(max_retries + 1):
            result = run_task(
                task_spec,
                max_steps=steps_per_gen,
                model=model,
                system_prompt=new_prompt,
                task_id=f"avo-gen{gen + 1}-try{attempt}",
            )

            # Accumulate evidence across generations
            for item in result.get("evidence", []):
                if isinstance(item, dict) and item.get("url"):
                    url = item["url"]
                    if url not in {e.get("url", "") for e in cumulative_evidence}:
                        cumulative_evidence.append(item)

            # Quick score to decide if retry is needed
            this_gen_urls = len(result.get("evidence", []))

            # If this attempt found very few new URLs and we have retries left, diagnose and retry
            if this_gen_urls < 5 and attempt < max_retries:
                print(
                    f"[AVO] Gen {gen + 1} attempt {attempt + 1}: only {this_gen_urls} URLs — diagnosing...",
                    file=sys.stderr,
                )
                # Diagnose: mutate prompt to fix the issue
                redirect_result = dispatch(
                    "avo_vary", None,
                    population=population, knowledge=knowledge,
                    task_spec=task_spec, use_llm=False,
                )
                retry_prompt = redirect_result.get("prompt")
                if retry_prompt:
                    new_prompt = retry_prompt
                continue
            break

        # 3. EVALUATE: Score using cumulative evidence
        score_input = dict(result)
        score_input["evidence"] = cumulative_evidence
        score_input["steps_used"] = sum(p.get("scores", {}).get("steps_used", steps_per_gen) for p in population) + result.get("steps_used", steps_per_gen)
        scores = dispatch("avo_score", score_input, target_count=100)
        gen_time = time.time() - gen_start

        print(
            f"[AVO] Gen {gen + 1}: total={scores['total']:.4f} "
            f"(urls={scores['unique_urls']}, cumulative={len(cumulative_evidence)}, "
            f"div={scores['diversity']:.2f}, eff={scores['efficiency']:.2f}) [{gen_time:.1f}s]",
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
            stagnant, reason, suggestions = check_stagnation(population)
            if stagnant:
                print(f"[AVO] Supervisor: STAGNATION — {reason}", file=sys.stderr)
                for s in suggestions:
                    print(f"[AVO] Supervisor: → {s}", file=sys.stderr)

                # Try LLM-based supervisor redirect first (AVO's "reviews overall trajectory")
                redirect_prompt = supervise_with_llm(population, knowledge, task_spec)
                if redirect_prompt:
                    print("[AVO] Supervisor: LLM generated new redirect strategy", file=sys.stderr)
                    best_prompt = redirect_prompt
                else:
                    # Fallback: template variation
                    print("[AVO] Supervisor: using template variation fallback", file=sys.stderr)
                    redirect_result = dispatch(
                        "avo_vary",
                        None,
                        population=population,
                        knowledge=knowledge,
                        task_spec=task_spec,
                        use_llm=False,
                    )
                    fallback_prompt = redirect_result.get("prompt")
                    if fallback_prompt:
                        best_prompt = fallback_prompt

    # Summary
    print(
        f"\n[AVO] Evolution complete. {max_generations} generations.", file=sys.stderr
    )
    print(f"[AVO] Best score: {best_score:.4f}", file=sys.stderr)
    print(f"[AVO] Population size: {len(population)}", file=sys.stderr)

    # Save best evolved prompt for future use
    best_prompt_path = Path(__file__).parent / "sources" / "evolved-prompt.txt"
    best_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    if best_prompt and best_score > 0:
        best_prompt_path.write_text(best_prompt)
        print(f"[AVO] Best prompt saved to {best_prompt_path}", file=sys.stderr)

    return {
        "status": "avo_complete",
        "generations": max_generations,
        "best_score": best_score,
        "population_size": len(population),
        "best_prompt_excerpt": best_prompt[:500] if best_prompt else "",
        "cumulative_evidence": len(cumulative_evidence),
        "cumulative_urls": [e.get("url", "") for e in cumulative_evidence[:20]],
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
