#!/usr/bin/env python3
"""
AutoSearch Engine — self-evolving search loop.

3 phases:
  Phase 1: EXPLORE — find best queries (pattern injection + LLM evaluation)
  Phase 2: HARVEST — collect findings with winning queries
  Phase 3: POST-MORTEM — analyze what worked/failed, write back to patterns.jsonl

AI fills GENES, PLATFORMS, TARGET_SPEC, OUTPUT_PATH before running.
"""

import json, urllib.request, urllib.parse, os, time, random, hashlib, statistics, subprocess
from datetime import datetime
from pathlib import Path

AUTOSEARCH_DIR = Path(__file__).parent
PATTERNS_PATH = AUTOSEARCH_DIR / "patterns.jsonl"
EVOLUTION_PATH = AUTOSEARCH_DIR / "evolution.jsonl"

# ============================================================
# AI FILLS THESE PER TASK
# ============================================================
GENES = {
    "entity": [],       # Product/tool names from requirement
    "pain_verb": [],    # What goes wrong
    "object": [],       # What's affected
    "symptom": [],      # How it manifests
    "context": [],      # Where/when it happens
}

PLATFORMS = [
    # {"name": "reddit", "sub": "..."},
    # {"name": "hn"},
    # {"name": "exa"},
    # {"name": "github", "repo": "owner/repo"},   # repo is optional
    # {"name": "twitter_exa"},
]

TARGET_SPEC = ""  # One sentence: "what does a useful finding look like?"
OUTPUT_PATH = "/tmp/autosearch-findings.jsonl"
TASK_NAME = "autosearch"  # Used for session doc filename

# ============================================================
# CONFIG
# ============================================================
MAX_STALE = 5
MAX_ROUNDS = 15
QUERIES_PER_ROUND = 15

HARVEST_SINCE = "2025-10-01"

# Query source ratios
LLM_RATIO = 0.20
PATTERN_RATIO = 0.20
GENE_RATIO = 0.60

# ============================================================
# LOAD PAST PATTERNS (self-evolution input)
# ============================================================
def load_patterns():
    """Read patterns.jsonl — past learnings injected into this run."""
    patterns = {"use": [], "avoid": []}
    if PATTERNS_PATH.exists():
        for line in PATTERNS_PATH.read_text().splitlines():
            if not line.strip(): continue
            p = json.loads(line)
            finding = p.get("finding", "")
            if any(w in finding.lower() for w in ["fail", "don't", "never", "avoid", "unreliable", "empty"]):
                patterns["avoid"].append(p)
            else:
                patterns["use"].append(p)
    return patterns

PAST_PATTERNS = load_patterns()

# ============================================================
# LLM EVALUATION (Anthropic API)
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def call_anthropic(prompt, max_tokens=1024):
    """Call Anthropic API. Returns parsed JSON or None on error/no key."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        text = resp.get("content", [{}])[0].get("text", "")
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None
    except Exception as e:
        print(f"    [LLM] Error: {e}")
        return None

def llm_evaluate_round(results_top10):
    """Ask LLM to evaluate result relevance and suggest new queries.

    Sends title + body[:200] (C2 fix: not just title).
    Returns {"results": [...], "next_queries": [...]} or None.
    """
    if not results_top10 or not ANTHROPIC_API_KEY:
        return None

    items = []
    for i, r in enumerate(results_top10[:10]):
        body_preview = r.get("body", "")[:200].replace("\n", " ")
        items.append(f'{i}. "{r["title"]}" | {body_preview}')

    prompt = f"""You are evaluating search results for relevance.

TARGET: {TARGET_SPEC}

Results:
{chr(10).join(items)}

Respond ONLY with JSON (no markdown, no code fences):
{{"results": [{{"index": 0, "relevant": true, "reason": "..."}}], "next_queries": ["search term 1", "search term 2"]}}

Rules:
- Mark relevant=true ONLY if the result directly matches the TARGET
- Suggest 2-3 next_queries that would find MORE results matching TARGET
- next_queries should be concrete search terms, not descriptions"""

    return call_anthropic(prompt)

# ============================================================
# PLATFORM CONNECTORS
# ============================================================
def search_reddit(sub, query, limit=20):
    url = f"https://www.reddit.com/r/{sub}/search.json?q={urllib.parse.quote(query)}&restrict_sr=on&limit={limit}&sort=relevance&t=all"
    req = urllib.request.Request(url, headers={"User-Agent": "agent-reach/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return [{"title": p["data"].get("title",""),
                 "url": "https://www.reddit.com" + p["data"].get("permalink",""),
                 "eng": p["data"].get("score",0) + p["data"].get("num_comments",0),
                 "created": datetime.fromtimestamp(p["data"].get("created_utc",0)).strftime("%Y-%m-%d"),
                 "body": p["data"].get("selftext","")[:500],
                 "source": "reddit"}
                for p in data.get("data",{}).get("children",[])]
    except Exception:
        return []

def search_hn(query, limit=20):
    url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={limit}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        return [{"title": h.get("title",""),
                 "url": f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
                 "eng": h.get("points",0) + h.get("num_comments",0),
                 "created": h.get("created_at","")[:10],
                 "source": "hn"}
                for h in data.get("hits",[])]
    except Exception:
        return []

def search_exa(query, limit=10):
    """Search via Exa (mcporter CLI). eng=0 — contributes URLs, not engagement."""
    try:
        escaped = query.replace('"', '\\"')
        cmd = ["mcporter", "call",
               f'exa.web_search_exa(query: "{escaped}", numResults: {limit})']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        results = data if isinstance(data, list) else data.get("results", [])
        return [{"title": r.get("title", ""),
                 "url": r.get("url", ""),
                 "eng": 0,
                 "created": r.get("publishedDate", "")[:10] if r.get("publishedDate") else "",
                 "body": r.get("text", "")[:500] if r.get("text") else "",
                 "source": "exa"}
                for r in results if r.get("url")]
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

def search_github_issues(query, repo=None, limit=10):
    """Search GitHub issues via gh CLI. eng=commentsCount."""
    try:
        cmd = ["gh", "search", "issues", query,
               "--sort", "comments", "--limit", str(limit),
               "--json", "title,url,commentsCount,body,createdAt"]
        if repo:
            cmd.extend(["--repo", repo])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
        issues = json.loads(result.stdout)
        return [{"title": i.get("title", ""),
                 "url": i.get("url", ""),
                 "eng": i.get("commentsCount", 0),
                 "created": i.get("createdAt", "")[:10],
                 "body": i.get("body", "")[:500] if i.get("body") else "",
                 "source": "github"}
                for i in issues]
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

def search_twitter_exa(query, limit=10):
    """Search Twitter/X via Exa with site:x.com filter. eng=0."""
    try:
        site_query = f"{query} site:x.com"
        escaped = site_query.replace('"', '\\"')
        cmd = ["mcporter", "call",
               f'exa.web_search_exa(query: "{escaped}", numResults: {limit})']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        results = data if isinstance(data, list) else data.get("results", [])
        return [{"title": r.get("title", ""),
                 "url": r.get("url", ""),
                 "eng": 0,
                 "created": r.get("publishedDate", "")[:10] if r.get("publishedDate") else "",
                 "body": r.get("text", "")[:500] if r.get("text") else "",
                 "source": "twitter"}
                for r in results if r.get("url")]
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

# ============================================================
# QUERY GENERATION (past patterns + LLM suggestions + gene pool)
# ============================================================
LLM_SUGGESTIONS = []  # Accumulated across rounds

def gen_query():
    cats = [k for k, v in GENES.items() if v]
    if len(cats) < 2: return ""
    parts = [random.choice(GENES[random.choice(cats)]) for _ in range(random.randint(2, 3))]
    return " ".join(parts)

def gen_queries_with_patterns(n=15):
    """Generate queries: 20% LLM + 20% past patterns + 60% gene pool."""
    queries = []
    sources = {}  # query -> source tag

    n_llm = int(n * LLM_RATIO)
    n_pattern = int(n * PATTERN_RATIO)

    # 20% from LLM suggestions (if available)
    if LLM_SUGGESTIONS:
        for q in random.sample(LLM_SUGGESTIONS, min(n_llm, len(LLM_SUGGESTIONS))):
            if q and q not in sources:
                queries.append(q)
                sources[q] = "llm"

    # 20% from past winning patterns
    if PAST_PATTERNS["use"]:
        for p in random.sample(PAST_PATTERNS["use"], min(n_pattern, len(PAST_PATTERNS["use"]))):
            finding = p.get("finding", "")
            cats = [k for k, v in GENES.items() if v]
            if cats:
                gene = random.choice(GENES[random.choice(cats)])
                keywords = [w for w in finding.split() if len(w) > 4]
                if keywords:
                    q = f"{random.choice(keywords)} {gene}"
                    if q not in sources:
                        queries.append(q)
                        sources[q] = "pattern"

    # 60% from gene pool
    attempts = 0
    while len(queries) < n and attempts < n * 3:
        q = gen_query()
        if q and q not in sources:
            queries.append(q)
            sources[q] = "gene"
        attempts += 1

    return queries[:n], sources

# ============================================================
# SCORING (relevance-aware + MAD confidence)
# ============================================================
SEEN = set()
ALL_SCORES = []

def score_results(results):
    """Score with dedup. avg_engagement only counts sources with eng > 0."""
    new_results = [r for r in results if r["url"] not in SEEN]
    if not new_results: return 0, 0, []
    for r in new_results: SEEN.add(r["url"])

    # Exa/Twitter contribute new_urls but don't dilute engagement average
    eng_results = [r for r in new_results if r["eng"] > 0]
    avg_eng = sum(r["eng"] for r in eng_results) / len(eng_results) if eng_results else 0

    return len(new_results), int(len(new_results) * avg_eng), new_results

def compute_adjusted_score(raw_score, relevance_ratio):
    """Weighted scoring: 40% engagement + 60% relevance.

    Fixes C1 zero-collapse: even with 0 engagement, relevance still scores.
    """
    normalized_eng = min(raw_score / 10000, 1.0) if raw_score > 0 else 0
    return int((0.4 * normalized_eng + 0.6 * relevance_ratio) * 10000)

def mad_confidence(scores):
    """Median Absolute Deviation confidence (from pi-autoresearch)."""
    if len(scores) < 3: return None
    median = statistics.median(scores)
    mad = statistics.median([abs(s - median) for s in scores])
    if mad == 0: return None
    best = max(scores)
    return round((best - median) / mad, 1)

# ============================================================
# SESSION DOCUMENT (atomic writes)
# ============================================================
SESSION_DOC_PATH = None

def _atomic_write(path, content):
    """Write to .tmp then rename — atomic on same filesystem."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)

def init_session_doc():
    """Write point 1: Phase 1 start."""
    global SESSION_DOC_PATH
    SESSION_DOC_PATH = AUTOSEARCH_DIR / f"{TASK_NAME}.md"
    content = (
        f"# AutoSearch Session: {TASK_NAME}\n\n"
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Target**: {TARGET_SPEC}\n"
        f"**Platforms**: {', '.join(p['name'] for p in PLATFORMS)}\n"
        f"**LLM evaluation**: {'ON' if ANTHROPIC_API_KEY else 'OFF'}\n"
        f"**Genes**: {json.dumps(GENES, ensure_ascii=False)}\n\n"
        f"---\n\n"
        f"## Phase 1: Exploration\n\n"
    )
    _atomic_write(SESSION_DOC_PATH, content)

def append_session_doc(text):
    """Append to session doc."""
    if not SESSION_DOC_PATH: return
    with open(SESSION_DOC_PATH, "a", encoding="utf-8") as f:
        f.write(text)

# ============================================================
# SEARCH RUNNER
# ============================================================
def run_query_all_platforms(query):
    all_results = []
    for plat in PLATFORMS:
        name = plat["name"]
        if name == "reddit":
            all_results.extend(search_reddit(plat["sub"], query))
        elif name == "hn":
            all_results.extend(search_hn(query))
        elif name == "exa":
            all_results.extend(search_exa(query))
        elif name == "github":
            all_results.extend(search_github_issues(query, repo=plat.get("repo")))
        elif name == "twitter_exa":
            all_results.extend(search_twitter_exa(query))
        time.sleep(0.15)
    return all_results

# ============================================================
# PHASE 1: EXPLORE
# ============================================================
init_session_doc()

print("=" * 60)
print("PHASE 1: Query Exploration")
print(f"  Past patterns loaded: {len(PAST_PATTERNS['use'])} positive, {len(PAST_PATTERNS['avoid'])} negative")
print(f"  LLM evaluation: {'ON' if ANTHROPIC_API_KEY else 'OFF (no ANTHROPIC_API_KEY)'}")
print(f"  Platforms: {', '.join(p['name'] for p in PLATFORMS)}")
print("=" * 60)

history_best_raw = 0
history_best_relevance = 0.0
stale = 0
all_experiments = []

for rnd in range(1, MAX_ROUNDS + 1):
    queries, query_sources = gen_queries_with_patterns(QUERIES_PER_ROUND)
    round_best_raw = 0
    round_new_total = 0
    round_all_results = []

    for q in queries:
        results = run_query_all_platforms(q)
        new_count, raw_score, new_results = score_results(results)
        round_new_total += new_count
        round_all_results.extend(new_results)

        all_experiments.append({
            "round": rnd, "query": q, "new": new_count, "score": raw_score,
            "adjusted_score": 0,  # filled after LLM evaluation
            "source": query_sources.get(q, "gene"),
            "sample_titles": [r["title"][:60] for r in (new_results or [])[:3]]
        })
        ALL_SCORES.append(raw_score)
        if raw_score > round_best_raw:
            round_best_raw = raw_score

    # --- Step 3.5: LLM evaluation ---
    relevance_ratio = 0.0
    llm_suggestions = []
    if round_all_results:
        top10 = sorted(round_all_results, key=lambda r: r["eng"], reverse=True)[:10]
        llm_result = llm_evaluate_round(top10)
        if llm_result:
            relevant_count = sum(1 for r in llm_result.get("results", []) if r.get("relevant"))
            total_evaluated = len(llm_result.get("results", []))
            relevance_ratio = relevant_count / max(total_evaluated, 1)
            llm_suggestions = llm_result.get("next_queries", [])
            LLM_SUGGESTIONS.extend(llm_suggestions)
            LLM_SUGGESTIONS[:] = LLM_SUGGESTIONS[-30:]  # recency cap

    # Adjusted score (C1 fix: weighted, no zero-collapse)
    round_adjusted = compute_adjusted_score(round_best_raw, relevance_ratio)

    # Back-fill adjusted_score for this round's experiments
    for e in all_experiments:
        if e["round"] == rnd:
            e["adjusted_score"] = compute_adjusted_score(e["score"], relevance_ratio)

    # Stale tracking: relevance if LLM succeeded, raw score otherwise
    llm_succeeded = ANTHROPIC_API_KEY and llm_result is not None
    if llm_succeeded:
        rel_delta = (relevance_ratio - history_best_relevance) / max(history_best_relevance, 0.01)
        if relevance_ratio > history_best_relevance:
            history_best_relevance = relevance_ratio
        stale = stale + 1 if rel_delta < 0.1 else 0
    else:
        raw_delta = (round_best_raw - history_best_raw) / max(history_best_raw, 1)
        if round_best_raw > history_best_raw:
            history_best_raw = round_best_raw
        stale = stale + 1 if raw_delta < 0.1 else 0

    conf = mad_confidence(ALL_SCORES) or "n/a"
    rel_str = f"rel={relevance_ratio:.0%} " if ANTHROPIC_API_KEY else ""
    print(f"  R{rnd:2d}: adj={round_adjusted:6d} raw={round_best_raw:6d} "
          f"new={round_new_total:3d} seen={len(SEEN):4d} "
          f"stale={stale}/{MAX_STALE} {rel_str}conf={conf}")

    # Write point 2: each round end
    llm_line = f"\n- LLM suggestions: {llm_suggestions}" if llm_suggestions else ""
    append_session_doc(
        f"### Round {rnd}\n"
        f"- Queries: {len(queries)} | New URLs: {round_new_total} | "
        f"Raw best: {round_best_raw} | Adjusted: {round_adjusted}\n"
        f"- Relevance: {relevance_ratio:.0%} | Stale: {stale}/{MAX_STALE}\n"
        f"- Top query: `{queries[0] if queries else 'n/a'}`"
        f"{llm_line}\n\n"
    )

    if stale >= MAX_STALE:
        print(f"  >>> EARLY STOP after {rnd} rounds")
        append_session_doc(f"**EARLY STOP** after {rnd} rounds (stale={stale})\n\n")
        break

top_queries = sorted(all_experiments, key=lambda x: x["adjusted_score"], reverse=True)[:20]
print(f"\nTop 5 queries:")
for q in top_queries[:5]:
    src_tag = f" [{q['source']}]" if q["source"] != "gene" else ""
    print(f"  score={q['score']:6d} new={q['new']:2d}{src_tag:9s} | {q['query'][:50]}")

append_session_doc(
    "## Top Queries\n\n"
    "| # | Query | Score | New | Source |\n"
    "|---|-------|-------|-----|--------|\n"
    + "\n".join(
        f"| {i+1} | {q['query'][:50]} | {q['score']} | {q['new']} | {q['source']} |"
        for i, q in enumerate(top_queries[:10])
    )
    + "\n\n"
)

# ============================================================
# PHASE 2: HARVEST
# ============================================================
print(f"\n{'='*60}")
print("PHASE 2: Harvest")
print(f"{'='*60}")

HARVEST_SEEN = set()
total_harvested = 0

for q_entry in top_queries[:15]:
    results = run_query_all_platforms(q_entry["query"])
    new = 0
    for r in results:
        if r["url"] in HARVEST_SEEN: continue
        created = r.get("created", "")
        if created and created < HARVEST_SINCE: continue
        # Engagement threshold only for sources that provide it
        if r["eng"] < 5 and r.get("source") not in ("exa", "twitter"):
            continue
        HARVEST_SEEN.add(r["url"])
        with open(OUTPUT_PATH, "a") as f:
            f.write(json.dumps({
                "url": r["url"], "title": r["title"][:150],
                "engagement": r["eng"], "created": r.get("created",""),
                "body": r.get("body","")[:500],
                "query": q_entry["query"],
                "source": r.get("source", "unknown"),
                "collected": datetime.now().strftime("%Y-%m-%d"),
            }, ensure_ascii=False) + "\n")
        new += 1
    total_harvested += new

print(f"  Harvested: {total_harvested} findings -> {OUTPUT_PATH}")

# Write point 3: Phase 2 end
append_session_doc(
    f"## Phase 2: Harvest\n\n"
    f"- Queries used: {min(len(top_queries), 15)}\n"
    f"- Findings harvested: {total_harvested}\n"
    f"- Output: `{OUTPUT_PATH}`\n\n"
)

# ============================================================
# PHASE 3: POST-MORTEM (self-evolution)
# ============================================================
print(f"\n{'='*60}")
print("PHASE 3: Post-Mortem (self-evolution)")
print(f"{'='*60}")

# 3a. Classify experiments
winners = [e for e in all_experiments if e["score"] > 0]
losers = [e for e in all_experiments if e["score"] == 0]

print(f"  Total experiments: {len(all_experiments)}")
print(f"  Winners: {len(winners)} ({len(winners)*100//max(len(all_experiments),1)}%)")
print(f"  Losers: {len(losers)} ({len(losers)*100//max(len(all_experiments),1)}%)")

# 3b. Source performance analysis (C3 fix)
def _source_stats(tag):
    exps = [e for e in all_experiments if e.get("source") == tag]
    wins = [e for e in exps if e["score"] > 0]
    rate = len(wins) / max(len(exps), 1)
    return len(wins), len(exps), rate

llm_w, llm_t, llm_rate = _source_stats("llm")
pat_w, pat_t, pat_rate = _source_stats("pattern")
gen_w, gen_t, gen_rate = _source_stats("gene")

print(f"\n  Source performance:")
print(f"    LLM:     {llm_w}/{llm_t} ({llm_rate:.0%})")
print(f"    Pattern: {pat_w}/{pat_t} ({pat_rate:.0%})")
print(f"    Gene:    {gen_w}/{gen_t} ({gen_rate:.0%})")

# 3c. Extract winning/losing word patterns
word_in_winners = {}
word_in_losers = {}
for e in winners:
    for w in e["query"].lower().split():
        if len(w) > 3:
            word_in_winners[w] = word_in_winners.get(w, 0) + 1
for e in losers:
    for w in e["query"].lower().split():
        if len(w) > 3:
            word_in_losers[w] = word_in_losers.get(w, 0) + 1

winning_words = []
losing_words = []
for w, win_count in word_in_winners.items():
    lose_count = word_in_losers.get(w, 0)
    if win_count >= 3 and win_count > lose_count * 2:
        winning_words.append((w, win_count))
for w, lose_count in word_in_losers.items():
    win_count = word_in_winners.get(w, 0)
    if lose_count >= 3 and win_count == 0:
        losing_words.append((w, lose_count))

# 3d. Write new patterns
new_patterns = []
timestamp = datetime.now().strftime("%Y-%m-%d")

if winning_words:
    top_winning = sorted(winning_words, key=lambda x: x[1], reverse=True)[:5]
    new_patterns.append({
        "pattern": f"winning_words_{timestamp}",
        "platform": "all",
        "finding": f"Words that correlate with high-scoring queries: {', '.join(w for w,c in top_winning)}",
        "impact": "Use these words when generating queries for similar topics",
        "validated": timestamp,
        "auto_generated": True,
    })

if losing_words:
    top_losing = sorted(losing_words, key=lambda x: x[1], reverse=True)[:5]
    new_patterns.append({
        "pattern": f"losing_words_{timestamp}",
        "platform": "all",
        "finding": f"Words that ONLY appear in failed queries: {', '.join(w for w,c in top_losing)}. Avoid these.",
        "impact": "These words don't produce results on any platform",
        "validated": timestamp,
        "auto_generated": True,
    })

# LLM win rate pattern (C3 fix) — only when LLM was active
if ANTHROPIC_API_KEY and llm_t > 0:
    new_patterns.append({
        "pattern": f"llm_win_rate_{timestamp}",
        "platform": "all",
        "finding": (f"LLM-suggested queries win rate: {llm_rate:.0%} ({llm_w}/{llm_t}). "
                    f"Pattern: {pat_rate:.0%} ({pat_w}/{pat_t}). "
                    f"Gene: {gen_rate:.0%} ({gen_w}/{gen_t})."),
        "impact": "Adjust LLM query quota based on performance vs other sources",
        "validated": timestamp,
        "auto_generated": True,
    })

# Overall session stats
conf_final = mad_confidence(ALL_SCORES)
new_patterns.append({
    "pattern": f"session_stats_{timestamp}",
    "platform": "all",
    "finding": (f"Session: {len(all_experiments)} queries, "
                f"{len(winners)} winners ({len(winners)*100//max(len(all_experiments),1)}%), "
                f"{len(SEEN)} unique URLs, confidence={conf_final}"),
    "impact": "Baseline for next session comparison",
    "validated": timestamp,
    "auto_generated": True,
})

# Append new patterns
with open(PATTERNS_PATH, "a") as f:
    for p in new_patterns:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"\n  NEW PATTERNS WRITTEN ({len(new_patterns)}):")
for p in new_patterns:
    print(f"    [{p['pattern']}] {p['finding'][:70]}")

# 3e. Save evolution log
with open(EVOLUTION_PATH, "a") as f:
    for e in all_experiments:
        e["session"] = timestamp
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

total_patterns = sum(1 for line in PATTERNS_PATH.read_text().splitlines() if line.strip())
print(f"\n  Total patterns in library: {total_patterns}")
print(f"  Evolution log: {EVOLUTION_PATH}")

# Write point 4: Phase 3 end
ww_str = ', '.join(w for w, c in sorted(winning_words, key=lambda x: x[1], reverse=True)[:10]) if winning_words else "None"
lw_str = ', '.join(w for w, c in sorted(losing_words, key=lambda x: x[1], reverse=True)[:10]) if losing_words else "None"
append_session_doc(
    f"## Phase 3: Post-Mortem\n\n"
    f"### Experiment Classification\n"
    f"- Total: {len(all_experiments)} | Winners: {len(winners)} "
    f"({len(winners)*100//max(len(all_experiments),1)}%) | Losers: {len(losers)}\n\n"
    f"### Source Performance\n\n"
    f"| Source | Winners | Total | Win Rate |\n"
    f"|--------|---------|-------|----------|\n"
    f"| LLM | {llm_w} | {llm_t} | {llm_rate:.0%} |\n"
    f"| Pattern | {pat_w} | {pat_t} | {pat_rate:.0%} |\n"
    f"| Gene | {gen_w} | {gen_t} | {gen_rate:.0%} |\n\n"
    f"### Winning Words\n{ww_str}\n\n"
    f"### Losing Words\n{lw_str}\n\n"
    f"### New Patterns Written\n"
    + "\n".join(f'- [{p["pattern"]}] {p["finding"][:80]}' for p in new_patterns)
    + f"\n\n### Stats\n"
    f"- Unique URLs: {len(SEEN)}\n"
    f"- MAD Confidence: {conf_final}\n"
    f"- Patterns in library: {total_patterns}\n"
)

print(f"\n{'='*60}")
print("DONE. Next run will read these patterns and start smarter.")
print(f"  Session doc: {SESSION_DOC_PATH}")
print(f"{'='*60}")
