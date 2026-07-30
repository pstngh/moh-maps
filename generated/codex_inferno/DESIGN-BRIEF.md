# Codex Inferno design brief

Status: authored revision 1 plan

Date: 2026-07-30

## Target

| Decision | Answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM and TDM |
| Player/bot count | 2-8 players/bots |
| Layout source | Original authored layout inspired by classic Inferno circulation |
| Fidelity target | Recognizable route graph and landmarks, not a brush conversion |
| Asset policy | Original bundled diffuse art plus stock AA sky/utility shaders |
| Lighting | Clear Mediterranean afternoon; warm direct sun, cool fill, low ambient |
| Performance budget | Under 1,200 authored brushes, no patches, under 32 point lights |
| Explicit omissions | Valve geometry/art/models, graffiti, signs, objective logic, dense clutter |

## Authored circulation graph

```text
                        +------- B site -------+
                        |          |           |
T spawn -- Banana ------+       Ruins/CT ------+
   |                               |           |
   +-- Lower mid -- Mid -- Top mid/Arch -------+
          |            |            |
          +-- Alt mid --+-- Short -- A site
                 |
                 +-- Apartments/Balcony --+
```

Every primary combat space has at least two exits. The long Banana sightline
is broken twice with authored bends and cover. A site can be approached from
Short, Library/CT, or Apartments. B site can be approached from Banana or CT.

## Construction strategy

The map is not generated from Source solids.

- A 128-unit occupancy grid describes only authored playable streets.
- The complement is greedily merged into complete solid building masses.
- Building heights, facade palettes, roofs, windows, and trim are generated
  deterministically.
- Apartments and Library are intentionally enclosed authored corridors.
- Site cover, arches, stairs, the B fountain, coffins, and the bell tower are
  manually placed landmarks.
- A sealed stock-AA sky shell surrounds the full layout.

This approach makes missing Source models incapable of creating holes:
non-playable space is a complete solid building or the sealed sky boundary.

## Revision-1 visual priorities

1. Readable route silhouettes and complete enclosure.
2. Recognizable A/B site proportions and approach directions.
3. Mediterranean plaster, brick, cobble, wood, and terracotta palette.
4. Strong warm-sun/cool-shadow separation.
5. Simple static collision for OpenMoHAA bots.
6. Decoration only after the route shell remains visually sound.
