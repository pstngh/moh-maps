# MOHAA `.map` source format reference (retail corpora)

This document is a measured reference for the original `.map` sources
stored in this repository — the retail Allied Assault, Spearhead, and
Breakthrough multiplayer and single-player campaign sources plus five
community maps: what the format's constructs mean and which conventions
those sources actually use. The repository's production target is
multiplayer maps only; the single-player sources are reference material for
format semantics and vocabulary, never build targets.
All counts were produced by parsing the current files programmatically;
constructs are quoted from the corpus verbatim. Numeric flag decodes come
from the MOHAA SDK-compatible `code/qcommon/surfaceflags.h` in the
OpenMoHAA source tree.

This document supersedes the early format primer at the top of the research
log's "Text `.map` grammar" section, which remains in place as chronological
evidence. Use this document when reading the retail sources for reference or
when debugging how a construct in them is meant to behave.

Confidence labeling: everything presented as a count, a duplication check,
or a decoded bit value is script-reproducible measurement. The handful of
interpretive readings — the `terrainDef` header fields, the exact modes of
`farplane_cull`/`farplane_bias`, and `map_time` as a save timestamp — are
worded as observations ("observed", "editor semantics not documented") and
should not be treated as engine-verified until someone tests them. Normative production
rules for this repository's own maps stay in
[`MAP-GENERATION-PLAYBOOK.md`](MAP-GENERATION-PLAYBOOK.md), and each
generated map documents itself under `generated/<map>/`; neither is covered
here.

## 1. Corpus inventory

| Corpus | Files | Entities | Brushes | `patchDef2` | `terrainDef` | Trailing flag columns |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `aa/` MP (`mohdm*`, `obj_team*`) | 10 | 6,574 | 34,120 | 1,946 | 35 | Real numeric values |
| `aa/` SP campaign (`m1l1`-`m6l3e`, `training`) | 35 | 64,205 | 161,390 | 15,599 | 5,972 | All zero |
| `aa_custom/` (community objective maps) | 13 | 13,491 | 45,489 | 4,272 | 32 | Real numeric values |
| `bt/` MP | 24 | 21,477 | 129,805 | 11,312 | 1,657 | All zero |
| `bt/` SP campaign (`e1l1`-`e3l4`) | 11 | 34,932 | 82,005 | 6,840 | 4,522 | All zero |
| `sh/` MP | 13 | 11,217 | 70,158 | 5,410 | 1,047 | All zero |
| `sh/` SP campaign (`t1l1`-`t3l2`) | 9 | 24,920 | 70,894 | 4,704 | 3,546 | All zero |

Provenance notes:

- The retail sources arrived as an upload (`Add files via upload`) and match
  the officially released EA map-source drops for AA, Spearhead, and
  Breakthrough multiplayer maps.
- Every file in `sh/` is byte-identical to its same-named file in `bt/`
  (verified with `cmp` across all 13 pairs). `bt/` additionally contains the
  11 Breakthrough-only maps. Analysis of `bt/` therefore covers `sh/`
  entirely.
- The per-side contents/surface-flag integers are zeroed in every SH/BT
  source and in the AA single-player campaign drop; only the AA MP sources
  and the community maps kept the compiled values. The zeroing is therefore
  an export-batch property, not an expansion property. All variants
  compile, which proves the compiler re-derives these flags from shader
  `surfaceparm` records and treats the stored integers as editor cache, not
  authority (see section 4.3).
- The single-player sources were added expressly as reference material:
  they carry the AI/vehicle/objective vocabulary and the overwhelming
  majority of the corpus's terrain (14,040 of 16,794 `terrainDef`
  instances). Production work in this repository targets MP only.
- A complete per-file table is in the appendix (section 10).

## 2. File anatomy

A `.map` file is a sequence of entity blocks. Entity 0 must be
`worldspawn`. Each block is:

```text
// entity 0
{
"key" "value"
...
// brush 0
{
<side lines, or a patchDef2 / terrainDef sub-block>
}
...
}
```

- Key/value pairs and brush blocks may interleave; retail files put keys
  first, but key order is not significant (retail files disagree on it).
- Comments are `// ...` lines. Retail AA writes `// entity N` / `// brush N`
  (lowercase); Spearhead/Breakthrough write `// Entity N` / `// Brush N`.
  The compiler ignores them.
- Brush-carrying entities (`worldspawn`, `func_*`, `trigger_*`,
  `script_object`, `vis_leafgroup`) contain brush/patch blocks; point
  entities (`light`, `info_*`, `static_*`, ...) contain only keys, with
  position in an `"origin" "X Y Z"` key.
- Brace depth must balance exactly.

## 3. `worldspawn` key reference

Keys observed across the corpus, with the corpora that use them:

| Key | Example values | Meaning | Seen in |
| --- | --- | --- | --- |
| `message` | `"South France"`, `"Omaha Beach"` | Map display name | all |
| `ambientlight` | `"7.5 7.5 7.5"`, `"12 12 24"` | Base ambient light color (RGB, 0-255 scale) | all |
| `ambient` | `"50"`, `"5 5 5"` | Alternate/additional ambient term (scalar or RGB) | aa, bt/sh |
| `suncolor` | `"65 60 45"` | Direct sunlight color | all |
| `sunlight` | `"255 243 171"` | Sunlight color variant used by two AA maps | aa |
| `sundirection` | `"320 150 0"` | Sun angles (pitch/yaw/roll degrees) | all |
| `sundiffuse` | `"1.3"` | Diffuse sky-bounce intensity | all |
| `sundiffusecolor` | `"85 85 85"` | Diffuse sky-bounce color | aa, bt/sh |
| `sunflare` / `sunflaredirection` | `"-7980 5388 3396"` | World position/direction of the visible sun flare | aa, bt/sh |
| `sunflarename` | `"none"` | Flare shader selection | aa, bt/sh |
| `overbright` | `"all"`, `"none"` | Lightmap overbright policy | aa |
| `farplane` | `"1500"`-`"7000"` | Distance-fog far plane and cull distance | all |
| `farplane_color` | `".25 .26 .28"` | Distance-fog color (0-1 floats) | all |
| `farplane_bias` | `"1000"`, `"-1000"` | Cull-distance bias relative to the fog plane | bt/sh |
| `farplane_cull` | `"0"`, `"1"`, `"2"` | Far-plane culling mode | bt/sh |
| `lightmapdensity` | `"16"`, `"32"`, `"64"`, `"128"` | Global lightmap texel density | aa, bt/sh |
| `northyaw` | `"270"`, `"37"` | Compass-north yaw for the HUD | aa, bt/sh |
| `map_time` | `"3986678584"` | Editor save timestamp; SH/BT exports only | bt/sh |
| `vis_derived` | `"0"`, `"1"` | Editor VIS-state cache flag | bt/sh |
| `_color`, `angle`, `scale`, `light`, `spawnflags`, `targetname`, `$targetname`, `sunangle` | various | Stray editor leftovers on worldspawn; harmless | aa, bt/sh |

## 4. Brush-side grammar

A brush is a convex solid described by its bounding planes, one line per
side:

```text
( x1 y1 z1 ) ( x2 y2 z2 ) ( x3 y3 z3 ) texture shiftX shiftY rotation scaleX scaleY contents surfaceFlags value [inline tokens]
```

Example (`aa/mohdm1.map`, brush 26):

```text
( 1632 2488 648 ) ( 1632 2504 648 ) ( 1280 2504 648 ) general_structure/plank_flat 60 46 0.00 0.500000 0.500000 0 16384 0 +surfaceparm detail
```

### 4.1 Plane and texture columns

- The three points define the plane; the visible face's normal follows the
  Quake winding rule (points in clockwise order viewed from outside the
  solid).
- `texture` is a shader path relative to `textures/` with no extension
  (`general_structure/plank_flat` means
  `textures/general_structure/plank_flat`, resolved through shader scripts
  first, then bare images).
- `shiftX shiftY rotation scaleX scaleY` are standard texture alignment.
  The retail sources use hand alignment throughout: arbitrary shifts,
  rotations, and negative scales for mirroring.

### 4.2 The three trailing integers

The columns are `contents surfaceFlags value` — the same bitfields the BSP
stores per shader. `value` is 0 on every side in the corpus. Decoded values
that actually occur:

**`contents` (observed):**

| Value | Decode | Where observed |
| ---: | --- | --- |
| `0` | none stored; compiler derives from the shader | most textured sides; all SH/BT sides |
| `8192` | `FENCE` (0x2000) | pass-through fence materials |
| `65536` | `PLAYERCLIP` | clips |
| `196608` | `PLAYERCLIP\|MONSTERCLIP` | `common/clip` |
| `204800` | `PLAYERCLIP\|MONSTERCLIP\|FENCE` | fence clips |
| `393216` | `MONSTERCLIP\|WEAPONCLIP` | `obj_pipeline` clips |
| `983040` | `PLAYERCLIP\|MONSTERCLIP\|WEAPONCLIP\|VEHICLECLIP` | `common/clipall` |
| `16777216` | `ORIGIN` (0x1000000) | `common/origin` in movers |
| `268435456` | `STRUCTURAL` (0x10000000) | `common/vis` leaf-group brushes |
| `536870912` | `TRANSLUCENT` (0x20000000) | `common/nodraw`, most helper sides |
| `536870944` | `TRANSLUCENT\|WATER` | water volumes |
| `805339136` | `STRUCTURAL\|TRANSLUCENT\|AREAPORTAL` | `common/areaportal` |

**`surfaceFlags` (observed):**

| Value | Decode | Where observed |
| ---: | --- | --- |
| `128` | `NODRAW` | `common/trigger` |
| `160` | `NODRAW\|NOMARKS` | caulk-class sides |
| `276` | `SKY\|NOIMPACT\|NOLIGHTMAP` | `sky/*` sides |
| `2176` | `NODRAW\|NONSOLID` | `common/origin` |
| `2192` | `NOIMPACT\|NODRAW\|NONSOLID` | `common/areaportal` |
| `2193` | `NODAMAGE\|NOIMPACT\|NODRAW\|NONSOLID` | `common/clip` |
| `2224` | `NOIMPACT\|NOMARKS\|NODRAW\|NONSOLID` | `common/nodraw` |
| `2448` | `NOIMPACT\|NODRAW\|NOLIGHTMAP\|NONSOLID` | `common/vis` |
| `16384` | `WOOD` | wood materials |
| `32768` | `METAL` | metal materials |
| `32928` | `METAL\|NODRAW\|NOMARKS` | `common/metalclip` |
| `131072` | `DIRT` | terrain borders |
| `524288` | `GRASS` | grass/terrain |
| `4194304` | `GLASS` | windows |
| `8388608` | `GRAVEL` | rubble |
| `33554944` | `FOLIAGE\|ALPHASHADOW` | bushes/hedges |
| `67108864` | `SNOW` | `mohdm5` winter surfaces |
| `134217888` | `CARPET\|NODRAW\|NOMARKS` | `common/carpetclip` |

The surface-type bits (`WOOD`, `METAL`, `GRASS`, ...) select footstep and
impact effects.

### 4.3 Stored flags are cache, not authority

The Spearhead/Breakthrough sources zero all three columns on every side and
still compile and play correctly, because Q3map re-reads `surfaceparm`
records from shader scripts at compile time. The retail AA values are what
MOHRadiant cached from the shaders it had loaded. A stored value cannot
override a shader — inline `+/-surfaceparm` tokens (below) are the
supported per-side override channel.

### 4.4 Detecting decompiled `.map` files

BSP-to-MAP decompiles must stay out of the reference corpus (they teach
machine idioms no mapper wrote). They are detectable by measurement; five
community files checked in 2026-07 (`Warehouse`, `dm_rockbound`,
`obj_canal`, `obj_rockbound`, `stlo`) all matched the decompile
fingerprint:

| Signal | Authored sources (measured) | Decompiles (measured) |
| --- | --- | --- |
| Sides with nonzero texture shift | 19-77% (MP retail/community) | 0.4-3.3% |
| Distinct scale pairs per map | 350-1,900 | exactly 2 |
| Plane points | real face windings (`( 1280 2560 32 ) ( 1312 2560 32 ) ...`) | canonical plane triples (`( X -16 16 ) ( X 0 0 ) ( X 16 16 )`) |
| Editor-only constructs (`func_group`, `vis_leafgroup`, `common/hint`) | routinely present | absent or trace |

Decompiles still carry intact entity lumps and measurable layout geometry,
but they lack the compiled-artifact data (lightmap pages, VIS, draw
surfaces) their parent BSP has — so the parent pk3/BSP is strictly more
useful and the decompile adds nothing beyond it.

Caveat on export lineages: only the AA MP sources and the community maps
show the full authored profile (66-77% nonzero shifts, hand flag values,
hints/groups/vis present). The SH/BT MP sources and all SP campaign
corpora measure much lower alignment (SH/BT MP: 1.9-8.2% shifts but
311-519 distinct scales, hint brushes in several maps, terrainDef
throughout; SP: 0.2-8.3% shifts but up to 818 scales, `vis_leafgroup`
entities present). Editor-only constructs prove these are authored
lineage, not decompiles — they would reopen and recompile — but they
passed through an export that zeroed the cached flag columns and lost or
canonicalized most shift alignment. Consequence: entity, brush, hint, and
terrain structure is trustworthy across the whole corpus; texture-
alignment idiom is trustworthy only in the AA MP and community sources.

### 4.5 Inline per-side tokens

After the three integers, sides may append token sequences:

| Token pattern | Occurrences | Meaning |
| --- | ---: | --- |
| `+surfaceparm detail` | ~1,400,000 | Marks the side's brush as detail (non-structural for BSP splitting). The single most common annotation in the corpus; nearly every dressed side carries it. |
| `+surfaceparm <name>` | various | Adds any shader surfaceparm per side: observed `weaponclip`, `playerclip`, `noimpact`, `nomarks`, `fence` |
| `-surfaceparm <name>` | ~120 | Removes a shader-declared surfaceparm per side: observed `-surfaceparm solid` on pass-through fence/foliage sides |
| `subdivisions <float>` | ~1,900 | Per-side curve/terrain subdivision override |
| `surfaceDensity <float>` | ~3,100 | Per-side lightmap sample density override (AA sources only; values 8-64 observed) |
| `surfaceColor <r> <g> <b>` | 54 | Per-side light tint (AA sources only) |

## 5. `patchDef2` (curved surfaces)

12,134 patches exist across the retail corpora. Grammar (from
`aa/mohdm1.map`):

```text
{
 patchDef2
 {
  general_industrial/ge_wires_para
  ( 3 3 536870912 -2147448784 0 )
  (
  ( ( 1405 2456 624 4.103734 -17.819874 ) ( 1405 2456 640 5.745227 -17.819874 ) ( 1405 2456 656 7.386721 -17.819874 ) )
  ...one row per control-point row...
  )
 }
}
```

- Header: texture, then `( width height contents surfaceFlags value )` —
  unlike Q3, MOHAA stores real flag values here. `-2147448784` decodes as
  `0x80008830` = `PATCH|METAL|NONSOLID|NOMARKS|NOIMPACT` (the sign comes
  from `SURF_PATCH` = 0x80000000 in a signed int).
- Control points are `( x y z s t )` with explicit texture coordinates —
  patches carry UVs per control point instead of the brush alignment
  columns.
- Retail uses patches for wires, arches, pipes, tarps, and terrain skirts.

## 6. `terrainDef` (retail editor terrain)

2,740 instances across the retail corpora — the MOHRadiant terrain
primitive. Readers of these sources hit it constantly (Ardennes alone has
250). Observed structure:

```text
{
 terrainDef
 {
  105 121 0                             <- header (grid identity/size, flags)
  -576.000000 -2368.000000 -725.000000  <- world origin of the grid
  {
   0 0 ( wilderness/m3l3grass_1rough 0 0 0.00 512 1 1 0 524288 0 )
   1 0 ( notexture 0 0 0.00 64 1 1 0 0 0 )
   ...one row per terrain quad: two flags, then a texture record
  }
  {
   206.000000 ( maxdetail ) ( maxdetail )
   130.000000 ( nodraw ) ( )
   0.000000 ( ) ( )
   ...one row per vertex: height plus two per-triangle keyword lists
  }
 }
}
```

- Quad rows reuse the side grammar's texture/flag fields (the `524288`
  above is `SURF_GRASS`); `notexture` quads are holes.
- Vertex rows carry a height offset from the grid origin plus optional
  per-triangle keywords — observed: `nodraw`, `maxdetail`.
- Q3map triangulates this into ordinary BSP surfaces at compile time. Its
  exact editor semantics are not documented anywhere in this repository's
  toolchain; treat it as readable reference geometry.

## 7. Entity vocabulary

### 7.1 Spawns

- `info_player_deathmatch` — FFA spawns; `info_player_allied` /
  `info_player_axis` — team spawns; `info_player_start` — SP/test start;
  `info_player_intermission` — spectator camera. Keys: `origin`, `angle`.
- Retail DM maps ship roughly 11-25 spawns per class; the objective maps
  skew heavily toward team spawns (obj_team3: 43 Allied / 59 Axis).

### 7.2 Lights and coronas

```text
{ "classname" "light"  "origin" "-648 576 88"  "_color" "0.988 0.886 0.737"  "light" "100" }
```

`light` (10,800+ instances across the retail corpora) with
`_color`/`light` (intensity) is the workhorse; `static_corona_*` entities
add visible glows at fixtures. The retail 60-lights-per-leaf runtime clamp
documented in the playbook is the budget that governs these.

### 7.3 Model props (`static_*`, `animate_*`, `addon_*`, `interactobject_*`)

```text
{ "classname" "static_natural_bush_regularbush"  "model" "static/bush_regularbush.tik"
  "origin" "267.20 684.00 84.00"  "angle" "0"  "scale" "2.20"  "testanim" "idle" }
```

The classname encodes the family; `model` points at the `.tik` asset. ~2,600
statics in AA sources, ~7,400 in BT. The families span vegetation, lamps,
furniture, obstacles (sandbags, hedgehogs, barbwire), vehicles, U-boat
fittings, and hand-placed clutter down to individual mugs and books.

### 7.4 Brush-tied function entities

- `func_group` — editor grouping only; compiled as world geometry.
- `detail` — 606 instances in AA sources: a classname that groups detail
  brushes (same effect as `+surfaceparm detail` sides inside `worldspawn`).
- `func_rotatingdoor` — interactive doors; keys `angle` (hinge direction),
  `time`, `wait`, `alwaysaway`, `spawnflags`; the door brush set includes a
  `common/origin` brush marking the hinge.
- `func_window`, `func_crate`, `func_barrel` — destructibles.
- `func_ladder` — climbable volume (`common/ladder` texture also occurs).
- `func_rain` — weather volume (`common/rain` texture).
- `func_fencepost` — Breakthrough fence-post helper (Ardennes).
- `trigger_use`, `trigger_multiple`, `trigger_multipleall`, `trigger_hurt`,
  `trigger_relay` — `common/trigger` brushes plus script hooks; `#type` and
  `targetname` keys observed (e.g. locked-door messages).

### 7.5 Scripting and AI plumbing

- `script_object` (brush), `script_model`, `script_origin` — geometry and
  points driven by the map's `.scr` logic; heavily used in objective maps
  (obj_team2: 25 script_objects animating the U-boat pen).
- `info_pathnode` — AI navigation nodes (750 across BT/SH; retail bots/AI
  need them).
- `info_splinepath` — camera/vehicle spline points (chained by
  `target`/`targetname`, `speed`, sometimes a `model` to fly, e.g.
  obj_team2's `vehicles/p47fly.tik`).
- `ai_*` / `addon_ai_*` — scripted AI spawner entities in SH/BT MP sources
  (TOW modes), with detailed behavior keys (`gun`, `accuracy`,
  `sound_awareness`, `type_attack`, ...).
- `turretweapon_*` — mounted guns; keys include `maxyawoffset`.
- `func_TOWObjective` — Spearhead/Breakthrough Tug-of-War objective marker:

```text
{ "classname" "func_TOWObjective"  "origin" "-4433 1639 292"
  "AlliesObjNum" "4"  "AxisObjNum" "2"  "ControlledBy" "1"
  "ObjectiveNBR" "2"  "$targetname" "Obj_artillerystrike"  "target" "t879" }
```

### 7.6 Visibility control

`vis_leafgroup` (443 in AA) — brush entities made of `common/vis`
(`STRUCTURAL` contents, `NOIMPACT|NODRAW|NOLIGHTMAP|NONSOLID` flags) that
partition space for the compiler's clustering; chained via
`targetname`/`target`.

### 7.7 Single-player-only vocabulary (reference)

The campaign sources add classes the MP corpus barely touches. None of
these are production targets here (MP-only policy); they are cataloged
because they pin down format semantics and show how the retail designers
budgeted hand-authored data:

- **`info_pathnode` at scale** — 52,607 instances across the SP corpora
  (26,432 in AA SP alone; `m4l3` has thousands by itself). Retail AI
  navigation is entirely hand-placed nodes; MP maps for OpenMoHAA bots need
  none of this because Recast builds navigation at load.
- **AI support points** — `info_waypoint` (3,102), `info_aispawnpoint`,
  `info_grenadehint` (grenade-throw targets), `info_vehiclepoint` /
  `trigger_vehicle` (vehicle routes), plus dense `ai_*` spawner entities
  whose keys (`gun`, `accuracy`, `sight`, `hearing`, `leash`,
  `disguise_*`) form the AI tuning surface.
- **Scripted-sequence plumbing** — thousands of `script_object` /
  `script_origin` / `script_model` instances, `trigger_once`, and
  `info_splinepath` chains for flyovers and vehicle runs.
- **SH/BT gameplay devices** — `ProjectileGenerator_*` (288: mortar/shell
  barrage volumes), `ThrobbingBox_*` (104: plantable-explosive interaction
  boxes), `item_*` pickups (ammo boxes, health) which also appear in two
  community MP maps.
- **Worldspawn extras** — SH campaign maps add `skybox_speed` /
  `skybox_farplane` and `overbright_range` beyond the MP key set.
- **Terrain density** — SP maps average hundreds of `terrainDef` grids per
  map (`e3l4`: 803, `t1l1`: 458, `m4l3`: 440); outdoor campaign spaces are
  terrain-first, brush-second. This is the corpus to read when pinning
  down `terrainDef` semantics experimentally.

## 8. Utility materials (`common/*`)

Usage across `aa/` + `aa_custom/`, most frequent first (BT/SH use the same
set):

| Material | Sides | Role |
| --- | ---: | --- |
| `common/caulk` | 64,290 | Invisible structural filler on unseen faces |
| `common/nodraw` | 40,539 | Invisible non-solid detail faces |
| `common/clip` | 3,645 | Player+monster collision |
| `common/playerclip` | 2,670 | Player-only collision |
| `common/vis` | 2,662 | VIS leaf-group volumes |
| `common/metalclip`, `carpetclip`, `dirtclip`, `stoneclip` | 2,300+ | Clips carrying footstep-material flags |
| `common/hint` | 1,752 | BSP split hints |
| `common/trigger` | 906 | Trigger volumes |
| `common/origin` | 846 | Mover rotation origin |
| `common/caulkshadow`, `caulksky` | 833 | Caulk variants that still cast shadow / seal sky |
| `common/clipall` | 450 | All-contents clip |
| `common/areaportal` | 330 | Area portals at door cuts |
| `common/ladder` | 102 | Climb volumes |
| `common/black`, `common/rain`, `common/bspindleclip` | <120 | Specials |

## 9. Reading order for a new map study

1. `worldspawn` keys — lighting/fog intent (section 3).
2. Spawn entities — mode support and player counts (section 7.1).
3. `common/*` usage — where the invisible engineering lives (section 8).
4. `vis_leafgroup` / `common/hint` — how the map controls VIS cost.
5. Statics and scripting entities — the dressing and mode logic budget.
6. `terrainDef`/`patchDef2` — where the organic and curved geometry is.

## 10. Appendix: per-file inventory

Counts parsed from the current files; brush counts exclude `patchDef2` and
`terrainDef` primitives, which are listed separately. Files that exist
identically in both `bt/` and `sh/` are listed once and marked.

| File | Entities | Brushes | patchDef2 | terrainDef | DM/Allied/Axis spawns | `message` |
| --- | ---: | ---: | ---: | ---: | :---: | --- |
| `aa/mohdm1.map` | 608 | 3,034 | 120 | 0 | 18/22/20 | South France |
| `aa/mohdm2.map` | 241 | 2,993 | 0 | 5 | 18/12/12 | Destroyed Village |
| `aa/mohdm3.map` | 849 | 3,299 | 86 | 8 | 11/13/12 | |
| `aa/mohdm5.map` | 548 | 1,300 | 17 | 1 | 13/17/17 | |
| `aa/mohdm6.map` | 636 | 2,325 | 68 | 2 | 25/25/25 | Stalingrad |
| `aa/mohdm7.map` | 1,009 | 5,556 | 534 | 1 | 18/18/18 | |
| `aa/obj_team1.map` | 372 | 2,450 | 137 | 5 | 0/18/18 | |
| `aa/obj_team2.map` | 752 | 5,827 | 708 | 7 | 14/16/16 | |
| `aa/obj_team3.map` | 842 | 3,379 | 102 | 1 | 0/43/59 | Omaha Beach |
| `aa/obj_team4.map` | 717 | 3,957 | 174 | 5 | 0/19/17 | |
| `aa_custom/obj_pipeline.map` | 670 | 2,970 | 288 | 1 | 39/18/19 | |
| `bt/MP_MonteBattaglia_TOW.map` | 596 | 3,737 | 218 | 40 | 16/17/16 | |
| `bt/mp_anzio_lib.map` | 1,349 | 7,068 | 688 | 71 | 19/24/32 | |
| `bt/mp_ardennes_tow.map` (= `sh/MP_Ardennes_TOW.map`) | 1,938 | 9,964 | 604 | 250 | 13/4/6 | |
| `bt/mp_bahnhof_dm.map` (= `sh/MP_Bahnhof_DM.map`) | 383 | 4,468 | 548 | 23 | 23/9/10 | |
| `bt/mp_bazaar_dm.map` (= `sh/MP_Bazaar_DM.map`) | 239 | 1,642 | 368 | 15 | 21/8/7 | |
| `bt/mp_berlin_tow.map` (= `sh/MP_Berlin_TOW.map`) | 1,426 | 6,901 | 311 | 0 | 17/8/8 | |
| `bt/mp_bizertefort_obj.map` | 614 | 4,905 | 648 | 4 | 16/8/8 | Bizerte |
| `bt/mp_bizerteharbor_lib.map` | 786 | 4,868 | 416 | 66 | 21/44/40 | |
| `bt/mp_bologna_obj.map` | 1,455 | 8,120 | 706 | 1 | 23/19/19 | Bologna |
| `bt/mp_brest_dm.map` (= `sh/MP_Brest_DM.map`) | 174 | 2,997 | 111 | 61 | 11/11/11 | The Bridge |
| `bt/mp_castello_obj.map` | 1,334 | 5,209 | 288 | 34 | 28/20/21 | Castello |
| `bt/mp_druckkammern_tow.map` (= `sh/MP_Druckkammern_TOW.map`) | 2,045 | 7,849 | 1,147 | 12 | 15/16/16 | |
| `bt/mp_flughafen_tow.map` (= `sh/MP_Flughafen_TOW.map`) | 1,287 | 6,868 | 1,101 | 384 | 12/7/7 | Flughafen |
| `bt/mp_gewitter_dm.map` (= `sh/MP_Gewitter_DM.map`) | 803 | 4,737 | 28 | 78 | 17/23/20 | |
| `bt/mp_holland_dm.map` (= `sh/MP_Holland_DM.map`) | 429 | 6,215 | 179 | 146 | 19/15/12 | |
| `bt/mp_kasserine_tow.map` | 725 | 6,237 | 530 | 228 | 31/23/20 | |
| `bt/mp_malta_dm.map` (= `sh/MP_Malta_DM.map`) | 1,208 | 5,632 | 325 | 50 | 15/8/8 | |
| `bt/mp_montecassino_tow.map` | 959 | 6,352 | 701 | 53 | 23/18/16 | Monte Cassino |
| `bt/mp_palermo_obj.map` | 551 | 4,039 | 122 | 22 | 35/16/16 | |
| `bt/mp_ship_lib.map` | 1,107 | 4,715 | 783 | 0 | 23/25/26 | Tunisia - Bizerte Harbor |
| `bt/mp_stadt_dm.map` (= `sh/MP_Stadt_DM.map`) | 427 | 4,026 | 280 | 9 | 23/12/12 | |
| `bt/mp_tunisia_lib.map` | 784 | 4,397 | 802 | 91 | 18/40/33 | Tunisian Desert |
| `bt/mp_unterseite_dm.map` (= `sh/MP_Unterseite_DM.map`) | 420 | 3,215 | 278 | 19 | 14/8/8 | |
| `bt/mp_verschneit_dm.map` (= `sh/MP_Verschneit_DM.map`) | 438 | 5,644 | 130 | 0 | 15/9/8 | |

### 10.1 Single-player campaign and community additions

Spawn columns are near-zero for SP maps by design (campaign maps use AI
spawners, not MP spawn classes).

| File | Entities | Brushes | patchDef2 | terrainDef | DM/Allied/Axis spawns | `message` |
| --- | ---: | ---: | ---: | ---: | :---: | --- |
| `aa/m1l1.map` | 1,099 | 2,782 | 615 | 18 | 0/0/0 | Rangers Lead the Way |
| `aa/m1l2a.map` | 2,738 | 5,781 | 556 | 146 | 0/0/0 | The Rescue Mission |
| `aa/m1l2b.map` | 1,601 | 3,935 | 327 | 8 | 0/0/0 | Sabotage the Motorpool |
| `aa/m1l3a.map` | 1,027 | 1,208 | 348 | 265 | 0/0/0 | Lighting the Torch - Desert Road |
| `aa/m1l3b.map` | 1,291 | 1,243 | 254 | 488 | 0/0/0 | Grounding the Airfield |
| `aa/m1l3c.map` | 1,226 | 3,772 | 437 | 0 | 0/0/0 | Lighting The Torch - Lighthouse |
| `aa/m2l1.map` | 2,178 | 5,524 | 570 | 0 | 0/0/0 | Secret Documents of the Kriegsmarine |
| `aa/m2l2a.map` | 1,825 | 5,656 | 707 | 0 | 0/0/0 | Scuttling the U-529 - Naxos Prototype |
| `aa/m2l2b.map` | 1,327 | 4,998 | 554 | 0 | 0/0/0 | Scuttling the U-529 - Inside the U-529 |
| `aa/m2l2c.map` | 1,484 | 3,828 | 488 | 0 | 0/0/0 | Scuttling the U-529 - Cover Blown |
| `aa/m2l3.map` | 1,338 | 5,714 | 921 | 0 | 0/0/0 | Escape from Trondheim |
| `aa/m3l1a.map` | 2,305 | 1,665 | 56 | 273 | 0/0/0 | Omaha Beach - The Landing |
| `aa/m3l1b.map` | 1,288 | 3,047 | 265 | 426 | 0/0/0 | Omaha Beach - Inside the Bunker |
| `aa/m3l2.map` | 2,827 | 4,681 | 536 | 165 | 0/0/0 | Battle in the Bocage |
| `aa/m3l3.map` | 4,078 | 4,834 | 435 | 391 | 0/0/0 | The Nebelwerfer Hunt |
| `aa/m4l0.map` | 1,662 | 2,654 | 133 | 591 | 0/0/0 |  |
| `aa/m4l1.map` | 1,312 | 5,020 | 1,543 | 8 | 0/0/0 | Rendezvous with the Resistance |
| `aa/m4l2.map` | 1,918 | 5,578 | 599 | 187 | 0/0/0 | Diverting the Enemy |
| `aa/m4l3.map` | 4,374 | 6,993 | 399 | 440 | 0/0/0 | The Command Post |
| `aa/m5l1a.map` | 1,038 | 3,684 | 69 | 161 | 0/0/0 | Sniper's Last Stand - Outskirts |
| `aa/m5l1b.map` | 2,391 | 6,506 | 171 | 212 | 0/0/0 | Sniper's Last Stand - City Hall |
| `aa/m5l2a.map` | 1,861 | 2,929 | 114 | 308 | 0/0/0 | The Hunt for the King Tiger - Destroyed Village |
| `aa/m5l2b.map` | 2,301 | 4,285 | 95 | 518 | 0/0/0 | The Hunt for the King Tiger - Country Road |
| `aa/m5l3.map` | 1,366 | 4,799 | 122 | 56 | 0/0/0 | The Bridge |
| `aa/m6l1a.map` | 3,156 | 9,166 | 36 | 460 | 0/0/0 | The Siegfried Forest - Flak Guns |
| `aa/m6l1b.map` | 2,515 | 7,380 | 93 | 388 | 0/0/0 | The Siegfried Forest - Bunker Hill |
| `aa/m6l1c.map` | 1,822 | 6,451 | 829 | 83 | 0/0/0 | Die Sturmgewehr |
| `aa/m6l2a.map` | 2,469 | 9,035 | 227 | 42 | 0/0/0 | The Communications Blackout |
| `aa/m6l2b.map` | 3,410 | 6,748 | 157 | 127 | 0/0/0 | The Schmerzen Express |
| `aa/m6l3a.map` | 1,629 | 5,503 | 860 | 80 | 0/0/0 | Storming Fort Schmerzen |
| `aa/m6l3b.map` | 872 | 4,660 | 797 | 0 | 0/0/0 | Storming Fort Schmerzen - Inner Facility |
| `aa/m6l3c.map` | 1,281 | 5,422 | 834 | 0 | 0/0/0 | Storming Fort Schmerzen - Final Run |
| `aa/m6l3d.map` | 343 | 2,195 | 610 | 0 | 0/0/0 | Storming Fort Schmerzen - Chemical Plant |
| `aa/m6l3e.map` | 414 | 1,844 | 54 | 51 | 0/0/0 | Storming Fort Schmerzen - Conclusion |
| `aa/training.map` | 439 | 1,870 | 788 | 80 | 0/0/0 | Training |
| `aa_custom/Tirtagaine-Kechtat_obj.map` | 330 | 1,921 | 0 | 0 | 10/16/16 |  |
| `aa_custom/complex_obj.map` | 407 | 3,155 | 111 | 0 | 17/16/16 |  |
| `aa_custom/obj_El_alamein_final.map` | 605 | 1,876 | 270 | 9 | 29/16/17 |  |
| `aa_custom/obj_moharg_team4.map` | 1,007 | 5,199 | 214 | 5 | 0/25/24 | Clave incorrecta! |
| `bt/e1l1.map` | 3,525 | 7,262 | 589 | 527 | 0/0/0 | Tunisia - Battle of Kasserine Pass I |
| `bt/e1l2.map` | 2,892 | 7,824 | 374 | 304 | 0/0/0 | Tunisia - Battle of Kasserine Pass II |
| `bt/e1l3.map` | 2,119 | 8,755 | 1,002 | 85 | 0/0/0 | Tunisia - Bizerte Canal |
| `bt/e1l4.map` | 3,607 | 12,578 | 1,108 | 119 | 0/0/0 | Tunisia - Bizerte Harbor |
| `bt/e2l1.map` | 2,314 | 4,042 | 361 | 514 | 0/0/0 | Sicily - Glider Landing |
| `bt/e2l2.map` | 3,477 | 7,589 | 603 | 635 | 0/0/0 | Sicily - The Airfield at Caltagirone |
| `bt/e2l3.map` | 3,497 | 7,278 | 554 | 613 | 0/0/0 | Sicily - Gela |
| `bt/e3l1.map` | 2,946 | 4,500 | 383 | 276 | 0/0/0 | Italy - Monte Cassino I |
| `bt/e3l2.map` | 2,583 | 7,494 | 583 | 172 | 0/0/0 | Italy - Monte Cassino II |
| `bt/e3l3.map` | 2,480 | 5,797 | 557 | 474 | 0/0/0 | Italy - Anzio |
| `bt/e3l4.map` | 5,492 | 8,886 | 726 | 803 | 0/0/0 | Italy - Monte Battaglia |
| `sh/t1l1.map` | 1,992 | 6,666 | 40 | 458 | 0/0/0 | Normandy |
| `sh/t1l2.map` | 2,203 | 5,951 | 176 | 469 | 0/0/0 | Normandy |
| `sh/t1l3.map` | 2,583 | 8,331 | 136 | 410 | 0/0/0 | Normandy |
| `sh/t2l1.map` | 4,072 | 10,725 | 874 | 601 | 0/0/0 | Bastogne |
| `sh/t2l2.map` | 2,025 | 9,904 | 1,039 | 582 | 0/0/0 | Bastogne |
| `sh/t2l3.map` | 2,051 | 4,635 | 96 | 462 | 0/0/0 | Bastogne |
| `sh/t2l4.map` | 4,663 | 10,908 | 249 | 564 | 0/0/0 | Bastogne |
| `sh/t3l1.map` | 2,855 | 6,982 | 1,028 | 0 | 0/0/0 | Berlin |
| `sh/t3l2.map` | 2,476 | 6,792 | 1,066 | 0 | 0/0/0 | Berlin |
| `aa_custom/obj_entre_pots.map` | 410 | 2,504 | 216 | 0 | 16/16/16 | |
| `aa_custom/obj_hrad_mpai.map` | 5,955 | 6,173 | 140 | 12 | 0/0/0 (AI-bot map: pathnode-driven) | |
| `aa_custom/obj_BaseUBoat_2.map` | 1,131 | 6,469 | 2,717 | 0 | 3/35/52 | |
| `aa_custom/obj_compound_dust.map` | 248 | 766 | 0 | 1 | 0/19/19 | Fnd The Switch To Open This Gate = In & Out |
| `aa_custom/obj_lager.map` | 353 | 1,810 | 0 | 0 | 1/16/11 | |
| `aa_custom/obj_mandrilux.map` | 803 | 3,780 | 182 | 0 | 0/20/21 | Mandrilux |
| `aa_custom/obj_st_floretes_3.map` | 449 | 2,488 | 41 | 4 | 0/36/36 | mew map |
| `aa_custom/obj_straphael.map` | 1,123 | 6,378 | 93 | 0 | 0/24/22 | |
