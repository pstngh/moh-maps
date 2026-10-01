# Converting CS:GO maps

```sh
python -m mohkit csgo de_dust2                  # -> local/csgo/cs_dust2/{cs_dust2.map, assets/, cs_dust2.pk3, shots}
python -m mohkit csgo de_inferno --name cs_inferno -q normal
python -m mohkit csgo de_dust2 --props-only     # re-place runtime props in the last compile (~1 min)
```

`--resume` skips conversion and compiling: it injects the props, packages and tests
what the last build left in `local/csgo/<name>/` (map, assets, `statics.json`) and its
compile root, for when a stage was re-run by hand. Drafts use `lightmapdensity 32`
(`--lightmap-density`): MOHlight time is about proportional to lightmap texels, and
de_nuke has ~1M of them at 16.

`--refresh-assets` re-converts and re-packages the last compile when only textures,
shaders or models changed: it refuses unless the new `.map` text equals the compiled one.

**Texture resizing trap (fixed 2026-10-01):** Pillow resizes RGBA images with
premultiplied alpha, so RGB goes black where alpha is 0. Source keeps specular/envmap
masks in the base texture's alpha, so every such texture over 512 px was written
darkened, and DecalModulate decals (neutral grey with alpha) came out as black squares.
Opaque images are now resized as RGB (`Converter._write_image`, `modelconv.convert_texture`).

`-q unlit` compiles BSP and fast VIS only and gives props a flat grey: geometry, props,
doors and ladders can be checked in minutes (de_nuke's draft light alone takes over an
hour, even with no light entities and `-notrace`: MOHlight's base cost per lightmap texel
dominates, and texel count is what `lightmap_density` controls).

`--props-only` re-converts, checks that nothing but `script_model` props changed
(`mapfile.compiled_difference`: brushes compared by plane, numbers to 0.01), and
rewrites only the entity lump of the last compile with `Q3map -onlyents`
(`compile.update_entities`): 48 s on de_dust2 instead of about 45 min. Lighting stays
that of the last compile, and anything else that changed (a clip brush, a light, a
static prop) refuses with the first difference: run a full build then.

The converter reads the **compiled** `.bsp` shipped with the game, plus
materials and models from the VPKs. It needs no decompiler (BSPSource) and
no VMF. Output goes to `local/` (gitignored). It contains textures decoded from
Valve's files, so it's for personal use only: don't commit or share it.

## What gets converted

| Source | MOHAA | notes |
|---|---|---|
| world brushes, `func_detail` | world brushes (`+surfaceparm detail`) | bevel planes pruned; face points snapped to the grid |
| `func_brush`, `func_wall`, `func_breakable`, `func_illusionary` (non-solid), doors | world brushes, transformed to world space | doors become static |
| `toolsclip` / `toolsplayerclip` / `toolsinvisible` | `common/clip` / `common/playerclip` | |
| nodraw faces | `common/caulk` | |
| sky faces | converted skybox shader (`skyParms env/csgo/<map>/sky`) | Source cubemap faces → `_rt _lf _ft _bk _up _dn` (up/dn rotated) |
| hint, skip, areaportal, trigger, occluder, fog, blocklos, grenade/NPC clip | dropped (counted in the report) | |
| ladder volumes (`CONTENTS_LADDER`) | **CS-style step columns** (default, `Options.ladder_style="steps"`): invisible `common/clip` slices against the wall face of the Source volume, 16 units high, each 1 unit shallower than the one below, from the floor (when one is within 96 units below the volume) to the volume top. Running into it climbs it, backing off climbs down, and the player can step off sideways or onto the ledge at the top, as in CS. `ladder_style="func_ladder"`: MOHAA ladders (`common/trigger` over the volume + 8 units toward the climber, `common/origin` on the climb face, `angle` toward the wall) | Facing: the side of the volume with solid (Source contents, or converted detail and clip brushes) behind it; a square volume tries both axes (mirage's leaning ladder is 32.0001 × 32, and float noise had picked the wrong axis). Why steps: MOHAA's `func_ladder` only lets a player off forward at the top, after a 98-unit clear rise (`Player::CondCanGetOffLadderTop`), and the jump-off is weak (`jumpxy -70 0 150`, `global/mike_torso.st`). CS scaffold and hole ladders (mirage's two at the scaffolds: platform behind and beside, upper floor 96 units above) hung the player near the top. Climb speed: MOHAA steps up at most 18 units per move (`STEPSIZE`, `bg_slidemove.cpp`), so a column climbs at ~600 units/s at 60 fps (8-unit steps were no slower; it depends on frame rate). Walking backward off the top just walks down the column, so a hole ladder is left by strafing onto the platform beside it (verified 2026-10-01 on an unlit Mirage: all 3 ladders climb to the top; strafing off the two scaffold ladders lands on their platforms at z -40 and -58). Probe: `game.ladder_probe(pk3s, map, game.ladders_for_probe(bsp))`. `func_ladder` notes: a hanging ladder's trigger is extended down to the floor (mounting puts the player at absmin + 2, `FuncLadder::PositionOnLadder`); a volume deeper than 28 units climbs 8 units off its far face; prop collision in a ladder volume or its mount box is dropped (it blocks `Player::CondLadder`/`CanUseLadder`). `Converter.ladders`, report `ladders` |
| water volumes | the drawn face gets a water shader (`surfaceparm water trans nonsolid`, image = the normal map's relief tinted with `$fogcolor`, alpha `$waterblendfactor`); hidden sides `common/waterskip` (caulk is solid and would fill the volume) | Source water has no base texture |
| `func_breakable`/`_surf` (glass panes, mirage's wall-hole covers) | `func_window` (MOHAA's breakable brush), Source `health`, glass debris for glass, coloured otherwise | |
| overlays (`info_overlay`, LUMP_OVERLAYS) | flat 3×3 patch half a unit off the surface; shader `ov_<material>`: `trans nonsolid nomarks polygonOffset`, `blendFunc blend` + `nextbundle $lightmap` like retail decals | U axis is packed in the z of UV points 0–2, V = N×U (negated if point 3's z is 1); overlays wrapped over corners/displacements are placed flat |
| doors (`prop_door_rotating`) | `func_rotatingdoor`: a brush slab between the model's two largest opposite faces, textured with the model's material (each face's texdef reproduces the UVs of the largest mesh triangle on it), origin brush on the hinge, `openangle` = `distance`, `time` = distance/speed, `alwaysaway` for two-way doors | door meshes can lie 90° off the frame their angles apply to (rotated root bone): the mesh is turned to match the MDL hull box (`_yaw_to_hull`); no static prop in de_nuke needs it |
| ropes (`move_rope` → `keyframe_rope` via `NextKey`) | two crossed ribbon patches per segment, `Width` wide, `rope_*` shader (nonsolid, `cull none`, alpha-tested, lightmapped) | sag ≈ sqrt(3·span·Slack/8): a parabola, exact as one 3-column patch row (quadratic Bezier) |
| `env_sprite` (lamp glows) | a thin `common/nodraw` brush whose east face is a quad with an additive `deformVertexes autosprite` shader (`spr_*`), image fitted to the quad, `rendercolor` × `renderamt` baked in; 0.75 × texture size × `scale`, 8–96 units | autosprite needs a 4-vertex surface: the brush floats free so nothing T-junctions it |
| props with an `OnBreak` output (de_nuke's vent slats and vent cover, mirage's shutter and sheet-metal wall covers) | `func_window` slab of the model (same slab as doors), health from Source or 25: the vent is shut until shot. Debris by `$surfaceprop`: glass 0 (retail), metal 7, wood 8. Retail's `models/fx/windows/debris_0..3.tik` are all glass shards, so converted maps ship `debris_7.tik` (sparks from `bh_metal_fastpiece` + `metal_section` chunks, `snd_bodyfall_metal1`) and `debris_8.tik` (crate planks and splinters, `snd_crate_wood`) (`convert.debris_tiki`; verified in a test room) | bots don't use crouch-only vents anyway (the navmesh is built at standing height) |
| texlights (`lights.rad`: emissive materials, e.g. de_nuke's office-light strips, lit windows, reactor glow) | default (`--no-texlights` turns it off): one point `light` per emitting face (de_nuke: 43, incl. the faces of its disabled emitter func_brushes), 8 units out along the normal, intensity sqrt(area × brightness) × 4 (40–600), colour from the rad line | `q3map_surfacelight` works (test room) but de_nuke's 43 emitting surfaces made `fastrad` light estimate ~15 hours. Compared on de_nuke (2026-10-01, same cameras): Hell 1.8x brighter, B site 1.4-1.7x, the Heaven approach 1.5x, lit like CS:GO instead of dim; B site's upper walls take the warm white of `window_illum_001` (252 239 209). dust2 and mirage have no texlights |
| `env_fog_controller` | worldspawn `farplane` = fogend / fogmaxdensity, `farplane_color`, `farplane_cull 0` | |
| sky (`skyname`) | six faces from each face material's `$basetexture` | de_nuke's `nukeblank` faces all use `skybox/nukeblankup` (plain 90 134 186 blue) |
| spectator cameras (`maps/<map>_cameras.txt`) | contact-sheet shots (eye position, pitch/yaw as given), pages of 9 (`<name>_shots.png`, `_shots_2.png`, …) | `named_cameras` |
| 3D skybox (the area containing `sky_camera`) | dropped | detected from BSP areas, not bounds |
| displacements | `patchDef2` meshes | midpoint-expanded so they pass through every kept Source sample; sample rows/columns straight within `disp_tolerance` (1 unit) dropped, consistently across shared edges; split to ≤ 17×17; visible side toward the air |
| materials | TGA/JPG + generated shader script | `$basetexture` only (blends use the first layer); power-of-two, max 512 px; `$surfaceprop` → MOHAA material surfaceparm; alphatest/translucent/nocull handled |
| texture alignment | Q3 shift/rotate/scale | exact for any rotation, scale or mirror (`tests/test_texdef.py`) |
| `info_player_terrorist` / `counterterrorist` / `info_deathmatch_spawn` | `info_player_axis` / `allied` / `deathmatch` | T+CT double as DM spawns when the map has none |
| `light`, `light_spot` | `light` (+ `info_null` target along VRAD's spot direction: z = +sin(pitch), so pitch -90 points down; until 2026-10-01 04:40 the converter used -sin and every ceiling spot lit the ceiling) | intensity ≈ 1.5 × Source brightness, clamped 40–800 (0.75× left interiors dark: MOHAA's `light` is about its reach in units, and a 175-brightness ceiling spot barely reached the floor). Lights below brightness 20 are dropped and a light within 32 units of a brighter one is folded into it (de_nuke 473 → 247): MOHlight keeps at most 60 lights per leaf, and in the converted map's big leaves the near-zero fill lights crowded out the fixtures (radio rooms went dark while the light grid, which gets every light, made their props bright) |
| `light_environment` | worldspawn `suncolor`, `sundirection`, `ambientlight`, `sundiffusecolor` | sky fill = `_ambient` colour normalised to its brightest channel × clamp(brightness / 8, 20, 70) |
| static props (`prop_static`) | `mohkit/source/modelconv.py` (MDL → TIKI/SKD/SKC + collision `.map`). **Default (`props_mode="inject"`): every prop** becomes a static model added to the lit BSP by `mohkit.staticlight` and coloured from its light grid, with its collision as world clip brushes. `props_mode="compile"`: the largest as MOHlight-lit `static_*` up to `--static-verts`, the next 600 as `script_model`s | MOHlight lights static models on one thread (~190 verts/s), so de_nuke's 4,801 props would light for hours; injection takes seconds and costs no entities |

## Visibility and compile time

Converted maps compile with Q3map `-blocksize 512` (`convert.BSP_ARGS`): the leaves of an
all-detail map are the BSP blocks, and smaller blocks mean fewer lights per leaf for
MOHlight's 60-light cap (de_nuke: ~500 clusters, 31 KB of VIS data).

By default every converted brush is detail inside a structural caulk shell. The price
is no VIS culling and a slow BSP stage on big maps: tens of thousands of faces share one
leaf. `--structural` keeps Source's own world/detail split instead. The old claim that
this overflows MOHAA's 2 MB VIS buffer is **false for de_dust2** (tested 2026-10-01 with
`-blocksize 512`, fast VIS): BSP 919 s (559 s all-detail), 691 clusters, 1,663 portals,
60,816 bytes of VIS data, no leak (a few lights inside walls "leaked" harmlessly). Not
yet compared: lit result, full VIS time, and whether it lights faster (smaller leaves).

**Displacements cost BSP time quadratically.** Q3map groups patches for LOD by
comparing every control point of every patch with every control point of every
other patch (`PatchMapDrawSurfs`, q3map `patch.c`). de_dust2's 619 patches
(118k control points) spent 673 s there, measured with timestamped logs.
Dropping straight sample lines halves the control points and cuts that work
3.9× (`Options.disp_tolerance`, default 1 unit; 2 units: 6.8×).

**A face's plane is `planes[planenum]` as stored; ignore `side`.** On every face of
de_dust2, de_mirage and de_nuke the stored plane agrees with the face winding, whatever
`side` says (`side` only records how the face sits on its BSP node). Until 2026-10-01 the
displacement normal was flipped when `side` was 1, so those displacements (dust2 176,
Mirage 143, Nuke 77) were turned inside out: back-facing patches the engine culls, seen
in game as flat `farplane_color` walls (Mirage's mid and B site). Found by casting the
camera's rays through both BSPs (every ray hit the patch; the patch faced away).
`tests/test_source_readers.py` now checks that displacements face the air.

## Scale

CS players are 72 units tall, MOHAA's are 94, but jump height (56 vs about 55)
and step height (18) are nearly equal. At the default `--scale 1` rooms feel a
bit tight, but every CS jump spot that doesn't need a crouch-jump stays
reachable. `--scale 1.25` gives more natural proportions but lifts many boxes
out of reach.

## Runtime prop lighting

A converted model's origin sits over its bounds centre, 16 units above its top
(`modelconv.convert_model(centre=True)`): the engine lights a non-solid
`script_model` from 8 units below its origin with one sun trace
(`docs/reference/engine.md` §5.2). From the Source pivot (on the floor), the rubble in
the first dust2 drafts was black; from the bounds centre, cars got ambient light only,
because the trace from inside their own collision hull entered another hull brush.
Instances are moved by `R(angles) * pivot` so they stay where Source put them.

Collision hulls (`.phy` pieces → `modelconv._hull_brush`) must not depend on the pivot.
They did until the near-coplanar face merge compared plane distances from the origin:
moving car002a's pivot merged two roof faces 2° apart and grew a hull by 20 units.
The merge now tests the triangle against the kept plane, and every plane is written
as three points 64 units apart around the hull centre's projection
(`tests/test_modelconv.py::test_hull_brush_translation_invariant`; dust2 props now
differ by ≤ 0.2 units between pivots, from near-parallel face conditioning).

## Static props without MOHlight (`mohkit.staticlight`)

Static models never collide (the collision loader skips them), so they don't need to
exist when Q3map runs: the converter adds each prop's clip brushes to the world,
compiles and lights the map, then `staticlight.inject` appends the props to
STATICMODELDEF, lists each in the leaves its bounds touch and writes per-vertex
colours to STATICMODELDATA. A vertex's colour comes from the map's own lightmaps
(`staticlight.LightmapField`, since 2026-10-01): every lightmap texel is binned into
16-unit cells by facing (six axis slots), and each vertex marches against each slot's
direction to the first texels facing that way (the floor under a crate lights its top),
blended by its normal and scaled by 1.78 (`LIGHTMAP_TO_VERTEX`). Against MOHlight's
own static-model colours on mk_medina (21k vertices): correlation 0.56 (light grid
0.41), mean error 45 (grid 51), and the quantiles match at 1.8-2.1x throughout.
Vertices that find no texel within 256 units fall back to the light grid (32-unit
cells, sampled 6 units out, `staticlight.shade`; means within 2% of MOHlight on an
ambient-only map and on mk_medina).

**Why not the light grid:** MOHlight fills the grid without spotlight cones. A spot
aimed at the floor of a closed test room (`target` or `angles`, 60 degree cone) lights
a lit pool in the lightmaps, but the grid is a flat ramp that brightens with depth
below the lamp at any distance off-axis: 11 just under it, 58 at the floor (the floor
lightmap's peak is 59), even outside the cone. A point light's grid is uneven too
(113-254 above the lamp, 51-131 near the floor, brighter on one side of a symmetric room). dust2's tunnel crates near a ceiling spot got
grid values of 13-21 (black) while the floor around them was lit; the lightmap field
gives them 130-190. Players are fine: with `r_fastentlight 0` (the default) the engine
also lights them from the light entities at run time, and a third-person player under
that tunnel spot looked as lit as one in the sun. `tests/test_staticlight.py`.

OpenMoHAA draws every static model whose bounds pass the frustum test (the leaf
`visCount` check is commented out in `tr_staticmodels.cpp`); at most 8,192 static
surfaces a frame (`MAX_STATIC_MODELS_SURFS`). de_nuke's 4,801 props have 9,071 surfaces
in all, so only a view of nearly the whole map (the overview shot) can lose some.

## Known gaps

- Blend textures use the first layer only.
- Door handles and other relief of door and vent models are lost (slabs). Vents break
  (`func_window`, metal debris) instead of swinging open.
- Detail sprites (grass) are dropped.

## Measured builds (2026-10-01, Apple Silicon, three or four builds sharing 10 cores)

| map | quality | props injected (vertices) | overlays | BSP | VIS | light | shots | bots (8, 90 s) |
|---|---|---|---|---|---|---|---|---|
| cs_dust2 | draft (density 32) | 1,574 (842k) | 459 | 559 s | 1 s | 1,962 s | 32 named cameras, 47 s | 75 kills |
| cs_nuke | unlit | 4,801 (5.6M) | 718 | 261–489 s | 1 s | — | 38 named cameras, 59 s | 83 kills |
| cs_nuke | fastrad (04:43 code, spot fix; alone on the CPU) | 4,801 (5.6M) | 718 | 200 s | 1 s | 2,389 s | 38, 59 s | 70 kills |
| cs_dust2 | fastrad (03:15 code) | 1,574 (842k) | 459 | 684 s | 2 s | 2,752 s | 32, 47 s | 91 kills |
| cs_mirage | fastrad (03:13 code) | 1,470 (1.35M) | 512 | 293 s | 1 s | 2,672 s | 30, 45 s | 77 kills |

de_nuke's draft light at density 16 had reached 1% after 6 minutes; at density 32 the
first 10% still took ~15 minutes (progress is not linear: the slow part comes first).
