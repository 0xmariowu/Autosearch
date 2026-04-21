---
title: "Using AutoSearch from an MCP Client"
description: "Install AutoSearch as an MCP server in Claude Code, Cursor, and other MCP-compatible clients"
---

# AutoSearch as an MCP Server

AutoSearch ships a standard [Model Context Protocol](https://modelcontextprotocol.io) stdio server that exposes two tools — `research` (the main deep-research entry point) and `health` (a liveness probe) — to any MCP client. Because the protocol is client-agnostic, the same server binary plugs into Claude Code, Cursor, Zed, Continue, and any other MCP-speaking surface without recompilation.

This page shows the config format for each supported client plus a one-minute verification routine.

## Prerequisites

- AutoSearch installed and on `PATH` (either `pipx install autosearch` or `uv pip install -e .` in a dev checkout). After install, the command `autosearch-mcp` should resolve.
- At least one LLM provider key in your environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`. You can also rely on a logged-in `claude` CLI on PATH as the provider.

Verify locally before wiring up a client:

```bash
autosearch-mcp --help 2>/dev/null || command -v autosearch-mcp
```

If the command is not found, your MCP client won't be able to launch it either — fix PATH first (for pipx installs, `pipx ensurepath` usually does it).

## Claude Code

Claude Code reads `~/.claude/mcp.json` globally and `<project>/.mcp.json` per-project. Add an `mcpServers.autosearch` entry:

```json
{
  "mcpServers": {
    "autosearch": {
      "command": "autosearch-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

You can also point the CLI at a specific config for one invocation:

```bash
claude --mcp-config /path/to/mcp.json -p "Use the research tool to summarize RAG evaluation methods"
```

AutoSearch additionally ships a Claude Code slash command at `commands/autosearch.md`; drop it into `~/.claude/commands/` to get `/autosearch <topic>`.

## Cursor

Cursor reads `~/.cursor/mcp.json`. Same schema:

```json
{
  "mcpServers": {
    "autosearch": {
      "command": "autosearch-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

After saving the file, restart Cursor. Open the MCP panel — `autosearch` should appear with the `research` tool listed. Prompting the agent with something like "use the research tool to survey vector database options" will invoke it.

### Using OpenAI or Gemini instead of Anthropic

Swap the `env` block for the provider you want to drive the pipeline:

```json
"env": {
  "OPENAI_API_KEY": "sk-...",
  "AUTOSEARCH_PROVIDER_CHAIN": "openai"
}
```

```json
"env": {
  "GOOGLE_API_KEY": "...",
  "AUTOSEARCH_PROVIDER_CHAIN": "gemini"
}
```

## Zed

Zed stores MCP servers under `context_servers` in `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "autosearch": {
      "command": {
        "path": "autosearch-mcp",
        "args": [],
        "env": {
          "ANTHROPIC_API_KEY": "sk-ant-..."
        }
      }
    }
  }
}
```

## Continue

Continue uses `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "autosearch-mcp",
          "env": {
            "ANTHROPIC_API_KEY": "sk-ant-..."
          }
        }
      }
    ]
  }
}
```

## The `research` tool

Input schema:

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Your research question. Natural language, English or Chinese. |
| `mode` | `"fast"` \| `"deep"` | `"fast"` | `fast` = 1 iteration, ~20–40s. `deep` = multi-iteration reflect-on-gaps loop, ~1–3 min and higher cost. |
| `languages` | `"all"` \| `"en_only"` \| `"zh_only"` \| `"mixed"` | `"all"` | Constrain channel selection by language scope. |
| `depth` | `"fast"` \| `"deep"` \| `"comprehensive"` | inherits `mode` | Finer-grained depth override; `comprehensive` extends `deep` with extra iteration budget. |
| `output_format` | `"md"` \| `"html"` | `"md"` | Markdown is the canonical report format; HTML wraps the markdown for client rendering. |

Output: a `ResearchResponse`-shaped result — most clients present it as a single text content block. On a successful research run the text is a Markdown report that typically ends with a `## References` section and `[N]`-style citations; on failure modes (rate limit, soft refusal, clarification needed) the content may instead be a short banner describing what happened. Don't assume `## References` always appears.

## Verifying the integration

Any MCP client supports a `tools/list` handshake before `tools/call`. If your client shows a GUI, the `research` tool appearing in the panel is proof enough. If you want a scripted check without a GUI client, run the following against any locally installed `autosearch-mcp`:

Run this with the same Python interpreter that has AutoSearch installed (for a `pipx install autosearch` setup, that's `pipx run --spec autosearch python` or inside the pipx venv — the snippet imports `mcp` which lives alongside `autosearch-mcp`, not in your system Python).

```python
import asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Forward whichever provider key is set. The MCP server picks the first one it finds.
PROVIDER_ENV = {
    k: os.environ[k]
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
    if os.environ.get(k)
}
assert PROVIDER_ENV, "set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY"

async def main():
    params = StdioServerParameters(
        command="autosearch-mcp",
        env={**PROVIDER_ENV, "PATH": os.environ["PATH"]},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert "research" in tool_names, f"research tool missing: {tool_names}"
            result = await session.call_tool("research", {"query": "Explain BM25 ranking", "mode": "fast"})
            report = "".join(c.text for c in result.content if hasattr(c, "text"))
            assert report.strip(), "research returned empty content"
            print("OK — autosearch-mcp responded with content length", len(report))

asyncio.run(main())
```

This is exactly the smoke that lands under `tests/e2b/matrix.yaml::F004_S4_mcp_stdio` in CI, so if local Python says "OK" your client config is guaranteed to work at the protocol layer — the only variable left is the client's own config file path and schema (covered in the sections above).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Client cannot find `autosearch-mcp` | Binary not on PATH for the client's shell | `pipx ensurepath && exec $SHELL`, or use an absolute path in `command` |
| `tools/list` returns empty | Server started but crashed before registering tools | Check LLM provider env var is set in the `env` block, not just your outer shell |
| `research` call returns empty Markdown | Provider rate-limited or invalid key | Verify the key independently: `anthropic` CLI / `openai api models list` / equivalent |
| Report has no `## References` | LLM returned a soft refusal | Retry with a more specific query; confirm the provider chain has an active key |

## Where to go next

- Pipeline architecture: [`docs/delivery-status.md`](delivery-status.md)
- Channel coverage: see the Supported Channels table in the top-level [`README.md`](../README.md)
- Roadmap: [`docs/roadmap.md`](roadmap.md)
