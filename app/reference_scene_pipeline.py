from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageColor, ImageFilter, ImageOps


@dataclass(slots=True)
class ReferenceSceneCompositeResult:
    image: Image.Image
    bbox: tuple[int, int, int, int] | None
    shadow_applied: bool
    reflection_applied: bool
    color_harmonize_strength: float


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _resize_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()
    return image.resize(size, Image.Resampling.LANCZOS)


def _average_color(image: Image.Image) -> tuple[int, int, int]:
    sample = image.convert("RGB").resize((1, 1), Image.Resampling.BILINEAR)
    return sample.getpixel((0, 0))


def build_neutral_product_preview(
    foreground_rgba: Image.Image,
    *,
    background_color: str = "#f3eee7",
) -> Image.Image:
    foreground = foreground_rgba.convert("RGBA")
    canvas = Image.new("RGBA", foreground.size, ImageColor.getrgb(background_color) + (255,))

    alpha = foreground.getchannel("A")
    if alpha.getbbox():
        soft_shadow = alpha.filter(ImageFilter.GaussianBlur(max(8, foreground.width // 48)))
        soft_shadow = ImageChops.offset(soft_shadow, 0, max(12, foreground.height // 40))
        shadow_layer = Image.new("RGBA", foreground.size, (102, 82, 60, 0))
        shadow_layer.putalpha(soft_shadow.point(lambda value: int(value * 0.22)))
        canvas.alpha_composite(shadow_layer)

    canvas.alpha_composite(foreground)
    return canvas.convert("RGB")


def composite_reference_scene(
    *,
    foreground_rgba: Image.Image,
    background_rgb: Image.Image,
    shadow_strength: float,
    reflection_strength: float,
    color_harmonize_strength: float,
) -> ReferenceSceneCompositeResult:
    background = background_rgb.convert("RGBA")
    foreground = _resize_canvas(foreground_rgba.convert("RGBA"), background.size)
    alpha = foreground.getchannel("A")
    bbox = alpha.getbbox()

    shadow_strength = _clamp(shadow_strength, 0.0, 1.0)
    reflection_strength = _clamp(reflection_strength, 0.0, 1.0)
    color_harmonize_strength = _clamp(color_harmonize_strength, 0.0, 1.0)

    shadow_applied = False
    reflection_applied = False

    if bbox and shadow_strength > 0:
        local_region = background.crop(
            (
                max(0, bbox[0] - 24),
                max(0, bbox[1] - 24),
                min(background.width, bbox[2] + 24),
                min(background.height, bbox[3] + 24),
            )
        )
        avg_r, avg_g, avg_b = _average_color(local_region)
        shadow_rgb = (
            int(avg_r * 0.28),
            int(avg_g * 0.24),
            int(avg_b * 0.22),
        )
        shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(14, background.width // 28)))
        shadow_alpha = ImageChops.offset(
            shadow_alpha,
            max(0, background.width // 180),
            max(10, background.height // 28),
        )
        shadow_layer = Image.new("RGBA", background.size, shadow_rgb + (0,))
        shadow_layer.putalpha(shadow_alpha.point(lambda value: int(value * (0.45 * shadow_strength))))
        background.alpha_composite(shadow_layer)
        shadow_applied = True

    if bbox and reflection_strength > 0:
        object_crop = foreground.crop(bbox)
        reflected = ImageOps.flip(object_crop)
        reflected = reflected.resize(
            (object_crop.width, max(1, int(object_crop.height * 0.42))),
            Image.Resampling.LANCZOS,
        )
        reflected_alpha = reflected.getchannel("A")
        fade = Image.linear_gradient("L").resize(reflected.size, Image.Resampling.BILINEAR)
        fade = ImageOps.flip(fade)
        reflected.putalpha(
            ImageChops.multiply(
                reflected_alpha,
                fade.point(lambda value: int(value * (0.52 * reflection_strength))),
            )
        )
        reflection_canvas = Image.new("RGBA", background.size, (0, 0, 0, 0))
        reflection_top = min(
            background.height - reflected.height,
            bbox[3] + max(6, background.height // 120),
        )
        if reflection_top >= 0 and reflection_top < background.height:
            reflection_canvas.alpha_composite(reflected, (bbox[0], reflection_top))
            reflection_canvas = reflection_canvas.filter(ImageFilter.GaussianBlur(1.2))
            background.alpha_composite(reflection_canvas)
            reflection_applied = True

    if bbox and color_harmonize_strength > 0:
        local_region = background.crop(
            (
                max(0, bbox[0] - 36),
                max(0, bbox[1] - 36),
                min(background.width, bbox[2] + 36),
                min(background.height, bbox[3] + 36),
            )
        )
        tint = Image.new("RGB", background.size, _average_color(local_region))
        harmonized_rgb = Image.blend(
            foreground.convert("RGB"),
            tint,
            0.18 * color_harmonize_strength,
        )
        foreground = harmonized_rgb.convert("RGBA")
        foreground.putalpha(alpha)

    background.alpha_composite(foreground)
    return ReferenceSceneCompositeResult(
        image=background.convert("RGB"),
        bbox=bbox,
        shadow_applied=shadow_applied,
        reflection_applied=reflection_applied,
        color_harmonize_strength=color_harmonize_strength,
    )
