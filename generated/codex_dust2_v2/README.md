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
bilinear base plane plus `offset + normal * distance`, then emits joined 3x3
MoHAA patch meshes. The 868 patches share all three control points along each
common edge, eliminating the void seams produced by thousands of touching
micro-brushes. Q3 patches interpolate quadratically rather than using Source's
linear triangle tessellation, so the result preserves the measured terrain
shape closely but is still not a byte-identical CS2 port.

The stock texture palette is drawn from the same families used by MoHAA's V2
and related industrial maps:

- `general_structure/bunker_wall`
- `general_structure/jh_conc512b`
- `normandy/bunker_conc3`
- `normandy/bunk_ceiling`
- `algiers/whsflrset1_1b`
- `das_boot/ironwall1`
- `german/rusty_iron`
- stock wood, crate, grate, and pipe materials

The rebuilt version also substitutes a small set of stock AA props for Source
props that cannot be transferred: six rusted cars, eight palm trees, and one
wagon. Crates and cover remain simple generated brushes so their collision is
deterministic. Unsupported domes and antennas are omitted because the earlier
brush stand-ins floated where their Source support models were absent. Tipped
Source cans/buckets and tilted drums are also omitted because an upright AA
substitute would not preserve their placement.

## Screenshot-driven repairs

The two playtest batches found floating props, visible nodraw rectangles,
layered displacement supports, missing terrain, triangular voids, and buried
cars. The converter now applies these rules:

- reconstruct all 61 playable displacement grids as 868 joined patch meshes;
- orient MOHAA's one-sided patch winding toward playable air using the source
  solid center;
- use real `common/caulk` for Source nodraw/helper faces;
- place generated crates from `origin.z - height / 2`;
- retain Source car Z origins instead of applying the incorrect fixed -28
  offset;
- lower `palm_tree_trunk.mdl` replacements by 536 units for AA's complete palm;
- omit unsupported dome and antenna stand-ins;
- omit tipped clutter instead of replacing it with an upright model.

The corrected final build contains 2,171 ordinary world brushes, 868 terrain
patches, and 142 entities. Q3map emitted 6,725 brush faces from 7,216 input
faces with no leak or invalid-brush error. Fast VIS processed 602 clusters,
1,898 portals, and 2,344 faces, with 549 clusters visible on average. MOHlight
lit all 15 retained stock models; its old patch-lighting path reported four
non-fatal potential-hash-mismatch warnings. OpenMoHAA 0.82.1 loaded 5,857
brush faces and all 868 meshes, and the automated screenshot check showed a
continuous, walkable floor without the prior black triangular holes.
An exact-package dedicated-server check built Recast navigation in 0.884
seconds and admitted `bot1` and `bot2`.

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
