# Codex Inferno revision 1

> **Rejected fidelity baseline.** The user's first in-game screenshots showed
> that this revision is a generic rectangular Inferno-like arena, not a
> recognizable clone of Inferno. It remains only as failure evidence. Do not
> regenerate, package, or use it as the starting point for later revisions.
> Revision 2 replaces it under the same map name.

## Identity

- Map: `codex_inferno`
- Revision: 1
- Date: 2026-07-30
- Goal: build a complete Inferno-like DM map from scratch after dense Source
  conversions proved visually incomplete
- User evidence: Dust II was the successful quality reference; Cache and Nuke
  showed that direct geometry conversion can preserve measurements while
  losing too much architecture and art
- Compatibility target: Allied Assault BSP 19 and OpenMoHAA

## Input measurements

| Measurement | Reference value |
| --- | ---: |
| World solids | 5,510 |
| Total solids | 7,921 |
| Displacement sides | 2,223 |
| Entities | 9,934 |
| Static props | 6,974 |
| Dedicated DM spawns | 67 |
| T/CT spawns | 20 / 20 |
| Point/spot lights | 75 |

The VMF informed route roles, scale, and omission risk only. No Source solids,
props, displacements, art, or game files entered the generated map.

## Planned and completed changes

| Cause-level decision | Result | Risk |
| --- | --- | --- |
| Author a compact route graph instead of converting 7,921 solids | 20 named connected areas | Interpretive rather than exact |
| Define streets as an occupancy grid and solidify the complement | 21 complete building masses, no prop-dependent holes | Blocky massing |
| Build facade/roof/window systems directly | 71 windows, 20 flat roofs, 2 gables | Human visual review pending |
| Bundle an original Mediterranean palette | 16 tile-validated TGAs | Art direction still needs in-engine review |
| Use simple static collision and many distributed spawns | 16 Axis, 16 Allied, 24 neutral | Spawn fairness needs longer human play |

## Conversion result

- Generated world brushes: 464
- Imported Source solids/props/displacements: 0 / 0 / 0
- Spawn entities: 16 Axis, 16 Allied, 24 neutral, one start, one intermission
- Point lights: 8
- Custom materials: 16
- Warnings: ordinary Quake `func_detail` brush entities were stripped by the
  MOHAA compiler; all authored brushes were therefore emitted in `worldspawn`

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | Passed | short | 2,052 input faces, 2,050 emitted; 2 removed |
| Fast VIS | Passed | 1.0 s | 1,127 clusters, 4,086 portals, 3,725 faces |
| Full MOHlight | Passed | 3.0 s | ambient `8 9 11`; no static models |

Seven interior light origins were reported outside a compiler leaf during BSP
construction. The BSP entity lump retains all eight lights and full lighting
completed. The diagnostic remains explicit visual-review debt.

## Runtime and bot validation

- Exact isolated PK3 tested: yes, 19 entries
- OpenMoHAA: 0.82.1-beta+5.a72bc15
- Bot configuration: DM, 16 clients, 8 max bots, 8 requested bots
- BSP parse: 0.008 s
- Recast navigation generation: 0.173 s
- Spawn/respawn: all eight bots entered
- Combat: 15 bot deaths in the final short sample
- Precache suggestions after fix: 0
- Fatal map-loading errors: 0

The stock-only runtime lacks optional `global/bot_run.scr`; native Recast bots
still moved and fought. No map-local bot script is fabricated to mask this
environment-level message.

## Visual regression matrix

| View | Result | Evidence |
| --- | --- | --- |
| Texture sources | Passed | Four generated source images inspected; palette coherent |
| Texture contact sheet | Not claimed | Automated image viewer blocked by Windows ACL sandbox |
| Spawn route | Pending | Human in-game screenshots needed |
| High overview | Pending | Human in-game screenshots needed |
| Long exterior | Pending | Human in-game screenshots needed |
| Deep interior | Pending | Human in-game screenshots needed |
| Transition/map edge | Pending | Human in-game screenshots needed |

## Outcome

- Fixed by design: Source-prop-dependent holes, missing facade families, and
  dense conversion/compiler budget risk
- Proven: generation, static policy, BSP/VIS/full light, exact package load,
  Recast generation, bot spawning, movement, and combat
- Remaining: first human visual pass, spawn fairness, static-door expectation,
  and any screenshot-driven revision-2 polish

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP | 271,270 | `40A7B86994757E80D127EFEAECA1FA044E0F742DFFF3DDC2A19895625F9A53B6` |
| BSP | 1,933,728 | `F2DECC307875AE9725D991DEE6DD969A818F0F80B8CD99F49C711B788ECBA223` |
| PK3 | 4,670,179 | `30FBE96874CC8BB2ECA4C80B047CE67E2FA3E67EE42C5153D99222ACDC82B8A2` |

## Knowledge promotion

- Map README: generation, compile, runtime, known debt, and hashes recorded
- Research log: from-scratch occupancy-complement case study added
- Playbook: complete-mass construction and `func_detail` compiler behavior
  promoted as reusable rules
- Asset catalog: unchanged; all custom art is project-owned and map-local

## Release checklist

- [x] Source/generator is reproducible.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded.
- [x] Required spawn classes/scripts are present.
- [x] Bots spawned, moved, and fought.
- [ ] Regression views were inspected.
- [x] Known debt is documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.
