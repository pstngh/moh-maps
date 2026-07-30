# Inferno original-art provenance

All bundled Inferno textures are original project assets. Valve art was used
only to classify broad material roles and is not copied or transformed.

## Built-in image-generation sources

The following source PNGs were generated with the built-in image-generation
workflow on 2026-07-30:

| Source | Prompt intent |
| --- | --- |
| `plaster_cream_source.png` | Pale cream Mediterranean lime plaster, subtle cracks, flat diffuse, no objects/text |
| `cobblestone_source.png` | Warm gray/beige compact street cobbles, orthographic diffuse, no unique debris |
| `roof_tile_source.png` | Muted burnt-orange terracotta roof rows, flat diffuse, no roof-edge objects |
| `brick_source.png` | Warm red-brown running-bond brick and sandy mortar, flat diffuse |

Every prompt required a square tileable game texture with no perspective,
logos, trademarks, watermark, graffiti, signage, focal damage, objects, or
baked directional lighting.

## Reused project-owned sources

These source PNGs were copied from the already documented `codex_cache`
original-art set so Inferno is self-contained:

- `wood_source.png`;
- `stone_floor_source.png`;
- `grass_source.png`;
- `painted_metal_source.png`.

They are project-owned originals, not retail or Source-game extracts.

## Deterministic derivation

`tools/build_original_textures.py`:

1. fits each source into a mirrored four-quadrant periodic tile;
2. creates restrained plaster, wood, stone, and painted-metal colorways;
3. creates simple window and ceiling materials procedurally;
4. writes uncompressed power-of-two TGA files;
5. asserts exact stored-edge equality on all four sides;
6. generates the committed contact sheet.

Image-generated sources are raw material inputs, not claims of perfect
seamlessness. The deterministic mirroring and stored-edge validation establish
the actual packaged tiling guarantee.
