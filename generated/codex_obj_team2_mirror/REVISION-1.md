# V2 Facility Mirror revision 1

## Identity

- Map: `codex_obj_team2_mirror`
- Revision: 1
- Date: 2026-08-08
- Commit before work: `628a59e5d9707b73e504c861400f92e8b952481d`
- Goal: create a separate complete inverse of AA `obj_team2`
- User evidence: direct request
- Compatibility target: retail Allied Assault data and OpenMoHAA

## Baseline and method

There was no previous package. The authoritative editable input is `aa/obj_team2.map`, 5,478,775 bytes with SHA-256 `04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f`. The transform reflects world X about zero.

Brush point winding, patch control-row order, terrain origin/rows/triangle pairs, entity origins, yaw, vector angles, and sun direction all require determinant-aware handling. Names and link keys stay unchanged because reflection changes coordinates, not the objective graph.

## Conversion result

| Measurement | Value |
| --- | ---: |
| Brush faces | 35,217 |
| Patches | 708 |
| Terrain blocks / samples / controls | 7 / 8,479 / 177 |
| Reflected origins | 595 |
| Reflected yaw / angle vectors / sun vectors | 249 / 71 / 1 |
| Neutral / Allied / Axis starts | 14 / 16 / 16 |
| Rotating doors | 23 |
| Spline nodes | 22 |
| Lights | 181 |

Validation preserves every source entity-class count and proves the reflection is a stable involution. Thin map-owned wrappers execute the retail map and precache scripts without copying their content.

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | passed | 127 s | 124 stock-source warnings; one existing missing-image family; zero leaks/degenerates |
| Q3map VIS | passed | < 0.1 s reported | 39,608 visibility bytes |
| MOHlight | passed | 517.7 s | one thread; 59 pages; zero clamps/hash warnings |

Original MOHlight first required `textures/wilderness/wldrrckset1_1.jpg` as a loose build input. The build extracts that exact retail file only into `.build/main`, which is ignored and never packaged. A later four-thread pass reproducibly access-violated; the config therefore pins `lightThreads` to one, which completed.

The resulting version-19 BSP is 12,342,844 bytes and contains 18,333 surfaces, 23 rotating doors, and all multiplayer spawn classes.

## Runtime and bot validation

Both tests used an isolated root with exactly retail Pak0-Pak6 plus the final three-entry candidate PK3.

| Mode | BSP / Recast | Bots | Combat | Candidate diagnostics |
| --- | --- | ---: | ---: | ---: |
| Objective (`g_gametype 4`) | 0.114 / 1.852 s | 8 | not required during setup sample | 0 |
| FFA topology exercise (`g_gametype 1`) | 0.113 / 1.853 s | 8 | 4 in 25 s | 0 |

Objective mode recorded five `Script Error` lines in `global/obj_dm.scr`. A separate Pak0-Pak6-only retail `obj/obj_team2` baseline also admitted eight bots and recorded exactly five script errors with the same control-room/null-listener context. The mirror therefore neither introduces nor conceals this stock behavior.

The FFA run establishes that Recast bots traverse and fight on the reflected geometry. It is not an Objective-rules acceptance substitute. Door presence is proven structurally; door swing, objective completion, and human feel remain playtest gates.

## Visual regression matrix

| View | Result | Evidence |
| --- | --- | --- |
| Allied / Axis spawn routes | pending human verdict | spawn classes and navigation pass; no reliable post-load capture |
| V2 and control-room objective areas | pending interaction verdict | original target graph retained; retail baseline shares script diagnostics |
| Exterior / deep interior | pending human verdict | compiled/lighted stock topology retained; no rendered claim |
| Terrain and repeated patch boundaries | structurally passed, visual pending | row, winding, and involution validators pass |
| Door row / transitions | structurally present, interaction pending | 23 compiled `func_rotatingdoor` entities |

## Outcome

- Fixed: not applicable; this is a new mirrored derivative.
- Improved: reusable terrain/patch/entity reflection tooling and exact stock-baseline classification for Objective script diagnostics.
- Unchanged: stock materials, lights, scripts, targets, doors, objective metadata, and source warnings.
- Regressed: none identified by structural, compile, or runtime gates.
- Remaining known debt: human appearance, door-swing, and complete objective-interaction playtest; possible editable-source versus retail-BSP discrepancies.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,484,624 | `91d14682e39cb79bc1f9d0fc50319b8ceac9b970dd2de4a6e14690ed94b0a183` |
| BSP | 12,342,844 | `d90ec65f3ec876a6b13b6884780cc58820ae3905df4f0182969f054ef096cd39` |
| PK3 | 2,187,167 | `3f94073eae1d6ac9f56827b8357c1e26807df8c012a4b04b2a18e337b31b5c81` |

The exact three-entry PK3 was generated twice to identical bytes.

## Knowledge promotion

- Map README: transform, build workarounds, runtime modes, stock baseline, hashes, and debt.
- Research log: terrain reflection, single-thread MOHlight stability, and baseline classification.
- Playbook: whole-map reflection and stock-runtime comparison gates.
- Asset catalog: unchanged; no retail art is redistributed or newly characterized.

## Release checklist

- [x] Source/generator is reproducible.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded in intended Objective mode.
- [x] Required spawn, door, spline, and script classes are present.
- [x] Bots spawned, generated navigation, and fought in the topology exercise.
- [ ] Human visual, door, and objective-completion views were inspected.
- [x] Known debt and inherited retail script diagnostics are documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.
