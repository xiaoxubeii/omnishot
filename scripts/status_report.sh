#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
RUN_SMOKE="${RUN_SMOKE:-false}"

cd "${ROOT_DIR}"

echo "==> Service health"
python3 - <<'PY'
import urllib.request
targets = [
    "http://127.0.0.1:8188/queue",
    "http://127.0.0.1:8000/api/health",
]
for url in targets:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(f"{url} -> {r.status}")
    except Exception as e:
        print(f"{url} -> ERROR: {e}")
PY

echo
echo "==> FLUX readiness"
"${PYTHON_BIN}" scripts/check_flux_readiness.py

if [[ "${RUN_SMOKE}" == "true" ]]; then
  echo
  echo "==> Generate smoke"
  "${PYTHON_BIN}" scripts/smoke_generate.py
fi
