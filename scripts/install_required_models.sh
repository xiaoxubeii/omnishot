#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${ROOT_DIR}/ComfyUI/models"
MIRROR_BASE="${HF_MIRROR_BASE:-https://hf-mirror.com}"
GGUF_FILE="${FLUX_GGUF_FILE:-flux1-dev-Q4_K_S.gguf}"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
HF_ENDPOINT_FOR_PRELOAD="${HF_ENDPOINT_FOR_PRELOAD:-${MIRROR_BASE}}"

mkdir -p \
  "${MODELS_DIR}/unet" \
  "${MODELS_DIR}/text_encoders" \
  "${MODELS_DIR}/clip" \
  "${MODELS_DIR}/vae" \
  "${MODELS_DIR}/controlnet" \
  "${MODELS_DIR}/RMBG/RMBG-2.0" \
  "${MODELS_DIR}/RMBG/BiRefNet"

download_file() {
  local url="$1"
  local dst="$2"
  local expected_size="$3"
  local tmp="${dst}.part"

  echo
  echo "==> Downloading $(basename "${dst}")"
  echo "    from: ${url}"
  echo "    to:   ${dst}"

  wget \
    --continue \
    --tries=50 \
    --retry-connrefused \
    --waitretry=2 \
    --read-timeout=30 \
    --timeout=30 \
    --progress=dot:giga \
    -O "${tmp}" \
    "${url}"

  mv "${tmp}" "${dst}"

  local actual_size
  actual_size="$(stat -c '%s' "${dst}")"
  if [[ "${actual_size}" != "${expected_size}" ]]; then
    echo "ERROR: size mismatch for ${dst}"
    echo "expected: ${expected_size}"
    echo "actual:   ${actual_size}"
    exit 1
  fi
  echo "    verified: ${actual_size} bytes"
}

download_file \
  "${MIRROR_BASE}/city96/FLUX.1-dev-gguf/resolve/main/${GGUF_FILE}" \
  "${MODELS_DIR}/unet/${GGUF_FILE}" \
  "6805988640"

download_file \
  "${MIRROR_BASE}/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" \
  "${MODELS_DIR}/text_encoders/t5xxl_fp8.safetensors" \
  "4893934904"

download_file \
  "${MIRROR_BASE}/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
  "${MODELS_DIR}/clip/clip_l.safetensors" \
  "246144152"

download_file \
  "${MIRROR_BASE}/Kijai/flux-fp8/resolve/main/flux-vae-bf16.safetensors" \
  "${MODELS_DIR}/vae/ae.sft" \
  "167664710"

download_file \
  "${MIRROR_BASE}/XLabs-AI/flux-controlnet-depth-v3/resolve/main/flux-depth-controlnet-v3.safetensors" \
  "${MODELS_DIR}/controlnet/flux-depth-controlnet.safetensors" \
  "1487623552"

download_file \
  "${MIRROR_BASE}/1038lab/RMBG-2.0/resolve/main/config.json" \
  "${MODELS_DIR}/RMBG/RMBG-2.0/config.json" \
  "405"

download_file \
  "${MIRROR_BASE}/1038lab/RMBG-2.0/resolve/main/birefnet.py" \
  "${MODELS_DIR}/RMBG/RMBG-2.0/birefnet.py" \
  "91320"

download_file \
  "${MIRROR_BASE}/1038lab/RMBG-2.0/resolve/main/BiRefNet_config.py" \
  "${MODELS_DIR}/RMBG/RMBG-2.0/BiRefNet_config.py" \
  "298"

download_file \
  "${MIRROR_BASE}/1038lab/RMBG-2.0/resolve/main/model.safetensors" \
  "${MODELS_DIR}/RMBG/RMBG-2.0/model.safetensors" \
  "884878856"

download_file \
  "${MIRROR_BASE}/1038lab/BiRefNet/resolve/main/config.json" \
  "${MODELS_DIR}/RMBG/BiRefNet/config.json" \
  "402"

download_file \
  "${MIRROR_BASE}/1038lab/BiRefNet/resolve/main/birefnet.py" \
  "${MODELS_DIR}/RMBG/BiRefNet/birefnet.py" \
  "92068"

download_file \
  "${MIRROR_BASE}/1038lab/BiRefNet/resolve/main/BiRefNet_config.py" \
  "${MODELS_DIR}/RMBG/BiRefNet/BiRefNet_config.py" \
  "298"

download_file \
  "${MIRROR_BASE}/1038lab/BiRefNet/resolve/main/BiRefNet-HR-matting.safetensors" \
  "${MODELS_DIR}/RMBG/BiRefNet/BiRefNet-HR-matting.safetensors" \
  "444473596"

echo
echo "==> Preloading depth preprocessor cache (LiheYoung/depth-anything-large-hf)"
HF_ENDPOINT="${HF_ENDPOINT_FOR_PRELOAD}" "${PYTHON_BIN}" - <<'PY'
from huggingface_hub import snapshot_download
repo = "LiheYoung/depth-anything-large-hf"
path = snapshot_download(repo_id=repo)
print("cached_at", path)
PY

echo
echo "All required FLUX demo model files are installed."
