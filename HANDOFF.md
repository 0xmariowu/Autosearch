# Handoff

## main (updated 2026-04-03)

**What**: AutoSearch product polish — tests, delivery formats, efficiency, plugin distribution.

**Done**: PRs #27 (tests 9→279), #29 (delivery formats + CalVer + dev automation), #31 (efficiency: language filter + Sonnet routing + progress output), #32 (repo cleanup), #34 (model routing enforcement), #36 (plugin command + mode fix + README).

**Key decisions**:
- Plugin command namespace: /autosearch:autosearch in plugin, install.sh creates global command for clean /autosearch
- Mode: "auto" mandatory for researcher agent (bypassPermissions caused 10min hang)
- Model routing is contract not suggestion: Haiku for batch, Sonnet for reasoning, HTTP for search
- CalVer YYYY.M.D, first tag v2026.4.3

**Next**:
1. F002 S3: Sonnet vs Opus quality comparison (run /autosearch same topic both models)
2. Test HTML/slides delivery end-to-end
3. Run real AVO evolution session (PR #30 fixed blockers, untested)
4. Update plugin cache after merges
