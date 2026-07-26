# Codex Cobblestone - revision 4 seam and collision repair

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

Revision 4 preserves the source's explicit player clips and 46 measured large
collision volumes, adds low-detail material-matched underlays beneath
traversable planar terrain, and omits vegetation that cannot be grounded
safely. This targets source route fidelity and bright terrain seams without
reintroducing speculative Source-model geometry.

Important Source-model architecture is now omitted unless its real mesh,
bounds, pivot, or a measured per-family reconstruction is available. Repeated
instance spacing alone is not enough evidence to synthesize a replacement.
The old diagnostic geometry remains available only through
`--legacy-architectural-placeholders`; it is not release geometry.

The distant Source 3D skybox, non-collision editor helpers, gameplay systems
that have no AA equivalent, and most cosmetic Source props remain omitted.
Upright barrels, hay bales, coffins, and crates still become generated cover,
while a reduced selection of grounded trees and bushes uses stock AA static
models.

This is a layout translation, not a byte-identical CS map. The reference VMF
is intentionally not redistributed. Terrain remains angular where the original
uses displacement sculpting. Some distant arcade and decorative architecture
is omitted because the original surfaces exist only in Source model files,
not in the decompiled VMF brush data.

Visible doors are static by source intent. The reference has 33 door-model
props but no `func_door` or `func_door_rotating` entity. Interactive AA doors
would be a gameplay enhancement requiring measured pivots, swing clearance,
and separate bot testing.

## Current build

- 5,142 generated brushes or patches
- 4,702 converted source solids
- all 2,735 source `func_detail` solids retained
- 840 planarized displacement backing brushes
- 44 neutral deathmatch spawns, plus 22 Axis and 22 Allied spawns
- 65 translated Source fixture lights; no spawn-following fill lights
- 31 grounded stock-AA tree and bush entities
- 123 generated cover brushes
- 311 material-matched planar terrain seam underlays
- 3 source player-clip and 46 measured large collision brushes
- 299 unmeasured architectural model substitutions omitted
- 5,682 exposed nodraw faces assigned a material-matched fallback
- 448 planar displacement supports considered for grounding; 117 retained
  prop origins adjusted by no more than 64 units
- 27,373 final BSP faces and 90 fast-VIS clusters

OpenMoHAA 0.82.1 loaded the exact final revision-4 PK3, generated Recast
navigation in 6.575 seconds, and ran eight bots that moved, fought, respawned,
used corridors, and traversed exterior routes. The six-view bot-follow run
recorded ten kills. Automated fixed-camera and high-altitude surveys found no
giant underlay or architecture regression, though they did not reproduce
every exact ground-level user camera.

The revision removes incompatible floating vegetation and adds bounded visual
coverage beneath the diagnosed planar terrain seams. Restoring the measured
Source clip volumes improves collision fidelity but does not fully contain
bots; some exterior terrain and edge routes remain reachable. The omitted
Source 3D skybox and incomplete exterior boundary are now the principal
visible and routing debt.

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

- generated MAP: 4,237,412 bytes; SHA-256
  `8C05CCEEF9A3E91C53FC08A9E3BC698231DB994D943792B45494B91221193E58`
- BSP: 20,422,536 bytes; SHA-256
  `BEB92C96CBCDB6CB7F00755F97EBFACADBA4E184E7CC1FCFF48B80515E7DB8E6`
- PK3: 3,916,777 bytes; SHA-256
  `22862E336C2C1CF8014AF7CBE1984CF07B7F6FD1CAD76F5E953728179394D32F`
- source ZIP: 452,664 bytes; SHA-256
  `EC4B11984FD58540FBD32DAEF819F1B816ACEF7C5B70235605D3AA3E46282CE2`

The repository's [revision-4 report](REVISION-4.md) records the compile
diagnostics, exact runtime evidence, door-entity audit, reproducibility check,
and remaining limitations.
