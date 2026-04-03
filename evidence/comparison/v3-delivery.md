# AutoSearch v3.0 Delivery: Self-Evolving AI Agent Frameworks and Research

**Query**: "find open-source self-evolving AI agent frameworks and research"
**Date**: 2026-03-31
**Pipeline**: v3.0 (5-phase, Claude-first architecture)

---

## Executive Summary

Self-evolving AI agents have emerged as a distinct and rapidly growing research field in 2025-2026, defined by the core question: **how can AI agents improve themselves autonomously without human intervention?** This delivery covers 55+ unique items across open-source frameworks, research papers, commercial efforts, and Chinese community perspectives.

**AutoSearch discovered 28+ items not in Claude's training data**, primarily:
- New open-source frameworks released in late 2025 and 2026 (Agent0, AgentEvolver, OpenSpace, MemRL, MemSkill, MemGen, SCOPE, Geneclaw, EvoAgentX ecosystem)
- The Hyperagents paper from Meta AI (March 2026)
- Comprehensive surveys from Princeton/Tsinghua (2025)
- Real-time star counts and community adoption data
- Chinese-language survey coverage and community analysis on Zhihu

---

## 1. Foundational Paradigms

### The Three Questions of Self-Evolution
A comprehensive survey (Princeton, Tsinghua, CMU, Shanghai Jiao Tong, Sydney, 2025) establishes the theoretical framework:
- **What to evolve**: model parameters, context/prompts, tools, architecture [knowledge]
- **When to evolve**: during task execution (intra-test) vs. after task completion (inter-test) [knowledge]
- **How to evolve**: in-context learning, supervised fine-tuning, reinforcement learning [knowledge]

### Core Methods
| Method | Key Idea | Confidence |
|--------|----------|------------|
| Reflexion (Shinn et al., NeurIPS 2023) | Verbal RL with episodic memory, no weight updates | [knowledge] |
| STaR (Zelikman et al., 2022) | Bootstrap reasoning from self-generated rationales | [knowledge] |
| STOP (Zelikman et al., COLM 2024) | Recursive self-improvement of code scaffolds; LLM writes improver that improves itself | [verified] |
| Meta-Agent Search / ADAS (Hu et al., ICLR 2025) | Meta-agent iteratively programs new agent architectures from an archive of discoveries. F1 +13.6 on DROP, accuracy +14.4% on MGSM | [verified] |
| GPTSwarm (Zhuge et al., ICML 2024 Oral, top 1.5%) | Agents as optimizable graphs; node+edge optimization via RL | [discovered] |
| Prompt evolution / genetic programming | Treat prompts as genes, mutate + select via fitness | [knowledge] |

---

## 2. Landmark Open-Source Frameworks

### Tier 1: High-Impact Established Projects (1000+ stars)

| Project | Stars | Description | Provenance |
|---------|-------|-------------|------------|
| [Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents) | 2,001 | Comprehensive survey + curated resource list (Princeton/Tsinghua survey companion) | [discovered] |
| [Darwin Godel Machine (DGM)](https://github.com/jennyzzt/dgm) | 1,976 | Open-ended evolution of self-improving agents. On SWE-bench: 20.0% -> 50.0%. By Sakana AI | [discovered] |
| [HyperAgents](https://github.com/facebookresearch/HyperAgents) | 1,958 | Self-referential self-improving agents. Meta AI + UBC + Vector Institute. March 2026. Task + meta agent in single editable program | [discovered] |
| [AgentEvolver](https://github.com/modelscope/AgentEvolver) | 1,319 | Self-questioning + self-navigating + self-attributing. By Alibaba/ModelScope. Nov 2025 | [discovered] |
| [Agent0](https://github.com/aiming-lab/Agent0) | 1,113 | Self-evolving from zero data via co-evolution of curriculum + executor agents. +18% math, +24% general reasoning on Qwen3-8B-Base | [discovered] |
| [Self-Evolving-Agents](https://github.com/CharlesQ9/Self-Evolving-Agents) | 1,005 | Survey companion repository | [discovered] |
| [GPTSwarm](https://github.com/metauto-ai/GPTSwarm) | 1,010 | Language agents as optimizable graphs. ICML 2024 oral | [discovered] |

### Tier 2: Notable Recent Projects (50-1000 stars)

| Project | Stars | Description | Provenance |
|---------|-------|-------------|------------|
| [EvoAgentX](https://github.com/EvoAgentX/EvoAgentX) | 2,514+ | Self-evolving ecosystem; TextGrad, MIPRO, AFlow, EvoPrompt algorithms. EMNLP 2025 demo. +7.44% HotPotQA, +10% MBPP, +20% GAIA | [discovered] |
| [Yunjue-Agent](https://github.com/YunjueTech/Yunjue-Agent) | 417 | Fully reproducible, zero-start in-situ self-evolving agent system | [discovered] |
| [MemSkill](https://github.com/ViktorAxelsen/MemSkill) | 381 | Evolving memory skills for self-evolving agents. Feb 2026 | [discovered] |
| [MemGen](https://github.com/bingreeky/MemGen) | 342 | Generative latent memory. Outperforms ExpeL/AWM by up to 38.22%. Sep 2025 | [discovered] |
| [Blockcell](https://github.com/blockcell-labs/blockcell) | 233 | Self-evolving agent infrastructure | [discovered] |
| [OpenSpace (HKUDS)](https://github.com/HKUDS/OpenSpace) | ~500+ | Self-evolving skill engine. 3 evolution modes (FIX/DERIVED/CAPTURED). 46% token reduction. Collective intelligence across agents | [discovered] |
| [Tencent SelfEvolvingAgent](https://github.com/Tencent/SelfEvolvingAgent) | 87 | WebEvolver (EMNLP 2025), WebCoT, R-Zero (zero-data reasoning evolution) | [discovered] |
| [MUSE](https://github.com/KnowledgeXLab/MUSE) | 85 | Experience-driven self-evolving agent for long-horizon tasks. SOTA on TAC benchmark (51.78%, +20% over prev SOTA). Oct 2025 | [discovered] |
| [MemRL](https://github.com/MemTensor/MemRL) | 71 | Runtime RL on episodic memory. Frozen LLM + evolving memory scores. Jan 2026 | [discovered] |
| [SCOPE](https://github.com/JarvisPei/SCOPE) | N/A | Self-evolving prompt evolution. HLE: 14.23% -> 38.64%. GAIA: 32.73% -> 56.97%. Dec 2025 | [discovered] |
| [MOLTRON](https://github.com/adridder/moltron) | 52 | Self-evolving agents with autonomous skill learning | [discovered] |
| [MetaAgent](https://github.com/qhjqhj00/MetaAgent) | 44 | Self-evolving via tool meta-learning | [discovered] |
| [BabyAGI-ASI](https://github.com/oliveirabruno01/babyagi-asi) | 799 | Autonomous and Self-Improving BabyAGI variant | [discovered] |
| [Metabot](https://github.com/xvirobotics/metabot) | 479 | Supervised self-evolving agent organization infrastructure (Chinese origin) | [discovered] |

### Tier 3: Emerging / Experimental

| Project | Stars | Description | Provenance |
|---------|-------|-------------|------------|
| [Geneclaw](https://github.com/Clawland-AI/Geneclaw) | 34 | Self-evolving with 5-layer safety gatekeeper | [discovered] |
| [CoralMind](https://github.com/KoanJan/coralmind) | 2 | Self-evolving with self-planning capabilities | [discovered] |
| [MetaClaw](https://github.com/brooks376/MetaClaw-Open-Source-Self-Evolving-AI-Agent-Framework-with-Online-RL) | 1 | Online RL from real conversations | [discovered] |
| [EvoForge](https://github.com/binghandsom/EvoForge) | 1 | Dynamic skill generation and optimization | [discovered] |

---

## 3. Key Research Papers

### Surveys
| Paper | Venue/Date | Key Contribution | Provenance |
|-------|-----------|-----------------|------------|
| "A Comprehensive Survey of Self-Evolving AI Agents" (arXiv 2508.07407) | Aug 2025 | Taxonomy: what/when/how to evolve. Princeton + Tsinghua + CMU + SJTU + Sydney | [discovered] |
| "A Survey on Self-Evolution of Large Language Models" | 2024 | Earlier survey on LLM self-evolution | [knowledge] |
| XMU DeepLIT Awesome-Self-Evolving-Agents (69 stars) | 2025-2026 | Alternative curated list by Xiamen University | [discovered] |

### Breakthrough Papers (2024-2026)
| Paper | Venue | Key Result | Provenance |
|-------|-------|-----------|------------|
| ADAS / Meta Agent Search | ICLR 2025 | Meta-agent designs novel agent architectures from archive | [verified] |
| Darwin Godel Machine | NeurIPS 2025? | Self-improving agents via evolutionary code modification | [discovered] |
| Hyperagents | arXiv 2603.19461, Mar 2026 | Self-referential self-modification. Meta AI. Transferred: paper review -> math grading (imp@50=0.630) | [discovered] |
| AgentEvolver | arXiv 2511.10395, Nov 2025 | Self-questioning + self-navigating + self-attributing | [discovered] |
| Agent0 | arXiv 2511.16043, Nov 2025 | Zero-data co-evolution of curriculum + executor | [discovered] |
| MemRL | arXiv 2601.03192, Jan 2026 | Runtime RL on episodic memory, frozen LLM | [discovered] |
| MemSkill | arXiv 2602.02474, Feb 2026 | Evolving memory skills with designer component | [discovered] |
| MemGen | arXiv 2509.24704, Sep 2025 | Generative latent memory, spontaneously evolves human-like memory faculties | [discovered] |
| SCOPE | arXiv 2512.15374, Dec 2025 | Prompt evolution for agent effectiveness | [discovered] |
| GPTSwarm | ICML 2024 Oral | Agents as optimizable graphs | [discovered] |
| MUSE | arXiv 2510.08002, Oct 2025 | Experience-driven self-evolution for long-horizon tasks | [discovered] |
| R-Zero (Tencent) | 2025 | Zero-data reasoning evolution via challenger-solver loop | [discovered] |
| Self-Evolving Embodied AI | arXiv 2602.04411 | Continually adaptive intelligence for embodied agents | [discovered] |
| ShinkaEvolve (Sakana AI) | 2025 | Evolving algorithms with LLMs, orders of magnitude more efficiently | [discovered] |
| The AI Scientist v2 (Sakana AI) | Apr 2025 | Workshop-level autonomous research. Published in Nature | [discovered] |
| ELL-StuLife | Aug 2025 | Experience-driven lifelong learning framework + benchmark | [discovered] |
| Bloom (Anthropic) | 2026 | Open-source tool for automated agent evaluation | [discovered] |

### Classic/Foundational Papers
| Paper | Venue | Provenance |
|-------|-------|------------|
| Reflexion | NeurIPS 2023 | [knowledge] |
| Voyager | NeurIPS 2023 Oral | [knowledge] |
| ReAct | ICLR 2023 | [knowledge] |
| DSPy | ICLR 2024 | [knowledge] |
| Tree of Thoughts | NeurIPS 2023 | [knowledge] |
| Generative Agents | UIST 2023 | [knowledge] |
| STOP | COLM 2024 | [verified] |

---

## 4. Design Patterns in Self-Evolving Agents

| Pattern | Examples | Provenance |
|---------|----------|------------|
| **Reflection loop** | Reflexion, MUSE, MemSkill | [knowledge] |
| **Skill library / tool creation** | Voyager, OpenSpace, MOLTRON | [knowledge] + [verified] |
| **Meta-agent search** | ADAS, DGM, Hyperagents | [verified] |
| **Memory evolution** | MemRL, MemSkill, MemGen | [discovered] |
| **Prompt evolution** | SCOPE, EvoPrompt, DSPy | [discovered] |
| **Graph optimization** | GPTSwarm (node+edge optimization) | [discovered] |
| **Co-evolution** | Agent0 (curriculum+executor), R-Zero (challenger+solver) | [discovered] |
| **Collective intelligence** | OpenSpace (shared skill repository across agents) | [discovered] |
| **Self-referential modification** | Hyperagents (meta-agent edits itself) | [discovered] |
| **Experience-driven evolution** | MUSE, ELL-StuLife, MemRL | [discovered] |

---

## 5. Commercial Players and Industry

| Company | Focus | Status | Provenance |
|---------|-------|--------|------------|
| Sakana AI | DGM, AI Scientist, ShinkaEvolve | $479M total raised, $2.635B valuation (Nov 2025) | [verified] |
| Meta AI | Hyperagents, self-referential agents | Open-source release Mar 2026 | [discovered] |
| Alibaba/ModelScope | AgentEvolver | Open-source, 1,319 stars | [discovered] |
| Tencent AI Lab | WebEvolver, R-Zero, SelfEvolvingAgent | Dedicated research team (Seattle) | [discovered] |
| Cognition (Devin) | Autonomous coding agent | $2B+ valuation | [knowledge] |
| LangChain | LangGraph, agent orchestration | Production platform | [knowledge] |
| Latitude | Self-improving AI agent builder | ProductHunt launch Mar 2025 | [discovered] |
| Keak | AI-driven website self-improvement | ProductHunt | [discovered] |
| EvoAgentX org | Self-evolving agent ecosystem | 2,514+ GitHub stars | [discovered] |
| HKUDS | OpenSpace skill engine | Open-source | [discovered] |
| Metauto AI | GPTSwarm | Open-source, ICML 2024 | [discovered] |

---

## 6. Chinese Community Perspective

### Zhihu Coverage (Top Articles)
- "Self-Evolving Agents Survey: Toward ASI" -- 10,000+ word translation/analysis of the comprehensive survey [discovered]
- "Wang Mengdi Team Self-Evolving Agent Survey" -- Princeton team coverage [discovered]
- "From Static Models to Lifelong Evolution" -- framework analysis [discovered]
- "SCOPE: Prompt Self-Evolution Doubles Task Success Rate" -- practical technique coverage [discovered]
- "EvoAgentX: Self-Evolving Multi-Agent System" -- framework walkthrough [discovered]
- "ClawHub EvoMap" -- Agent evolution network discussion [discovered]

### CSDN Coverage
- "2026 Agentic AI 20 Framework Deep Evaluation" -- comprehensive framework comparison [discovered]
- "2025 AI Agent Full Analysis" -- industry landing guide [discovered]
- "19 Agent Framework Comparison (2025 Edition)" -- technical comparison [discovered]

### Juejin Coverage
- "2026 Top 10 AI Agent Frameworks on GitHub" -- trending frameworks overview [discovered]
- "LLM Agent Reflection Workflow Deep Analysis" -- technical deep-dive [discovered]
- "Multi-Agent Collaboration Workflow Analysis" -- design patterns [discovered]

**Chinese platform results: 30+ articles across 3 platforms**

---

## 7. Risks and Open Questions

| Issue | Status | Provenance |
|-------|--------|------------|
| Scaffolding ceiling: can prompt/workflow evolution rival weight updates? | Open debate. DGM+Hyperagents suggest yes for code tasks | [knowledge] + [verified] |
| Safety of self-modifying agents | Active concern. Geneclaw adds 5-layer safety gatekeeper | [knowledge] + [discovered] |
| Catastrophic forgetting during evolution | MemRL addresses by freezing LLM, evolving only memory | [discovered] |
| Evaluation difficulty | ELL-StuLife proposes lifelong learning benchmark | [discovered] |
| Reward hacking in self-evolution loops | Remains unsolved at scale | [knowledge] |
| Data dependency for evolution | Agent0 and R-Zero show zero-data evolution is possible | [discovered] |

---

## 8. Key Trends (2025-2026)

1. **Memory as the evolution substrate**: MemRL, MemSkill, MemGen all evolve memory rather than model weights, avoiding catastrophic forgetting
2. **Zero-data self-evolution**: Agent0, R-Zero eliminate need for human-curated training data
3. **Meta-agent architectures**: DGM, Hyperagents, ADAS -- agents that design/modify other agents
4. **Collective intelligence**: OpenSpace shows agents sharing evolved skills across a network
5. **Prompt evolution becoming systematic**: SCOPE, EvoPrompt move beyond ad-hoc prompt tuning to principled evolution
6. **Industry convergence**: Sakana AI ($479M), Meta AI, Alibaba, Tencent all investing heavily
7. **Chinese research community highly active**: Extensive Zhihu coverage, Tencent/Alibaba open-source contributions

---

## Statistics

| Metric | Count |
|--------|-------|
| Total unique items | 55+ |
| Own-knowledge items | 27 |
| Discovered items (not in training data) | 28+ |
| Verified items (training data confirmed/updated) | 5 |
| GitHub repos found | 30+ |
| Research papers identified | 20+ |
| Commercial players covered | 11 |
| Chinese platform articles found | 30+ |
| Channels used | 8 |
| Search queries executed | 15 |
| Unique URLs | 95+ |
