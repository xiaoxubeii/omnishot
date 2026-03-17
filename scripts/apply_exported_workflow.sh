#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
DEFAULT_EXPORT="${ROOT_DIR}/workflows/incoming/exported_api_workflow.json"

WORKFLOW_PATH="${1:-${DEFAULT_EXPORT}}"

if [[ ! -f "${WORKFLOW_PATH}" ]]; then
  echo "ERROR: workflow export not found: ${WORKFLOW_PATH}"
  echo "Put your ComfyUI 'Save (API Format)' json here or pass a path as argument."
  exit 1
fi

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/generate_bindings_from_api_json.py" \
  --workflow "${WORKFLOW_PATH}" \
  --write-template "${ROOT_DIR}/workflows/flux_product_demo.template.json" \
  --write-bindings "${ROOT_DIR}/workflows/flux_product_demo.bindings.json" \
  --print-nodes

echo
echo "Applied workflow export:"
echo "- template: ${ROOT_DIR}/workflows/flux_product_demo.template.json"
echo "- bindings: ${ROOT_DIR}/workflows/flux_product_demo.bindings.json"
