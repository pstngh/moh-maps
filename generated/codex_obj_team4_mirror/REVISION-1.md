# The Bridge Mirror revision 1

## Identity

- Map: `codex_obj_team4_mirror`
- Revision: 1
- Date: 2026-08-08
- Commit before work: `26128dfd778dce89cf02e85d5224c6b551d78b86`
- Goal: create a separate complete inverse of AA `obj_team4`
- User evidence: direct request
- Compatibility target: retail Allied Assault data and OpenMoHAA

## Baseline and method

There was no previous package. The authoritative editable input is `aa/obj_team4.map`, 4,153,220 bytes with SHA-256 `71880e3fd218ab5d8f6af8a045d02000b572b0487e789f98e99a1de3409586cf`. The transform reflects world X about zero.

Brush point winding, patch control-row order, terrain origin/vertices/material ownership/triangle pairs, entity origins, yaw, vector angles, and sun direction require determinant-aware handling. Names and link keys remain unchanged because reflection changes coordinates, not the objective graph.

## Conversion result

| Measurement | Value |
| --- | ---: |
| Brush faces | 23,671 |
| Patches | 174 |
| Terrain blocks / samples / controls | 5 / 29,229 / 543 |
| Reflected origins | 515 |
| Reflected yaw / angle vectors / sun vectors | 247 / 1 / 1 |
| Neutral / Allied / Axis starts | 1 / 19 / 17 |
| Rotating doors / windows | 13 / 21 |
| Lights | 176 |

Validation preserves every source entity class and non-transform key/value, proves the output equals the canonical configured transform, and proves the reflection is a stable involution. Thin map-owned wrappers execute the retail map and precache scripts without copying their content.

## Terrain-control correction

The initial full-row material-control reversal moved each MOH terrain cell owner by one position because the last record in a control row is a boundary sentinel. This made an intentional stock 534-unit `nodraw` cliff visible to Q3map and produced `maximum height variation 534 > 510` at the reflected location.

The reusable generator now has an explicit `terrainControlMode`. New mirrors default to `cell-sentinel`: reverse the cell-owning controls and retain the final sentinel. The existing published `mohdm6` and `obj_team2` configs explicitly pin their historical `legacy-full-row` mode so their current packages remain reproducible until they receive a deliberate rebuild/retest revision. The validator now rejects any MAP that differs from its configured canonical transform.

## Compile result

The editable stock source itself requests 3,089,432 bytes during Q3map's manual-vis prepass, above the original 2,097,152-byte limit. The reflected source requests 3,108,152 bytes. The map-specific, allowlisted `-nomanvis` option disables that prepass without deleting geometry; ordinary VIS subsequently produced a compact valid set.

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | passed | 9.048 s | `-nomanvis`; 24 inherited helper/image warnings; zero leaks/degenerates |
| Q3map VIS | passed | 0.224 s | 283 clusters / 463 portals / 11,328 bytes |
| MOHlight | passed | 774.05 s | one thread; 60 pages; five retail-limit clamps; zero hash warnings |

Four-thread MOHlight access-violated with Windows exit `-1073741819`. The one-thread pass completed the exact BSP deterministically. The resulting version-19 BSP is 8,329,732 bytes and contains 8,167 surfaces, 13 rotating doors, 21 windows, and all multiplayer spawn classes.

## Runtime and bot validation

Both candidate tests used an isolated root with exactly retail Pak0-Pak6 plus the final three-entry candidate PK3.

| Mode | BSP / Recast | Bots | Combat | Candidate diagnostics |
| --- | --- | ---: | ---: | ---: |
| Objective (`g_gametype 4`) | 0.094 / 6.202 s | 8 | not required during setup sample | 0 |
| FFA topology exercise (`g_gametype 1`) | 0.111 / 6.327 s | 8 | 7 in 35 s | 0 |

Objective mode recorded ten bridge/null-listener `Script Error` lines. A separate Pak0-Pak6-only retail `obj/obj_team4` baseline parsed in 0.112 seconds, generated Recast in 3.728 seconds, admitted eight bots, and recorded exactly the same ten errors and context. The mirror neither introduces nor conceals this stock behavior.

The FFA run establishes that Recast bots traverse and fight on the reflected geometry. It is not an Objective-rules acceptance substitute. Door presence is proven structurally; door swing, bridge destruction, objective completion, and human feel remain playtest gates.

## Visual regression matrix

| View | Result | Evidence |
| --- | --- | --- |
| Allied / Axis spawn routes | pending human verdict | 36 team starts and navigation pass; no rendered claim |
| Bridge top and under-bridge objectives | pending interaction verdict | original bridge target graph retained; retail baseline shares script diagnostics |
| Town interiors / windows | pending human verdict | 21 compiled windows and stock topology retained |
| Terrain and patch boundaries | structurally passed, visual pending | corrected cell/sentinel control ownership, winding, and involution pass |
| Door transitions | structurally present, interaction pending | 13 compiled `func_rotatingdoor` entities |

## Outcome

- Fixed: terrain material-owner reflection and stock-source manual-vis/tool stability blockers.
- Improved: the reusable builder records allowlisted map-specific Q3map arguments; validation now requires canonical output equality.
- Unchanged: stock materials, lights, scripts, targets, doors, objective metadata, and source warnings.
- Regressed: none identified by structural, compile, or runtime gates.
- Remaining known debt: human appearance, door swing, bridge destruction, and complete objective-interaction playtest; possible editable-source versus retail-BSP discrepancies.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 4,076,951 | `55522114f6a77f9578fa1b26c203e212214b07c7275595d58b0d5c61aa1e3e30` |
| BSP | 8,329,732 | `467bf131e0c4d90787ea51e7b04f59b7f3417b2a52dc9455979681f9753b2989` |
| PK3 | 1,651,141 | `0e658e19868cb7eec00d885f5010d1b778980472e4562886f6bbb347a81900b6` |

The exact three-entry PK3 was generated twice to identical bytes.

## Knowledge promotion

- Map README: transform, terrain ownership, compile workarounds, runtime modes, stock baseline, hashes, and debt.
- Research log: cell/sentinel terrain semantics, manual-vis overflow classification, single-thread MOHlight stability, and retail script baseline.
- Playbook: corrected terrain-control rule, canonical-transform gate, and safe `-nomanvis` exception.
- Asset catalog: unchanged; no retail art is redistributed or newly characterized.

## Release checklist

- [x] Source/generator is reproducible under an explicit terrain-control mode.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded in intended Objective mode.
- [x] Required spawn, door, window, and objective-script classes are present.
- [x] Bots spawned, generated navigation, and fought in the topology exercise.
- [ ] Human visual, door, bridge-bomb, and objective-completion views were inspected.
- [x] Known debt and inherited retail script diagnostics are documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.