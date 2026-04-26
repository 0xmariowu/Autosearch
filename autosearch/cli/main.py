# Source: gpt-researcher/cli.py:L28-L216 (adapted)
import json
import sys
from typing import Annotated, Literal

import httpx
import typer
from pydantic import ValidationError

from autosearch import __version__
from autosearch.cli.mcp_config_writers import MCPConfigWriteError
from autosearch.core.environment_probe import probe_environment
from autosearch.core.models import SearchMode
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

# Tools that must be registered on the MCP server for a v2 install to be usable.
_REQUIRED_MCP_TOOLS = (
    "list_skills",
    "run_clarify",
    "run_channel",
    "list_channels",
    "doctor",
    "select_channels_tool",
    "delegate_subtask",
    "citation_create",
    "citation_add",
    "citation_export",
)


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
    # Route structlog to stderr so `--json` output stays parseable and CLI
    # users don't see info logs interleaved with the brief on stdout. (MCP
    # path does the same in autosearch/mcp/cli.py.)
    import structlog

    structlog.configure(logger_factory=structlog.WriteLoggerFactory(file=sys.stderr))

    # Push ~/.config/ai-secrets.env keys into process env so subcommands and
    # any provider/channel that does `os.getenv("FOO_API_KEY")` actually sees
    # what the user configured via `autosearch configure`.
    from autosearch.core.secrets_store import inject_into_env

    inject_into_env()

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

    # v2 P1-7: thin orchestration over MCP tools. Autosearch does NOT synthesize a
    # report — output is structured evidence + citations the user pastes into a
    # runtime AI (Claude / ChatGPT / Cursor) for synthesis.
    import asyncio

    from autosearch.cli.query_pipeline import render_json, render_markdown, run_query

    # `mode` is the clarifier hint (fast/deep/comprehensive). `depth` is the
    # legacy CLI alias; map it to a SearchMode if it matches a known value.
    effective_mode: SearchMode | None = mode
    if effective_mode is None and depth is not None:
        depth_value = depth.value if hasattr(depth, "value") else str(depth)
        try:
            effective_mode = SearchMode(depth_value)
        except ValueError:
            effective_mode = None

    try:
        result = asyncio.run(
            run_query(
                normalized_query, mode_hint=effective_mode, top_k_channels=3, per_channel_k=top_k
            )
        )
    except Exception as exc:  # noqa: BLE001 — boundary; surface a structured error
        _exit_query_failure(
            f"query pipeline failed: {type(exc).__name__}: {exc}",
            exit_code=1,
            json_output=json_output,
        )

    if json_output:
        typer.echo(render_json(result))
    else:
        typer.echo(render_markdown(result))

    raise typer.Exit(code=0)


@app.command()
def mcp() -> None:
    from autosearch.mcp.cli import main as mcp_main

    mcp_main()


@app.command()
def init(
    client: Annotated[
        str | None,
        typer.Option(
            "--client",
            help="Limit MCP client config writes to one client (claude/cursor/zed).",
        ),
    ] = None,
    scope: Annotated[
        Literal["project"] | None,
        typer.Option(
            "--scope",
            help="MCP config scope. Currently only `project` is used for Claude Code fallback.",
        ),
    ] = None,
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
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print MCP client config writes that would happen without touching files.",
        ),
    ] = False,
) -> None:
    if check_channels:
        _print_channel_check()
        return

    if dry_run:
        typer.echo("Dry-run: showing MCP client writes only (no files will be modified).\n")
        try:
            mcp_status = _auto_configure_mcp(dry_run=True, client=client, scope=scope)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except MCPConfigWriteError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        for line in mcp_status.split("; "):
            typer.echo(f"  {line}")
        return

    # ── Banner ────────────────────────────────────────────────────────────────
    typer.echo(
        "\n"
        " █████╗ ██╗   ██╗████████╗ ██████╗ ███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗\n"
        "██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║\n"
        "███████║██║   ██║   ██║   ██║   ██║███████╗█████╗  ███████║██████╔╝██║     ███████║\n"
        "██╔══██║██║   ██║   ██║   ██║   ██║╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║\n"
        "██║  ██║╚██████╔╝   ██║   ╚██████╔╝███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║\n"
        "╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝\n"
    )
    typer.echo(
        f"Welcome to AutoSearch v{__version__} — Open-source deep research for coding agents"
    )
    typer.echo("-" * 60)
    typer.echo("This tool will:")
    typer.echo("  - Detect your LLM providers (Anthropic, OpenAI, Gemini, claude CLI)")
    typer.echo("  - Create ~/.autosearch/config.yaml")
    typer.echo("  - Auto-configure the MCP server for Claude Code / Cursor")
    typer.echo("  - Show which of the 39 search channels are ready to use")
    typer.echo("")
    typer.echo("(Nothing destructive — existing configs are merged, not overwritten)")
    typer.echo("-" * 60)
    typer.echo("Analyzing and configuring local environment...")
    typer.echo("")

    # ── Run init ──────────────────────────────────────────────────────────────
    runner = InitRunner()
    try:
        result = runner.run(overwrite=overwrite)
    except InitError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    # ── Provider status ───────────────────────────────────────────────────────
    version = sys.version_info
    typer.echo("Integration Status:")
    typer.echo(f"  ✅ Python {version.major}.{version.minor}.{version.micro}            [OK]")
    for provider, detected in result.providers.items():
        if detected:
            typer.echo(f"  ✅ {provider:<24} [Detected]")
        else:
            typer.echo(f"  ○  {provider:<24} [Not found]")

    # ── Auto-write MCP config ─────────────────────────────────────────────────
    try:
        mcp_status = _auto_configure_mcp(client=client, scope=scope)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except MCPConfigWriteError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"  ✅ MCP server                   [{mcp_status}]")

    # ── Channel summary ───────────────────────────────────────────────────────
    import os  # noqa: PLC0415

    from autosearch.core.doctor import scan_channels  # noqa: PLC0415

    # Suppress all log output at fd level (structlog bypasses sys.stderr)
    _devnull_fd = os.open(os.devnull, os.O_WRONLY)
    _old_stderr_fd = os.dup(2)
    os.dup2(_devnull_fd, 2)
    os.close(_devnull_fd)
    try:
        channel_results = scan_channels()
    finally:
        os.dup2(_old_stderr_fd, 2)
        os.close(_old_stderr_fd)
    ok_count = sum(1 for r in channel_results if r.status == "ok")
    total = len(channel_results)
    typer.echo(f"  ✅ Search channels              [{ok_count}/{total} ready]")

    # ── Success box ───────────────────────────────────────────────────────────
    typer.echo("")
    typer.echo("+" + "-" * 60 + "+")
    typer.echo("|  You are all set!                                          |")
    typer.echo("|                                                            |")
    typer.echo(f"|  Config: {str(result.config_path):<51}|")
    typer.echo("|                                                            |")
    typer.echo("|  Run:  autosearch doctor  — full channel status            |")
    typer.echo("|  Run:  autosearch login xhs  — unlock Chinese social media |")
    typer.echo("+" + "-" * 60 + "+")
    typer.echo("")


def _auto_configure_mcp(
    dry_run: bool = False,
    *,
    client: str | None = None,
    scope: Literal["project"] | None = None,
) -> str:
    """Write the autosearch MCP entry to every supported client's config file.

    Each client gets its own writer (Claude Code, Cursor, Zed) so the entry
    lands under the correct namespace key — not a flat top-level dict that the
    client cannot load. Skips clients whose config dir doesn't exist (i.e. the
    user hasn't installed them).
    """
    from autosearch.cli.mcp_config_writers import WRITERS, write_for_clients

    if client is not None and client not in WRITERS:
        raise ValueError(f"unknown client {client!r}. Known: {', '.join(sorted(WRITERS))}")
    if client == "claude" and scope is None:
        writer = WRITERS["claude"]
        has_claude_cli = getattr(writer, "has_claude_cli", lambda: False)
        if not has_claude_cli():
            raise MCPConfigWriteError(
                "Claude Code MCP is not configured: `claude` CLI is not on PATH, and "
                "AutoSearch will not write the stale ~/.claude/mcp.json path. Run "
                "`claude mcp add --transport stdio autosearch -- autosearch-mcp` or "
                "`autosearch init --client claude --scope project` to write ./.mcp.json."
            )

    results = write_for_clients(clients=[client] if client else None, dry_run=dry_run, scope=scope)

    parts: list[str] = []
    for r in results:
        if r.status == "skipped":
            continue
        prefix = "(dry-run) " if dry_run else ""
        if r.status == "already-set":
            parts.append(f"{prefix}{r.client}: already set")
        elif r.status == "backup-and-replaced":
            backup_note = f" (backup → {r.backup_path.name})" if r.backup_path else ""
            parts.append(f"{prefix}{r.client}: rewritten{backup_note}")
        else:
            parts.append(f"{prefix}{r.client}: written")

    if not parts:
        return "no MCP clients detected (none of ~/.claude, ~/.cursor, ~/.config/zed exist)"
    return "; ".join(parts)


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
def configure(
    key: Annotated[str, typer.Argument(help="Environment variable name, e.g. OPENAI_API_KEY.")],
    value: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Value to store. If omitted, you will be prompted with hidden "
                "input — preferred to avoid leaking the secret to shell history "
                "and the process list."
            ),
        ),
    ] = None,
    from_stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read value from stdin (for automation pipelines, e.g. `pass | autosearch configure KEY --stdin`).",
        ),
    ] = False,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help="Replace an existing key in place. Without this flag, an existing key is left untouched.",
        ),
    ] = False,
) -> None:
    """Write a key=value pair to ~/.config/ai-secrets.env.

    Default flow: prompts for the value with hidden input so the secret never
    appears on the command line, in shell history, or in `ps`.
    """
    import shlex
    import sys

    if from_stdin:
        value = sys.stdin.read().rstrip("\n")
    elif value is None:
        if not _is_tty():
            typer.echo(
                "error: no value provided and stdin is not a TTY. "
                "Pass the value as an argument or use --stdin.",
                err=True,
            )
            raise typer.Exit(code=2)
        value = typer.prompt(f"Value for {key}", hide_input=True, confirmation_prompt=False)

    if not value:
        typer.echo("error: value must not be empty.", err=True)
        raise typer.Exit(code=2)

    # Bug 3 (fix-plan): write target must follow AUTOSEARCH_SECRETS_FILE so
    # containers / CI / multi-user installs don't end up writing to A while
    # the runtime reads B.
    from autosearch.core.secrets_store import secrets_path as _secrets_path  # noqa: PLC0415

    secrets_path = _secrets_path()
    existing: dict[str, str] = {}
    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                existing[k.strip()] = v

    if key in existing and not replace:
        typer.echo(
            f"{key} already exists in {secrets_path}. "
            f"Pass --replace to overwrite, or edit the file manually."
        )
        raise typer.Exit(code=0)

    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    if key in existing and replace:
        # Rewrite the file in place with the new value, preserve all others.
        existing[key] = shlex.quote(value)
        secrets_path.write_text(
            "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
            encoding="utf-8",
        )
    else:
        with secrets_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{key}={shlex.quote(value)}\n")

    # Restrict file permissions so other users on the box can't read the secrets.
    try:
        secrets_path.chmod(0o600)
    except OSError:
        pass

    typer.echo(f"Written: {key} -> {secrets_path}")


@app.command()
def login(
    platform: Annotated[
        str, typer.Argument(help="Platform to log in (e.g. xhs, twitter, bilibili).")
    ],
    browser: Annotated[
        str,
        typer.Option(
            "--browser", "-b", help="Browser to read cookies from (chrome/firefox/edge/brave)."
        ),
    ] = "chrome",
    from_string: Annotated[
        str | None,
        typer.Option(
            "--from-string",
            help=(
                "DEPRECATED: leaks the cookie into shell history and the "
                "process list. Prefer --stdin (pipe the cookie in) or omit "
                "to read from the browser."
            ),
        ),
    ] = None,
    from_stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read the cookie string from stdin (avoids shell-history leak).",
        ),
    ] = False,
    check_health: Annotated[
        bool,
        typer.Option(
            "--check-health",
            help=(
                "Check cookie health (xhs only) by probing the me endpoint. "
                "Skips cookie import. Exits 0 if healthy, 1 if account flagged."
            ),
        ),
    ] = False,
) -> None:
    """Import cookies from your local browser — no copy-paste needed.

    Four modes:
      1. Default: read cookies straight from the browser session.
      2. --stdin: pipe the cookie string in (no shell-history leak).
      3. --from-string: cookie on the command line (DEPRECATED — leaks).
      4. --check-health: probe a previously imported cookie to see whether
         the account is currently flagged (xhs only — code=300011).

    Examples:
        autosearch login xhs
        autosearch login twitter --browser firefox
        printf 'SESSDATA=xxx; bili_jct=yyy' | autosearch login bilibili --stdin
        autosearch login xhs --check-health

    Supported platforms: xhs, twitter, bilibili, weibo, douyin, zhihu, xueqiu
    """

    # 1:1 from Agent-Reach agent_reach/cookie_extract.py PLATFORM_SPECS
    _PLATFORM_SPECS: dict[str, tuple[tuple[str, ...], str]] = {
        "xhs": ((".xiaohongshu.com",), "XHS_COOKIES"),
        "twitter": ((".x.com", ".twitter.com"), "TWITTER_COOKIES"),
        "bilibili": ((".bilibili.com",), "BILIBILI_COOKIES"),
        "weibo": ((".weibo.com", ".weibo.cn"), "WEIBO_COOKIES"),
        "douyin": ((".douyin.com",), "DOUYIN_COOKIES"),
        "zhihu": ((".zhihu.com",), "ZHIHU_COOKIES"),
        "xueqiu": ((".xueqiu.com", "xueqiu.com"), "XUEQIU_COOKIES"),
    }

    if platform not in _PLATFORM_SPECS:
        typer.echo(
            f"Unsupported platform: {platform}. Supported: {', '.join(_PLATFORM_SPECS)}",
            err=True,
        )
        raise typer.Exit(code=1)

    if check_health:
        if platform != "xhs":
            typer.echo(
                "--check-health is currently only supported for xhs.",
                err=True,
            )
            raise typer.Exit(code=2)
        _run_xhs_health_check()
        return

    domains, env_key = _PLATFORM_SPECS[platform]

    if from_stdin and from_string:
        typer.echo("error: --stdin and --from-string are mutually exclusive.", err=True)
        raise typer.Exit(code=2)

    # Bug 4 (fix-plan): preferred non-leaking input — pipe the cookie in.
    if from_stdin:
        cookie_input = sys.stdin.read().strip()
        if not cookie_input:
            typer.echo("error: --stdin received empty cookie string.", err=True)
            raise typer.Exit(code=2)
        _write_cookie_to_secrets(env_key, cookie_input, platform)
        typer.echo(f"Done. {env_key} written from stdin.")
        return

    # Deprecated path: cookie on the command line.
    if from_string:
        typer.echo(
            "warning: --from-string puts the cookie in your shell history and "
            "process list. Prefer --stdin (pipe it in) for new automation.",
            err=True,
        )
        _write_cookie_to_secrets(env_key, from_string.strip(), platform)
        typer.echo(f"Done. {env_key} written from --from-string.")
        return

    try:
        import rookiepy
    except ImportError:
        typer.echo(
            "Cookie import requires rookiepy. Install it with:\n"
            "  uv pip install rookiepy\n"
            "or: pip install rookiepy",
            err=True,
        )
        raise typer.Exit(code=1)

    browser_lower = browser.lower()
    browser_map = {
        "chrome": rookiepy.chrome,
        "firefox": rookiepy.firefox,
        "edge": rookiepy.edge,
        "brave": rookiepy.brave,
        "opera": rookiepy.opera,
    }
    if browser_lower not in browser_map:
        typer.echo(f"Unsupported browser: {browser}. Use: {', '.join(browser_map)}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Reading {platform} cookies from {browser}...")
    try:
        raw = browser_map[browser_lower](list(domains))
    except Exception as exc:
        typer.echo(f"Could not read cookies: {exc}", err=True)
        raise typer.Exit(code=1)

    if not raw:
        typer.echo(
            f"No {platform} cookies found in {browser}. "
            f"Make sure you're logged in to {platform} in {browser}.\n"
            f"Tip: use Cookie-Editor extension → Export → Header String, then:\n"
            f'  autosearch login {platform} --from-string "<paste>"',
            err=True,
        )
        raise typer.Exit(code=1)

    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in raw)
    _write_cookie_to_secrets(env_key, cookie_str, platform, n_cookies=len(raw))
    typer.echo(f"Done. {platform} searches will now use your {browser} session.")


def _run_xhs_health_check() -> None:
    """Probe XHS me endpoint with the currently-configured cookies.

    Exits 0 if the account is healthy; exits 1 if flagged (code=300011)
    or if no cookies are configured.
    """
    import asyncio
    import os

    cookies = (
        os.environ.get("XHS_COOKIES")
        or os.environ.get("XIAOHONGSHU_COOKIES")
        or os.environ.get("XHS_A1_COOKIE", "")
    )
    if not cookies:
        typer.echo(
            "No XHS_COOKIES found. Run `autosearch login xhs` first to import cookies.",
            err=True,
        )
        raise typer.Exit(code=1)

    headers = {
        "Cookie": cookies,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "application/json, text/plain, */*",
    }

    from autosearch.skills.channels.xiaohongshu.methods.via_signsrv import (
        _check_account_health,
    )

    async def _probe() -> tuple[bool, str | None]:
        async with httpx.AsyncClient(timeout=10) as client:
            return await _check_account_health(client, headers)

    healthy, code = asyncio.run(_probe())

    if healthy:
        typer.echo("OK: XHS cookies appear healthy (account not flagged).")
        return

    if code == "300011":
        typer.echo(
            "FLAGGED: XHS account is restricted (code=300011). "
            "Re-run `autosearch login xhs` with a different account.",
            err=True,
        )
    else:
        typer.echo(
            f"UNKNOWN: probe returned restricted with code={code}",
            err=True,
        )
    raise typer.Exit(code=1)


def _write_cookie_to_secrets(
    env_key: str, cookie_str: str, platform: str, n_cookies: int = 0
) -> None:
    """Write or update a cookie env var in the secrets file.

    Bug 3 (fix-plan): respects AUTOSEARCH_SECRETS_FILE so the runtime reads
    the same file we just wrote. Bug 4: chmods the file 0o600 after write
    so cookies aren't world-readable on shared boxes.
    """
    import shlex

    from autosearch.core.secrets_store import secrets_path as _secrets_path

    secrets_path = _secrets_path()
    secrets_path.parent.mkdir(parents=True, exist_ok=True)

    existing_keys: set[str] = set()
    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_keys.add(stripped.split("=", 1)[0].strip())

    label = f"{n_cookies} cookies" if n_cookies else "cookies"
    if env_key in existing_keys:
        lines = secrets_path.read_text(encoding="utf-8").splitlines()
        new_lines = [
            f"{env_key}={shlex.quote(cookie_str)}"
            if line.strip().startswith(f"{env_key}=")
            else line
            for line in lines
        ]
        secrets_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        typer.echo(f"Updated {env_key} ({label}) → {secrets_path}")
    else:
        with secrets_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{env_key}={shlex.quote(cookie_str)}\n")
        typer.echo(f"Written {env_key} ({label}) → {secrets_path}")

    try:
        secrets_path.chmod(0o600)
    except OSError:
        pass


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


def _is_tty() -> bool:
    return sys.stdin.isatty()


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


@app.command()
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit ChannelStatus list as JSON instead of human report."),
    ] = False,
) -> None:
    """Scan channel availability and print a status report.

    Does not require any LLM key. Exits 0 when the scan completes.
    """
    from dataclasses import asdict

    from autosearch.core.doctor import format_report, scan_channels

    results = scan_channels()

    if json_output:
        typer.echo(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
        return

    typer.echo(format_report(results))


@app.command("mcp-check")
def mcp_check(
    client: Annotated[
        str | None,
        typer.Option(
            "--client",
            help="Also verify a specific MCP client's config file shape "
            "(claude/cursor/zed). Without this flag only the server-side "
            "tool registry is checked.",
        ),
    ] = None,
) -> None:
    """Verify the MCP server registers every tool the v2 install contract requires.

    Creates the server in-process, lists registered tools, and exits non-zero
    when any of the required tools is missing. Performs no network I/O.

    With `--client <name>`, additionally inspect that client's config file and
    confirm the autosearch entry sits under the correct namespace key.
    """
    import asyncio

    from autosearch.mcp.server import create_server

    server = create_server()
    tools = asyncio.run(server.list_tools())
    registered = sorted({t.name for t in tools})

    typer.echo(f"Registered tools ({len(registered)}):")
    for name in registered:
        typer.echo(f"  {name}")

    typer.echo("")
    typer.echo("Required v2 tools:")
    missing: list[str] = []
    for name in _REQUIRED_MCP_TOOLS:
        mark = "✓" if name in registered else "✗"
        typer.echo(f"  {mark} {name}")
        if name not in registered:
            missing.append(name)

    typer.echo("")
    if missing:
        typer.echo(f"FAIL: {len(missing)} required tool(s) missing: {', '.join(missing)}")
        raise typer.Exit(code=1)
    typer.echo(f"OK: all {len(_REQUIRED_MCP_TOOLS)} required tools registered.")

    if client is None:
        return

    from autosearch.cli.mcp_config_writers import WRITERS

    typer.echo("")
    writer = WRITERS.get(client)
    if writer is None:
        typer.echo(
            f"FAIL: unknown client {client!r}. Known: {', '.join(sorted(WRITERS))}",
            err=True,
        )
        raise typer.Exit(code=1)
    ok, message = writer.verify()
    typer.echo(f"Client config check ({client}):")
    if ok:
        typer.echo(f"  ✓ {message}")
        return
    typer.echo(f"  ✗ {message}")
    raise typer.Exit(code=1)


@app.command()
def diagnostics(
    redact_output: Annotated[
        bool,
        typer.Option(
            "--redact",
            help=(
                "Required. Strip secrets / cookies / API key values before "
                "printing. Without this flag the command refuses to run, so a "
                "user copy-paste into a public issue can't accidentally leak "
                "credentials."
            ),
        ),
    ] = False,
) -> None:
    """Print a copy-pasteable diagnostics bundle for support / GitHub issues.

    Includes: autosearch version, Python info, install method, MCP client
    config status, secrets-file presence (key NAMES only, never values),
    runtime experience dir size, MCP tool registry summary, doctor counts.

    Excludes: secret values, raw env dumps, full user queries.
    """
    from autosearch.cli.diagnostics import build_bundle, render_bundle

    if not redact_output:
        typer.echo(
            "error: refusing to run without --redact. The bundle may contain "
            "filesystem paths, environment variable names, or other context "
            "that should be scrubbed before posting publicly. Re-run with "
            "`autosearch diagnostics --redact`.",
            err=True,
        )
        raise typer.Exit(code=2)

    bundle = build_bundle()
    typer.echo(render_bundle(bundle, redact_output=True))


if __name__ == "__main__":
    app()
