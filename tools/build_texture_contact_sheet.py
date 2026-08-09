#!/usr/bin/env python3
"""Build a labeled contact sheet from extracted texture images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()

    paths = sorted(
        path
        for path in args.input.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tga"}
    )
    if not paths:
        raise SystemExit(f"No texture images found below {args.input}")

    tile_width = 288
    tile_height = 330
    preview_size = (256, 256)
    rows = (len(paths) + args.columns - 1) // args.columns
    sheet = Image.new("RGB", (args.columns * tile_width, rows * tile_height), (22, 24, 27))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, image_path in enumerate(paths):
        with Image.open(image_path) as source:
            preview = ImageOps.contain(source.convert("RGB"), preview_size)
        x = (index % args.columns) * tile_width
        y = (index // args.columns) * tile_height
        image_x = x + (tile_width - preview.width) // 2
        image_y = y + 12 + (preview_size[1] - preview.height) // 2
        sheet.paste(preview, (image_x, image_y))
        label = image_path.relative_to(args.input).as_posix()
        draw.multiline_text((x + 12, y + 278), label, fill=(235, 237, 240), font=font, spacing=2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"{args.output} ({len(paths)} textures)")


if __name__ == "__main__":
    main()
