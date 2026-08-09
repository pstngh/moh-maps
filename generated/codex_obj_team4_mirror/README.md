# The Bridge Mirror (`codex_obj_team4_mirror`)

`codex_obj_team4_mirror` is a complete left/right inverse of the repository's Allied Assault `aa/obj_team4.map`. The reflection plane is world `x = 0`; the result is a separate Objective map and does not replace retail `obj_team4`.

## Install and run

Copy `codex_obj_team4_mirror.pk3` into the Allied Assault `main` directory, select Objective mode, then load:

```text
map obj/codex_obj_team4_mirror
```

The package expects normal retail `Pak0.pk3` through `Pak6.pk3`.

## What was mirrored

The deterministic transform reflects every brush plane while restoring winding; reflects and reverses patch control rows; reflects legacy terrain vertices, triangle flags, and cell-owned material controls; and transforms entity origins, yaw/angle vectors, and the sun direction. Target names, links, bridge-bomb objective keys, class names, materials, light values, and scripts remain authoritative.

| Preserved/transformed input | Count |
| --- | ---: |
| Brush faces | 23,671 |
| Patches | 174 |
| Terrain blocks / samples | 5 / 29,229 |
| Terrain material controls | 543 |
| Entity origins | 515 |
| Yaw angles / angle vectors | 247 / 1 |
| Neutral / Allied / Axis starts | 1 / 19 / 17 |
| Rotating doors / windows | 13 / 21 |
| Lights | 176 |

The validator confirms identical entity-class and entity-key counts, the preserved non-transform key/value multiset, an exact canonical configured transform, and a stable involution: applying the configured reflection three times reproduces the first reflection byte-for-byte.

## Terrain and compiler findings

MOH terrain material controls own 8-by-8 cells; the last control in each row is a boundary sentinel. Reversing the entire control row shifts every material owner by one cell. `obj_team4` exposed this because its source contains an intentional 534-unit cliff hidden behind `notexture`/`nodraw`: the shifted owner made Q3map treat the cliff as visible and reject it. The corrected `cell-sentinel` mode reverses the cell controls while retaining the sentinel. No terrain was flattened or deleted.

The unmodified editable source also exceeds original Q3map's 2 MiB manual-visibility prepass (`3,089,432` requested bytes). The mirror reproduced the same stock-source limitation. Its config uses the narrowly allowlisted `-nomanvis` BSP option, which preserves all geometry and disables only that obsolete prepass; the ordinary full fast-VIS stage then completed with 283 clusters and 11,328 visibility bytes.

Four-thread MOHlight access-violated during final lighting. The deterministic one-thread pass completed in 774.05 seconds, so the config pins `lightThreads` to one.

## Scripts and assets

The package contains only the mirrored BSP and two thin wrappers. They execute retail `obj_team4.scr` and `obj_team4_precache.scr`; no retail script, texture, model, or sound payload is redistributed. The wrapper explicitly caches the retail bot bazooka explosion effect.

## Rebuild

From the repository root, with retail AA data and MOHTools in the adjacent default locations:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team4_mirror
```

Local compiler staging and logs remain below the ignored `.build` directory.

## Validation

- Q3map: 9.048 seconds with `-nomanvis`; 24 stock-source warnings, primarily absent optional `corona_orange.map` helpers plus the source's existing `textures/notexture` reference; zero leak or degenerate diagnostics.
- VIS: 0.224 seconds; 283 clusters, 463 portals, and 11,328 visibility bytes.
- MOHlight: 774.05 seconds, one thread; five dense entity-light leaves clamped to the retail limit of 60, zero hash warnings, and 60 lightmap pages.
- BSP: version 19, 8,167 surfaces, 8,329,732 bytes.
- Intended Objective mode, isolated OpenMoHAA 0.82.1-beta root: exactly Pak0-Pak6 plus this PK3; BSP parsed in 0.094 seconds, Recast completed in 6.202 seconds, and eight bots entered.
- FFA topology exercise: BSP parsed in 0.111 seconds, Recast completed in 6.327 seconds, eight bots entered, and seven classified combat events occurred in 35 seconds.
- Candidate-specific runtime diagnostics were zero in both reports.

Objective mode logged ten legacy bridge/null-listener script errors. A separate isolated retail `obj/obj_team4` run using only Pak0-Pak6 logged the same ten errors, eight bots, and matching context. This is inherited retail/OpenMoHAA behavior, not a mirror-only regression. The FFA run is only a bot movement/combat proof; Objective mode remains the intended gameplay.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Editable MAP | 4,076,951 | `55522114f6a77f9578fa1b26c203e212214b07c7275595d58b0d5c61aa1e3e30` |
| BSP | 8,329,732 | `467bf131e0c4d90787ea51e7b04f59b7f3417b2a52dc9455979681f9753b2989` |
| PK3 | 1,651,141 | `0e658e19868cb7eec00d885f5010d1b778980472e4562886f6bbb347a81900b6` |

The PK3 has exactly three entries and reproduced byte-identically twice.

## Known debt

- A human visual, door-swing, bridge-bomb, and full objective-completion sweep remains the final acceptance gate; automated checks prove structure, loading, navigation, and combat, not the human interaction sequence.
- This reflects the supplied AA editable source, not the shipped BSP. Any pre-existing source-versus-retail-BSP discrepancy remains possible.
- The 24 inherited editor-helper/missing-image warnings and five dense-light clamps remain documented rather than hidden.
- The ten intended-mode script errors remain because the untouched retail baseline reproduces them exactly.