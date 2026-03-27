"""Source health check — probe all configured search providers."""

name = "check_health"
description = "Run health checks against configured search sources and return a full capability report with per-source status, availability, and tier classification."
when = "When you need to know which search providers are currently operational before starting a research round."
input_type = "config"
output_type = "report"


def run(provider_names=None, **context):
    from source_capability import refresh_source_capability

    selected = list(provider_names or []) if provider_names else None
    return refresh_source_capability(selected_names=selected)


def test():
    from source_capability import refresh_source_capability  # noqa: F401

    return "ok"
