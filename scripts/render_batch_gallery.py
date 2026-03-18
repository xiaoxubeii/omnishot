#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TYPE_ORDER = {"scene": 0, "edit": 1, "tryon": 2, "tryon_angle": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a contact sheet and HTML gallery from a batch output directory.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--thumb-width", type=int, default=420)
    parser.add_argument("--thumb-height", type=int, default=420)
    parser.add_argument("--columns", type=int, default=4)
    return parser.parse_args()


def load_records(manifest_path: Path) -> list[dict]:
    records: list[dict] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("status") != "ok":
                continue
            saved_path = Path(str(record.get("saved_path", "")))
            if saved_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            records.append(record)
    records.sort(key=lambda item: (TYPE_ORDER.get(str(item.get("type")), 99), str(item.get("variant", ""))))
    return records


def render_contact_sheet(output_dir: Path, records: list[dict], thumb_width: int, thumb_height: int, columns: int) -> Path:
    rows = max(1, math.ceil(len(records) / max(columns, 1)))
    margin = 28
    gutter = 20
    caption_height = 78
    width = margin * 2 + columns * thumb_width + (columns - 1) * gutter
    height = margin * 2 + rows * (thumb_height + caption_height) + (rows - 1) * gutter

    sheet = Image.new("RGB", (width, height), (246, 241, 234))
    draw = ImageDraw.Draw(sheet)

    for index, record in enumerate(records):
        row = index // columns
        col = index % columns
        x = margin + col * (thumb_width + gutter)
        y = margin + row * (thumb_height + caption_height + gutter)

        image_path = ROOT_DIR / str(record["saved_path"])
        image = Image.open(image_path).convert("RGB")
        thumb = ImageOps.contain(image, (thumb_width, thumb_height))
        frame = Image.new("RGB", (thumb_width, thumb_height), (255, 255, 255))
        paste_x = (thumb_width - thumb.width) // 2
        paste_y = (thumb_height - thumb.height) // 2
        frame.paste(thumb, (paste_x, paste_y))
        sheet.paste(frame, (x, y))

        draw.rectangle(
            [x, y, x + thumb_width, y + thumb_height],
            outline=(210, 199, 184),
            width=2,
        )
        draw.text((x, y + thumb_height + 10), f"{record['type']} / {record['variant']}", fill=(42, 31, 20))
        draw.text((x, y + thumb_height + 34), image_path.name, fill=(101, 82, 62))

    target = output_dir / "contact-sheet.png"
    sheet.save(target)
    return target


def build_html(output_dir: Path, records: list[dict], contact_sheet_path: Path) -> Path:
    cards = []
    for record in records:
        image_path = (ROOT_DIR / str(record["saved_path"])).resolve()
        relative_path = image_path.relative_to(output_dir)
        cards.append(
            f"""
            <article class="card">
              <img src="{relative_path.as_posix()}" alt="{record['variant']}">
              <div class="meta">
                <strong>{record['type']}</strong>
                <span>{record['variant']}</span>
                <code>{record.get('generator_mode', '')}</code>
              </div>
            </article>
            """
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Batch Gallery</title>
  <style>
    body {{
      margin: 0;
      background: #f2ece4;
      color: #24180f;
      font-family: "Noto Serif SC", serif;
    }}
    .wrap {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px;
    }}
    .sheet {{
      width: 100%;
      border-radius: 20px;
      border: 1px solid #d8c9b7;
      margin-bottom: 24px;
      background: #fff;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 18px;
    }}
    .card {{
      background: #fff;
      border: 1px solid #decfbd;
      border-radius: 18px;
      overflow: hidden;
    }}
    .card img {{
      width: 100%;
      display: block;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      background: #f8f5f0;
    }}
    .meta {{
      display: grid;
      gap: 6px;
      padding: 14px;
    }}
    code {{
      color: #8f5c2e;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Batch Gallery</h1>
    <p>Output dir: {output_dir}</p>
    <img class="sheet" src="{contact_sheet_path.name}" alt="Contact sheet">
    <div class="grid">
      {''.join(cards)}
    </div>
  </div>
</body>
</html>
"""
    target = output_dir / "gallery.html"
    target.write_text(html, encoding="utf-8")
    return target


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    records = load_records(manifest_path)
    if not records:
        raise SystemExit(f"no successful image records found in: {manifest_path}")

    contact_sheet_path = render_contact_sheet(
        output_dir=output_dir,
        records=records,
        thumb_width=args.thumb_width,
        thumb_height=args.thumb_height,
        columns=args.columns,
    )
    gallery_path = build_html(output_dir, records, contact_sheet_path)
    print(f"records: {len(records)}")
    print(f"contact_sheet: {contact_sheet_path}")
    print(f"gallery: {gallery_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
