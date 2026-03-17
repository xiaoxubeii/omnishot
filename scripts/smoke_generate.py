#!/usr/bin/env python3
import argparse
import base64
import json
from pathlib import Path
from urllib import request


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for /generate endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/generate")
    parser.add_argument(
        "--image",
        type=Path,
        default=ROOT_DIR / "data" / "comfy-input" / "demo-product.png",
    )
    parser.add_argument("--prompt", default="放在木桌上，阳光斑驳，商品摄影")
    parser.add_argument("--negative-prompt", default="模糊,变形")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument(
        "--save-to",
        type=Path,
        default=ROOT_DIR / "data" / "output" / "smoke-latest.png",
    )
    args = parser.parse_args()

    if not args.image.exists():
        print(f"ERROR: image not found: {args.image}")
        return 1

    payload = {
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "seed": args.seed,
        "filename": args.image.name,
        "image_base64": base64.b64encode(args.image.read_bytes()).decode("utf-8"),
    }

    req = request.Request(
        args.url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with request.urlopen(req, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))

    output_b64 = body.get("image_base64")
    if not output_b64:
        print("ERROR: missing image_base64 in response")
        return 1

    args.save_to.parent.mkdir(parents=True, exist_ok=True)
    args.save_to.write_bytes(base64.b64decode(output_b64))

    print(f"status: ok")
    print(f"generator_mode: {body.get('generator_mode')}")
    print(f"prompt_id: {body.get('prompt_id')}")
    print(f"api_output_url: {body.get('output_url')}")
    print(f"saved_file: {args.save_to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
