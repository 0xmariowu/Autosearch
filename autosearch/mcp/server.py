# Self-written, plan v2.3 § 13.5 MCP Server (~1 day per plan)
from collections.abc import Callable
from typing import Literal

from mcp.server.fastmcp import FastMCP

from autosearch.channels.ddgs import DDGSChannel
from autosearch.channels.demo import DemoChannel
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.llm.client import LLMClient


def _default_pipeline_factory() -> Pipeline:
    return Pipeline(llm=LLMClient(), channels=[DemoChannel(), DDGSChannel()])


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
    async def research(query: str, mode: Literal["fast", "deep"] = "fast") -> str:
        """Run an AutoSearch research query and return the report text."""
        try:
            result = await factory().run(query, mode_hint=SearchMode(mode))
        except Exception as exc:
            return f"[error] {exc}"

        if result.status == "needs_clarification":
            question = result.clarification.question or "More detail is required."
            return f"[clarification needed] {question}"

        return result.markdown or ""

    @server.tool()
    def health() -> str:
        """Return a cheap liveness indicator for MCP clients."""
        return "ok"

    return server
