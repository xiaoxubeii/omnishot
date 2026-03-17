from pathlib import Path

from app.config import ROOT_DIR


CATVTON_ROOT = ROOT_DIR.parent / "CatVTON"

TRYON_TEMPLATE_IMAGES = {
    "woman_1": CATVTON_ROOT / "resource" / "demo" / "example" / "person" / "women" / "1-model_3.png",
    "woman_2": CATVTON_ROOT / "resource" / "demo" / "example" / "person" / "women" / "2-model_4.png",
    "woman_3": CATVTON_ROOT / "resource" / "demo" / "example" / "person" / "women" / "049713_0.jpg",
    "man_1": CATVTON_ROOT / "resource" / "demo" / "example" / "person" / "men" / "model_5.png",
    "man_2": CATVTON_ROOT / "resource" / "demo" / "example" / "person" / "men" / "Simon_1.png",
}


def list_tryon_templates() -> list[dict]:
    return [
        {
            "name": name,
            "path": str(path),
            "exists": path.exists(),
        }
        for name, path in sorted(TRYON_TEMPLATE_IMAGES.items())
    ]

