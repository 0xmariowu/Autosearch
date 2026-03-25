---
title: alphaXiv MCP — Research Paper Search & Analysis
date: 2026-03-24
project: search-methodology
type: platform
tags: [alphaxiv, papers, research, arxiv, mcp]
status: active
---

# alphaXiv MCP

## What It's Best For

- **Paper-first retrieval**: finding arXiv papers when the task is explicitly academic or method-comparison oriented
- **Paper understanding**: pulling structured paper content or asking targeted questions about a PDF
- **Paper-to-code bridging**: exploring a paper's linked GitHub repository from the same tool surface

## Access Methods

| Method | API / Tool | Best For |
|--------|-----------|----------|
| AlphaXiv MCP | SSE endpoint `https://api.alphaxiv.org/mcp/v1` | Paper search, paper reading, PDF QA, codebase exploration |
| Claude Code MCP client | OAuth-backed remote MCP connection | Interactive research workflows |

## Available Tools

| Tool | Best For |
|------|----------|
| `embedding_similarity_search` | Semantic paper discovery from multi-sentence research descriptions |
| `full_text_papers_search` | Short keyword search over paper full text |
| `agentic_paper_retrieval` | Broad recall when coverage matters more than precision |
| `get_paper_content` | Pulling structured paper content or raw full text |
| `answer_pdf_queries` | Asking focused questions about a specific paper PDF |
| `read_files_from_github_repository` | Inspecting a paper's code repository from GitHub URL |

## Validated Patterns

### Use alphaXiv when the object is a paper, not a repo
- **Finding**: alphaXiv is a better primary surface than Exa when the task is clearly "find papers / compare methods / read the paper" rather than general web discovery.
- **Date validated**: 2026-03-24
- **How validated**: alphaXiv MCP docs review + tool surface comparison against existing AutoSearch providers
- **Confidence**: documentation-backed
- **Implication**: keep Exa for broad discovery; use alphaXiv when the desired artifact is academic evidence.

### Match the query style to the tool
- **Finding**: `embedding_similarity_search` wants a 2-3 sentence concept description, `full_text_papers_search` wants short keyword queries, and `agentic_paper_retrieval` is best for natural-language research questions.
- **Date validated**: 2026-03-24
- **How validated**: official alphaXiv MCP parameter docs
- **Confidence**: documentation-backed
- **Pattern**:
  - Use `embedding_similarity_search` for concept-level discovery
  - Use `full_text_papers_search` for method names, benchmarks, authors
  - Use `agentic_paper_retrieval` for "find the important papers on X"

### Treat alphaXiv as analysis depth, not daily default breadth
- **Finding**: alphaXiv MCP uses remote SSE + OAuth, which makes it a strong interactive research source but a weaker fit for unattended daily runtime until auth and automation semantics are pinned down.
- **Date validated**: 2026-03-24
- **How validated**: integration review against AutoSearch daily pipeline behavior
- **Confidence**: implementation-backed
- **Implication**: wire it into the environment now, but keep daily default providers unchanged for V1.

### Use paper-to-code verification when a paper claims an implementation
- **Finding**: `read_files_from_github_repository` gives a direct path from paper discovery to implementation inspection without leaving the MCP surface.
- **Date validated**: 2026-03-24
- **How validated**: official alphaXiv MCP tool documentation
- **Confidence**: documentation-backed
- **Implication**: for research-heavy topics, pair paper retrieval with code verification before recommending intake.

## Usage Guidance

### Best-fit cases
- Literature reviews
- Benchmark/method comparisons
- Model architecture searches
- Paper-grounded deep research

### Not the best first tool
- General web discovery
- Community pain-point search
- Product launch / trend detection
- High-volume unattended daily runs

## Suggested Workflow

```text
Need academic evidence
→ alphaXiv search tool
→ get_paper_content / answer_pdf_queries
→ verify linked repo when relevant
→ feed distilled findings into downstream candidate/routing flow
```

## Known Constraints

| Constraint | Impact | Date |
|-----------|--------|------|
| OAuth-backed SSE MCP | requires interactive auth on first use | 2026-03-24 |
| Remote MCP, not native AutoSearch connector | not yet part of unattended `daily.py` provider set | 2026-03-24 |
| Academic focus | weak fit for community sentiment or product chatter | 2026-03-24 |

## Unvalidated

- Whether alphaXiv should become a first-class AutoSearch provider in the runtime engine
- Whether paper results should route to Armory, AIMD, or a separate paper-candidate layer by default
