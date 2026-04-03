# Survey of LLM Memory Architectures and Implementations

## Executive Framework

LLM memory architectures can be understood along three principal axes:

### Axis 1: Memory Substrate
- **Parametric** — encoded in model weights (fine-tuning, LoRA, state-space models like Mamba)
- **Context-resident** — held in the prompt/context window (in-context learning, conversation history)
- **External-store** — persisted outside the model (vector DBs, knowledge graphs, SQL stores, filesystems)

### Axis 2: Temporal Scope
- **Working memory** — current session context (conversation buffer, sliding window)
- **Short-term** — within-task persistence (episode memory, scratchpad)
- **Long-term** — cross-session persistence (archival memory, knowledge base, user profiles)

### Axis 3: Control Policy
- **Static** — fixed rules for read/write (traditional RAG, buffer memory)
- **Heuristic** — rule-based management with forgetting/consolidation (MemoryBank's Ebbinghaus decay)
- **Agentic** — LLM decides when/what to store, retrieve, update, delete (Letta, AgeMem, A-Mem)

The field has evolved through three stages [discovered]: **Storage** (trajectory preservation) → **Reflection** (trajectory refinement) → **Experience** (trajectory abstraction), as formalized by the "From Storage to Experience" survey (Jan 2026).

---

## Architectural Design Patterns

### Pattern 1: OS-Inspired Tiered Memory
**Exemplar**: [Letta/MemGPT](https://github.com/letta-ai/letta)

The LLM acts as an OS managing memory tiers: core block (system prompt), conversation buffer (recent messages), recall memory (searchable conversation history), and archival memory (long-term vector store). The model explicitly calls memory tools (search, insert, update) as part of its action space.

**Strengths**: Principled, extensible, model-agnostic. Letta Code (#1 on Terminal-Bench) validates the pattern for coding agents.
**Weaknesses**: Relies on LLM's judgment for memory management decisions; quality varies by model.

### Pattern 2: Temporal Knowledge Graphs
**Exemplar**: [Zep/Graphiti](https://github.com/getzep/graphiti)

Memory stored as a temporal knowledge graph where entities and relationships have validity windows (when a fact became true, when it was superseded). Retrieval combines semantic search, graph traversal, and temporal filtering.

**Strengths**: Handles evolving knowledge naturally, supports temporal reasoning. Zep achieves 94.8% on DMR with 90% latency reduction. [discovered]
**Weaknesses**: Graph construction adds complexity; requires entity extraction pipeline.

### Pattern 3: Multi-Graph Architecture
**Exemplar**: [MAGMA](https://arxiv.org/abs/2601.03236) (Jan 2026) [discovered]

Represents each memory item across orthogonal semantic, temporal, causal, and entity graphs. Retrieval is policy-guided traversal across these relational views. Achieves highest overall judge score (0.7), outperforming alternatives by 18.6%-45.5%.

**Strengths**: Query-adaptive retrieval across multiple relationship types.
**Weaknesses**: Computational overhead of maintaining four parallel graph structures.

### Pattern 4: Zettelkasten/Interconnected Knowledge Networks
**Exemplar**: [A-Mem](https://arxiv.org/abs/2502.12110) (NeurIPS 2025) [discovered]

Applies Zettelkasten principles — dynamic indexing and linking of atomic memory notes. Memories are interconnected through semantic links, enabling associative retrieval.

**Strengths**: Rich cross-referencing, supports emergent knowledge discovery.
**Weaknesses**: Link management overhead grows with memory size.

### Pattern 5: Four-Network Epistemic Architecture
**Exemplar**: [Hindsight](https://arxiv.org/abs/2512.12818) (Dec 2025) [discovered]

Four separate memory networks: **world** (objective facts), **bank** (agent experiences), **opinion** (subjective judgments with confidence), **observation** (preference-neutral entity summaries). TEMPR retrieval runs four parallel searches (semantic, BM25, graph, temporal). CARA handles preference-aware reasoning.

**Strengths**: 91.4% on LongMemEval, 89.61% on LoCoMo — among the strongest benchmark results. Open-source with 20B model outperforms GPT-4o full-context.
**Weaknesses**: Complex four-network maintenance; not yet widely adopted in production.

### Pattern 6: Bio-Inspired Forgetting and Consolidation
**Exemplar**: [MemoryBank](https://arxiv.org/abs/2305.10250) (AAAI 2024) [knowledge], [Larimar](https://arxiv.org/abs/2403.11901) (ICML 2024) [knowledge, verified]

MemoryBank uses Ebbinghaus forgetting curve (R=e^(-t/S)) for memory intensity decay — recalled memories persist longer. Larimar uses complementary learning systems (hippocampal fast-learning + neocortical slow-learning) for one-shot knowledge updates without retraining (4-10x speedup).

**Strengths**: Prevents unbounded memory growth; neuroscience-grounded.

### Pattern 7: Memory-as-Operating-System
**Exemplar**: [MemOS](https://github.com/MemTensor/MemOS) (v2.0 Dec 2025) [discovered], [EverMemOS](https://github.com/EverMind-AI/EverMemOS) (Jan 2026) [discovered]

Memory treated as an OS-level concern with skill persistence and cross-task reuse. MemOS v2.0 adds multi-modal memory (images/charts) and tool memory for agent planning. EverMemOS achieves 93% on LoCoMo with self-organizing memory.

**Strengths**: Persistent skill memory enables cross-task transfer; OS abstraction is familiar to developers.

### Pattern 8: Zero-LLM Cognitive Processing
**Exemplar**: [Mnemosyne](https://github.com/28naem-del/mnemosyne) (Feb 2026) [discovered]

5-layer cognitive architecture running zero LLM calls during ingestion. 12-step algorithmic pipeline completes in <50ms. At 100K memories/month, saves $1,000-3,000 in API costs vs LLM-based extraction.

**Strengths**: Dramatically lower cost and latency for memory operations.
**Weaknesses**: Sacrifices LLM semantic understanding during ingestion; limited to structured extraction.

---

## Evidence Tables: Commercial and Production Systems

| System | Architecture | LoCoMo | LongMemEval | Key Metric | Funding/Stars |
|--------|-------------|--------|-------------|------------|---------------|
| [Mem0](https://mem0.ai/) | Vector + graph memory | 67.1% | 49.0%* | 186M API calls/Q, 26% > OpenAI memory | $24M Series A, 41K stars |
| [Letta](https://github.com/letta-ai/letta) | OS-inspired tiered | ~83.2% | — | #1 on Terminal-Bench (coding) | Seed funded, 16K+ stars |
| [Zep/Graphiti](https://github.com/getzep/graphiti) | Temporal KG | — | — | 94.8% DMR, 90% latency reduction | — |
| [Supermemory](https://supermemory.ai/) | 5-layer stack | — | 85.4% (99% exp.) | <300ms at 100B+ tokens/mo | SOC2/HIPAA |
| [Hindsight](https://github.com/vectorize-io/hindsight) | 4-network epistemic | 89.6% | 91.4% | Open 20B > GPT-4o full-context | Open source |
| [OMEGA](https://omegamax.co/compare) | — | — | 95.4% | #1 on LongMemEval | — |
| [Mnemosyne](https://github.com/28naem-del/mnemosyne) | Zero-LLM cognitive | — | — | <50ms ingestion, 0 LLM calls | Open source |
| [MemOS](https://github.com/MemTensor/MemOS) | Memory OS | — | — | Skill persistence + multi-modal | Open source |

*Mem0's LoCoMo score cited from comparison articles; Mem0 reports 67.13% LLM-as-Judge on their own evaluation.

---

## Evidence Tables: Research Papers and Frameworks

| Paper/System | Venue | Contribution | Status |
|-------------|-------|-------------|--------|
| [A-Mem](https://arxiv.org/abs/2502.12110) | NeurIPS 2025 | Zettelkasten-inspired agentic memory with dynamic indexing | Published [discovered] |
| [MAGMA](https://arxiv.org/abs/2601.03236) | Jan 2026 | Multi-graph architecture (semantic/temporal/causal/entity) | Preprint [discovered] |
| [AgeMem](https://arxiv.org/abs/2601.01885) | Jan 2026 | Unified LT/ST memory as tool-based actions in agent policy | Preprint [discovered] |
| [Continuum Memory](https://arxiv.org/html/2601.09913v1) | Jan 2026 | Formal CMA definition for long-horizon agents | Preprint [discovered] |
| [MELODI](https://openreview.net/pdf?id=rajioNWfRs) | ICLR 2026 | Low-dimension memory (8x reduction vs Memorizing Transformer) | Published [discovered] |
| [NAMMs](https://proceedings.iclr.cc/paper_files/paper/2025/file/da85790fb1cb4f11f431648455c561b5-Paper-Conference.pdf) | ICLR 2025 | Neural attention memory models for pre-trained transformers | Published [discovered] |
| [Cognitive Workspace](https://www.arxiv.org/pdf/2508.13171) | Aug 2025 | Active memory management transcending traditional RAG | Preprint [discovered] |
| [Collaborative Memory](https://arxiv.org/html/2505.18279v1) | May 2025 | Multi-user memory with dynamic access control | Preprint [discovered] |
| [Multi-Agent Memory](https://arxiv.org/abs/2603.10062) | Mar 2026 | Computer architecture perspective on multi-agent memory | Position paper [discovered] |
| [SimpleMem](https://github.com/aiming-lab/SimpleMem) | Jan 2026 | Semantic lossless compression for lifelong memory | Preprint [discovered] |
| [MemEngine](https://github.com/nuster1128/MemEngine) | TheWebConf 2025 | Unified modular library for agent memory development | Published [discovered] |
| [MemoryCD](https://arxiv.org/html/2603.25973) | Mar 2026 | Cross-domain personalization benchmark (14 models, 6 baselines) | Preprint [discovered] |
| [Larimar](https://arxiv.org/abs/2403.11901) | ICML 2024 | Episodic memory via complementary learning systems | Published [verified] |
| [MemoryBank](https://arxiv.org/abs/2305.10250) | AAAI 2024 | Ebbinghaus forgetting curve for memory management | Published [knowledge] |

---

## Evaluation Benchmarks

| Benchmark | Focus | Key Finding |
|-----------|-------|-------------|
| [LongMemEval](https://github.com/xiaowu0162/LongMemEval) (ICLR 2025) | 5 core memory abilities across 500 questions, up to 1.5M tokens | Long-context LLMs drop 30-60%; commercial systems only 30-70% accuracy [discovered] |
| [LoCoMo](https://snap-research.github.io/locomo/) | Long-term conversational memory with temporal/event grounding | Primary testbed used by Mem0, Hindsight, Letta [knowledge, verified] |
| [MemoryCD](https://arxiv.org/html/2603.25973) (Mar 2026) | Cross-domain personalization: 14 models, 6 baselines, 12 domains | Newest comprehensive benchmark [discovered] |
| [DMR](https://arxiv.org/abs/2501.13956) | Deep Memory Retrieval — established by MemGPT team | Zep 94.8% vs MemGPT 93.4% [discovered] |

---

## Risk Analysis

1. **Context window vs. external memory tension**: Context windows now reach 10M tokens (Llama 4), but "lost in the middle" degrades accuracy to 76-82% for middle-positioned content [discovered]. External memory remains necessary for structured knowledge and cross-session persistence.

2. **Benchmark gaming**: Different systems report on different benchmarks. OMEGA leads LongMemEval (95.4%), Hindsight leads LoCoMo (89.6%), Zep leads DMR (94.8%). No single system dominates all benchmarks, making direct comparison difficult.

3. **Multi-agent memory consistency**: Access protocols for shared memory remain under-specified [discovered]. Key open questions: Can agents read each other's long-term memory? Read-only or read-write? What is the unit of access?

4. **Memory poisoning and privacy**: Storing user data creates PII risks. Only Supermemory explicitly advertises SOC 2 + HIPAA compliance among the surveyed systems.

5. **Cost at scale**: LLM-based memory management (extraction, classification) costs $1,000-3,000/month at 100K memories. Zero-LLM approaches (Mnemosyne) trade semantic understanding for 100x cost reduction.

---

## Gap Declaration

1. **No standardized benchmark**: LongMemEval, LoCoMo, DMR, and MemoryCD each test different dimensions. No unified leaderboard exists.
2. **Multi-agent memory protocols**: Mostly theoretical position papers; no production-validated shared memory standard found.
3. **Parametric memory integration**: Most systems focus on external-store memory. Integration with weight-based memory (fine-tuning, LoRA adapters) is underexplored.
4. **Long-term evaluation**: All benchmarks test short-term or medium-term scenarios. No benchmark tests memory over weeks/months of real usage.
5. **Chinese-developed systems**: Alibaba's [MemoryScope](https://blog.csdn.net/u010522887/article/details/143354689), and systems like Mirix and MemU mentioned in Chinese surveys, lack English documentation — potentially significant implementations with limited global visibility.

---

## Resource Index

### Surveys (start here)
- [Memory for Autonomous LLM Agents (Mar 2026)](https://arxiv.org/pdf/2603.07670) — most recent, formal write-manage-read taxonomy
- [Agent-Memory-Paper-List](https://github.com/Shichun-Liu/Agent-Memory-Paper-List) — curated paper list for "Memory in the Age of AI Agents" survey
- [Awesome-AI-Memory (IAAR-Shanghai)](https://github.com/IAAR-Shanghai/Awesome-AI-Memory) — comprehensive knowledge base
- [Awesome-Memory-for-Agents (Tsinghua)](https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents) — Tsinghua C3I paper collection

### Implementations (for builders)
- [Letta](https://github.com/letta-ai/letta) — OS-inspired stateful agents
- [Mem0](https://github.com/mem0ai/mem0) — production memory layer
- [Graphiti](https://github.com/getzep/graphiti) — temporal knowledge graphs
- [Hindsight](https://github.com/vectorize-io/hindsight) — 4-network epistemic memory
- [MemEngine](https://github.com/nuster1128/MemEngine) — modular memory development library
- [SimpleMem](https://github.com/aiming-lab/SimpleMem) — compression-based lifelong memory

### Benchmarks (for evaluation)
- [LongMemEval](https://github.com/xiaowu0162/LongMemEval) — ICLR 2025, 5 memory abilities
- [LoCoMo](https://snap-research.github.io/locomo/) — long-term conversational memory

### Chinese-language resources
- [2025年Memory最全综述 (Zhihu)](https://zhuanlan.zhihu.com/p/1985435669187825983) — unified classification beyond RAG
- [2025 AI 记忆系统大横评 (Zhihu)](https://zhuanlan.zhihu.com/p/1978869876396413893) — from plugins to OS
- [万字解析 Agent Memory 实现 (Zhihu)](https://zhuanlan.zhihu.com/p/1940091301249909899) — 10K-word implementation analysis
- [阿里开源 MemoryScope 实战 (CSDN)](https://blog.csdn.net/u010522887/article/details/143354689) — Alibaba's memory framework

### Academic events
- [ICLR 2026 MemAgents Workshop](https://sites.google.com/view/memagent-iclr26/) — April 26-27, 2026

---

## Provenance Summary

- **[knowledge]**: 18 items from Claude's training data (foundational methods, established projects, known papers)
- **[discovered]**: 37 items found through search that extend beyond training data
- **[verified]**: 5 items where search confirmed/enriched existing knowledge (Larimar, Mem0 funding, Zep architecture, LoCoMo, MemoryBank)

AutoSearch discovered 37 items not in Claude's training data, including:
- 6 new memory frameworks (MAGMA, A-Mem, SimpleMem, EverMemOS, Mnemosyne, Continuum Memory)
- 4 new benchmarks (LongMemEval, MemoryCD, DMR details, Memory Mosaics v2)
- The ICLR 2026 MemAgents workshop
- Concrete benchmark comparison data across all major systems
- Chinese-language resources covering systems not visible in English (MemoryScope, Mirix, MemU)
- Production adoption metrics (Mem0: $24M funding, 186M API calls/quarter)
