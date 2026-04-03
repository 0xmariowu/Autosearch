# Self-Evolving Search: A Deep Research Report

> Session: 20260403 | Score: 0.698 (quantity 1.0, relevance 0.977) | 43 results across 5 platforms

---

## 1. Executive Framework

Self-evolving search is a system that **improves its own search strategies over time** through feedback loops — not just returning results, but learning from each search cycle to search better next time.

The field sits at the intersection of three traditions:

```
                    Evolutionary Computation
                    (population-based search,
                     mutation, selection)
                           │
                           ▼
    ┌──────────────────────────────────────────┐
    │         SELF-EVOLVING SEARCH             │
    │                                          │
    │  What evolves: queries, strategies,      │
    │  ranking, tools, architecture            │
    │                                          │
    │  How it evolves: RL, evolution,          │
    │  meta-learning, reflection               │
    │                                          │
    │  Feedback signal: task completion,       │
    │  relevance scores, user feedback         │
    └──────────────────────────────────────────┘
                ▲                    ▲
                │                    │
    Reinforcement Learning     LLM-as-Agent
    (reward-driven,            (reflection, memory,
     policy optimization)       tool use)
```

### The Four Layers of Self-Evolution

| Layer | What Evolves | Example System | Mechanism |
|-------|-------------|----------------|-----------|
| **L1: Query** | Search queries get better | SE-Search [1], Search-R1 [20] | RL with dense rewards |
| **L2: Strategy** | Which platform/method to use | MR-Search [5], ACQO [4] | Meta-RL, bandit selection |
| **L3: Pipeline** | Entire search workflow | DSPy [27], SAGE [18] | Prompt compilation, reflection |
| **L4: Architecture** | Agent structure itself | ADAS [background knowledge], AgentEvolver [19] | Meta-agent search, self-questioning |

**Key insight**: Most current systems operate at L1-L2 (query and strategy). L3-L4 (pipeline and architecture evolution) is where the frontier research is headed, but also where reward hacking risks are highest.

---

## 2. Evidence Tables

### 2.1 Core Self-Evolving Search Systems

| System | Type | Mechanism | Key Result | Status |
|--------|------|-----------|------------|--------|
| [SE-Search](https://arxiv.org/abs/2603.03293) [1] | Search Agent | Memory purification + atomic query + dense RL rewards | +10.8 pts over Search-R1 | Paper (Mar 2026) |
| [Search-R1](https://arxiv.org/abs/2503.09516) [20] | Search Agent | RL-trained LLM learns when/how to search | +41% over RAG baselines | Open-source (Mar 2025) |
| [R1-Searcher](https://arxiv.org/abs/2503.05592) [22] | Search Agent | RL incentivizing search in LLMs | Companion to Search-R1 | Open-source (Mar 2025) |
| [MR-Search](https://huggingface.co/papers/2603.11327) [5] | Search Agent | Meta-RL with cross-episode self-reflection | Learns search strategy transfer | Paper (Mar 2026) |
| [ACQO](https://arxiv.org/html/2601.21208) [4] | Query Optimizer | RL for adaptive sub-query depth/strategy selection | Adaptive complex query handling | Paper (Jan 2026) |
| [SERAG](https://viterbi-web.usc.edu/~sabek/pdf/25_workshop_serag.pdf) [2] | RAG System | Self-evolving vector DB + query plan caching | Runtime self-improvement | Workshop (Jun 2025) |
| [SEFRQO](https://dl.acm.org/doi/abs/10.1145/3769826) [3] | Query Optimizer | Self-evolving fine-tuned RAG query optimizer | ACM SIGMOD publication | Published (2025) |

### 2.2 Self-Evolving Agent Frameworks (Applicable to Search)

| System | Stars/Adoption | Mechanism | License |
|--------|---------------|-----------|---------|
| [EvoAgentX](https://github.com/EvoAgentX/EvoAgentX) [8] | Active development | Modular agent evolution with iterative feedback | Open-source |
| [AgentEvolver](https://github.com/modelscope/AgentEvolver) [19] | ModelScope backed | Self-questioning + self-navigating + self-attributing | Apache 2.0 |
| [DSPy](https://github.com/stanfordnlp/dspy) [26] | 20k+ stars | GEPA (evolutionary), MIPROv2, SIMBA optimizers | MIT |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) [10] | AlphaEvolve clone | Quality-diversity evolution, island architecture | Open-source |
| [CodeEvolve](https://arxiv.org/abs/2510.14150) [7] | Academic | Islands-based GA + LLM orchestration | Open-source |
| [SAGE](https://arxiv.org/abs/2409.00872) [18] | Academic | Reflection + Ebbinghaus memory curve | Paper (Sep 2024) |

### 2.3 Evolutionary Code/Algorithm Search

| System | Creator | Key Achievement |
|--------|---------|-----------------|
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) [11] | Google DeepMind | Saved 0.7% global compute, improved Strassen's 1969 algo |
| [FunSearch](https://www.nature.com/articles/s41586-023-06924-6) [background knowledge] | Google DeepMind | Nature 2024, evolved novel mathematical functions |
| [OR-Agent](https://arxiv.org/html/2602.13769) [9] | Academic | Outperforms evolutionary baselines on OR problems |

### 2.4 Surveys and Meta-Resources

| Resource | Scope | Key Contribution |
|----------|-------|-----------------|
| [Survey: What, When, How, Where to Evolve](https://arxiv.org/abs/2507.21046) [16] | Comprehensive | 4 evolution targets × 2 temporal regimes × 3 paradigms |
| [Survey: Bridging FM and Lifelong Agents](https://arxiv.org/abs/2508.07407) [15] | Comprehensive | Taxonomy: single-agent / multi-agent / domain-specific |
| [Survey: Deep Research Agents](https://arxiv.org/abs/2508.12752) [29] | Search-focused | Planning → question → exploration → synthesis pipeline |
| [Survey: LLM Deep Search Agents](https://arxiv.org/html/2508.05668v3) [31] | Search-focused | Paradigm, optimization, evaluation, challenges |
| [Survey: Agentic RAG](https://arxiv.org/abs/2501.09136) [32] | RAG-focused | Autonomous planning + multi-turn dynamic retrieval |
| [Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents) [14] | Curated list | Bridges both surveys with code links |
| [ICLR 2026 RSI Workshop](https://recursive-workshop.github.io/) [23] | Workshop | Five lenses: targets, temporal regime, mechanisms, contexts, evidence |

---

## 3. Design Patterns

Seven recurring patterns emerged across all systems studied:

### Pattern 1: Reflection Loop
**Use**: Execute → observe outcome → reflect on failure → revise strategy → re-execute
**Found in**: SE-Search (memory purification), SAGE (reflective agents), MR-Search (cross-episode reflection), DSPy GEPA (reflection-guided optimization)
**Why it works**: Turns each search failure into a training signal without requiring gradient updates

### Pattern 2: Dense Reward Decomposition
**Use**: Break monolithic "good search" reward into fine-grained components (query quality, memory quality, outcome, format)
**Found in**: SE-Search (4-component dense reward), Search-R1 (retrieved token masking + outcome reward)
**Why it works**: Sparse rewards (only task completion) create credit assignment problems; dense rewards tell the agent which specific behavior to improve

### Pattern 3: Evolutionary Population Search
**Use**: Maintain population of candidate strategies → evaluate → select → mutate → next generation
**Found in**: AlphaEvolve (island-based GA), CodeEvolve (islands + LLM mutation), PromptBreeder (self-referential mutation), DéjàQ (MAP-Elites for training data)
**Trade-off**: More diverse exploration but higher compute cost. Island architecture helps parallelize.

### Pattern 4: Experience Memory with Forgetting
**Use**: Store successful search strategies, prune outdated ones
**Found in**: SAGE (Ebbinghaus forgetting curve), SE-Search (memory purification), AgentEvolver (experience reuse)
**Why it matters**: Unbounded memory leads to retrieval noise; forgetting curves prioritize recent and frequently-validated strategies

### Pattern 5: Meta-Agent Search
**Use**: An agent that designs/selects other agents or search strategies
**Found in**: ADAS (agent architecture search), AgentEvolver (self-questioning for task generation), OR-Agent (multi-agent research workflow)
**Risk**: Second-order optimization is harder to control; meta-agent may optimize for evaluability rather than actual quality

### Pattern 6: Self-Referential Improvement
**Use**: The system improves the process that improves itself
**Found in**: PromptBreeder (mutation-prompts evolve alongside task-prompts), DSPy GEPA (optimizer reflects on its own failures)
**Open question**: Does this converge or diverge? PromptBreeder showed convergence on benchmarks, but real-world stability is unproven

### Pattern 7: Compile-Then-Evolve
**Use**: Treat the search pipeline as a program, compile it against metrics, then evolve the compiled program
**Found in**: DSPy (compiling LM calls into optimized pipelines), AutoSearch/AVO (agent-as-variational-operator with judge.py as fitness function)
**Advantage**: Separates "what to evolve" from "how to evolve" — the compilation step makes evolution tractable

---

## 4. Risk Analysis

### 4.1 Reward Hacking / Goodhart's Law
**Risk level**: HIGH
**Mechanism**: Self-evolving systems optimize the metric, not the actual goal. If your judge scores keyword overlap, the system will learn to stuff keywords without improving results.
**Evidence**: AVO paper (arXiv:2603.24517) explicitly addresses this with anti-cheat mechanisms [background knowledge]. DéjàQ [28] uses MAP-Elites to maintain diversity specifically to counter mode collapse.
**Mitigation**: Multi-dimensional scoring, anti-novelty-collapse checks, human-in-the-loop validation at key checkpoints.

### 4.2 Scaffolding Ceiling
**Risk level**: MEDIUM
**Mechanism**: Prompt/workflow evolution may hit a ceiling where only weight updates (fine-tuning, RL) can make further progress. The ICLR 2026 RSI workshop [23] explicitly debates this boundary.
**Evidence**: SE-Search [1] and Search-R1 [20] use actual RL training, not just prompt evolution, suggesting the field is already moving past pure scaffold-level changes. DSPy GEPA [25] finds that reflective prompt evolution CAN outperform RL on some benchmarks, keeping the debate alive.

### 4.3 Catastrophic Forgetting
**Risk level**: MEDIUM
**Mechanism**: Evolved strategies may lose effectiveness on previously-solved query types as the system specializes.
**Evidence**: SAGE [18] addresses this with Ebbinghaus forgetting curves. Quality-diversity approaches (MAP-Elites) [28] maintain diverse solution archives to prevent mode collapse.
**Mitigation**: Append-only pattern stores, periodic regression testing, quality-diversity archives.

### 4.4 Evaluation Bottleneck
**Risk level**: HIGH
**Mechanism**: Self-evolution requires a reliable fitness signal. If the evaluator is wrong, evolution amplifies the error.
**Evidence**: AutoSearch protocol explicitly fixes judge.py as immutable to prevent the system from gaming its own evaluator [background knowledge]. Search-R1 [20] found that the choice of search engine significantly shapes RL training dynamics.
**Mitigation**: Fix the evaluator, evolve everything else. Use human validation to calibrate the evaluator periodically.

### 4.5 Compute Cost
**Risk level**: MEDIUM-LOW (decreasing)
**Mechanism**: Evolutionary approaches are inherently expensive (population maintenance, evaluation per candidate).
**Evidence**: AgentEvolver [19] specifically targets efficiency — 7B model outperforms 14B through efficient self-evolution. AlphaEvolve [11] uses Gemini Flash for breadth + Pro for depth to optimize cost.
**Mitigation**: Island architectures for parallelism, tiered model routing (cheap models for exploration, expensive for evaluation).

---

## 5. Trend Analysis

### Trend 1: From Static RAG to Self-Evolving Search (2023 → 2026)

The trajectory is clear:
1. **2023**: Static RAG (retrieve-then-generate, fixed retrieval)
2. **2024**: Adaptive RAG (choose retrieval strategy per query) [39]
3. **2025**: Agentic search (Search-R1 [20], R1-Searcher [22] — RL-trained search decisions)
4. **2026**: Self-evolving search (SE-Search [1], MR-Search [5] — cross-episode learning, memory purification)

**Causal mechanism**: Each step addresses a limitation of the previous one. Static RAG can't adapt; adaptive RAG can't learn; agentic search learns within episodes but forgets between them; self-evolving search carries knowledge across episodes.

### Trend 2: Convergence of RL and Evolutionary Approaches

Early self-evolving systems were either RL-based (Search-R1) or evolution-based (AlphaEvolve). In 2025-2026, we see hybrid approaches:
- DSPy GEPA [25] combines evolutionary search with reflective feedback
- OR-Agent [9] bridges evolutionary search with structured research
- CodeEvolve [7] pairs genetic algorithms with LLM-guided mutation

### Trend 3: Self-Evolving Search as 2026 Keyword

Chinese industry analysis explicitly identifies self-evolution as a 2026 trend [34]. ICLR 2025 had "Scaling Self-Improving Foundation Models" workshop; ICLR 2026 escalated to "AI with Recursive Self-Improvement" [23] — the framing shifted from "scaling" to "recursive," signaling increased ambition.

---

## 6. Comparison: Three Approaches to Self-Evolving Search

| Dimension | RL-Based (Search-R1) | Evolution-Based (AlphaEvolve) | Reflection-Based (SAGE/DSPy) |
|-----------|---------------------|-------------------------------|------------------------------|
| **What evolves** | Model weights (policy) | Code/algorithms (programs) | Prompts/strategies (scaffold) |
| **Feedback signal** | Outcome reward + format reward | Automated evaluator output | Self-reflection on failures |
| **Compute cost** | High (RL training) | High (population evaluation) | Low (inference-time only) |
| **Stability** | Moderate (reward shaping needed) | High (git commit/revert) | Low (prompt drift risk) |
| **Ceiling** | High (weight updates) | Very high (program space) | Medium (scaffolding ceiling) |
| **Speed of improvement** | Slow (training required) | Medium (generations needed) | Fast (within single session) |
| **Best for** | Learning optimal search policies | Discovering novel algorithms | Rapid strategy adaptation |

**Recommendation**: For most practical self-evolving search systems, start with reflection-based (cheapest, fastest), add RL for search policy optimization when you have enough data, and reserve evolutionary approaches for algorithm-level innovation.

---

## 7. Open Questions and Controversies

### Can scaffold-level evolution match weight updates?

**For**: DSPy GEPA [25] shows reflective prompt evolution outperforming RL on some benchmarks. PromptBreeder [13] achieves strong results through pure prompt evolution.

**Against**: SE-Search [1] and Search-R1 [20] achieve their best results through actual RL weight updates, not just prompt changes. The scaffolding ceiling appears real for complex multi-hop reasoning.

**Unresolved**: The boundary likely depends on task complexity. Simple search tasks may not need weight updates; complex multi-step research tasks probably do.

### Does self-evolution lead to filter bubbles or break them?

No system studied explicitly addresses this. Quality-diversity approaches (MAP-Elites, DéjàQ [28]) maintain diversity by design, which should resist filter bubbles. But RL-trained search agents (Search-R1 [20]) optimize for task completion, which could narrow search scope over time.

### Is a fixed evaluator sustainable?

The AVO/AutoSearch approach of fixing judge.py while evolving everything else is principled [background knowledge], but the evaluator may become the bottleneck. If the evaluator can't distinguish truly better search from Goodhart-optimized search, evolution stalls or goes wrong. The ICLR 2026 RSI workshop [23] organizes evidence of improvement as one of its five lenses.

---

## 8. Gap Declaration

What this research did NOT find:

1. **Production-deployed self-evolving search at scale**: No evidence of companies running self-evolving search in production beyond Google's AlphaEvolve [11] (which is for algorithm search, not information search). Perplexity, Google Search, etc. likely use adaptive mechanisms but don't publish self-evolution details.

2. **Benchmarks for self-evolving search**: SE-Search [1] evaluates on QA benchmarks, but there's no benchmark specifically designed to measure search self-improvement over time (e.g., performance on session N vs session N+100).

3. **Self-evolving search for non-English languages**: All systems found are English-centric. Chinese analysis discusses the trend [34][35] but no Chinese-language self-evolving search system was found.

4. **Safety/alignment for self-evolving search**: No formal safety framework for ensuring self-evolving search systems don't develop harmful search behaviors or filter bubbles.

5. **Cost-benefit analysis**: No paper quantifies when self-evolving search becomes worthwhile vs. simply using a better base model.

---

## 9. Recommendation for AutoSearch

Based on this research, AutoSearch's AVO approach is well-positioned:

1. **Your pattern store (`patterns.jsonl`) IS the skill library pattern** — accumulating winning strategies across sessions is exactly what SAGE [18] and AgentEvolver [19] do
2. **Your fixed judge.py IS the principled evaluator approach** — this is the same insight the ICLR 2026 workshop emphasizes: separate the evaluator from the thing being evaluated
3. **Your git commit/revert IS the evolution safety mechanism** — CodeEvolve [7] and AlphaEvolve [11] use the same approach

**Next steps to consider**:
- Add dense reward decomposition (Pattern 2) — break your judge score into per-query and per-platform feedback
- Add Ebbinghaus-style forgetting to patterns.jsonl — decay old patterns that haven't been validated recently
- Consider adding cross-session meta-RL (like MR-Search [5]) once you have enough session data

---

## Sources

[1] SE-Search — https://arxiv.org/abs/2603.03293
[2] SERAG — https://viterbi-web.usc.edu/~sabek/pdf/25_workshop_serag.pdf
[3] SEFRQO — https://dl.acm.org/doi/abs/10.1145/3769826
[4] ACQO — https://arxiv.org/html/2601.21208
[5] MR-Search — https://huggingface.co/papers/2603.11327
[6] SimRAG — https://www.amazon.science/publications/simrag-self-improving-retrieval-augmented-generation-for-adapting-large-language-models-to-specialized-domains
[7] CodeEvolve — https://arxiv.org/abs/2510.14150
[8] EvoAgentX — https://github.com/EvoAgentX/EvoAgentX
[9] OR-Agent — https://arxiv.org/html/2602.13769
[10] OpenEvolve — https://github.com/algorithmicsuperintelligence/openevolve
[11] AlphaEvolve — https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
[12] AlphaEvolve (paper) — https://arxiv.org/abs/2506.13131
[13] PromptBreeder — https://arxiv.org/abs/2309.16797
[14] Awesome-Self-Evolving-Agents — https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents
[15] Survey: Bridging FM and Lifelong Agents — https://arxiv.org/abs/2508.07407
[16] Survey: What/When/How/Where — https://arxiv.org/abs/2507.21046
[17] XMU Awesome-Self-Evolving-Agents — https://github.com/XMUDeepLIT/Awesome-Self-Evolving-Agents
[18] SAGE — https://arxiv.org/abs/2409.00872
[19] AgentEvolver — https://github.com/modelscope/AgentEvolver
[20] Search-R1 — https://arxiv.org/abs/2503.09516
[21] Search-R1 GitHub — https://github.com/PeterGriffinJin/Search-R1
[22] R1-Searcher — https://arxiv.org/abs/2503.05592
[23] ICLR 2026 RSI Workshop — https://recursive-workshop.github.io/
[24] ICLR 2026 RSI Workshop (OpenReview) — https://openreview.net/forum?id=OsPQ6zTQXV
[25] DSPy GEPA — https://dspy.ai/api/optimizers/GEPA/overview/
[26] DSPy GitHub — https://github.com/stanfordnlp/dspy
[27] DSPy (paper) — https://arxiv.org/abs/2310.03714
[28] DéjàQ — https://arxiv.org/html/2601.01931v1
[29] Deep Research Survey — https://arxiv.org/abs/2508.12752
[30] From Web Search to Agentic Deep Research — https://arxiv.org/abs/2506.18959
[31] Survey: LLM Deep Search Agents — https://arxiv.org/html/2508.05668v3
[32] Agentic RAG Survey — https://arxiv.org/abs/2501.09136
[33] SEAgent — https://arxiv.org/abs/2508.04700
[34] Self-Evolving as 2026 Keyword — https://finance.sina.com.cn/roll/2026-02-01/doc-inhkhmvm5291632.shtml
[35] AI自我进化综述 — https://zhuanlan.zhihu.com/p/1934227459366196529
[36] AgentEvolver Chinese Guide — https://www.modelscope.cn/learn/2804
[37] Self-Evolving Agents 2026 Open-Source — https://evoailabs.medium.com/self-evolving-agents-open-source-projects-redefining-ai-in-2026-be2c60513e97
[38] Rotifer Protocol — https://dev.to/rotiferdev/nvidia-proved-evolutionary-code-search-beats-humans-heres-what-an-open-protocol-for-it-looks-like-1b0e
[39] Adaptive RAG Guide — https://www.meilisearch.com/blog/adaptive-rag
[40] CycleQD (ICLR 2025) — https://proceedings.iclr.cc/paper_files/paper/2025/file/755acd0c7c07180d78959b6d89768207-Paper-Conference.pdf
[41] AlphaEvolve 中文分析 — https://zhuanlan.zhihu.com/p/1908151063078496189
[42] AgentEvolver paper — https://arxiv.org/abs/2511.10395
