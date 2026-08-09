# `codex_obj_team2_expanded` revision 4

## Identity

- Map/revision/date: `codex_obj_team2_expanded` / 4 / 2026-08-09
- Starting commit: `17edddb42ee63466cd8b896ba12bd8ea700da4b1`
- Goal: remove every visible and invisible fence component and complete a substantial forest-side route from Allied spawn around the bunker into the expanded rear/east yards
- User evidence: revision 3 still retained fencing, curb geometry, and an incomplete exterior; the requested side passage did not form a complete map area
- Compatibility target: Allied Assault BSP19 and stock AA assets, with OpenMoHAA bot support

## Baseline and defect inventory

Revision 3 had a useful annex but treated the Allied opening as a local gate. The stock perimeter was actually a cooperating system spread across entities and worldspawn: panels, wire, posts, caps, rails, curbs, four invisible playerclips, and route-blocking foliage. Removing only the obvious panel left physical and visual fragments. The original terrain also did not span the apparently open central outside area: western terrain ended near X=-192 and eastern terrain began near X=1088, so a route drawn through that interval was neither floored nor enclosed.

| ID | Area | Revision-3 defect | Revision-4 cause-level repair |
| --- | --- | --- | --- |
| R4-1 | West/south/east perimeter | Fence system and brick/concrete base remained | Removed 59 exact untargeted fence entities and 33 cooperating world brushes, including four playerclips |
| R4-2 | Allied spawn to rear yard | Passage was local/incomplete | Built a continuous graded forest loop with 320-unit minimum combat width and a 1,024-unit central causeway |
| R4-3 | Central exterior | Missing terrain/hull exposed voids and leaks | Added structural foundation, side sky hulls, and a ceiling matched to the stock west ceiling at Z=832 |
| R4-4 | Causeway edge/facade | First sealed build still looked unfinished | Added retaining wall/piers, raised tree planters, oak trees, projecting facade bays, service doors, banding, and lights |
| R4-5 | Regression coverage | Earlier cameras did not cover the full new route | Expanded the matrix to 28 named views and moved all route cameras into proven playable air |

## Input measurements and preservation

- Canonical source: `aa/obj_team2.map`, 5,478,775 bytes, SHA-256 `04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f`.
- Exact removals: 22 west fence entities, 37 south/east fence entities, 33 fence-associated world brushes, and 24 untargeted foliage entities.
- Preserved exactly: 23 `func_rotatingdoor` entities, 88 targetnames, 16 Allied starts, 16 Axis starts, retail Objective scripts, and their target graph.
- Additions: 334 brushes, 152 entities, and 21 neutral deathmatch starts. The compiled BSP contains 35 neutral starts including the retained stock set.
- Custom/retail asset payload added: zero bytes. All new materials and models are references to stock AA content.

## Route and construction result

The playable route now runs from an open Allied court into a west transition lane, eleven-step forest climb, west ridge, broad central causeway, east ridge, fourteen-step descent, lower forest lane, and the annex grand apron. Its narrowest designed combat section is 320 units; the central crossing is 1,024 units wide. Static cover and broad turns preserve close-range bot action without reducing the route to a corridor.

The central completion is intentionally architectural rather than a bare sealing box. The south edge has a solid retaining wall and six piers, five raised grass planters with stock oak trees, and no exposed construction backs. The north facility face has four projecting pilasters, three service doors/lintels, a horizontal band, and three caged-lamp/corona/light groups. Every potentially visible face uses a solid stock material; no ambiguous new structural face depends on caulk, nodraw, or an alpha grate.

## Seal investigation

The route was sealed through focused Q3map probes before the expensive release build:

1. The first route leaked below the central terrain gap; a structural rock foundation was added.
2. The trace moved to the north stock-floor edge; the foundation and facility face were joined to the stock brush boundary.
3. The trace moved through the missing south enclosure; a stock `sky/mohday1` side hull was added.
4. The trace moved through the north underside; a north hull completed that boundary.
5. The trace then exposed the missing central ceiling; a sky ceiling was added.
6. The west stock ceiling ended at Z=832 while the first central ceiling started at Z=960. Matching the ceiling to Z=832 and trimming overlapping ridge slabs removed the final seam.

The accepted probe and release compile both wrote `.prt` and no `.lin`. This proves that `terrainDef` surface extent and visible outdoor scenery cannot be used as proxies for the sealed world hull.

## Compile result

| Stage | Result | Duration | Evidence |
| --- | --- | ---: | --- |
| Q3map BSP | Passed | 119.793 s | BSP19, 19,624 surfaces, zero degenerates, `.prt` present, `.lin` absent |
| VIS | Passed | 0.398 s | 131,080 visibility bytes |
| MOHlight | Passed | 320.630 s | 67 lightmap pages, zero clamp and hash warnings |

Q3map recorded one inherited `textures/notexture` image warning and five stock helper/light leak classifications. They are not a structural leak: the portal file exists, no leak line exists, VIS completed, and runtime emitted no candidate diagnostic.

## Runtime and visual validation

- Objective mode: isolated Pak0-Pak6 plus candidate, BSP parse 0.123 s, Recast 2.150 s, eight bots admitted, five combat events in 60 s, zero candidate diagnostics.
- FFA topology test: BSP parse 0.121 s, Recast 2.134 s, eight bots admitted, four combat events in 60 s, zero candidate diagnostics.
- Compiled-zone audit: Allied perimeter 51 surfaces; west route 172; central causeway 288; east return 328; annex 2,036.
- Visual QA: 28 requested views, 28 screenshots, zero visual-script errors. The inspected route views show no remaining fence/curb, black void, open sky seam, or floating route prop.
- Package inventory: exactly the BSP, map wrapper, and precache wrapper.

Automated navigation/combat establishes playability, not route frequency, objective balance, or door/objective completion. A human traversal remains authoritative for those points.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,637,967 | `871719b096129a5db24e94b77f5c3ba980aacdd4a796fd2fa9d48f415f2a8070` |
| BSP | 13,873,788 | `140ee2bf482ca4f83f1ecea11aee9d79d377cdf2974111a190fe1a9c1b1792eb` |
| PK3 | 2,543,033 | `4b85f8ede35726bbb6ea5f6f71480e2b8a2b10e47930f490c7082156e2833918` |
| Visual contact sheet | 13,031,828 | `fe8d438940bdd655dbbed927a2d336b9975490cc498972ce322aed07a530df62` |

## Knowledge promotion

- A visible perimeter must be inventoried as a complete cooperating system, including worldspawn collision and curb brushes—not only model entities.
- Legacy terrain inspection must report actual cell/surface extents separately from structural hull extents.
- Enlarged outside space needs explicit floor/foundation, side enclosure, and a ceiling joined at the stock boundary; follow each `.lin` trace until the portal file is clean.
- A clean compile is not a visual acceptance. Whole-route views must prove that structural seals read as finished scenery from player height.
- `tools/inspect_map_terrain.js` is the reusable terrain-extent inspector added by this revision.

## Release checklist

- [x] Deterministic source/generator and structural validator
- [x] BSP, VIS, and full light against retail AA data
- [x] Exact isolated PK3 loaded in Objective and FFA
- [x] Scripts and spawn classes present
- [x] Eight bots spawned, navigated, and fought in both modes
- [x] Twenty-eight regression views captured and inspected
- [x] Known human gates stated
- [x] Hashes match repository artifacts
- [x] README, research log, playbook, and asset catalog updated
- [ ] Human full-route, door, and Objective completion/balance playtest
