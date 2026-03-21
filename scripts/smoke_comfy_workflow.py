#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.comfy_client import ComfyClient
from app.config import get_settings
from app.workflow import build_workflow


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not args.image.exists():
        print(f"ERROR: image not found: {args.image}")
        return 1

    comfy = ComfyClient(args.comfy_base_url, args.comfy_ws_url)
    try:
        comfy_filename = await comfy.upload_image(args.image.read_bytes(), args.image.name)
        workflow, bindings = build_workflow(
            args.template,
            args.bindings,
            image_name=comfy_filename,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            seed=args.seed,
        )
        result = await comfy.run_workflow(
            workflow,
            preferred_output_nodes=bindings.preferred_output_nodes,
            timeout_seconds=args.timeout,
        )
    finally:
        await comfy.aclose()

    args.save_to.parent.mkdir(parents=True, exist_ok=True)
    args.save_to.write_bytes(result.image_bytes)
    print("status: ok")
    print(f"prompt_id: {result.prompt_id}")
    print(f"saved_file: {args.save_to}")
    print(f"image_ref: {result.image_ref}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a workflow template directly against ComfyUI.")
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT_DIR / "workflows" / "flux_json_reference_latent.template.json",
    )
    parser.add_argument(
        "--bindings",
        type=Path,
        default=ROOT_DIR / "workflows" / "flux_json_reference_latent.bindings.json",
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--comfy-base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--comfy-ws-url", default="ws://127.0.0.1:8188/ws")
    parser.add_argument(
        "--save-to",
        type=Path,
        default=ROOT_DIR / "data" / "output" / "smoke-comfy-workflow-latest.png",
    )
    return parser.parse_args()


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_run(parse_args())))
