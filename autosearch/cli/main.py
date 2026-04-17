# Source: gpt-researcher/cli.py:L28-L216 (adapted)
import asyncio
import json
import sys
from typing import Annotated

import click
import typer
import uvicorn

from autosearch import __version__
from autosearch.channels.demo import DemoChannel
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.llm.client import LLMClient


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
    stream: Annotated[
        bool,
        typer.Option(
            "--stream/--no-stream",
            help="Emit newline-delimited progress events to stderr while the query runs.",
        ),
    ] = True,
) -> None:
    stream_callback = _stderr_event_writer if stream and not json_output else None
    try:
        result = asyncio.run(
            Pipeline(
                llm=LLMClient(),
                channels=[DemoChannel()],
                top_k_evidence=top_k,
                on_event=stream_callback,
            ).run(query, mode_hint=mode)
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if result.status == "needs_clarification":
        typer.echo(result.clarification.question or "More detail is required.", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "status": result.status,
                    "markdown": result.markdown,
                    "iterations": result.iterations,
                    "quality_grade": (
                        result.quality.grade.value if result.quality is not None else None
                    ),
                }
            )
        )
        return

    typer.echo(result.markdown or "")


@app.command()
def mcp() -> None:
    from autosearch.mcp.cli import main as mcp_main

    mcp_main()


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", help="Host interface for the FastAPI server."),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="TCP port for the FastAPI server."),
    ] = 8080,
) -> None:
    uvicorn.run("autosearch.server.main:app", host=host, port=port)


def _stderr_event_writer(event: dict[str, object]) -> None:
    sys.stderr.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stderr.flush()
