"""Plan the next research round using gap analysis and query generation."""

name = "plan_research"
description = "Build a research plan with prioritized queries, branch decisions, and planning ops based on the current goal case, bundle state, and judge result."
when = "When the loop needs to decide what to search next. Takes the current research context and returns a structured plan with queries and execution parameters."
input_type = "plan"
output_type = "plan"


def run(research_context, **context):
    from research import build_research_plan

    if isinstance(research_context, str):
        research_context = {"query": research_context}
    ctx = dict(research_context or {})
    ctx.update(context)
    return build_research_plan(
        searcher=ctx.get("searcher"),
        bundle_state=ctx.get("bundle_state") or {},
        judge_result=ctx.get("judge_result") or {},
        tried_queries=set(ctx.get("tried_queries") or []),
        available_providers=list(ctx.get("available_providers") or []),
        active_program=ctx.get("active_program") or ctx.get("program") or {},
        round_history=list(ctx.get("round_history") or []),
        plan_count=int(ctx.get("plan_count", 1) or 1),
        max_queries=int(ctx.get("max_queries", 6) or 6),
        local_evidence_records=ctx.get("local_evidence_records"),
        gap_queue=ctx.get("gap_queue"),
        diary_summary=ctx.get("diary_summary"),
        action_policy=ctx.get("action_policy"),
    )


def test():
    from research import build_research_plan  # noqa: F401
    return "ok"
