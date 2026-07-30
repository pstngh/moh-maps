from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art_sources"
OUTPUT = ROOT / "main" / "textures" / "codex_inferno"
SIZE = 512


def mirror_tile(image: Image.Image) -> Image.Image:
    mode = "RGBA" if "A" in image.getbands() else "RGB"
    quarter = ImageOps.fit(
        image.convert(mode),
        (SIZE // 2, SIZE // 2),
        method=Image.Resampling.LANCZOS,
    )
    result = Image.new(mode, (SIZE, SIZE))
    result.paste(quarter, (0, 0))
    result.paste(ImageOps.mirror(quarter), (SIZE // 2, 0))
    result.paste(ImageOps.flip(quarter), (0, SIZE // 2))
    result.paste(
        ImageOps.flip(ImageOps.mirror(quarter)),
        (SIZE // 2, SIZE // 2),
    )
    return matching_edges(result)


def matching_edges(image: Image.Image) -> Image.Image:
    result = image.copy()
    pixels = result.load()
    for y in range(result.height):
        pixels[result.width - 1, y] = pixels[0, y]
    for x in range(result.width):
        pixels[x, result.height - 1] = pixels[x, 0]
    return result


def colorize_gray(
    image: Image.Image,
    black: tuple[int, int, int],
    white: tuple[int, int, int],
) -> Image.Image:
    return ImageOps.colorize(ImageOps.grayscale(image), black=black, white=white)


def tune(image: Image.Image, brightness: float, contrast: float) -> Image.Image:
    result = ImageEnhance.Brightness(image).enhance(brightness)
    return ImageEnhance.Contrast(result).enhance(contrast)


def generated_window() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), (40, 55, 64))
    draw = ImageDraw.Draw(image)
    for x in range(SIZE):
        highlight = int(15 * (1 - abs((x % 160) - 80) / 80))
        draw.line(
            (x, 0, x, SIZE),
            fill=(40 + highlight, 55 + highlight, 64 + highlight),
        )
    draw.rectangle((0, 0, SIZE - 1, SIZE - 1), outline=(25, 31, 35), width=10)
    draw.line((SIZE // 2, 0, SIZE // 2, SIZE), fill=(25, 31, 35), width=8)
    return matching_edges(image)


def generated_ceiling() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), (181, 173, 152))
    draw = ImageDraw.Draw(image)
    for coordinate in range(0, SIZE, 128):
        draw.line((coordinate, 0, coordinate, SIZE), fill=(124, 116, 99), width=3)
        draw.line((0, coordinate, SIZE, coordinate), fill=(124, 116, 99), width=3)
    return matching_edges(image)


def save_tga(image: Image.Image, name: str) -> None:
    image.save(OUTPUT / name, format="TGA", compression=None)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    plaster = mirror_tile(Image.open(SOURCE / "plaster_cream_source.png"))
    cobble = mirror_tile(Image.open(SOURCE / "cobblestone_source.png"))
    roof = mirror_tile(Image.open(SOURCE / "roof_tile_source.png"))
    brick = mirror_tile(Image.open(SOURCE / "brick_source.png"))
    wood = mirror_tile(Image.open(SOURCE / "wood_source.png"))
    stone = mirror_tile(Image.open(SOURCE / "stone_floor_source.png"))
    grass = mirror_tile(Image.open(SOURCE / "grass_source.png"))
    metal = mirror_tile(Image.open(SOURCE / "painted_metal_source.png"))

    save_tga(tune(plaster, 0.90, 0.88), "plaster_cream.tga")
    save_tga(
        colorize_gray(plaster, (70, 48, 28), (211, 162, 91)),
        "plaster_ochre.tga",
    )
    save_tga(
        colorize_gray(plaster, (72, 42, 37), (194, 133, 116)),
        "plaster_rose.tga",
    )
    save_tga(
        colorize_gray(plaster, (86, 86, 78), (224, 220, 201)),
        "plaster_white.tga",
    )
    save_tga(tune(cobble, 0.88, 0.92), "cobblestone.tga")
    save_tga(tune(roof, 0.86, 0.90), "roof_tile.tga")
    save_tga(tune(brick, 0.88, 0.92), "brick.tga")
    save_tga(tune(stone, 0.86, 0.90), "stone_floor.tga")
    save_tga(
        colorize_gray(stone, (57, 52, 44), (177, 163, 137)),
        "stone_trim.tga",
    )
    save_tga(tune(grass, 0.75, 0.88), "grass.tga")
    save_tga(tune(wood, 0.84, 0.95), "wood.tga")
    save_tga(
        colorize_gray(wood, (35, 24, 18), (116, 76, 47)),
        "wood_dark.tga",
    )
    save_tga(tune(metal, 0.78, 0.90), "painted_metal.tga")
    save_tga(
        colorize_gray(metal, (26, 48, 42), (89, 126, 102)),
        "shutter_green.tga",
    )
    save_tga(generated_window(), "window_dark.tga")
    save_tga(generated_ceiling(), "ceiling.tga")

    output_paths = sorted(OUTPUT.glob("*.tga"))
    for output_path in output_paths:
        with Image.open(output_path) as built:
            if built.size != (SIZE, SIZE):
                raise RuntimeError(
                    f"{output_path.name} has unexpected dimensions {built.size}"
                )
            pixels = built.load()
            if any(pixels[0, y] != pixels[SIZE - 1, y] for y in range(SIZE)):
                raise RuntimeError(
                    f"{output_path.name} does not tile horizontally"
                )
            if any(pixels[x, 0] != pixels[x, SIZE - 1] for x in range(SIZE)):
                raise RuntimeError(
                    f"{output_path.name} does not tile vertically"
                )

    previews = []
    for output_path in output_paths:
        with Image.open(output_path) as built:
            preview = Image.new("RGB", (220, 248), (27, 30, 33))
            sample = built.convert("RGB").resize((208, 208), Image.Resampling.LANCZOS)
            preview.paste(sample, (6, 6))
            ImageDraw.Draw(preview).text(
                (8, 220),
                output_path.stem,
                fill=(232, 235, 238),
            )
            previews.append(preview)

    columns = 4
    rows = (len(previews) + columns - 1) // columns
    contact_sheet = Image.new(
        "RGB",
        (columns * 220, rows * 248),
        (17, 19, 21),
    )
    for index, preview in enumerate(previews):
        contact_sheet.paste(
            preview,
            ((index % columns) * 220, (index // columns) * 248),
        )
    contact_sheet.save(ROOT / "texture-contact-sheet.png")

    print(f"Built {len(output_paths)} original textures in {OUTPUT}")


if __name__ == "__main__":
    main()
