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
EVOLVED_DIR = Path(__file__).parent / "genome" / "evolved"
AVO_TYPE = "avo_generation"
AVO_GENOME_TYPE = "avo_genome_generation"


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


def load_genome_population(task_spec=""):
    """Load genome-based AVO population from evolution.jsonl."""
    if not EVOLUTION_PATH.exists():
        return []
    population = []
    with open(EVOLUTION_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("type") in (AVO_TYPE, AVO_GENOME_TYPE):
                    if not task_spec or entry.get("task_spec", "") == task_spec:
                        population.append(entry)
            except (json.JSONDecodeError, KeyError):
                continue
    return population


def commit_genome_generation(
    task_spec,
    generation,
    genome_id,
    genome_path,
    parent_id,
    mutation_type,
    mutation_detail,
    scores,
    evidence_count,
):
    """Append genome-based AVO generation record to evolution.jsonl."""
    entry = {
        "type": AVO_GENOME_TYPE,
        "task_spec": task_spec,
        "generation": generation,
        "genome_id": genome_id,
        "genome_path": str(genome_path),
        "parent_id": parent_id,
        "mutation_type": mutation_type,
        "mutation_detail": mutation_detail,
        "scores": scores,
        "evidence_count": evidence_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(EVOLUTION_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def save_evolved_genome(genome, genome_id):
    """Persist an evolved genome to genome/evolved/{genome_id}.json."""
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True)
    path = EVOLVED_DIR / f"{genome_id}.json"
    path.write_text(genome.to_json() + "\n", encoding="utf-8")
    return path


def load_best_genome(task_spec=""):
    """Load the highest-scoring genome from evolution history."""
    population = load_genome_population(task_spec)
    genome_entries = [
        p
        for p in population
        if p.get("genome_path") and p.get("scores", {}).get("total", 0) > 0
    ]
    if not genome_entries:
        return None
    best = max(genome_entries, key=lambda p: p.get("scores", {}).get("total", 0))
    genome_path = best.get("genome_path", "")
    if genome_path and Path(genome_path).exists():
        from genome import load_genome

        return load_genome(genome_path)
    return None


def check_stagnation(population, window=3):
    """AVO Supervisor: detect stagnation + diagnose + suggest redirects (Section 3.3)."""
    if len(population) < window:
        return False, "", []
    recent = population[-window:]
    scores = [p.get("scores", {}).get("total", 0) for p in recent]

    if max(scores) == 0:
        return False, "", []

    stagnant = False
    reason = ""

    if scores and max(scores) <= min(scores) * 1.01:
        stagnant = True
        reason = (
            f"Scores flat for {window} generations: {[round(s, 3) for s in scores]}"
        )
    if len(scores) >= 2 and all(
        scores[i] <= scores[i - 1] for i in range(1, len(scores))
    ):
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
    suggestions.append(
        "Reframe topic: 'AI agent' → 'autonomous AI tools' or 'LLM orchestration'"
    )

    # Per-section genome diagnosis (for genome-based evolution)
    section_hints = []
    if weakest == "quantity_score":
        section_hints.append("engine: increase max_rounds or queries_per_round")
        section_hints.append("phases: add more search primitives")
    elif weakest == "diversity":
        section_hints.append("platform_routing: widen intent_routing")
        section_hints.append("thresholds: lower max_source_concentration")
    elif weakest == "relevance":
        section_hints.append("scoring: increase title term_weight")
        section_hints.append("query_generation: refine intent_patterns")
    elif weakest == "efficiency":
        section_hints.append("orchestrator: reduce max_steps")
        section_hints.append("phases: remove redundant primitives")
    suggestions.extend(section_hints)

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

    payload = json.dumps(
        {
            "model": os.environ.get(
                "OPENROUTER_ORCHESTRATOR_MODEL", "google/gemini-2.5-flash"
            ),
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        }
    ).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
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
                    "avo_vary",
                    None,
                    population=population,
                    knowledge=knowledge,
                    task_spec=task_spec,
                    use_llm=False,
                )
                retry_prompt = redirect_result.get("prompt")
                if retry_prompt:
                    new_prompt = retry_prompt
                continue
            break

        # 3. EVALUATE: Score using cumulative evidence
        score_input = dict(result)
        score_input["evidence"] = cumulative_evidence
        score_input["steps_used"] = sum(
            p.get("scores", {}).get("steps_used", steps_per_gen) for p in population
        ) + result.get("steps_used", steps_per_gen)
        scores = dispatch("avo_score", score_input, target_count=100)
        gen_time = time.time() - gen_start

        print(
            f"[AVO] Gen {gen + 1}: total={scores['total']:.4f} "
            f"(urls={scores.get('unique_urls', 0)}, cumulative={len(cumulative_evidence)}, "
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
                    print(
                        "[AVO] Supervisor: LLM generated new redirect strategy",
                        file=sys.stderr,
                    )
                    best_prompt = redirect_prompt
                else:
                    # Fallback: template variation
                    print(
                        "[AVO] Supervisor: using template variation fallback",
                        file=sys.stderr,
                    )
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


def run_avo_genome(
    task_spec,
    max_generations=5,
    seed_genome_path="",
    **kwargs,
):
    """Run AVO evolution loop on genomes (not prompts).

    Each generation:
    1. Select parent genome
    2. Vary: mutate genome → child genome
    3. Run: runtime.execute(child, task)
    4. Evaluate: goal_judge scores
    5. Commit/discard based on improvement
    6. Supervise: check stagnation → redirect
    """
    from genome import load_genome, validate_genome
    from genome.runtime import execute
    from genome.vary import vary_genome

    # Load seed genome
    if seed_genome_path:
        parent = load_genome(seed_genome_path)
    else:
        parent = load_genome(
            Path(__file__).parent / "genome" / "seeds" / "engine-3phase.json"
        )

    population = load_genome_population(task_spec)
    knowledge = _load_patterns()
    best_score = max(
        (p.get("scores", {}).get("total", 0) for p in population), default=0
    )
    best_genome = load_best_genome(task_spec) or parent
    generation_offset = len(population)

    print(
        f"[AVO-Genome] Starting: {max_generations} generations",
        file=sys.stderr,
    )
    print(
        f"[AVO-Genome] Population: {len(population)} prior, best: {best_score:.4f}",
        file=sys.stderr,
    )

    for gen in range(max_generations):
        gen_start = time.time()
        gen_num = generation_offset + gen + 1
        genome_id = f"gen-{gen_num}-{int(time.time())}"

        # 1. SELECT parent
        if population and best_score > 0:
            parent = best_genome

        # 2. VARY
        diagnosis = ""
        if gen >= 2:
            stagnant, reason, suggestions = check_stagnation(population)
            if stagnant:
                diagnosis = reason
                print(f"[AVO-Genome] Stagnation: {reason}", file=sys.stderr)

        child, mutation_type, mutation_detail = vary_genome(
            parent, population, knowledge, diagnosis
        )
        child.genome_id = genome_id
        child.parent_id = parent.genome_id

        errors = validate_genome(child)
        if errors:
            print(
                f"[AVO-Genome] Gen {gen_num}: invalid genome ({errors}), skipping",
                file=sys.stderr,
            )
            continue

        # 3. RUN
        result = execute(child, task_spec, **kwargs)

        # 4. EVALUATE
        scores = _evaluate_result(result, task_spec)
        gen_time = time.time() - gen_start

        print(
            f"[AVO-Genome] Gen {gen_num} ({mutation_type}): "
            f"total={scores.get('total', 0):.4f} urls={scores.get('unique_urls', 0)} "
            f"[{gen_time:.1f}s] — {mutation_detail}",
            file=sys.stderr,
        )

        # 5. COMMIT (genome file first, then JSONL — cleanup on failure)
        genome_path = save_evolved_genome(child, genome_id)
        try:
            entry = commit_genome_generation(
                task_spec,
                gen_num,
                genome_id,
                str(genome_path),
                parent.genome_id,
                mutation_type,
                mutation_detail,
                scores,
                scores.get("unique_urls", 0),
            )
        except Exception as exc:
            # Remove orphan genome file if JSONL write fails
            genome_path.unlink(missing_ok=True)
            print(
                f"[AVO-Genome] Gen {gen_num}: commit failed ({exc}), skipping",
                file=sys.stderr,
            )
            continue
        population.append(entry)

        if scores["total"] > best_score:
            best_score = scores["total"]
            best_genome = child
            print(
                f"[AVO-Genome] *** New best! {best_score:.4f} ***",
                file=sys.stderr,
            )

    print(f"\n[AVO-Genome] Done. Best: {best_score:.4f}", file=sys.stderr)
    return {
        "status": "avo_genome_complete",
        "generations": max_generations,
        "best_score": best_score,
        "best_genome_id": best_genome.genome_id,
        "population_size": len(population),
        "score_trajectory": [
            {
                "gen": p.get("generation", "?"),
                "total": p.get("scores", {}).get("total", 0),
                "mutation": p.get("mutation_type", ""),
            }
            for p in population[-max_generations:]
        ],
    }


def _load_patterns():
    """Load patterns.jsonl if it exists."""
    path = Path(__file__).parent / "patterns.jsonl"
    if not path.exists():
        return []
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            patterns.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return patterns


def _evaluate_result(result, task_spec):
    """Score a runtime result. Uses avo_score capability if available."""
    evidence = result.evidence if hasattr(result, "evidence") else []
    unique_urls = result.unique_urls if hasattr(result, "unique_urls") else 0

    try:
        from capabilities import dispatch

        score_input = {
            "evidence": evidence,
            "unique_urls": unique_urls,
            "steps_used": result.rounds_completed
            if hasattr(result, "rounds_completed")
            else 0,
        }
        return dispatch("avo_score", score_input, target_count=100)
    except Exception:
        # Fallback: simple URL-based scoring
        url_score = min(unique_urls / 100, 1.0) if unique_urls else 0
        return {
            "total": url_score,
            "unique_urls": unique_urls,
            "quantity_score": url_score,
            "diversity": 0.0,
            "relevance": 0.0,
            "efficiency": 0.0,
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
    parser.add_argument(
        "--genome",
        action="store_true",
        help="Use genome-based evolution (new AVO)",
    )
    parser.add_argument(
        "--seed-genome",
        type=str,
        default="",
        help="Path to seed genome JSON",
    )

    args = parser.parse_args()
    if args.genome:
        result = run_avo_genome(
            args.task_spec,
            max_generations=args.generations,
            seed_genome_path=args.seed_genome,
        )
    else:
        result = run_avo(
            args.task_spec, args.generations, args.steps_per_gen, args.model
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
