#!/usr/bin/env bash
# Start a local SearXNG instance for the autosearch searxng channel.
# Usage: bash scripts/dev/start-searxng.sh [--dry-run] [--port 8080]
set -euo pipefail

PORT=8080
DRY_RUN=false
CONTAINER_NAME="autosearch-searxng"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --port) shift; PORT="$1" ;;
    --port=*) PORT="${arg#*=}" ;;
  esac
done

if ! command -v docker &>/dev/null; then
  echo "error: Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop/" >&2
  exit 1
fi

CMD="docker run -d \
  --name $CONTAINER_NAME \
  --rm \
  -p ${PORT}:8080 \
  -e SEARXNG_BASE_URL=http://localhost:${PORT} \
  docker.io/searxng/searxng:latest"

if $DRY_RUN; then
  echo "[dry-run] would run:"
  echo "  $CMD"
  echo ""
  echo "After start, set:"
  echo "  export SEARXNG_URL=http://localhost:${PORT}"
  exit 0
fi

# Stop existing container if running
if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
  echo "Stopping existing $CONTAINER_NAME..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
fi

echo "Starting SearXNG on port $PORT..."
eval "$CMD"

echo ""
echo "SearXNG started. Set the following environment variable:"
echo ""
echo "  export SEARXNG_URL=http://localhost:${PORT}"
echo ""
echo "Or add to ~/.config/ai-secrets.env:"
echo "  SEARXNG_URL=http://localhost:${PORT}"
echo ""
echo "To stop: docker stop $CONTAINER_NAME"
