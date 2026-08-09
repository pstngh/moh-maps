# V2 Facility Mirror (`codex_obj_team2_mirror`)

`codex_obj_team2_mirror` is a complete left/right inverse of the repository's Allied Assault `aa/obj_team2.map`. The reflection plane is world `x = 0`; the result is a separate Objective map and does not replace retail `obj_team2`.

## Install and run

Copy `codex_obj_team2_mirror.pk3` into the Allied Assault `main` directory, select Objective mode, then load:

```text
map obj/codex_obj_team2_mirror
```

The package expects normal retail `Pak0.pk3` through `Pak6.pk3`.

## What was mirrored

The deterministic transform reflects every brush plane while restoring winding; reflects and reverses patch control rows; reverses legacy terrain rows, texture controls, and paired triangle flags; and transforms all entity origins, yaw/angle vectors, and the sun direction. Target names, links, objective keys, class names, materials, light values, and scripts remain authoritative.

| Preserved/transformed input | Count |
| --- | ---: |
| Brush faces | 35,217 |
| Patches | 708 |
| Terrain blocks / samples | 7 / 8,479 |
| Terrain texture controls | 177 |
| Entity origins | 595 |
| Yaw angles / angle vectors | 249 / 71 |
| Neutral / Allied / Axis starts | 14 / 16 / 16 |
| Rotating doors | 23 |
| Lights | 181 |

The validator confirms identical entity-class counts and a stable involution: applying the canonical reflection three times reproduces the first reflection byte-for-byte.

## Scripts and assets

The package contains only the mirrored BSP and two thin wrappers. They execute retail `obj_team2.scr` and `obj_team2_precache.scr`; no retail script, texture, or model payload is redistributed. The wrapper explicitly caches the retail bot bazooka explosion effect.

One retail terrain image is extracted from Pak2 only into the ignored build root because original MOHlight cannot read it directly from the archive during this map's terrain pass. It is never included in the output PK3.

## Rebuild

From the repository root, with retail AA data and MOHTools in the adjacent default locations:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team2_mirror
```

The config pins MOHlight to one thread. Four-thread MOHlight reproduced an access violation on this large stock source; single-thread MOHlight completed deterministically.

## Validation

- Q3map: 127 seconds; no leaks or degenerate diagnostics; 124 stock-source warnings, primarily absent optional static-model `.map` helpers plus the source's existing `textures/notexture` reference.
- VIS: completed with 39,608 visibility bytes.
- MOHlight: 517.7 seconds, one thread; no light clamps and no hash warnings.
- BSP: version 19, 18,333 surfaces, 59 lightmap pages.
- Intended Objective mode, isolated OpenMoHAA 0.82.1-beta root: exactly Pak0-Pak6 plus this PK3; BSP parsed in 0.114 seconds, Recast completed in 1.852 seconds, and eight bots entered and joined teams.
- FFA topology exercise: Recast completed in 1.853 seconds; eight bots entered and produced four classified combat events in 25 seconds.
- Candidate-specific load diagnostics were zero in both reports.

Objective mode logged five legacy `global/obj_dm.scr` script errors around the optional control-room target. A separate isolated retail `obj/obj_team2` run using only Pak0-Pak6 logged the same five errors, eight bots, and matching null-listener context. This is inherited retail behavior, not a mirror-only regression. The FFA run is only a bot movement/combat proof; Objective mode remains the intended gameplay.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Editable MAP | 5,484,624 | `91d14682e39cb79bc1f9d0fc50319b8ceac9b970dd2de4a6e14690ed94b0a183` |
| BSP | 12,342,844 | `d90ec65f3ec876a6b13b6884780cc58820ae3905df4f0182969f054ef096cd39` |
| PK3 | 2,187,167 | `3f94073eae1d6ac9f56827b8357c1e26807df8c012a4b04b2a18e337b31b5c81` |

The PK3 has exactly three entries and reproduced byte-identically twice.

## Known debt

- A human visual and objective-interaction sweep remains the final acceptance gate. The desktop session loaded the renderer but could not obtain a reliable post-load capture through its window-capture path, so no visual or end-to-end objective completion claim is made.
- This reflects the supplied AA editable source, not the shipped BSP. Any pre-existing source-versus-retail-BSP discrepancy remains possible.
- Existing optional editor-helper and `textures/notexture` compile warnings remain documented rather than hidden.
- The five intended-mode `obj_dm.scr` errors remain because a retail baseline reproduces them exactly.
