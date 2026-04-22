# Source: gpt-researcher/cli.py:L28-L216 (adapted)
import json
import sys
from typing import Annotated

import click
import httpx
import typer
import uvicorn
from pydantic import ValidationError

from autosearch import __version__
from autosearch.core.environment_probe import probe_environment
from autosearch.core.models import SearchMode
from autosearch.core.models import PipelineResult
from autosearch.core.scope_clarifier import ScopeClarifier
from autosearch.core.search_scope import (
    ChannelScope,
    Depth,
    OutputFormat,
    ScopeQuestion,
    SearchScope,
)
from autosearch.init.channel_status import (
    TIER_LABELS,
    TIER_ORDER,
    ChannelStatus,
    compile_channel_statuses,
    default_channels_root,
)
from autosearch.init_runner import InitError, InitRunner
from autosearch.llm.client import AllProvidersFailedError

_NO_PROVIDER_MESSAGE = (
    "No LLM provider available; set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
    "GOOGLE_API_KEY, or install the `claude` CLI."
)
_AUTH_FAILURE_MESSAGE = "LLM authentication failed"


class _DefaultQueryGroup(typer.core.TyperGroup):
    default_command = "query"

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and not args[0].startswith("-") and args[0] not in self.commands:
            command = self.get_command(ctx, self.default_command)
            return self.default_command, command, args
        return super().resolve_command(ctx, args)


app = typer.Typer(add_completion=False, no_args_is_help=False, cls=_DefaultQueryGroup)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(code=0)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the AutoSearch version and exit.",
            is_eager=True,
        ),
    ] = None,
) -> None:
    if ctx.invoked_subcommand is None and not version:
        raise typer.Exit(code=0)


@app.command()
def query(
    query: Annotated[str, typer.Argument(help="The research question to run through AutoSearch.")],
    mode: Annotated[
        SearchMode | None,
        typer.Option("--mode", case_sensitive=False, help="Execution depth for the query."),
    ] = None,
    top_k: Annotated[
        int,
        typer.Option("--top-k", min=1, help="Maximum number of evidences to keep after reranking."),
    ] = 20,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit a machine-readable JSON response envelope."),
    ] = False,
    channel_scope: Annotated[
        ChannelScope | None,
        typer.Option(
            "--channel-scope",
            "--languages",
            help='Channel scope: "all" (default), "en_only", "zh_only", or "mixed".',
            case_sensitive=False,
        ),
    ] = None,
    depth: Annotated[
        Depth | None,
        typer.Option(
            "--depth",
            help='Search depth: "fast" (default), "deep", or "comprehensive".',
            case_sensitive=False,
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option(
            "--output-format",
            "--format",
            help='Output format: "md" (default) or "html".',
            case_sensitive=False,
        ),
    ] = None,
    domain_followup: Annotated[
        list[str] | None,
        typer.Option(
            "--domain-followup",
            help="Repeatable; each value is one follow-up angle to prioritize.",
        ),
    ] = None,
    interactive: Annotated[
        bool | None,
        typer.Option(
            "--interactive/--no-interactive",
            help=(
                "Force (or suppress) the interactive prompt when flags are missing. "
                "Defaults to auto-detect based on TTY."
            ),
        ),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option(
            "--stream/--no-stream",
            help="Emit newline-delimited progress events to stderr while the query runs.",
        ),
    ] = True,
) -> None:
    if mode is not None and depth is not None:
        typer.echo("--mode ignored because --depth was also provided", err=True)

    normalized_query = query.strip()
    if not normalized_query:
        _exit_query_failure("Query must not be empty.", exit_code=2, json_output=json_output)

    # v2: legacy pipeline removed. Direct CLI query is deprecated.
    _exit_query_failure(
        "autosearch query is deprecated in v2.\n"
        "Use the MCP tools instead: list_skills / run_clarify / run_channel.\n"
        "See docs/migration/legacy-research-to-tool-supplier.md",
        exit_code=1,
        json_output=json_output,
    )

    # Dead code below — kept as reference until full pipeline removal is complete.
    # The deprecation exit above prevents any of this from running.
    _ = normalized_query  # suppress unused variable warning


@app.command()
def mcp() -> None:
    from autosearch.mcp.cli import main as mcp_main

    mcp_main()


@app.command()
def init(
    check_channels: Annotated[
        bool,
        typer.Option(
            "--check-channels",
            help="Print a tier-grouped status table of all available channels.",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Replace the generated config instead of merging detected providers into it.",
        ),
    ] = False,
) -> None:
    if check_channels:
        _print_channel_check()
        return

    runner = InitRunner()
    config_exists = runner.config_path().exists()
    action = "merged" if config_exists and not overwrite else "created"
    if config_exists and overwrite:
        action = "overwritten"

    try:
        result = runner.run(overwrite=overwrite)
    except InitError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    version = sys.version_info
    typer.echo(f"Python 3.12+ check: OK (running {version.major}.{version.minor}.{version.micro})")
    typer.echo("Provider detection:")
    for provider, detected in result.providers.items():
        status = "✅" if detected else "❌"
        typer.echo(f"{status} {provider}")
    typer.echo(f"Config: {action} {result.config_path}")

    if result.warnings:
        typer.echo("Warnings:")
        for warning in result.warnings:
            typer.echo(f"- {warning}")

    typer.echo("Next steps:")
    for step in result.next_steps:
        typer.echo(f"- {step}")


def _print_channel_check() -> None:
    channels_root = default_channels_root()
    if not channels_root.is_dir():
        typer.echo(f"Channel skills root missing: {channels_root}", err=True)
        raise typer.Exit(code=1)

    rows = compile_channel_statuses(channels_root, probe_environment())
    grouped: dict[str, list[ChannelStatus]] = {tier: [] for tier in TIER_ORDER}
    totals = {"available": 0, "blocked": 0, "scaffold-only": 0}
    for row in rows:
        grouped[row.tier].append(row)
        totals[row.status] += 1

    for tier in TIER_ORDER:
        typer.echo(f"{TIER_LABELS[tier]} ({len(grouped[tier])})")
        for row in grouped[tier]:
            symbol = _channel_status_symbol(row)
            typer.echo(f"  {symbol} {row.channel:<18}", nl=False)
            typer.secho(f"{row.status:<14}", fg=_channel_status_color(row.status), nl=False)
            if row.unmet_requires:
                typer.echo(f" {', '.join(row.unmet_requires)}")
            else:
                typer.echo()
        typer.echo()

    typer.echo(
        "Total: "
        f"{len(rows)} channels | "
        f"{totals['available']} available | "
        f"{totals['blocked']} blocked | "
        f"{totals['scaffold-only']} scaffold-only"
    )


def _channel_status_color(status: str) -> str | None:
    if status == "available":
        return typer.colors.GREEN
    if status == "blocked":
        return typer.colors.RED
    if status == "scaffold-only":
        return typer.colors.YELLOW
    return None


def _channel_status_symbol(row: ChannelStatus) -> str:
    if row.status == "available":
        return "✓"
    if row.status == "blocked":
        return "✗"
    return "·"


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", help="Host interface for the FastAPI server."),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", min=0, max=65535, help="TCP port for the FastAPI server."),
    ] = 8080,
) -> None:
    uvicorn.run("autosearch.server.main:app", host=host, port=port)


def _stderr_event_writer(event: dict[str, object]) -> None:
    sys.stderr.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def _friendly_query_error_message(error: Exception) -> str:
    if _is_authentication_error(error):
        return _AUTH_FAILURE_MESSAGE
    if _is_no_provider_configured_error(error):
        return _NO_PROVIDER_MESSAGE
    if isinstance(error, AllProvidersFailedError):
        return "No LLM provider available; all configured providers failed."
    return str(error)


def _is_no_provider_configured_error(error: Exception) -> bool:
    return isinstance(error, RuntimeError) and "No LLM provider configured" in str(error)


def _is_authentication_error(error: Exception) -> bool:
    if isinstance(error, AllProvidersFailedError):
        provider_errors = list(error.provider_errors.values())
        return bool(provider_errors) and all(
            _is_authentication_error(provider_error) for provider_error in provider_errors
        )
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {401, 403}

    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "authentication failed",
            "invalid api key",
            "api key is invalid",
            "unauthorized",
            "forbidden",
            "invalid x-api-key",
        )
    )


def _exit_query_failure(message: str, *, exit_code: int, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "delivery_status": "error",
                    "error": message,
                    "exit_code": exit_code,
                }
            )
        )
    else:
        typer.echo(message, err=True)
    raise typer.Exit(code=exit_code)


def _resolve_scope(
    *,
    provided: dict[str, object],
    interactive: bool | None,
    json_output: bool,
) -> SearchScope:
    try:
        clarifier = ScopeClarifier()
        if _should_prompt_for_scope(interactive=interactive, json_output=json_output):
            answers = _prompt_for_scope_answers(clarifier.questions_for(provided))
            return clarifier.apply_answers(SearchScope(), {**provided, **answers})
        return clarifier.apply_answers(SearchScope(), provided)
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _should_prompt_for_scope(*, interactive: bool | None, json_output: bool) -> bool:
    if interactive is True:
        return True
    if interactive is False:
        return False
    return sys.stdin.isatty() and sys.stdout.isatty() and not json_output


def _prompt_for_scope_answers(questions: list[ScopeQuestion]) -> dict[str, object]:
    answers: dict[str, object] = {}
    for question in questions:
        answers[question.field] = _prompt_for_scope_question(question)
    return answers


def _prompt_for_scope_question(question: ScopeQuestion) -> str:
    if not question.options:
        return typer.prompt(question.prompt, default="", show_default=False).strip()

    choices_text = ", ".join(
        f"{index}. {option}" for index, option in enumerate(question.options, start=1)
    )
    prompt_text = f"{question.prompt} [{choices_text}]"
    for _ in range(3):
        answer = typer.prompt(prompt_text).strip()
        resolved = _resolve_prompt_answer(answer, question.options)
        if resolved is not None:
            return resolved
        typer.echo(
            f"Invalid choice. Enter 1-{len(question.options)} or one of: "
            f"{', '.join(question.options)}",
            err=True,
        )
    raise typer.Exit(code=2)


def _resolve_prompt_answer(answer: str, options: list[str]) -> str | None:
    normalized = answer.strip().lower()
    if not normalized:
        return None
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(options):
            return options[index]
        return None
    for option in options:
        if normalized == option.lower():
            return option
    return None


def _render_output(markdown_text: str, title: str, output_format: str) -> str:
    if output_format == "html":
        return _render_html(markdown_text=markdown_text, title=title)
    return markdown_text


def _render_html(markdown_text: str, title: str) -> str:
    import html as html_lib

    try:
        import markdown as md
    except ImportError as exc:
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            raise RuntimeError("markdown package is required for --output-format html") from exc
        body = MarkdownIt("js-default").render(markdown_text or "")
    else:
        body = md.markdown(markdown_text or "", extensions=["tables", "fenced_code"])
    safe_title = html_lib.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        '<head><meta charset="utf-8"><title>{title}</title></head>\n'
        "<body><article>\n{body}\n</article></body>\n"
        "</html>\n"
    ).format(title=safe_title, body=body)


def _json_sources(result: PipelineResult) -> list[dict[str, str]]:
    return [
        {
            "channel": evidence.source_channel,
            "url": evidence.url,
            "title": evidence.title,
        }
        for evidence in result.evidences
    ]


if __name__ == "__main__":
    app()
