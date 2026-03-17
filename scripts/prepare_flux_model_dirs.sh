#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${ROOT_DIR}/ComfyUI/models"

declare -A TARGETS
TARGETS["unet"]="flux1-dev-Q4_K_M.gguf"
TARGETS["text_encoders"]="t5xxl_fp8.safetensors (or t5xxl_fp16.safetensors)"
TARGETS["clip"]="clip_l.safetensors"
TARGETS["vae"]="ae.sft"
TARGETS["controlnet"]="flux-depth-controlnet.safetensors"

mkdir -p "${MODELS_DIR}"

for subdir in "${!TARGETS[@]}"; do
  mkdir -p "${MODELS_DIR}/${subdir}"
done

cat > "${MODELS_DIR}/FLUX_MODEL_PLACEMENT.txt" <<EOF
FLUX demo model placement
Generated at: $(date)

Place your model files in these directories:
- ${MODELS_DIR}/unet
  Example: ${TARGETS["unet"]}

- ${MODELS_DIR}/text_encoders
  Example: ${TARGETS["text_encoders"]}

- ${MODELS_DIR}/clip
  Example: ${TARGETS["clip"]}

- ${MODELS_DIR}/vae
  Example: ${TARGETS["vae"]}

- ${MODELS_DIR}/controlnet
  Example: ${TARGETS["controlnet"]}
EOF

echo "Prepared model directories:"
for subdir in "unet" "text_encoders" "clip" "vae" "controlnet"; do
  printf "  - %s/%s\n" "${MODELS_DIR}" "${subdir}"
done
echo "Guide file: ${MODELS_DIR}/FLUX_MODEL_PLACEMENT.txt"
