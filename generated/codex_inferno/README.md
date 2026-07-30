# Codex Inferno

> **Current status: revision 3 playable candidate; human visual review pending.**
> Revision 3 compiles, lights, packages, builds OpenMoHAA navigation, and
> supports sustained eight-bot combat. It replaces the rejected maze-like
> revision 2 architecture with complete callout-zoned village masses. Do not
> call it a visually accepted baseline until the user's ground-level and
> overview screenshots confirm recognition.

`codex_inferno` is a manually reauthored Allied Assault/OpenMoHAA clone of the
supplied CS:GO Inferno layout. The private Source files are used only as
measurement and comparison inputs. No Valve brush, texture, model, sound, or
embedded asset is distributed.

## Revision 3 inventory

- the measured T, Alt/Second Mid, Mid, Apartments, A, Arch/Library, CT,
  Banana, and B footprint;
- 6,997 collision-verified 32-unit walk cells and 13,420 route edges retained
  as a connectivity oracle rather than rendered as walls;
- 479 merged walk-floor plates surrounded by 455 complete building masses
  derived from 9,750 filled non-route columns;
- 222 measured indoor separation runs; zero rendered outdoor grid-wall runs;
- 455 roofs, including 26 gable silhouettes, plus ten major passage arches;
- measured A/B sites, correctly scaled B fountain, CT well, B coffins/barrels,
  A hay/boxes, balconies, and bell-tower silhouette;
- 20 Axis, 20 Allied, and 67 neutral DM spawns derived from supplied origins;
- sixteen original bundled 512x512 textures and stock AA sky/utility shaders;
- warm Mediterranean direct sun, cool environment fill, low ambient, and
  fourteen interior lights;
- 1,805 worldspawn brushes and 10,457 draw surfaces, using 7.45 MB of Q3map's
  original 10.00 MB BSP budget.

See [`REVISION-3.md`](REVISION-3.md) for exact evidence and
[`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for the private-reference audit.
Revisions 1 and 2 remain documented as rejected fidelity baselines.

## Install and play

Copy `codex_inferno.pk3` into the game's `main` directory, then run:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_inferno
```

The map targets simple DM/TDM play against bots. The Source audit found one
real rotating door. Revision 3 leaves that route open and does not ship a
dynamic door while its AA pivot, swing clearance, and bot value remain
unverified.

## Regenerate

From the repository root, using the committed measured blueprint:

```powershell
python generated/codex_inferno/tools/build_original_textures.py
node generated/codex_inferno/tools/generate_inferno.js
node generated/codex_inferno/tools/validate_inferno_build.js
```

`generate_inferno.js` and `validate_inferno_build.js` are the stable revision-3
entry points. The private VMF is needed only to reproduce the source audit:

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

The six sky-shell brushes are structural. Internal route and village geometry
uses MOHAA's `+surfaceparm detail` form to retain collision/lighting without
exceeding Q3map's fixed portal-data limit.

## Validation evidence

- all 7,921 reference solids reconstructed with zero failures;
- all 107 supplied spawns matched to the collision-verified route graph;
- official radar transform and callout anchors agree with the authored plan;
- static revision-3 validator passes with no failures;
- Q3map: 10,457 faces from 10,824 inputs in 44 seconds;
- fast VIS: 36 clusters, 60 portals, 296 visibility bytes;
- full MOHlight: 73 seconds, ambient `8 9 12`, zero stderr warnings;
- Q3map `-info`: 1,805 brushes, 10,457 draw surfaces, 65 lightmaps, and
  7.45 MB of the original 10.00 MB BSP budget;
- exact-PK3 OpenMoHAA load: BSP parse 0.035 seconds, Recast 0.611 seconds;
- eight bots admitted and 11 combat/death events in the timed sample;
- zero fatal runtime errors.

## Known debt and next gate

Revision 3 is a recognition-first massing baseline, not a claimed 1:1 art
finish. It intentionally omits Source props/models, displacements, graffiti,
signs, dense clutter, and dynamic door behavior. Facade windows are not yet
generated, slopes are simplified, and some village silhouettes remain
blockier than the reference. The next evidence must be user screenshots from
T spawn, Mid, Apartments, A, CT, Banana, B, and a high overview. Fix visible
architectural errors before adding cosmetic detail.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 1,230,507 | `6A683B7D88EEBF6C2440CD1971EB29F4912AA72D5043BAA5ED60E64A38E108B8` |
| BSP | 8,353,932 | `F5B9DD04F06513A0C51BAA764A21D57F8F9FE5D41678273BA1B65026B711CD5F` |
| PK3 | 5,507,308 | `10EB9994BD08354846C8B0A9DD57579F977B79994F23EC7513EE259E9B65C6CB` |

The durable blueprint SHA-256 is
`D5C30783387415C9C57CDB1608B07F8C04CC5DF4A460A8BD4ED3ADD5F8AFF8B0`.
