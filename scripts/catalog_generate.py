#!/usr/bin/env python3
import argparse
import base64
import json
import time
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from urllib import request


ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scene and try-on images from a folder of product images.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input-dir", type=Path, default=ROOT_DIR / "data" / "incoming-products")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data" / "catalog-output")
    parser.add_argument(
        "--product-brief",
        default="premium ecommerce apparel product",
        help="Injected into scene preset prompt templates.",
    )
    parser.add_argument("--scene-count", type=int, default=4, help="How many built-in scene presets to use.")
    parser.add_argument(
        "--tryon-templates",
        default="woman_1,woman_2,woman_3",
        help="Comma-separated built-in person templates for try-on.",
    )
    parser.add_argument("--cloth-type", default="overall", choices=["upper", "lower", "overall"])
    parser.add_argument("--once", action="store_true", help="Run one scan then exit.")
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--seed-start", type=int, default=1000)
    return parser.parse_args()


def api_get_json(url: str, timeout: float) -> list[dict]:
    with request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post_json(url: str, payload: dict, timeout: float) -> dict:
    req = request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_images(input_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(input_dir.glob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]


def build_job_key(image_path: Path, category: str, variant: str) -> str:
    stat = image_path.stat()
    raw = f"{image_path.resolve()}::{stat.st_size}::{stat.st_mtime_ns}::{category}::{variant}"
    return sha1(raw.encode("utf-8")).hexdigest()


def load_processed_keys(manifest_path: Path) -> set[str]:
    processed = set()
    if not manifest_path.exists():
        return processed
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get("status") == "ok" and record.get("job_key"):
                processed.add(record["job_key"])
    return processed


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def save_response_image(target_dir: Path, stem: str, variant_name: str, payload: dict) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{stem}__{variant_name}.png"
    output_path.write_bytes(base64.b64decode(payload["image_base64"]))
    return output_path


def render_scene_prompt(template: str, product_brief: str) -> str:
    return template.format(product_brief=product_brief).strip()


def process_once(args: argparse.Namespace) -> None:
    scenes = api_get_json(f"{args.api_base_url}/api/presets/scenes", timeout=args.timeout)[: args.scene_count]
    tryon_templates = [item.strip() for item in args.tryon_templates.split(",") if item.strip()]

    images = discover_images(args.input_dir)
    manifest_path = args.output_dir / "manifest.jsonl"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed_keys = load_processed_keys(manifest_path)

    seed = args.seed_start
    for image_path in images:
        image_b64 = encode_image(image_path)

        for scene in scenes:
            job_key = build_job_key(image_path, "scene", scene["name"])
            if job_key in processed_keys:
                continue
            payload = {
                "prompt": render_scene_prompt(scene["prompt_template"], args.product_brief),
                "negative_prompt": scene["negative_prompt"],
                "seed": seed,
                "filename": image_path.name,
                "image_base64": image_b64,
            }
            response_payload = api_post_json(
                f"{args.api_base_url}/generate/scene",
                payload,
                timeout=args.timeout,
            )
            saved_path = save_response_image(
                args.output_dir / "scenes",
                image_path.stem,
                scene["name"],
                response_payload,
            )
            write_manifest(
                manifest_path,
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "job_key": job_key,
                    "status": "ok",
                    "type": "scene",
                    "source_image": str(image_path),
                    "variant": scene["name"],
                    "saved_path": str(saved_path),
                    "generator_mode": response_payload.get("generator_mode"),
                    "pipeline": response_payload.get("pipeline"),
                },
            )
            processed_keys.add(job_key)
            print(f"scene ok: {image_path.name} -> {scene['name']} -> {saved_path}")
            seed += 1

        for template_name in tryon_templates:
            job_key = build_job_key(image_path, "tryon", template_name)
            if job_key in processed_keys:
                continue
            payload = {
                "filename": image_path.name,
                "image_base64": image_b64,
                "person_template": template_name,
                "cloth_type": args.cloth_type,
                "seed": seed,
                "steps": 30,
                "guidance": 2.5,
                "width": 768,
                "height": 1024,
            }
            response_payload = api_post_json(
                f"{args.api_base_url}/generate/tryon",
                payload,
                timeout=args.timeout,
            )
            saved_path = save_response_image(
                args.output_dir / "tryon",
                image_path.stem,
                template_name,
                response_payload,
            )
            write_manifest(
                manifest_path,
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "job_key": job_key,
                    "status": "ok",
                    "type": "tryon",
                    "source_image": str(image_path),
                    "variant": template_name,
                    "saved_path": str(saved_path),
                    "generator_mode": response_payload.get("generator_mode"),
                    "pipeline": response_payload.get("pipeline"),
                    "metadata": response_payload.get("metadata", {}),
                },
            )
            processed_keys.add(job_key)
            print(f"tryon ok: {image_path.name} -> {template_name} -> {saved_path}")
            seed += 1


def write_manifest(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()

    while True:
        process_once(args)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
