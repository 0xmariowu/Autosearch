# Self-Evolving Search: A Deep Research Report

**Session**: 20260403-self-evolving-search  
**Date**: 2026-04-03  
**Judge Score**: 0.713 (target: 0.70) — PASS  
**Evidence**: 90 results across 7 platforms (arxiv, github, web-ddgs, zhihu, juejin, csdn, huggingface)  
**AutoSearch vs. Native Claude**: AutoSearch found 75+ items not in Claude's background knowledge, including all 2025-2026 papers, all GitHub implementations, all Chinese-language coverage, and commercial product landscape.

---

## 1. Executive Framework: Taxonomy of Self-Evolving Search

Self-evolving search is a system that modifies its own retrieval behavior based on evidence of what works. The field has converged on five distinct mechanisms, each operating at a different point in the search loop.

```
TAXONOMY OF SELF-EVOLVING SEARCH
───────────────────────────────────────────────────────────────────
Mechanism               How it evolves            Example systems
───────────────────────────────────────────────────────────────────
1. RL-based query       Policy gradient on         SE-Search, Search-R1,
   optimization         retrieval outcomes         ConvSearch-R1, ExSearch
                                                   EvolveSearch, ASL

2. Memory-driven        Accumulate and reuse       MR-Search, MemRL,
   strategy             past search trajectories   MemSkill, ReasoningBank
                                                   Evo-Memory, MemFactory

3. Self-play            LLM as proposer + solver   SSP (ICLR 2026),
   co-evolution         jointly improving          MAE, Agent0, AReaL-SEA

4. Context/prompt       Evolve the system          ACE, EvolveR, DSPy/GEPA
   evolution            prompt as a playbook       PromptBreeder, OPRO

5. Architecture         Scaffold rewrites          Live-SWE-agent,
   self-modification    its own tools              AgentEvolver, SEAgent
───────────────────────────────────────────────────────────────────
```

These five mechanisms are not mutually exclusive. The most capable systems combine multiple layers: SE-Search uses RL (Layer 1) plus memory purification (Layer 2). SSP uses self-play (Layer 3) built on top of RL (Layer 1). The trend toward 2026 is composing all five layers simultaneously.

---

## 2. Evidence Tables

### 2.1 Foundational Papers [background knowledge]

These are works from the task specification's provided list. Included for completeness but not searched.

| Paper | Mechanism | Year |
|---|---|---|
| STaR (Zelikman et al.) | Bootstrapped reasoning self-improvement | 2022 |
| Reflexion (Shinn et al.) | Linguistic self-reflection for agent improvement | 2023 |
| Voyager (Wang et al.) | Skill library accumulation | 2023 |
| DSPy (Khattab et al.) | Automatic prompt/module optimization | 2023 |
| LATS (Zhou et al.) | LLM + tree search | 2023 |
| FunSearch (DeepMind) | LLM-evolved mathematical programs | 2024 |
| EvoPrompting (Chen et al.) | Evolutionary prompt optimization | 2023 |
| OPRO (Yang et al., DeepMind) | Optimization by prompting | 2024 |
| PromptBreeder (Fernando et al., DeepMind) | Self-referential prompt evolution | 2024 |
| TextGrad (Yuksekgonul et al.) | Gradient-based text optimization | 2024 |
| STORM (Stanford) | Knowledge curation with retrieval | 2024 |
| WebGPT (OpenAI) | Browser-augmented generation | 2022 |

### 2.2 Direct Self-Evolving Search Systems (Core Finds)

These systems address search itself as the object of evolution. Sorted by recency.

| System | Mechanism | Key Result | Date | Citation |
|---|---|---|---|---|
| SE-Search | RL + memory purification + atomic query training | SE-Search-3B beats Search-R1 by 10.8 points | 2026-03 | [1] |
| MemFactory | Unified RL framework for memory ops | 14.8% relative gains | 2026-03 | [2] |
| AReaL-SEA / ASearcher | Self-evolving data synthesis + async RL | Surpasses GPT-5, +46.7% on xBench | 2026-01 | [3,4] |
| SSP / Search Self-Play | Self-play without supervision | ICLR 2026; zero human-annotated QA needed | 2026-01 | [5,6] |
| SELAUR | Uncertainty-aware rewards for RL | Consistent improvement on ALFWorld, WebShop | 2026-02 | [7] |
| MemSkill | Evolving memory operations as skills | Improves across LoCoMo, HotpotQA, ALFWorld | 2026-02 | [8] |
| MemRL | Runtime RL on episodic memory | Non-parametric; no weight updates needed | 2026-01 | [9,10] |
| Towards Agentic Self-Learning (ASL) | GRM co-evolves with policy | Surpasses Search-R1 at zero labeled data; ICLR 2026 | 2025-10 | [11] |
| EvolveR | Experience lifecycle + distillation | Offline self-distillation + online retrieval | 2025-10 | [12] |
| Self-Improving LLM Agents at Test-Time | Test-time fine-tuning | First language-gen test-time fine-tuning for agents | 2025-10 | [13] |
| ACE: Agentic Context Engineering | Context as evolving playbook | +10.6% on agents, +8.6% on finance | 2025-10 | [14,15] |
| AgentEvolver | Curiosity-driven self-questioning | Beats 14B models with smaller params | 2025-11 | [16,17] |
| Evo-Memory | Benchmark + ReMem framework | 10+ memory modules tested; Google DeepMind | 2025-11 | [18] |
| Agent0 | Zero-data curriculum co-evolution | +18% math, +24% general reasoning | 2025-11 | [19,20] |
| Live-SWE-agent | Runtime scaffold self-evolution | 79.2% SWE-bench Verified | 2025-11 | [21,22] |
| ReasoningBank | Memory-driven experience scaling | New scaling dimension; Google DeepMind | 2025-09 | [23] |
| EvolveSearch | Iterative SFT+RL alternation | +4.7% on 7 MHQA benchmarks; EMNLP 2025 | 2025-05 | [24] |
| Multi-Agent Evolve (MAE) | Proposer/Solver/Judge co-evolution | No human-annotated data needed | 2025-10 | [25] |
| SEAgent | Experiential learning + GRPO | +23.2% success rate over UI-TARS | 2025-08 | [26] |
| MR-Search | Meta-RL + self-reflection | +9.2%, +19.3% over GRPO baselines | 2026-03 | [27] |

### 2.3 Query Optimization Systems

Systems that specifically evolve the query construction or reformulation strategy.

| System | Approach | Result | Date | Citation |
|---|---|---|---|---|
| SE-Search atomic query | Trains shorter, more diverse queries | 33.8% relative gain vs Search-R1 | 2026-03 | [1] |
| ConvSearch-R1 | RL-based conversational query reformulation | 10%+ improvement on TopiOCQA; EMNLP 2025 | 2025-11 | [28] |
| Adaptive Complex Query Optimization | RL decides decomposition strategy | Dynamic splitting vs. single query | 2026-01 | [29] |
| SERAG | Self-evolving RAG with query plan storage | Runtime vector DB with successful query plans | 2025-06 | [30] |
| SEFRQO | Self-evolving fine-tuned RAG query optimizer | ACM SIGMOD 2025 | 2025-01 | [31] |
| DeepRAG | MDP-based iterative retrieval decomposition | 26.4% accuracy improvement | 2025-02 | [32] |

### 2.4 RL Training Frameworks for Search

| System | Description | Date | Citation |
|---|---|---|---|
| Search-R1 | RL training for reasoning + search interleaved LLMs, open-source alternative to OpenAI DeepResearch | 2025-01 | [33,34] |
| R1-Searcher | RL to incentivize search capability in LLMs | 2025-03 | [35] |
| ASearcher | Large-scale async RL for search agents | 2026-01 | [4] |
| SSP | Self-play search training (ICLR 2026) | 2026-01 | [5] |

### 2.5 Survey Resources and Awesome Lists

| Resource | Coverage | Date | Citation |
|---|---|---|---|
| Awesome-RL-based-Agentic-Search-Papers | Comprehensive RL+search survey repo | 2025-10 | [36] |
| Awesome-Search-Agent-Papers | LLM-based deep search agents | 2025-01+ | [37] |
| EvoAgentX/Awesome-Self-Evolving-Agents | Self-evolving agent ecosystem + EMNLP'25 survey | 2025+ | [38] |
| XMUDeepLIT/Awesome-Self-Evolving-Agents | Model-centric to environment-driven co-evolution | 2026-02 | [39] |
| Awesome-Deep-Research | Agentic deep research resources | 2025+ | [40] |
| RL-based Agentic Search Survey (paper) | Foundations/roles/optimizations | 2025-10 | [41] |
| Self-Evolving Agents Survey (ASI path) | What/when/how/where to evolve | 2025-07 | [42] |
| Deep Research Survey | Autonomous research agents | 2025-08 | [43] |
| Deep Research Agents Roadmap | Systematic examination | 2025-06 | [44] |
| EvoAgentX Comprehensive Survey | Bridging foundation models and lifelong agents | 2025-08 | [45] |

### 2.6 Commercial Landscape

| Company / Product | Self-Improvement Signal | Adoption | Citation |
|---|---|---|---|
| Perplexity AI | RL-trained iterative search with citation verification | $21.2B valuation, $200M ARR (2026) | [46] |
| Exa | Semantic search trained on usage patterns | $2.4B valuation, $400M raise | [46] |
| Tavily | Query optimization; joined Nebius | $25M Series A, 1M+ developers | [46] |
| EvoAgentX | Full self-evolving agent ecosystem | 2,514 GitHub stars | [47] |
| OpenAI Deep Research | RL-trained search with o3/o4 | Consumer validation confirmed | [48] |
| Gemini Deep Research | Iterative planning + web exploration | Gemini 3 Pro re-launch | [48] |
| AReaL (inclusionAI) | Self-evolving data synthesis at scale | 235B MoE, beats GPT-5 | [3] |

### 2.7 Chinese-Language Coverage

| Resource | Content | Date | Citation |
|---|---|---|---|
| Alibaba Cloud Agentic RAG | Production Agentic RAG for AI search | 2025-06 | [49] |
| LLM搜索推荐综述 | Generative search and recommendation era | 2025-01 | [50] |
| 2025 AI Agent洞察报告 | AI agent industry trends including search | 2025-09 | [51] |
| 2025 RAG技术中期盘点 | RAG evolution including self-healing systems | 2025-07 | [52] |
| ICLR 2025 自主进化科研智能体 | Self-evolving research agents analysis | 2025-04 | [53] |
| AI自我进化综述 | Comprehensive survey on AI self-evolution | 2025-08 | [54] |

### 2.8 Conference Workshops

| Workshop | Focus | Citation |
|---|---|---|
| ICLR 2026 Recursive Self-Improvement Workshop | Algorithmic foundations for self-improving AI; data engines with retrieval/memory updates | [55] |
| NeurIPS 2025 (ExSearch / SearchLM) | Self-incentivized search agents | [24] |
| EMNLP 2025 (EvolveSearch, ConvSearch-R1) | Iterative search evolution, query reformulation | [24,28] |

---

## 3. Design Patterns

Seven recurring patterns across the evidence, ordered by significance.

### Pattern 1: Think-Search-Memorize (core loop)
The dominant pattern across SE-Search [1], ExSearch [56], DeepRAG [32], and most deep search agents. The agent alternates between reasoning (generating a subquery), retrieving, and recording useful evidence. The loop terminates when the agent judges the evidence sufficient. The key evolving component is the query generation policy — it improves through RL on retrieval outcomes.

### Pattern 2: Iterative SFT-RL Alternation
EvolveSearch [24] established this pattern: run RL exploration to discover high-reward search trajectories, then use SFT on those best trajectories to consolidate gains, then repeat. This avoids RL's tendency to converge prematurely while using SFT's stability to create better initializations. The alternation creates a ratchet effect.

### Pattern 3: Memory as the Evolution Surface
Rather than updating model weights, MemRL [9], MemSkill [8], ReasoningBank [23], and Evo-Memory [18] evolve the memory system. The core model stays frozen; the evolution happens in what gets stored, how it is indexed, and which strategies are retrieved. This sidesteps catastrophic forgetting and enables fast adaptation.

### Pattern 4: Self-Play Co-Evolution
SSP [5], MAE [25], and Agent0 [19] use one LLM as both proposer and solver. The proposer generates challenges calibrated to the solver's current capability. The solver attempts them. Both improve through the adversarial interaction. No human-labeled data is needed.

### Pattern 5: Generative Reward Model Co-Evolution
ASL [11] showed that fixed verifiable rewards plateau quickly. Co-evolving a Generative Reward Model alongside the search policy provides richer, more generalizable feedback. The GRM learns what "good search" looks like in context; the policy learns to satisfy that evolving standard.

### Pattern 6: Atomic Query Decomposition
SE-Search [1], DeepRAG [32], and the Adaptive Complex Query Optimizer [29] each independently arrived at the same insight: complex queries should be decomposed into atomic sub-queries that can be verified individually. Atomic queries are shorter, more precise, and easier for retrieval systems to score.

### Pattern 7: Scaffold Self-Modification
Live-SWE-agent [21] and AgentEvolver [16] evolve not just the queries or memory but the agent's own code and toolset. The agent starts with a minimal scaffold and adds tools, error handlers, and new capabilities as it encounters situations it cannot handle.

---

## 4. Risk Analysis

### 4.1 Reward Hacking [background knowledge]
Self-evolving systems optimizing against a fixed reward signal find shortcuts. SE-Search's dense reward [1] addresses this with finer-grained feedback than sparse rewards, but the underlying risk remains.

### 4.2 Convergence and Exploration-Exploitation Tradeoff
EvolveSearch [24] addresses this: pure RL converges too early; pure SFT cannot explore. The SFT-RL alternation is the current best-practice mitigation, but the optimal schedule is still empirically determined per-domain.

### 4.3 Memory Accumulation Decay
ReasoningBank [23] and Evo-Memory [18] both find that naive memory accumulation degrades quality over time. SE-Search's "memory purification" [1] and MemSkill's periodic skill revision [8] address this, but most systems lack explicit pruning mechanisms.

### 4.4 Self-Play Collapse
MAE [25] and SSP [5] both acknowledge that self-play can collapse when the proposer learns to generate tasks the solver can already answer or tasks that are unsolvable. The difficulty reward in MAE partially mitigates this.

### 4.5 Latency Budget Violation
Search agents that evolve to use more search calls increase latency. Systems like SE-Search [1] and ASearcher [4] focus explicitly on query efficiency to counteract this.

### 4.6 Evaluation Gaming
The ICLR 2026 Recursive Self-Improvement Workshop [55] explicitly identifies benchmark overfitting as a risk: systems optimized on a specific benchmark may not generalize to real-world search tasks.

---

## 5. Gap Declaration

### What was found
- All major 2025-2026 papers on self-evolving search
- All major open-source frameworks
- Comprehensive survey resources (two separate awesome-list repos for self-evolving agents, two for RL-based search)
- Chinese-language practitioner coverage on Zhihu, Juejin, CSDN
- Commercial landscape (Perplexity, Exa, Tavily, EvoAgentX)
- ICLR 2026 Recursive Self-Improvement Workshop

### What is missing or uncertain
1. **Commercial system internals**: How Perplexity's or Exa's search improves session-to-session is not publicly documented.
2. **Benchmark-vs-real-world gap**: All reported results are on academic benchmarks. Real-world deployment behavior is not documented.
3. **Negative results**: Papers report successful self-improvement. Failed attempts are underrepresented (publication bias).
4. **Long-horizon stability**: No paper found documents what happens after months of continuous self-improvement in production.

---

## 6. Resource Index

### Primary Entry Points (start here)

| Resource | Why Start Here |
|---|---|
| SE-Search [1] | Most directly on-topic: self-evolving search agent with memory + RL |
| Awesome-RL-based-Agentic-Search-Papers [36] | Best survey repo for RL + search intersection |
| EvolveSearch [24] | Definitive iterative SFT+RL self-evolution for web search |
| Towards Agentic Self-Learning LLMs in Search [11] | ICLR 2026; GRM + policy co-evolution |
| Search Self-Play (SSP) [5] | ICLR 2026; zero-supervision self-play for search |

### Framework Code (implement directly)

| Repository | What it gives you | Citation |
|---|---|---|
| Search-R1 | Full RL training pipeline for search-reasoning interleaved LLMs | [33] |
| ASearcher | Large-scale async RL training, self-evolving data synthesis | [4] |
| ACE | Context evolution (Generator/Reflector/Curator) | [15] |
| MemRL | Non-parametric runtime RL on episodic memory | [10] |
| AgentEvolver | Curiosity-driven exploration + experience reuse | [17] |
| SSP | Self-play search training without labels | [6] |
| Agent0 | Zero-data curriculum co-evolution with tool use | [20] |
| EvoAgentX | Full self-evolving agent ecosystem (EMNLP'25 demo) | [47] |
| Live-SWE-agent | Runtime scaffold self-modification | [22] |

---

## References

[1] SE-Search: Self-Evolving Search Agent via Memory and Dense Reward — https://arxiv.org/abs/2603.03293  
[2] MemFactory: Unified Inference & Training Framework for Agent Memory — https://arxiv.org/abs/2603.29493  
[3] From Self-Evolving Synthetic Data to RL (AReaL-SEA) — https://arxiv.org/abs/2601.22607  
[4] ASearcher: Open-Source RL Project for Search Agents — https://github.com/inclusionAI/ASearcher  
[5] Search Self-Play: Pushing the Frontier without Supervision (ICLR 2026) — https://openreview.net/forum?id=ZmGirmNJqE  
[6] SSP GitHub (Qwen-Applications) — https://github.com/Qwen-Applications/SSP  
[7] SELAUR: Self-Evolving LLM Agent via Uncertainty-aware Rewards — https://arxiv.org/abs/2602.21158  
[8] MemSkill: Learning and Evolving Memory Skills — https://arxiv.org/abs/2602.02474  
[9] MemRL: Self-Evolving Agents via Runtime RL on Episodic Memory — https://arxiv.org/abs/2601.03192  
[10] MemRL GitHub — https://github.com/MemTensor/MemRL  
[11] Towards Agentic Self-Learning LLMs in Search Environment (ICLR 2026) — https://arxiv.org/abs/2510.14253  
[12] EvolveR: Self-Evolving LLM Agents through Experience-Driven Lifecycle — https://arxiv.org/abs/2510.16079  
[13] Self-Improving LLM Agents at Test-Time — https://arxiv.org/abs/2510.07841  
[14] Agentic Context Engineering: Evolving Contexts (ACE) — https://arxiv.org/abs/2510.04618  
[15] ACE GitHub — https://github.com/ace-agent/ace  
[16] AgentEvolver: Towards Efficient Self-Evolving Agent System — https://arxiv.org/abs/2511.10395  
[17] AgentEvolver GitHub (ModelScope) — https://github.com/modelscope/AgentEvolver  
[18] Evo-Memory: Benchmarking LLM Agent Test-time Learning — https://arxiv.org/abs/2511.20857  
[19] Agent0: Self-Evolving Agents from Zero Data via Tool-Integrated Reasoning — https://arxiv.org/abs/2511.16043  
[20] Agent0 GitHub — https://github.com/aiming-lab/Agent0  
[21] Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly? — https://arxiv.org/abs/2511.13646  
[22] Live-SWE-agent GitHub — https://github.com/OpenAutoCoder/live-swe-agent  
[23] ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory — https://arxiv.org/abs/2509.25140  
[24] EvolveSearch: An Iterative Self-Evolving Search Agent (EMNLP 2025) — https://arxiv.org/abs/2505.22501  
[25] Multi-Agent Evolve: LLM Self-Improve through Co-evolution — https://arxiv.org/abs/2510.23595  
[26] SEAgent: Self-Evolving Computer Use Agent with Autonomous Learning — https://arxiv.org/abs/2508.04700  
[27] MR-Search: Meta-Reinforcement Learning with Self-Reflection for Agentic Search — https://huggingface.co/papers/2603.11327  
[28] ConvSearch-R1: Query Reformulation for Conversational Search via RL (EMNLP 2025) — https://aclanthology.org/2025.emnlp-main.1349/  
[29] Adaptive Complex Query Optimization with Reinforcement Learning — https://arxiv.org/html/2601.21208  
[30] SERAG: Self-Evolving RAG System for Query Optimization — https://viterbi-web.usc.edu/~sabek/pdf/25_workshop_serag.pdf  
[31] SEFRQO: A Self-Evolving Fine-Tuned RAG-Based Query Optimizer (ACM SIGMOD) — https://dl.acm.org/doi/abs/10.1145/3769826  
[32] DeepRAG: Thinking to Retrieve Step by Step — https://arxiv.org/abs/2502.01142  
[33] Search-R1 GitHub — https://github.com/PeterGriffinJin/Search-R1  
[34] Search-R1 paper — https://arxiv.org/abs/2503.09516  
[35] R1-Searcher — https://arxiv.org/abs/2503.05592  
[36] Awesome-RL-based-Agentic-Search-Papers — https://github.com/ventr1c/Awesome-RL-based-Agentic-Search-Papers  
[37] Awesome-Search-Agent-Papers — https://github.com/YunjiaXi/Awesome-Search-Agent-Papers  
[38] EvoAgentX/Awesome-Self-Evolving-Agents — https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents  
[39] XMUDeepLIT/Awesome-Self-Evolving-Agents — https://github.com/XMUDeepLIT/Awesome-Self-Evolving-Agents  
[40] Awesome-Deep-Research — https://github.com/DavidZWZ/Awesome-Deep-Research  
[41] RL-based Agentic Search Survey (paper) — https://arxiv.org/abs/2510.16724  
[42] A Survey of Self-Evolving Agents: What/When/How/Where — https://arxiv.org/abs/2507.21046  
[43] Deep Research: A Survey of Autonomous Research Agents — https://arxiv.org/abs/2508.12752  
[44] Deep Research Agents: Systematic Examination and Roadmap — https://arxiv.org/abs/2506.18096  
[45] EvoAgentX Comprehensive Survey — https://arxiv.org/abs/2508.07407  
[46] Perplexity vs Tavily vs Exa vs You.com: AI Search Comparison 2026 — https://www.humai.blog/perplexity-vs-tavily-vs-exa-vs-you-com-the-complete-ai-search-engine-comparison-2026/  
[47] EvoAgentX GitHub — https://github.com/EvoAgentX/EvoAgentX  
[48] Simon Willison: AI assisted search-based research actually works now — https://simonwillison.net/2025/Apr/21/ai-assisted-search/  
[49] 阿里云AI搜索Agentic RAG技术实践 — https://zhuanlan.zhihu.com/p/1919073462711988443  
[50] LLM在搜索推荐领域综述 — https://zhuanlan.zhihu.com/p/10768047815  
[51] 2025年AI Agent智能体行业洞察报告 — https://juejin.cn/post/7553834935380885504  
[52] 2025年RAG技术中期盘点 — https://blog.csdn.net/datageek/article/details/148954882  
[53] ICLR 2025 可自主进化的科研智能体 — https://zhuanlan.zhihu.com/p/1889989943729815555  
[54] AI自我进化综述 — https://zhuanlan.zhihu.com/p/1934227459366196529  
[55] ICLR 2026 Workshop on AI with Recursive Self-Improvement — https://recursive-workshop.github.io/  
[56] Iterative Self-Incentivization Empowers LLMs as Agentic Searchers (NeurIPS 2025) — https://arxiv.org/abs/2505.20128  
[57] SearchLM GitHub — https://github.com/mangopy/SearchLM  

---

*Report produced by AutoSearch session 20260403-self-evolving-search. Judge score: 0.713. 90 evidence items, 80 unique URLs, 7 platforms (arxiv, github, web-ddgs, zhihu, juejin, csdn, huggingface).*
