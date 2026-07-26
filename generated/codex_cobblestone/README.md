# Codex Cobblestone - revision 2 repair

`codex_cobblestone` is an Allied Assault/OpenMoHAA deathmatch translation of
the classic Counter-Strike Cobblestone layout. It uses only stock Allied
Assault textures and models.

## What this build preserves

The generator converts ordinary world, all `func_detail`, and `func_brush`
solids and preserves all 44 original team spawn coordinates. A
structural six-brush AA sky shell encloses the imported layout; imported
geometry is flagged detail so it remains solid without exceeding Q3map's fixed
2 MiB portal-data limit.

The default playable build keeps all Source displacement backing brushes as
planar, textured collision. Exact displacement reconstruction exists behind
`--full-displacements`, including ordinary BSPSource `dispinfo`, patch
surfaces, backing hulls, and terrain-only boundary skirts, but the complete
839-surface result is currently too expensive for the legacy Q3map compiler.

Revision 1 filtered 1,514 small `func_detail` solids to shorten Q3map compile
time. User screenshots proved that some were thin wall skins, floors, and
ceilings rather than cosmetic trim. Revision 2 retains all 2,735 source detail
solids; the resulting Q3map stage takes about 12-14 minutes on the validation
machine but restores the missing building shells. The distant Source 3D
skybox, editor helpers, gameplay systems that have no AA equivalent, and most
cosmetic Source props remain omitted.

Important castle props receive deliberately simple AA-native replacements:

- arches and ports become non-solid three-piece stone wall modules;
- windows, doors, and grates become non-solid stock-textured panels;
- upright barrels, hay bales, coffins, and crates become generated cover;
- a reduced selection of trees and bushes uses stock AA static models.

This is a layout translation, not a byte-identical CS map. The reference VMF
is intentionally not redistributed. Terrain remains angular where the original
uses displacement sculpting. Some distant arcade and decorative architecture
is simplified because the original surfaces exist only in Source model files,
not in the decompiled VMF brush data.

## Current build

- 5,471 generated world/detail/prop brushes
- 4,653 converted source solids
- all 2,735 source `func_detail` solids retained
- 840 planarized displacement backing brushes
- 44 neutral deathmatch spawns, plus 22 Axis and 22 Allied spawns
- 65 translated Source fixture lights; no spawn-following fill lights
- 74 stock-AA tree and bush entities
- 137 generated cover brushes, 195 arch/port replacements, and 90 facade panels
- 25,873 final BSP faces and 90 fast-VIS clusters

OpenMoHAA 0.82.1 loaded the final PK3 and ran eight bots that moved, fought,
used corridors, and traversed exterior routes. Eight spectator viewpoints
were inspected after the bot test. The revision specifically removes the
large open-sky wall fields, floating door/window groups, interior shell holes,
and missing floor/ceiling surfaces visible in the first user playtest.

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

- BSP: 18,722,768 bytes; SHA-256
  `89A9FD5A42C0D3F4E998455A609764E9EA75080C66358AC6865FB768ADAE23F9`
- PK3: 3,694,818 bytes; SHA-256
  `B63199BB5A044D9ADA1A21F665D819DF899CBDA200EE722745806E97A15E99C5`
