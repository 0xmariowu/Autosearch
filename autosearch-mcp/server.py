#!/usr/bin/env python3
"""AutoSearch MCP Server — exposes search capabilities via Model Context Protocol."""

import sys
import os
import asyncio

# Add autosearch root to Python path
AUTOSEARCH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AUTOSEARCH_ROOT)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from tools import register_tools

server = Server("autosearch")
register_tools(server)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
