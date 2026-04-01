# Handoff

## feat/channel-improvements (updated 2026-04-01)
**What**: PR #19 open, CI pending. Improves search channel quality.
**Changes**: github-repos --sort=stars, arXiv API replaces dead Papers With Code, Semantic Scholar retry on 429, reddit channel added.
**Next**:
1. Merge PR #19 after CI green
2. **Core task: make every channel search well** — 42 channels registered but many use unreliable ddgs site:X. Each channel needs a real, working search backend. This is the product's core competitive advantage.
3. Start with failed channels from pipeline test: zhihu, reddit, producthunt, papers-with-code (now arxiv)
4. Study Armory/Search projects for per-channel best implementations (analysis done, see experience note)
**Product direction**: Don't reduce channels. Don't add API key requirements. Improve each channel's search quality individually. Skills-based open architecture stays.

## main (updated 2026-04-01)
**What**: v4.0 rubric AVO merged (#16), bugfix merged (#17). PR #15 closed (content already on main via #16).
**Pipeline test**: Ran full 7-phase pipeline on "self-evolving AI agent frameworks". Pass rate 0.880 (22/25 rubrics). 4/8 channels failed (reddit missing, zhihu noise, producthunt/papers-with-code 0 results). GitHub sort-by-stars was biggest quality win.
**Next**: After channel improvements merge → F008 10-run evolution validation (5 topics × 2 runs).
