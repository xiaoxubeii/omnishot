#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_DIR="${ROOT_DIR}/ComfyUI"
INPUT_DIR="${ROOT_DIR}/data/comfy-input"
OUTPUT_DIR="${ROOT_DIR}/data/comfy-output"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
HF_CACHE_DIR="${HF_HOME:-${HOME}/.cache/huggingface}"

mkdir -p "${INPUT_DIR}" "${OUTPUT_DIR}"

export HF_HOME="${HF_CACHE_DIR}"
export HF_HUB_CACHE="${HF_CACHE_DIR}/hub"
export TRANSFORMERS_CACHE="${HF_CACHE_DIR}/hub"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_ENABLE_HF_TRANSFER=0
# DepthAnything and similar preprocessors are already cached locally; forcing
# offline mode avoids slow HEAD retries against huggingface.co during startup
# and first inference.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

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
