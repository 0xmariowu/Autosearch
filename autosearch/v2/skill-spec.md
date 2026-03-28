# AutoSearch v2 Skill Specification
AutoSearch v2 skills are executable Markdown contracts. A skill is valid only if an agent can read the file, follow it literally, and produce the declared output with no hidden context beyond the listed CLI tools.
## Scope
- Every skill is one Markdown file with YAML frontmatter followed by ordered body sections.
- Skill files live at `skills/platforms/<name>.md`, `skills/strategies/<name>.md`, or `skills/avo/<name>.md`.
- The filename SHOULD match the frontmatter `name`.
- `name` MUST be unique across `autosearch/v2/skills/`.
- Behaviorally significant edits require a `version` bump. AVO MUST do this when it evolves a skill.
- Unknown frontmatter keys are forbidden except `x-*` extension keys, which consumers MUST ignore.
## Runtime Conventions
- Commands MUST be non-interactive.
- Every command block MUST use the `bash` fence.
- A skill MAY read `QUERY`, `LIMIT`, `OUT`, `SINCE`, and `NOW`, but every variable it uses MUST be given a meaning and a safe default in `Execute`.
- Result-producing skills SHOULD write final JSONL to `$OUT`; if `$OUT` is unset, they MUST define a default path.
- Temporary files are allowed, but the final artifact path MUST be explicit.
## YAML Frontmatter
Every skill MUST start with:
```yaml
---
name: skill-name
type: platform | strategy | avo
version: "1.0"
requires: [gh, curl, ...]
triggers: [keyword1, ...]
cost: free | low | medium
platforms: [github, ...]
dimensions: [relevance, freshness, ...]
---
```
Rules:
- `name`: required, lowercase kebab-case.
- `type`: required, one of `platform`, `strategy`, `avo`.
- `version`: required quoted semantic version string such as `"1.0"` or `"1.1"`.
- `requires`: required array of executable names; use `[]` when none are needed.
- `triggers`: required array of lowercase keywords or short phrases.
- `cost`: required enum describing marginal invocation cost.
- `platforms`: required and non-empty only for `type: platform`; otherwise use `[]`.
- `dimensions`: required and non-empty only for `type: strategy`; use exact `judge.py` dimension names when applicable; otherwise use `[]`.
## Required Body Sections
The body MUST contain these level-2 headings in this exact order:
1. `## Purpose`
2. `## When to Use`
3. `## Execute`
4. `## Parse`
5. `## Score Hints`
6. `## Known Limitations`
7. `## Evolution Notes`
Section rules:
- `Purpose`: exactly one sentence stating what the skill does and when to select it.
- `When to Use`: trigger conditions, prerequisites, and exclusions; short bullets preferred.
- `Execute`: numbered steps only; every step that does work includes a `bash` block; commands must be copy-pastable and concrete.
- `Parse`: define the emitted artifact and exact schema.
- `Score Hints`: describe quality signals; these guide ranking and diagnosis but do not replace `judge.py`.
- `Known Limitations`: state failure modes, rate limits, blind spots, and what to do on zero or malformed results.
- `Evolution Notes`: for AVO only; record tunable parameters, prior attempts, and next experiments. Prefer bullet prefixes `Tune:`, `Tried:`, and `Next:`.
## Parse Contract
Every skill that produces search results MUST emit UTF-8 JSONL with one JSON object per line and no outer array. Each result object MUST contain at least:
```json
{"url":"...","title":"...","source":"platform-name","snippet":"...","found_at":"ISO8601","query":"the query used","metadata":{}}
```
Field semantics are fixed:
- `url`: canonical absolute URL for the result.
- `title`: non-empty human-readable title.
- `source`: lowercase platform identifier such as `github`, `reddit`, or `hackernews`.
- `snippet`: short evidence text; use `""` if unavailable.
- `found_at`: timestamp when the skill found the result, in ISO 8601 UTC.
- `query`: exact query string used to fetch the result.
- `metadata`: platform-specific object for publish dates, scores, stars, comments, language, author, IDs, and similar extra signals.
If a strategy or AVO skill does not produce search results, `Parse` MUST define its output artifact and exact JSON schema instead.
## Scoring Guidance
- Platform and strategy skills SHOULD map their hints to `quantity`, `diversity`, `relevance`, `freshness`, and `efficiency` whenever possible.
- Extra signals not scored directly by `judge.py` MAY still appear in `metadata` and `Score Hints` if they help ranking, diagnosis, or later evolution.
## Example Skill
This example is complete and conforms to the spec.
````md
---
name: hackernews-minimal
type: platform
version: "1.0"
requires: [curl, python3]
triggers: [hackernews, hn, show hn, launch]
cost: free
platforms: [hackernews]
dimensions: []
---
## Purpose
Search Hacker News stories for a query when developer discussion and launch feedback are likely to matter.
## When to Use
- Use when the task mentions Hacker News directly or when community reaction is valuable.
- Prefer this skill for early tool discovery, launch feedback, and developer pain points.
- Do not use it as the only source for official facts or freshness-sensitive claims.
## Execute
1. Define inputs and paths.
```bash
QUERY="${QUERY:-ai agent}"
LIMIT="${LIMIT:-10}"
OUT="${OUT:-/tmp/hackernews-minimal.jsonl}"
RAW="$(mktemp)"
export QUERY LIMIT OUT RAW
```
2. Fetch matching stories from the public Algolia API.
```bash
curl -sG 'https://hn.algolia.com/api/v1/search' \
  --data-urlencode "query=$QUERY" \
  --data-urlencode "tags=story" \
  --data-urlencode "hitsPerPage=$LIMIT" \
  > "$RAW"
```
3. Convert the response into AutoSearch JSONL.
```bash
python3 -c 'import datetime,json,os;data=json.load(open(os.environ["RAW"]));now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z");query=os.environ["QUERY"];out=open(os.environ["OUT"],"w",encoding="utf-8"); \
for hit in data.get("hits",[]): url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get(\"objectID\")}"; row={"url":url,"title":hit.get("title") or hit.get("story_title") or url,"source":"hackernews","snippet":hit.get("story_text") or "","found_at":now,"query":query,"metadata":{"hn_id":hit.get("objectID"),"points":hit.get("points",0),"num_comments":hit.get("num_comments",0),"author":hit.get("author"),"published_at":hit.get("created_at")}}; print(json.dumps(row, ensure_ascii=False), file=out); \
out.close()'
```
## Parse
Write JSONL to `$OUT`. Each line uses the base schema and adds `hn_id`, `points`, `num_comments`, `author`, and `published_at` in `metadata`.
## Score Hints
- `relevance`: title contains the exact topic or product terms from `QUERY`.
- `freshness`: recent `published_at` is stronger for fast-moving topics.
- `efficiency`: multiple relevant hits from one query suggest strong query-platform fit.
- Extra signal: high `points` and `num_comments` often indicate valuable discussion.
## Known Limitations
- Coverage is biased toward technical and startup communities.
- Some hits have no outbound URL; the HN discussion URL is still valid but less informative.
- Very broad queries can return noisy results.
## Evolution Notes
- Tune: `tags`, quoting, and result count.
- Tried: story-only search to avoid comment noise.
- Next: add a comment-search variant when discussion detail matters more than linked pages.
````
