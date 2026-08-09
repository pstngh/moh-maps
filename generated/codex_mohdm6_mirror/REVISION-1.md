# Stalingrad Mirror revision 1

## Identity

- Map: `codex_mohdm6_mirror`
- Revision: 1
- Date: 2026-08-08
- Commit before work: `628a59e5d9707b73e504c861400f92e8b952481d`
- Goal: create a separate complete inverse of AA `mohdm6`
- User evidence: direct request
- Compatibility target: retail Allied Assault data and OpenMoHAA

## Baseline and method

There was no previous package. The authoritative editable input is `aa/mohdm6.map`, 1,726,335 bytes with SHA-256 `07c786c8f8f0f5f176b253bda2f0d37159f1b56784f80b07e2151011c2cdc0c7`. The transform is reflection across world `x = 0`.

A negative-determinant transform requires more than negating X coordinates. Brush face point order is reversed to preserve outward planes. Patch control rows are reversed after reflecting X. Each legacy terrain origin becomes `-(x0 + (width - 1) * 64)`, sample/control rows are reversed, and the two triangle-flag groups per sample are exchanged. Entity yaw becomes `180 - yaw`; angle vectors reflect yaw and roll; special `-1`/`-2` angles remain special. `sundirection` receives the matching reflection.

## Conversion result

| Measurement | Value |
| --- | ---: |
| Brush faces | 13,938 |
| Patches | 68 |
| Terrain blocks / samples / controls | 2 / 442 / 15 |
| Reflected origins | 491 |
| Reflected yaw / angle vectors / sun vectors | 115 / 2 / 1 |
| Neutral / Allied / Axis starts | 25 / 25 / 25 |
| Lights | 293 |

Validation preserves all entity-class counts and proves a stable reflection involution. Retail behavior is retained with thin wrappers that execute the original retail map and precache scripts. No retail script contents were copied.

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | passed | 5.493 s | 63 stock-source warnings; 36 light leak diagnostics; zero degenerates |
| Q3map VIS | passed | 0.307 s | 72,392 visibility bytes |
| MOHlight | passed | 32.851 s | 25 pages; three 60-light clamps; zero hash warnings |

The version-19 BSP is 4,495,204 bytes, contains 5,463 surfaces, and retains all 75 multiplayer spawn entities. Missing `curtain`, `curtain_dirty`, and `corona_orange` editor-side `.map` helpers are compile-time stock-source warnings; their retail runtime assets remain available.

## Runtime and bot validation

The exact final PK3 ran in an isolated root containing retail Pak0-Pak6 plus exactly one candidate package. OpenMoHAA 0.82.1-beta parsed the BSP in 0.044 seconds, generated Recast in 0.500 seconds, admitted eight bots, and logged two classified combat events during the final ten-second sample. Candidate-specific diagnostics and script errors were zero. Eight missing `global/bot_run.scr` messages are classified separately as an existing retail-only environment condition; native Recast bots still moved and fought.

Initial sustained runs requested explicit caches for `dm_50_healthbox.tik` and `bazookaexplosion_dm.tik`. The final thin precache wrapper adds those retail paths, and the clean repeat emitted no candidate-specific missing-cache request.

## Visual regression matrix

| View | Result | Evidence |
| --- | --- | --- |
| Spawn route | pending human verdict | client loaded and entered the map; desktop capture path returned loading/black frames |
| Overview / map edge | pending human verdict | structural reflection and BSP counts pass; no rendered claim |
| Interior / exterior transition | pending human verdict | stock topology retained; no rendered claim |
| Terrain / patch boundaries | structurally passed, visual pending | deterministic row/winding validation; human renderer review still required |

## Outcome

- Fixed: not applicable; this is a new mirrored derivative.
- Improved: reusable, validated whole-map reflection tooling now handles brushes, patches, terrain, entity orientations, and sun direction.
- Unchanged: source textures, gameplay metadata, stock scripts, target graph, spawns, lighting intent, and stock-source warnings.
- Regressed: none identified by structural, compile, or runtime gates.
- Remaining known debt: human visual sweep and any discrepancies already present in the supplied editable source versus the retail BSP.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 1,700,554 | `d10bf1ae1caf744504146be6bd6cda81e40e92dc49639704933b988ac969908c` |
| BSP | 4,495,204 | `57ff1b395012c1a792d3046296441907daeff28baa79f19a31c96bfa728f0a22` |
| PK3 | 874,060 | `43278a35d28cc64c32827479a4c30a66440f38f5c7350f94f6049b04ae102585` |

The exact three-entry PK3 was generated twice to identical bytes.

## Knowledge promotion

- Map README: identity, transform, build, runtime, warnings, hashes, and debt.
- Research log: canonical MOH negative-determinant reflection rules and runtime evidence.
- Playbook: whole-map reflection gate.
- Asset catalog: unchanged; no new asset behavior was characterized.

## Release checklist

- [x] Source/generator is reproducible.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded.
- [x] Required spawn classes/scripts are present.
- [x] Bots spawned, navigated, and fought.
- [ ] Human regression views were inspected.
- [x] Known debt is documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.
