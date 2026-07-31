# MOHAA `.map` source format reference

This document is a measured reference for every `.map` source in this
repository: what the format's constructs mean, which conventions retail
Medal of Honor sources actually use, and exactly how this repository's
generators emit the format. All counts were produced by parsing the current
files programmatically; constructs are quoted from the corpus verbatim.
Numeric flag decodes come from the MOHAA SDK-compatible
`code/qcommon/surfaceflags.h` in the OpenMoHAA source tree.

Use this document when reading retail sources for reference, when writing or
modifying a generator, or when debugging a compile that rejects emitted
geometry. Normative production rules stay in
[`MAP-GENERATION-PLAYBOOK.md`](MAP-GENERATION-PLAYBOOK.md); this file is the
format-level ground truth those rules stand on.

## 1. Corpus inventory

| Corpus | Files | Entities | Brushes | Sides | `patchDef2` | `terrainDef` | Trailing flag columns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `aa/` (retail Allied Assault MP sources) | 10 | 6,574 | 34,120 | ~205,000 | 1,946 | 35 | Real numeric values |
| `aa_custom/` (community `obj_pipeline`) | 1 | 670 | 2,970 | ~20,000 | 288 | 1 | Real numeric values |
| `bt/` (Breakthrough MP sources) | 24 | 21,477 | 129,805 | ~1,000,000 | 11,312 | 1,657 | All zero |
| `sh/` (Spearhead MP sources) | 13 | 11,217 | 70,158 | ~545,000 | 5,410 | 1,047 | All zero |
| `generated/` (this repository's maps) | 6 | 1,111 | 33,787 | ~207,000 | 1,479 | 0 | Fixed per-material values |

Provenance notes:

- The retail sources arrived as an upload (`Add files via upload`) and match
  the officially released EA/2015 map-source drops for AA, Spearhead, and
  Breakthrough multiplayer maps.
- Every file in `sh/` is byte-identical to its same-named file in `bt/`
  (verified with `cmp` across all 13 pairs). `bt/` additionally contains the
  11 Breakthrough-only maps. Analysis of `bt/` therefore covers `sh/`
  entirely.
- The Spearhead/Breakthrough sources were exported with all per-side
  contents/surface-flag integers zeroed; the retail AA sources kept the
  compiled values. Both compile, which proves the compiler re-derives these
  flags from shader `surfaceparm` records and treats the stored integers as
  editor cache, not authority (see section 4.3).
- A complete per-file table is in the appendix (section 11).

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
  The compiler ignores them; the repository's generators emit the lowercase
  AA style.
- Brush-carrying entities (`worldspawn`, `func_*`, `trigger_*`,
  `script_object`, `vis_leafgroup`) contain brush/patch blocks; point
  entities (`light`, `info_*`, `static_*`, ...) contain only keys, with
  position in an `"origin" "X Y Z"` key.
- Brace depth must balance exactly; a generator bug that emits a literal
  `\n` two-character sequence instead of a newline surfaces as an unrelated
  "incomplete line" compiler error (proven during Nuke work; see the
  playbook's preflight rule).

## 3. `worldspawn` key reference

Keys observed across the corpus, with the corpora that use them:

| Key | Example values | Meaning | Seen in |
| --- | --- | --- | --- |
| `message` | `"South France"`, `"Codex Nuke"` | Map display name | all |
| `ambientlight` | `"7.5 7.5 7.5"`, `"12 14 18"` | Base ambient light color (RGB, 0-255 scale) | all |
| `ambient` | `"50"`, `"5 5 5"` | Alternate/additional ambient term (scalar or RGB) | aa, bt/sh |
| `suncolor` | `"65 60 45"` | Direct sunlight color | all |
| `sunlight` | `"255 243 171"` | Sunlight color variant used by two AA maps | aa |
| `sundirection` | `"320 150 0"` | Sun angles (pitch/yaw/roll degrees) | all |
| `sundiffuse` | `"1.3"` | Diffuse sky-bounce intensity | all |
| `sundiffusecolor` | `"70 79 94"` | Diffuse sky-bounce color | aa, bt/sh, generated |
| `sunflare` / `sunflaredirection` | `"-7980 5388 3396"` | World position/direction of the visible sun flare | aa, bt/sh |
| `sunflarename` | `"none"` | Flare shader selection | aa, bt/sh |
| `overbright` | `"all"`, `"none"` | Lightmap overbright policy | aa |
| `farplane` | `"1500"`-`"8000"` | Distance-fog far plane and cull distance | all |
| `farplane_color` | `".25 .26 .28"` | Distance-fog color (0-1 floats) | all |
| `farplane_bias` | `"1000"`, `"-1000"` | Cull-distance bias relative to the fog plane | bt/sh |
| `farplane_cull` | `"0"`, `"1"`, `"2"` | Far-plane culling mode | bt/sh |
| `lightmapdensity` | `"16"`, `"32"`, `"64"`, `"128"` | Global lightmap texel density | aa, bt/sh |
| `northyaw` | `"270"`, `"37"` | Compass-north yaw for the HUD | aa, bt/sh |
| `map_time` | `"3986678584"` | Editor save timestamp; SH/BT exports only | bt/sh |
| `vis_derived` | `"0"`, `"1"` | Editor VIS-state cache flag | bt/sh |
| `_color`, `angle`, `scale`, `light`, `spawnflags`, `targetname`, `$targetname`, `sunangle` | various | Stray editor leftovers on worldspawn; harmless | aa, bt/sh |

The repository's generators emit exactly: `message`, `ambientlight`,
`suncolor`, `sundirection`, `sundiffusecolor`, `sundiffuse`, `_color`,
`farplane`, `farplane_color` (plus Nuke's `sundiffuse` variant set). This is
the proven-sufficient subset for a DM map lit by MOHlight.

## 4. Brush-side grammar

A brush is a convex solid described by its bounding planes, one line per
side:

```text
( x1 y1 z1 ) ( x2 y2 z2 ) ( x3 y3 z3 ) texture shiftX shiftY rotation scaleX scaleY contents surfaceFlags value [inline tokens]
```

Retail example (`aa/mohdm1.map`, brush 26):

```text
( 1632 2488 648 ) ( 1632 2504 648 ) ( 1280 2504 648 ) general_structure/plank_flat 60 46 0.00 0.500000 0.500000 0 16384 0 +surfaceparm detail
```

Generated example (`generated/codex_nuke/.../codex_nuke.map`):

```text
( 728 -1404 -526 ) ( 728 -1404 -608 ) ( 728 -1340 -608 ) codex_nuke/corrugated_gray 0 0 0 0.5 0.5 0 32768 0 +surfaceparm detail
```

### 4.1 Plane and texture columns

- The three points define the plane; the visible face's normal follows the
  Quake winding rule (points in clockwise order viewed from outside the
  solid). Getting the winding backwards makes faces invisible from the
  playable side — the leading cause of "missing wall" defects in early
  conversions.
- `texture` is a shader path relative to `textures/` with no extension
  (`general_structure/plank_flat` means
  `textures/general_structure/plank_flat` resolved through shader scripts
  first, then bare images).
- `shiftX shiftY rotation scaleX scaleY` are standard texture alignment.
  Retail maps use hand alignment (arbitrary shifts, rotations, negative
  scales for mirroring). Every converter in this repository emits the fixed
  alignment `0 0 0 0.5 0.5` (half-scale doubles texel density of the 512px
  originals); `codex_arena01` uses `1 1`.

### 4.2 The three trailing integers

The columns are `contents surfaceFlags value` — the same bitfields the BSP
stores per shader. `value` is 0 on every one of the ~2,000,000 sides in the
corpus. Decoded values that actually occur:

**`contents` (observed):**

| Value | Decode | Where observed |
| ---: | --- | --- |
| `0` | none stored; compiler derives from the shader | almost all textured sides; all SH/BT sides |
| `8192` | `FENCE` (0x2000) | generated alpha materials (chainlink/foliage/glass) |
| `65536` | `PLAYERCLIP` | AA clips |
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
| `262176` | `GRILL\|NOMARKS` | metal grating |
| `524288` | `GRASS` | grass/terrain |
| `4194304` | `GLASS` | windows |
| `8388608` | `GRAVEL` | rubble |
| `33554944` | `FOLIAGE\|ALPHASHADOW` | bushes/hedges |
| `67108864` | `SNOW` | `mohdm5` winter surfaces |
| `134217888` | `CARPET\|NODRAW\|NOMARKS` | `common/carpetclip` |

The surface-type bits (`WOOD`, `METAL`, `GRASS`, ...) select footstep and
impact effects; the repository's generators set them deliberately per
original material (e.g. every `codex_nuke` metal family carries `32768`).

### 4.3 Stored flags are cache, not authority

The Spearhead/Breakthrough sources zero all three columns on every side and
still compile and play correctly, because Q3map re-reads `surfaceparm`
records from shader scripts at compile time. The retail AA values are what
MOHRadiant cached from the shaders it had loaded. Consequences proven in
this repository:

- an emitted side may carry `0 0 0` safely for any material whose shader
  declares the right surfaceparms;
- conversely, a stored value cannot override a shader — inline
  `+surfaceparm` tokens (below) are the supported override channel;
- generators still emit explicit values so that behavior does not depend on
  which shader files happen to be staged.

### 4.4 Inline per-side tokens

After the three integers, retail and generated sides append token
sequences:

| Token pattern | Occurrences | Meaning |
| --- | ---: | --- |
| `+surfaceparm detail` | ~1,580,000 | Marks the side's brush as detail (non-structural for BSP splitting). The single most common annotation in the corpus; nearly every dressed side carries it. |
| `+surfaceparm <name>` | various | Adds any shader surfaceparm per side: observed `weaponclip`, `playerclip`, `noimpact`, `nomarks`, `fence`, `nolightmap` (generated only) |
| `-surfaceparm <name>` | ~120 retail, ~26,000 generated | Removes a shader-declared surfaceparm per side: retail uses `-surfaceparm solid` on pass-through fence/foliage; the generators use it for every non-solid decoration family |
| `subdivisions <float>` | ~1,900 | Per-side curve/terrain subdivision override |
| `surfaceDensity <float>` | ~3,100 | Per-side lightmap sample density override (AA sources only; values 8-64 observed) |
| `surfaceColor <r> <g> <b>` | 54 | Per-side light tint (AA sources only) |

The repository's proven lighting-policy rules for `+surfaceparm nolightmap`
(alpha-detail only, exact-count gated, and always followed by the
constant-page relight before packaging) are in the playbook and in
`generated/codex_nuke/REVISION-5.md`.

## 5. `patchDef2` (curved surfaces)

13,613 patches exist across the corpus. Grammar (from `aa/mohdm1.map`):

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
  The generators use them for two jobs: rebuilt Source-displacement surfaces
  (dust2's full mode) and flat measured seam underlays beneath planarized
  terrain (cobblestone/cache/inferno/nuke; e.g. Nuke's 632 underlay
  patches).

## 6. `terrainDef` (retail editor terrain)

2,740 instances, exclusively in retail corpora — the MOHRadiant terrain
primitive. This repository's generators never emit it (planar underlays and
patches replaced it), but readers of retail sources will hit it constantly
(Ardennes alone has 250). Observed structure:

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
- Q3map triangulates this into ordinary BSP surfaces at compile time.
  Treat it as readable reference geometry, not as a target output format:
  its exact editor semantics are not documented anywhere in this
  repository's toolchain, and nothing here needs to write it.

## 7. Entity vocabulary

### 7.1 Spawns (all corpora)

- `info_player_deathmatch` — FFA spawns; `info_player_allied` /
  `info_player_axis` — team spawns; `info_player_start` — SP/test start;
  `info_player_intermission` — spectator camera. Keys: `origin`, `angle`.
- Retail DM maps ship roughly 11-25 spawns per class; the generated maps
  ship 16-67 DM plus 16-22 per team (converted from CS spawn sets).

### 7.2 Lights and coronas

```text
{ "classname" "light"  "origin" "-648 576 88"  "_color" "0.988 0.886 0.737"  "light" "100" }
```

`light` (10,000+ instances corpus-wide) with `_color`/`light` (intensity)
is the workhorse; `static_corona_*` entities add visible glows at fixtures.
The retail 60-lights-per-leaf runtime clamp documented in the playbook is
the budget that governs these.

### 7.3 Model props (`static_*`, `animate_*`, `addon_*`, `interactobject_*`)

```text
{ "classname" "static_natural_bush_regularbush"  "model" "static/bush_regularbush.tik"
  "origin" "267.20 684.00 84.00"  "angle" "0"  "scale" "2.20"  "testanim" "idle" }
```

The classname encodes the family; `model` points at the `.tik` asset. ~2,600
statics in AA sources, ~7,400 in BT. The generated maps use only the small
verified subset in `STOCK-AA-ASSET-CATALOG.md` (bushes, trees, rusted
vehicles, a wagon — 44 instances total); everything else is reconstructed
as brush geometry precisely because arbitrary `.tik` references cannot be
verified without staged retail data.

### 7.4 Brush-tied function entities

- `func_group` — editor grouping only; compiled as world geometry.
- `detail` — 606 instances in AA sources: a classname that groups detail
  brushes (same effect as `+surfaceparm detail` sides inside `worldspawn`).
- `func_rotatingdoor` — interactive doors; keys `angle` (hinge direction),
  `time`, `wait`, `alwaysaway`, `spawnflags`; the door brush set includes a
  `common/origin` brush marking the hinge. The generated maps' four-door
  Nuke set replicates exactly this pattern.
- `func_window`, `func_crate`, `func_barrel` — destructibles.
- `func_ladder` — climbable volume (`common/ladder` texture also occurs).
- `func_rain` — weather volume (`common/rain` texture).
- `trigger_use`, `trigger_multiple`, `trigger_multipleall`, `trigger_hurt`,
  `trigger_relay` — `common/trigger` brushes plus script hooks; `#type` and
  `targetname` keys observed (e.g. locked-door messages).

### 7.5 Scripting and AI plumbing (retail only)

- `script_object` (brush), `script_model`, `script_origin` — geometry and
  points driven by the map's `.scr` logic; heavily used in objective maps
  (obj_team2: 25 script_objects animating the U-boat pen).
- `info_pathnode` — AI navigation nodes (750 across BT/SH; retail bots/AI
  need them; OpenMoHAA bots use Recast instead, so generated maps ship
  none).
- `info_splinepath` — camera/vehicle spline points (chained by
  `target`/`targetname`, `speed`, sometimes a `model` to fly).
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
(`STRUCTURAL`, `NOLIGHTMAP|NODRAW|...`) that partition space for the
compiler's clustering; chained via `targetname`/`target`. The generated maps
rely on ordinary structural shells plus fast VIS instead.

## 8. Utility materials (`common/*`)

Corpus-wide usage, most frequent first:

| Material | AA+custom sides | Generated sides | Role |
| --- | ---: | ---: | --- |
| `common/caulk` | 64,290 | 13,453 | Invisible structural filler on unseen faces |
| `common/nodraw` | 40,539 | 0 | Invisible non-solid detail faces |
| `common/clip` | 3,645 | 2,344 | Player+monster collision |
| `common/playerclip` | 2,670 | 78 | Player-only collision |
| `common/vis` | 2,662 | 0 | VIS leaf-group volumes |
| `common/metalclip`, `carpetclip`, `dirtclip`, `stoneclip`, `grassclip` | 2,300+ | 0 | Clips carrying footstep-material flags |
| `common/hint` | 1,752 | 0 | BSP split hints |
| `common/trigger` | 906 | 0 | Trigger volumes |
| `common/origin` | 846 | 36 | Mover rotation origin |
| `common/caulkshadow`, `caulksky` | 833 | 0 | Caulk variants that still cast shadow / seal sky |
| `common/clipall` | 450 | 0 | All-contents clip |
| `common/areaportal` | 330 | 0 | Area portals at door cuts |
| `common/ladder` | 102 | 0 | Climb volumes |
| `common/black`, `common/rain`, `common/bspindleclip` | <120 | 0 | Specials |

The generated maps deliberately use only four of these (`caulk`, `clip`,
`playerclip`, `origin`); everything else in them is either real textured
geometry or a custom `codex_<map>/*` material with an explicit shader.

## 9. How this repository's `.map` files are made

### 9.1 Six maps, three construction modes

| Map | Source reference | Construction | Brushes / patches | Spawns (DM/A/X) |
| --- | --- | --- | ---: | :---: |
| `codex_arena01` | none | Hand-designed procedural gray-box, authored directly in JS (`generate_dm_map.js` emits primitives) | 35 / 0 | 16/8/8 |
| `codex_dust2_v2` | `de_dust2_reference.vmf` | Direct VMF conversion; displacement surfaces rebuilt as patches; facade panels; stock props | 2,330 / 296 | 40/20/20 |
| `codex_cobblestone` | `de_cbble_reference.vmf` | Direct conversion with `planar`/`full` displacement modes and placeholder-policy flags | 4,831 / 311 | 44/22/22 |
| `codex_cache` | `de_cache_d.vmf` | Direct conversion; three-axis filtering; compile-budget mode; original texture palette | 10,795 / 83 | 24/20/20 |
| `codex_inferno` | `de_inferno_d.vmf` | Five revisions: invented layout (rejected) → measured rebuild → direct conversion → prop layers driven by a measured model-bounds manifest | 6,972 / 157 | 67/20/20 |
| `codex_nuke` | `de_nuke_d.vmf` | Direct conversion plus a measured fidelity manifest (4,687 prop transforms) reconstructed as family-specific brushes | 8,824 / 632 | 32/16/16 |

Per-map details, revision history, and evidence live in each
`generated/<map>/README.md` and `REVISION-*.md`; the VMF references are
read locally by the tools and are never committed.

### 9.2 The shared converter architecture

Every VMF-based generator (`generate_<map>.js`, 1,200-2,500 lines each) is
a self-contained Node script with the same skeleton:

1. **Tokenizer/parser** for Valve's VMF key-value tree.
2. **Solid filter** — helper-material solids (`tools/tools*`) are skipped
   (recorded per material), skybox-cluster solids are excluded by measured
   coordinate bounds, and remaining solids are validated (≥4 sides, sane
   windings; invalid count must end at zero).
3. **Material mapping** — every Source material name maps to a target
   material record `{texture, contentFlags, surfaceFlags}` from a fixed
   table; unknown materials fall back to caulk/nodraw and are counted
   (`nodrawFallbackFaces`).
4. **Displacement policy** — `full` mode rebuilds Source displacements as
   patch grids plus skirts; `planar` mode (the proven default since
   Cobblestone) flattens them to planes and adds measured patch underlays
   at seams.
5. **Prop policy** — props convert only with positive evidence (measured
   bounds from studio headers, family templates); everything unproven is
   omitted and counted, never guessed (the Nuke rev-2 aggregate-fill
   failure is the case law).
6. **Entity emission** — spawn sets converted from CS spawn points, light
   clustering (Source fixture candidates deduplicated per cell, e.g. Nuke
   471→259), doors as `func_rotatingdoor` with origin brushes.
7. **Deterministic output** — `main/maps/dm/<map>.map` plus a JSON
   conversion report with every counter; a separate validator script
   re-reads both and gates exact counts.

Emission conventions shared by all of them:

- side line template: `<plane> <texture> 0 0 0 0.5 0.5 <contents> <surfaceFlags> 0`
  with ` +surfaceparm detail` on every non-structural side;
- ` -surfaceparm solid` on non-solid decoration families,
  ` +surfaceparm nolightmap` only under the playbook's alpha-detail policy;
- coordinates rounded to at most 4 decimals (`Number(v.toFixed(4))`);
- entity vocabulary restricted to `worldspawn`, `light`, the four spawn
  classes, `func_rotatingdoor`, and cataloged `static_*` props.

### 9.3 From `.map` to playable PK3

Every generated map ships the same runtime file set:

```text
main/maps/dm/<map>.map              editable source (committed)
main/maps/dm/<map>.bsp              compiled artifact (committed)
main/maps/dm/<map>.scr              match script: g_obj_* text cvars,
                                    DMprecache exec, level.script binding
main/maps/dm/<map>_precache.scr     precache exec
main/scripts/<map>.shader           custom shaders (where alpha/nolightmap
                                    materials exist: cache, nuke)
main/textures/<map>/*.tga           original 512x512 palette
<map>.pk3                           zip of all of the above
```

The compile chain (MOHTools 1.48 `Q3map.exe`/`MOHlight.exe` against a
staged retail tree, documented per map):

```text
generate → validate → Q3map BSP → Q3map -vis -fast
        → [map-specific BSP post-passes, e.g. Nuke's atlas repack]
        → MOHlight → inspect → [Nuke: relight unlit surfaces → inspect]
        → package pk3 → isolated OpenMoHAA load + Recast + bot QA
```

Stage-by-stage failure interpretation and the hard budgets
(`MAX_MAP_LIGHTING` 180 lightmap pages, 60 lights/leaf,
`MAX_MAP_DRAWINDEXES`) are in the playbook's Phase 6.

## 10. Invariants for anything that writes `.map` files

Distilled from the corpus and this repository's compile history:

1. Entity 0 is `worldspawn`; brace depth balances; real newlines only.
2. Every brush is convex, ≥4 sides, with outward-facing plane windings.
3. Texture paths have no `textures/` prefix and no extension; every custom
   path must resolve to a committed shader or TGA (validators enforce
   this; Q3map continues past `Couldn't find image` and bakes wrong UV
   scale — treat that warning as a failed build).
4. The three trailing integers may be zero, but whatever is emitted must
   agree with the shader's surfaceparms; use `+/-surfaceparm` tokens for
   per-side intent, and pair every `+surfaceparm nolightmap` side with the
   post-light constant-page relight before packaging.
5. Structural shell first, `+surfaceparm detail` on dressing; do not hide
   geometry problems with clips or broad lighting overrides.
6. Spawn set: 16+ per used class, placed on walkable floor. DM maps need
   `info_player_deathmatch` and both team classes for DM/TDM.
7. Doors: brush entity + `common/origin` hinge brush + `angle`/`time`/
   `wait` keys.
8. Emit deterministically (stable ordering, fixed rounding) so diffs and
   hashes stay reviewable, and write a machine-checkable conversion report
   next to the map.

## 11. Appendix: per-file inventory

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
| `generated/codex_arena01/.../codex_arena01.map` | 43 | 35 | 0 | 0 | 16/8/8 | Codex Arena 01 |
| `generated/codex_dust2_v2/.../codex_dust2_v2.map` | 120 | 2,330 | 296 | 0 | 40/20/20 | Codex Dust II - V2 Facility |
| `generated/codex_cobblestone/.../codex_cobblestone.map` | 186 | 4,831 | 311 | 0 | 44/22/22 | Codex Cobblestone |
| `generated/codex_cache/.../codex_cache.map` | 268 | 10,795 | 83 | 0 | 24/20/20 | Codex Cache |
| `generated/codex_inferno/.../codex_inferno.map` | 165 | 6,972 | 157 | 0 | 67/20/20 | Codex Inferno |
| `generated/codex_nuke/.../codex_nuke.map` | 329 | 8,824 | 632 | 0 | 32/16/16 | Codex Nuke |
