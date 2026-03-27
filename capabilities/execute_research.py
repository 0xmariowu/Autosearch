"""Execute a research plan — run queries, collect evidence, build findings."""

name = "execute_research"
description = "Execute a research plan by running its queries against search backends, collecting local evidence, and returning consolidated findings."
when = "When a research plan has been built and needs to be executed to produce evidence hits."
input_type = "plan"
output_type = "hits"


def run(plan, **context):
    from research import execute_research_plan

    return execute_research_plan(
        plan,
        default_platforms=list(context.get("default_platforms") or []),
        provider_mix=context.get("provider_mix"),
        backend_roles=context.get("backend_roles"),
        sampling_policy=context.get("sampling_policy"),
        tried_queries=context.get("tried_queries"),
        query_key_fn=context.get("query_key_fn"),
        local_evidence_records=context.get("local_evidence_records"),
    )


def test():
    from research import execute_research_plan  # noqa: F401

    return "ok"
