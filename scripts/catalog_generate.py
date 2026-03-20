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
DEFAULT_PRODUCT_BRIEF = "高端电商服饰商品主图"
DEFAULT_SCENE_COUNT = 4
DEFAULT_SCENE_PRESETS = ""
DEFAULT_TRYON_TEMPLATES = "woman_1,woman_2,woman_3"
DEFAULT_EDIT_PRESETS = ""
DEFAULT_TRYON_ANGLE_PRESETS = ""
TRYON_ANGLE_SUFFIX = (
    "保持完全相同的模特身份、面部、发型、身体比例、服装贴合度、花型、"
    "辅料、颜色和轮廓。只改变镜头视角、取景和灯光，生成照片级真实的"
    "高级电商时尚图。"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate scene, try-on, edit, and tryon-angle images from a folder of product images."
    )
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input-dir", type=Path, default=ROOT_DIR / "data" / "incoming-products")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data" / "catalog-output")
    parser.add_argument(
        "--profile",
        default="",
        help="Built-in catalog profile name from /api/presets/catalog-profiles, e.g. sleepwear_luxury.",
    )
    parser.add_argument(
        "--product-brief",
        default=DEFAULT_PRODUCT_BRIEF,
        help="Injected into scene preset prompt templates.",
    )
    parser.add_argument("--scene-count", type=int, default=DEFAULT_SCENE_COUNT)
    parser.add_argument(
        "--scene-presets",
        default=DEFAULT_SCENE_PRESETS,
        help="Comma-separated scene preset names. Empty means use scene-count or profile defaults.",
    )
    parser.add_argument("--tryon-templates", default=DEFAULT_TRYON_TEMPLATES)
    parser.add_argument("--cloth-type", default="overall", choices=["upper", "lower", "overall"])
    parser.add_argument(
        "--edit-presets",
        default=DEFAULT_EDIT_PRESETS,
        help="Comma-separated built-in edit preset names. Empty means disabled.",
    )
    parser.add_argument(
        "--edit-extra-prompt",
        default="",
        help="Extra prompt appended to product edit requests.",
    )
    parser.add_argument(
        "--tryon-angle-presets",
        default=DEFAULT_TRYON_ANGLE_PRESETS,
        help="Comma-separated built-in edit preset names applied to try-on outputs. Empty means disabled.",
    )
    parser.add_argument(
        "--tryon-angle-extra-prompt",
        default="",
        help="Extra prompt appended to model-wearing angle edit requests.",
    )
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


def load_success_records(manifest_path: Path) -> tuple[set[str], dict[str, dict]]:
    processed = set()
    records: dict[str, dict] = {}
    if not manifest_path.exists():
        return processed, records
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            job_key = str(record.get("job_key", "")).strip()
            if record.get("status") == "ok" and job_key:
                processed.add(job_key)
                records[job_key] = record
    return processed, records


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def save_response_image(target_dir: Path, stem: str, variant_name: str, payload: dict) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{stem}__{variant_name}.png"
    output_path.write_bytes(base64.b64decode(payload["image_base64"]))
    return output_path


def render_scene_prompt(template: str, product_brief: str) -> str:
    return template.format(product_brief=product_brief).strip()


def parse_names(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def index_presets(items: list[dict]) -> dict[str, dict]:
    return {item["name"]: item for item in items}


def select_presets(all_presets: list[dict], names: list[str]) -> list[dict]:
    if not names:
        return []
    indexed = index_presets(all_presets)
    selected: list[dict] = []
    missing: list[str] = []
    for name in names:
        preset = indexed.get(name)
        if preset is None:
            missing.append(name)
            continue
        selected.append(preset)
    if missing:
        raise ValueError(f"Unknown presets: {', '.join(missing)}")
    return selected


def select_profile(all_profiles: list[dict], profile_name: str) -> dict | None:
    profile_name = profile_name.strip()
    if not profile_name:
        return None
    indexed = index_presets(all_profiles)
    profile = indexed.get(profile_name)
    if profile is None:
        raise ValueError(f"Unknown profile: {profile_name}")
    return profile


def choose_value(current: str, default: str, profile_value: str | None) -> str:
    if current != default:
        return current
    return current if profile_value is None else str(profile_value)


def choose_names(current: str, default: str, profile_values: list[str] | None) -> list[str]:
    if current != default:
        return parse_names(current)
    return [str(item).strip() for item in (profile_values or []) if str(item).strip()]


def render_product_edit_prompt(preset: dict, extra_prompt: str) -> str:
    parts = [
        str(preset.get("prompt_template", "")).strip(),
        extra_prompt.strip(),
    ]
    return "\n".join(part for part in parts if part).strip()


def render_tryon_angle_prompt(preset: dict, extra_prompt: str) -> str:
    parts = [
        str(preset.get("prompt_template", "")).strip(),
        TRYON_ANGLE_SUFFIX,
        extra_prompt.strip(),
    ]
    return "\n".join(part for part in parts if part).strip()


def write_manifest(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def process_once(args: argparse.Namespace) -> None:
    scenes_all = api_get_json(f"{args.api_base_url}/api/presets/scenes", timeout=args.timeout)
    edit_presets_all = api_get_json(f"{args.api_base_url}/api/presets/edit-presets", timeout=args.timeout)
    catalog_profiles = api_get_json(f"{args.api_base_url}/api/presets/catalog-profiles", timeout=args.timeout)
    profile = select_profile(catalog_profiles, args.profile)

    product_brief = choose_value(args.product_brief, DEFAULT_PRODUCT_BRIEF, profile.get("product_brief") if profile else None)
    cloth_type = choose_value(args.cloth_type, "overall", profile.get("cloth_type") if profile else None)
    scene_names = choose_names(args.scene_presets, DEFAULT_SCENE_PRESETS, profile.get("scene_presets") if profile else None)
    tryon_templates = choose_names(args.tryon_templates, DEFAULT_TRYON_TEMPLATES, profile.get("tryon_templates") if profile else None)
    edit_preset_names = choose_names(args.edit_presets, DEFAULT_EDIT_PRESETS, profile.get("edit_presets") if profile else None)
    tryon_angle_preset_names = choose_names(
        args.tryon_angle_presets,
        DEFAULT_TRYON_ANGLE_PRESETS,
        profile.get("tryon_angle_presets") if profile else None,
    )
    edit_extra_prompt = choose_value(args.edit_extra_prompt, "", profile.get("edit_extra_prompt") if profile else None)
    tryon_angle_extra_prompt = choose_value(
        args.tryon_angle_extra_prompt,
        "",
        profile.get("tryon_angle_extra_prompt") if profile else None,
    )

    if scene_names:
        scenes = select_presets(scenes_all, scene_names)
    else:
        scenes = scenes_all[: args.scene_count]

    edit_presets = select_presets(edit_presets_all, edit_preset_names)
    tryon_angle_presets = select_presets(edit_presets_all, tryon_angle_preset_names)

    images = discover_images(args.input_dir)
    manifest_path = args.output_dir / "manifest.jsonl"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed_keys, success_records = load_success_records(manifest_path)

    seed = args.seed_start
    for image_path in images:
        image_b64 = encode_image(image_path)

        for scene in scenes:
            job_key = build_job_key(image_path, "scene", scene["name"])
            if job_key in processed_keys:
                continue
            payload = {
                "prompt": render_scene_prompt(scene["prompt_template"], product_brief),
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
            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "job_key": job_key,
                "status": "ok",
                "type": "scene",
                "source_image": str(image_path),
                "variant": scene["name"],
                "saved_path": str(saved_path),
                "generator_mode": response_payload.get("generator_mode"),
                "pipeline": response_payload.get("pipeline"),
            }
            write_manifest(manifest_path, record)
            processed_keys.add(job_key)
            success_records[job_key] = record
            print(f"scene ok: {image_path.name} -> {scene['name']} -> {saved_path}")
            seed += 1

        for preset in edit_presets:
            job_key = build_job_key(image_path, "edit", preset["name"])
            if job_key in processed_keys:
                continue
            payload = {
                "filename": image_path.name,
                "image_base64": image_b64,
                "angle_preset": preset["name"],
                "prompt": render_product_edit_prompt(preset, edit_extra_prompt),
                "negative_prompt": preset.get("negative_prompt", ""),
                "seed": seed,
                "steps": 8,
                "true_cfg_scale": 1.0,
                "use_angle_lora": False,
                "use_lightning": False,
            }
            response_payload = api_post_json(
                f"{args.api_base_url}/generate/edit",
                payload,
                timeout=args.timeout,
            )
            saved_path = save_response_image(
                args.output_dir / "edit",
                image_path.stem,
                preset["name"],
                response_payload,
            )
            record = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "job_key": job_key,
                "status": "ok",
                "type": "edit",
                "source_image": str(image_path),
                "variant": preset["name"],
                "saved_path": str(saved_path),
                "generator_mode": response_payload.get("generator_mode"),
                "pipeline": response_payload.get("pipeline"),
                "metadata": response_payload.get("metadata", {}),
            }
            write_manifest(manifest_path, record)
            processed_keys.add(job_key)
            success_records[job_key] = record
            print(f"edit ok: {image_path.name} -> {preset['name']} -> {saved_path}")
            seed += 1

        for template_name in tryon_templates:
            tryon_job_key = build_job_key(image_path, "tryon", template_name)
            tryon_response_payload: dict | None = None
            tryon_saved_path: Path | None = None

            if tryon_job_key in processed_keys:
                saved_path = success_records.get(tryon_job_key, {}).get("saved_path")
                if saved_path:
                    tryon_saved_path = Path(saved_path)
            else:
                payload = {
                    "filename": image_path.name,
                    "image_base64": image_b64,
                    "person_template": template_name,
                    "cloth_type": cloth_type,
                    "seed": seed,
                    "steps": 30,
                    "guidance": 2.5,
                    "width": 768,
                    "height": 1024,
                }
                tryon_response_payload = api_post_json(
                    f"{args.api_base_url}/generate/tryon",
                    payload,
                    timeout=args.timeout,
                )
                tryon_saved_path = save_response_image(
                    args.output_dir / "tryon",
                    image_path.stem,
                    template_name,
                    tryon_response_payload,
                )
                record = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "job_key": tryon_job_key,
                    "status": "ok",
                    "type": "tryon",
                    "source_image": str(image_path),
                    "variant": template_name,
                    "saved_path": str(tryon_saved_path),
                    "generator_mode": tryon_response_payload.get("generator_mode"),
                    "pipeline": tryon_response_payload.get("pipeline"),
                    "metadata": tryon_response_payload.get("metadata", {}),
                }
                write_manifest(manifest_path, record)
                processed_keys.add(tryon_job_key)
                success_records[tryon_job_key] = record
                print(f"tryon ok: {image_path.name} -> {template_name} -> {tryon_saved_path}")
                seed += 1

            if not tryon_angle_presets:
                continue

            if tryon_response_payload is not None:
                tryon_source_b64 = str(tryon_response_payload["image_base64"])
            elif tryon_saved_path is not None and tryon_saved_path.exists():
                tryon_source_b64 = encode_image(tryon_saved_path)
            else:
                print(f"tryon_angle skip: missing try-on source for {image_path.name} / {template_name}")
                continue

            for preset in tryon_angle_presets:
                variant_name = f"{template_name}__{preset['name']}"
                job_key = build_job_key(image_path, "tryon_angle", variant_name)
                if job_key in processed_keys:
                    continue
                payload = {
                    "filename": f"{image_path.stem}__{template_name}.png",
                    "image_base64": tryon_source_b64,
                    "angle_preset": preset["name"],
                    "prompt": render_tryon_angle_prompt(preset, tryon_angle_extra_prompt),
                    "negative_prompt": preset.get("negative_prompt", ""),
                    "seed": seed,
                    "steps": 8,
                    "true_cfg_scale": 1.0,
                    "use_angle_lora": False,
                    "use_lightning": False,
                }
                response_payload = api_post_json(
                    f"{args.api_base_url}/generate/edit",
                    payload,
                    timeout=args.timeout,
                )
                saved_path = save_response_image(
                    args.output_dir / "tryon-angle",
                    image_path.stem,
                    variant_name,
                    response_payload,
                )
                record = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "job_key": job_key,
                    "status": "ok",
                    "type": "tryon_angle",
                    "source_image": str(image_path),
                    "variant": variant_name,
                    "saved_path": str(saved_path),
                    "generator_mode": response_payload.get("generator_mode"),
                    "pipeline": response_payload.get("pipeline"),
                    "metadata": response_payload.get("metadata", {}),
                }
                write_manifest(manifest_path, record)
                processed_keys.add(job_key)
                success_records[job_key] = record
                print(f"tryon_angle ok: {image_path.name} -> {variant_name} -> {saved_path}")
                seed += 1


def main() -> int:
    args = parse_args()

    while True:
        process_once(args)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
