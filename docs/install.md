# AutoSearch — Installation Guide

<!-- Structure 1:1 from Agent-Reach docs/install.md -->

## For Humans

Copy this to your Claude Code (or any AI agent):

```
帮我安装 AutoSearch：https://raw.githubusercontent.com/0xmariowu/Autosearch/main/docs/install.md
```

---

## For AI Agents

### Goal

Install AutoSearch and configure the MCP server so the user's agent has access to 37+ search channels across academic papers, developer platforms, Chinese social media, and more.

### ⚠️ Boundaries

- **DO NOT** run commands with `sudo` unless the user explicitly approved
- **DO NOT** modify system files outside the user's home directory
- If something requires elevated permissions, **tell the user** and let them decide

---

### Step 1: Install AutoSearch

```bash
# Recommended: pipx (cleanest)
pipx install git+https://github.com/0xmariowu/Autosearch.git

# If pipx not available, use uv or pip in a venv:
uv tool install git+https://github.com/0xmariowu/Autosearch.git
# or:
python3 -m venv ~/.autosearch-venv
source ~/.autosearch-venv/bin/activate
pip install git+https://github.com/0xmariowu/Autosearch.git
```

### Step 2: Initialize and detect providers

```bash
autosearch init
```

This will:
- Detect available LLM providers (Anthropic, OpenAI, Gemini, claude CLI)
- Create `~/.autosearch/config.yaml`
- Print the MCP server config snippet

### Step 3: Add MCP server to your agent

After `autosearch init`, you'll see a config snippet like this. Add it to your MCP config:

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

### Step 4: Check status

```bash
autosearch doctor
```

You'll see a tiered report:

```
AutoSearch 渠道状态
==========================================
开箱即用 (21/21)
  ✅ arxiv              21/21 methods available
  ✅ pubmed             1/1 methods available
  ✅ ddgs               1/1 methods available
  ... 18 more

API key 渠道 (0/1)
  ❌ youtube            未配置  →  autosearch configure YOUTUBE_API_KEY <your-key>

需登录渠道 (0/15)
  ❌ xiaohongshu        未配置  →  autosearch login xhs
  ❌ twitter            未配置  →  autosearch login twitter
  ... 13 more

状态：21/37 个渠道可用
```

---

### Optional: Unlock more channels

**Ask the user which optional channels they want**, then use these commands:

#### Chinese social media (TikHub key required)
```bash
autosearch configure TIKHUB_API_KEY <your-key>
# Unlocks: xiaohongshu, douyin, weibo, zhihu, twitter, instagram, tiktok, bilibili, and more
```

#### Xiaohongshu with your own account (no TikHub fee)
```bash
autosearch login xhs
# Reads cookies from Chrome automatically.
# If it fails, use Cookie-Editor browser extension → Export → Header String, then:
autosearch login xhs --from-string "<paste-cookie-string>"
```

#### Twitter/X
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

#### SearXNG (local meta-search, completely free)
```bash
docker run -d -p 8080:8080 searxng/searxng
autosearch configure SEARXNG_URL http://localhost:8080
```

---

### How to use

Once the MCP server is running, AutoSearch exposes these tools to your agent:

| Tool | Description |
|---|---|
| `run_clarify` | Understand the research goal and pick the right channels |
| `run_channel` | Search a specific channel |
| `delegate_subtask` | Run multiple channels in parallel |
| `list_channels` | See all available channels with status |
| `doctor` | Full health report with fix hints |

**Typical research flow:**
```
run_clarify("latest transformer architectures 2026")
→ select_channels_tool(query, mode="academic")
→ delegate_subtask(["arxiv", "papers", "hackernews"], query)
→ citation_create() + export_citations()
```

---

### Updating

```bash
pipx upgrade autosearch
# or:
uv tool upgrade autosearch
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

Your XHS account was flagged. Run with a normal, actively-used account:
```bash
autosearch login xhs  # re-login with a different account
```
