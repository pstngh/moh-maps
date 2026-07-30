# Codex Inferno

`codex_inferno` revision 2 is a manually reauthored Allied Assault/OpenMoHAA
clone of the supplied CS:GO Inferno layout. “From scratch” describes how the
geometry is built, not permission to invent a different map: the VMF is used as
a measurement/reference drawing while the output remains MOHAA-native.

Revision 1's generic Inferno-like arena was rejected after the user's first
screenshots because it was not recognizable as Inferno. Revision 2 replaces it
under the same map and package name.

## Current build

- actual measured T, Mid/Alt Mid/Apartments, A, Arch/Library, CT, Banana, and B
  footprint;
- 6,997 collision-verified 32-unit walk cells and 13,420 permitted route edges;
- 479 merged floor plates, 1,058 wall runs, 77 enclosed wood-route ceiling
  plates, and 2,683 total worldspawn brushes;
- measured A/B target positions, B fountain/coffins/barrels, A hay/boxes, ten
  passage arches, four balconies, and a bell-tower silhouette;
- 20 Axis, 20 Allied, and 67 neutral DM spawns derived from supplied origins;
- sixteen original bundled 512x512 textures; no Source texture/model content;
- warm Mediterranean sun, cool environment fill, low ambient, and fourteen
  interior lights;
- compiled below the original 10 MB Q3map BSP budget and validated with eight
  OpenMoHAA bots.

See [`REVISION-2.md`](REVISION-2.md) for exact evidence and
[`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for the reconstruction method.

## Install and play

Copy `codex_inferno.pk3` into the game's `main` directory, then run:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_inferno
```

The map targets simple DM/TDM play against bots. Doors are represented as open
route geometry or static facade detail; revision 2 does not add interactive
door logic.

## Regenerate

From the repository root, using the committed measured blueprint:

```powershell
python generated/codex_inferno/tools/build_original_textures.py
node generated/codex_inferno/tools/generate_inferno.js
node generated/codex_inferno/tools/validate_inferno_build.js
```

`generate_inferno.js` and `validate_inferno_build.js` are stable entry points
for revision 2. The source VMF is only required to reproduce the audit itself:

```powershell
node generated/codex_inferno/tools/audit_inferno_layout.js `
  "path/to/de_inferno_d.vmf" generated/codex_inferno
```

Compile against a clean Allied Assault root containing retail Pak0-Pak6:

```powershell
Q3map.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

Q3map.exe -vis -fast -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

MOHlight.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

powershell -ExecutionPolicy Bypass `
  -File generated/codex_inferno/tools/package_inferno.ps1
```

The six sky-shell brushes are structural. Internal route/facade geometry is in
worldspawn with `+surfaceparm detail`, which preserves collision and lighting
without exceeding Q3map's fixed portal-data limit.

## Validation evidence

- all 7,921 reference solids reconstructed with zero failures;
- all 107 supplied spawns matched to the collision-verified route graph;
- static revision-2 validator passes with no failures;
- Q3map: 15,717 faces from 16,111 inputs in 98 seconds;
- fast VIS: 36 clusters, 60 portals, 296 visibility bytes;
- full MOHlight: ambient `8 9 12`;
- Q3map `-info`: 9.69 MB of the original 10.00 MB BSP budget;
- exact-PK3 OpenMoHAA load: BSP parse 0.054 seconds, Recast 1.916 seconds;
- eight bots admitted and 8 combat deaths in 38 seconds;
- zero fatal runtime errors.

## Remaining debt

The first human visual pass of revision 2 is still required. Runtime evidence
does not prove that every facade, elevation transition, prop substitute, or
sightline looks correct. Future work must use callout/location-specific
screenshots and preserve the measured route graph unless a photographed defect
proves the graph itself is wrong.

Revision 1 is historical/rejected evidence, not a fallback release. See
[`REVISION-1.md`](REVISION-1.md).

## Artifact fingerprints

- MAP: 1,825,136 bytes; SHA-256
  `117DDF45E264A87DEC64D094E0720B08016D265EC8A33EA4E3689B1489E85414`
- BSP: 10,982,668 bytes; SHA-256
  `FA8E27CC0D00D5D1EA17A1E64E4795A04A68B4EDA26F8E0858346DC126A0C1F9`
- PK3: 6,007,217 bytes; SHA-256
  `D5F31886CB7390F9DAB7D7FE418079CB91A2FF2E5745FE61BEAC36384F8D8777`
