#!/usr/bin/env bash
# scripts/bump-version.sh — bump autosearch version across files
#
# Version scheme: CalVer YYYY.MM.DD.N (e.g. 2026.04.21.1).
#   - N is the daily sequence number (1, 2, 3...) within the same calendar day.
#   - Auto-computed if not passed as argument.
#
# Updates (when files exist):
#   - pyproject.toml         (version = "...")
#   - .claude-plugin/plugin.json         (JSON "version")
#   - .claude-plugin/marketplace.json    (JSON "version", metadata.version, plugins[0].version)
#   - CHANGELOG.md                        (prepend empty entry if missing)
#
# Usage:
#   scripts/bump-version.sh                      # auto-bump to today's version
#   scripts/bump-version.sh 2026.04.21.1         # explicit version

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

today="$(date -u +%Y.%m.%d)"

if [ -n "${1:-}" ]; then
  new_version="$1"
else
  current=""
  if [ -f pyproject.toml ]; then
    current=$(grep -E '^version\s*=\s*"' pyproject.toml | head -1 | sed -E 's/.*"(.*)".*/\1/')
  fi
  next_seq=1
  if [[ "$current" =~ ^${today}\.([0-9]+)$ ]]; then
    next_seq=$((${BASH_REMATCH[1]} + 1))
  fi
  new_version="${today}.${next_seq}"
  head_commit=$(git rev-parse HEAD 2>/dev/null || true)
  while git show-ref --tags --verify --quiet "refs/tags/v${new_version}"; do
    tag_commit=$(git rev-list -n 1 "v${new_version}" 2>/dev/null || true)
    if [ -n "$head_commit" ] && [ "$tag_commit" = "$head_commit" ]; then
      break
    fi
    next_seq=$((next_seq + 1))
    if [ "$next_seq" -gt 99 ]; then
      echo "ERROR: no unclaimed ${today}.N version found before ${today}.99" >&2
      exit 1
    fi
    new_version="${today}.${next_seq}"
  done
fi

echo "Bumping to $new_version"

update_pyproject() {
  [ -f pyproject.toml ] || return 0
  python3 - "$new_version" <<'PY'
import re, sys
new_version = sys.argv[1]
path = 'pyproject.toml'
content = open(path).read()
content = re.sub(r'^(version\s*=\s*)"[^"]*"', rf'\1"{new_version}"', content, count=1, flags=re.M)
open(path, 'w').write(content)
PY
  echo "  updated pyproject.toml"
}

update_json_version() {
  local path="$1"
  [ -f "$path" ] || return 0
  python3 - "$path" "$new_version" <<'PY'
import json, sys
path, new_version = sys.argv[1], sys.argv[2]
with open(path) as f: d = json.load(f)
d['version'] = new_version
if path == '.claude-plugin/marketplace.json':
    d.setdefault('metadata', {})['version'] = new_version
    plugins = d.setdefault('plugins', [])
    if not plugins:
        plugins.append({})
    plugins[0]['version'] = new_version
with open(path, 'w') as f: json.dump(d, f, indent=2, ensure_ascii=False); f.write('\n')
PY
  echo "  updated $path"
}

ensure_changelog_entry() {
  [ -f CHANGELOG.md ] || { echo "# Changelog" > CHANGELOG.md; echo "" >> CHANGELOG.md; }
  if ! grep -q "## $new_version" CHANGELOG.md; then
    python3 - "$new_version" <<'PY'
from datetime import date
import sys
new_version = sys.argv[1]
path = 'CHANGELOG.md'
content = open(path).read()
banner = content.split('\n', 1)[0] if content.startswith('# ') else '# Changelog'
rest = content[len(banner)+1:] if content.startswith('# ') else content
entry = f'\n## {new_version} — {date.today().isoformat()}\n\n- \n'
open(path, 'w').write(banner + '\n' + entry + rest)
PY
    echo "  prepended CHANGELOG.md entry (fill in the bullet)"
  fi
}

update_npm_package_version() {
  local path="npm/package.json"
  [ -f "$path" ] || return 0
  python3 - "$path" "$new_version" <<'PY'
import json, sys
path, py_version = sys.argv[1], sys.argv[2]
parts = py_version.split('.')
if len(parts) != 4:
    raise SystemExit(f"unexpected pyproject version shape: {py_version}")
year, month, day, _seq = parts
npm_version = f"{int(year)}.{int(month)}.{int(day)}"
with open(path) as f: d = json.load(f)
if d.get('version') == npm_version:
    raise SystemExit(0)
d['version'] = npm_version
with open(path, 'w') as f: json.dump(d, f, indent=2, ensure_ascii=False); f.write('\n')
print(npm_version)
PY
  echo "  updated $path (derived from $new_version)"
}

update_pyproject
update_json_version .claude-plugin/plugin.json
update_json_version .claude-plugin/marketplace.json
update_npm_package_version
ensure_changelog_entry

echo "Done. Review diff before committing:"
echo "  git diff pyproject.toml .claude-plugin/ npm/package.json CHANGELOG.md"
