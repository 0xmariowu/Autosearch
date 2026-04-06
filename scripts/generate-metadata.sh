#!/bin/bash
# generate-metadata.sh — Auto-generate release-metadata.json from actual directories.
# Source of truth: channels/*/search.py for channels, skills/*/SKILL.md for skills.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"
OUTPUT="$ROOT/release-metadata.json"

# Count channels (dirs with search.py, excluding _engines)
CHANNEL_DIRS=()
while IFS= read -r dir; do
    CHANNEL_DIRS+=("$(basename "$dir")")
done < <(find "$ROOT/channels" -maxdepth 2 -name "search.py" -not -path "*/_engines/*" -exec dirname {} \; | sort)

CHANNEL_COUNT=${#CHANNEL_DIRS[@]}

# Count skills (dirs with SKILL.md)
SKILL_COUNT=$(find "$ROOT/skills" -maxdepth 2 -name "SKILL.md" | wc -l | tr -d ' ')

# Read version from plugin.json
VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])")

# Generate JSON
CHANNELS_JSON=$(printf '%s\n' "${CHANNEL_DIRS[@]}" | python3 -c "
import sys, json
channels = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(channels))
")

python3 -c "
import json

data = {
    'version': '$VERSION',
    'channel_count': $CHANNEL_COUNT,
    'skill_count': $SKILL_COUNT,
    'channels': $CHANNELS_JSON
}

with open('$OUTPUT', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

echo "release-metadata.json: version=$VERSION channels=$CHANNEL_COUNT skills=$SKILL_COUNT"
