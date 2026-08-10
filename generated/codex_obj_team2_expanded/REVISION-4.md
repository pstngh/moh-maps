# `codex_obj_team2_expanded` revision 4

Status: **REJECTED**. Automated visual conclusions are **SUPERSEDED**.

## Superseding human rejection

After the automated revision-4 report, the user supplied a human screenshot and
explicitly rejected the map as crude and visibly unfinished. The screenshot
showed huge beige voids, disconnected-looking terrain/map islands, crude
elevated causeway/slab construction, unfinished visible boundaries, and an
overall result far below acceptable mapping quality.

The 28-view automated suite established only that selected scripted cameras
captured frames without script errors. It did not reproduce or correctly judge
the human failure angle, large-scale spatial continuity, the elevated
construction, newly exposed edges, or whether sealed structure read as a
finished world. Surface counts, `.prt` without `.lin`, Recast generation, bot
combat, and automated capture success could not answer those visual questions.

Therefore all prior revision-4 language implying a complete/finished forest
loop, visually coherent causeway/facade, no visible void, polished boundary,
release readiness, or acceptance is `SUPERSEDED`. The revision remains useful
only as historical technical and negative evidence. It must not be used as a
positive construction template without fresh verification.

## Historical identity and intent

- Map/revision/date: `codex_obj_team2_expanded` / 4 / 2026-08-09
- Starting commit: `17edddb42ee63466cd8b896ba12bd8ea700da4b1`
- Intended goal: remove identified fence components and attempt a substantial
  forest-side route from Allied spawn around the bunker into the rear/east yards
- Entering evidence: revision 3 retained fencing, curb geometry, and an
  incomplete exterior
- Compatibility target: Allied Assault BSP19 and stock AA assets with OpenMoHAA
  bot support

## Historical source and transformation record

- Canonical source: `aa/obj_team2.map`, 5,478,775 bytes, SHA-256
  `04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f`.
- Removed: 22 west fence entities, 37 south/east fence entities, 33 associated
  world brushes, and 24 foliage entities.
- Preserved by the encoded validator: 23 `func_rotatingdoor` entities, 88
  targetnames, 16 Allied starts, 16 Axis starts, retail Objective scripts, and
  their target graph.
- Added: 334 brushes, 152 entities, and 21 neutral deathmatch starts.
- Added retail/custom payload bytes: zero; generated geometry referenced stock
  AA assets.

The generator attempted an open Allied court, west transition, stepped forest
climb, west ridge, 1,024-unit elevated causeway, east ridge/descent, lower lane,
and annex apron. Numeric width, entity counts, and source-preservation checks do
not establish visual coherence; the later human screenshot disproved the
automated interpretation of the result.

## Historical seal investigation

Focused Q3map probes reported successive leak traces at the central foundation,
north stock-floor edge, south enclosure, north underside, central ceiling, and
the west/new ceiling join. The final probe wrote `.prt` and no `.lin` after a
Z=832 sky ceiling and structural joins were added.

This supports only the narrow observation that the compiler produced a sealed
portal graph for the generated source. It does not prove that the visible
sealing geometry, terrain continuity, or elevated construction was visually
complete. The later human evidence showed that it was not.

## Historical compile, runtime, and capture record

| Gate | Historical result | Current interpretation |
| --- | --- | --- |
| Q3map BSP | 119.793 s; BSP19; 19,624 surfaces; `.prt` present; `.lin` absent | Compile observation only |
| VIS | 0.398 s; 131,080 visibility bytes | Compile observation only |
| MOHlight | 320.630 s; 67 pages; no recorded clamps/hash warnings | Lighting-stage observation, not visual approval |
| Objective runtime | Recast 2.150 s; eight bots; five combat events/60 s | Runtime/bot observation only |
| FFA topology runtime | Recast 2.134 s; eight bots; four combat events/60 s | Runtime/bot observation only |
| Automated visual suite | 28 requested frames and no script errors | Insufficient and superseded as a quality verdict |

The earlier report stated that selected frames showed no fence/curb remnant,
black void, open sky seam, or floating route prop. Those statements were bounded
to selected frames and were incorrectly generalized. The later human screenshot
showed beige voids, disconnected-looking islands, crude slabs/causeway, and
unfinished edges; any broader no-void or finished claim is `REJECTED`.

## Historical artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,637,967 | `871719b096129a5db24e94b77f5c3ba980aacdd4a796fd2fa9d48f415f2a8070` |
| BSP | 13,873,788 | `140ee2bf482ca4f83f1ecea11aee9d79d377cdf2974111a190fe1a9c1b1792eb` |
| PK3 | 2,543,033 | `4b85f8ede35726bbb6ea5f6f71480e2b8a2b10e47930f490c7082156e2833918` |
| Automated contact sheet | 13,031,828 | `fe8d438940bdd655dbbed927a2d336b9975490cc498972ce322aed07a530df62` |

## Lessons retained with corrected scope

- `OBSERVED`: A visible perimeter may include model entities, wire, posts,
  curbs, rails, collision/playerclip, and foliage owners.
- `OBSERVED`: `terrainDef` visible extent and sealed-hull extent can differ.
- `PROVEN`: `.prt` without `.lin` proves a compiler enclosure result, not visual
  completion.
- `PROVEN`: Automated cameras must include the exact human failure domain, and
  capture success cannot replace human visual judgment.
- `REJECTED`: Revision 4 as a finished, visually coherent, release-ready, or
  accepted map.

## Disposition checklist

- [x] Historical source, compile, runtime, and artifact evidence retained.
- [x] Later human rejection recorded.
- [x] Contradicted positive visual claims marked `SUPERSEDED`.
- [x] Candidate classified `rejected`, not accepted.
- [ ] No repair is authorized by this bootstrap.
