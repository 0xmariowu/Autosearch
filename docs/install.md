# Installation

## For Humans

Paste this into your AI agent (Claude Code, Cursor, etc.):

```
Help me install AutoSearch: https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

---

## For AI Agents

### Goal

Install AutoSearch and configure the MCP server so the user's agent has access to 40 search channels across academic papers, developer platforms, Chinese social media, and more.

### ⚠️ Boundaries

- **DO NOT** run commands with `sudo` unless the user explicitly approved
- **DO NOT** modify system files outside the user's home directory
- If something requires elevated permissions, **tell the user** and let them decide

---

### Step 1: Install AutoSearch

```bash
# Option 1: npx — one command, no setup required (recommended)
npx autosearch-ai

# Option 2: curl install script
curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash

# Option 3: pip
pip install autosearch && autosearch init

# Option 4: pipx
pipx install autosearch && autosearch init
```

> The curl option runs `autosearch init` automatically. The npx option prints the install URL it's about to fetch and waits for `y` to confirm — pass `--yes` (or `-y`) to skip the prompt for non-interactive automation.

This will:
- Detect available LLM providers (Anthropic, OpenAI, Gemini, claude CLI)
- Create `~/.autosearch/config.yaml`
- Auto-write MCP server config to `~/.claude/mcp.json` and `~/.cursor/mcp.json`

### Step 3: Check status

```bash
autosearch doctor
```

You'll see a tiered report:

```
AutoSearch Channel Status
==========================================
Always-on (27/27)
  ✅ arxiv              1/1 methods available
  ✅ pubmed             1/1 methods available
  ✅ ddgs               1/1 methods available
  ... 24 more

API-key (0/11)
  ○  youtube            autosearch configure YOUTUBE_API_KEY <your-key>
  ○  bilibili           autosearch configure TIKHUB_API_KEY <your-key>
  ... 9 more

Login required (0/2)
  ○  xiaohongshu        autosearch login xhs
  ○  xueqiu             autosearch login xueqiu

Status: 27/40 channels ready
```

---

### Optional: Unlock more channels

**Ask the user which optional channels they want**, then use these commands:

#### Chinese social media (TikHub auth)
```bash
autosearch configure TIKHUB_API_KEY <your-key>
# Unlocks: xiaohongshu, douyin, weibo, zhihu, twitter, tiktok, bilibili, and more
```

If you use an AutoSearch TikHub proxy, configure the proxy URL and token instead.
Together, `AUTOSEARCH_PROXY_URL` and `AUTOSEARCH_PROXY_TOKEN` satisfy TikHub
channel availability without `TIKHUB_API_KEY`:

```bash
autosearch configure AUTOSEARCH_PROXY_URL <proxy-url>
autosearch configure AUTOSEARCH_PROXY_TOKEN <proxy-token>
```

#### Xiaohongshu with your own account (no TikHub fee)
```bash
autosearch login xhs
# Reads cookies from Chrome automatically.
# If it fails, use Cookie-Editor browser extension → Export → Header String, then:
autosearch login xhs --from-string "<paste-cookie-string>"
```

#### Twitter / X
```bash
autosearch login twitter
```

#### Bilibili
```bash
autosearch login bilibili
```

#### YouTube
```bash
autosearch configure YOUTUBE_API_KEY <your-key>
# Free key: console.cloud.google.com → Enable YouTube Data API v3
```

---

### MCP server config

AutoSearch writes this automatically during `init`. For manual setup:

**Claude Code** (`~/.claude/mcp.json`):
```json
{
  "mcpServers": {
    "autosearch": {
      "command": "autosearch-mcp",
      "type": "stdio"
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "autosearch": {
      "command": "autosearch-mcp",
      "type": "stdio"
    }
  }
}
```

---

### Updating

```bash
npm install -g autosearch-ai   # npm
pipx upgrade autosearch        # pipx
pip install --upgrade autosearch  # pip
```

---

### Troubleshooting

**Channel returns empty results?**
```bash
autosearch doctor  # check which channels are off and why
```

**MCP server not found?**
```bash
which autosearch-mcp  # verify it's on PATH
autosearch-mcp --help
```

**Xiaohongshu returns code=300011 (account restricted)?**

Your XHS account was flagged. Re-login with a normal, actively-used account:
```bash
autosearch login xhs
```
