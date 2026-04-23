# Installation

## For Humans

Paste this into your AI agent (Claude Code, Cursor, etc.):

```
Help me install AutoSearch: https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

---

## For AI Agents

### Goal

Install AutoSearch and configure the MCP server so the user's agent has access to 39 search channels across academic papers, developer platforms, Chinese social media, and more.

### ⚠️ Boundaries

- **DO NOT** run commands with `sudo` unless the user explicitly approved
- **DO NOT** modify system files outside the user's home directory
- If something requires elevated permissions, **tell the user** and let them decide

---

### Step 1: Install AutoSearch

```bash
# Option 1: npm (no Python setup required)
npm install -g autosearch-ai

# Option 2: pip
pip install autosearch

# Option 3: pipx (cleanest Python install)
pipx install autosearch
```

### Step 2: Initialize

> **npm users**: init runs automatically — skip this step.

```bash
autosearch init      # pip/pipx only
```

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
Always-on (21/21)
  ✅ arxiv              ready
  ✅ pubmed             ready
  ✅ ddgs               ready
  ... 18 more

Env-gated (0/1)
  ○  youtube            set YOUTUBE_API_KEY to enable

Login required (0/15)
  ○  xiaohongshu        run: autosearch login xhs
  ○  twitter            run: autosearch login twitter
  ... 13 more

Status: 21/37 channels ready
```

---

### Optional: Unlock more channels

**Ask the user which optional channels they want**, then use these commands:

#### Chinese social media (TikHub key required)
```bash
autosearch configure TIKHUB_API_KEY <your-key>
# Unlocks: xiaohongshu, douyin, weibo, zhihu, twitter, tiktok, bilibili, and more
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
  "autosearch": {
    "command": "autosearch-mcp",
    "type": "stdio"
  }
}
```

**Cursor** (Settings → MCP):
```json
{
  "autosearch": {
    "command": "autosearch-mcp",
    "args": []
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
