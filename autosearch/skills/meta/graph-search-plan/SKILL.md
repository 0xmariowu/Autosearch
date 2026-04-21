---
name: autosearch:graph-search-plan
description: Represent a research plan as a directed graph — nodes are sub-questions, edges are "answer-depends-on" dependencies. Independent nodes can be executed in parallel; downstream nodes wait for their predecessors. Borrowed from MindSearch's WebSearchGraph pattern. Replaces list/tree decomposition for plans with non-linear dependencies.
version: 0.1.0
layer: meta
domains: [workflow, planning]
scenarios: [complex-plan, parallel-subtasks, dependency-tracking, graph-research]
trigger_keywords: [graph, dependency, parallel plan, depends on, root node]
model_tier: Best
auth_required: false
cost: free
experience_digest: experience.md
---

# Graph Search Plan — DAG Over Research Sub-Questions

Most research plans are flat (list) or shallow tree (decompose-task). When sub-questions have **dependencies** ("to answer Q3, first need answers from Q1 and Q2"), a DAG captures the structure more accurately and enables parallelism.

## Node

```yaml
node:
  id: str                           # "root", "q1", "q1a", ...
  question: str
  rationale: str
  depends_on: list[str]             # node ids whose answers are required first
  status: "pending" | "running" | "done" | "failed" | "skipped"
  assigned_subtask_id: str | null   # link to a delegate-subtask when executed
  answer_summary: str | null        # populated when status == "done"
  answer_evidence: list[dict] | null
```

## Graph

```yaml
graph:
  nodes: dict[str, Node]
  edges: list[tuple[from_id, to_id]]  # redundant but convenient — derivable from depends_on
  root_id: "root"
  status: "planning" | "executing" | "finalizing" | "complete" | "failed"
  adjacency: dict[str, list[str]]     # node_id → successor ids (for bfs)
```

## Invariants

1. **Acyclic**: runtime AI must validate no cycles when generating the plan. Cycle → reject plan, re-decompose.
2. **Connected**: every node is reachable from `root_id` (directly or transitively via predecessors).
3. **Dependencies exist**: every `depends_on` id appears in `nodes`.

## Execution Policy

At each tick:

```
ready_nodes = [n for n in graph.nodes.values()
               if n.status == "pending"
               and all(graph.nodes[d].status == "done" for d in n.depends_on)]

# Limit parallelism
take = ready_nodes[:max_parallel_nodes]  # e.g. 4
for node in take:
    subtask_id = delegate_subtask(node.question, ...)
    node.status = "running"
    node.assigned_subtask_id = subtask_id
```

On subtask completion, set `node.status = "done"` and store `answer_summary` + `answer_evidence`. Re-run ready-node detection; if new nodes become ready, dispatch them.

## Graph Generation (Planner)

Initial plan (Best-tier LLM):

- Input: original query + clarify result + rubrics.
- Output: graph with root + 3-8 sub-questions.

Re-planning (trigger: a node's answer reveals a new dependency):

- Insert new child node under the revealing node.
- Re-validate acyclicity.
- Do NOT change the graph of any `done` node's descendants — stability matters for reproducibility.

## Visualization (runtime side-effect)

Runtime AI MAY render the graph for user visibility:

```
root: "how does X compare to Y for production RAG?"
├── q1: "what is X's indexing strategy?" [done]
├── q2: "what is Y's indexing strategy?" [done]
├── q3: "what are X and Y's benchmark results?" [running]
└── q4: "what are real production users saying?" [depends_on: q1, q2] [pending]
```

Not required for correctness; only for UX.

## When to Use

- Task has genuine dependencies (later questions can only be answered after earlier ones).
- Parallelism is useful (3+ independent subtasks).
- User benefits from seeing the plan structure.

## When NOT to Use

- Simple single-level decomposition — use `decompose-task` (list) or `perspective-questioning` (personas).
- Linear pipeline where every question depends on the previous — graph is overkill; just use `reflective-search-loop`.

## Cost

Best-tier LLM for planning + re-planning. Execution cost is the sum of `delegate-subtask` costs across all nodes.

## Interactions

- Feeds into → `delegate-subtask` (one per graph node).
- Feeds into → `citation-index` (merge citations from all node answers).
- Feeds into → `synthesize-knowledge` (final assembly from graph result).
- Complements → `reflective-search-loop` (which is linear; graph is DAG).
