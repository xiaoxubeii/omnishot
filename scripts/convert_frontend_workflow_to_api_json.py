#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.comfy_ui_workflow import (
    adapt_api_workflow_for_local_runtime,
    convert_frontend_workflow_to_api,
    load_frontend_workflow,
)
from scripts.generate_bindings_from_api_json import build_bindings, write_json


def fetch_object_info(base_url: str) -> dict:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/object_info", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a ComfyUI frontend workflow export to API workflow JSON.")
    parser.add_argument("--workflow-ui", type=Path, required=True)
    parser.add_argument("--write-template", type=Path, required=True)
    parser.add_argument("--write-bindings", type=Path, required=True)
    parser.add_argument("--write-local-template", type=Path)
    parser.add_argument("--write-local-bindings", type=Path)
    parser.add_argument("--comfy-base-url", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    frontend_workflow = load_frontend_workflow(args.workflow_ui)
    object_info = fetch_object_info(args.comfy_base_url)
    api_workflow = convert_frontend_workflow_to_api(frontend_workflow, object_info)
    bindings = build_bindings(api_workflow)

    write_json(args.write_template, api_workflow)
    write_json(args.write_bindings, bindings)

    print(f"template_written: {args.write_template}")
    print(f"bindings_written: {args.write_bindings}")
    print(json.dumps(bindings, ensure_ascii=False, indent=2))

    if args.write_local_template or args.write_local_bindings:
        if not args.write_local_template or not args.write_local_bindings:
            raise SystemExit("--write-local-template and --write-local-bindings must be provided together")
        local_workflow = adapt_api_workflow_for_local_runtime(api_workflow, object_info)
        local_bindings = build_bindings(local_workflow)
        write_json(args.write_local_template, local_workflow)
        write_json(args.write_local_bindings, local_bindings)
        print(f"local_template_written: {args.write_local_template}")
        print(f"local_bindings_written: {args.write_local_bindings}")
        print(json.dumps(local_bindings, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
