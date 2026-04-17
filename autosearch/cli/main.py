# Source: gpt-researcher/cli.py:L28-L216 (adapted)
from typing import Annotated

import typer

from autosearch import __version__
from autosearch.core.models import SearchMode

app = typer.Typer(add_completion=False, no_args_is_help=False)


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
    text: str,
    mode: Annotated[
        SearchMode,
        typer.Option("--mode", case_sensitive=False, help="Execution depth for the query."),
    ] = SearchMode.FAST,
) -> None:
    _ = mode
    typer.echo(f"M1: {text}")
