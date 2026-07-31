# Nuke revision 5: local CS2 topology pilot

## Identity

- Map: `codex_nuke_source2`
- Revision: 5, local enhanced pilot
- Date: 2026-07-31
- Commit before work: `7cc8232e9b573fc62709193cc8b1ae7d60071e90`
- Goal: replace the most visibly blocky Nuke substitutes with measured CS2
  topology and clean original material pixels while preserving the accepted
  brush layout, doors, collision, spawns, and bot routes
- User evidence: revision-4 screenshots showed recognizable Nuke architecture
  but extensive missing objects, broken-looking substitutes, and sparse
  industrial scenes
- Compatibility target: original Allied Assault BSP 19 and OpenMoHAA

## Baseline

- Public revision-4 MAP SHA-256:
  `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040`
- Public revision-4 BSP: 31,236,136 bytes, 47,615 draw surfaces, 154 VIS
  clusters, 166 allocated/written lightmap pages
- Known debt entering revision: bounds-backed machinery and vehicles, 710
  omitted Source 1 autocombines, planarized displacements, and a provisional
  modern-industrial material approximation
- Fixed regression viewpoints: Outside/yard, A-site crane and rafters,
  control rooms, ramp, and B-site reactor/fuel area

## Input measurements

| Measurement | Value |
| --- | ---: |
| CS2 map container | `game/csgo/maps/de_nuke.vpk` |
| CS2 Nuke VPK SHA-256 | `616286bdfba283f8026cb719321e4c2d0986f04ce925cb13b0ff7ff913c33007` |
| CS2 `pak01_dir.vpk` SHA-256 | `f9c82be3724ee2938ef8b1538efb56b7bc252800d47d00c5da32d214ca8e7f4f` |
| Allow-listed asset records | 17 |
| Pilot Source2 resources selected | 12 |
| Pilot MOHAA model assets | 11 |
| Instance-local resources excluded | 2 |
| Safe extended resources deferred | 3 |
| Over-limit resource requiring model partitioning | 1 |
| Local MAP world brushes | 9,407 |
| Local MAP entities | 340 |
| Neutral/Allied/Axis spawns | 32 / 16 / 16 |
| Interactive rotating doors | 4 |

Only resource identifiers, hashes, tools, and derived observations enter the
repository. GLB, PNG, TGA, SKD, SKC, TIKI, BSP, and PK3 payloads derived from
Valve data stay in ignored local directories.

## Defect inventory

| ID | Location/view | Visible symptom | Suspected shared cause | Confidence |
| --- | --- | --- | --- | --- |
| N5-01 | Outside | forklifts and cargo cranes read as stacked boxes | Source 1 proxy bounds were used as art | high |
| N5-02 | B site | reactor vessel head lacks its defining contour | complex mesh was reduced to primitives | high |
| N5-03 | catwalk/rafters | industrial supports lack recognizable topology | bounds cannot encode open frames | high |
| N5-04 | control rooms | desks/displays look sparse and generic | model layer was only partially substituted | high |
| N5-05 | whole map | replacing props risks duplicate silhouettes/collision | old proxies must be suppressed selectively | high |

## Cause-level changes

- Added a pinned CS2-first extraction pipeline using ValveResourceFormat 19.2.
- Added a GLB-to-retail-SKD/SKC/TIKI converter with full node-transform and
  coordinate conversion, deterministic surface splitting, lossless identical-
  attribute vertex welding, multi-GLB model assembly, retail collapse arrays,
  and short TIKI surface identifiers.
- Added a base-color PNG-to-TGA converter and collision/hash checks.
- Added report-backed canonical/staged TGA hash validation; a one-byte
  corruption negative test is rejected as intended.
- Made multi-GLB material resolution source-aware and proved that the fix
  retains the accepted catwalk SKD/SKC/TIKI bytes exactly.
- Added an allow-list separating world-space `agg_merge`/`agg_nomerge`
  resources from instance-local `agg_prop` resources.
- Added an opt-in generator manifest. Without it, the public MAP remains
  byte-identical. With it, the generator adds one origin-zero static entity per
  world-space aggregate and suppresses only explicitly covered Source 1 proxy
  families.
- Added deterministic bounds recentering for runtime aggregates so their
  entity origin is a meaningful lighting-grid sample point while local bounds
  plus origin exactly reconstruct the Source world bounds.
- Extended BSP validation to require each runtime model's exact origin and to
  prove all 27 non-entity lumps unchanged across an entity-only correction.
- Added a local build/validation/package path and ignore boundary.

## Conversion result

- Converted CS2 model assets: 11 (10 static-lit, 1 runtime-lit)
- Source2 topology retained: 12 resources, 92 surfaces, 76,733 vertices,
  67,766 triangles
- MOHlight static set: 71,507 vertices / 63,724 triangles
- Runtime control-room table: 5,226 vertices / 4,042 triangles
- Converted unique CS2 base-color textures: 11
- Material audit: 12/12 bindings are opaque, single-sided, and have a
  referenced base-color image; no alpha shader substitute is required
- Safely suppressed Source 1 proxy instances: 23
- Remaining family-specific fidelity brushes: 2,814
- Local MAP bytes: 8,151,345
- Local MAP world brushes/entities: 9,407 / 340
- Collision policy: existing measured brush/clip collision only
- Regression proof: all four `func_rotatingdoor` blocks and the complete
  32/16/16 neutral/Axis/Allied spawn entity sets are byte-identical to the
  public revision-4 generation
- Expected model-loader warnings: animation downgrade to the old runtime
  format and missing optional per-model collision `.map` helpers

The first static-model proof crashed original Q3map because the SKD writer
omitted two zero-filled per-vertex collapse arrays. Adding those arrays fixed
the crash. A second proof exposed 32-character TIKI surface identifiers as a
binding corruption risk; limiting identifiers to at most 28 characters fixed
all surface-binding warnings. One isolated map then loaded all 12 pilot models
with Q3map exit 0 and no fatal or binding error.

A full-map MOHlight run exposed a separate cumulative static-vertex buffer.
Ten models / 68,570 vertices passed at 207,382 light-data bytes, and eleven /
75,555 passed at 228,513 bytes. The 12-model / 81,002-vertex set crashed with
access violation `-1073741819`. Twelve lightweight unique definitions totaling
10,464 vertices passed, proving the count itself is not the limit. Lossless
welding reduced all topology to 76,733 vertices but still crossed the boundary.
The builder now enforces a conservative 75,000 static-vertex ceiling. The final
composition statically lights 71,507 vertices and emits the 5,226-vertex table
as a runtime `script_model`; all converted triangles remain present. The exact
final static-set probe passed with 216,227 light-data bytes.

Q3map `-onlyents` was also rejected as a shortcut: it changed entity text but
left stale static-model lumps. Static/runtime reclassification requires full
Q3map.

OpenMoHAA renderer-source inspection showed that runtime model lighting is
sampled at the entity origin. The table previously retained world-space
vertices around `(1066, -512, -620)` at entity origin zero. It is now
recentered to local bounds and placed at
`(1066.047593887195, -511.99985813796957, -619.9027421660321)`. Exact
local-bounds-plus-origin reconstruction proves that its world placement did
not move. Because this changes only the established runtime entity origin,
Q3map `-onlyents` may be used after the full classification compile, provided
all non-entity BSP lumps are proven unchanged.

An extended-tier probe exposed another original-tool limit before release. The
224-way retail split of the large HVAC aggregate overflowed Q3map's fixed
24-entry TIKI setup-surface array, produced repeated `Too many skins` errors,
and crashed. The converter and inspector now reject any single TIKI above 24
surfaces, and that resource is marked `requires-model-partitioning`. Before the two catwalk resources were combined into one TIKI, the three
remaining extended roof-HVAC resources plus the pilot formed a 15-definition
safe proof; all 15 passed one combined original-Q3map compile and exact BSP
static-model count/transform validation with no unexpected warning. That is
historical format/loader evidence, not the current manifest's model count.

A complete identifier inventory found 806 Nuke `vmdl_c` resources: 238
`agg_merge`, 41 `agg_nomerge`, 73 `agg_prop`, 353 other world-node resources,
100 entity resources, and one world-physics resource. Of ten high-impact
world-space candidates probed next, six stayed retail-safe and passed one
combined original-Q3map proof: tank top (5 surfaces), ventilation exhausts
(9), office desks (15), metal ladders (18), window assemblies (11), and the
secondary airduct set (10). Silo 1, silo 2, office chairs, and the large roll-up
set require 25, 27, 41, and 53 surfaces respectively, so they are queued behind
multi-model partitioning. None of these ten changes the current pilot payload.

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Pilot all-model Q3map proof | passed | short probe | original 12/12 static set loaded; zero fatal/binding errors |
| MOHlight 11-model boundary proof | passed | short probe | 75,555 vertices; 228,513 light-data bytes |
| MOHlight 12-full-model negative proof | rejected as intended | short probe | 81,002 vertices; access violation `-1073741819` |
| MOHlight 12-lightweight-definition proof | passed | short probe | 10,464 vertices; 33,360 light-data bytes |
| Final static-set MOHlight proof | passed | short probe | 10 models; 71,507 vertices; 216,227 bytes |
| Recentered runtime-table OpenMoHAA proof | passed | 18 s sample | exact 70-entry package; corrected origin; Recast 0.035 s; one bot admitted; zero table-specific load/precache diagnostics |
| Safe extended Q3map proof | passed | short probe | 15/15 BSP static models; zero unexpected warnings |
| Next-pass candidate Q3map proof | passed | short probe | 6/6 BSP static models; zero unexpected warnings |
| Oversized HVAC negative proof | rejected as intended | short probe | 224 surfaces exceed fixed 24-surface setup array |
| Missing-retail-pack full Q3map | rejected as intended | 5,998 s | five unresolved stock shader images; 22 invalid full-width lightmap rectangles |
| Strengthened retail/all-model preflight | passed | 8 s | 18,294 retail files; common/sky resolved; 10 static definitions; 71,507 / 75,000 vertices lit |
| Corrected full Q3map BSP | passed | 5,572 s | 50,407 input / 47,329 output / 3,078 removed; 10 expected downgrade + 10 optional collision-helper warnings; zero unexpected |
| Q3map VIS | passed | <1 s | 154 clusters; 283 portals; 3,704 visibility bytes |
| Lossless atlas repack | passed | short | 42,559 lightmapped surfaces; 192 to 165 pages; one-pixel gutters |
| MOHlight | passed | 4,749 s | 10 models / 71,507 vertices lit; zero vertices in solid leaves; 216,247 model-light bytes; 28 entity-light leaves clamped to retail maximum 60 |
| Runtime-origin entity-only update | passed | 6 s | exact table origin present; all 27 non-entity BSP lumps byte-identical |
| Deterministic local package | passed | two builds | 70 entries; identical 14,877,947-byte PK3 and SHA-256 |

The original-tool compile, local package, and automated runtime gates are
complete. Human screenshot comparison remains a separate visual-fidelity gate.

## Runtime and bot validation

- Exact isolated PK3: 70 entries, 14,877,947 bytes, SHA-256
  `5391F57425E3E27F271876F90E42433EF58DE369A3B11F23D8A2B379DE2B7C0D`
- Isolation: exactly seven retail AA packs plus the one candidate package
- OpenMoHAA: `0.82.1-beta+5.a72bc15`; `omohaaded.exe` SHA-256
  `DDB7D12666560701D914FF0D26B5082D686C1CC027407A929FB4950D24FBDAFB`
- Runtime duration: 180.591 seconds across two automatic map cycles
- BSP parse: 0.157 and 0.183 seconds
- Recast: 17.136 and 17.304 seconds
- Bots: eight unique bots, 16 admission events across both cycles
- Combat: 154 combat/death lines
- Candidate-specific Source2 model, runtime-table, fatal-map, and precache
  diagnostics: zero
- The stock seven-pack environment still reports missing `global/bot_run.scr`;
  bots nevertheless navigate and fight, so this is recorded separately from
  candidate failures.
- Automated bot movement/combat is proven; human screenshot and collision-feel
  review remain required.

## Visual regression matrix

| View | Baseline defect | Current status | Evidence required |
| --- | --- | --- | --- |
| Outside | blocky forklifts/cranes | topology replacement built | new client screenshot |
| A/rafters | sparse crane/catwalk forms | topology replacement built | new client screenshot |
| Control rooms | generic desks/displays | partial topology replacement built | new client screenshot |
| B site | crude reactor head | topology replacement built | new client screenshot |
| Routes/doors | accepted collision and four doors | preserved; automated bots navigate and fight | human collision-feel pass |

## Outcome

- Fixed in tooling: reproducible CS2 topology extraction, retail static-model
  emission, model-load crash, TIKI surface binding, duplicate-proxy policy,
  local legal boundary, and deterministic validation
- Improved by construction: defining machinery geometry and its original
  base-color material data
- Unchanged: public revision-4 package, accepted direct-converted architecture,
  collision foundation, lights, doors, and spawn placement
- Remaining known debt: `agg_prop` instance transforms, broader resource
  coverage, and human screenshot/collision judgment

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| Public revision-4 MAP | 8,195,795 | `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040` |
| Local enhanced MAP | 8,151,345 | `F89E7C99B2BC3AE501E06EA76982EE60D27BE778E8646D0AE1138815650934A7` |
| Local enhanced BSP | 31,279,504 | `150E6E27A3969493706130C82591E27E346E52CB7426D8F3F490CB207F9A7CF0` |
| Local enhanced PK3 | 14,877,947 | `5391F57425E3E27F271876F90E42433EF58DE369A3B11F23D8A2B379DE2B7C0D` |

## Knowledge promotion

- Map README: local CS2 pipeline, commands, scope, and legal boundary
- Research log: exact static model formats, transform proof, failure sequence,
  proxy-replacement rule, and public-build determinism
- Playbook: retail SKD/TIKI gates, aggregate coordinate-space gate,
  commercial-payload boundary, and isolated model-load proof
- Open questions: Source 2 instance-transform recovery for `agg_prop`,
  animated/dynamic CS2 assets, and which additional resource families produce
  the largest visible gain within AA limits

## Release checklist

- [x] Public generator remains reproducible and byte-identical without opt-in.
- [x] Local extraction/conversion is reproducible from user-owned files.
- [x] All pilot models load through original Q3map in an isolated proof.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded.
- [x] Required spawn classes/scripts and four doors remain present.
- [x] Bots spawned, moved, and fought.
- [ ] Regression views were inspected.
- [x] Known debt is documented honestly.
- [x] Final hashes are recorded.
- [x] Documentation is updated.
- [ ] Commit is pushed.
