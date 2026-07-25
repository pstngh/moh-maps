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
be transferred directly to the Allied Assault BSP format, so each retained
displacement face is rebuilt as a thin 16-unit convex slab: the source outer
quad is visible and its inner/edge faces are caulked. This preserves a clean,
playable surface without exposing the large Source support solid, but it does
not reproduce the displaced vertex deformation. The result is therefore a
measured brush-layout replica rather than a byte-identical CS2 port.

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
wagon. Domes, upright drums, baskets, antennas, crates, and cover remain simple
generated brushes so their collision is deterministic. Tipped Source
cans/buckets and tilted drums are omitted because an upright AA substitute
would not preserve their placement.

## Extended-playtest repairs

The six-view bot playtest found floating props, visible nodraw rectangles,
layered displacement supports, and triangular ground overlaps. The converter
now applies these rules:

- rebuild all 61 playable displacement faces as thin slabs and discard their
  original support volumes;
- use real `common/caulk` for Source nodraw/helper faces;
- place generated crates from `origin.z - height / 2`;
- lower Source car origins by 28 units for AA's ground-rooted rusted car;
- lower `palm_tree_trunk.mdl` replacements by 536 units for AA's complete palm;
- omit tipped clutter instead of replacing it with an upright model.

The corrected final build contains 2,289 world brushes and 142 entities.
Q3map emitted 6,905 faces from 7,388 input faces with no leak or invalid-brush
error. Fast VIS processed 633 clusters, 2,003 portals, and 2,490 faces, with
550 clusters visible on average. MOHlight lit all 15 retained stock models.
OpenMoHAA 0.82.1 generated Recast navigation in 0.839 seconds and admitted two
bots from the exact packaged PK3.

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
