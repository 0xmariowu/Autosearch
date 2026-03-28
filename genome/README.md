# Genome — Evolvable Search Strategy

A Genome is a complete JSON description of a search strategy that the AVO controller can evolve. It contains no executable code — only data that the Runtime interprets.

## Directory Structure

```
genome/
├── schema.py           # GenomeSchema dataclass (8 sections)
├── runtime.py          # Generic interpreter (~400 lines)
├── primitives.py       # 13 registered atomic operations
├── vary.py             # 5 mutation operators for AVO evolution
├── safe_eval.py        # Sandboxed expression evaluator
├── __init__.py         # load_genome / merge_genome / validate_genome
├── defaults/           # Default values per section (source of truth)
│   ├── engine.json
│   ├── orchestrator.json
│   ├── orchestrator-system-prompt.txt
│   ├── modes.json
│   ├── scoring.json
│   ├── platform_routing.json
│   ├── thresholds.json
│   ├── synthesis.json
│   └── query_generation.json
├── seeds/              # Starting genomes for AVO evolution
│   ├── engine-3phase.json
│   ├── orchestrator-react.json
│   └── daily-discovery.json
└── evolved/            # AVO-produced genomes (do not edit manually)
```

## Genome Sections

| Section | Controls | Source |
|---------|----------|--------|
| `engine` | rounds, query ratios, stale detection | engine.py |
| `orchestrator` | steps, temperature, model, timeout | orchestrator.py |
| `modes` | speed/balanced/deep policies | research/modes.py |
| `scoring` | term weights, engagement formulas | rerank/lexical.py |
| `platform_routing` | provider selection, intent routing | source_capability.py |
| `thresholds` | caps, concentration limits, stagnation | multiple files |
| `synthesis` | claim terms, report templates | research/synthesizer.py |
| `query_generation` | anchor tokens, mutation weights | research/planner.py |
| `phases` | ordered list of primitive calls | seed-specific |

## Usage

```python
from genome import load_genome, validate_genome
from genome.runtime import execute

genome = load_genome("genome/seeds/engine-3phase.json")
errors = validate_genome(genome)
assert not errors

result = execute(genome, "find AI agent frameworks")
print(f"Found {result.unique_urls} unique URLs in {result.elapsed_seconds:.1f}s")
```

## Rules

- Do not manually edit `genome/evolved/` — those are AVO output
- New strategy decisions go in `genome/defaults/`, not Python code
- `evolution.jsonl` is append-only
- Engagement formulas use `safe_eval` whitelist (no arbitrary code execution)

