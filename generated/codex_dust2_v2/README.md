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
Bezier handles. The 61 surface patches preserve all 6,944 measured source-grid
triangles without the void seams produced by touching micro-brushes.

The surface alone is not enough at a displacement perimeter: displaced edge
points can move away from the original support hull and expose the void. The
converter therefore adds 235 quadratic boundary-skirt patches joining every
moved surface edge back to its undisplaced base edge. Long edges are divided
at the same Source-cell boundaries as the main mesh. The result has 296 terrain
meshes in total: 61 measured surfaces plus 235 skirts representing 3,480
additional sealing triangles. AA's legacy patch parser expects dimensions in
row-record-first order (`rows columns`); this matters for rectangular skirts
and was hidden while all earlier patches were square. The result is still not
a byte-identical CS2 port.

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

## Lighting

The lighting is an original AA-compatible Mediterranean daylight profile. It
uses a warm cream directional sun (`135 116 88`) against cooler diffuse sky
fill (`58 66 84`), low cool ambient (`8 9 11`), and a neutral blue-gray
farplane. This gives outdoor geometry directional shape without copying the
lighting of V2, `obj_team2`, or a Breakthrough map.

Earlier builds forced all 25 retained Source fixtures to at least 450 intensity
and placed 20 additional 550-intensity lights over multiplayer spawns. That
made the level uniformly tan and flattened the architecture. The generator now
removes all spawn-following lights and translates only the real Source fixtures
into AA's practical range. The final 25 lights range from 24 to 150 intensity,
with median 60 and average 72.4. Interiors remain darker than courtyards but
retain readable surfaces and player silhouettes.

## Screenshot-driven repairs

Successive playtest batches found floating props, visible nodraw rectangles,
layered displacement supports, missing terrain, triangular voids, buried
cars, and finally open bands between displaced surfaces and their support
hulls. The converter now applies these rules:

- reconstruct all 61 playable displacement grids as 61 midpoint-expanded
  patch meshes;
- retain the 60 original displacement-bearing brush hulls behind those patches,
  caulking the displaced base plane and texturing exposed perimeter faces so
  the patch undersides have a closed volume;
- add 235 material-matched patch skirts between moved displacement boundaries
  and their corresponding base-hull edges so neither large wall bands nor
  small triangular wedges can reveal the void;
- orient MOHAA's one-sided patch winding toward playable air using the source
  solid center;
- use real `common/caulk` for Source nodraw/helper faces;
- place generated crates from `origin.z - height / 2`;
- snap the four retained AA car substitutes to the nearest 64-unit local grade
  when the Source origin is within 32 units of it; the retail
  `vehicle_car_rusted.tik` Quaked bounds and collision maps both begin at
  model Z=0, so the entity origin is the contact plane;
- preserve each retained car's Source pitch, yaw, and roll, and start its
  generated collision volume at the same grounded entity Z;
- omit cars with more than five degrees of Source pitch or roll;
- lower `palm_tree_trunk.mdl` replacements by 536 units for AA's complete palm;
- back omitted window models with yaw-aligned non-solid masonry slabs and
  separately sized `central_europe/shutter_set2` faces;
- omit unsupported dome and antenna stand-ins;
- omit tipped clutter instead of replacing it with an upright model.

The corrected final build contains 2,330 ordinary world-brush records, 296
terrain patches, and 120 entities. Q3map emitted 7,036 brush faces from 7,551
input faces with no leak or invalid-brush error. Fast VIS processed 599
clusters, 1,913 portals, and 2,326 faces, with 547 clusters visible on average.
MOHlight lit all 13 retained stock models; its old patch-lighting path reported
58 non-fatal potential-hash-mismatch warnings. OpenMoHAA loaded 6,740 faces
and all 296 meshes from the exact lighting-revision package, generated Recast
navigation in 3.171 seconds, and ran eight bots that navigated and fought
successfully. Two eight-viewpoint lighting passes covered sunlit routes,
shadow transitions, and the darkest retained-fixture interior.

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
