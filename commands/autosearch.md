---
description: "Deep research via AutoSearch pipeline"
allowed-tools: ["Bash"]
---

Run deep research with AutoSearch and return the markdown report inline.

If AutoSearch is available in this Claude Code session as an MCP server, call the `research` tool.
- Pass `query` as the full user request.
- Pass `mode` as `"deep"` only when the user explicitly asks for deep or exhaustive coverage. Otherwise use `"fast"`.

If the MCP tool is not available, run the CLI instead:

```bash
autosearch query "$ARGUMENTS"
```

For explicitly deeper coverage, run:

```bash
autosearch query "$ARGUMENTS" --mode deep
```

Return the markdown report inline with no extra preamble.
If AutoSearch asks for clarification, ask that question to the user verbatim.
If AutoSearch returns an error, report the error briefly and stop.
