#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec "${ROOT_DIR}/scripts/start_mcp_server.sh" \
  --transport streamable-http \
  --host "${HOST:-0.0.0.0}" \
  --port "${MCP_PORT:-8765}" \
  --streamable-http-path "${MCP_PATH:-/mcp}" \
  --api-base-url "${OMNISHOT_API_BASE_URL:-http://127.0.0.1:${PORT:-8000}}" \
  "$@"
