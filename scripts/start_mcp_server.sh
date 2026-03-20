#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

cd "${ROOT_DIR}"

# Default to HTTP MCP for remote deployments when no explicit args are provided.
# Callers can still override by passing explicit flags, e.g.:
#   ./scripts/start_mcp_server.sh --transport stdio
if [[ "$#" -eq 0 ]]; then
  set -- \
    --transport "${OMNISHOT_MCP_TRANSPORT:-streamable-http}" \
    --host "${OMNISHOT_MCP_HOST:-0.0.0.0}" \
    --port "${OMNISHOT_MCP_PORT:-8765}" \
    --streamable-http-path "${OMNISHOT_MCP_PATH:-/mcp}" \
    --api-base-url "${OMNISHOT_API_BASE_URL:-http://127.0.0.1:${PORT:-8000}}"
fi

exec "${PYTHON_BIN}" -m app.mcp_server "$@"
