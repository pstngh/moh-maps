# Codex Inferno revision 3

Date: 2026-07-30

Status: **technically accepted playable candidate; human visual review
pending**

## Why this revision exists

Revision 1 invented an Inferno-like arena and was rejected because it was not
the requested layout. Revision 2 recovered the real playable graph, but
rendered 1,058 blocked graph-edge runs as shallow walls with 294 fragmented
roof caps. The user's overview showed a hollow maze rather than Inferno.

Revision 3 keeps the measured graph as evidence but discards it as a rendering
grammar. The goal of this pass is recognizable continuous street and village
massing before facade decoration.

## Restored-reference audit

The restored CS:GO BSP, VPK, radar, overview text, and private VMF were audited
without copying commercial bytes into the output. The official overview
transform (`pos_x -2087`, `pos_y 3870`, `scale 4.9`) aligns the authored
semantic plan with the real route footprint and T/A/B/CT positions.

The source audit also resolved all 82 visible material definitions and all 308
unique referenced models. Parsed model headers supplied real scale evidence
for the B fountain, CT well, large arch, and coffins. This corrected the B
fountain from a 104-unit-radius approximation to a measured 156-unit basin
with a 43-unit center and 136-unit authored center height.

## Complete village massing

The revision-3 generator:

1. preserves all 6,997 connected walk cells, 13,420 permitted transitions,
   479 merged floor plates, and 107 matched spawns;
2. dilates the route footprint by ten 32-unit cells;
3. flood-fills exterior air and fills bounded blocked pockets;
4. assigns T, Alt Mid, Mid, Apartments, A, CT/Library, Banana, and B height and
   material families;
5. greedily merges 9,750 mass columns into 455 complete building rectangles;
6. caps all 455 masses and adds 26 intentional gable silhouettes;
7. retains 222 measured indoor separation runs while rendering zero outdoor
   graph-edge wall runs.

Measured hero elements include the B fountain, CT well, B coffins/barrels, A
boxes/hay, ten open passage arches, four balconies, and bell tower. No Source
brush, displacement, texture, model, sound, or embedded asset is shipped.

| Geometry | Count |
| --- | ---: |
| Merged walk-floor rectangles | 479 |
| Filled mass columns | 9,750 |
| Complete building rectangles | 455 |
| Roof masses | 455 |
| Gable roofs | 26 |
| Outdoor grid-wall runs rendered | 0 |
| Indoor separation runs rendered | 222 |
| Ceiling rectangles | 77 |
| Site-surface brushes | 37 |
| Measured arches | 10 |
| Total worldspawn brushes | 1,805 |
| Axis / Allied / neutral spawns | 20 / 20 / 67 |
| Point lights | 14 |

## Compiler evidence

The corrected final source passed the stable revision-3 validator with no
failures. A clean retail Pak0-Pak6 build produced:

- ordinary Q3map: 10,457 faces from 10,824 inputs, 367 removed (3.4%), 44
  seconds;
- fast VIS: 36 portal clusters, 60 portals, 296 visibility bytes, 36 clusters
  visible on average;
- full MOHlight: 73 seconds, ambient `8 9 12`, zero stderr output;
- Q3map `-info`: 1,805 brushes, 10,457 draw surfaces, 65 lightmaps;
- BSP budget: 7.45 MB used out of the original 10.00 MB limit.

The PK3 manifest contains exactly 19 entries: the BSP, two map scripts, and
sixteen original 512x512 TGA textures. It contains no Source paths or assets.

## Exact-package OpenMoHAA evidence

OpenMoHAA 0.82.1 loaded the final PK3 in a fresh home backed only by retail
Pak0-Pak6. It parsed the BSP in 0.035 seconds and generated Recast navigation
in 0.611 seconds. Eight bots entered and produced 11 combat/death events in
the timed sample. The runtime logged zero fatal map errors.

The first launch in this pass repeated a known QA mistake: `bot_enable` or an
unrelated minimum-player cvar is insufficient. The valid harness sets
`g_gametype 1`, `sv_maxbots 8`, and `sv_numbots 8` before loading the map. This
is recorded so later QA does not silently pass with zero bots.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 1,230,507 | `6A683B7D88EEBF6C2440CD1971EB29F4912AA72D5043BAA5ED60E64A38E108B8` |
| BSP | 8,353,932 | `F5B9DD04F06513A0C51BAA764A21D57F8F9FE5D41678273BA1B65026B711CD5F` |
| PK3 | 5,507,308 | `10EB9994BD08354846C8B0A9DD57579F977B79994F23EC7513EE259E9B65C6CB` |

## Honest acceptance state

Technical gates pass. The private official-radar comparison supports the
plan-scale/layout claim. Automated Windows capture was unavailable in this
workspace because the app-control runtime could not initialize through the
workspace ACL, so this pass does not claim an in-engine visual verdict.

Known visual debt includes no generated facade-window panels, simplified
slopes/elevation transitions, blockier-than-source roofs and silhouettes,
omitted Source-only props/displacements, and an intentionally omitted dynamic
door. The next decisive evidence is the user's ground-level and high-overview
screenshot set. Fix architecture first; add windows, shutters, and trim only
after the callouts are recognizable.
