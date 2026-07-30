# Codex Inferno design brief

Status: revision 2 measured clone, awaiting first human visual pass

Date: 2026-07-30

## Target

| Decision | Answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM and TDM |
| Player/bot count | 2-8 players/bots |
| Layout source | Supplied CS:GO Inferno VMF used as a measurement/reference drawing |
| Fidelity target | Same recognizable topology, scale, elevations, sites, openings, and major landmarks |
| Construction policy | New MOHAA-native geometry; no direct Source brush or asset import |
| Asset policy | Original bundled diffuse art plus stock AA sky/utility shaders |
| Lighting | Clear Mediterranean afternoon; warm direct sun, cool fill, low ambient |
| Engine budget | At or below Q3map's original 10 MB BSP budget |
| Explicit omissions | Graffiti, warning signs, objective logic, dense foliage/clutter, Valve art/models |

## Interpretation of “from scratch”

From scratch means manual reauthoring of the requested map. It does not mean an
original design inspired by that map. Revision 1 violated this requirement and
is rejected.

The committed collision-aware blueprint is the topology contract. Its 6,997
walk cells and 13,420 route edges define where movement exists and where a wall
must remain. Art, facade mass, cover, and lighting may improve around that
contract. Route changes require measured or screenshot evidence.

## Actual orientation

```text
west                         center/east                       north

T spawn -- Alt/Second Mid -- Mid -- Arch/Library -- CT -------+
   |                            \                    |          |
   +-- Apartments --------------+-- A site          +-- B site
                                                  Banana   Fountain
```

The schematic is descriptive only; `layout-plan.svg` and
`inferno-walk-grid-reference.svg` are the measured plan views.

## Construction strategy

1. Reconstruct convex source solids from plane intersections for measurement.
2. Sample floor candidates on a 32-unit grid.
3. Reject cells without player headroom.
4. Test neighbor transitions against collision planes.
5. Flood-fill from all 107 supplied spawns.
6. Greedily merge connected floor cells by height/material role.
7. Author a wall only when the measured route graph forbids that edge.
8. Add complete facade masses, roofs, interiors, and landmark substitutes.
9. Keep the sky shell structural and mark internal worldspawn brushes as MOHAA
   detail to stay within portal limits.
10. Compile, light, package, validate, then use human screenshots for revision.
