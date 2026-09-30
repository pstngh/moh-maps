# Materials: textures and shaders

## Finding stock textures

- [reference/materials.md](reference/materials.md): every material used by
  the stock maps, by theme, with image size, typical scale, whether it's used on
  floors, walls or ceilings, footstep material, and which maps use it.
  Regenerate with `python -m mohkit.catalog`.
- `data/palettes.json`: the 25 most-used materials of each stock MP map. Good
  starting palettes ("what does Stalingrad use for walls?").
- **Look before choosing.** Names mislead. Render a contact sheet of a folder
  and view it (e.g. `central_europe`, `general_structure`, `algiers`,
  `normandy`, `german`, `mohtest`, `misc_outside`).
- `mohkit.validate` (and `mohkit build`) reject shader names that don't exist in
  the retail paks. A missing texture renders as a black-and-white checker.

Useful families (retail AA):

| role | good choices |
|---|---|
| plaster facades | `central_europe/exterior_wall_2`, `general_structure/plaster_wall2`, `plaster_wall3b`, `mohtest/plasterwal1a` |
| half-timbered upper storeys | `central_europe/tudor_set1_exwall1a` (one storey per 256 px, scale 0.625 for a 160-unit storey), `tudor_set2a–d` |
| brick | `central_europe/normndybrik1`, `general_structure/jh_brick4`, `brickwall_set3` |
| stone | `general_structure/stonebricks1`, `stonewall2`, `rockwall3`, `archstone2`, `mohtest/stonewall1grim` |
| concrete / bunker | `general_structure/jh_conc512a/b/c`, `bunker_wall`, `flatgrey_conc` |
| streets and squares | `central_europe/strtset_cew`, `small_cobble`, `general_structure/…`, `mohtest/rubble2c` |
| floors (inside) | `general_structure/floor4`, `central_europe/flrwood2`, `mohtest/flrwood1_rep`, `algiers/whsflrset1_1b` |
| roofs | `central_europe/redshingle`, `rusticshingle`, `general_structure/jh_tileroof1`, `shingles_ce2` |
| wood trim, beams | `general_structure/beam_wood1` (256×32), `plank_flat`, `mohtest/joist` |
| windows (as images in niches) | `general_structure/denmark_win2` (128×180), `window4_frame`, `central_europe/windowtownhall1` |
| doors (images) | `general_structure/doubledoor2`, `door_offwhite2`, `door_rorng2`, `cellardoor` (128×256) |
| shutters | `central_europe/shutter_set2` (64×128) |
| mouldings | `general_structure/building_molding` (128×64) |

## Scale and alignment

- **Scale 1** (one texel per unit) for almost everything, as in the stock maps.
  Use 0.5 for finer brick or stone.
- Textures are world-projected, so adjacent brushes line up without work. To
  fit an image exactly onto a panel (windows, doors, signs) use
  `mohkit.kit.fit()`, or `kit.window()` which also carves the niche.
- Rotate roof textures 90° when the ridge runs along Y so the shingle rows
  follow the eaves.

## Tool shaders (`common/*`)

| shader | solid to players | stops bullets | visible | use |
|---|---|---|---|---|
| `common/caulk` | yes | yes | no | every face nobody sees. The Carver does this automatically |
| `common/nodraw` | **no** | no | no | non-solid invisible |
| `common/clip` | yes | **no** | no | smooth collision around stairs and props; blocks players and AI |
| `common/playerclip` | players only | no | no | keep players out of places |
| `common/weapon` | no | yes | no | bullet-only blocker (there is no `common/weaponclip`) |
| `common/woodclip`, `metalclip`, `stoneclip`, `dirtclip`, `grassclip`, `glassclip`, … | yes | yes | no | collision with a material: impact effects and footstep sounds. Use around props |
| `common/foliageclip` | no | yes | no | bushes |
| `common/origin` | — | — | no | rotation origin for doors and ladders |
| `common/hint`, `common/vis` | — | — | no | VIS hints |
| `common/areaportal` | — | — | no | areaportals (with doors) |
| `common/trigger` | — | — | no | trigger brushes |
| `common/caulksky` | — | — | sky | sky without an image |
| `sky/*` | yes | — | sky | sky faces (`sky/mohday2`, …) |

## Material surfaceparms (footsteps and impacts)

`wood metal rock dirt grass gravel sand snow mud puddle glass grill foliage paper
carpet`. `surfaceparm stone` and `plaster` **do nothing** in AA: 552 AA
shaders say `stone`, and it silently falls back to `rock`. Custom shaders should
say `rock`. Faces without a material default to `rock`. Glass, foliage, paper and
puddle always let bullets through; wood lets through weapons with
`bulletthroughwood`.

## Custom textures

- Power-of-two TGA (with alpha) or JPG, usually 256 or 512. The engine prefers
  `.jpg` over `.tga` when both exist.
- Path `textures/<folder>/<name>.jpg`, referenced in the `.map` as
  `<folder>/<name>`. Without a shader script the image is used directly
  (texture × lightmap, rock material).
- A shader script `scripts/<anything>.shader` in the PK3 adds surfaceparms and
  blending. The MOHAA idiom for an opaque lightmapped surface:

```text
textures/mymap/wall_plaster
{
	qer_editorimage textures/mymap/wall_plaster.tga
	surfaceparm rock
	{
		map textures/mymap/wall_plaster.jpg
	nextbundle
		map $lightmap
	}
}
```

`qer_editorimage` always names the **`.tga`**, even when the file is a `.jpg`.
Q3map copies it into the BSP, the engine loads it by that exact name as a TGA
fence mask, and a `.jpg` there stops the map from loading (`LoadTGA: Only type
2 …`). A missing `.tga` is fine: no mask, and the tools fall back to the `.jpg`.
Generated shaders use `mohkit.shaders.editor_image()`.

Alpha-tested (fences, foliage):

```text
	surfaceparm trans
	surfaceparm alphashadow
	cull none
	{
		map textures/mymap/fence.tga
		alphaFunc GE128
		depthWrite
	nextbundle
		map $lightmap
	}
```

Translucent glass: `surfaceparm glass`, `surfaceparm trans`, `cull none`, one
stage with `blendFunc blend` (no lightmap).

Sky: `surfaceparm sky`, `surfaceparm noimpact`, `surfaceparm nolightmap`,
`skyParms env/<name> 512 -` with six images `env/<name>_rt|lf|ft|bk|up|dn.jpg`.

- Put custom assets in `maps/<name>/assets/` (`textures/…`, `scripts/…`,
  `env/…`). `mohkit build` copies them into the compile root (the compiler needs
  them for lightmap sizing and flags) and into the PK3.
- Duplicate shader names: the first-loaded script wins. Prefix everything with
  your map name.
