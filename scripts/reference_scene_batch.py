#!/usr/bin/env python3
import argparse
import base64
import json
from datetime import datetime
from pathlib import Path
from urllib import request


ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch generate reference-driven scene variants with locked product compositing.",
    )
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--seed-start", type=int, default=3000)
    return parser.parse_args()


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def discover_images(input_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(input_dir.glob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]


def load_plan(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("plan file must be a non-empty JSON list")

    normalized: list[dict] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"plan item #{index + 1} must be an object")
        name = str(item.get("name", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        style_refs = item.get("style_references", [])
        if not name or not prompt or not isinstance(style_refs, list) or not style_refs:
            raise ValueError(f"plan item #{index + 1} missing name, prompt, or style_references")
        normalized.append(
            {
                "name": name,
                "prompt": prompt,
                "negative_prompt": str(item.get("negative_prompt", "")).strip(),
                "style_references": [str(value).strip() for value in style_refs if str(value).strip()],
                "steps": int(item.get("steps", 8)),
                "true_cfg_scale": float(item.get("true_cfg_scale", 1.0)),
                "shadow_strength": float(item.get("shadow_strength", 0.4)),
                "reflection_strength": float(item.get("reflection_strength", 0.14)),
                "color_harmonize_strength": float(item.get("color_harmonize_strength", 0.18)),
            }
        )
    return normalized


def post_json(url: str, payload: dict, timeout: float) -> dict:
    req = request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def save_image(output_dir: Path, product_name: str, plan_name: str, payload: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{product_name}__{plan_name}.png"
    target.write_bytes(base64.b64decode(payload["image_base64"]))
    return target


def main() -> int:
    args = parse_args()
    images = discover_images(args.input_dir)
    plan_items = load_plan(args.plan_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.jsonl"

    seed = args.seed_start
    for image_path in images:
        image_base64 = encode_image(image_path)
        for plan in plan_items:
            style_ref_paths = [
                (args.plan_file.parent / value).resolve() if not Path(value).is_absolute() else Path(value)
                for value in plan["style_references"]
            ]
            payload = {
                "filename": image_path.name,
                "image_base64": image_base64,
                "style_reference_images_base64": [encode_image(path) for path in style_ref_paths],
                "prompt": plan["prompt"],
                "negative_prompt": plan["negative_prompt"],
                "seed": seed,
                "steps": plan["steps"],
                "true_cfg_scale": plan["true_cfg_scale"],
                "shadow_strength": plan["shadow_strength"],
                "reflection_strength": plan["reflection_strength"],
                "color_harmonize_strength": plan["color_harmonize_strength"],
            }
            response_payload = post_json(
                f"{args.api_base_url}/generate/reference-scene",
                payload,
                timeout=args.timeout,
            )
            saved_path = save_image(args.output_dir / "results", image_path.stem, plan["name"], response_payload)
            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "source_image": str(image_path),
                "plan_name": plan["name"],
                "saved_path": str(saved_path),
                "generator_mode": response_payload.get("generator_mode"),
                "pipeline": response_payload.get("pipeline"),
                "metadata": response_payload.get("metadata", {}),
                "style_references": [str(path) for path in style_ref_paths],
            }
            with manifest_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"ok: {image_path.name} -> {plan['name']} -> {saved_path}")
            seed += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
