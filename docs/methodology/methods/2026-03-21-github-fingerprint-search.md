---
title: "Reverse Fingerprint Search: Finding Hidden Data on GitHub via Internal File Signatures"
date: 2026-03-21
project: search-methodology
type: method
platforms: [github]
precision: high
yield: high
tags: [fingerprinting, data-collection, claude-code, agent-traces, reverse-engineering]
status: active
---

# Reverse Fingerprint Search Methodology

## Problem

Public coding agent session data is scarce. Active sharing channels (DataClaw → HuggingFace, simonw/claude-code-transcripts) yield ~16 independent users. Traditional keyword search ("claude code dataset", "agent traces") only finds data people **intentionally** shared.

But many developers **accidentally** commit their local agent data to GitHub — they don't add `~/.claude/` to `.gitignore`. These repos have no searchable description, no tags, no README mentioning "session data." They're invisible to keyword search.

## Core Insight

**Don't search for how people describe data. Search for the data's own fingerprint.**

Every tool leaves unique artifacts on disk. If you know the internal file structure of a tool, you can search for those artifacts on GitHub to find repos that contain the tool's data — regardless of whether the repo owner intended to share it.

## Method: 5-Layer Search

### Layer 1: Internal File Signatures (Highest Precision)

Identify files/directories that **only** the target tool creates. These have near-zero false positives.

**Claude Code internal files:**

| Signature | Why It's Unique | Search Query |
|-----------|----------------|--------------|
| `.claude/statsig/` | A/B testing SDK cache, only in `~/.claude/` | `gh search code "path:.claude/statsig"` |
| `.claude/shell-snapshots/` | Shell env snapshots at session boundaries | `gh search code "path:shell-snapshots"` |
| `.claude/debug/` | Debug logs | `gh search code "path:.claude/debug"` |
| `security_warnings_state_*.json` | Per-session security state, filename contains UUID | `gh search code "security_warnings_state" --extension json` |
| `stats-cache.json` + `totalInputTokens` | Token usage cache, unique field name | `gh search code "stats-cache" "totalInputTokens"` |
| `.claude/plans/` | Planning files | `gh search code "path:.claude/plans" --extension md` |
| `.claude/plugins/` | Plugin state | `gh search code "path:.claude/plugins"` |

**Codex CLI internal files:**

| Signature | Search Query |
|-----------|--------------|
| `.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | `gh search code "path:.codex/sessions"` |
| `.codex/history.jsonl` | `gh search code "path:.codex" --extension jsonl` |

**OpenClaw internal files:**

| Signature | Search Query |
|-----------|--------------|
| `agents/*/sessions/*.jsonl` | `gh search code "path:agents" "sessions" --extension jsonl` |
| `.openclaw-state/` | `gh search code "path:.openclaw-state"` |

### Layer 2: JSONL Content Fingerprints (High Precision)

Even if the file isn't in a standard path, the content has unique field combinations.

**Claude Code session JSONL fields:**

| Field Combo | Uniqueness | Search Query |
|-------------|-----------|--------------|
| `thinkingMetadata` + `disabled` + `triggers` | Only Claude Code | `gh search code "thinkingMetadata" "disabled" "triggers" --extension jsonl` |
| `isSidechain` + `userType: "external"` | Only Claude Code | `gh search code "isSidechain" "userType" "external" --extension jsonl` |
| `stop_hook_active` + `transcript_path` | Hook events | `gh search code "stop_hook_active" "transcript_path"` |
| `slug` + `sessionId` + `gitBranch` | Session metadata | `gh search code "slug" "sessionId" "gitBranch" --extension jsonl` |

### Layer 3: Path Encoding Patterns (Medium Precision)

Claude Code encodes project paths as directory names: `/Users/john/project` → `.claude/projects/-Users-john-project/`

| Pattern | OS | Search Query |
|---------|-----|--------------|
| `projects/-Users-` | macOS | `gh search code "projects/-Users-" "jsonl"` |
| `projects/-home-` | Linux | `gh search code "projects/-home-" "jsonl"` |
| `projects/-root-` | root user | `gh search code "projects/-root-" "jsonl"` |
| `projects/-data-data-com-termux-` | Termux (Android) | Found in ryvynn session |

### Layer 4: Non-Standard Archive Paths (Medium Precision)

Some developers reorganize their session data before committing:

| Path Pattern | Search Query | Example Find |
|-------------|--------------|-------------|
| `conversation-archive/` | `gh search code "path:conversation-archive" --extension jsonl` | SkogAI (1,346 JSONL) |
| `claude-sessions/` | `gh search code "path:claude-sessions" --extension jsonl` | jwilger (2,875 JSONL) |
| `claude-logs/` | `gh search code "path:claude-logs"` | kim-em AoC2025 |
| `chat-sessions/` | `gh search code "path:chat-sessions" --extension jsonl` | Magicianhax |
| `raw_logs/` + `.claude` | `gh search code "path:.claude/raw_logs"` | 2lab-ai |
| `sesiones_historial/` | Found via content search | henlo-mm (Spanish team) |

### Layer 5: Tool Ecosystem Tracking (Indirect)

Find export tools → find their users → find their data:

1. DataClaw stargazers → check HuggingFace for their uploads
2. cctrace/ccexport forks → check if they published transcripts
3. simonw/claude-code-transcripts forks (133 forks) → check GitHub Pages
4. Traces.com platform → browse public traces (requires account)

## Results

| Search Layer | Repos Found | Unique Users | Data Volume |
|-------------|-------------|-------------|-------------|
| Layer 1 (internal files) | ~40 | ~35 | Largest single find: ryvynn 3.2GB |
| Layer 2 (JSONL content) | ~25 | ~20 | ecielam 1,193 JSONL |
| Layer 3 (path encoding) | ~15 | ~12 | mrpuna 4.7GB |
| Layer 4 (non-standard paths) | ~10 | ~8 | jwilger 2,875 JSONL, SkogAI 1,346 |
| Layer 5 (ecosystem) | ~35 HF datasets | ~16 | DataClaw 2,607 sessions |
| **Total (deduplicated)** | **~70 GitHub repos + 16 HF datasets** | **~80+** | **~34 GB** |

Layer 1 alone contributed **~50% of all new data sources**.

## Why This Works

1. **Accidental commit is systematic** — new Claude Code users don't know to `.gitignore` `.claude/`. Dotfiles repos are especially prone.
2. **Internal signatures have near-zero false positives** — `statsig` inside `.claude/` doesn't appear in normal code.
3. **GitHub indexes everything** — including files people didn't intend to make public.
4. **Doesn't require user intent** — unlike DataClaw/HuggingFace, no need for users to decide to share.

## Generalizable Pattern

This method works for **any tool** that creates unique local files:

1. Install the tool locally
2. Inspect what files it creates (especially in hidden directories)
3. Identify files/fields that are **unique to this tool** (not generic names like `config.json`)
4. Use GitHub code search to find repos containing those signatures
5. Verify hits are real data (not tools/parsers with example fixtures)

**Examples of tools this could work for:**
- Cursor (`.cursor/` directory)
- Continue.dev (`.continue/`)
- Cline (`.cline/`)
- Windsurf (`.windsurf/`)
- Any IDE plugin that writes local state

## Limitations

- GitHub code search has rate limits (~30 requests/minute)
- Results are capped at ~1000 per query
- Some repos may be taken down after owners realize they committed sensitive data
- The data contains PII (usernames, file paths, API keys in some cases) — scrubbing required for public use
- `--depth 1` clones only get the latest snapshot, not full history of session accumulation

## Appendix: Full Search Query List

```bash
# Layer 1: Internal files
gh search code "path:.claude/statsig" --limit 30
gh search code "path:shell-snapshots" --limit 30
gh search code "path:.claude/debug" --limit 20
gh search code "security_warnings_state" --extension json --limit 30
gh search code "stats-cache" "totalInputTokens" --extension json --limit 30
gh search code "path:.claude/plans" --extension md --limit 30
gh search code "path:.claude/plugins" --limit 20

# Layer 2: JSONL content
gh search code "thinkingMetadata" "disabled" "triggers" --extension jsonl --limit 30
gh search code "isSidechain" "userType" "external" --extension jsonl --limit 30
gh search code "stop_hook_active" "transcript_path" --extension jsonl --limit 20
gh search code "slug" "sessionId" "gitBranch" --extension jsonl --limit 30

# Layer 3: Path encoding
gh search code "projects/-Users-" "jsonl" --limit 30
gh search code "projects/-home-" "jsonl" --limit 30
gh search code "projects/-root-" "jsonl" --limit 20

# Layer 4: Non-standard paths
gh search code "path:conversation-archive" --extension jsonl --limit 30
gh search code "path:claude-sessions" --extension jsonl --limit 20
gh search code "path:claude-logs" --extension jsonl --limit 20
gh search code "path:chat-sessions" --extension jsonl --limit 20
gh search code "path:ai-sessions" --extension jsonl --limit 20
gh search code "path:coding-sessions" --extension jsonl --limit 20
gh search code "path:.claude/raw_logs" --limit 20

# Layer 5: Other tools
gh search code "path:.codex/sessions" --limit 30
gh search code "path:.codex" --extension jsonl --limit 30
gh search code ".aider.chat.history" --limit 30
gh search code "path:.openclaw" --limit 20

# Verification: check if repo has real session data
gh api repos/OWNER/REPO/git/trees/HEAD?recursive=1 --jq '[.tree[] | select(.path | test("\\.jsonl$"))] | length'
```
