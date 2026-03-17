#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_DIR="${ROOT_DIR}/ComfyUI"
INPUT_DIR="${ROOT_DIR}/data/comfy-input"
OUTPUT_DIR="${ROOT_DIR}/data/comfy-output"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

mkdir -p "${INPUT_DIR}" "${OUTPUT_DIR}"

extra_args=()
if [[ -n "${COMFYUI_EXTRA_ARGS:-}" ]]; then
  read -r -a extra_args <<< "${COMFYUI_EXTRA_ARGS}"
fi

exec "${PYTHON_BIN}" "${COMFY_DIR}/main.py" \
  --listen "${COMFYUI_LISTEN:-127.0.0.1}" \
  --port "${COMFYUI_PORT:-8188}" \
  --input-directory "${INPUT_DIR}" \
  --output-directory "${OUTPUT_DIR}" \
  "${extra_args[@]}" \
  "$@"
