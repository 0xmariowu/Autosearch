#!/usr/bin/env python3
"""
AutoSearch CLI — manual task entry point.

Usage:
  python cli.py --config task.json
  python cli.py --genes '{"entity":["Claude"],...}' --target "..." --platforms reddit,hn,exa

For daily mode (F001.S2), use: python pipeline.py --mode daily
"""

import argparse
import json
import sys
from pathlib import Path

from engine import Engine, EngineConfig
from source_capability import load_source_capability_report


def parse_platforms(platforms_str: str) -> list[dict]:
    """Parse comma-separated platform names into config dicts.

    Supports format: "reddit:MachineLearning,hn,exa,github_issues,twitter_exa"
    """
    result = []
    for p in platforms_str.split(","):
        p = p.strip()
        if not p:
            continue
        if ":" in p:
            name, param = p.split(":", 1)
            if name == "reddit":
                result.append({"name": "reddit", "sub": param})
            elif name in ("github_issues", "github"):
                result.append({"name": "github_issues", "repo": param})
            else:
                result.append({"name": name})
        else:
            # Defaults for platforms that need params
            if p == "reddit":
                result.append({"name": "reddit", "sub": "all"})
            else:
                result.append({"name": p})
    return result


def main():
    parser = argparse.ArgumentParser(
        description="AutoSearch — self-evolving search engine",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to JSON config file with genes, platforms, target_spec",
    )
    parser.add_argument(
        "--genes",
        type=str,
        help='JSON string: {"entity":["X"],"pain_verb":["Y"],...}',
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Target spec: what does a useful finding look like?",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        help="Comma-separated: reddit:sub,hn,exa,github_issues,twitter_exa",
    )
    parser.add_argument(
        "--task-name",
        type=str,
        default="autosearch",
        help="Task name for session doc filename",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/autosearch-findings.jsonl",
        help="Output JSONL path for harvested findings",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=15,
        help="Maximum exploration rounds",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="claude-haiku-4-5-20251001",
        help="Anthropic model for LLM evaluation",
    )
    parser.add_argument(
        "--orchestrated",
        action="store_true",
        default=False,
        help="Use AI orchestrator mode: pass first positional arg as task_spec",
    )
    parser.add_argument(
        "task_spec",
        nargs="?",
        default=None,
        help="Task description for orchestrator mode (positional)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Maximum orchestrator steps (defaults to --max-rounds value)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default="",
        help="Resume from checkpoint file or task ID",
    )
    parser.add_argument(
        "--evolve", action="store_true", default=False, help="Run AVO evolution mode"
    )
    parser.add_argument(
        "--generations", type=int, default=5, help="AVO generations (default: 5)"
    )
    parser.add_argument(
        "--steps-per-gen", type=int, default=None, help="Steps per AVO generation"
    )

    args = parser.parse_args()

    if args.evolve and args.orchestrated:
        print(
            "Error: --evolve and --orchestrated are mutually exclusive", file=sys.stderr
        )
        sys.exit(1)

    # --- AVO Evolution mode ---
    if args.evolve:
        if not args.task_spec:
            print(
                "Error: --evolve requires a positional task_spec argument",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            from avo import run_avo
        except ImportError as exc:
            print(f"Error: cannot import avo: {exc}", file=sys.stderr)
            sys.exit(1)
        result = run_avo(
            args.task_spec,
            max_generations=args.generations,
            steps_per_gen=args.steps_per_gen
            if args.steps_per_gen
            else (args.max_steps if args.max_steps else 15),
            model=args.llm_model,
        )
        print("\n--- AVO Evolution Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    # --- Orchestrated mode ---
    if args.orchestrated:
        if not args.task_spec:
            print(
                "Error: --orchestrated requires a positional task_spec argument",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            from orchestrator import run_task
        except ImportError as exc:
            print(f"Error: cannot import orchestrator: {exc}", file=sys.stderr)
            sys.exit(1)
        max_steps = args.max_steps if args.max_steps is not None else args.max_rounds
        try:
            result = run_task(
                args.task_spec,
                max_steps=max_steps,
                model=args.llm_model,
                resume_from=args.resume,
            )
        except Exception as exc:
            print(f"Error: orchestrator failed: {exc}", file=sys.stderr)
            sys.exit(1)
        print("\n--- Orchestrated Result ---")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        sys.exit(0)

    # Build config from file or CLI args
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in {args.config}: {e}", file=sys.stderr)
            sys.exit(1)
        config = EngineConfig(
            genes=cfg.get("genes", {}),
            platforms=cfg.get("platforms", []),
            target_spec=cfg.get("target_spec", ""),
            task_name=cfg.get("task_name", "autosearch"),
            output_path=cfg.get("output_path", "/tmp/autosearch-findings.jsonl"),
            max_rounds=cfg.get("max_rounds", 15),
            llm_model=cfg.get("llm_model", "claude-haiku-4-5-20251001"),
            capability_report=load_source_capability_report(),
        )
    elif args.genes and args.target and args.platforms:
        try:
            genes = json.loads(args.genes)
        except json.JSONDecodeError as e:
            print(f"Error: --genes is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        config = EngineConfig(
            genes=genes,
            platforms=parse_platforms(args.platforms),
            target_spec=args.target,
            task_name=args.task_name,
            output_path=args.output,
            max_rounds=args.max_rounds,
            llm_model=args.llm_model,
            capability_report=load_source_capability_report(),
        )
    else:
        parser.print_help()
        print(
            "\nError: provide --config or (--genes + --target + --platforms)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate
    non_empty_genes = [k for k, v in config.genes.items() if v]
    if len(non_empty_genes) < 2:
        print("Error: genes must have at least 2 non-empty categories", file=sys.stderr)
        sys.exit(1)
    if not config.platforms:
        print("Error: at least one platform required", file=sys.stderr)
        sys.exit(1)
    if not config.target_spec:
        print("Error: target_spec is required", file=sys.stderr)
        sys.exit(1)

    # Run
    base_dir = Path(__file__).parent
    engine = Engine(config, base_dir)
    summary = engine.run()

    print("\n--- Summary ---")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
