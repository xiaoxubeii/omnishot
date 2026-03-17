#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIP_BIN="${ROOT_DIR}/.venv/bin/pip"
TORCH_VERSION="${TORCH_VERSION:-2.5.1}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.20.1}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.5.1}"
PYTORCH_INDEX_URL="${PYTORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
INSTALL_COMFYUI_FULL_REQUIREMENTS="${INSTALL_COMFYUI_FULL_REQUIREMENTS:-false}"
COMFYUI_DIR="${ROOT_DIR}/ComfyUI"

if [[ ! -d "${COMFYUI_DIR}" || ! -f "${COMFYUI_DIR}/main.py" ]]; then
  git -C "${ROOT_DIR}" submodule update --init --recursive ComfyUI
fi

"${PIP_BIN}" uninstall -y torch torchvision torchaudio || true
"${PIP_BIN}" install \
  "torch==${TORCH_VERSION}" \
  "torchvision==${TORCHVISION_VERSION}" \
  "torchaudio==${TORCHAUDIO_VERSION}" \
  --index-url "${PYTORCH_INDEX_URL}"

"${PIP_BIN}" install \
  aiohttp \
  requests \
  tqdm \
  einops \
  comfyui-frontend-package==1.41.20 \
  comfy-aimdo>=0.2.12 \
  safetensors \
  scipy \
  psutil \
  alembic \
  SQLAlchemy \
  av \
  comfy-kitchen \
  simpleeval \
  blake3 \
  kornia \
  spandrel \
  PyOpenGL \
  glfw \
  torchsde \
  tokenizers \
  sentencepiece \
  transformers

if [[ "${INSTALL_COMFYUI_FULL_REQUIREMENTS}" == "true" ]]; then
  "${PIP_BIN}" install -r "${COMFYUI_DIR}/requirements.txt"
fi
