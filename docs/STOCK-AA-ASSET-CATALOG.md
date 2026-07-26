# Stock Allied Assault asset catalog

Status: verified starter catalog, not yet exhaustive

Last updated: 2026-07-26

This file records stock AA asset names that have been compiled and rendered
successfully in generated maps. It is not a substitute for visual inspection.
Future work should add thumbnails/contact sheets, dimensions, shader behavior,
and map examples.

Stock asset references do not need to be bundled in a custom PK3; the player
supplies the retail AA data.

## Construction and hidden surfaces

| Role | Verified stock material | Notes |
| --- | --- | --- |
| Hidden face | `common/caulk` | Requires retail shader definitions during compile |
| Day sky | `sky/mohday1` | AA-compatible sky used by current conversions |
| Player/solid clipping | `common/clip`, `common/playerclip` | Use intentionally; do not render |
| Material clipping | `common/metalclip`, `common/stoneclip` | Match collision sound/behavior where appropriate |

## Castle and European materials

| Role | Verified stock material | Current use |
| --- | --- | --- |
| General stone wall | `general_structure/stonewall2` | Cobblestone concrete/stone fallback |
| Stone brick | `general_structure/stonebricks1` | Cobblestone primary architecture |
| Dark stone brick | `general_structure/stonebricks1drk` | Port and shadowed architecture |
| European plaster wall | `central_europe/exterior_wall_2` | Wall/plaster class |
| Small cobble | `central_europe/small_cobble` | Roads and floors |
| Rough grass | `wilderness/m3l3grass_1rough` | Terrain backing and grass cover |
| Wood shingles | `general_structure/jh_woodshingles1a` | Roofs |
| Wood beam | `general_structure/beam_wood1` | Beams and wood fallback |
| Shutter | `central_europe/shutter_set2` | Non-solid façade panels |
| Wood door | `central_europe/frenchdoor_wood1` | Door panels |
| Window glass | `mohcommon/window5` | Compiled and rendered as stock translucent glass in Cobblestone revision 3 |
| Reinforced crate | `german/crate_reinforced1_side` | Generated cover |
| Rusted iron | `german/rusty_iron` | Barrels/metal accents |
| Iron wall | `das_boot/ironwall1` | Generic metal |
| Deck grate | `general_industrial/deckgrate_set1a` | Grates |
| Pipe | `general_industrial/jh_pipe1` | Pipe/duct fallback |

## Industrial/V2 family candidates

These names are verified in the stock corpus. They are candidates, not a
mandatory palette:

| Role | Stock material candidates |
| --- | --- |
| Bunker wall | `general_structure/bunker_wall`, `normandy/bunker_conc3` |
| Concrete | `general_structure/jh_conc512b`, `mohcommon/jeff-concrete-walla`, `mohcommon/jeff-concrete-wallb` |
| Floor/steps | `algiers/whsflrset1_1b`, `algiers/doccrtset_1stepsml` |
| Metal deck | `general_industrial/deckgrate_set1a`, `general_industrial/deckgrate_set1b` |
| Bunker ceiling | `normandy/bunk_ceiling` |
| Structural metal | `mohcommon/ibeam_1a`, `general_industrial/verticalbrace` |
| Utility box | `general_industrial/utilitybox_side`, `general_industrial/utilitybox_front`, `general_industrial/utilboxtop` |

## Stock models proven in generated-map QA

| Role | Stock model | Notes |
| --- | --- | --- |
| Common tree | `static//tree_commontree.tik` | Used in Cobblestone at reduced scale |
| Regular bush | `static//bush_regularbush.tik` | Used in Cobblestone |
| Caged lamp | `static//lightbulb_caged.tik` | Present in `obj_team2`; pair with a purposeful light |
| Orange corona | `static//corona_orange.tik` | Decorative light effect; not illumination by itself |

## Selection protocol

Before finalizing a map material:

1. Verify the shader and image exist in retail AA data.
2. Extract and inspect the actual image.
3. Check natural scale and directionality.
4. Compare at least two candidates in the map's lighting.
5. Confirm surface/content flags after compile.
6. Record the winner, rejected alternatives, and reason.

Do not infer visual suitability from a filename alone.

Cobblestone revision 3 also established that the source families
`de_cbble/outwall02` and `de_cbble/trimwall01` read as castle masonry in this
layout. Mapping them to `general_structure/stonebricks1` is more coherent than
the broad European-plaster fallback. This is a source-family decision, not a
rule that every material containing `wall` or `trim` should become stone.

## Catalog backlog

- Extract all stock AA texture images and shader metadata.
- Generate category contact sheets with shader names printed below thumbnails.
- Record pixel dimensions, alpha, surface flags, common scale, and stock-map
  examples.
- Add verified TIKI bounds and origin conventions for useful static props.
- Separate AA-only assets from Spearhead/Breakthrough dependencies.
