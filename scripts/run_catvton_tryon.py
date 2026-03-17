#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.tryon_templates import CATVTON_ROOT, TRYON_TEMPLATE_IMAGES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CatVTON try-on with a cloth image and a model template.")
    parser.add_argument("--cloth-image", type=Path, default=None)
    parser.add_argument("--person-image", type=Path, default=None)
    parser.add_argument("--person-template", default="woman_1", choices=sorted(TRYON_TEMPLATE_IMAGES))
    parser.add_argument("--cloth-type", default="overall", choices=["upper", "lower", "overall"])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance", type=float, default=2.5)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--mixed-precision", default="bf16", choices=["no", "fp16", "bf16"])
    parser.add_argument("--base-model-path", default="booksforcharlie/stable-diffusion-inpainting")
    parser.add_argument("--resume-path", default="zhengchong/CatVTON")
    parser.add_argument("--hf-endpoint", default="https://hf-mirror.com")
    parser.add_argument("--catvton-root", type=Path, default=CATVTON_ROOT)
    parser.add_argument("--print-templates", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.print_templates:
        for name, path in TRYON_TEMPLATE_IMAGES.items():
            print(f"{name}: {path}")
        return 0

    if args.cloth_image is None or args.output is None:
        print("ERROR: --cloth-image and --output are required unless --print-templates is used")
        return 1

    if not args.cloth_image.exists():
        print(f"ERROR: cloth image not found: {args.cloth_image}")
        return 1

    person_image = args.person_image or TRYON_TEMPLATE_IMAGES[args.person_template]
    if not person_image.exists():
        print(f"ERROR: person image not found: {person_image}")
        return 1

    os.environ.setdefault("HF_ENDPOINT", args.hf_endpoint)
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    catvton_root = args.catvton_root.resolve()
    sys.path.insert(0, str(catvton_root))

    import torch
    from diffusers.image_processor import VaeImageProcessor
    from huggingface_hub import snapshot_download
    from PIL import Image

    from model.cloth_masker import AutoMasker
    from model.pipeline import CatVTONPipeline
    from utils import init_weight_dtype, resize_and_crop, resize_and_padding

    repo_path = snapshot_download(repo_id=args.resume_path)
    pipeline = CatVTONPipeline(
        base_ckpt=args.base_model_path,
        attn_ckpt=repo_path,
        attn_ckpt_version="mix",
        weight_dtype=init_weight_dtype(args.mixed_precision),
        use_tf32=True,
        device="cuda",
        skip_safety_check=True,
    )
    automasker = AutoMasker(
        densepose_ckpt=os.path.join(repo_path, "DensePose"),
        schp_ckpt=os.path.join(repo_path, "SCHP"),
        device="cuda",
    )
    mask_processor = VaeImageProcessor(
        vae_scale_factor=8,
        do_normalize=False,
        do_binarize=True,
        do_convert_grayscale=True,
    )

    generator = torch.Generator(device="cuda").manual_seed(args.seed)
    person = resize_and_crop(Image.open(person_image).convert("RGB"), (args.width, args.height))
    cloth = resize_and_padding(Image.open(args.cloth_image).convert("RGB"), (args.width, args.height))
    mask = automasker(person, args.cloth_type)["mask"]
    mask = mask_processor.blur(mask, blur_factor=9)

    result = pipeline(
        image=person,
        condition_image=cloth,
        mask=mask,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        generator=generator,
    )[0]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(f"person_image: {person_image}")
    print(f"cloth_image: {args.cloth_image}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
