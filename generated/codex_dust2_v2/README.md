# Codex Dust II V2

`codex_dust2_v2` is a deathmatch-focused MoHAA/OpenMoHAA translation of the
Dust II brush layout, dressed with stock Allied Assault textures and a
V2-facility treatment.

## What is included

- The editable MoHAA `.map`
- Multiplayer and precache scripts
- The VMF analyzer and VMF-to-MoHAA converter
- The conversion report
- The PK3 packaging script

The reference VMF is intentionally **not** included. No Valve textures, models,
sounds, or other game assets are redistributed. The playable PK3 contains only
the compiled geometry and scripts and resolves its art from a normal retail
MoHAA installation.

## Fidelity boundary

The converter preserves ordinary source brush planes and source spawn
coordinates. It translates Source detail brushes into MoHAA world brushes,
skips editor-only helper volumes and the distant 3D skybox, and reconstructs
selected prop cover as simple collision brushes. A Source displacement cannot
be transferred directly to the Allied Assault BSP format. For each of the 61
retained faces, the converter now reconstructs every VMF grid point from the
bilinear base plane plus `offset + normal * distance`. It inserts arithmetic
midpoints between neighboring samples and emits one joined MoHAA patch per
retained displacement face. This makes every Source cell a bilinear Bezier
span, preventing the quadratic bowing caused by treating raw samples as
Bezier handles. The 61 patches preserve all 6,944 measured source-grid
triangles without the void seams produced by touching micro-brushes. The
result is still not a byte-identical CS2 port.

The stock texture palette is drawn from the same families used by MoHAA's V2
and related industrial maps:

- `general_structure/bunker_wall`
- `general_structure/jh_conc512b`
- `normandy/bunker_conc3`
- `normandy/bunk_ceiling`
- `wilderness/wldrrckset1_1`
- `algiers/whsflrset1_1b`
- `das_boot/ironwall1`
- `german/rusty_iron`
- `central_europe/shutter_set2`
- stock wood, crate, grate, and pipe materials

The rebuilt version also substitutes a small set of stock AA props for Source
props that cannot be transferred: four level rusted cars, eight palm trees,
and one wagon. Crates and cover remain simple generated brushes so their
collision is deterministic. The 112 omitted Dust facade-window models receive
large inset `bunker_wall` visual backings plus modest stock AA shutter faces
instead of exposing black or sky-colored holes.
Unsupported domes, antennas, steeply tilted cars, stone teeth, baskets, tipped
cans/buckets, and tilted drums are omitted because the available AA stand-ins
cannot preserve their placement.

## Screenshot-driven repairs

The two playtest batches found floating props, visible nodraw rectangles,
layered displacement supports, missing terrain, triangular voids, and buried
cars. The converter now applies these rules:

- reconstruct all 61 playable displacement grids as 61 midpoint-expanded
  patch meshes;
- retain the 60 original displacement-bearing brush hulls behind those patches,
  caulking the displaced base plane and texturing exposed perimeter faces so
  the patch undersides and boundaries cannot reveal the void;
- orient MOHAA's one-sided patch winding toward playable air using the source
  solid center;
- use real `common/caulk` for Source nodraw/helper faces;
- place generated crates from `origin.z - height / 2`;
- retain Source Z for level AA car substitutes; direct engine inspection and
  stock `obj_team4` placement both show that the model's raised entity origin
  is intentional;
- omit cars with more than five degrees of Source pitch or roll;
- lower `palm_tree_trunk.mdl` replacements by 536 units for AA's complete palm;
- back omitted window models with yaw-aligned non-solid masonry slabs and
  separately sized `central_europe/shutter_set2` faces;
- omit unsupported dome and antenna stand-ins;
- omit tipped clutter instead of replacing it with an upright model.

The corrected final build contains 2,330 ordinary world-brush records, 61
terrain patches, and 140 entities. Q3map emitted 6,801 brush faces from 7,316
input faces with no leak or invalid-brush error. Fast VIS processed 599
clusters, 1,913 portals, and 2,326 faces, with 547 clusters visible on average.
MOHlight
lit all 13 retained stock models; its old patch-lighting path reported 22
non-fatal potential-hash-mismatch warnings. OpenMoHAA loaded 6,740 brush faces
and 61 meshes from the exact final PK3, generated Recast navigation in 2.265
seconds, and ran eight bots that navigated and fought successfully.

## Regenerating

Place a legally obtained `de_dust2.vmf` at:

```text
work/references/de_dust2_reference.vmf
```

Then run from the workspace root:

```powershell
node work/mapgen/analyze_vmf.js work/references/de_dust2_reference.vmf
node work/mapgen/generate_dust2_v2.js
```

Compile the resulting map with Q3map, VIS, and MOHlight. `gameRoot` must be an
installed Allied Assault root whose `main` folder contains the retail PK3s:

```powershell
$map = Resolve-Path work/generated_dust2_v2/main/maps/dm/codex_dust2_v2.map

& work/MOHTools/Q3map.exe `
  -gamedir "gameRoot" -moddir main $map

& work/MOHTools/Q3map.exe `
  -vis -fast -gamedir "gameRoot" -moddir main $map

& work/MOHTools/MOHlight.exe `
  -gamedir "gameRoot" -moddir main $map
```

Do not compile this map against an empty staging directory. Q3map and MOHlight
need the retail shader scripts to resolve `common/caulk`, `sky/mohday1`, and
the stock material flags. Without them, the BSP can compile without a hard
error but render with a black sky and apparently missing surfaces.

Use a clean, retail-only compile root. A mod-heavy game directory can add
enough shader and surface definitions to overflow this old toolchain with
`MAX_SURFACE_INFO`, even though the generated map itself is within the BSP
limits.

Then package it:

```powershell
& work/mapgen/package_dust2_v2.ps1
```

## Playing

Copy `codex_dust2_v2.pk3` into the game's `main` folder, then use:

```text
g_gametype 1
map dm/codex_dust2_v2
```

For OpenMoHAA bots:

```text
sv_maxbots 8
sv_numbots 4
map dm/codex_dust2_v2
```
