# Codex Inferno design brief

Status: revision 4 direct-VMF playable candidate; human visual review pending

Date: 2026-07-30

## Target

| Decision | Answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM and TDM |
| Player/bot count | 2-8 players/bots |
| Layout source | Supplied CS:GO Inferno VMF; BSP/radar remain private comparison inputs |
| Fidelity target | Recognizable original routes, scale, elevations, openings, architecture, sites, and major landmarks |
| Construction policy | Directly convert playable VMF brush solids after two inferred reauthoring methods failed |
| Asset policy | Original bundled diffuse art plus stock AA sky/utility shaders; no Valve asset bytes |
| Lighting | Clear Mediterranean afternoon; warm direct sun, cool fill, low ambient |
| Engine budget | Preserve recognizable architecture first; optimize the valid 12.34 MB BSP after visual acceptance |
| Explicit omissions | Graffiti, warning signs, objective logic, Valve textures/models/sounds/radar, dense clutter |

## Meaning of direct conversion

Revision 4 reconstructs convex Source brush solids from their planes and emits
equivalent MOHAA map brushes. It preserves the playable world's architectural
brushes plus solids from `func_detail`, `func_brush`, and `func_breakable`.
Imported internal geometry is emitted in `worldspawn` with MOHAA
`+surfaceparm detail`; an explicit structural sky shell controls BSP portals.

Direct geometry conversion does not mean copying Source assets. Source material
names are classified into original project-owned Inferno texture roles. Source
models, textures, radar pixels, sounds, and embedded pak data are not packaged.

## Inclusion policy

| Source feature | Revision 4 policy |
| --- | --- |
| Playable world/detail/brush/breakable solids | Directly reconstruct and emit |
| Verified large/player clips | Preserve where needed for route containment |
| Helper-only clip/hint/skip/areaportal brushes | Exclude and count |
| Distant 3D skybox cluster | Exclude and count |
| Displacements | Preserve their supporting planar faces; defer height-field reconstruction |
| Source props/models | Omit unless a target-engine representation and bounds are verified |
| Team/DM spawns | Translate all 20/20/67 |
| Playable Source lights | Cluster 75 candidates into 55 practical AA lights |
| Verified rotating door | Translate one model-bounded 90-degree `func_rotatingdoor` |

The playable filter is X `-2400..3200`, Y `-1350..4200`, Z `-320..960`.
The structural shell spans `(-2464,-1408,-384)` to `(3264,4256,1152)`.

## Acceptance gates

Technical acceptance requires deterministic generation, static validation,
Q3map/VIS/full MOHlight, an exact-PK3 OpenMoHAA load, Recast generation, all
requested bots, and observed combat. Revision 4 passes these gates.

Visual acceptance is separate. T, Mid, Apartments, A, CT, Banana, and B must
read correctly at ground level, and the whole-map overview must resemble the
source layout. Revision 4 remains a candidate until the user's screenshots
pass that gate.

The 12.34 MB BSP exceeds the original tool's nominal 10 MB display but compiles
and runs. Do not remove measured architecture merely to reduce this number
before visual review. Once recognition passes, optimize by proven feature
class and repeat the same screenshot/runtime gates.
