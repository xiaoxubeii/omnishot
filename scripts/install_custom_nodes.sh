#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIP_BIN="${ROOT_DIR}/.venv/bin/pip"
LOG_DIR="${ROOT_DIR}/logs"
INSTALL_CUSTOM_NODES_FAST="${INSTALL_CUSTOM_NODES_FAST:-false}"
COMFYUI_DIR="${ROOT_DIR}/ComfyUI"
CUSTOM_NODES_DIR="${COMFYUI_DIR}/custom_nodes"

if [[ ! -x "${PIP_BIN}" ]]; then
  echo "ERROR: pip not found at ${PIP_BIN}"
  exit 1
fi

if [[ ! -d "${COMFYUI_DIR}" || ! -f "${COMFYUI_DIR}/main.py" ]]; then
  git -C "${ROOT_DIR}" submodule update --init --recursive ComfyUI
fi

mkdir -p "${LOG_DIR}"

node_dirs=(
  "ComfyUI-GGUF"
  "comfyui_controlnet_aux"
  "ComfyUI-RMBG"
)

if [[ $# -gt 0 ]]; then
  node_dirs=("$@")
fi

declare -A node_repos=(
  ["ComfyUI-GGUF"]="https://github.com/city96/ComfyUI-GGUF.git"
  ["comfyui_controlnet_aux"]="https://github.com/Fannovel16/comfyui_controlnet_aux.git"
  ["ComfyUI-RMBG"]="https://github.com/1038lab/ComfyUI-RMBG.git"
)

for node_dir in "${node_dirs[@]}"; do
  node_path="${CUSTOM_NODES_DIR}/${node_dir}"
  req_file="${node_path}/requirements.txt"
  log_file="${LOG_DIR}/install-${node_dir}.log"

  if [[ ! -d "${node_path}" ]]; then
    repo_url="${node_repos[${node_dir}]:-}"
    if [[ -z "${repo_url}" ]]; then
      echo "SKIP: unknown custom node repo for ${node_dir}"
      continue
    fi
    git clone "${repo_url}" "${node_path}"
  fi

  if [[ ! -f "${req_file}" ]]; then
    echo "SKIP: requirements not found: ${req_file}"
    continue
  fi

  echo "==> Installing ${node_dir} dependencies"
  echo "    mode: $([[ \"${INSTALL_CUSTOM_NODES_FAST}\" == \"true\" ]] && echo fast || echo full)"
  echo "    requirements: ${req_file}"
  echo "    log: ${log_file}"

  if [[ "${INSTALL_CUSTOM_NODES_FAST}" == "true" && "${node_dir}" == "comfyui_controlnet_aux" ]]; then
    {
      date
      echo "[fast mode] Installing minimal dependencies for comfyui_controlnet_aux"
      PIP_PROGRESS_BAR="${PIP_PROGRESS_BAR:-off}" \
        "${PIP_BIN}" install opencv-python-headless
    } 2>&1 | tee "${log_file}"
  elif [[ "${INSTALL_CUSTOM_NODES_FAST}" == "true" && "${node_dir}" == "ComfyUI-RMBG" ]]; then
    {
      date
      echo "[fast mode] Installing minimal dependencies for ComfyUI-RMBG"
      PIP_PROGRESS_BAR="${PIP_PROGRESS_BAR:-off}" \
        "${PIP_BIN}" install opencv-python-headless onnxruntime transparent-background
    } 2>&1 | tee "${log_file}"
  else
    {
      date
      PIP_PROGRESS_BAR="${PIP_PROGRESS_BAR:-off}" \
        "${PIP_BIN}" install -r "${req_file}"
    } 2>&1 | tee "${log_file}"
  fi

  echo "==> Done: ${node_dir}"
done

echo "All requested custom-node dependency installs finished."
