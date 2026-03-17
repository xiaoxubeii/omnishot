#!/usr/bin/env python3
import argparse
import importlib
import json
import os
import sys
import warnings
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
COMFYUI_BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")


NODE_GROUPS = {
    "GGUF nodes": ["gguf"],
    "RMBG nodes": ["rmbg"],
    "Depth preprocess nodes": ["depthanything", "midas", "zoe", "leres", "depth map preprocessor"],
}

IMPORT_CHECKS = {
    "gguf": {"desc": "GGUF loader runtime", "required": True},
    "cv2": {"desc": "OpenCV for preprocessors", "required": True},
    "skimage": {"desc": "scikit-image for preprocessors", "required": False},
    "mediapipe": {"desc": "MediaPipe (some aux preprocessors)", "required": False},
    "onnxruntime": {"desc": "ONNX runtime (RMBG optional nodes)", "required": False},
    "transparent_background": {"desc": "RMBG transparent-background", "required": False},
}

MODEL_DIRS = {
    "UNet/GGUF": ROOT_DIR / "ComfyUI" / "models" / "unet",
    "Text Encoders": ROOT_DIR / "ComfyUI" / "models" / "text_encoders",
    "CLIP": ROOT_DIR / "ComfyUI" / "models" / "clip",
    "VAE": ROOT_DIR / "ComfyUI" / "models" / "vae",
    "ControlNet": ROOT_DIR / "ComfyUI" / "models" / "controlnet",
}

MODEL_EXAMPLES = {
    "UNet/GGUF": "flux1-dev-Q4_K_S.gguf",
    "Text Encoders": "t5xxl_fp8.safetensors (or t5xxl_fp16.safetensors)",
    "CLIP": "clip_l.safetensors",
    "VAE": "ae.sft",
    "ControlNet": "flux-depth-controlnet.safetensors",
}

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".gguf", ".sft"}


def print_line(label: str, value: str) -> None:
    print(f"{label:<24} {value}")


def fetch_object_info() -> dict:
    with urllib.request.urlopen(f"{COMFYUI_BASE_URL}/object_info", timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def check_node_groups(node_names: list[str]) -> tuple[dict[str, bool], list[str]]:
    lowered = [name.lower() for name in node_names]
    result: dict[str, bool] = {}
    missing: list[str] = []

    for label, patterns in NODE_GROUPS.items():
        present = any(any(pattern in node for pattern in patterns) for node in lowered)
        result[label] = present
        if not present:
            missing.append(label)
    return result, missing


def check_imports() -> tuple[dict[str, bool], list[str]]:
    result: dict[str, bool] = {}
    missing: list[str] = []
    for module_name, meta in IMPORT_CHECKS.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                importlib.import_module(module_name)
            result[module_name] = True
        except Exception:
            result[module_name] = False
            if meta["required"]:
                missing.append(module_name)
    return result, missing


def count_model_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    count = 0
    for file in path.iterdir():
        if file.is_file() and file.suffix.lower() in MODEL_EXTENSIONS:
            count += 1
    return count


def check_models() -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    missing: list[str] = []
    for label, path in MODEL_DIRS.items():
        count = count_model_files(path)
        counts[label] = count
        if count == 0:
            missing.append(label)
    return counts, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Check FLUX demo readiness on local ComfyUI.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 if any required item is missing.",
    )
    args = parser.parse_args()

    print_line("Workspace", str(ROOT_DIR))
    print_line("Python", sys.executable)
    print_line("ComfyUI URL", COMFYUI_BASE_URL)

    overall_missing: list[str] = []

    try:
        object_info = fetch_object_info()
        node_names = list(object_info.keys())
        print_line("ComfyUI object_info", f"ok ({len(node_names)} nodes)")
    except urllib.error.URLError as exc:
        print_line("ComfyUI object_info", f"unreachable ({exc})")
        if args.strict:
            return 1
        return 0
    except Exception as exc:
        print_line("ComfyUI object_info", f"error ({exc})")
        if args.strict:
            return 1
        return 0

    node_status, missing_node_groups = check_node_groups(node_names)
    for label, status in node_status.items():
        print_line(label, "ok" if status else "missing")
    overall_missing.extend([f"nodes:{name}" for name in missing_node_groups])

    import_status, missing_imports = check_imports()
    for module_name, status in import_status.items():
        meta = IMPORT_CHECKS[module_name]
        role = "required" if meta["required"] else "optional"
        print_line(
            f"Import {module_name}",
            f"{'ok' if status else 'missing'} ({role}: {meta['desc']})",
        )
    overall_missing.extend([f"import:{name}" for name in missing_imports])

    model_counts, missing_models = check_models()
    for label, count in model_counts.items():
        print_line(f"Models {label}", str(count))
        print_line(f"Path {label}", str(MODEL_DIRS[label]))
        print_line(f"Example {label}", MODEL_EXAMPLES[label])
    overall_missing.extend([f"models:{name}" for name in missing_models])

    if overall_missing:
        print("\nMissing items:")
        for item in overall_missing:
            print(f"- {item}")
    else:
        print("\nAll checks passed.")

    if args.strict and overall_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
