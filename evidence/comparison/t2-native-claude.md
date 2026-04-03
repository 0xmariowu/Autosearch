# Survey of LLM Memory Architectures and Implementations

**Method**: Native Claude (training knowledge + WebSearch + `gh search repos`)
**Wall clock time**: 213 seconds
**Date**: 2026-03-31

---

## 1. Conceptual Framework

### 1.1 Memory Taxonomy from Cognitive Science

LLM memory architectures draw heavily from cognitive science and classical cognitive architectures (ACT-R, Soar). The standard taxonomy maps human memory types to agent components:

| Human Memory Type | Agent Analog | Description |
|---|---|---|
| **Working Memory** | Context window / scratchpad | Active reasoning state; recent perceptual input, goals, intermediate results |
| **Episodic Memory** | Conversation logs, experience traces | Sequences of past behaviors and interactions, time-stamped |
| **Semantic Memory** | Knowledge bases, knowledge graphs | Facts about the world, stable over time |
| **Procedural Memory** | Skill libraries, tool definitions | Learned behaviors and reusable action sequences |

The CoALA framework (Cognitive Architectures for Language Agents, [arXiv:2309.02427](https://arxiv.org/abs/2309.02427)) formalizes this mapping, proposing that LLM agents can be understood through the same observe-decide-act pattern found in Soar and ACT-R.

### 1.2 Parametric vs Non-Parametric Memory

A fundamental distinction in LLM memory:

- **Parametric memory**: Knowledge encoded in model weights during training. Frozen at inference time (unless fine-tuned). Analogous to long-term implicit knowledge.
- **Non-parametric memory**: External knowledge stores (vector databases, knowledge graphs, document stores) accessed at inference time. Can be updated dynamically.

RAG (Retrieval-Augmented Generation) bridges these: parametric memory is the model's "long-term memory," while retrieved context serves as "short-term memory" ([arXiv:2312.10997](https://arxiv.org/abs/2312.10997)).

### 1.3 Evolutionary Framework

A recent survey ([OpenReview](https://openreview.net/forum?id=l9Ly41xxPb)) proposes three evolutionary stages of LLM agent memory:

1. **Storage** (trajectory preservation): Raw logging of agent experiences
2. **Reflection** (trajectory refinement): Synthesizing stored experiences into higher-level insights
3. **Experience** (trajectory abstraction): Distilling transferable knowledge from reflected experiences

### 1.4 Dimensional Classification

The survey "From Human Memory to AI Memory" ([arXiv:2504.15965](https://arxiv.org/abs/2504.15965)) proposes a three-dimensional classification:

- **Object dimension**: Personal vs System memory
- **Form dimension**: Parametric vs Non-parametric
- **Time dimension**: Short-term vs Long-term

These three dimensions produce eight quadrants, each representing a distinct memory configuration.

---

## 2. Academic Papers (with arXiv links)

### 2.1 Foundational Works

| Paper | Year | Venue | Key Contribution |
|---|---|---|---|
| [Generative Agents](https://arxiv.org/abs/2304.03442) | 2023 | UIST | Memory stream + reflection + planning. Foundational agent memory architecture |
| [MemGPT](https://arxiv.org/abs/2310.08560) | 2023 | ICLR | OS-inspired virtual context management. Self-editing memory via tool calls |
| [Reflexion](https://arxiv.org/abs/2303.11366) | 2023 | NeurIPS | Verbal reinforcement learning. Episodic memory of self-reflections |
| [Voyager](https://arxiv.org/abs/2305.16291) | 2023 | -- | Skill library as procedural memory. Executable code indexed by embeddings |
| [RAG Survey](https://arxiv.org/abs/2312.10997) | 2023 | -- | Comprehensive survey of Naive/Advanced/Modular RAG paradigms |

### 2.2 Graph-Based and Structured Memory

| Paper | Year | Venue | Key Contribution |
|---|---|---|---|
| [HippoRAG](https://arxiv.org/abs/2405.14831) | 2024 | NeurIPS | Hippocampal-inspired: LLMs + knowledge graphs + Personalized PageRank |
| [RAPTOR](https://arxiv.org/abs/2401.18059) | 2024 | ICLR | Tree-structured hierarchical retrieval via recursive clustering/summarization |
| [LightRAG](https://arxiv.org/abs/2410.05779) | 2024 | EMNLP 2025 | Dual-level retrieval with graph + vector. Five retrieval modes |
| [Zep](https://arxiv.org/abs/2501.13956) | 2025 | -- | Temporal knowledge graph tracking fact changes over time |
| [A-MEM](https://arxiv.org/abs/2502.12110) | 2025 | NeurIPS 2025 | Zettelkasten-inspired self-organizing memory with dynamic indexing |

### 2.3 Memory Operating Systems and Advanced Architectures (2025-2026)

| Paper | Year | Key Contribution |
|---|---|---|
| [MemOS](https://arxiv.org/abs/2505.22101) | 2025 | Three memory types: plaintext, parametric (LoRA), activation (KV-cache) |
| [EverMemOS](https://arxiv.org/abs/2601.02163) | 2026 | Engram-inspired lifecycle: Episodic Trace -> Semantic Consolidation -> Reconstructive Recollection. 92.3% on LoCoMo |
| [MAGMA](https://arxiv.org/abs/2601.03236) | 2026 | Multi-graph (semantic/temporal/causal/entity). 45.5% higher accuracy, 95% token reduction |
| [Mnemis](https://arxiv.org/abs/2602.15313) | 2026 | Microsoft. System-1 similarity + System-2 global selection on hierarchical graphs. 93.9 on LoCoMo |
| [Continuum Memory](https://arxiv.org/abs/2601.09913) | 2026 | Continuum memory architectures for long-horizon agents |
| [Agentic Memory](https://arxiv.org/abs/2601.01885) | 2026 | Unified long-term and short-term memory management |

### 2.4 Surveys

| Paper | Year | Venue |
|---|---|---|
| [From Human Memory to AI Memory](https://arxiv.org/abs/2504.15965) | 2025 | arXiv |
| [Memory in the Age of AI Agents](https://arxiv.org/abs/2512.13564) | 2025 | arXiv |
| [Memory Mechanism of LLM-based Agents](https://dl.acm.org/doi/10.1145/3748302) | 2024 | ACM TOIS |
| [From Storage to Experience](https://openreview.net/forum?id=l9Ly41xxPb) | 2026 | OpenReview |
| [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) | 2023 | arXiv |

### 2.5 Security Papers

| Paper | Year | Key Finding |
|---|---|---|
| [MemoryGraft](https://arxiv.org/abs/2512.16962) | 2025 | Persistent compromise via poisoned experience retrieval |
| [MINJA](https://arxiv.org/abs/2503.03704) | 2025 | Memory injection via queries and output observations alone |
| [Cognitive Memory in LLMs](https://arxiv.org/abs/2504.02441) | 2025 | Cognitive memory concept mapping to LLM architectures |

---

## 3. Open-Source Projects

### 3.1 Major Projects (>10K stars)

| Project | Stars | Description | URL |
|---|---|---|---|
| **LangChain** | 131.7K | Full LLM framework. Legacy memory types (ConversationBufferMemory, etc.) deprecated in v0.3.1 in favor of LangGraph checkpointing | [GitHub](https://github.com/langchain-ai/langchain) |
| **Mem0** | 51.5K | Universal memory layer. Hybrid graph+vector+key-value store. $24M funding | [GitHub](https://github.com/mem0ai/mem0) |
| **claude-mem** | 43.7K | Memory extension for Claude AI | [GitHub](https://github.com/thedotmack/claude-mem) |
| **Microsoft GraphRAG** | 31.9K | Entity-centric knowledge graphs with community detection. Local/Global/DRIFT search | [GitHub](https://github.com/microsoft/graphrag) |
| **LightRAG** | 31.2K | Simple, fast graph+vector RAG. Five retrieval modes. EMNLP 2025 | [GitHub](https://github.com/HKUDS/LightRAG) |
| **Graphiti** (Zep) | 24.4K | Real-time temporal knowledge graphs. P95 latency 300ms. MCP server | [GitHub](https://github.com/getzep/graphiti) |
| **Letta** (MemGPT) | 21.8K | Stateful agent platform. Self-editing memory. REST API + SDKs | [GitHub](https://github.com/letta-ai/letta) |
| **Generative Agents** | 21K | Stanford/Google memory stream + reflection architecture | [GitHub](https://github.com/joonspk-research/generative_agents) |
| **SuperMemory** | 20.6K | Memory API + second brain. Browser extension + MCP. Multi-source sync | [GitHub](https://github.com/supermemoryai/supermemory) |
| **Cognee** | 14.8K | Knowledge engine for agent memory in 6 lines of code | [GitHub](https://github.com/topoteretes/cognee) |

### 3.2 Mid-Range Projects (1K-10K stars)

| Project | Stars | Description | URL |
|---|---|---|---|
| **MemOS** | 8K | AI memory OS with plaintext/parametric/activation memory types | [GitHub](https://github.com/MemTensor/MemOS) |
| **Voyager** | 6.8K | Skill library as procedural memory in Minecraft | [GitHub](https://github.com/MineDojo/Voyager) |
| **Hindsight** | 6.7K | Biomimetic memory (World/Experiences/Mental Models). SOTA on LongMemEval | [GitHub](https://github.com/vectorize-io/hindsight) |
| **OpenMemory** | 3.8K | Local persistent memory. Cross-agent. Migration from Mem0/Zep/SuperMemory | [GitHub](https://github.com/CaviraOSS/OpenMemory) |
| **EverMemOS** | 3.5K | Engram-inspired self-organizing memory OS | [GitHub](https://github.com/EverMind-AI/EverMemOS) |
| **HippoRAG** | 3.3K | Hippocampal-inspired RAG with knowledge graphs | [GitHub](https://github.com/OSU-NLP-Group/HippoRAG) |
| **Reflexion** | 3.1K | Verbal reinforcement learning with episodic memory | [GitHub](https://github.com/noahshinn/reflexion) |
| **RAPTOR** | 1.6K | Tree-organized hierarchical retrieval | [GitHub](https://github.com/parthsarthi03/raptor) |
| **LangMem** | 1.4K | Memory for LangGraph agents (by LangChain team) | [GitHub](https://github.com/langchain-ai/langmem) |

### 3.3 Emerging Projects (<1K stars)

| Project | Stars | Description | URL |
|---|---|---|---|
| **A-MEM** | 941 | Zettelkasten-inspired self-organizing memory (NeurIPS 2025) | [GitHub](https://github.com/agiresearch/A-mem) |
| **General Agentic Memory** | 836 | Deep-research powered memory system | [GitHub](https://github.com/VectorSpaceLab/general-agentic-memory) |
| **Awesome-AI-Memory** | 641 | Curated knowledge base on AI memory | [GitHub](https://github.com/IAAR-Shanghai/Awesome-AI-Memory) |
| **Agentic Memory** | 520 | Cognitive architecture concepts for LLM systems | [GitHub](https://github.com/ALucek/agentic-memory) |
| **Agent Memory Paper List** | 1.7K | Companion list to "Memory in the Age of AI Agents" survey | [GitHub](https://github.com/Shichun-Liu/Agent-Memory-Paper-List) |
| **Memorix** | 340 | Cross-agent memory via MCP (Cursor, Claude Code, Codex, etc.) | [GitHub](https://github.com/AVIDS2/memorix) |
| **CASS Memory** | 304 | Procedural memory for coding agents | [GitHub](https://github.com/Dicklesworthstone/cass_memory_system) |
| **Mnemis** | 53 | Microsoft's dual-route hierarchical memory | [GitHub](https://github.com/microsoft/Mnemis) |

---

## 4. Commercial Products

| Product | Vendor | Approach | Key Feature |
|---|---|---|---|
| **ChatGPT Memory** | OpenAI | Auto-saves + user-directed memories. Free users get short-term; Plus/Pro get long-term | [Docs](https://openai.com/index/memory-and-new-controls-for-chatgpt/) |
| **Claude Memory** | Anthropic | File-based CLAUDE.md + MCP knowledge graph server. Transparent, editable | [Docs](https://docs.anthropic.com/en/docs/claude-code/memory) |
| **Gemini Personal Context** | Google | Auto-extracts preferences from conversations. Roadmap: cross-app recall, adaptive compression | [Blog](https://www.datastudios.org/post/google-gemini-context-window-token-limits-and-memory-in-2025) |
| **Zep Platform** | Zep | Temporal knowledge graphs via Graphiti engine. Commercial managed service | [Site](https://www.getzep.com/) |
| **Mem0 Platform** | Mem0 | Managed hybrid graph+vector+KV store. $24M funding. Y Combinator | [Site](https://mem0.ai/) |
| **Letta Cloud** | Letta | Managed stateful agent infrastructure. Agent Development Environment | [Site](https://www.letta.com) |

---

## 5. Design Patterns

### 5.1 Buffer Pattern
Store full conversation history in context. Simple but scales linearly with conversation length. Token overflow risk. (LangChain's ConversationBufferMemory)

### 5.2 Summary Pattern
Compress conversation history into running summary. Reduces token usage but loses detail. Automatic summaries can drift from original meaning. (LangChain's ConversationSummaryMemory)

### 5.3 Sliding Window / Windowed Buffer
Keep only the last N messages. Fixed cost but loses earlier context completely.

### 5.4 Vector Store Pattern
Embed and index memories as vectors. Retrieve by semantic similarity at query time. Foundation of RAG. Scales well but only captures similarity, not temporal or causal relationships.

### 5.5 Knowledge Graph Pattern
Store memories as entities and relationships. Enables multi-hop reasoning and structured queries. Used by GraphRAG, Graphiti, HippoRAG. More expressive but higher complexity.

### 5.6 Self-Editing Memory Pattern (MemGPT/Letta)
Agent actively manages its own memory via tool calls (memory_replace, memory_insert, archival_memory_search). Two-tier: main context (limited) + archival storage (unlimited). OS-inspired virtual context management.

### 5.7 Memory Stream Pattern (Generative Agents)
Natural language records scored by recency, relevance, and importance. Periodic reflection synthesizes higher-level insights. Plans generated from reflections.

### 5.8 Skill Library Pattern (Voyager)
Successful task completions stored as executable code. Indexed by embedding of skill descriptions. Retrieved and composed for new tasks. Prevents catastrophic forgetting.

### 5.9 Multi-Graph Pattern (MAGMA)
Orthogonal graphs (semantic, temporal, causal, entity) with policy-guided traversal. Query-adaptive view selection. Fuses subgraphs into compact context.

### 5.10 Engram/Lifecycle Pattern (EverMemOS)
Memory lifecycle: episodic traces -> semantic consolidation -> reconstructive recollection. Inspired by biological engram formation. Continuous refinement as new memories arrive.

### 5.11 Temporal Knowledge Graph Pattern (Zep/Graphiti)
Facts tracked with temporal provenance. Real-time incremental ingestion. Entity resolution against existing nodes. Captures how facts change over time.

---

## 6. Benchmarks and Evaluation

| Benchmark | Scope | Key Metrics |
|---|---|---|
| **LoCoMo** | Very long-term conversational memory. 50 conversations, ~9K tokens, 35 sessions | QA accuracy, event summarization, multimodal generation |
| **LongMemEval** | Long-term memory evaluation for agents | Factual recall, temporal reasoning, multi-hop |
| **MemBench** | Information extraction, multi-hop reasoning, knowledge updating, preference following, temporal reasoning | Comprehensive memory assessment |
| **MemoryCD** | Cross-domain personalization with long-context user memory | Lifelong cross-domain adaptation |
| **LifeBench** | Long-horizon multi-source memory | Multi-source integration, temporal consistency |
| **MemEval** (Prosus AI) | Benchmark suite for agent/LLM memory systems | [GitHub](https://github.com/ProsusAI/MemEval) |

### Current SOTA Results (LoCoMo)

| System | Score | Method |
|---|---|---|
| Mnemis (Microsoft) | 93.9 | Dual-route hierarchical graphs |
| EverMemOS | 92.3 | Engram-inspired lifecycle |
| MAGMA | Competitive | Multi-graph with policy-guided traversal |

---

## 7. Tutorials and Learning Resources

| Resource | Format | URL |
|---|---|---|
| **LLMs as Operating Systems: Agent Memory** (DeepLearning.AI/Letta) | Coursera guided project, <2 hours | [Course](https://learn.deeplearning.ai/courses/llms-as-operating-systems-agent-memory/information) |
| **Conversational Memory in LangChain** (Aurelio AI) | Tutorial article | [Link](https://www.aurelio.ai/learn/langchain-conversational-memory) |
| **Conversational Memory for LLMs** (Pinecone) | Tutorial series | [Link](https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/) |
| **Design Patterns for Long-Term Memory** (Serokell) | Blog post | [Link](https://serokell.io/blog/design-patterns-for-long-term-memory-in-llm-powered-architectures) |
| **Deep Dive into Memory for LLMs Architectures** (Substack) | Long-form analysis | [Link](https://machinelearningatscale.substack.com/p/deep-dive-into-memory-for-llms-architectures) |
| **Mem0 vs Zep vs LangMem vs MemoClaw** (DEV Community) | Comparison article, 2026 | [Link](https://dev.to/anajuliabit/mem0-vs-zep-vs-langmem-vs-memoclaw-ai-agent-memory-comparison-2026-1l1k) |
| **3 Ways to Build LLMs with Long-Term Memory** (SuperMemory) | Blog post | [Link](https://supermemory.ai/blog/3-ways-to-build-llms-with-long-term-memory/) |
| **Agentic LLM Memory Architectures** (APXML) | Online course | [Link](https://apxml.com/courses/agentic-llm-memory-architectures/chapter-3-designing-memory-systems/long-term-memory-vector-stores) |
| **LLM Memory Architectures** (Aussie AI) | Research overview | [Link](https://www.aussieai.com/research/llm-memory) |

---

## 8. Risks and Security Concerns

### 8.1 Memory Poisoning
Malicious instructions injected into an agent's long-term memory via indirect prompt injection. Once planted, instructions persist across sessions and influence the agent every time that poisoned memory is recalled. Research shows this can enable silent data exfiltration ([Palo Alto Unit42](https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/)).

### 8.2 Memory Injection Attacks
MINJA ([arXiv:2503.03704](https://arxiv.org/abs/2503.03704)) demonstrates that attackers can inject malicious records into memory banks by only interacting via queries and output observations -- no direct access to the memory store required.

### 8.3 Experience Poisoning
MemoryGraft ([arXiv:2512.16962](https://arxiv.org/abs/2512.16962)) implants malicious "successful experiences" into long-term memory. Unlike transient prompt injection, these persist and exploit the agent's tendency to imitate past successful patterns.

### 8.4 Training Data Poisoning
As few as 250 malicious documents can create backdoor vulnerabilities in LLMs regardless of model size ([Anthropic research](https://www.anthropic.com/research/small-samples-poison)).

### 8.5 Hallucination Amplification
Persistent memory can amplify hallucinations: a hallucinated fact stored in memory becomes a "trusted" source for future retrievals, creating self-reinforcing false beliefs.

### 8.6 Privacy Leakage
LLMs may unintentionally store and later retrieve private or personally identifiable information. Memory systems that persist conversation history across sessions increase the surface area for privacy violations.

### 8.7 Memory Staleness and Conflict
Long-lived memories may become stale as the world changes. Without temporal tracking (as in Graphiti/Zep), outdated facts persist indefinitely. Conflicting memories from different time periods can produce contradictory outputs.

### 8.8 Uncontrolled Memory Growth
Without pruning or consolidation mechanisms, memory stores grow unboundedly, increasing retrieval latency and reducing precision as irrelevant memories accumulate.

---

## 9. Vector Databases (Infrastructure Layer)

| Database | Type | Notable Feature |
|---|---|---|
| **Pinecone** | Managed SaaS | Purpose-built for high-dimensional search. Enterprise scale |
| **Weaviate** | Open source / managed | Knowledge graph + vector search hybrid |
| **Chroma** | Open source | Easy LLM integration. Lightweight. Good for prototyping |
| **FAISS** (Meta) | Library | GPU-accelerated. Handles billions of vectors. No database features |
| **Qdrant** | Open source / managed | Rust-based. High performance. Filtering capabilities |
| **Milvus** | Open source | Distributed. Zilliz cloud managed option |

---

## 10. Execution Metrics

| Metric | Value |
|---|---|
| **Total wall clock time** | 213 seconds |
| **Total unique URLs** | 72 |
| **WebSearch queries executed** | 20 |
| **GitHub API queries executed** | 8 |
| **Resources by type** | |
| - Academic papers | 26 |
| - Open-source projects | 27 |
| - Commercial products | 6 |
| - Tutorials/guides | 9 |
| - Security research | 4 |
| - Benchmarks | 5 |
| - Awesome lists | 2 |
| **Source split** | |
| - From web search | 69 (~96%) |
| - From training knowledge (recall) | 3 (~4%) |

### Notes on Source Split

Nearly all resources were found via web search or GitHub API rather than training recall. The few "recall" items (MemGPT's core concept, basic RAG taxonomy, cognitive architecture mappings) were used as starting points for searches that then discovered current URLs and verified details. The conceptual framework and design patterns section draws on training knowledge for synthesis and organization, but all specific citations were verified through search.
