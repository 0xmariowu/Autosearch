#!/bin/bash
# bump-version.sh — Atomically bump version in all manifest files
#
# Usage:
#   scripts/bump-version.sh          # auto: today's date as YYYY.M.D
#   scripts/bump-version.sh 2026.4.5 # explicit version
#
# Updates:
#   .claude-plugin/plugin.json    → "version": "X.Y.Z"
#   .claude-plugin/marketplace.json → metadata.version + plugins[0].version
#   CHANGELOG.md                  → moves Unreleased under new ## X.Y.Z header

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
DIM='\033[0;90m'; BOLD='\033[1m'; NC='\033[0m'

die()  { printf "${RED}error:${NC} %s\n" "$*" >&2; exit 1; }
info() { printf "${GREEN}ok:${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}warning:${NC} %s\n" "$*"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_JSON="$REPO_ROOT/.claude-plugin/plugin.json"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"
CHANGELOG="$REPO_ROOT/CHANGELOG.md"

# --- Verify files exist ---
[ -f "$PLUGIN_JSON" ]      || die "Missing $PLUGIN_JSON"
[ -f "$MARKETPLACE_JSON" ] || die "Missing $MARKETPLACE_JSON"
[ -f "$CHANGELOG" ]        || die "Missing $CHANGELOG"

# --- Get current version ---
CURRENT=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])")
printf "${DIM}current version:${NC} %s\n" "$CURRENT"

# --- Determine new version ---
if [ -n "${1:-}" ]; then
    NEW_VERSION="$1"
else
    # Auto-generate from today's date: YYYY.M.D (no zero-padding)
    YEAR=$(date +%Y)
    MONTH=$(date +%-m)
    DAY=$(date +%-d)
    NEW_VERSION="${YEAR}.${MONTH}.${DAY}"

    # If this version already exists (same-day release), append suffix
    if [ "$NEW_VERSION" = "$CURRENT" ]; then
        # Check for existing suffixed versions
        SUFFIX=1
        while git tag -l "v${NEW_VERSION}-${SUFFIX}" 2>/dev/null | grep -q .; do
            SUFFIX=$((SUFFIX + 1))
        done
        NEW_VERSION="${NEW_VERSION}-${SUFFIX}"
        warn "same-day release — using suffix: $NEW_VERSION"
    fi
fi

# --- Validate format ---
if [[ ! "$NEW_VERSION" =~ ^[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}(-[0-9]+)?$ ]]; then
    die "invalid version format: $NEW_VERSION (expected YYYY.M.D or YYYY.M.D-N)"
fi

# --- Confirm ---
printf "${BOLD}bump:${NC} %s → %s\n" "$CURRENT" "$NEW_VERSION"

# --- Update plugin.json ---
python3 -c "
import json, sys
path = '$PLUGIN_JSON'
with open(path) as f:
    data = json.load(f)
data['version'] = '$NEW_VERSION'
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
info "updated plugin.json"

# --- Update marketplace.json ---
python3 -c "
import json
path = '$MARKETPLACE_JSON'
with open(path) as f:
    data = json.load(f)
data['metadata']['version'] = '$NEW_VERSION'
for plugin in data.get('plugins', []):
    plugin['version'] = '$NEW_VERSION'
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
info "updated marketplace.json"

# --- Update CHANGELOG.md ---
# Move Unreleased content under new version header. Skip if Unreleased is empty.
python3 -c "
import re, sys

path = '$CHANGELOG'
new_ver = '$NEW_VERSION'

with open(path) as f:
    text = f.read()

# Find '## Unreleased' section
unreleased_match = re.search(r'^## Unreleased\s*$', text, re.MULTILINE)
if not unreleased_match:
    print('warning: no ## Unreleased section found in CHANGELOG.md', file=sys.stderr)
    sys.exit(0)

# Find the next ## heading or --- after Unreleased
rest = text[unreleased_match.end():]
next_heading = re.search(r'^(## |---)', rest, re.MULTILINE)
if next_heading:
    insert_pos = unreleased_match.end() + next_heading.start()
else:
    insert_pos = len(text)

# Extract content between Unreleased and next heading/separator
unreleased_content = text[unreleased_match.end():insert_pos].strip()
# Remove leading --- separator if present
unreleased_content = re.sub(r'^---\s*', '', unreleased_content).strip()

# Remove any existing ## for this version to prevent duplicates
text = re.sub(r'\n## ' + re.escape(new_ver) + r'(-\d+)?\s*\n+---\n', '\n', text)

# Rebuild: find the first real version section (## YYYY...)
text_with_unreleased = re.sub(
    r'(## Unreleased)\s*(\n---\n)?',
    r'\1\n\n---\n\n',
    text
)

# Re-locate positions after cleanup
unreleased_match = re.search(r'^## Unreleased\s*$', text_with_unreleased, re.MULTILINE)
rest = text_with_unreleased[unreleased_match.end():]
next_version = re.search(r'^## \d{4}\.', rest, re.MULTILINE)

if next_version:
    split_pos = unreleased_match.end() + next_version.start()
else:
    split_pos = len(text_with_unreleased)

# Insert new version between Unreleased and first existing version
before = text_with_unreleased[:unreleased_match.end()]
after = text_with_unreleased[split_pos:]

new_section = f'\n\n---\n\n## {new_ver}\n'
if unreleased_content:
    new_section += f'\n{unreleased_content}\n'
new_section += '\n'

result = before + new_section + after

# Clean up multiple blank lines
result = re.sub(r'\n{4,}', '\n\n\n', result)

with open(path, 'w') as f:
    f.write(result)
"
info "updated CHANGELOG.md"

# --- Summary ---
echo ""
printf "${BOLD}Version bumped to ${GREEN}%s${NC}\n" "$NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. git add .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md"
echo "  2. scripts/committer \"chore: bump version to $NEW_VERSION\" .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md"
echo "  3. git tag v$NEW_VERSION"
echo "  4. git push && git push --tags"
