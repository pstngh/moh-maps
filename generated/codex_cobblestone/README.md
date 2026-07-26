# Codex Cobblestone - revision 3 visual repair

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
ceilings rather than cosmetic trim. Revision 2 restored all 2,735 source
detail solids. Revision 3 keeps that structural repair while removing 299
unmeasured architectural placeholders that caused floating arches, ribs,
shutters, doors, and facade panels.

Important Source-model architecture is now omitted unless its real mesh,
bounds, pivot, or a measured per-family reconstruction is available. Repeated
instance spacing alone is not enough evidence to synthesize a replacement.
The old diagnostic geometry remains available only through
`--legacy-architectural-placeholders`; it is not release geometry.

The distant Source 3D skybox, editor helpers, gameplay systems that have no AA
equivalent, and most cosmetic Source props remain omitted. Upright barrels,
hay bales, coffins, and crates still become generated cover, while a reduced
selection of trees and bushes uses stock AA static models.

This is a layout translation, not a byte-identical CS map. The reference VMF
is intentionally not redistributed. Terrain remains angular where the original
uses displacement sculpting. Some distant arcade and decorative architecture
is omitted because the original surfaces exist only in Source model files,
not in the decompiled VMF brush data.

## Current build

- 4,782 generated world/detail/prop brushes
- 4,653 converted source solids
- all 2,735 source `func_detail` solids retained
- 840 planarized displacement backing brushes
- 44 neutral deathmatch spawns, plus 22 Axis and 22 Allied spawns
- 65 translated Source fixture lights; no spawn-following fill lights
- 74 stock-AA tree and bush entities
- 123 generated cover brushes
- 299 unmeasured architectural model substitutions omitted
- 5,682 exposed nodraw faces assigned a material-matched fallback
- 448 planar displacement supports considered for grounding; 117 retained
  prop origins adjusted by no more than 64 units
- 27,062 final BSP faces and 90 fast-VIS clusters

OpenMoHAA 0.82.1 loaded the exact final revision-3 PK3 and ran eight bots that
moved, fought, used corridors, and traversed exterior routes. Eight bot-follow
and ten fixed-camera viewpoints were inspected. The revision removes the
repeated U-frame/rib fields, floating shutter and door groups, black facade
panels, and tested floor/support cuts visible across the 19-screenshot user
playtest. The final material pass maps Cobblestone's `outwall02` and
`trimwall01` families to the established stock stone instead of bright
plaster.

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

The removed revision-2 placeholders can be emitted for a controlled diagnostic
comparison, but should not be shipped:

```powershell
node work/mapgen/generate_cobblestone.js `
  work/references/de_cbble_reference.vmf `
  work/generated_cobblestone `
  codex_cobblestone `
  --legacy-architectural-placeholders
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

- BSP: 19,716,348 bytes; SHA-256
  `43BF77D445D00842165CBD9C62DA9FBFE36E30CD2F575E6F263CDE0894203A69`
- PK3: 3,877,188 bytes; SHA-256
  `A0452E095D4E7A0AFC82A6DDCFAFF211A223C16A5FD9D54F273B4499B9CB4651`

The repository's revision-3 report records the complete compile measurements,
visual evidence, source-bundle fingerprint, and remaining limitations.
