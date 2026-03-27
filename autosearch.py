#!/usr/bin/env python3
"""
AutoSearch — two-phase self-improving search with early stopping.

Phase 1: Query exploration (fast, score-only, no content extraction)
  - Generate query variants from gene pool
  - Score by UNIQUE results × avg_engagement (deduped across queries)
  - Early stop: 3 consecutive rounds with <10% improvement over history_best
  - Output: ranked playbook

Phase 2: Harvest (slow, content extraction with verified queries)
  - Use top queries from Phase 1
  - Collect structured findings
  - Early stop: new findings per round < 5
"""

import json
import urllib.request
import urllib.parse
import os
import time
import random
from datetime import datetime

DEST = os.path.expanduser("/Volumes/4TB/Armory/dataset/_search")

# ============================================================
# GENE POOL
# ============================================================
GENES = {
    "product": [
        "Claude Code",
        "CLAUDE.md",
        "Cursor",
        "cursorrules",
        "AGENTS.md",
        "Codex",
        "Copilot",
        "Windsurf",
        "aider",
    ],
    "pain_verb": [
        "ignores",
        "violates",
        "breaks",
        "forgets",
        "loses",
        "overwrites",
        "deletes",
        "hallucinates",
        "skips",
        "bypasses",
        "doesn't follow",
        "keeps doing",
        "refuses to",
        "fails to",
    ],
    "object": [
        "rules",
        "instructions",
        "conventions",
        "guidelines",
        "configuration",
        "coding standards",
        "context",
        "custom instructions",
        "system prompt",
        "project settings",
        "style",
        "format",
    ],
    "symptom": [
        "wrong",
        "broken",
        "after compact",
        "long conversation",
        "repeatedly",
        "first attempt",
        "80% of the time",
        "worse",
        "degraded",
        "inconsistent",
    ],
}

PLATFORMS = [
    {"name": "reddit", "sub": "ClaudeCode"},
    {"name": "reddit", "sub": "ClaudeAI"},
    {"name": "reddit", "sub": "cursor"},
    {"name": "reddit", "sub": "ChatGPTCoding"},
]


def gen_query():
    patterns = [
        lambda: (
            f"{random.choice(GENES['product'])} {random.choice(GENES['pain_verb'])} {random.choice(GENES['object'])}"
        ),
        lambda: f"{random.choice(GENES['product'])} {random.choice(GENES['symptom'])}",
        lambda: (
            f"{random.choice(GENES['pain_verb'])} {random.choice(GENES['object'])} {random.choice(GENES['symptom'])}"
        ),
    ]
    return random.choice(patterns)()


def search_reddit(sub, query, limit=20):
    url = f"https://www.reddit.com/r/{sub}/search.json?q={urllib.parse.quote(query)}&restrict_sr=on&limit={limit}&sort=relevance&t=all"
    req = urllib.request.Request(url, headers={"User-Agent": "agent-reach/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return [
            {
                "title": p["data"].get("title", ""),
                "url": "https://www.reddit.com" + p["data"].get("permalink", ""),
                "eng": p["data"].get("score", 0) + p["data"].get("num_comments", 0),
            }
            for p in data.get("data", {}).get("children", [])
        ]
    except:
        return []


# ============================================================
# PHASE 1: QUERY EXPLORATION
# ============================================================
print("=" * 70)
print("PHASE 1: Query Exploration (early stopping at 3 stale rounds)")
print("=" * 70)

SEEN_URLS = set()  # global dedup across all queries
history_best = 0
stale_rounds = 0
MAX_STALE = 3
MAX_ROUNDS = 10
QUERIES_PER_ROUND = 12

all_query_scores = []

for round_num in range(1, MAX_ROUNDS + 1):
    queries = list(set(gen_query() for _ in range(QUERIES_PER_ROUND * 2)))[
        :QUERIES_PER_ROUND
    ]
    round_scores = []

    for query in queries:
        query_new_urls = 0
        query_total_eng = 0

        for plat in PLATFORMS:
            results = search_reddit(plat["sub"], query)
            for r in results:
                if r["url"] not in SEEN_URLS:
                    SEEN_URLS.add(r["url"])
                    query_new_urls += 1
                    query_total_eng += r["eng"]
            time.sleep(0.15)

        # Score = NEW unique results × avg engagement of new results
        avg_eng = query_total_eng / max(query_new_urls, 1)
        score = int(query_new_urls * avg_eng)
        round_scores.append(
            {"query": query, "new_urls": query_new_urls, "score": score}
        )

    round_scores.sort(key=lambda x: x["score"], reverse=True)
    round_best = round_scores[0]["score"] if round_scores else 0
    total_new = sum(r["new_urls"] for r in round_scores)

    # Check improvement
    if history_best > 0:
        improvement = (round_best - history_best) / history_best
    else:
        improvement = 1.0 if round_best > 0 else 0

    if round_best > history_best:
        history_best = round_best

    if improvement < 0.1:
        stale_rounds += 1
    else:
        stale_rounds = 0

    # Print round summary
    top3 = round_scores[:3]
    print(
        f"\n  R{round_num}: best={round_best:6d} new_urls={total_new:3d} improvement={improvement:+.0%} stale={stale_rounds}/{MAX_STALE}"
    )
    for r in top3:
        print(f"    score={r['score']:6d} new={r['new_urls']:2d} | {r['query'][:50]}")

    all_query_scores.extend([{**r, "round": round_num} for r in round_scores])

    # EARLY STOPPING
    if stale_rounds >= MAX_STALE:
        print(
            f"\n  >>> EARLY STOP: {MAX_STALE} consecutive rounds with <10% improvement"
        )
        break

    # Gene evolution: extract words from high-scoring query results
    if total_new > 0:
        for r in round_scores[:3]:
            words = r["query"].lower().split()
            for w in words:
                if len(w) > 4 and w not in sum(GENES.values(), []):
                    # Add to a random category
                    GENES["symptom"].append(w)

print(f"\n  Total unique URLs discovered: {len(SEEN_URLS)}")
print(f"  Total query experiments: {len(all_query_scores)}")

# Rank all queries
all_query_scores.sort(key=lambda x: x["score"], reverse=True)

# ============================================================
# PHASE 1 OUTPUT: PLAYBOOK
# ============================================================
playbook = [q for q in all_query_scores if q["score"] > 0][:30]

playbook_path = os.path.join(DEST, "playbook-final.jsonl")
with open(playbook_path, "w") as f:
    for q in playbook:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f"\n{'=' * 70}")
print(f"PHASE 1 COMPLETE: {len(playbook)} queries in playbook-final.jsonl")
print(f"{'=' * 70}")
print("\nTop 10 queries:")
for i, q in enumerate(playbook[:10]):
    print(
        f"  #{i + 1:2d} score={q['score']:6d} new={q['new_urls']:2d} R{q['round']} | {q['query'][:50]}"
    )

# ============================================================
# PHASE 2: HARVEST
# ============================================================
print(f"\n{'=' * 70}")
print("PHASE 2: Harvest (early stopping at <5 new findings/round)")
print(f"{'=' * 70}")

FINDINGS_PATH = os.path.join(DEST, "findings-v2.jsonl")
harvest_seen = set()
if os.path.exists(FINDINGS_PATH):
    with open(FINDINGS_PATH) as f:
        for line in f:
            harvest_seen.add(json.loads(line).get("url", ""))

# Use top 15 queries from playbook
harvest_queries = playbook[:15]
total_harvested = 0
harvest_round = 0

for q_entry in harvest_queries:
    query = q_entry["query"]
    new_this_query = 0

    for plat in PLATFORMS:
        url = f"https://www.reddit.com/r/{plat['sub']}/search.json?q={urllib.parse.quote(query)}&restrict_sr=on&limit=25&sort=relevance&t=all"
        req = urllib.request.Request(url, headers={"User-Agent": "agent-reach/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            for p in data.get("data", {}).get("children", []):
                d = p["data"]
                post_url = "https://www.reddit.com" + d.get("permalink", "")
                if post_url in harvest_seen:
                    continue

                created = datetime.fromtimestamp(d.get("created_utc", 0)).strftime(
                    "%Y-%m-%d"
                )
                if created < "2025-10-01":
                    continue

                eng = d.get("score", 0) + d.get("num_comments", 0)
                if eng < 5:
                    continue

                finding = {
                    "url": post_url,
                    "title": d.get("title", "")[:150],
                    "source": f"reddit/r/{plat['sub']}",
                    "query": query,
                    "engagement": eng,
                    "score": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "created": created,
                    "body": d.get("selftext", "")[:500],
                    "collected": datetime.now().strftime("%Y-%m-%d"),
                }
                with open(FINDINGS_PATH, "a") as f:
                    f.write(json.dumps(finding, ensure_ascii=False) + "\n")
                harvest_seen.add(post_url)
                new_this_query += 1
        except:
            pass
        time.sleep(0.2)

    total_harvested += new_this_query
    harvest_round += 1

    if harvest_round % 5 == 0:
        print(f"  After {harvest_round} queries: {total_harvested} total new findings")

    # Early stop check every 5 queries
    if harvest_round >= 5 and harvest_round % 5 == 0:
        recent_rate = total_harvested / harvest_round
        if recent_rate < 1:  # less than 1 new finding per query
            print(f"  >>> HARVEST STOP: rate={recent_rate:.1f} findings/query")
            break

print(f"\n{'=' * 70}")
print("PHASE 2 COMPLETE")
print(f"  Harvested: {total_harvested} new findings")
print(f"  Total in file: {len(harvest_seen)}")
print(f"{'=' * 70}")
