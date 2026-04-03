"""Search program — the ONE file the AI modifies.

This is the train.py equivalent. Everything here is fair game for the AI
to change: queries, providers, strategy. The AI reads this file, modifies
it, runs prepare.py, and checks if the score improved.

Rules:
- Each query should target specific keywords from the goal case dimensions.
- Keep queries that produce keyword hits, discard ones that don't.
- The AI should read results.tsv to avoid repeating failed strategies.
"""

# Which goal case to optimize
GOAL_CASE = "atoms-auto-mining-perfect"

# Queries — the core action space. AI adds/removes/modifies these.
QUERIES = [
    "code review dataset original revised code direct conversion",
    "review comment dataset with original and revised code pairs",
    "ReviewComments dataset actionability of code review feedback",
    "separate extraction from validation and labeling in data pipelines",
    "great expectations pandera data validation quality gate",
    "schema validation as a post-extraction quality layer",
    "pair success and failure trajectories on the same swe-bench instance",
    "swe-bench resolved and unresolved trajectory instances",
    "swe-bench trajectories with resolved and unresolved runs",
    "post-run validation report and fail-closed release gate",
    "data contract validation report before release gate",
    "smoke test fail-closed release validation",
    "semantic deduplication and fake-Gold detection for near-duplicate code pairs",
    "near duplicate detection and fake gold filtering",
    "duplicate detection similarity matching dedup pipeline",
]

# Providers — which search backends to use
PROVIDERS = [
    "searxng",
    "ddgs",
    "github_repos",
    "github_issues",
    "github_code",
    "huggingface_datasets",
]

# Max results per query per provider
PER_QUERY_CAP = 5
