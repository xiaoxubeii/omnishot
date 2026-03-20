#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
HF_HOME="${HF_HOME:-${ROOT_DIR}/data/hf-cache}"
DOWNLOAD_BASE_MODEL="${DOWNLOAD_BASE_MODEL:-true}"
DOWNLOAD_LIGHTNING="${DOWNLOAD_LIGHTNING:-false}"
DOWNLOAD_ANGLE_LORA="${DOWNLOAD_ANGLE_LORA:-false}"
QWEN_EDIT_MODEL_ID="${QWEN_EDIT_MODEL_ID:-Qwen/Qwen-Image-Edit-2511}"
QWEN_EDIT_LIGHTNING_REPO="${QWEN_EDIT_LIGHTNING_REPO:-lightx2v/Qwen-Image-Lightning}"
QWEN_EDIT_LIGHTNING_FILENAME="${QWEN_EDIT_LIGHTNING_FILENAME:-Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors}"
QWEN_EDIT_ANGLE_REPO="${QWEN_EDIT_ANGLE_REPO:-dx8152/Qwen-Edit-2509-Multiple-angles}"
QWEN_EDIT_ANGLE_FILENAME="${QWEN_EDIT_ANGLE_FILENAME:-镜头转换.safetensors}"

mkdir -p "${HF_HOME}"

export HF_ENDPOINT
export HF_HOME
export HF_HUB_CACHE="${HF_HOME}"
export HF_HUB_ENABLE_HF_TRANSFER=0
export DOWNLOAD_BASE_MODEL
export DOWNLOAD_LIGHTNING
export DOWNLOAD_ANGLE_LORA
export QWEN_EDIT_MODEL_ID
export QWEN_EDIT_LIGHTNING_REPO
export QWEN_EDIT_LIGHTNING_FILENAME
export QWEN_EDIT_ANGLE_REPO
export QWEN_EDIT_ANGLE_FILENAME

echo "HF_ENDPOINT=${HF_ENDPOINT}"
echo "HF_HOME=${HF_HOME}"

"${PYTHON_BIN}" - <<'PY'
import os

from huggingface_hub import hf_hub_download, snapshot_download

download_base = os.environ.get("DOWNLOAD_BASE_MODEL", "true").lower() == "true"
download_lightning = os.environ.get("DOWNLOAD_LIGHTNING", "false").lower() == "true"
download_angle_lora = os.environ.get("DOWNLOAD_ANGLE_LORA", "false").lower() == "true"
base_model_id = os.environ["QWEN_EDIT_MODEL_ID"]
lightning_repo = os.environ["QWEN_EDIT_LIGHTNING_REPO"]
lightning_filename = os.environ["QWEN_EDIT_LIGHTNING_FILENAME"]
angle_repo = os.environ["QWEN_EDIT_ANGLE_REPO"]
angle_filename = os.environ["QWEN_EDIT_ANGLE_FILENAME"]
cache_dir = os.environ["HF_HOME"]

if download_base:
    path = snapshot_download(repo_id=base_model_id, cache_dir=cache_dir)
    print("base_model_cached_at", path)
else:
    print("base_model_skipped", base_model_id)

if download_lightning:
    lightning_path = hf_hub_download(
        repo_id=lightning_repo,
        filename=lightning_filename,
        cache_dir=cache_dir,
    )
    print("lightning_cached_at", lightning_path)
else:
    print("lightning_skipped", lightning_repo, lightning_filename)

if download_angle_lora:
    angle_path = hf_hub_download(
        repo_id=angle_repo,
        filename=angle_filename,
        cache_dir=cache_dir,
    )
    print("angle_lora_cached_at", angle_path)
else:
    print("angle_lora_skipped", angle_repo, angle_filename)
PY
