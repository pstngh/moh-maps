# Nuke revision 4: measured visual-fidelity layer

## Identity

- Map: `codex_nuke`
- Revision: 4
- Date: 2026-07-30
- Commit before work: `23add09c54e881bcab59d18f3698a9901afd327e`
- Goal: make the stable but visibly empty revision-3 map resemble the CS:GO
  Nuke reference in its structures, machinery, cover, silhouette, and room
  furnishing rather than applying another texture-only pass.
- User evidence: direct verdict that revision 3 is “very empty”; the user
  supplied the Nuke gallery at
  `https://counterstrike.fandom.com/wiki/Nuke/Gallery` as a location-by-location
  visual reference.
- Compatibility target: retail Allied Assault BSP 19 and OpenMoHAA DM/TDM with
  4-10 bots.

## Visual-reference checklist

- Gallery coverage: A Site, B Site, T and CT spawn, Outside/garage, Tunnel,
  Ramp, Trophy, Hell, Lobby, Hut, Squeaky, Roof, Secret, Vent, Heaven, Mini,
  Main, observation/control, and decontamination.
- Official design cues: clean institutional surfaces, readable routes,
  reconfigured Outside cover, restricted A rafters with canisters and a
  Hut-to-Rafters route, expanded B planting/storage space, and deliberately
  modular industrial detail such as pipes, I-beams, HVAC, and heavy machinery.
- References:
  - `https://counterstrike.fandom.com/wiki/Nuke/Gallery`
  - `https://www.counter-strike.net/reintroducing_nuke`
- These references establish visual roles and location coverage only. The
  committed/distributed geometry and art are original AA-native substitutes;
  no screenshot, Source texture, or Source model payload is bundled.

## Baseline

- Previous PK3 SHA-256:
  `4790A691A592DAA7B6D35DD5BD658E02760EB994EC691152F8601D84D7FFCF63`
- Previous BSP: 23,494,100 bytes; 32,140 emitted faces; 154 clusters.
- Known debt entering revision: 3,065 unsupported ordinary prop instances,
  710 omitted BSP autocombines, sparse A/B-site machinery, missing outdoor
  vehicles and utility equipment, weak roof/yard silhouette, sparse offices
  and control rooms, and a provisional flat sky.
- Fixed regression viewpoints: Outside/garage, T entrance and roof, A site
  from Mini/Main, Heaven, B site and observation, ramp/trophy/hell, lobby/hut,
  secret stairs, and the vent transition.

## Input measurements

| Measurement | Value |
| --- | ---: |
| World solids | 8,039 |
| Total brush sides | 48,098 |
| Displacement sides | 761 |
| Entities | 10,488 |
| Props/unique models | 6,898 model entities / 1,405 unique models |
| Playable-envelope model instances | 4,687 |
| Materials | 121 visible brush materials |
| Neutral/Allied/Axis spawns | 32 / 16 / 16 |
| Lights | 471 Source candidates |

The committed `fidelity-manifest.json` records the 4,687 playable-envelope
model transforms and measured studio-header hulls as derived facts. It
contains no Source mesh, texture, VMT, VTF, MDL, VVD, or VTX payload.

## Defect inventory

| ID | Location/view | Visible symptom | Suspected shared cause | Confidence |
| --- | --- | --- | --- | --- |
| N4-01 | A site | Reactor/silo room lacks its defining white vessels, yellow crane framing, columns, platforms, control panels, and ceiling fixtures | Important ordinary Source props were outside the narrow rev3 allow-list | High |
| N4-02 | B site/observation | Lower reactor room and control areas read as bare converted architecture | Vessel head, fuel racks, consoles, displays, equipment, and furniture were omitted | High |
| N4-03 | Outside/garage | Yard lacks vehicles, forklift, cargo crane, transformers, poles, fences, foliage, and roof equipment | Ordinary prop models were omitted even when their family and measured bounds were understandable | High |
| N4-04 | Ramp/lobby/trophy | Rooms are geometrically present but visually under-furnished | Doors, frames, windows, lockers, desks, chairs, hatches, and ventilation were omitted | High |
| N4-05 | Whole map | Earlier rev2 fill attempt created giant bars and slabs | Aggregate autocombine AABBs were mistaken for model topology | Proven |
| N4-06 | Exterior terrain | Some planarized displacement boundaries can still crack | Source displacement curvature is simplified | Medium |
| N4-07 | Skyline | Flat sky and absent distant 3D skybox reduce the original atmosphere | Current target uses a stock provisional sky; distant Source skybox models are intentionally omitted | High |

## Planned changes

| Defect IDs | Cause-level change | Expected count/visual effect | Risk |
| --- | --- | --- | --- |
| N4-01, N4-02 | Add coordinate-preserving family reconstructions for site vessels, reactor head, fuel racks, sparse crane frames, platforms, columns, consoles, displays, and electrical equipment | Restore Nuke’s defining interior industrial language without closing walkable space | Medium |
| N4-03 | Add measured multi-brush vehicles, forklifts, crane, transformers, power poles, fencing, roof ventilation, cover, and original foliage cards | Fill the exterior with recognizable yard equipment and skyline detail | Medium |
| N4-04 | Add measured doors, frames, windows, hatches, furniture, chairs, and ventilation | Make transitions and side rooms read as occupied facility spaces | Low-medium |
| N4-05 | Keep all 710 autocombines omitted and keep validator prohibition on aggregate fill | No return of rev2’s false bars/slabs | Low |
| N4-06 | Retain the measured planar-underlay policy unchanged | Avoid introducing speculative broad floors | Low |

## Material and asset decisions

| Surface/prop role | Candidates inspected | Selected asset or original art | Reason |
| --- | --- | --- | --- |
| Clean vessels and machinery | Existing gray corrugation and Source gallery palette | Original `clean_white_metal.tga` | Restores the clean white industrial masses visible in Nuke without copying Source art |
| Safety equipment/cranes/rails | Existing gray metal | Original `safety_yellow.tga` and `safety_red.tga` | Makes cranes, rails, and vehicles legible at a distance |
| Equipment and consoles | Existing blue corrugation and dark concrete | Original `equipment_blue.tga`, `control_panel.tga`, and `rubber.tga` | Separates machinery, displays, vehicle tires, and office/control-room furniture |
| Exterior foliage | Source foliage models were reference-only and unavailable to the target | Original alpha-tested `foliage.tga` cross cards | Recovers exterior density without redistributing Source textures or meshes |
| Transparent enclosure | Existing original chainlink/glass shaders | Retained and expanded by measured placement | Already validated in revision 3 |

The palette remains original work derived from the repository’s licensed or
generated art sources. No Valve texture or model is packaged.

## Conversion result

- Generated world brushes: 9,448.
- Converted Source solids: 5,639; invalid: zero.
- Displacements/backings: 604 planarized faces and 632 measured seam
  underlays, with maximum expansion 117 units.
- Fidelity substitutions: 1,932 handled model instances and 2,855 new
  family-specific brushes.
- Baseline measured props retained outside the new layer: 282 brushes,
  including 206 fluorescent fixtures, 49 bollards, and 27 concrete barriers.
- Hero industrial forms retained: 34 brushes for outside water tanks, process
  silos, and reactor skyline structures.
- Unsupported ordinary props reduced from 3,065 to 1,546.
- Foliage: 242 instances; chainlink: 236; ventilation: 216; cover: 178;
  structural columns/supports: 137; furniture: 137; electrical equipment: 83;
  control-room displays: 59; static doors: 44; chairs: 35; industrial rails:
  24; transformers: 22; cars: 17; forklifts: 8; cargo-crane components: 8.
- Spawn entities: 16 Axis, 16 Allied, and 32 neutral deathmatch.
- Lights: 259 retained from 471 Source candidates after fixture-cell
  deduplication.
- Autocombines: 710 omitted, zero inferred aggregate fills.
- Targeted alpha-detail `+surfaceparm nolightmap`: 4,320 sides (2,904 foliage-card sides and 1,416 chain-link-panel sides); zero opaque architectural, machinery, vehicle, furniture, cover, or fence-post sides.

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP, first full-detail pass | Succeeded | 5,328 s | Valid geometry; later MOHlight requested 210 pages |
| Q3map BSP, canonical alpha-detail pass | Succeeded | 5,285 s | 50,669 input faces; 47,591 output faces; 3,078 removed; empty stderr |
| Q3map fast VIS, canonical pass | Succeeded | 1 s | 154 clusters; 283 portals; 3,704 visibility bytes; empty stderr |
| MOHlight, alpha-detail-only correction | Failed hard budget gate | <1 s | Requested 194 lightmaps; retail AA limit is 180 |
| Lossless BSP lightmap repack | Succeeded | <1 s | 42,815 baked surfaces retained; 194 pages repacked to 166 with one-pixel gutters |
| Final MOHlight | Succeeded | 1,581 s | 166 written pages; empty stderr; 28 entity-light leaves clamped to 60 lights |

### Lighting-budget correction

The first full-detail BSP/fast-VIS build was valid, but MOHlight requested 210
lightmaps against the engine's hard 180-page ceiling.

The first proposed correction used `q3map_lightmapSampleSize`, but binary-string
inspection and execution proved that the bundled MOHTools 1.48 programs do not
support that newer q3map2 control. A `-samplesize` probe also left MOHlight in a
zero-CPU wait and was terminated. Those unsupported directives were removed.

The corrected source excludes exactly 4,320 large alpha-detail sides from the
atlas: 2,904 foliage cross-card sides and 1,416 chain-link-panel sides. Q3map
retained 2,904 foliage and 1,408 chain-link draw surfaces after ordinary face
removal. Chain-link posts and every opaque architectural face, machinery,
vehicle, furniture, cover, and structural support retain normal baked
lighting. Both alpha shaders use renderer-supported constant dark tint. Static
validation rejects any source-level `+surfaceparm nolightmap` side outside the
two-material allow-list.

That narrow source correction still allocated 194 pages. A controlled glass
shader experiment produced the same 194 pages and the same instant MOHlight
failure, proving that a shader-level flag does not remove an already allocated
draw-surface rectangle.

The final correction is a deterministic post-VIS BSP 19 repack based on the
actual MOHAA Q3map lightmap allocator semantics. It collects every lightmapped
draw surface, rejects shared vertex ranges and invalid rectangles/UVs,
globally skyline-packs the exact rectangles with a one-pixel gutter, updates
the draw-surface page/X/Y fields, and translates each owned draw vertex's
normalized lightmap UV by the exact atlas delta divided by 128. It preserved
all 42,815 baked surfaces and every original rectangle width/height while
reducing 194 pages to 166. Exact texel utilization is 53.98%; reserved
rectangle-plus-gutter utilization is 96.12%.

The final BSP inspector reports 166 allocated and 166 written pages, 47,615
draw surfaces, 38 shaders, and the expected referenced non-lightmapped records
only: foliage, chain-link, and the pre-existing black window backing. This is a
lossless atlas-placement fix, not another broad vertex/fullbright workaround.
## Runtime and bot validation

- Exact isolated PK3 tested: 26 entries, 9,567,575 bytes, SHA-256
  `214F0EAD023D754F5FA199A9C9F8E5A66E6C0AC9F89EF0A6DA6B53A1834E067F`.
- OpenMoHAA version: local 0.82.1 development runtime used by the repository's
  existing map QA workflow.
- Bot configuration: `sv_maxbots 8`, `sv_numbots 8`, DM.
- BSP parse result: 0.158, 0.160, and 0.166 seconds over three automatic match
  cycles.
- Navigation-build result: Recast completed in 16.404, 16.698, and 17.370
  seconds.
- Spawn/respawn result: all eight bots entered each cycle; 24 admissions total.
- Combat result: 263 combat/death events across the sample.
- Fatal errors: zero matched fatal, recursive-error, or map-load markers.
- Shutdown: only the launched isolated server PID was stopped afterward.

## Automated visual QA

The exact-package OpenMoHAA client generated fifteen fixed-camera frames in two
scripted sweeps. The first sweep covered Outside, the cargo/forklift yards,
interior candidates, and an overview. The second was anchored to measured A/B
silo, crane, reactor, fuel-rack, and control-display placements.

Usable views confirm that Outside is no longer the empty revision-3 shell and
that lower industrial spaces now contain yellow crane beams, platforms,
stairs, ceiling modules, equipment masses, and the clean blue/gray/white
institutional palette. Several coordinates landed against walls, ceilings, or
black window-backing volumes and therefore cannot support a room-level visual
claim. The provisional stock sky, conservative blocky substitutes, omitted
low-value clutter, and any alignment defect exposed by the user's next
playtest remain explicit debt. Automated screenshots are a regression screen,
not human acceptance.

## Visual regression matrix

| View | Baseline defect | Result: fixed/improved/unchanged/regressed | Evidence |
| --- | --- | --- | --- |
| Spawn route | Sparse facility dressing | Pending human verdict | Automated cameras were not route-following; user playtest remains required |
| High overview | Empty roof/yard silhouette | Improved in renderer | Automated overview/yard frames show the restored dome, roof equipment, fencing, vehicles, cover, and utility dressing |
| Long exterior | Empty parking/utility yards | Improved in renderer | Exact-package Outside frames show cars/trucks, forklift forms, fencing, cover, poles, and facility masses |
| Deep interior | Bare A/B industrial rooms | Improved, human verdict pending | Usable lower-site frames show yellow crane beams, platforms, stairs, equipment, and ceiling modules; several other cameras were obstructed |
| Transition | Bare doors/windows/ramps | Improved in source | Static doors, frames, windows, hatches, ventilation, and furnishings are rebuilt |
| Map edge | Sparse vegetation/utility boundary | Improved in renderer | Outside frames confirm the new fencing, cover, utility pieces, vehicles, and original non-solid foliage layer |
| Displacement boundary | Possible terrain cracks | Unchanged | Existing measured underlays retained; no speculative broad floor |
| Repeated modules | Missing props or giant aggregate bars | Improved in source | Ordinary families restored; all autocombine aggregate fills remain forbidden |

## Outcome

- Fixed in source: the primary ordinary-prop omission class that made revision
  3 read as empty.
- Improved in source: A site, B site, Outside, garage/yard, control rooms,
  offices, roofline, fences, and repeated facility modules.
- Unchanged: Source displacement curvature, distant 3D skybox, and provisional
  stock sky.
- Regressed: none found by compile, runtime, or the usable automated frames; the
  user screenshot verdict is still pending.
- Newly exposed: the remaining 710 autocombines are now a more isolated detail
  debt rather than the majority of visible scene content.
- Remaining known debt: user screenshot review, any family-specific alignment
  fixes, and topology-backed reconstruction of selected autocombines only.
  The 1,546 omitted ordinary instances are now concentrated in low-priority
  signage, light cables/attachments, switches, outlets, alarms, sprinklers,
  binders, helmets, and similar small clutter; promote any of them only when a
  screenshot proves that its absence matters.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP | 8,195,795 bytes | `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040` |
| BSP | 31,236,136 bytes | `675E457505389837F6F2BAA99B44A818701BA3BB9D9E68380E9D689556E2CA95` |
| PK3 | 9,567,575 bytes | `214F0EAD023D754F5FA199A9C9F8E5A66E6C0AC9F89EF0A6DA6B53A1834E067F` |
| Derived fidelity manifest | 2,931,826 bytes | `F232A9DC88703F7A09446DAB2650FDBA51C21BF139F8C4123EF2652C323976C4` |

## Knowledge promotion

- Map README records final compile, atlas, runtime, visual-QA, and artifact
  evidence.
- Research log records the measured ordinary-family method and final gates.
- Playbook records both the family-specific prop rule and the proven lossless
  BSP lightmap-atlas repack, including its invariants and failed alternatives.
- Art provenance records the seven new original Nuke industrial/foliage
  materials and the complete 22-texture package.
- Open questions/hypotheses: which visually important autocombine families
  remain noticeable after ordinary-prop restoration; whether the stock sky
  should be replaced after the geometry review.

## Release checklist

- [x] Source/generator is reproducible.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded.
- [x] Required spawn classes/scripts are present.
- [x] Bots spawned, moved, and fought.
- [x] Regression views were inspected in the target renderer.
- [x] Known debt is documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.
