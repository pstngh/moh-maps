# Stalingrad Mirror (`codex_mohdm6_mirror`)

`codex_mohdm6_mirror` is a complete left/right inverse of the repository's Allied Assault `aa/mohdm6.map`. The reflection plane is world `x = 0`: what was east is west, while height and north/south placement stay unchanged. It is a separate map and does not replace retail `mohdm6`.

## Install and run

Copy `codex_mohdm6_mirror.pk3` into the Allied Assault `main` directory, then load:

```text
map dm/codex_mohdm6_mirror
```

Free-for-all, team, and bot spawn classes are retained. The package expects normal retail `Pak0.pk3` through `Pak6.pk3`.

## What was mirrored

The deterministic generator reflects every brush plane point and restores winding, reflects and reverses patch control rows, reverses terrain rows and triangle flags, and transforms entity origins and orientation keys. The world sun direction is reflected too. Target names, target links, class names, script keys, textures, light values, and gameplay metadata are otherwise unchanged.

| Preserved/transformed input | Count |
| --- | ---: |
| Brush faces | 13,938 |
| Patches | 68 |
| Terrain blocks / samples | 2 / 442 |
| Entity origins | 491 |
| Yaw angles / angle vectors | 115 / 2 |
| Sun directions | 1 |
| Neutral / Allied / Axis starts | 25 / 25 / 25 |
| Lights | 293 |

The validator confirms identical entity-class counts and a stable involution: applying the canonical reflection three times reproduces the first reflection byte-for-byte.

## Scripts and assets

The package contains only the mirrored BSP and two thin map-owned wrappers. The wrappers execute retail `mohdm6.scr` and `mohdm6_precache.scr`; no retail script or art payload is redistributed. Two bot-requested retail models are explicitly cached by the wrapper.

## Rebuild

From the repository root, with retail AA data and MOHTools in the adjacent default locations:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_mohdm6_mirror
```

The build regenerates and validates the MAP, runs original Q3map BSP, full VIS, full MOHlight, inspects the BSP, and produces a deterministic PK3 twice.

## Validation

- Q3map: 5.493 seconds; 63 warnings inherited from the stock editable source, principally absent optional static-model `.map` helpers and 36 exterior light leak diagnostics.
- VIS: 0.307 seconds.
- MOHlight: 32.851 seconds; three leaves clamped from 86, 81, and 64 lights to the retail 60-light limit; no hash warnings.
- BSP: version 19, 5,463 surfaces, 25 lightmap pages, 72,392 visibility bytes.
- Isolated OpenMoHAA 0.82.1-beta root: exactly Pak0-Pak6 plus this PK3; BSP parsed in 0.044 seconds and Recast completed in 0.500 seconds.
- Eight bots entered and produced two classified combat events in the final ten-second report; candidate-specific diagnostics and script errors were zero.

The retained compiler warnings are not claimed clean. They arise while recompiling the supplied stock editable source and are recorded in `codex_mohdm6_mirror-build-report.json`.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Editable MAP | 1,700,554 | `d10bf1ae1caf744504146be6bd6cda81e40e92dc49639704933b988ac969908c` |
| BSP | 4,495,204 | `57ff1b395012c1a792d3046296441907daeff28baa79f19a31c96bfa728f0a22` |
| PK3 | 874,060 | `43278a35d28cc64c32827479a4c30a66440f38f5c7350f94f6049b04ae102585` |

The PK3 has exactly three entries and reproduced byte-identically twice.

## Known debt

- A human visual sweep remains the final appearance gate. The desktop session loaded the renderer but could not obtain a reliable post-load capture through its window-capture path, so no visual acceptance is claimed.
- This is a geometric inverse of the supplied AA source, not a hand-restored replacement for any discrepancy between that editable source and EA's shipped BSP.
- Stock-source Q3map leak/helper warnings and the three retail light clamps remain unchanged and documented.
