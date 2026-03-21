from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.cloth_preprocessor import extract_cutout_rgba

LOGGER = logging.getLogger(__name__)

_MASK_THRESHOLD = 16

StyleReferenceExtractor = Callable[..., Awaitable[Image.Image]]


def _load_rgb_image(image_bytes: bytes) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def _normalize_cutout_size(subject_cutout_rgba: Image.Image, size: tuple[int, int]) -> Image.Image:
    cutout = subject_cutout_rgba.convert("RGBA")
    if cutout.size == size:
        return cutout
    return cutout.resize(size, Image.Resampling.LANCZOS)


def _expand_and_feather_mask(mask_image: Image.Image, image_size: tuple[int, int]) -> Image.Image:
    mask = np.array(mask_image.convert("L"))
    if not np.any(mask > 0):
        return mask_image.convert("L")

    short_side = max(1, min(image_size))
    dilate_size = max(5, (short_side // 18) | 1)
    blur_size = max(5, (short_side // 24) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_size, dilate_size))
    expanded = cv2.dilate(mask, kernel, iterations=1)
    feathered = cv2.GaussianBlur(expanded, (blur_size, blur_size), 0)
    return Image.fromarray(feathered.astype(np.uint8), mode="L")


def _collect_mask_stats(mask_image: Image.Image) -> dict[str, Any]:
    binary_mask = np.array(mask_image.convert("L")) > _MASK_THRESHOLD
    coverage = float(binary_mask.mean()) if binary_mask.size else 0.0
    bbox = Image.fromarray((binary_mask.astype(np.uint8) * 255), mode="L").getbbox()
    touches_border = bool(
        binary_mask.any()
        and (
            binary_mask[0, :].any()
            or binary_mask[-1, :].any()
            or binary_mask[:, 0].any()
            or binary_mask[:, -1].any()
        )
    )

    reasons: list[str] = []
    if bbox is None:
        reasons.append("empty-mask")
    if coverage < 0.01:
        reasons.append("mask-too-small")
    if coverage > 0.55:
        reasons.append("mask-too-large")
    if touches_border:
        reasons.append("mask-touches-border")

    return {
        "bbox": list(bbox) if bbox else None,
        "mask_ratio": round(coverage, 4),
        "touches_border": touches_border,
        "cleanup_reliable": not reasons,
        "status": "ok" if not reasons else ",".join(reasons),
    }


def _inpaint_reference_image(reference_image: Image.Image, mask_image: Image.Image) -> Image.Image:
    rgb_array = np.array(reference_image.convert("RGB"))
    inpaint_mask = np.where(np.array(mask_image.convert("L")) > _MASK_THRESHOLD, 255, 0).astype(np.uint8)
    radius = max(3, min(reference_image.size) // 32)
    cleaned_bgr = cv2.inpaint(
        cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR),
        inpaint_mask,
        radius,
        cv2.INPAINT_TELEA,
    )
    cleaned_rgb = cv2.cvtColor(cleaned_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cleaned_rgb, mode="RGB")


def cleanup_style_reference_image(
    *,
    reference_image: Image.Image,
    subject_cutout_rgba: Image.Image,
) -> dict[str, Any]:
    normalized_cutout = _normalize_cutout_size(subject_cutout_rgba, reference_image.size)
    alpha_mask = normalized_cutout.getchannel("A").point(lambda value: 255 if value > 8 else 0)
    expanded_mask = _expand_and_feather_mask(alpha_mask, reference_image.size)
    stats = _collect_mask_stats(expanded_mask)

    if stats["bbox"] is None:
        return {
            "cleaned_image": reference_image.copy(),
            "mask_image": None,
            "cleanup_applied": False,
            "used_cleaned_reference": False,
            **stats,
        }

    cleaned_image = _inpaint_reference_image(reference_image, expanded_mask)
    return {
        "cleaned_image": cleaned_image,
        "mask_image": expanded_mask,
        "cleanup_applied": True,
        "used_cleaned_reference": True,
        **stats,
    }


def _build_cleanup_metadata(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "style_reference_cleanup_applied": any(item["cleanup_applied"] for item in items),
        "style_reference_cleanup_reliable": bool(items) and all(item["cleanup_reliable"] for item in items),
        "style_reference_cleanup_paths": [
            {
                "index": item["index"],
                "original_path": item["original_path"],
                "mask_path": item["mask_path"],
                "cleaned_path": item["cleaned_path"],
            }
            for item in items
        ],
        "style_reference_cleanup_items": items,
    }


async def prepare_style_reference_images(
    *,
    comfy,
    references: list[dict[str, bytes | str]],
    original_paths: list[Path],
    debug_dir: Path,
    timeout_seconds: int,
    extractor: StyleReferenceExtractor | None = None,
) -> tuple[list[Image.Image], dict[str, Any]]:
    active_extractor = extractor or extract_cutout_rgba
    debug_dir.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex[:8]
    prepared_images: list[Image.Image] = []
    items: list[dict[str, Any]] = []

    for index, reference in enumerate(references):
        reference_bytes = bytes(reference["image_bytes"])
        filename = str(reference["filename"])
        reference_image = _load_rgb_image(reference_bytes)
        original_path = str(original_paths[index]) if index < len(original_paths) else None

        item: dict[str, Any] = {
            "index": index + 1,
            "filename": filename,
            "original_path": original_path,
            "mask_path": None,
            "cleaned_path": None,
        }

        try:
            subject_cutout = await active_extractor(
                comfy=comfy,
                image_bytes=reference_bytes,
                filename=filename,
                timeout_seconds=timeout_seconds,
            )
            cleanup_result = cleanup_style_reference_image(
                reference_image=reference_image,
                subject_cutout_rgba=subject_cutout,
            )
            item.update(
                {
                    key: value
                    for key, value in cleanup_result.items()
                    if key not in {"cleaned_image", "mask_image"}
                }
            )

            if cleanup_result["cleanup_applied"]:
                mask_path = debug_dir / f"reference-scene-style-mask-{run_id}-{index + 1}.png"
                cleaned_path = debug_dir / f"reference-scene-style-clean-{run_id}-{index + 1}.png"
                cleanup_result["mask_image"].save(mask_path)
                cleanup_result["cleaned_image"].save(cleaned_path)
                item["mask_path"] = str(mask_path)
                item["cleaned_path"] = str(cleaned_path)
                prepared_images.append(cleanup_result["cleaned_image"])
            else:
                prepared_images.append(reference_image)
        except Exception as exc:
            LOGGER.warning("Style reference cleanup failed for %s: %s", filename, exc)
            prepared_images.append(reference_image)
            item.update(
                {
                    "bbox": None,
                    "mask_ratio": 0.0,
                    "touches_border": False,
                    "cleanup_applied": False,
                    "cleanup_reliable": False,
                    "used_cleaned_reference": False,
                    "status": f"cleanup-failed:{exc}",
                }
            )

        items.append(item)

    return prepared_images, _build_cleanup_metadata(items)
