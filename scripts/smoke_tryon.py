#!/usr/bin/env python3
import argparse
import base64
import json
from pathlib import Path
from urllib import request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for /generate/tryon endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/generate/tryon")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--person-template", default="woman_1")
    parser.add_argument("--cloth-type", default="overall")
    parser.add_argument("--save-to", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "filename": args.image.name,
        "image_base64": base64.b64encode(args.image.read_bytes()).decode("utf-8"),
        "person_template": args.person_template,
        "cloth_type": args.cloth_type,
        "seed": 123,
        "steps": 20,
        "guidance": 2.5,
        "width": 768,
        "height": 1024,
    }
    req = request.Request(
        args.url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=args.timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    args.save_to.parent.mkdir(parents=True, exist_ok=True)
    args.save_to.write_bytes(base64.b64decode(body["image_base64"]))
    print(f"status: ok")
    print(f"pipeline: {body.get('pipeline')}")
    print(f"generator_mode: {body.get('generator_mode')}")
    print(f"saved_file: {args.save_to}")
    print(f"metadata: {json.dumps(body.get('metadata', {}), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
