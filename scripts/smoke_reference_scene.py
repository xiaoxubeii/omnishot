#!/usr/bin/env python3
import argparse
import base64
import json
from pathlib import Path
from urllib import request


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for /generate/reference-scene endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/generate/reference-scene")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--style-reference", type=Path, action="append", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--true-cfg-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--shadow-strength", type=float, default=0.4)
    parser.add_argument("--reflection-strength", type=float, default=0.14)
    parser.add_argument("--color-harmonize-strength", type=float, default=0.18)
    parser.add_argument(
        "--save-to",
        type=Path,
        default=ROOT_DIR / "data" / "output" / "smoke-reference-scene-latest.png",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "filename": args.image.name,
        "image_base64": base64.b64encode(args.image.read_bytes()).decode("utf-8"),
        "style_reference_images_base64": [
            base64.b64encode(path.read_bytes()).decode("utf-8") for path in args.style_reference
        ],
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "seed": args.seed,
        "steps": args.steps,
        "true_cfg_scale": args.true_cfg_scale,
        "shadow_strength": args.shadow_strength,
        "reflection_strength": args.reflection_strength,
        "color_harmonize_strength": args.color_harmonize_strength,
    }
    req = request.Request(
        args.url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=3600.0) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    args.save_to.parent.mkdir(parents=True, exist_ok=True)
    args.save_to.write_bytes(base64.b64decode(body["image_base64"]))
    print("status: ok")
    print(f"pipeline: {body.get('pipeline')}")
    print(f"generator_mode: {body.get('generator_mode')}")
    print(f"saved_file: {args.save_to}")
    print(f"metadata: {json.dumps(body.get('metadata', {}), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
