#!/usr/bin/env bash
# G1-T3: Initialize experience/ directories for all channel skills.
# Creates experience/ dir + empty patterns.jsonl for channels that lack them.
# Safe to run multiple times (idempotent).

set -euo pipefail

CHANNELS_DIR="$(cd "$(dirname "$0")/../.." && pwd)/autosearch/skills/channels"

if [ ! -d "$CHANNELS_DIR" ]; then
  echo "error: channels dir not found: $CHANNELS_DIR" >&2
  exit 1
fi

created=0
skipped=0

for channel_dir in "$CHANNELS_DIR"/*/; do
  [ -d "$channel_dir" ] || continue
  channel_name=$(basename "$channel_dir")

  # Skip __pycache__ and non-channel dirs
  [[ "$channel_name" == __* ]] && continue
  [ ! -f "$channel_dir/SKILL.md" ] && continue

  exp_dir="$channel_dir/experience"
  patterns_file="$exp_dir/patterns.jsonl"

  if [ -f "$patterns_file" ]; then
    skipped=$((skipped + 1))
    continue
  fi

  mkdir -p "$exp_dir"
  touch "$patterns_file"
  echo "  initialized: $channel_name/experience/patterns.jsonl"
  created=$((created + 1))
done

total=$((created + skipped))
echo ""
echo "Done: $created created, $skipped already existed, $total total channels"
