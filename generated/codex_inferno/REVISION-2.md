# Codex Inferno revision 2

Date: 2026-07-30

Status: **visually rejected by the user** after screenshot `shot0021.tga`;
compile/runtime evidence remains valid but this is not a recognizable Inferno
clone and must not be treated as a release baseline

## Human review verdict

The overhead screenshot shows a dense maze of narrow roof and wall strips,
hollow gaps, fragmented elevations, and no readable continuous Inferno
streets/building blocks. The user still could not recognize the map.

The root cause is architectural generation, not lighting or texture polish:

- the 32-unit walk graph was rendered too literally;
- almost every blocked cell edge became a wall run;
- exterior masses extend only 112 units instead of becoming complete semantic
  buildings;
- 294 short roof masses cap those boundary strips rather than forming coherent
  rooftops;
- small height/material changes fragment facades and destroy the visual rhythm
  of T spawn, Mid, Apartments, A, CT, Banana, and B.

The collision-aware graph remains useful measurement evidence, but it is not a
renderable architectural blueprint. Passing compile, navigation, and bot QA
did not establish visual fidelity.

## Why revision 2 exists

Revision 1 misunderstood “build Inferno from scratch.” It invented a compact
Inferno-like route graph. The user's screenshots showed that it was not
recognizable as Inferno, so revision 1 is rejected as a fidelity baseline.

For this project, **clone from scratch** now has a precise meaning:

- manually author new MOHAA-native geometry;
- reproduce the supplied map's actual topology, scale, elevations, sites,
  openings, and landmark positions;
- use the VMF as a measurement/reference drawing, not as a direct brush
  conversion;
- never replace the requested layout with an analogous or “inspired by”
  design unless the user explicitly asks for one.

## Measured reconstruction

The audit tool reconstructed all 7,921 convex solids in the supplied
`de_inferno_d.vmf` with zero failures. It then sampled floor candidates on a
32-unit grid, rejected cells without player headroom, checked transitions
against reconstructed collision planes, and flood-filled from every supplied
spawn.

The durable blueprint contains:

| Evidence | Value |
| --- | ---: |
| Candidate XY cells | 12,485 |
| Candidate floor nodes | 13,372 |
| Nodes rejected for headroom | 5,397 |
| Collision buckets | 2,602 |
| Spawn seeds | 107 |
| Connected playable cells | 6,997 |
| Verified route edges | 13,420 |
| Unmatched spawns | 0 |
| T / CT / DM spawns | 20 / 20 / 67 |

This recovered the actual orientation and footprint: T spawn west, A
southeast, CT east, Banana/B north, and the real Mid/Alt Mid/Apartments loops.

## Authored output

Revision 2 greedily merges the measured walk trace into 479 floor rectangles,
then authors walls only where the measured edge graph says movement is
blocked. It adds 77 wood-route ceiling rectangles and fills exterior facade
boundaries with 112-unit-deep building masses so omitted Source props cannot
become black holes.

Recognizable measured landmark replacements include:

- B fountain at `(352, 2768)`;
- B coffins and barrel stacks at their measured clusters;
- A boxes plus the pit hay/cart silhouette;
- ten major open passage arches;
- four measured facade balconies;
- the visible bell-tower silhouette;
- 123 facade windows and 294 roof masses.

Final authored geometry:

| Item | Count |
| --- | ---: |
| Floor rectangles | 479 |
| Raw blocked wall edges | 2,843 |
| Merged wall runs | 1,058 |
| Ceiling rectangles | 77 |
| Total worldspawn brushes | 2,683 |
| Original bundled texture roles | 16 |
| Interior point lights | 14 |

No Source brush, displacement, texture, model, sound, or embedded asset is in
the MAP or PK3.

## Compiler and engine evidence

- Ordinary Q3map completed in 98 seconds and emitted 15,717 faces from 16,111
  inputs.
- Internal geometry uses MOHAA's proven `+surfaceparm detail` form; only the
  six-brush sky shell is structural.
- Fast VIS completed with 36 clusters, 60 portals, and 296 visibility bytes.
- Full MOHlight completed with ambient `8 9 12`.
- Q3map `-info` reports 2,683 brushes, 15,717 draw surfaces, 64 lightmaps, and
  9.69 MB used out of the original 10.00 MB BSP budget.
- The exact PK3 loaded in a fresh OpenMoHAA home backed only by retail
  Pak0-Pak6.
- OpenMoHAA parsed the BSP in 0.054 seconds and generated Recast navigation in
  1.916 seconds.
- Eight bots entered and produced 8 combat deaths in the 38-second sample.
- The runtime logged zero fatal errors.

The stock-only test environment still lacks optional `global/bot_run.scr`.
That warning is not map content; native bots nevertheless navigate and fight.

## Current artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 1,825,136 | `117DDF45E264A87DEC64D094E0720B08016D265EC8A33EA4E3689B1489E85414` |
| BSP | 10,982,668 | `FA8E27CC0D00D5D1EA17A1E64E4795A04A68B4EDA26F8E0858346DC126A0C1F9` |
| PK3 | 6,007,217 | `D5F31886CB7390F9DAB7D7FE418079CB91A2FF2E5745FE61BEAC36384F8D8777` |

The blueprint SHA-256 is
`D5C30783387415C9C57CDB1608B07F8C04CC5DF4A460A8BD4ED3ADD5F8AFF8B0`.

## Replacement requirement

Revision 3 must not extrude the walk-cell boundary into architecture. It must
hand-reconstruct continuous callout-scale streets and complete building
volumes, using the VMF and walk graph only for measurements and connectivity
checks. It should be reviewed at T spawn, Mid, Apartments, A, CT, Banana, and B
before a full-map package is called recognizable.
