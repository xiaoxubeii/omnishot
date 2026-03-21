import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.reference_style_cleanup import cleanup_style_reference_image, prepare_style_reference_images


def _make_reference_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), (48, 160, 92))
    for x in range(20, 44):
        for y in range(18, 46):
            image.putpixel((x, y), (220, 32, 32))
    return image


def _make_subject_cutout() -> Image.Image:
    cutout = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(20, 44):
        for y in range(18, 46):
            cutout.putpixel((x, y), (220, 32, 32, 255))
    return cutout


def _image_to_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class CleanupStyleReferenceImageTests(unittest.TestCase):
    def test_cleanup_style_reference_image_removes_subject_and_marks_reliable(self) -> None:
        result = cleanup_style_reference_image(
            reference_image=_make_reference_image(),
            subject_cutout_rgba=_make_subject_cutout(),
        )

        self.assertTrue(result["cleanup_applied"])
        self.assertTrue(result["cleanup_reliable"])
        self.assertTrue(result["used_cleaned_reference"])
        self.assertIsNotNone(result["mask_image"])
        self.assertGreater(result["mask_ratio"], 0.05)
        self.assertNotEqual(result["cleaned_image"].getpixel((32, 32)), (220, 32, 32))
        self.assertEqual(result["cleaned_image"].getpixel((5, 5)), (48, 160, 92))


class PrepareStyleReferenceImagesTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_style_reference_images_writes_debug_artifacts_and_summary(self) -> None:
        reference_image = _make_reference_image()
        reference_bytes = _image_to_bytes(reference_image)

        async def fake_extractor(**_: object) -> Image.Image:
            return _make_subject_cutout()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            original_path = tmp_path / "reference.png"
            original_path.write_bytes(reference_bytes)

            prepared_images, metadata = await prepare_style_reference_images(
                comfy=None,
                references=[{"image_bytes": reference_bytes, "filename": "reference.png"}],
                original_paths=[original_path],
                debug_dir=tmp_path,
                timeout_seconds=30,
                extractor=fake_extractor,
            )

            self.assertEqual(len(prepared_images), 1)
            self.assertNotEqual(prepared_images[0].getpixel((32, 32)), (220, 32, 32))
            self.assertTrue(metadata["style_reference_cleanup_applied"])
            self.assertTrue(metadata["style_reference_cleanup_reliable"])
            self.assertEqual(len(metadata["style_reference_cleanup_items"]), 1)

            item = metadata["style_reference_cleanup_items"][0]
            self.assertTrue(item["cleanup_applied"])
            self.assertTrue(item["cleanup_reliable"])
            self.assertEqual(item["original_path"], str(original_path))
            self.assertTrue(Path(item["mask_path"]).exists())
            self.assertTrue(Path(item["cleaned_path"]).exists())

    async def test_prepare_style_reference_images_falls_back_to_original_when_extractor_fails(self) -> None:
        reference_image = _make_reference_image()
        reference_bytes = _image_to_bytes(reference_image)

        async def failing_extractor(**_: object) -> Image.Image:
            raise RuntimeError("extract failed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            original_path = tmp_path / "reference.png"
            original_path.write_bytes(reference_bytes)

            prepared_images, metadata = await prepare_style_reference_images(
                comfy=None,
                references=[{"image_bytes": reference_bytes, "filename": "reference.png"}],
                original_paths=[original_path],
                debug_dir=tmp_path,
                timeout_seconds=30,
                extractor=failing_extractor,
            )

            self.assertEqual(len(prepared_images), 1)
            self.assertEqual(prepared_images[0].getpixel((32, 32)), (220, 32, 32))
            self.assertFalse(metadata["style_reference_cleanup_applied"])
            self.assertFalse(metadata["style_reference_cleanup_reliable"])

            item = metadata["style_reference_cleanup_items"][0]
            self.assertFalse(item["cleanup_applied"])
            self.assertFalse(item["cleanup_reliable"])
            self.assertFalse(item["used_cleaned_reference"])
            self.assertIsNone(item["mask_path"])
            self.assertIsNone(item["cleaned_path"])
            self.assertIn("extract failed", item["status"])
