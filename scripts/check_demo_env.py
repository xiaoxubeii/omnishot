#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_TEMPLATE = ROOT_DIR / "workflows" / "flux_product_demo.template.json"
WORKFLOW_BINDINGS = ROOT_DIR / "workflows" / "flux_product_demo.bindings.json"
COMFYUI_DIR = ROOT_DIR / "ComfyUI"
COMFYUI_BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188")


def print_line(label: str, value: str) -> None:
    print(f"{label:<24} {value}")


def check_comfyui() -> None:
    try:
        with urllib.request.urlopen(f"{COMFYUI_BASE_URL}/queue", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        print_line("ComfyUI API", f"reachable ({list(payload.keys())})")
    except urllib.error.URLError as exc:
        print_line("ComfyUI API", f"unreachable ({exc})")


def main() -> int:
    print_line("Workspace", str(ROOT_DIR))
    print_line("Python", sys.executable)
    print_line("ComfyUI dir", "ok" if COMFYUI_DIR.exists() else "missing")
    print_line("Workflow template", "ok" if WORKFLOW_TEMPLATE.exists() else "missing")
    print_line("Workflow bindings", "ok" if WORKFLOW_BINDINGS.exists() else "missing")
    check_comfyui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

