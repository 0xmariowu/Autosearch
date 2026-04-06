#!/bin/bash
# bump-version.sh — Atomically bump version in all manifest files
#
# Format: YYYY.MM.DD.N (CalVer with zero-padded month/day + daily sequence)
#   2026.04.04.1 = April 4, first release
#   2026.04.04.2 = April 4, second release
#   2026.04.05.1 = April 5, first release
#
# Usage:
#   scripts/bump-version.sh              # auto: today + next sequence number
#   scripts/bump-version.sh 2026.04.05.1 # explicit version
#
# Updates:
#   .claude-plugin/plugin.json    → "version"
#   .claude-plugin/marketplace.json → metadata.version + plugins[0].version
#   CHANGELOG.md                  → moves Unreleased under new ## header

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
DIM='\033[0;90m'; BOLD='\033[1m'; NC='\033[0m'

die()  { printf "${RED}error:${NC} %s\n" "$*" >&2; exit 1; }
info() { printf "${GREEN}ok:${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}warning:${NC} %s\n" "$*"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_JSON="$REPO_ROOT/.claude-plugin/plugin.json"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"
NPM_PKG="$REPO_ROOT/npm/package.json"
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
    # Auto-generate: YYYY.MM.DD.N
    TODAY=$(date +%Y.%m.%d)

    # Find next sequence number for today
    SEQ=1
    while git tag -l "v${TODAY}.${SEQ}" 2>/dev/null | grep -q .; do
        SEQ=$((SEQ + 1))
    done
    # Also check if current version is today's — increment from there
    if [[ "$CURRENT" == "${TODAY}."* ]]; then
        CURRENT_SEQ="${CURRENT##*.}"
        if [ "$CURRENT_SEQ" -ge "$SEQ" ] 2>/dev/null; then
            SEQ=$((CURRENT_SEQ + 1))
        fi
    fi
    NEW_VERSION="${TODAY}.${SEQ}"
fi

# --- Validate format ---
if [[ ! "$NEW_VERSION" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+$ ]]; then
    die "invalid version format: $NEW_VERSION (expected YYYY.MM.DD.N)"
fi

# --- Confirm ---
printf "${BOLD}bump:${NC} %s → %s\n" "$CURRENT" "$NEW_VERSION"

# --- Update plugin.json ---
python3 -c "
import json
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

# --- Update npm/package.json ---
if [ -f "$NPM_PKG" ]; then
    python3 -c "
import json
path = '$NPM_PKG'
with open(path) as f:
    data = json.load(f)
data['version'] = '$NEW_VERSION'
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
    info "updated npm/package.json"
fi

# --- Update CHANGELOG.md ---
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
unreleased_content = re.sub(r'^---\s*', '', unreleased_content).strip()

# Rebuild
text_with_unreleased = re.sub(
    r'(## Unreleased)\s*(\n---\n)?',
    r'\1\n\n---\n\n',
    text
)

unreleased_match = re.search(r'^## Unreleased\s*$', text_with_unreleased, re.MULTILINE)
rest = text_with_unreleased[unreleased_match.end():]
next_version = re.search(r'^## \d{4}\.', rest, re.MULTILINE)

if next_version:
    split_pos = unreleased_match.end() + next_version.start()
else:
    split_pos = len(text_with_unreleased)

before = text_with_unreleased[:unreleased_match.end()]
after = text_with_unreleased[split_pos:]

new_section = f'\n\n---\n\n## {new_ver}\n'
if unreleased_content:
    new_section += f'\n{unreleased_content}\n'
new_section += '\n'

result = before + new_section + after
result = re.sub(r'\n{4,}', '\n\n\n', result)

with open(path, 'w') as f:
    f.write(result)
"
info "updated CHANGELOG.md"

# --- Sync CHANGELOG.md → docs/changelog.mdx ---
DOCS_CHANGELOG="$REPO_ROOT/docs/changelog.mdx"
if [ -f "$DOCS_CHANGELOG" ]; then
    {
        echo '---'
        echo 'title: Changelog'
        echo 'description: All changes to AutoSearch, organized by release.'
        echo '---'
        echo ''
        tail -n +2 "$CHANGELOG" | sed '/./,$!d'
    } > "$DOCS_CHANGELOG"
    info "synced docs/changelog.mdx"
fi

# --- Refresh release-metadata.json and sync counts ---
"$REPO_ROOT/scripts/generate-metadata.sh"
CHANNEL_COUNT=$(python3 -c "import json; print(json.load(open('$REPO_ROOT/release-metadata.json'))['channel_count'])")
SKILL_COUNT=$(python3 -c "import json; print(json.load(open('$REPO_ROOT/release-metadata.json'))['skill_count'])")

# Sync channel/skill counts across all docs and README
# Pattern-based sed: only replace numbers in known contexts, not blindly
for f in \
    "$REPO_ROOT/README.md" \
    "$REPO_ROOT/npm/README.md" \
    "$REPO_ROOT/docs/introduction.mdx" \
    "$REPO_ROOT/docs/channels.mdx" \
    "$REPO_ROOT/docs/quickstart.mdx" \
    "$REPO_ROOT/docs/architecture.mdx" \
    "$REPO_ROOT/docs/skills.mdx"; do
    [ -f "$f" ] || continue
    # Channel count patterns
    sed -i '' -E "s/[0-9]+ search channels/${CHANNEL_COUNT} search channels/g" "$f"
    sed -i '' -E "s/[0-9]+ dedicated (connectors|channels)/${CHANNEL_COUNT} dedicated \1/g" "$f"
    sed -i '' -E "s/[0-9]+ channel plugins/${CHANNEL_COUNT} channel plugins/g" "$f"
    sed -i '' -E "s/channels-[0-9]+-green/channels-${CHANNEL_COUNT}-green/g" "$f"
    sed -i '' -E "s/has [0-9]+ dedicated/has ${CHANNEL_COUNT} dedicated/g" "$f"
    sed -i '' -E "s/All [0-9]+ (search )?channels/All ${CHANNEL_COUNT} \1channels/g" "$f"
    sed -i '' -E "s/[0-9]+ channels\./34 channels./g" "$f"
    # Skill count patterns
    sed -i '' -E "s/[0-9]+ (evolvable )?skills/${SKILL_COUNT} \1skills/g" "$f"
done
info "synced channel ($CHANNEL_COUNT) and skill ($SKILL_COUNT) counts"

# --- Summary ---
echo ""
printf "${BOLD}Version bumped to ${GREEN}%s${NC}\n" "$NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Review docs/ — add content for new features if needed"
echo "  2. git add .claude-plugin/ npm/package.json CHANGELOG.md docs/ README.md release-metadata.json"
echo "  3. scripts/committer \"chore: bump version to $NEW_VERSION\" .claude-plugin/plugin.json .claude-plugin/marketplace.json npm/package.json CHANGELOG.md docs/changelog.mdx release-metadata.json README.md"
echo "  4. git tag v$NEW_VERSION"
echo "  5. git push && git push --tags"
