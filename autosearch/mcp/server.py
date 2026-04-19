# Self-written, plan v2.3 § 13.5 MCP Server (~1 day per plan)
from collections.abc import Callable
from typing import Literal

from mcp.server.fastmcp import FastMCP

from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.pipeline import Pipeline
from autosearch.core.search_scope import SearchScope, depth_to_mode
from autosearch.llm.client import LLMClient


class ResearchResponse(str):
    def __new__(
        cls,
        content: str,
        *,
        channel_empty_calls: dict[str, int],
        routing_trace: dict[str, object],
        delivery_status: str,
        scope: SearchScope,
    ) -> "ResearchResponse":
        instance = str.__new__(cls, content)
        instance.channel_empty_calls = dict(channel_empty_calls)
        instance.routing_trace = dict(routing_trace)
        instance.delivery_status = delivery_status
        instance.scope = scope.model_dump()
        return instance


def _default_pipeline_factory() -> Pipeline:
    return Pipeline(llm=LLMClient(), channels=_build_channels())


def create_server(pipeline_factory: Callable[[], Pipeline] | None = None) -> FastMCP:
    factory = pipeline_factory or _default_pipeline_factory
    server = FastMCP(
        name="autosearch",
        instructions=(
            "Deep research tool that runs the AutoSearch pipeline and returns "
            "markdown reports or clarification prompts."
        ),
    )

    @server.tool()
    async def research(
        query: str,
        mode: Literal["fast", "deep"] = "fast",
        languages: Literal["all", "en_only", "zh_only", "mixed"] | None = None,
        depth: Literal["fast", "deep", "comprehensive"] | None = None,
        output_format: Literal["md", "html"] | None = None,
    ) -> str:
        """Run an AutoSearch research query and return the report text."""
        scope = SearchScope(
            channel_scope=languages or "all",
            depth=depth or mode,
            output_format=output_format or "md",
        )
        mode_hint = depth_to_mode(scope.depth)
        assert mode_hint is not None

        try:
            result = await factory().run(query, mode_hint=mode_hint, scope=scope)
        except Exception as exc:
            return ResearchResponse(
                f"[error] {exc}",
                channel_empty_calls={},
                routing_trace={},
                delivery_status="error",
                scope=scope,
            )

        if result.delivery_status == "needs_clarification":
            question = result.clarification.question or "More detail is required."
            return ResearchResponse(
                f"[clarification needed] {question}",
                channel_empty_calls=result.channel_empty_calls,
                routing_trace=result.routing_trace,
                delivery_status=result.delivery_status,
                scope=scope,
            )

        banner = _scope_banner(scope)
        markdown_text = result.markdown or ""
        if banner is not None:
            markdown_text = f"{banner}\n\n{markdown_text}" if markdown_text else banner

        return ResearchResponse(
            _render_output(
                markdown_text=markdown_text,
                title=query,
                output_format=scope.output_format,
            ),
            channel_empty_calls=result.channel_empty_calls,
            routing_trace=result.routing_trace,
            delivery_status=result.delivery_status,
            scope=scope,
        )

    @server.tool()
    def health() -> str:
        """Return a cheap liveness indicator for MCP clients."""
        return "ok"

    return server


def _scope_banner(scope: SearchScope) -> str | None:
    default_scope = SearchScope()
    parts: list[str] = []
    if scope.channel_scope != default_scope.channel_scope:
        parts.append(f"languages={scope.channel_scope}")
    if scope.depth != default_scope.depth:
        parts.append(f"depth={scope.depth}")
    if scope.output_format != default_scope.output_format:
        parts.append(f"format={scope.output_format}")
    if not parts:
        return None
    return "[scope] " + " ".join(parts)


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
            raise RuntimeError("markdown package is required for HTML output") from exc
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
