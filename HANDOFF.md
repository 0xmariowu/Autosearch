# Handoff

## main (updated 2026-04-03)

**What**: AutoSearch v1.0.0 — Claude Code Plugin, published to GitHub marketplace.

**Done this session (5 PRs merged)**:
1. PR #22: Channel plugin system — 32 channels as independent plugins (SKILL.md + search.py)
2. PR #24: Report quality (citation lock, mandatory queries) + AVO evolution refinement + model routing (Haiku/Sonnet)
3. PR #25: Plugin structure (commands/, agents/, skills/, hooks/, scripts/)
4. PR #26: README, LICENSE, output templates, search depth config
5. Direct commits: benchmark results, CodeQL, install script, marketplace.json, repo cleanup

**Key technical decisions**:
- Chinese channels use kaifa.baidu.com (Baidu Developer Search) — no CAPTCHA, 100% success
- ddgs package upgraded to v9.12 (old duckduckgo_search was broken)
- Twitter/X channel searches both domains, dedup by status ID
- Reddit/Google Scholar use native API with ddgs fallback
- SearXNG engines extracted for: bilibili, stackoverflow, youtube, wechat, npm-pypi
- Plugin auto-setup via SessionStart hook (no manual /autosearch:setup needed)
- commands/autosearch.md deleted to avoid duplicate /autosearch:autosearch entry

**Benchmark**: AutoSearch 92% vs Native Claude 72% (+20%) across 5 topics

**Install**:
```
claude plugin marketplace add 0xmariowu/autosearch && claude plugin install autosearch@autosearch
```

**Known issue**: Old `/autosearch` skill with "v2.2" and "autosearch/v2/" paths persists in session cache. Fix: start fresh Claude Code session. The plugin's skills have correct paths.

**Next**:
1. Test /autosearch in a fresh session — verify plugin loads clean, no old cache
2. The /autosearch command was deleted from commands/ — the skill entry point is now through the plugin's skill system (pipeline-flow/SKILL.md). May need to add back a clean command file if /autosearch doesn't trigger from skills alone
3. Run a full end-to-end /autosearch search from the plugin (not from the project directory)
4. AVO evolution: find a topic with pass_rate < 0.90, run 3 rounds to validate evolution actually flips rubrics
5. Consider: should more channels be added? (V2EX, Hacker News China, Product Hunt alternatives)
6. Publish/promote: Twitter/Reddit/HN post with benchmark data
