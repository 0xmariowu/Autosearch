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

    args = parser.parse_args()

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
