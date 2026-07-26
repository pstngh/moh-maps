from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art_sources"
OUTPUT = ROOT / "main" / "textures" / "codex_nuke"
SIZE = 512


def mirror_tile(image: Image.Image) -> Image.Image:
    """Guarantee four-edge continuity without copying pixels across the seam."""
    mode = "RGBA" if "A" in image.getbands() else "RGB"
    image = ImageOps.fit(image.convert(mode), (SIZE // 2, SIZE // 2), method=Image.Resampling.LANCZOS)
    result = Image.new(mode, (SIZE, SIZE))
    result.paste(image, (0, 0))
    result.paste(ImageOps.mirror(image), (SIZE // 2, 0))
    result.paste(ImageOps.flip(image), (0, SIZE // 2))
    result.paste(ImageOps.flip(ImageOps.mirror(image)), (SIZE // 2, SIZE // 2))
    return result


def colorize_gray(image: Image.Image, black: tuple[int, int, int], white: tuple[int, int, int]) -> Image.Image:
    return ImageOps.colorize(ImageOps.grayscale(image), black=black, white=white)


def save_tga(image: Image.Image, name: str) -> None:
    image.save(OUTPUT / name, format="TGA", compression=None)


def matching_edges(image: Image.Image) -> Image.Image:
    """Close a mathematically periodic precision pattern at the stored edge."""
    image = image.copy()
    pixels = image.load()
    for y in range(image.height):
        pixels[image.width - 1, y] = pixels[0, y]
    for x in range(image.width):
        pixels[x, image.height - 1] = pixels[x, 0]
    return image


def generated_ceiling_tile() -> Image.Image:
    tile = Image.new("RGB", (SIZE, SIZE), (184, 188, 187))
    draw = ImageDraw.Draw(tile)
    for coordinate in range(0, SIZE, 128):
        draw.line((coordinate, 0, coordinate, SIZE), fill=(116, 121, 122), width=3)
        draw.line((coordinate + 3, 0, coordinate + 3, SIZE), fill=(214, 216, 213), width=1)
        draw.line((0, coordinate, SIZE, coordinate), fill=(116, 121, 122), width=3)
        draw.line((0, coordinate + 3, SIZE, coordinate + 3), fill=(214, 216, 213), width=1)
    return tile


def generated_grating() -> Image.Image:
    tile = Image.new("RGB", (SIZE, SIZE), (39, 45, 47))
    draw = ImageDraw.Draw(tile)
    for coordinate in range(-SIZE, SIZE * 2, 32):
        draw.line((coordinate, 0, coordinate - SIZE, SIZE), fill=(102, 110, 112), width=6)
        draw.line((coordinate + 8, 0, coordinate + 8 - SIZE, SIZE), fill=(24, 29, 31), width=3)
        draw.line((coordinate, 0, coordinate + SIZE, SIZE), fill=(83, 91, 93), width=5)
    return tile


def generated_glass() -> Image.Image:
    return Image.new("RGBA", (SIZE, SIZE), (111, 148, 165, 76))


def generated_chainlink() -> Image.Image:
    fence = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fence)
    spacing = 64
    for coordinate in range(-SIZE, SIZE * 2, spacing):
        draw.line((coordinate, 0, coordinate - SIZE, SIZE), fill=(154, 162, 163, 255), width=5)
        draw.line((coordinate + 5, 0, coordinate + 5 - SIZE, SIZE), fill=(70, 76, 78, 230), width=2)
        draw.line((coordinate, 0, coordinate + SIZE, SIZE), fill=(154, 162, 163, 255), width=5)
        draw.line((coordinate + 5, 0, coordinate + 5 + SIZE, SIZE), fill=(70, 76, 78, 230), width=2)
    return fence


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    painted = mirror_tile(Image.open(SOURCE / "painted_concrete_source.png"))
    floor = mirror_tile(Image.open(SOURCE / "concrete_floor_source.png"))
    asphalt = mirror_tile(Image.open(SOURCE / "asphalt_source.png"))
    corrugated = mirror_tile(Image.open(SOURCE / "corrugated_blue_source.png"))
    grass = mirror_tile(Image.open(SOURCE / "grass_source.png"))
    gravel = mirror_tile(Image.open(SOURCE / "gravel_source.png"))

    save_tga(painted, "painted_concrete.tga")
    save_tga(
        colorize_gray(painted, (63, 76, 83), (178, 197, 201)),
        "painted_concrete_blue.tga",
    )
    save_tga(floor, "concrete_floor.tga")
    save_tga(
        ImageEnhance.Brightness(colorize_gray(floor, (45, 49, 52), (150, 155, 157))).enhance(0.85),
        "concrete_dark.tga",
    )
    save_tga(asphalt, "asphalt.tga")
    save_tga(grass, "grass.tga")
    save_tga(gravel, "gravel.tga")
    save_tga(corrugated, "corrugated_blue.tga")
    save_tga(
        colorize_gray(corrugated, (50, 55, 58), (184, 189, 190)),
        "corrugated_gray.tga",
    )
    save_tga(
        colorize_gray(floor, (49, 55, 59), (167, 174, 176)),
        "metal_trim.tga",
    )
    save_tga(matching_edges(generated_ceiling_tile()), "ceiling_tile.tga")
    save_tga(matching_edges(generated_grating()), "metal_grating.tga")
    save_tga(generated_glass(), "glass.tga")
    save_tga(matching_edges(generated_chainlink()), "chainlink.tga")

    for output_path in sorted(OUTPUT.glob("*.tga")):
        with Image.open(output_path) as built:
            if built.size != (SIZE, SIZE):
                raise RuntimeError(f"{output_path.name} has unexpected dimensions {built.size}")
            pixels = built.load()
            if any(pixels[0, y] != pixels[SIZE - 1, y] for y in range(SIZE)):
                raise RuntimeError(f"{output_path.name} does not tile on its horizontal edge")
            if any(pixels[x, 0] != pixels[x, SIZE - 1] for x in range(SIZE)):
                raise RuntimeError(f"{output_path.name} does not tile on its vertical edge")

    previews = []
    for output_path in sorted(OUTPUT.glob("*.tga")):
        with Image.open(output_path) as built:
            preview = Image.new("RGB", (220, 248), (27, 30, 33))
            sample = built.convert("RGBA").resize((208, 208), Image.Resampling.LANCZOS)
            checker = Image.new("RGB", sample.size, (62, 65, 68))
            checker_draw = ImageDraw.Draw(checker)
            for y in range(0, sample.height, 16):
                for x in range(0, sample.width, 16):
                    if (x // 16 + y // 16) % 2:
                        checker_draw.rectangle((x, y, x + 15, y + 15), fill=(91, 94, 97))
            checker.paste(sample, (0, 0), sample)
            preview.paste(checker, (6, 6))
            ImageDraw.Draw(preview).text((8, 220), output_path.stem, fill=(232, 235, 238))
            previews.append(preview)

    columns = 4
    rows = (len(previews) + columns - 1) // columns
    contact_sheet = Image.new("RGB", (columns * 220, rows * 248), (17, 19, 21))
    for index, preview in enumerate(previews):
        contact_sheet.paste(preview, ((index % columns) * 220, (index // columns) * 248))
    contact_sheet.save(ROOT / "texture-contact-sheet.png")

    print(f"Built {len(list(OUTPUT.glob('*.tga')))} original textures in {OUTPUT}")


if __name__ == "__main__":
    main()
