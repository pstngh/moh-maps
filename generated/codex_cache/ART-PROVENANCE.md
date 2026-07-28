# Cache original-art provenance

Date: 2026-07-27

All map-specific raster art in the Cache PK3 is original project-bound work.
No Valve VTF/VMT image is copied, converted, traced, or packaged.

## Generated source surfaces

The following source PNGs were created with OpenAI image generation for this
project:

| File | Prompt intent |
| --- | --- |
| `art_sources/brick_source.png` | Seamless muted red-brown industrial brick wall, gray mortar, subtle age and variation, neutral diffuse light, no graffiti, lettering, logos, borders, or perspective |
| `art_sources/wood_source.png` | Seamless weathered industrial plywood and horizontal plank surface, restrained tan-gray palette, subtle grain and wear, neutral diffuse light, no nails as focal points, text, logos, borders, or perspective |
| `art_sources/painted_metal_source.png` | Seamless cool blue-gray painted steel panel, understated rivets and wear, clean modern industrial character, neutral diffuse light, no labels, warning marks, logos, borders, or perspective |

The generator-produced image files were copied into this repository before
derivation. They are not generated from CS:GO artwork.

Six additional original source surfaces—painted concrete, smooth concrete
floor, asphalt, blue corrugated metal, maintained grass, and compact
gravel—are shared with the project’s Nuke palette. Their original sources and
derivation remain project-owned and are copied into this map’s `art_sources`
directory so Cache rebuilds are self-contained.

## Deterministic derivation

`tools/build_original_textures.py`:

- crops each source to a square;
- creates a four-quadrant mirrored 512×512 tile with mathematically matching
  stored edges;
- derives restrained color variants for light concrete, blue concrete, dark
  concrete, gray corrugation, and metal trim;
- creates original procedural ceiling tile, grating, window backing,
  chain-link, and translucent glass;
- writes uncompressed TGA images accepted by Allied Assault;
- verifies all four stored edges pixel-for-pixel;
- writes `texture-contact-sheet.png` for visual inspection.

The resulting palette contains 19 original 512×512 textures.

## Use boundary

Local Valve assets may be read to classify a Source material’s role or measure
a model, but they must never be copied into `main`, the PK3, or this
repository. The committed PNG/TGA files described above are the complete
map-specific art payload.
