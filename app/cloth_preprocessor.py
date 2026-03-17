import io
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from app.comfy_client import ComfyClient


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


async def preprocess_cloth_image(
    *,
    comfy: ComfyClient,
    image_bytes: bytes,
    filename: str,
    save_to: Path,
    timeout_seconds: int,
) -> Path:
    comfy_filename = await comfy.upload_image(image_bytes, filename)
    workflow = _build_cutout_workflow(comfy_filename)
    result = await comfy.run_workflow(
        workflow,
        preferred_output_nodes=["3"],
        timeout_seconds=timeout_seconds,
    )
    prepared = _crop_and_flatten(Image.open(io.BytesIO(result.image_bytes)))
    save_to.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(save_to)
    return save_to
