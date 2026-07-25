# Codex Cobblestone — initial playable conversion

`codex_cobblestone` is an Allied Assault/OpenMoHAA deathmatch translation of
the classic Counter-Strike Cobblestone layout. It uses only stock Allied
Assault textures and models.

## What this first build preserves

The generator converts ordinary world, selected `func_detail`, and
`func_brush` solids and preserves all 44 original team spawn coordinates. A
structural six-brush AA sky shell encloses the imported layout; imported
geometry is flagged detail so it remains solid without exceeding Q3map's fixed
2 MiB portal-data limit.

The default playable build keeps all Source displacement backing brushes as
planar, textured collision. Exact displacement reconstruction exists behind
`--full-displacements`, including ordinary BSPSource `dispinfo`, patch
surfaces, backing hulls, and terrain-only boundary skirts, but the complete
839-surface result is currently too expensive for the legacy Q3map compiler.

Source `func_detail` brushes with a bounding-box volume below 65,536 cubic
units are omitted. This removes 1,514 thin trim fragments while preserving
1,221 larger detail solids such as walls, roofs, stairs, and major façade
sections. The distant Source 3D skybox, editor helpers, gameplay systems that
have no AA equivalent, and most cosmetic Source props are also omitted.

Important castle props receive deliberately simple AA-native replacements:

- arches and ports become non-solid three-piece stone frames;
- windows, doors, and grates become non-solid stock-textured panels;
- upright barrels, hay bales, coffins, and crates become generated cover;
- a reduced selection of trees and bushes uses stock AA static models.

This is a layout translation, not a byte-identical CS map. The reference VMF
is intentionally not redistributed. Some thin Source-only frames and prop
fragments are visibly absent or floating in this initial revision; terrain is
angular where the original uses displacement sculpting.

## Current build

- 3,938 generated world/detail/prop brushes
- 3,140 converted source solids
- 840 planarized displacement backing brushes
- 44 neutral deathmatch spawns, plus 22 Axis and 22 Allied spawns
- 65 translated Source fixture lights; no spawn-following fill lights
- 74 stock-AA tree and bush entities
- 123 generated cover brushes, 193 arch/port replacements, and 90 façade panels
- 18,610 final BSP faces and 90 fast-VIS clusters

OpenMoHAA 0.82.1 loaded the final PK3 and ran eight bots that moved, fought,
used corridors, and traversed exterior routes. Eight spectator viewpoints
were inspected after the bot test.

## Regenerating

Place a legally obtained `de_cbble.vmf` at:

```text
work/references/de_cbble_reference.vmf
```

Run from the workspace root:

```powershell
node work/mapgen/analyze_vmf.js work/references/de_cbble_reference.vmf
node work/mapgen/generate_cobblestone.js
```

The experimental curved-displacement output can be generated explicitly:

```powershell
node work/mapgen/generate_cobblestone.js `
  work/references/de_cbble_reference.vmf `
  work/generated_cobblestone `
  codex_cobblestone `
  --full-displacements
```

Compile the default generated map against a clean retail Allied Assault
installation with Q3map, fast VIS, and MOHlight:

```powershell
$map = Resolve-Path work/generated_cobblestone/main/maps/dm/codex_cobblestone.map

& work/MOHTools/Q3map.exe `
  -fast -threads 4 -gamedir work/compile_retail -moddir main $map

& work/MOHTools/Q3map.exe `
  -vis -fast -threads 4 -gamedir work/compile_retail -moddir main $map

& work/MOHTools/MOHlight.exe `
  -threads 4 -gamedir work/compile_retail -moddir main $map
```

Then package it with:

```powershell
& work/mapgen/package_cobblestone.ps1
```

## Playing

Copy `codex_cobblestone.pk3` into the game's `main` folder, then use:

```text
g_gametype 1
map dm/codex_cobblestone
```

For OpenMoHAA bots:

```text
sv_maxbots 8
sv_numbots 4
map dm/codex_cobblestone
```

## Artifact fingerprints

- BSP: 14,511,848 bytes; SHA-256
  `8C7404BA4C21B45906D623208845AB7C498BF96662CCA39A4F8F953F9DF3AA7C`
- PK3: 2,857,786 bytes; SHA-256
  `C3F0455695E71001948743348C86659033D43512DA6899CDB8BDC3C517A50E7E`
