# Stock Allied Assault asset catalog

Status: audited starter catalog, not exhaustive

Last updated: 2026-08-09

This file records stock AA asset names observed to compile or render in stated
roles. A generated map's success does not prove that an asset is visually
suitable, grounded, correctly scaled, or accepted in another context. Recheck
the retail asset, shader behavior, origin, collision, scale, lighting, and
full-resolution in-engine result for each new use.

Stock asset references do not need to be bundled in a custom PK3; the player
supplies retail AA data. Do not commit extracted retail payloads.

## Construction and hidden surfaces

| Role | Observed stock material | Notes |
| --- | --- | --- |
| Hidden face | `common/caulk` | Requires retail shader definitions; use only on faces proven permanently hidden |
| Day sky | `sky/mohday1` | AA-compatible sky observed in current conversions; not a universal lighting solution |
| Player/solid clipping | `common/clip`, `common/playerclip` | Use intentionally; audit every newly playable boundary |
| Material clipping | `common/metalclip`, `common/stoneclip` | Match collision sound/behavior where evidence supports the role |

## Castle and European materials

| Role | Observed stock material | Current evidence scope |
| --- | --- | --- |
| General stone wall | `general_structure/stonewall2` | Cobblestone concrete/stone fallback |
| Stone brick | `general_structure/stonebricks1` | Cobblestone primary architecture |
| Dark stone brick | `general_structure/stonebricks1drk` | Port and shadowed architecture |
| European plaster wall | `central_europe/exterior_wall_2` | Wall/plaster class |
| Small cobble | `central_europe/small_cobble` | Roads and floors |
| Rough grass | `wilderness/m3l3grass_1rough` | Terrain backing and grass cover |
| Wood shingles | `general_structure/jh_woodshingles1a` | Roofs |
| Wood beam | `general_structure/beam_wood1` | Beams and wood fallback |
| Shutter | `central_europe/shutter_set2` | Non-solid facade panels |
| Wood door | `central_europe/frenchdoor_wood1` | Door panels |
| Window glass | `mohcommon/window5` | Rendered as stock translucent glass in Cobblestone revision 3 |
| Reinforced crate | `german/crate_reinforced1_side` | Generated cover |
| Rusted iron | `german/rusty_iron` | Barrels/metal accents |
| Iron wall | `das_boot/ironwall1` | Generic metal |
| Deck grate | `general_industrial/deckgrate_set1a` | Grates; never assume alpha surfaces are safe structure |
| Pipe | `general_industrial/jh_pipe1` | Pipe/duct fallback |

## Industrial/V2 family candidates

These names exist in the inspected stock corpus. They are candidates, not a
mandatory palette or proof of visual suitability:

| Role | Stock material candidates |
| --- | --- |
| Bunker wall | `general_structure/bunker_wall`, `normandy/bunker_conc3` |
| Concrete | `general_structure/jh_conc512b`, `mohcommon/jeff-concrete-walla`, `mohcommon/jeff-concrete-wallb` |
| Floor/steps | `algiers/whsflrset1_1b`, `algiers/doccrtset_1stepsml` |
| Metal deck | `general_industrial/deckgrate_set1a`, `general_industrial/deckgrate_set1b` |
| Bunker ceiling | `normandy/bunk_ceiling` |
| Structural metal | `mohcommon/ibeam_1a`, `general_industrial/verticalbrace` |
| Utility box | `general_industrial/utilitybox_side`, `general_industrial/utilitybox_front`, `general_industrial/utilboxtop` |

## Stock models observed in generated-map QA

| Role | Stock model | Evidence boundary |
| --- | --- | --- |
| Common tree | `static//tree_commontree.tik` | Rendered in Cobblestone at reduced scale; grounding must be rechecked |
| Oak tree | `static//tree_oak.tik` | Rendered in rejected obj_team2 revision 4; that run does not prove coherent placement or visual acceptance |
| Regular bush | `static//bush_regularbush.tik` | Used in Cobblestone; recheck collision and grounding |
| Caged lamp | `static//lightbulb_caged.tik` | Present in stock `obj_team2`; pair with purposeful illumination |
| Orange corona | `static//corona_orange.tik` | Decorative effect, not illumination by itself |
| Opel truck | `static//vehicle_opeltruck.tik` | Loaded/rendered in obj_team2 expansion QA; placement quality is not proven by the rejected map |
| Nazi crate | `static//nazi_crate.tik` | Loaded/rendered in obj_team2 expansion QA; placement quality is not proven by the rejected map |

`codex_obj_team2_expanded` revision 4 observed that the listed oak, Opel, crate,
caged-lamp, and corona paths resolved and rendered without candidate runtime
diagnostics. Later human evidence rejected the map's visual construction, so any
earlier implication that the run proved coherent grounding, placement, or
scene quality is `SUPERSEDED`. Retain only the narrow asset-resolution
observation and reverify origins, support, scale, collision, and viewing domain.

Each new `static//corona_orange.tik` placement can add an optional missing
editor-helper `.map` notice during original Q3map. Prefer the warning-free,
explicitly precached runtime-corona pattern observed in standalone maps when
stock-source fidelity is not required, then verify the exact package.

## Selection protocol

Before finalizing a material or model:

1. Verify the shader/image/model exists in locally supplied retail AA data.
2. Inspect the actual asset; filenames are not visual evidence.
3. Check origin, bounds, collision, natural scale, and directionality.
4. Compare relevant alternatives under the candidate's lighting.
5. Confirm surface/content flags and runtime behavior after compile.
6. Inspect full-resolution player-height and overview evidence.
7. Record the winner, rejected alternatives, evidence label, and reason.

Cobblestone revision 3 observed that Source families `de_cbble/outwall02` and
`de_cbble/trimwall01` read more coherently as castle masonry when mapped to
`general_structure/stonebricks1` than to the broad plaster fallback. Treat this
as a source-family observation, not a filename-based global rule or acceptance
of the map.

## Catalog backlog

- Extract and privately inspect stock AA images and shader metadata.
- Generate category contact sheets with shader names below thumbnails.
- Record pixel dimensions, alpha, surface flags, typical scale, and stock-map
  examples.
- Add verified TIKI bounds, origin, collision, and support conventions.
- Separate AA-only assets from Spearhead/Breakthrough dependencies.

## V2 Depot stock-industrial observation set

Revision 1 compiled and rendered these retail families together with zero
compiler/light warnings and no exact-runtime asset diagnostics: bunker/concrete
(`bunker_wall`, `jh_conc512b`, `bunker_conc3`); floor/steps
(`whsflrset1_1b`, `doccrtset_1stepsml`); structure (`ibeam_1a`, bunker
ceiling/beams, `verticalbrace`); metal (`deckgrate_set1b`, `ironwall1`,
`rusty_iron`); and face-specific utility-box/crate sets.

The run also observed a working static caged lamp and a clean explicitly
precached `static//corona_orange.tik` runtime model when collision was
unnecessary; the tested retail build lacked its optional static `.map` helper.
The Opel truck loaded and rendered. These are role-scoped technical
observations, not proof of V2 Depot's visual quality or a mandatory palette.
