# Codex Inferno design brief

Status: revision 5 technically validated measured structural-prop fill
candidate; human visual review pending

Date: 2026-07-30

## Target

| Decision | Answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM and TDM |
| Player/bot count | 2-8 players/bots |
| Layout source | Supplied CS:GO Inferno VMF; BSP/radar remain private comparison inputs |
| Fidelity target | Recognizable original routes, scale, elevations, openings, architecture, sites, and major landmarks |
| Construction policy | Preserve revision-4 direct brush architecture exactly; append only measured high-impact prop substitutes |
| Asset policy | Original bundled diffuse art plus stock AA sky/utility shaders; no Valve asset bytes |
| Collision policy | Approximate facade/roof/detail pieces non-solid; collision only for measured cover and simple landmarks |
| Lighting | Clear Mediterranean afternoon; warm direct sun, cool fill, low ambient |
| Engine budget | Preserve recognized architecture and evidence-backed fill first; optimize only after new visual review |
| Explicit omissions | Graffiti, warning signs, objective logic, Valve textures/models/sounds/radar, foliage, wires, vehicles, and cosmetic clutter |

## Meaning of measured fill

Revision 5 does not reconstruct commercial model meshes. A reproducible private
audit parses each referenced IDST version 49 header and commits only local hull
bounds, reference counts, header versions, resolution-source labels, and input
fingerprints. The generator applies original entity origins, angles, and scales
to conservative boxes, oriented prisms, cylinders, rings, and frame assemblies
made from redistributable project textures.

The first 5,696 world brush blocks remain identical to revision 4. This makes
the prop layer independently removable or refinable and prevents a set-dressing
pass from silently changing the first recognized route/architecture baseline.

## Inclusion policy

| Source feature | Revision 5 policy |
| --- | --- |
| Playable world/detail/brush/breakable solids | Preserve all 5,533 direct conversions |
| Revision-4 shell/clips/support geometry | Preserve byte-for-byte |
| Verified large/player clips | Preserve where needed for route containment |
| Helper-only clip/hint/skip/areaportal brushes | Exclude and count |
| Distant 3D skybox cluster | Exclude and count |
| Displacements | Preserve supporting planar faces; defer height-field reconstruction |
| Windows/shutters/doors/frames/arches | Measured non-solid visual substitutes |
| Roof/pillar/chimney/support families | Measured non-solid visual substitutes |
| Barrels/crates/hay/coffins | Measured, grounded gameplay-cover collision |
| B fountain and CT well | Simple measured landmark assemblies with bounded collision |
| Irregular/foliage/wire/vehicle/cosmetic props | Omit and count |
| Team/DM spawns | Preserve all 20/20/67 |
| Playable Source lights | Preserve 55 clustered AA lights from 75 candidates |
| Verified rotating door | Preserve one model-bounded 90-degree `func_rotatingdoor` |

The playable filter remains X `-2400..3200`, Y `-1350..4200`, Z
`-320..960`. The structural shell remains `(-2464,-1408,-384)` to
`(3264,4256,1152)`.

## Acceptance gates

Technical acceptance requires deterministic generation, complete model-bounds
resolution, per-instance substitution auditing, MAP syntax and transform
validation, compile-stage map/texture hash parity, Q3map/VIS/full MOHlight,
Q3map `-info`, exact-PK3 OpenMoHAA loading, Recast generation, all requested
bots, observed combat, and zero fatal runtime map errors.

Visual acceptance is separate. T, Mid, Apartments, A, CT, Banana, B, and the
whole-map overview must show that the restored layer fills facades and sites
without floating pieces, false occlusion, ghost doors, route blockers, or badly
scaled landmarks. Technical success does not establish that result.

Revision 5 passes the complete technical gate, including corrected stage parity,
BSP/VIS/full light, exact-PK3 Recast generation, eight-bot admission, observed
combat, and zero fatal map errors. The 16.55 MB BSP exceeds the old nominal
10.00 MB display but loads successfully. Human screenshots remain mandatory
before revision 5 becomes a visually accepted baseline.