---
title: "Using AutoSearch from an MCP Client"
description: "Install AutoSearch as an MCP server in Claude Code, Cursor, and other MCP-compatible clients"
---

# AutoSearch as an MCP Server

AutoSearch ships a standard [Model Context Protocol](https://modelcontextprotocol.io) stdio server that exposes the v2 tool-supplier toolkit — `list_skills`, `list_channels`, `run_clarify`, `select_channels_tool`, `run_channel`, `delegate_subtask`, plus `citation_create` / `citation_add` / `citation_export`, `doctor`, and helper tools such as `health` — to any MCP client. The host agent calls these tools and synthesizes the final answer itself; AutoSearch does not return a pre-baked report. Because the protocol is client-agnostic, the same server binary plugs into Claude Code, Cursor, Zed, Continue, and any other MCP-speaking surface without recompilation.

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
claude --mcp-config /path/to/mcp.json -p "List autosearch skills, then call run_channel on arxiv to find RAG evaluation papers and summarize the top results"
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

After saving the file, restart Cursor. Open the MCP panel — `autosearch` should appear with the v2 tools listed (`list_skills`, `list_channels`, `run_channel`, the citation helpers, etc.). Prompting the agent with something like "list autosearch skills, then run_channel on arxiv to survey vector database options" drives the v2 flow.

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

## The v2 MCP tools

The host agent drives a tool-supplier flow: discover skills, optionally clarify the user's intent, pick channels, run them, and synthesize the answer. The 10 required v2 tools are the names in `_REQUIRED_MCP_TOOLS`; `health` is a helper, not a required install-contract tool.

| Tool | Status | Purpose |
|---|---|---|
| `list_skills` | Required | Catalog of channel skills the agent can pick from. |
| `run_clarify` | Required | Optional one-shot clarification turn before search starts. |
| `run_channel` | Required | Run one channel for one query; returns `status` (`ok` / `no_results` / `not_configured` / `unknown_channel` / `auth_failed` / `rate_limited` / `budget_exhausted` / `transient_error` / `channel_unavailable` / `channel_error`), `evidence`, `unmet_requires`, `fix_hint`. The core retrieval call. |
| `list_channels` | Required | Per-channel availability (status, methods, language, requires). |
| `doctor` | Required | Channel-status snapshot (same data as the CLI, JSON-shaped). |
| `select_channels_tool` | Required | Helper that ranks candidate channels for a query. |
| `delegate_subtask` | Required | Run one query across multiple channels concurrently for a bounded subtask. |
| `citation_create` | Required | Open a citation collection for the current task. |
| `citation_add` | Required | Append a source URL + supporting evidence. |
| `citation_export` | Required | Export citations as `[N]`-numbered Markdown references. |
| `health` | Helper | Structured liveness snapshot — version, tool counts, required-tool status, channel counts by status, secrets-file presence (key NAMES only, never values), runtime cooldown snapshot. |

Beyond these, the server registers helpers like `consolidate_research`, `list_modes`, citation hardening (`citation_merge`), context controls (`context_retention_policy`), and several loop / planning helpers. The deprecated `research` tool is opt-in: it is only registered when `AUTOSEARCH_LEGACY_RESEARCH=1` is set, and new integrations should not depend on it.

`run_channel` schema:

| Field | Type | Default | Description |
|---|---|---|---|
| `channel_name` | string | required | One of the channels reported by `list_channels`. |
| `query` | string | required | Search query. Natural language, English or Chinese. |
| `rationale` | string | `""` | Optional short rationale, used by some channels to tune ranking. |
| `k` | int | 10 | Max evidence items to return. |

## Verifying the integration

Any MCP client supports a `tools/list` handshake before `tools/call`. If your client shows a GUI, seeing the v2 tool names (`list_skills`, `list_channels`, `run_channel`, …) in the panel is proof enough. For a scripted check without a GUI client, run this against any locally installed `autosearch-mcp`:

Run it with the same Python interpreter that has AutoSearch installed (for a `pipx install autosearch` setup, that's `pipx run --spec autosearch python` or inside the pipx venv — the snippet imports `mcp` which lives alongside `autosearch-mcp`, not in your system Python).

```python
import asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REQUIRED_V2_TOOLS = {
    "list_skills", "list_channels", "run_clarify", "select_channels_tool",
    "run_channel", "citation_create", "citation_add", "citation_export",
    "doctor", "delegate_subtask",
}

async def main():
    params = StdioServerParameters(
        command="autosearch-mcp",
        env={"PATH": os.environ["PATH"]},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            missing = REQUIRED_V2_TOOLS - tool_names
            assert not missing, f"required v2 tools missing: {missing}"

            # Smoke a free channel — no LLM key required.
            result = await session.call_tool(
                "run_channel",
                {"channel_name": "arxiv", "query": "BM25 ranking", "k": 3},
            )
            payload = result.content[0].text if result.content else ""
            print("OK — run_channel(arxiv) returned", len(payload), "chars")

asyncio.run(main())
```

The same handshake lands under `tests/e2b/matrix.yaml::F004_S4_mcp_stdio` in CI, so if local Python says "OK" your client config is guaranteed to work at the protocol layer — the only variable left is the client's own config file path and schema (covered in the sections above).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Client cannot find `autosearch-mcp` | Binary not on PATH for the client's shell | `pipx ensurepath && exec $SHELL`, or use an absolute path in `command` |
| `tools/list` returns empty | Server started but crashed before registering tools | Check LLM provider env var is set in the `env` block, not just your outer shell |
| `run_channel` returns `status="not_configured"` | The channel needs a key or login that isn't set yet | Follow the `fix_hint` in the response (e.g. `autosearch configure YOUTUBE_API_KEY <key>` or `autosearch login xhs`) |
| `run_channel` returns `status="auth_failed"` | Upstream rejected the request — 401/403, expired cookie, invalid API key, or a flagged account (XHS `code=300011`) | Follow the `fix_hint` (typically `autosearch login <channel>` with a different account, or `autosearch configure <KEY> <new-value>`) |
| `run_channel` returns `status="rate_limited"` | The declared per-minute / per-hour limit was exceeded for that channel + method | Lower the agent's parallel-channel fan-out, or wait a minute before retrying |
| `run_channel` returns `status="budget_exhausted"` | Paid quota / wallet is empty (TikHub 402, OpenAI `insufficient_quota`, etc.) | Top up the provider's balance — retrying without refilling will loop on the same error |
| `run_channel` returns `status="transient_error"` | Retryable transport or upstream failure | Retry the same channel later, or continue with other channels and come back if coverage is weak |
| `run_channel` returns `status="channel_unavailable"` | The channel is configured, but no method is usable right now | Try another channel; retry later if the unavailable method is expected to recover |
| `run_channel` returns `status="channel_error"` with a redacted `reason` | Upstream channel hiccup; secret-shaped strings are scrubbed before reaching the response | Retry; if persistent, check `autosearch doctor --json` and the upstream provider's status page |

## Where to go next

- Pipeline architecture: [`docs/delivery-status.md`](delivery-status.md)
- Channel coverage: see the Supported Channels table in the top-level [`README.md`](../README.md)
- Roadmap: [`docs/roadmap.md`](roadmap.md)
