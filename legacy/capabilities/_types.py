"""Capability contract — every .py file in capabilities/ follows this convention.

Module-level variables (required):
    name: str           — unique identifier (e.g. "search_web")
    description: str    — what this capability does (1-2 sentences, for AI consumption)
    when: str           — when to use this capability (1 sentence, for AI consumption)
    input_type: str     — one of: query, queries, hits, urls, documents, evidence, scores, learnings, plan, config, any
    output_type: str    — one of: query, queries, hits, urls, documents, evidence, scores, learnings, plan, report, any

Functions (required):
    run(input, **context) -> output
        Execute the capability. input matches input_type, output matches output_type.
        context may contain: task_spec, budget, learnings, query_family, limit, mode

Functions (optional):
    test() -> str
        Self-test with minimal fixtures. Returns "ok" on success.
    health_check() -> dict
        Check if external dependencies are available. Returns {"status": "ok"|"off", "message": str}
"""
