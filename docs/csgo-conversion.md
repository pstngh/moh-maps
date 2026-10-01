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
| ladder volumes (`CONTENTS_LADDER`) | `func_ladder`: `common/trigger` over the Source volume + 8 units on the climber's side, `common/origin` brush on the climb face, `angle` toward the wall | wall side = solid world contents behind the volume, else the side a static prop (the visible ladder) is on; stacked volumes merged. `Converter.ladders`, report `ladders` |
| water volumes | the drawn face gets a water shader (`surfaceparm water trans nonsolid`, image = the normal map's relief tinted with `$fogcolor`, alpha `$waterblendfactor`); hidden sides `common/waterskip` (caulk is solid and would fill the volume) | Source water has no base texture |
| breakable glass (`func_breakable`/`_surf` whose drawn materials are all `$surfaceprop glass`) | `func_window` (MOHAA breakable glass), Source `health` | |
| overlays (`info_overlay`, LUMP_OVERLAYS) | flat 3×3 patch half a unit off the surface; shader `ov_<material>`: `trans nonsolid nomarks polygonOffset`, `blendFunc blend` + `nextbundle $lightmap` like retail decals | U axis is packed in the z of UV points 0–2, V = N×U (negated if point 3's z is 1); overlays wrapped over corners/displacements are placed flat |
| doors (`prop_door_rotating`) | `func_rotatingdoor`: a brush slab between the model's two largest opposite faces, textured with the model's material (each face's texdef reproduces the UVs of the largest mesh triangle on it), origin brush on the hinge, `openangle` = `distance`, `time` = distance/speed, `alwaysaway` for two-way doors | door meshes can lie 90° off the frame their angles apply to (rotated root bone): the mesh is turned to match the MDL hull box (`_yaw_to_hull`); no static prop in de_nuke needs it |
| `env_fog_controller` | worldspawn `farplane` = fogend / fogmaxdensity, `farplane_color`, `farplane_cull 0` | |
| sky (`skyname`) | six faces from each face material's `$basetexture` | de_nuke's `nukeblank` faces all use `skybox/nukeblankup` (plain 90 134 186 blue) |
| spectator cameras (`maps/<map>_cameras.txt`) | contact-sheet shots (eye position, pitch/yaw as given), pages of 9 (`<name>_shots.png`, `_shots_2.png`, …) | `named_cameras` |
| 3D skybox (the area containing `sky_camera`) | dropped | detected from BSP areas, not bounds |
| displacements | `patchDef2` meshes | midpoint-expanded so they pass through every kept Source sample; sample rows/columns straight within `disp_tolerance` (1 unit) dropped, consistently across shared edges; split to ≤ 17×17; visible side toward the air |
| materials | TGA/JPG + generated shader script | `$basetexture` only (blends use the first layer); power-of-two, max 512 px; `$surfaceprop` → MOHAA material surfaceparm; alphatest/translucent/nocull handled |
| texture alignment | Q3 shift/rotate/scale | exact for any rotation, scale or mirror (`tests/test_texdef.py`) |
| `info_player_terrorist` / `counterterrorist` / `info_deathmatch_spawn` | `info_player_axis` / `allied` / `deathmatch` | T+CT double as DM spawns when the map has none |
| `light`, `light_spot` | `light` (+ `info_null` target) | intensity ≈ 0.75 × Source brightness, clamped 40–600 |
| `light_environment` | worldspawn `suncolor`, `sundirection`, `ambientlight`, `sundiffusecolor` | |
| static props (`prop_static`) | `mohkit/source/modelconv.py` (MDL → TIKI/SKD/SKC + collision `.map`). **Default (`props_mode="inject"`): every prop** becomes a static model added to the lit BSP by `mohkit.staticlight` and coloured from its light grid, with its collision as world clip brushes. `props_mode="compile"`: the largest as MOHlight-lit `static_*` up to `--static-verts`, the next 600 as `script_model`s | MOHlight lights static models on one thread (~190 verts/s), so de_nuke's 4,801 props would light for hours; injection takes seconds and costs no entities |

## Visibility and compile time

By default every converted brush is detail inside a structural caulk shell.
That compiles reliably; a Source layout imported as structural geometry
overflows MOHAA's 2 MB VIS buffer. The price is no VIS culling and a slow
BSP stage on big maps: tens of thousands of faces share one leaf. `--structural`
keeps Source's own world/detail split instead; try it on small maps.

**Displacements cost BSP time quadratically.** Q3map groups patches for LOD by
comparing every control point of every patch with every control point of every
other patch (`PatchMapDrawSurfs`, q3map `patch.c`). de_dust2's 619 patches
(118k control points) spent 673 s there, measured with timestamped logs.
Dropping straight sample lines halves the control points and cuts that work
3.9× (`Options.disp_tolerance`, default 1 unit; 2 units: 6.8×).

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
colours to STATICMODELDATA. A vertex's colour is the light grid (32-unit cells in v19)
sampled 6 units out along its normal, scaled like MOHlight's own static lighting and
shaded mildly by facing (`staticlight.shade`). Calibration against MOHlight output:
ambient-only test map 40.4 vs 40.3 mean over 161k vertices; sunlit mk_medina 129.7 vs
130.9 over 23k (per-vertex error is larger: MOHlight traces shadows per vertex, the grid
is 32 units coarse). `tests/test_staticlight.py`.

OpenMoHAA draws every static model whose bounds pass the frustum test (the leaf
`visCount` check is commented out in `tr_staticmodels.cpp`); at most 8,192 static
surfaces a frame (`MAX_STATIC_MODELS_SURFS`).

## Known gaps

- Blend textures use the first layer only.
- Openable/breakable props (`prop_dynamic` vent slats opened by `func_button` or `OnBreak`)
  aren't converted: those vents are open. Door handles and other relief are lost.
- Ropes and cables (`keyframe_rope`/`move_rope`), sprites and detail sprites are dropped.
