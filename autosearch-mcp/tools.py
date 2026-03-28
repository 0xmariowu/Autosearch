"""AutoSearch MCP tool definitions.

Requires: pip install mcp>=1.0
"""

from __future__ import annotations

import json
import traceback
from typing import Any

from mcp.server import Server
import mcp.types as types


def register_tools(server: Server) -> None:
    """Register all AutoSearch MCP tools on the given server."""

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="autosearch_search",
                description=(
                    "Quick search using AutoSearch interface. "
                    "Wraps AutoSearchInterface.run_orchestrated for simple queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text",
                        },
                        "providers": {
                            "type": "string",
                            "description": (
                                "Comma-separated provider list to check health for. "
                                "Leave empty to use all available providers."
                            ),
                            "default": "",
                        },
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="autosearch_orchestrate",
                description=(
                    "Full AI-orchestrated search. The orchestrator reads capability "
                    "descriptions, uses LLM to plan and execute search steps, and "
                    "returns collected evidence with learnings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_spec": {
                            "type": "string",
                            "description": "Natural-language description of the search task",
                        },
                        "max_steps": {
                            "type": "integer",
                            "description": "Maximum orchestrator steps",
                            "default": 15,
                        },
                    },
                    "required": ["task_spec"],
                },
            ),
            types.Tool(
                name="autosearch_doctor",
                description=(
                    "Check provider health. Returns the current source capability "
                    "report showing which search providers are reachable."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "providers": {
                            "type": "string",
                            "description": (
                                "Comma-separated provider names to check. "
                                "Leave empty to check all."
                            ),
                            "default": "",
                        },
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="autosearch_capabilities",
                description=(
                    "List all available AutoSearch capabilities. Returns the "
                    "full manifest of registered capability modules."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            types.Tool(
                name="autosearch_resume",
                description=(
                    "Resume an orchestrated search from a checkpoint. "
                    "Continues a previously started task using its task_id."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task ID from a previous orchestrated run to resume",
                        },
                    },
                    "required": ["task_id"],
                },
            ),
            types.Tool(
                name="autosearch_evolve",
                description=(
                    "Run AVO (Adaptive Variation Optimization) evolution on a search task. "
                    "Evolves search strategies over multiple generations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_spec": {
                            "type": "string",
                            "description": "Natural-language description of the search task to evolve",
                        },
                        "generations": {
                            "type": "integer",
                            "description": "Number of evolution generations",
                            "default": 3,
                        },
                    },
                    "required": ["task_spec"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == "autosearch_search":
                return await _handle_search(arguments)
            elif name == "autosearch_orchestrate":
                return await _handle_orchestrate(arguments)
            elif name == "autosearch_doctor":
                return await _handle_doctor(arguments)
            elif name == "autosearch_capabilities":
                return await _handle_capabilities(arguments)
            elif name == "autosearch_resume":
                return await _handle_resume(arguments)
            elif name == "autosearch_evolve":
                return await _handle_evolve(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as exc:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            ]


# --- Handler implementations ---


async def _handle_search(arguments: dict) -> list[types.TextContent]:
    """Quick search: wraps AutoSearchInterface.doctor for provider check + run_orchestrated."""
    from interface import AutoSearchInterface

    query = arguments["query"]
    providers_raw = arguments.get("providers", "")
    provider_list = [p.strip() for p in providers_raw.split(",") if p.strip()] or None

    iface = AutoSearchInterface()
    result = iface.run_orchestrated(
        query,
        max_steps=5,
        mode="fast",
    )
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


async def _handle_orchestrate(arguments: dict) -> list[types.TextContent]:
    """Full AI-orchestrated search via orchestrator.run_task."""
    from orchestrator import run_task

    task_spec = arguments["task_spec"]
    max_steps = arguments.get("max_steps", 15)

    result = run_task(task_spec, max_steps=max_steps)

    # Extract summary for response
    output: dict[str, Any] = {
        "status": result.get("status", "unknown"),
        "collected_count": len(result.get("collected", [])),
        "summary": result.get("summary", ""),
        "top_results": result.get("collected", [])[:20],
    }
    return [
        types.TextContent(
            type="text",
            text=json.dumps(output, ensure_ascii=False, indent=2),
        )
    ]


async def _handle_doctor(arguments: dict) -> list[types.TextContent]:
    """Check provider health via capabilities.dispatch('check_health')."""
    from capabilities import dispatch

    providers_raw = arguments.get("providers", "")
    provider_list = [p.strip() for p in providers_raw.split(",") if p.strip()] or None

    result = dispatch("check_health", provider_list)
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


async def _handle_capabilities(arguments: dict) -> list[types.TextContent]:
    """List all available capabilities via capabilities.manifest_text."""
    from capabilities import manifest_text

    text = manifest_text()
    return [
        types.TextContent(
            type="text",
            text=text,
        )
    ]


async def _handle_resume(arguments: dict) -> list[types.TextContent]:
    """Resume from checkpoint via orchestrator.run_task with resume_from."""
    from orchestrator import run_task

    task_id = arguments["task_id"]
    result = run_task(
        "",  # empty task_spec — resume uses the checkpoint's spec
        resume_from=task_id,
    )
    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]


async def _handle_evolve(arguments: dict) -> list[types.TextContent]:
    """Run AVO evolution using genome-based evolution."""
    task_spec = arguments["task_spec"]
    generations = arguments.get("generations", 3)

    try:
        import asyncio
        from avo import run_avo_genome

        result = await asyncio.to_thread(
            run_avo_genome,
            task_spec,
            max_generations=generations,
            seed_genome_path=arguments.get("seed_genome", ""),
        )
    except ImportError:
        result = {
            "status": "not_implemented",
            "message": (
                "AVO genome evolution module is not yet available. "
                f"Requested: task_spec={task_spec!r}, generations={generations}"
            ),
        }

    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    ]
