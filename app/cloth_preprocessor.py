import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from app.comfy_client import ComfyClient

LOGGER = logging.getLogger(__name__)


def _build_cutout_workflow(image_name: str) -> dict:
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_name,
            },
        },
        "2": {
            "class_type": "BiRefNetRMBG",
            "inputs": {
                "image": ["1", 0],
                "model": "BiRefNet-HR-matting",
                "mask_blur": 0,
                "mask_offset": 0,
                "invert_output": False,
                "refine_foreground": True,
                "background": "Alpha",
                "background_color": "#000000",
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["2", 0],
                "filename_prefix": "tryon-cutout",
            },
        },
    }


def _load_rgba_image(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes)).convert("RGBA")


def _keep_largest_alpha_component(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = np.array(rgba.getchannel("A"))
    mask = alpha > 8
    if not mask.any():
        return rgba

    labels, total = ndimage.label(mask)
    if total > 1:
        counts = np.bincount(labels.ravel())
        counts[0] = 0
        keep = labels == counts.argmax()
        alpha = np.where(keep, alpha, 0).astype(np.uint8)
        rgba.putalpha(Image.fromarray(alpha, mode="L"))
    return rgba


def _crop_and_flatten(image: Image.Image) -> Image.Image:
    rgba = _keep_largest_alpha_component(image)
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        pad = max(12, int(max(rgba.size) * 0.03))
        bbox = (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(rgba.width, x1 + pad),
            min(rgba.height, y1 + pad),
        )
        rgba = rgba.crop(bbox)

    flattened = Image.new("RGB", rgba.size, (255, 255, 255))
    flattened.paste(rgba, mask=rgba.getchannel("A"))
    return flattened


def _extract_cutout_locally(image_bytes: bytes) -> Image.Image:
    return _keep_largest_alpha_component(_load_rgba_image(image_bytes))


def _preprocess_locally(image_bytes: bytes) -> Image.Image:
    # Fast local fallback when ComfyUI RMBG is unavailable. This does not
    # remove the background aggressively, but it keeps try-on smoke tests and
    # clean catalog images runnable without a live ComfyUI worker.
    return _crop_and_flatten(_extract_cutout_locally(image_bytes))


async def extract_cutout_rgba(
    *,
    comfy: ComfyClient,
    image_bytes: bytes,
    filename: str,
    timeout_seconds: int,
) -> Image.Image:
    try:
        comfy_filename = await comfy.upload_image(image_bytes, filename)
        workflow = _build_cutout_workflow(comfy_filename)
        result = await comfy.run_workflow(
            workflow,
            preferred_output_nodes=["3"],
            timeout_seconds=timeout_seconds,
        )
        return _keep_largest_alpha_component(_load_rgba_image(result.image_bytes))
    except Exception as exc:
        LOGGER.warning("ComfyUI cutout extraction failed, falling back to local cutout: %s", exc)
        return _extract_cutout_locally(image_bytes)


def composite_foreground_locked(
    *,
    foreground_rgba: Image.Image,
    background_rgb: Image.Image,
    feather_radius: float = 1.5,
) -> Image.Image:
    background = background_rgb.convert("RGBA")
    source = foreground_rgba.convert("RGBA")

    scale = min(
        background.width / max(source.width, 1),
        background.height / max(source.height, 1),
    )
    resized_size = (
        max(1, int(round(source.width * scale))),
        max(1, int(round(source.height * scale))),
    )
    resized = source.resize(resized_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", background.size, (0, 0, 0, 0))
    offset = (
        (background.width - resized.width) // 2,
        (background.height - resized.height) // 2,
    )
    canvas.alpha_composite(resized, offset)

    alpha = canvas.getchannel("A")
    if feather_radius > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather_radius))
        canvas.putalpha(alpha)

    locked = background.copy()
    locked.alpha_composite(canvas)
    return locked.convert("RGB")


async def preprocess_cloth_image(
    *,
    comfy: ComfyClient,
    image_bytes: bytes,
    filename: str,
    save_to: Path,
    timeout_seconds: int,
) -> Path:
    try:
        comfy_filename = await comfy.upload_image(image_bytes, filename)
        workflow = _build_cutout_workflow(comfy_filename)
        result = await comfy.run_workflow(
            workflow,
            preferred_output_nodes=["3"],
            timeout_seconds=timeout_seconds,
        )
        prepared = _crop_and_flatten(_load_rgba_image(result.image_bytes))
    except Exception as exc:
        LOGGER.warning("ComfyUI cloth preprocessing failed, falling back to local remover: %s", exc)
        prepared = _preprocess_locally(image_bytes)

    save_to.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(save_to)
    return save_to
