# Codex Inferno design brief

Status: revision 3 playable recognition candidate; human visual review pending

Date: 2026-07-30

## Target

| Decision | Answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM and TDM |
| Player/bot count | 2-8 players/bots |
| Layout source | Supplied CS:GO Inferno VMF/BSP/radar used as private measurement and comparison inputs |
| Fidelity target | Same recognizable topology, scale, elevations, sites, openings, and major landmarks |
| Construction policy | New MOHAA-native geometry; no direct Source brush or asset import |
| Asset policy | Original bundled diffuse art plus stock AA sky/utility shaders |
| Lighting | Clear Mediterranean afternoon; warm direct sun, cool fill, low ambient |
| Engine budget | At or below Q3map's original 10 MB BSP budget |
| Explicit omissions | Graffiti, warning signs, objective logic, Valve art/models, dense foliage/clutter |

## Interpretation of "from scratch"

From scratch means manual reauthoring of the requested map. It does not mean an
original design inspired by that map. Revision 1 violated this requirement and
is rejected.

The committed collision-aware blueprint is a measurement and connectivity
oracle, not an architectural drawing. Its 6,997 walk cells and 13,420 route
edges prove where player movement and openings must survive. They must never
again be extruded one-for-one into facades. Architecture is authored at
callout scale, then checked against the graph for route regressions.

## Actual orientation

```text
west                         center/east                       north

T spawn -- Alt/Second Mid -- Mid -- Arch/Library -- CT -------+
   |                            \                    |          |
   +-- Apartments --------------+-- A site          +-- B site
                                                  Banana   Fountain
```

The schematic is descriptive only. `layout-plan.svg`,
`inferno-walk-grid-reference.svg`, and the private official radar comparison
are the measured plan views.

## Revision 3 construction strategy

1. Reconstruct convex source solids from plane intersections for measurement.
2. Sample floor candidates on a 32-unit grid and reject cells without player
   headroom or collision-safe transitions.
3. Flood-fill from all 107 supplied spawns and preserve the resulting graph as
   a validator only.
4. Merge connected walk cells into intentional floor plates.
5. Dilate the route footprint by ten cells, flood-fill exterior air, and fill
   bounded non-route pockets so the village becomes complete solid mass.
6. Divide that mass into T, Alt Mid, Mid, Apartments, A, CT/Library, Banana,
   and B zones with intentional material/height families.
7. Greedily merge mass columns into complete buildings and cap them with
   coherent roofs, including selected gables.
8. Retain measured indoor separation walls, but render no outdoor graph-edge
   wall strips.
9. Add measured hero substitutes only where origin and dimensions are proven.
10. Keep the sky shell structural and mark internal worldspawn geometry as
    MOHAA detail to stay within portal limits.
11. Compile, light, package, validate, bot-test, compare against the radar, and
    require user screenshots before promotion.

## Acceptance gates

Technical acceptance requires deterministic generation, static validation,
ordinary Q3map/VIS/full MOHlight, the original 10 MB BSP budget, an exact-PK3
OpenMoHAA load, Recast generation, and observed bot combat.

Visual acceptance is separate. T, Mid, Apartments, A, CT, Banana, and B must
read correctly at ground level, and the whole-map overview must resemble the
reference. Revision 3 has passed the technical gate only.
