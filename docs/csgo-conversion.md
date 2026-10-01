# Converting CS:GO maps

```sh
python -m mohkit csgo de_dust2                  # -> local/csgo/cs_dust2/{cs_dust2.map, assets/, cs_dust2.pk3, shots}
python -m mohkit csgo de_inferno --name cs_inferno -q normal
```

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
| hint, skip, areaportal, trigger, occluder, fog, blocklos, grenade/NPC clip, water, ladders | dropped (counted in the report) | ladders and water are TODO |
| 3D skybox (the area containing `sky_camera`) | dropped | detected from BSP areas, not bounds |
| displacements | `patchDef2` meshes | midpoint-expanded so they pass through every kept Source sample; sample rows/columns straight within `disp_tolerance` (1 unit) dropped, consistently across shared edges; split to ≤ 17×17; visible side toward the air |
| materials | TGA/JPG + generated shader script | `$basetexture` only (blends use the first layer); power-of-two, max 512 px; `$surfaceprop` → MOHAA material surfaceparm; alphatest/translucent/nocull handled |
| texture alignment | Q3 shift/rotate/scale | exact for any rotation, scale or mirror (`tests/test_texdef.py`) |
| `info_player_terrorist` / `counterterrorist` / `info_deathmatch_spawn` | `info_player_axis` / `allied` / `deathmatch` | T+CT double as DM spawns when the map has none |
| `light`, `light_spot` | `light` (+ `info_null` target) | intensity ≈ 0.75 × Source brightness, clamped 40–600 |
| `light_environment` | worldspawn `suncolor`, `sundirection`, `ambientlight`, `sundiffusecolor` | |
| static props (`prop_static`) | `mohkit/source/modelconv.py` (MDL → TIKI/SKD/SKC + collision `.map`). Largest first: `static_*` models up to `--static-verts` lit vertices (70k; **0 in `-q draft`**), the next 600 as non-solid `script_model` with baked clip brushes, the rest dropped (reported) | static-prop lighting is single-threaded (~190 verts/s at best), so the budget is compile time |

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

## Known gaps

- Static props (the cars, boxes, barrels, doors and trim that make CS maps
  look finished) are pending the model converter.
- Overlays and decals (`info_overlay`) aren't converted.
- Blend textures use the first layer only.
- No `func_ladder` conversion yet.
- Water is dropped.
