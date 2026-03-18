#!/usr/bin/env python3
import argparse
import base64
import json
import random
import re
import time
from hashlib import sha1
from datetime import datetime
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "http://127.0.0.1:8000/generate"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

DEFAULT_SCENES = [
    {
        "name": "sunset_bedroom",
        "prompt": (
            "luxury silk nightdress product photo on a bedroom chair near a window, "
            "golden sunset light, warm atmosphere, realistic shadows, premium commercial look"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed fabric, distorted shape, watermark"
        ),
    },
    {
        "name": "morning_terrace",
        "prompt": (
            "luxury silk nightdress product photo folded on a terrace table, "
            "soft morning light, fresh air mood, realistic texture, premium ecommerce style"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed fabric, distorted shape, watermark"
        ),
    },
    {
        "name": "neon_storefront",
        "prompt": (
            "luxury silk nightdress product photo in a fashion storefront display, "
            "subtle neon reflections, cinematic night ambience, realistic lighting, high detail"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed fabric, distorted shape, watermark"
        ),
    },
]

DEFAULT_EDITS = [
    {
        "name": "camera_left_45",
        "angle_preset": "camera_left_45",
        "prompt": "same exact product, premium ecommerce realism, accurate material response",
        "negative_prompt": "different product, changed silhouette, blurry, low quality, watermark",
        "use_angle_lora": True,
        "use_lightning": True,
        "steps": 8,
        "true_cfg_scale": 1.0,
    },
    {
        "name": "camera_right_45",
        "angle_preset": "camera_right_45",
        "prompt": "same exact product, premium ecommerce realism, accurate material response",
        "negative_prompt": "different product, changed silhouette, blurry, low quality, watermark",
        "use_angle_lora": True,
        "use_lightning": True,
        "steps": 8,
        "true_cfg_scale": 1.0,
    },
    {
        "name": "top_down",
        "angle_preset": "top_down",
        "prompt": "same exact product, premium ecommerce realism, accurate material response",
        "negative_prompt": "different product, changed silhouette, blurry, low quality, watermark",
        "use_angle_lora": True,
        "use_lightning": True,
        "steps": 8,
        "true_cfg_scale": 1.0,
    },
    {
        "name": "editorial_light_shift",
        "angle_preset": "editorial_light_shift",
        "prompt": "same exact product, only restyle the lighting into premium editorial light",
        "negative_prompt": "different product, changed silhouette, blurry, low quality, watermark",
        "use_angle_lora": False,
        "use_lightning": True,
        "steps": 8,
        "true_cfg_scale": 1.0,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch or watch-mode generation client for /generate endpoint.",
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Default: {DEFAULT_API_URL}")
    parser.add_argument("--edit-api-url", default="http://127.0.0.1:8000/generate/edit")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT_DIR / "data" / "incoming-products",
        help="Directory containing product images.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "data" / "batch-output",
        help="Directory to store generated images.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="JSONL file for run records. Default: <output-dir>/manifest.jsonl",
    )
    parser.add_argument(
        "--scenes-file",
        type=Path,
        default=None,
        help="Optional JSON file with scene list [{name,prompt,negative_prompt?}].",
    )
    parser.add_argument(
        "--edits-file",
        type=Path,
        default=None,
        help="Optional JSON file with edit list [{name,angle_preset?,prompt,negative_prompt?,use_angle_lora?,use_lightning?,steps?,true_cfg_scale?}].",
    )
    parser.add_argument(
        "--job-type",
        choices=["scene", "edit", "both"],
        default="scene",
        help="Which generation jobs to run. Default keeps old scene-only behavior.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan only and exit.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Watch-mode polling interval in seconds.",
    )
    parser.add_argument(
        "--max-images-per-cycle",
        type=int,
        default=0,
        help="0 means no limit; otherwise limit image count per cycle.",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=1000,
        help="Base seed for deterministic runs.",
    )
    parser.add_argument(
        "--random-seed",
        action="store_true",
        help="Use random seed per request instead of deterministic increment.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=900.0,
        help="HTTP timeout for each /generate request.",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=1,
        help="Retry count on request failure.",
    )
    parser.add_argument(
        "--move-processed-dir",
        type=Path,
        default=None,
        help="Optional directory to move source images after all scenes succeed.",
    )
    parser.add_argument(
        "--job-version",
        default=None,
        help="Optional job version tag used in de-dup keys. Default auto-derived from workflow files.",
    )
    return parser.parse_args()


def load_scenes(path: Path | None) -> list[dict]:
    if path is None:
        return DEFAULT_SCENES

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("scenes file must be a non-empty JSON list")

    scenes: list[dict] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"scene #{idx + 1} must be an object")
        name = str(item.get("name", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        negative_prompt = str(item.get("negative_prompt", "")).strip()
        if not name or not prompt:
            raise ValueError(f"scene #{idx + 1} missing name or prompt")
        scenes.append(
            {
                "name": slugify(name),
                "prompt": prompt,
                "negative_prompt": negative_prompt,
            }
        )
    return scenes


def load_edits(path: Path | None) -> list[dict]:
    if path is None:
        return DEFAULT_EDITS

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("edits file must be a non-empty JSON list")

    edits: list[dict] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"edit #{idx + 1} must be an object")
        name = str(item.get("name", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        angle_preset = str(item.get("angle_preset", "")).strip()
        if not name or (not prompt and not angle_preset):
            raise ValueError(f"edit #{idx + 1} missing name or prompt/angle_preset")
        edits.append(
            {
                "name": slugify(name),
                "prompt": prompt,
                "angle_preset": angle_preset or None,
                "negative_prompt": str(item.get("negative_prompt", "")).strip(),
                "use_angle_lora": bool(item.get("use_angle_lora", True)),
                "use_lightning": bool(item.get("use_lightning", True)),
                "steps": int(item.get("steps", 8)),
                "true_cfg_scale": float(item.get("true_cfg_scale", 1.0)),
            }
        )
    return edits


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    return cleaned or "scene"


def discover_images(input_dir: Path) -> list[Path]:
    images = []
    for path in sorted(input_dir.glob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            images.append(path)
    return images


def detect_job_version() -> str:
    template = ROOT_DIR / "workflows" / "flux_product_demo.template.json"
    bindings = ROOT_DIR / "workflows" / "flux_product_demo.bindings.json"
    parts = []
    for p in (template, bindings):
        if p.exists():
            s = p.stat()
            parts.append(f"{p.name}:{s.st_size}:{s.st_mtime_ns}")
        else:
            parts.append(f"{p.name}:missing")
    return sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def build_job_key(image_path: Path, kind: str, variant_name: str, job_version: str) -> str:
    stat = image_path.stat()
    return (
        f"{image_path.resolve()}::size={stat.st_size}::mtime_ns={stat.st_mtime_ns}"
        f"::kind={kind}::variant={variant_name}::job_version={job_version}"
    )


def load_processed_keys(manifest_path: Path) -> set[str]:
    processed: set[str] = set()
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
            key = str(record.get("job_key", "")).strip()
            status = str(record.get("status", "")).strip()
            if key and status == "ok":
                processed.add(key)
    return processed


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def call_generate(
    api_url: str,
    image_path: Path,
    prompt: str,
    negative_prompt: str,
    seed: int,
    timeout: float,
) -> dict:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "filename": image_path.name,
        "image_base64": encode_image(image_path),
    }
    req = request.Request(
        api_url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_edit_generate(
    api_url: str,
    image_path: Path,
    edit: dict,
    seed: int,
    timeout: float,
) -> dict:
    payload = {
        "prompt": edit.get("prompt", ""),
        "negative_prompt": edit.get("negative_prompt", ""),
        "seed": seed,
        "filename": image_path.name,
        "image_base64": encode_image(image_path),
        "angle_preset": edit.get("angle_preset"),
        "use_angle_lora": bool(edit.get("use_angle_lora", True)),
        "angle_lora_scale": float(edit.get("angle_lora_scale", 1.0)),
        "use_lightning": bool(edit.get("use_lightning", True)),
        "lightning_lora_scale": float(edit.get("lightning_lora_scale", 1.0)),
        "steps": int(edit.get("steps", 8)),
        "true_cfg_scale": float(edit.get("true_cfg_scale", 1.0)),
    }
    req = request.Request(
        api_url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_manifest_line(manifest_path: Path, record: dict) -> None:
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_output_image(output_dir: Path, source_image: Path, variant_name: str, response: dict) -> Path:
    image_b64 = response.get("image_base64")
    if not isinstance(image_b64, str) or not image_b64:
        raise ValueError("missing image_base64 in response")

    prompt_id = str(response.get("prompt_id", "unknown"))
    out_name = f"{slugify(source_image.stem)}__{variant_name}__{slugify(prompt_id)}.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / out_name
    out_path.write_bytes(base64.b64decode(image_b64))
    return out_path


def process_cycle(
    args: argparse.Namespace,
    scenes: list[dict],
    manifest_path: Path,
    processed_success: set[str],
    seed_counter: list[int],
) -> tuple[int, int]:
    candidates = discover_images(args.input_dir)
    if args.max_images_per_cycle > 0:
        candidates = candidates[: args.max_images_per_cycle]

    if not candidates:
        return 0, 0

    jobs_total = 0
    jobs_ok = 0

    for image_path in candidates:
        all_scene_ok = True
        for scene in scenes:
            scene_name = scene["name"]
            job_key = build_job_key(image_path, "scene", scene_name, args.job_version)
            if job_key in processed_success:
                continue

            jobs_total += 1
            seed = random.randint(1, 2_147_483_647) if args.random_seed else seed_counter[0]
            if not args.random_seed:
                seed_counter[0] += 1

            attempt = 0
            last_error = None
            response_payload = None
            while attempt <= args.retry:
                try:
                    response_payload = call_generate(
                        api_url=args.api_url,
                        image_path=image_path,
                        prompt=scene["prompt"],
                        negative_prompt=scene.get("negative_prompt", ""),
                        seed=seed,
                        timeout=args.request_timeout,
                    )
                    break
                except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                    attempt += 1
                    if attempt <= args.retry:
                        time.sleep(1.5)

            now = datetime.now().isoformat(timespec="seconds")
            if response_payload is None:
                all_scene_ok = False
                record = {
                    "timestamp": now,
                    "status": "error",
                    "job_key": job_key,
                    "input_image": str(image_path),
                    "scene": scene_name,
                    "prompt": scene["prompt"],
                    "negative_prompt": scene.get("negative_prompt", ""),
                    "seed": seed,
                    "error": last_error or "unknown error",
                }
                write_manifest_line(manifest_path, record)
                print(f"[ERROR] {image_path.name} / {scene_name}: {record['error']}")
                continue

            try:
                output_path = save_output_image(args.output_dir, image_path, scene_name, response_payload)
            except Exception as exc:
                all_scene_ok = False
                record = {
                    "timestamp": now,
                    "status": "error",
                    "job_key": job_key,
                    "input_image": str(image_path),
                    "scene": scene_name,
                    "prompt": scene["prompt"],
                    "negative_prompt": scene.get("negative_prompt", ""),
                    "seed": seed,
                    "error": f"save_output_failed: {exc}",
                }
                write_manifest_line(manifest_path, record)
                print(f"[ERROR] {image_path.name} / {scene_name}: {record['error']}")
                continue

            jobs_ok += 1
            processed_success.add(job_key)
            record = {
                "timestamp": now,
                "status": "ok",
                "job_key": job_key,
                "input_image": str(image_path),
                "scene": scene_name,
                "prompt": scene["prompt"],
                "negative_prompt": scene.get("negative_prompt", ""),
                "seed": seed,
                "generator_mode": response_payload.get("generator_mode"),
                "prompt_id": response_payload.get("prompt_id"),
                "output_file": str(output_path),
                "api_output_url": response_payload.get("output_url"),
            }
            write_manifest_line(manifest_path, record)
            print(
                f"[OK] {image_path.name} / {scene_name} -> {output_path.name} "
                f"(mode={record['generator_mode']})"
            )

        if all_scene_ok and args.move_processed_dir is not None and args.job_type == "scene":
            args.move_processed_dir.mkdir(parents=True, exist_ok=True)
            target = args.move_processed_dir / image_path.name
            image_path.rename(target)
            print(f"[MOVE] {image_path.name} -> {target}")

    return jobs_total, jobs_ok


def process_edit_cycle(
    args: argparse.Namespace,
    edits: list[dict],
    manifest_path: Path,
    processed_success: set[str],
    seed_counter: list[int],
) -> tuple[int, int]:
    candidates = discover_images(args.input_dir)
    if args.max_images_per_cycle > 0:
        candidates = candidates[: args.max_images_per_cycle]

    if not candidates:
        return 0, 0

    jobs_total = 0
    jobs_ok = 0

    for image_path in candidates:
        for edit in edits:
            edit_name = edit["name"]
            job_key = build_job_key(image_path, "edit", edit_name, args.job_version)
            if job_key in processed_success:
                continue

            jobs_total += 1
            seed = random.randint(1, 2_147_483_647) if args.random_seed else seed_counter[0]
            if not args.random_seed:
                seed_counter[0] += 1

            attempt = 0
            last_error = None
            response_payload = None
            while attempt <= args.retry:
                try:
                    response_payload = call_edit_generate(
                        api_url=args.edit_api_url,
                        image_path=image_path,
                        edit=edit,
                        seed=seed,
                        timeout=args.request_timeout,
                    )
                    break
                except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                    attempt += 1
                    if attempt <= args.retry:
                        time.sleep(1.5)

            now = datetime.now().isoformat(timespec="seconds")
            if response_payload is None:
                record = {
                    "timestamp": now,
                    "status": "error",
                    "job_key": job_key,
                    "type": "edit",
                    "input_image": str(image_path),
                    "edit": edit_name,
                    "angle_preset": edit.get("angle_preset"),
                    "prompt": edit.get("prompt", ""),
                    "negative_prompt": edit.get("negative_prompt", ""),
                    "seed": seed,
                    "error": last_error or "unknown error",
                }
                write_manifest_line(manifest_path, record)
                print(f"[ERROR] {image_path.name} / edit:{edit_name}: {record['error']}")
                continue

            try:
                output_path = save_output_image(args.output_dir / "edit", image_path, edit_name, response_payload)
            except Exception as exc:
                record = {
                    "timestamp": now,
                    "status": "error",
                    "job_key": job_key,
                    "type": "edit",
                    "input_image": str(image_path),
                    "edit": edit_name,
                    "prompt": edit.get("prompt", ""),
                    "seed": seed,
                    "error": f"save_output_failed: {exc}",
                }
                write_manifest_line(manifest_path, record)
                print(f"[ERROR] {image_path.name} / edit:{edit_name}: {record['error']}")
                continue

            jobs_ok += 1
            processed_success.add(job_key)
            record = {
                "timestamp": now,
                "status": "ok",
                "job_key": job_key,
                "type": "edit",
                "input_image": str(image_path),
                "edit": edit_name,
                "angle_preset": edit.get("angle_preset"),
                "prompt": edit.get("prompt", ""),
                "negative_prompt": edit.get("negative_prompt", ""),
                "seed": seed,
                "generator_mode": response_payload.get("generator_mode"),
                "pipeline": response_payload.get("pipeline"),
                "prompt_id": response_payload.get("prompt_id"),
                "output_file": str(output_path),
                "api_output_url": response_payload.get("output_url"),
                "metadata": response_payload.get("metadata", {}),
            }
            write_manifest_line(manifest_path, record)
            print(
                f"[OK] {image_path.name} / edit:{edit_name} -> {output_path.name} "
                f"(mode={record['generator_mode']})"
            )

    return jobs_total, jobs_ok


def main() -> int:
    args = parse_args()
    args.input_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest or (args.output_dir / "manifest.jsonl")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.touch(exist_ok=True)

    args.job_version = str(args.job_version).strip() if args.job_version else detect_job_version()

    scenes = load_scenes(args.scenes_file)
    edits = load_edits(args.edits_file)
    processed_success = load_processed_keys(manifest_path)
    seed_counter = [args.seed_start]

    print("batch_generate started")
    print(f"api_url: {args.api_url}")
    print(f"edit_api_url: {args.edit_api_url}")
    print(f"input_dir: {args.input_dir}")
    print(f"output_dir: {args.output_dir}")
    print(f"manifest: {manifest_path}")
    print(f"job_version: {args.job_version}")
    print(f"job_type: {args.job_type}")
    print(f"scenes: {[scene['name'] for scene in scenes]}")
    print(f"edits: {[edit['name'] for edit in edits]}")
    print(f"mode: {'once' if args.once else 'watch'}")

    if args.once:
        total = 0
        ok = 0
        if args.job_type in {"scene", "both"}:
            scene_total, scene_ok = process_cycle(args, scenes, manifest_path, processed_success, seed_counter)
            total += scene_total
            ok += scene_ok
        if args.job_type in {"edit", "both"}:
            edit_total, edit_ok = process_edit_cycle(args, edits, manifest_path, processed_success, seed_counter)
            total += edit_total
            ok += edit_ok
        print(f"done_once total_jobs={total} success_jobs={ok}")
        return 0

    try:
        while True:
            total = 0
            ok = 0
            if args.job_type in {"scene", "both"}:
                scene_total, scene_ok = process_cycle(args, scenes, manifest_path, processed_success, seed_counter)
                total += scene_total
                ok += scene_ok
            if args.job_type in {"edit", "both"}:
                edit_total, edit_ok = process_edit_cycle(args, edits, manifest_path, processed_success, seed_counter)
                total += edit_total
                ok += edit_ok
            if total > 0:
                print(f"cycle_done total_jobs={total} success_jobs={ok}")
            time.sleep(max(0.5, args.poll_seconds))
    except KeyboardInterrupt:
        print("stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
