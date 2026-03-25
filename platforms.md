# Platform Connectors

## Reddit

**Best for**: User pain points, community discussions, tips/workarounds
**API**: `https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=on&limit=25&sort=relevance&t=all`
**Header**: `User-Agent: agent-reach/1.0`
**Rate limit**: ~0.2s between requests
**Engagement**: score + num_comments

### Validated patterns
- `sort=relevance` >> `sort=top` for finding pain points (53% vs 10% pain ratio)
- `restrict_sr=on` is MANDATORY — without it you get r/all noise
- Pain verbs in query outperform solution terms
- Product feature names as direct queries (e.g. "CLAUDE.md") work well

### Subreddit selection guide
- Coding AI: r/ClaudeCode, r/ClaudeAI, r/cursor, r/ChatGPTCoding
- Programming: r/programming, r/webdev, r/reactjs, r/typescript
- AI general: r/LocalLLaMA, r/artificial
- Choose based on the product/topic in the requirement

## Hacker News

**Best for**: High-level discourse, product launches, technical analysis
**API**: `https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=20`
**Engagement**: points + num_comments

### Validated patterns
- Product name in quotes: `"Claude Code"` → 16,600 score
- Product name + any modifier: `"Claude Code" rules` → 46 score (99% drop!)
- NEVER use abstract concepts ("AI coding agent context" = 26 points)
- Show HN tool posts need >100 points to be signal (otherwise just self-promo)

## Exa (semantic search)

**Best for**: Discovery, GitHub issues, blog posts, research papers
**API**: `mcporter call 'exa.web_search_exa(query: "...", numResults: 10)'`
**Engagement**: Not provided — use for discovery, then verify on source platform

### Validated patterns
- Natural language problem descriptions work best
- Add `site:huggingface.co/datasets` or `github.com` for focused results
- Found 8/8 relevant GitHub issues in one query (vs 0 from `gh search`)
- Best for finding things keyword search can't reach

## GitHub Issues

**Best for**: Specific bug reports, feature requests, reproducible problems
**API**: `gh search issues "query" --repo owner/repo --sort comments --limit 10 --json title,url,commentsCount`
**Also via Exa**: Often better discovery than native `gh search`

### Validated patterns
- Exa finds GitHub issues better than gh search
- Sort by comments for most-discussed issues
- Multi-repo search: anthropics/claude-code, getcursor/cursor, paul-gauthier/aider, etc.

## HuggingFace Datasets

**Best for**: Structured datasets, benchmarks, training data
**API**: `https://huggingface.co/api/datasets?search={query}&sort=downloads&direction=-1&limit=20`
**Also via Exa**: Better for semantic discovery

### Validated patterns
- HF API: max 2 keywords, more = empty results
- Exa: use natural language ("coding agent trajectory tool-use dataset")
- Check author's other datasets when you find a good one
- Check HF Collections for curated lists

## Twitter/X (updated)

**Best for**: Real-time complaints, developer hot takes, product announcements
**API options**:
1. `xreach search "query" -n 10 --json` — unreliable, often returns empty
2. `xreach tweets @username -n 20 --json` — works for known users
3. Exa with `site:twitter.com` or `site:x.com` — best discovery method
4. `xreach tweet URL --json` — reading specific tweets works

### Validated patterns
- xreach search is unreliable for all query types (tested 2026-03-21)
- Use Exa for discovery, then xreach to read specific tweet URLs
- Known influential accounts for coding AI: search their timelines directly

### Usage flow
```
1. Exa search with topic + "site:x.com" → find tweet URLs
2. xreach tweet URL --json → read full tweet + engagement
3. If user is prolific, xreach tweets @user -n 20 → scan timeline
```

**Note on `twitter_xreach` in daily pipeline**: `daily.py` includes `twitter_xreach` as a platform. Despite xreach search being unreliable for general queries, it may occasionally return results for specific product names. Treat twitter_xreach results as supplementary — Exa-based discovery remains the primary Twitter search method.

## Variant Connectors (engine.py)

The engine supports multiple connectors per platform. These are the additional variants not described above:

## alphaXiv MCP

**Best for**: arXiv paper discovery, paper reading, PDF question answering, paper-linked code exploration
**Endpoint**: `https://api.alphaxiv.org/mcp/v1`
**Transport**: SSE + OAuth 2.0
**Status**: Environment-integrated via `~/.mcp.json`, not yet a daily runtime provider

### Why it matters
- Exa is still the better default for broad discovery across the web
- alphaXiv is better when the desired artifact is explicitly an academic paper
- It adds paper-native analysis depth that current daily providers do not have

### Current integration boundary
- Available to Claude Code as an MCP research source
- Documented in `docs/methodology/platforms/alphaxiv.md`
- Not yet wired into `engine.py` / `daily.py` as an unattended provider because first-use OAuth and runtime semantics need to be pinned down

### reddit_exa
- **What**: Exa semantic search scoped to `site:reddit.com`
- **When to use**: When Reddit API fails or when natural language queries are needed
- **Connector**: `PlatformConnector._reddit_exa()`

### hn_exa
- **What**: Exa semantic search scoped to `site:news.ycombinator.com`
- **When to use**: When HN Algolia doesn't surface what you need via keywords
- **Connector**: `PlatformConnector._hn_exa()`

### github_repos
- **What**: `gh search repos` — searches for repositories (not issues)
- **When to use**: Finding tools, frameworks, reference implementations
- **Sorts by**: stars (default)
- **Connector**: `PlatformConnector._github_repos()`

### twitter_xreach vs twitter_exa
- **`twitter_exa`**: Exa + `site:x.com` — reliable for discovery
- **`twitter_xreach`**: `xreach search` directly — unreliable, used in daily pipeline as supplementary
- Both are separate named platforms in engine.py's dispatch table
