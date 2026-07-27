# Nuke original-art provenance

Status: original revision-2 assets

Date: 2026-07-26

## Policy

No Valve texture pixels were supplied to the image generator and no VTF was
converted into the distributable palette. Local Source files were used only
to inventory material roles and metadata such as dimensions.

Six original square raster sources were generated, copied into
`art_sources/`, and retained so every derivative can be rebuilt. The script
`tools/build_original_textures.py` makes the raster sources four-edge
continuous by mirrored tiling, closes the mathematically periodic edges of the
precision-pattern materials, converts everything to 512×512 TGA, creates
controlled color variants, validates exact stored edge continuity, and emits
`texture-contact-sheet.png`.

Revision 2 retains the same six generated raster sources. It adjusts the
deterministic glass color/alpha and adds one fully procedural
`window_backing.tga`; no additional generated-image source and no Valve pixels
were used.

## Generated source prompts

### `painted_concrete_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original clean painted concrete wall surface for a modern industrial power facility, cool light gray/off-white paint over fine concrete grain, very subtle roller variation and restrained age marks
Style/medium: realistic seamless tileable diffuse texture, clean contemporary industrial material, designed to remain readable under baked game lightmaps
Composition/framing: perfectly front-facing orthographic square material sample filling the entire canvas; even texel density; no perspective
Lighting/mood: flat neutral diffuse illumination only; absolutely no directional light, cast shadow, highlight, vignette, ambient occlusion, or baked shading
Constraints: seamless on all four edges; original design; no panels, seams, borders, cracks, bolts, pipes, objects, graffiti, text, logos, symbols, stains with obvious focal shapes, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

### `corrugated_blue_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original clean blue-gray corrugated galvanized steel wall cladding for a modern industrial power facility, narrow vertical repeating ribs, slightly desaturated institutional blue coating, subtle realistic metal grain and very restrained wear
Style/medium: realistic seamless tileable diffuse texture, clean contemporary industrial material, designed to remain readable under baked game lightmaps
Composition/framing: perfectly front-facing orthographic square material sample filling the entire canvas; vertical ribs run exactly top to bottom with uniform spacing; no perspective
Lighting/mood: flat neutral diffuse illumination; only subtle symmetric tonal modeling within each corrugation so the ribs remain visible in a diffuse-only legacy engine; no directional cast shadows, highlights, vignette, ambient occlusion, or scene lighting
Constraints: seamless on all four edges; original design; no panels, borders, bolts, fasteners, damage, rust streaks, pipes, objects, graffiti, text, logos, symbols, obvious focal stains, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

### `asphalt_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original clean but lightly used dark charcoal asphalt paving for a modern industrial facility yard, dense fine aggregate with a few subtle medium aggregate flecks, dry surface
Style/medium: realistic seamless tileable diffuse texture, contemporary industrial material, designed to remain readable under baked game lightmaps
Composition/framing: perfectly top-down orthographic square material sample filling the entire canvas; uniform scale and detail distribution; no perspective
Lighting/mood: flat neutral diffuse illumination only; absolutely no directional light, cast shadow, highlight, wet reflection, vignette, ambient occlusion, or baked shading
Constraints: seamless on all four edges; original design; no road markings, cracks, potholes, oil stains, tire marks, leaves, debris, objects, text, logos, symbols, obvious focal shapes, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

### `concrete_floor_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original smooth poured concrete floor for a clean modern industrial power facility interior, medium cool gray, fine sand aggregate, subtle mottling from finishing, very restrained use wear
Style/medium: realistic seamless tileable diffuse texture, contemporary industrial material, designed to remain readable under baked game lightmaps
Composition/framing: perfectly top-down orthographic square material sample filling the entire canvas; uniform detail distribution; no perspective
Lighting/mood: flat neutral diffuse illumination only; absolutely no directional light, cast shadow, highlight, reflection, vignette, ambient occlusion, or baked shading
Constraints: seamless on all four edges; original design; no slab joints, seams, borders, cracks, tire marks, oil stains, paint markings, objects, debris, text, logos, symbols, obvious focal shapes, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

### `grass_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original maintained short grass ground cover beside a modern industrial power facility, dense fine blades, restrained cool green and olive variation, slightly dry in small areas but generally clean and maintained
Style/medium: realistic seamless tileable diffuse texture, contemporary facility landscaping, designed to remain readable under baked game lightmaps
Composition/framing: perfectly top-down orthographic square material sample filling the entire canvas; uniform scale and detail distribution; no perspective
Lighting/mood: flat neutral diffuse illumination only; absolutely no directional light, cast shadow, highlight, vignette, ambient occlusion, or baked shading
Constraints: seamless on all four edges; original design; no dirt paths, bare patches with focal shapes, flowers, leaves, litter, stones, objects, tire marks, text, logos, symbols, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

### `gravel_source.png`

```text
Use case: stylized-concept
Asset type: tileable game texture for a 2002-era first-person shooter diffuse/albedo map
Primary request: original compact fine gravel ground for drainage strips and service areas at a modern industrial power facility, small angular gray and muted beige stones packed tightly with a little dark aggregate between them
Style/medium: realistic seamless tileable diffuse texture, clean contemporary industrial ground material, designed to remain readable under baked game lightmaps
Composition/framing: perfectly top-down orthographic square material sample filling the entire canvas; uniform stone scale and distribution; no perspective
Lighting/mood: flat neutral diffuse illumination only; absolutely no directional light, cast shadow, highlight, wet reflection, vignette, ambient occlusion, or baked shading
Constraints: seamless on all four edges; original design; no large rocks, dirt paths, tire tracks, weeds, leaves, litter, objects, paint markings, text, logos, symbols, obvious focal shapes, or watermark; moderate-low contrast; no normal-map coloration; no PBR sphere or presentation backdrop
```

## Derived outputs

| Output | Derivation |
| --- | --- |
| `painted_concrete.tga` | Seam-safe painted-concrete source |
| `painted_concrete_blue.tga` | Cool blue-gray color grade of painted concrete |
| `concrete_floor.tga` | Seam-safe smooth-floor source |
| `concrete_dark.tga` | Dark neutral grade of smooth concrete |
| `asphalt.tga` | Seam-safe asphalt source |
| `grass.tga` | Seam-safe maintained-grass source |
| `gravel.tga` | Seam-safe compact-gravel source |
| `corrugated_blue.tga` | Seam-safe corrugated source |
| `corrugated_gray.tga` | Neutral gray grade of corrugated source |
| `metal_trim.tga` | Cool neutral fine-grain grade |
| `ceiling_tile.tga` | Deterministic original grid drawing |
| `metal_grating.tga` | Deterministic original cross-grating drawing |
| `glass.tga` | Deterministic original translucent neutral blue-gray RGBA, revised to alpha 42 |
| `chainlink.tga` | Deterministic original chain-link RGBA |
| `window_backing.tga` | Deterministic original blue-gray vertical reflection field |

These are revision-2 materials. Final acceptance requires in-engine scale,
tiling, lightmap, alpha-shader, and long-surface repetition checks.
