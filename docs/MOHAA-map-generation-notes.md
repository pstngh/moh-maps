# MOHAA/OpenMoHAA map-generation research log

Status: chronological evidence and case studies

Last updated: 2026-07-26

The normative workflow is
[`MAP-GENERATION-PLAYBOOK.md`](MAP-GENERATION-PLAYBOOK.md). Start at
[`docs/README.md`](README.md) when beginning new map work.

## Maintenance rule

This file preserves experiments, measurements, compiler behavior, runtime
results, visual defects, fixes, and map-specific case studies. Every material
map iteration must add its evidence here.

Confirmed reusable rules must also be promoted into the playbook. Current
map-specific status belongs in `generated/<map>/README.md`, verified asset
behavior belongs in `STOCK-AA-ASSET-CATALOG.md`, and repeatable revision data
should follow `templates/MAP-REVISION-REPORT.md`.

Historical results remain even when a later revision supersedes them. This is
intentional: failed approaches are evidence that prevents repeated mistakes.

## Research-log index

- Format and toolchain fundamentals: text map grammar, BSP/runtime format,
  compiler recipe, entities, scripts, packaging, and bot navigation.
- Original prototype: `codex_arena01` specification and first in-engine result.
- Dust II case study: source conversion, displacements, props, façades,
  collision, regression repair, and ten revisions.
- Lighting study: stock AA corpus, Monte Cassino reference, and the final
  warm-direct/cool-fill Dust profile.
- Cobblestone case study: source selection, displacement parsing, structural
  sky shell, portal limits, detail restoration, and modular architecture.
- Revision log: compact chronological summary at the end of this file.

## Goal and current result

The immediate target is a compiled Medal of Honor: Allied Assault deathmatch
map that also plays under OpenMoHAA and is easy for its bots to navigate.

That target is now technically proven. `codex_arena01` was generated as text,
compiled with the original Allied Assault Q3map/VIS/MOHlight tools, loaded by
OpenMoHAA 0.82.1, and accepted by OpenMoHAA's automatic Recast navigation
builder.

That path has now produced both an original gray-box arena and a much larger
Dust II brush-layout study using stock Allied Assault materials and props.

## Sources inspected

| Source | Revision inspected | What it contributed |
| --- | --- | --- |
| [pstngh/moh-maps](https://github.com/pstngh/moh-maps) | `7e336eb37814b52417c91d700138a305c020bb4c` | Stock AA, Spearhead, and Breakthrough `.map` source corpus |
| [openmoh/openmohaa](https://github.com/openmoh/openmohaa) | `a2f340195975f4f042e28a60b62561dd9a0b2700` | BSP constants/loader, map-tool parser, scripts, runtime, and bot navigation |
| [pstngh/netradiant-custom](https://github.com/pstngh/netradiant-custom) | `10165e88d118c97c4cd430e396f27fa759ac8b9f` | Modern Radiant editor and generic Q3map2 brush/patch implementation |
| [pstngh/MOHTools](https://github.com/pstngh/MOHTools) | `dd050da3d5981a53e904b67f079255e762ac0e94` | MoHRadiant, the actual AA compilers, stock AA sources, and EA multiplayer templates |

The NetRadiant source is useful for understanding how a Radiant-family editor
represents and manipulates convex brushes and patches. Its Q3map2 game list
does not currently include a MoHAA profile, so it is not a drop-in replacement
for the MoHAA compiler. MOHTools was the missing practical bridge.

## End-to-end mental model

```text
Radiant or generator
        |
        v
text .map + scripts + source art
        |
        | Q3map BSP stage
        v
.bsp + .prt + .vis helper
        |
        | Q3map -vis
        v
visibility data
        |
        | MOHlight
        v
lit AA BSP (visibility/lightmaps/lightgrid embedded)
        |
        | ZIP with .pk3 extension
        v
main/maps/dm/<name>.bsp
main/maps/dm/<name>.scr
main/maps/dm/<name>_precache.scr
textures/scripts/models used by the map
        |
        v
MoHAA/OpenMoHAA runtime
        |
        v
OpenMoHAA generates Recast navigation for custom maps at load time
```

The `.map` is editable source. The `.bsp` is the playable compiled level.
The sidecar `.prt` and `.vis` files are build artifacts and do not belong in
the runtime `.pk3`.

## Text `.map` grammar

### Entities

A map is a sequence of top-level entity blocks. The first entity is
`worldspawn`; it owns the static world brushes, patches, and terrain.

```text
{
"classname" "worldspawn"
"message" "Example"
"ambientlight" "18 18 20"
{
    ...brush faces...
}
}
{
"classname" "info_player_deathmatch"
"origin" "256 128 32"
"angle" "180"
}
```

Entity properties are quoted string pairs. Point entities usually need a
`classname` and `origin`; many also use `angle`, `target`, `targetname`,
`spawnflags`, or class-specific values.

### Convex brushes

A normal brush is a nested block of plane definitions. One face line has:

```text
( p1x p1y p1z ) ( p2x p2y p2z ) ( p3x p3y p3z )
texture/name shiftX shiftY rotation scaleX scaleY content surface value
```

Whitespace/newlines are flexible. The three points define an oriented plane;
point order selects the solid half-space. A valid brush is the convex
intersection of all its planes. Reversing a face can turn the solid inside out,
so generator code should use tested face-winding helpers rather than improvised
point order.

MoHAA maps can append per-face extensions such as:

```text
surfaceColor r g b
+surfaceparm name
-surfaceparm name
subdivisions n
surfaceDensity n
```

The final three numeric fields and these extensions affect contents, surface
behavior, tessellation, and lighting. Plain `0 0 0` faces are sufficient for
ordinary solid gray-box geometry.

### Patches

Curved surfaces use a `patchDef2` block. It identifies a texture, dimensions,
and a rectangular control-point grid. Each control point contains world
coordinates and texture coordinates:

```text
{
patchDef2
{
texture/name
( width height 0 0 0 )
(
    ( ( x y z s t ) ... )
    ...
)
}
}
```

Patches are useful for arches, pipes, trims, and smooth curved façades, but
collision and bot movement usually need separate simple brushwork.

### Terrain

MoHAA's `terrainDef` is a game-specific height/texture cell structure rather
than merely another brush. It is common in outdoor SH/BT work and present in
several AA maps. The old `ommap` source in OpenMoHAA explicitly skips
`terrainDef`: its comment says the MoHAA syntax is incompatible with the
inherited Q3map terrain parser. This is a strong reason to use the original
Q3map/MOHlight tools for compatibility.

Terrain is not necessary for the first generation system. Reliable convex
brushes are enough for indoor arenas, courtyards, streets, stairs, ramps, and
most cover.

## Multiplayer entities and scripts

The EA multiplayer notes shipped in MOHTools establish the minimum:

- `info_player_deathmatch` is used by free-for-all deathmatch.
- `info_player_allied` and `info_player_axis` are required for team modes.
- `info_player_start` is the spectator/team-selection start.
- DM/TDM files belong under `maps/dm`; objective files belong under `maps/obj`.
- The map needs a same-named `.scr` and `<name>_precache.scr`.
- A basic multiplayer precache script executes `global/DMprecache.scr`.

For a reusable simple DM generator I include all three multiplayer spawn
classes. This makes the same geometry usable in free-for-all and team modes.
Spawn origins must be above the floor, clear of solids, separated from cover,
and preferably aimed toward useful space.

A minimal map script is:

```text
main:

setcvar "g_obj_alliedtext1" "Map title"
setcvar "g_obj_alliedtext2" ""
setcvar "g_obj_alliedtext3" ""
setcvar "g_obj_axistext1" ""
setcvar "g_obj_axistext2" ""
setcvar "g_obj_axistext3" ""

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/example.scr
level waittill spawn

end
```

and the precache file is:

```text
exec global/DMprecache.scr
```

The stock game supplies `global/DMprecache.scr`, player models, state files,
weapons, sounds, and other standard runtime data.

## What the stock corpus shows

Counts below come from a structural parser written during this study. They are
useful as scale references, not quality targets.

| Game | Map | Entities | Brushes | Faces | Patches | Terrains | DM / Allied / Axis spawns | Lights |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| AA | `mohdm1` | 608 | 3,034 | 18,179 | 120 | 0 | 18 / 22 / 20 | 156 |
| AA | `mohdm2` | 241 | 2,993 | 17,513 | 0 | 5 | 18 / 12 / 12 | 60 |
| AA | `mohdm6` | 636 | 2,325 | 13,957 | 68 | 2 | 25 / 25 / 25 | 293 |
| AA | `mohdm7` | 1,009 | 5,556 | 33,225 | 534 | 1 | 18 / 18 / 18 | 463 |
| SH | `MP_Bazaar_DM` | 239 | 1,642 | 12,323 | 368 | 15 | 21 / 8 / 7 | 61 |
| SH | `MP_Gewitter_DM` | 803 | 4,737 | 37,070 | 28 | 78 | 17 / 23 / 20 | 259 |
| SH | `MP_Holland_DM` | 429 | 6,215 | 48,093 | 179 | 146 | 19 / 15 / 12 | 0 |
| BT | `mp_brest_dm` | 174 | 2,997 | 23,132 | 111 | 61 | 11 / 11 / 11 | 26 |
| BT | `mp_stadt_dm` | 427 | 4,026 | 31,298 | 280 | 9 | 23 / 12 / 12 | 57 |
| BT | `mp_verschneit_dm` | 438 | 5,644 | 40,486 | 130 | 0 | 15 / 9 / 8 | 197 |

Practical observations:

- Stock maps commonly provide roughly 11–25 neutral DM spawns.
- Team-spawn counts do not have to equal neutral-spawn counts.
- AA already uses brushes, patches, and terrain; the expansions lean heavily
  into large patch and terrain counts but do not introduce a wholly different
  authoring language.
- `common/caulk` and `common/nodraw` are heavily used to suppress invisible
  faces. Expansion maps also make extensive use of dedicated player/metal/wood
  clipping materials.
- Some SH maps in the BT source corpus are byte-identical, useful evidence
  that the basic source representation remains shared.

## Reusing the `obj_team2` stock palette

The preferred visual direction for the next AA map is the V2
industrial/bunker material family used by `obj_team2`. A custom map can
reference these stock shader names directly; the texture images and shader
scripts remain in the player's retail AA PK3s and do not need to be copied into
the custom map package.

Useful visible materials include:

| Purpose | Stock material candidates |
| --- | --- |
| Bunker walls | `general_structure/bunker_wall`, `normandy/bunker_conc3` |
| Concrete | `general_structure/jh_conc512b`, `mohcommon/jeff-concrete-walla`, `mohcommon/jeff-concrete-wallb` |
| Solid floors/steps | `algiers/whsflrset1_1b`, `algiers/doccrtset_1stepsml` |
| Metal deck/grates | `general_industrial/deckgrate_set1a`, `general_industrial/deckgrate_set1b` |
| Ceiling | `normandy/bunk_ceiling` |
| Iron panels | `das_boot/ironwall1`, `german/rusty_iron` |
| Structural trim | `general_structure/beam_wood1`, `mohcommon/ibeam_1a`, `general_industrial/verticalbrace` |
| Utility detail | `general_industrial/utilitybox_side`, `general_industrial/utilitybox_front`, `general_industrial/utilboxtop` |

Invisible brush faces should use `common/caulk`; purpose-built collision can
use `common/clip`, `common/playerclip`, `common/metalclip`, or
`common/stoneclip` as appropriate. This both matches stock construction
practice and avoids rendering hidden surfaces.

`obj_team2` also uses stock `static//lightbulb_caged.tik` lamps,
`static//corona_orange.tik` coronas, warm `_color "1.0 0.9 0.8"` lights, and
substantial explicit light placement. Those stock models can be referenced
without bundling them, but the light entities still need to be compiled into
the map. The next generator revision should support per-face materials so
grates, walls, floors, ceilings, and hidden sides are assigned deliberately
rather than applying one texture to every side of a box.

## AA BSP/runtime format

OpenMoHAA's `qfiles.h` records:

- little-endian BSP identifier `2015`;
- AA BSP version `19`;
- supported historical range `17` through `21`, with `21` labeled
  Breakthrough;
- 28 named BSP lumps;
- 128×128 lightmaps;
- major limits such as 32,768 brushes, 131,072 draw surfaces, and 524,288
  draw vertices.

The generated BSP begins:

```text
32 30 31 35 13 00 00 00 ...
```

That is ASCII `2015` followed by little-endian version `19`.

Important lumps include shaders, planes, lightmaps, surfaces, draw vertices and
indices, leaves/nodes, brush sides/brushes, models, entities, visibility,
lightgrid data, sphere lights, terrain, and static models.

## Compiler recipe

For `gameRoot\main\maps\dm\example.map`:

```powershell
Q3map.exe -gamedir "gameRoot" -moddir main "gameRoot\main\maps\dm\example.map"
Q3map.exe -vis -fast -gamedir "gameRoot" -moddir main "gameRoot\main\maps\dm\example.map"
MOHlight.exe -gamedir "gameRoot" -moddir main "gameRoot\main\maps\dm\example.map"
```

The first stage creates the BSP tree and portal data. The second calculates
potential visibility. MOHlight writes lightmaps, grids, and entity lighting
back into the BSP. `-fast` is useful for light-preview iterations; the
distributed prototype uses the full light pass.

Compiler warnings must be interpreted by stage:

- A leak means the playable void is connected to the outside; fix it before
  relying on VIS or lighting.
- Invalid or degenerate brushes indicate generator geometry/winding bugs.
- Missing textures can still compile but will render incorrectly.
- Complexity limits should be monitored with the compiler's info output.

The official compiler reported the prototype at about 0.25 MB, comfortably
under its 10 MB guidance.

## OpenMoHAA bots and navigation

OpenMoHAA 0.82.x generates Recast navigation for custom maps at runtime.
Legacy navigation files cover stock maps and can be selected with
`g_navigation_legacy 1`, but generated custom maps do not need a hand-authored
legacy nav file.

Geometry still determines whether the resulting mesh is useful. A bot-focused
generator should favor:

- broad stairs/ramps and landings;
- simple convex floors;
- adequate headroom and lane width;
- cover that does not form one-way pockets;
- no thin sliver brushes;
- connected circulation routes;
- spawn clearance from walls and obstacles.

The prototype uses four 224-unit-wide stairways, 24-unit rises, open lanes, and
simple rectangular cover. The headless runtime log reached:

```text
CM_LoadMap( maps/dm/codex_arena01.bsp, 0 )
Server Initialization Complete
Building the navigation mesh...
Recast navigation mesh(es) generated in 0.084 seconds
```

The isolated test server then attempted to add bots and stopped on missing
retail `american_army` model/state assets. That is expected because the test
directory intentionally contained OpenMoHAA plus this map, not the copyrighted
retail PK3s. It proved map loading and navigation generation independently of
the later full-data playtest.

## Prototype specification and validation

`codex_arena01` contains:

- a sealed 2,560×2,560×512-unit indoor arena;
- 35 static world brushes and 210 source faces;
- a 96-unit central platform with four broad stairways;
- 12 low cover elements forming two circulating lanes;
- 16 neutral, 8 Allied, and 8 Axis spawns;
- one spectator start;
- nine warm point lights plus low ambient light;
- four original procedural 128×128 TGA textures;
- no retail map geometry, textures, models, or sounds.

Verified results:

- BSP, VIS, and full MOHlight stages completed successfully.
- No leak, invalid-plane, or degenerate-brush error was reported.
- Final BSP size: 273,332 bytes.
- Final BSP SHA-256:
  `2201CECC40796973B84B75C56F443C46305DC7480411FEB8C889A0886BCA83ED`.
- OpenMoHAA 0.82.1 loaded the map and generated Recast navigation.
- A second clean test loaded the map and scripts from the seven-file `.pk3`
  alone, with no loose map copy masking packaging errors.
- A user playtest with the full game data rendered the arena and showed a bot
  walking through it, confirming installed-PK3 loading, textures, spawning, and
  practical navigation.

### First in-game visual result

![Codex Arena 01 running with a bot](codex_arena01-ingame.png)

The geometry reads as intended: the central platform, four stairs, perimeter
cover, and circulating floor lanes are all present. The procedural checker
textures are rendering rather than falling back to a missing-texture material.

The main issue is illumination. Ambient `18 18 20`, nine lights at intensity
`500`, dark source textures, and a broad enclosed room produce insufficient
contrast. The next gray-box pass should raise ambient light, strengthen and
lower the point lights, and brighten the base materials. The ceiling also
occupies a large dark band at the top of the view, so raising it or giving it
brighter surface treatment would improve spatial readability.

## Packaging

A `.pk3` is a ZIP archive with a different extension. The prototype contains:

```text
maps/dm/codex_arena01.bsp
maps/dm/codex_arena01.scr
maps/dm/codex_arena01_precache.scr
textures/codex/floor.tga
textures/codex/wall.tga
textures/codex/trim.tga
textures/codex/ceiling.tga
```

ZIP entry names should use forward slashes even when the archive is built on
Windows. The supplied build script writes the archive through the .NET ZIP API
instead of PowerShell's `Compress-Archive`, whose Windows entry names use
backslashes.

Install it in the game's `main` folder and launch:

```text
g_gametype 1
map dm/codex_arena01
```

For OpenMoHAA bots:

```text
sv_maxbots 8
sv_numbots 4
map dm/codex_arena01
```

## Compatibility and licensing boundaries

The prototype is compiled as an AA version-19 BSP and uses only basic AA
entity/script conventions. It should therefore be the safest common target for
original AA and OpenMoHAA.

The original EA AA executable was not available in the isolated validation
directory, so that binary was not launched. Original-AA compatibility is based
on the original AA compiler and version-19 format; OpenMoHAA was directly
runtime-tested.

The official EA tools are licensed for use with Medal of Honor: Allied Assault
and are not redistributed in the deliverables. The stock `.map` corpus was used
as format/reference material. Original EA map geometry and art should not be
copied into generated maps without a clear right to redistribute them.

The prototype's map geometry, generator, and procedural textures are newly
created. The retail game remains necessary for its standard multiplayer
scripts and game assets.

## What remains before calling the prototype polished

1. Walk every spawn and stair; look for snagging, z-fighting, texture
   stretching, excessive darkness, and sightline problems.
2. Run several bot counts and watch for navigation stalls or dominant loops.
3. Correct the underlighting and reevaluate player/cover silhouette contrast.
4. Adjust cover and spawn visibility based on combat behavior.
5. Add a theme, richer materials, soundscape, loading image, and scoreboard art
   only after the gray-box plays well.

## Dust II to V2 translation study

The second generated map tests whether the pipeline can preserve a documented
layout rather than inventing a small arena. Dust II was selected because its
route structure is recognizable, its scale is suitable for multiplayer bots,
and an editor-format VMF could be parsed as a geometric measurement source.

The reference contained 973 world solids and 1,093 entities. Including entity
brushes, it represented 2,281 solids, 14,462 sides, 69 displacement-bearing
sides, 20 Terrorist starts, and 20 Counter-Terrorist starts. The converter:

- preserved the original brush planes for the playable world and detail solids;
- skipped editor-only clips, hints, triggers, areaportals, and helper volumes;
- removed the distant Source 3D skybox;
- replaced Source displacements and selected prop cover with simple brushes;
- mapped every material to a stock MoHAA texture family;
- translated the Source sky shell to AA's real `sky/mohday1` shader;
- emitted 20 Axis, 20 Allied, and 40 neutral DM spawn entities;
- retained useful point lights and added evenly distributed fill lighting.

The corrected AA map contains 2,294 world brushes and 165 entities. Q3map
produced a version-19 BSP, fast VIS processed 599 clusters and 1,913 portals,
and MOHlight lit 38 stock static models. OpenMoHAA loaded the packaged map,
generated its Recast navigation mesh, and accepted two bots into the battle in
a full-data server smoke test.

This is a measured brush-layout translation, not a byte-identical CS2 port.
Source and Allied Assault use different BSP capabilities, collision behavior,
props, displacements, lighting, and player movement. The current CS2 release
also distributes a compiled `de_dust2.vmap_c`, not the editable source VMF used
by this experiment. The source VMF and all Valve art assets are excluded from
the deliverables. The playable package contains only the compiled MoHAA BSP and
scripts and uses stock MoHAA materials/models at runtime.

### Visual-correctness repair after the first playtest

The first Dust II package passed structural compile, load, and navigation tests
but failed visually. A user screenshot showed a black sky, large black voids,
and architecture that appeared to float.

The root cause was the compile environment rather than absent source brushes.
The BSP had been built against an isolated staging root without the retail
`Pak0.pk3` shader scripts. Q3map therefore gave named materials default flags:
`common/caulk` was not treated like stock caulk and the sky substitute was not
a sky shader. At runtime, hidden-face treatment and the sky no longer agreed
with what the compiler had encoded, exposing black gaps even though the
corresponding Source sky shell and brush geometry were present.

Correct production rule:

1. Generate source anywhere convenient.
2. Run Q3map, VIS, and MOHlight with `-gamedir` pointing to a real retail AA
   installation containing its normal `main/Pak0.pk3` data.
3. Package only the generated BSP and scripts; do not redistribute retail PK3s.

The repair also:

- maps Source sky directly to `sky/mohday1`;
- gives exposed Source nodraw faces a visible stock masonry fallback when they
  belong to an otherwise visible brush;
- reserves `common/caulk` for faces and collision brushes that are genuinely
  safe to hide;
- restores recognizable silhouette detail with 163 generated decor brushes;
- substitutes 38 stock AA props: eight palms, six rusted cars, one wagon, and
  scaled buckets/cans;
- lowers and strengthens fill lighting while retaining warm V2-style color;
- narrows prop matching so car parts do not become whole cars and milk cartons
  do not become full-size buckets.

The final compile reported no leak or invalid-brush error. An in-engine
live-player screenshot confirmed a rendered sky, continuous floors and walls,
lit routes, stock vehicles, cover, and architectural detail. The dark
triangular region seen from the first repaired spectator camera was verified
from a player spawn to be a lower route in perspective, not a missing surface.

### Second Dust II playtest: displacement and prop-origin defects

A six-screenshot bot playtest exposed defects that the initial spawn-area
visual check did not cover:

- crates and rusted cars floated above their intended floors;
- all eight substituted palms were suspended above the skyline;
- a group of large layered slabs blocked a route;
- several ground areas showed overlapping triangular strips and z-fighting;
- isolated black floor gaps remained near displaced terrain;
- rectangular masonry patches appeared where hidden Source faces should be.

The VMF analysis confirmed 68 retained world solids with displacement faces.
Copying those solids as ordinary AA brushes exposes the displacement support
volume rather than the deformed Source surface. Mapping every mixed-solid
nodraw face to visible masonry made those support sides and other hidden faces
visible, producing the slab piles, triangular slivers, and rectangular wall
patches.

The prop defects come from incompatible model origins:

- Dust crate origins are at their vertical centers; generated boxes must start
  at `origin.z - height / 2`.
- Source vehicle origins sit roughly 28 units above the ground, while the stock
  AA rusted-car model expects a ground-level origin.
- `palm_tree_trunk.mdl` origins are approximately 536 units above the ground
  because the Source trunk model extends downward from its origin. A complete
  stock AA palm uses a root origin and therefore needs that offset removed.
- Most Source cans and buckets are tipped clutter objects. Replacing them with
  upright AA buckets loses their orientation and should be omitted.

The corrective conversion rule is to rebuild each displacement face as a thin
convex slab extruded into the original solid, render only its outer face, and
caulk the inner and edge faces. Regular Source nodraw/helper faces can return to
real `common/caulk` now that every compile uses the retail shader scripts.

### Corrected-build validation

Revision 5 implemented the rule for all 61 playable displacement faces. The
generator emitted 2,289 world brushes and 142 entities, skipped no retained
displacement, omitted 28 unsupported/tipped clutter props, and retained 15
stock models (eight palms, six rusted cars, and one wagon). Generated crates
are now bottom-aligned from their center origins; cars are lowered 28 units;
and Source palm-trunk replacements are lowered 536 units.

The retail-data compile completed without a leak or invalid-brush error. Q3map
reduced 7,388 input faces to 6,905, fast VIS processed 633 clusters, 2,003
portals, and 2,490 faces with 550 clusters visible on average, and MOHlight lit
all 15 retained models. The final BSP is 4,971,888 bytes with SHA-256
`2CF6FBEA7D8B97282E0AA1A4F80B258529409A1FEF03C011E9DDFC12FB6D8B73`.
The packaged PK3 is 937,829 bytes with SHA-256
`645D437B108CDD5CE41892BB42F0A3775D8915DA4BC5B50F0EEBB2132C645667`.

An exact-package OpenMoHAA 0.82.1 dedicated test loaded the three-file PK3,
built Recast navigation in 0.839 seconds, and admitted two bots into the
battle. The bot server requires both `sv_maxbots` and `sv_numbots`; `addbot`
cannot increase the count when `sv_maxbots` remains at its default zero.

Automated visual-QA note: OpenMoHAA's `wait` command advances one command
buffer frame and ignores a numeric count, so timed capture configs need
repeated `wait` lines. The `tele` and `face` player events require the latched
`cheats` cvar. A failed cheat/teleport sweep can still write screenshots from
the unchanged spawn and must not be counted as coverage of the requested
coordinates. The successful ordinary-spawn capture showed continuous
caulk-corrected surfaces and grounded palms, while the displacement and
prop-origin repairs above were validated structurally and through compile and
runtime checks; the next human playtest remains the decisive visual check for
all six reported viewpoints.

### Third Dust II playtest: why thin base-plane slabs are insufficient

An eight-screenshot follow-up confirmed that center-aligned crates now rest on
the ground, but it also exposed major regressions:

- broad bright/sky-colored gaps appeared below walls and across missing terrain;
- the replacement displacement planes overlapped into layered ramps and ridges;
- generated dome stand-ins floated above the map in large clusters;
- at least one rusted-car substitute was buried deeply in an intact floor;
- black rectangular surfaces and unsealed openings remained in several routes.

The earlier fixed `-28` car-origin correction was based on an incorrect visual
inference: missing terrain below the first cars made them appear suspended.
Where an intact floor is visible, subtracting 28 units places the AA car below
the surface. The stock model should retain the Source car origin; only its
simple collision brush should extend downward around the wheels.

The larger regression proves that a Source displacement's undeformed support
face cannot stand in for its rendered surface, even when that face is extruded
as a thin slab. The `dispinfo` block stores a `(2^power + 1)` square vertex
grid. Each rendered vertex starts at a bilinear point on the original face and
then applies its stored offset plus `normal * distance`. Correct conversion
therefore requires tessellating that final grid and emitting the resulting
triangles as thin AA detail prisms. Using only the four base corners discards
the terrain shape, creates overlap between neighboring supports, and exposes
the bright world outside through the missing displaced surface.

The dome and antenna brush approximations are decorative rather than
gameplay-significant. Their Source placement depends on the original model
bounds and on roof geometry that may itself be displaced or model-based.
When that support is not reproduced exactly, a fabricated cylinder stack
becomes conspicuous floating geometry. These stand-ins should be omitted until
their support surface can be proven.

### Fourth Dust II repair: joined patch meshes, not micro-brushes

Reconstructing all displacement grid points fixed the missing terrain shape,
but representing its 6,944 grid triangles as individual eight-unit brush
prisms was not stable in the Allied Assault Q3map compiler. In-engine
wireframe and lightmap diagnostics proved that the remaining black polygons
were absent faces, not dark lightmaps or texture defects. Texturing the
perimeter sides did not help. Giving every triangle a local extrusion normal
made the gaps larger because adjacent solid prisms no longer shared the same
back volume.

The reliable representation is a set of joined `patchDef2` surfaces:

1. Reconstruct each VMF point as `bilinearBase + offset + normal * distance`.
2. Divide each odd-sized displacement grid into overlapping 3x3 control
   patches, advancing two samples per patch.
3. Reuse all three control points on every shared patch edge.
4. Determine playable-side winding from the original Source solid center.
5. Reverse the patch columns when the mathematical
   `cross(columnAdvance, rowAdvance)` normal points toward playable air,
   because MOHAA/Q3 patch draw winding uses the opposite visible side.

For the Dust II reference, this converts 61 displacement faces into 868 joined
patches while preserving the 6,944 source-grid triangle samples. Q3's patch
interpolation is quadratic, whereas Source renders a linear triangle grid, so
this is not byte-identical topology. It is visually continuous, collision is
present, and it avoids both the flat-support regression and the micro-brush
seams.

The final corrected build contains 2,171 ordinary world brushes, 868 patches,
and 142 entities. Q3map reduced 7,216 input brush faces to 6,725 in 28 seconds
with no leak or invalid-brush error. Fast VIS processed 602 clusters, 1,898
portals, and 2,344 faces with 549 clusters visible on average. MOHlight lit all
15 retained stock models in 17 seconds. It emitted four non-fatal
`potential hash mismatch` warnings while lighting curved patches.

OpenMoHAA 0.82.1 loaded 5,857 brush faces and all 868 meshes. The automated
player-spawn screenshot showed a continuous, lit, walkable floor without any
of the former black triangular holes. The test also confirmed that Source car
Z origins should be retained, crates should remain bottom-aligned, palms need
the measured -536 root correction, and unsupported dome/antenna stand-ins
should stay omitted.

The exact final three-file PK3 also passed a dedicated-server bot smoke test:
OpenMoHAA parsed the BSP in 0.040 seconds, generated Recast navigation in 0.884
seconds, and admitted `bot1` and `bot2`.

Revision 6 artifact fingerprints:

- BSP: 4,956,168 bytes, SHA-256
  `BBA2E073D632E10BA4794E017135CDE989886B9749800BA664A0576979F352E4`
- PK3: 1,003,791 bytes, SHA-256
  `BCEBCE2B542CAFD7EA32EC2C04512DDF2F5D95787B112443DC93A065B683B44C`

### Fifth Dust II playtest: quadratic terrain and missing facade props

Eleven follow-up screenshots (`shot0015` through `shot0025`) show that revision
6 removed the triangular terrain holes, but three defect classes remain:

- rock-wall displacements bow into oversized curtain-like ridges because raw
  VMF samples were used directly as quadratic Bezier control points;
- all six AA rusted-car substitutions remain about one Source-origin offset
  above the ground, and the larger AA silhouette collides visually with nearby
  crate substitutions;
- dozens of Source window facade models were omitted, leaving stark black or
  sky-colored rectangles in otherwise solid masonry.

A quadratic Bezier span does not pass through its middle control point. Using
three consecutive Source displacement samples as a 3x3 patch therefore changes
the measured terrain even though the patch edges meet. The better translation
is to preserve every Source sample as a Bezier endpoint and insert arithmetic
midpoints between adjacent samples. A 9x9 Source grid becomes a 17x17 patch;
each individual Source cell is then a bilinear span with no overshoot. This
also reduces the Dust II terrain from 868 separately lit patches to one joined
patch per retained displacement face.

The facade analysis also explains many apparent world holes. The reference
contains 27 `du_window_bridge` props, 13 `du_window_palace` props, and dozens
of dimension-named Dust window/shutter variants. Their surrounding wall
brushes were retained but the models themselves were skipped. Simple inset
stock-wood panels, oriented from each prop yaw and sized from the encoded
window dimensions, are a safer AA fallback than exposing the outside of the
map. Unsupported stone teeth, baskets, and loose stone-block stand-ins should
be omitted until their Source bounds are reproduced.

The final repair lowers level AA car replacements by 28 units and omits the
two Source cars whose pitch or roll exceeds five degrees. A static AA model
entity retains yaw but cannot reproduce those cars' steep compound tilt; the
previous upright substitutions therefore floated and overlapped nearby
geometry. Four level cars remain.

The corrected build contains 2,218 ordinary world brushes, 61 midpoint-
expanded terrain patches, 112 facade panels, and 140 entities. Q3map emitted
6,185 brush faces from 6,676 input faces with no leak or invalid-brush error.
Fast VIS processed 602 clusters, 1,898 portals, and 2,344 faces, with 549
clusters visible on average. MOHlight lit all 13 retained stock models. Its
old patch-lighting path emitted 22 non-fatal `potential hash mismatch`
warnings.

OpenMoHAA 0.82.1 loaded the exact final PK3 with 6,124 brush faces and 61
meshes, generated Recast navigation in 1.689 seconds, and ran four bots that
successfully navigated and killed one another. The runtime screenshot showed
a continuous floor and stock-wood backing panels in openings that were
previously black.

Revision 7 artifact fingerprints:

- BSP: 5,212,212 bytes, SHA-256
  `67F75242F7B3897088C48DE78FE2231046DE090CCB99D4812DFBE4295B616780`
- PK3: 1,252,297 bytes, SHA-256
  `B18E5C6466ABD7C19B742CF835DA0D48DDE76AE931724CB339BAD21D0C9A5A17`

### Sixth Dust II playtest: displacement backings and layered facades

Eleven more screenshots (`shot0000` through `shot0010`) confirm that revision 7
made the terrain continuous and restored active bot combat. They also reveal
the next visual defects:

- the terrain and rock-wall perimeter can still expose black void or brightly
  shaded undersides because the converter emitted only the displacement skin;
- `normandy` concrete is a poor substitute for Dust's rough rock boundary;
- one oversized replacement panel makes the missing facade models obvious,
  while a small panel alone leaves cream or black gaps around the opening;
- the revision 7 car correction buries the AA car's wheels.

A Source displacement belongs to a solid. Reconstructing only its displaced
face loses the brush volume behind the skin, including the side and bottom
surfaces that close the world wherever the terrain perimeter is visible. The
revision 8 converter therefore emits the 61 joined midpoint-expanded patches
and restores the 60 original displacement-bearing brush hulls behind them. The
displaced base plane is caulked; exposed helper-only perimeter faces use the
same visible material as the displacement. This keeps the accurate patch
surface while sealing its underside and boundary.

Facade repair works better as two independent visual layers. The generator now
places a large, two-unit-thick `general_structure/bunker_wall` backing across
each of the 112 missing model footprints, then adds a smaller four-unit-thick
`central_europe/shutter_set2` decorative face. Both are non-solid. The large
neutral backing closes the unwanted black/cream field without turning the
entire opening into a giant wooden shutter, while the modest shutter retains
the architectural cue. Keeping these visual replacements non-solid preserves
the routes generated from the Source brush layout; eight-bot runtime testing
confirmed traversal and combat.

The rough terrain boundary now uses `wilderness/wldrrckset1_1`, a stock texture
family already used by `obj_team2`. This matches the requested AA asset palette
more closely than bunker concrete.

Direct engine inspection corrected another model-origin assumption. The
revision 7 `-28` Z adjustment buries the wheels of the AA rusted-car model. A
retail `obj_team4` placement also keeps this model's entity origin roughly 28
units above its contact floor, proving that the raised origin is part of the
model contract rather than a Source offset that should be removed. Revision 8
retains the Source Z for the four level cars and continues to omit the two
steeply tilted cars that an upright AA static model cannot reproduce.

Compilation should use a clean retail-only game root. Compiling the same source
against a mod-heavy installation exhausted the old MOHTools surface table with
`MAX_SURFACE_INFO`; hardlinking only retail Pak0 through Pak6 into a staging
root removed the unrelated shader/surface pressure and produced a valid build.

The revision 8 generator emits 2,330 ordinary world-brush records, 61 terrain
patches, 112 facade backings, 112 decorative shutter panels, and 140 entities.
Q3map emitted 6,801 brush faces from 7,316 input faces with no leak or invalid
brush. Fast VIS processed 599 clusters, 1,913 portals, and 2,326 faces, with 547
clusters visible on average. MOHlight lit all 13 retained stock models and
reported 22 non-fatal `potential hash mismatch` warnings.

OpenMoHAA 0.82.1 loaded the exact PK3 with 6,740 brush faces and 61 meshes,
generated Recast navigation in 2.265 seconds, and ran eight bots that navigated
and killed one another.

Revision 8 artifact fingerprints:

- BSP: 5,565,188 bytes, SHA-256
  `A82B29231DEC86668ABEADE559F1D0B85A716076997106EF91BFD97D6C7063B5`
- PK3: 1,303,606 bytes, SHA-256
  `51604126DEFE362D6E3E2A0E407306622D32BCE29CFA1D26B47CDABF8E3826BB`

### Seventh Dust II playtest: boundary skirts and grade-snapped cars

Seven more screenshots (`shot0011` through `shot0017`) confirm that the
revision 8 layered facade treatment fixed the empty windows. They also isolate
two remaining conversion errors:

- cars whose Source origins are about 24 to 29 units above their local grade
  still visibly float;
- displacement edges can leave large black wall bands and smaller triangular
  wedges even though both the displaced patch and original support hull are
  present.

The second defect is a boundary-connectivity problem. A Source displacement
starts on a solid face, but its stored offsets and distances can move any
perimeter sample away from that face's undeformed edge. Restoring the original
brush hull closes the volume behind the base plane; it does not fill the space
between a moved patch perimeter and the base perimeter. That explains both the
large missing-wall-looking spans in `shot0012` through `shot0014` and the
smaller black rock wedges in `shot0015` and `shot0016`.

Revision 9 emits a material-matched quadratic patch skirt along each moved
boundary. Every skirt has three control rows: the reconstructed displaced
edge, arithmetic midpoint controls, and the original base edge. Long edges are
split at the same maximum eight-Source-cell span used by the main surface.
Winding is selected relative to the original solid center so the playable side
is visible. Edges whose displaced and base samples are effectively identical
are omitted. The 61 measured displacement surfaces require 235 skirts, adding
3,480 sealing triangles and bringing the runtime terrain total to 296 meshes.

The first skirt compile also exposed a legacy syntax rule that square patches
had hidden: AA Q3map interprets the first `patchDef2` dimension as the number
of row records and the second as the number of points in each row. A rectangular
skirt written as `(17 3)` while supplying three row records fails parsing; the
correct declaration for those records is `(3 17)`. Generators should treat the
dimension pair as `(rows columns)`, regardless of conventions used by other
Q3-family tools.

Direct inspection of retail `models/static/vehicle_car_rusted.tik` corrects
the revision 8 car-origin inference. Its Quaked bounds are
`(-128 -56 0) (128 48 96)`, and its collision maps also bottom out at model
Z=0. The entity origin is therefore the contact plane. Retaining Source car Z
values of `27.91`, `28.91`, `24`, and `144` necessarily suspends the AA
replacement. Revision 9 snaps a retained car to the nearest 64-unit grade when
it is within 32 units, producing Z values `0`, `0`, `0`, and `128`. It
preserves the small Source pitch, yaw, and roll through the entity `angles`
key and starts the extra caulk collision volume at the same grounded Z. The
two cars tilted by more than five degrees remain omitted.

The revision 9 generator emits 2,330 ordinary world-brush records, 61
midpoint-expanded terrain surfaces, 235 boundary skirts, 112 facade backings,
112 decorative shutter panels, and 140 entities. Q3map emitted 7,036 brush
faces from 7,551 input faces with no leak or invalid brush. Fast VIS processed
599 clusters, 1,913 portals, and 2,326 faces, with 547 clusters visible on
average. MOHlight lit all 13 retained stock models and reported 58 non-fatal
`potential hash mismatch` warnings from its old curved-patch lighting path.

OpenMoHAA 0.82.1 loaded the exact package with 6,740 brush faces and all 296
meshes and stitched 92 patch LoD cracks. It generated Recast navigation in
3.339 seconds in the first visual run and 3.309 seconds in the final
clean-retail package run, then ran eight bots. The bots traversed the map and
killed one another; eight automated viewpoints rendered lit, continuous
geometry on the sampled routes without the former black boundary bands.

Revision 9 artifact fingerprints:

- BSP: 6,213,732 bytes, SHA-256
  `47FB6DDED8B3A458B6867CCF53563D24575CB5F995AB435F08E760C03D3CE447`
- PK3: 1,546,408 bytes, SHA-256
  `7E0AD4C676091D192458F0EB2B305BEA0B0870F20F9B70221BAE1A18A8F640DD`
- source ZIP: 450,472 bytes, SHA-256
  `1EBCE36B4A5534EC36C4DFB479E7199D0CAB252CF7B1209E7954CFFD44589601`

### Lighting study: stock AA and Breakthrough's Monte Cassino

The revision 9 Dust II lighting is structurally wrong even though it is no
longer black. Its generator sets `ambientlight` to `15 15 16`, `ambient` to
`42`, `suncolor` to `92 84 68`, and adds 20 warm spawn-area fill lights at
550 intensity. It also clamps every retained Source point light to at least
450. Those large omnidirectional fills flatten surfaces, tint the whole level
tan, and erase the directional contrast that makes stock Medal of Honor maps
read well.

Stock AA maps do not require one fixed lighting recipe, and `obj_team2` should
be treated only as a useful data point rather than a target to copy. Across the
ten retail AA multiplayer sources, median point-light intensities are generally
between 5 and 80. `obj_team2` has 181 point lights with median 80 and average
88; `obj_team4` has 176 with median 50 and average 56.8. The AA sources also
prove that `sundiffuse`, `sundiffusecolor`, `farplane_color`, and low global
ambient values are valid AA techniques.

The user's Breakthrough reference is almost certainly
`mp_montecassino_tow.map`, whose worldspawn message is `Monte Cassino`. Its
distinctive outdoor look is produced by separation of lighting roles:

- warm direct sun: `suncolor "100 60 20"`;
- cool sky fill: `sundiffusecolor "70 70 90"` with `sundiffuse "1.1"`;
- low neutral/cool floor: `ambientlight "8 8 10"`;
- dark violet atmospheric distance:
  `farplane_color ".036 .024 .036"` at `farplane "4000"`;
- a dedicated `ep2sky/cassino` sky material;
- 291 local point lights whose median is only 15 and average is 61.6. Of
  those, 224 are intensity 20 or lower. Three exceptional 2500-intensity
  lights exist, but they are special accents rather than the baseline.

The transferable lesson is the warm-sun/cool-shadow relationship, low ambient,
restrained fixture lights, and a sky/farplane palette designed as part of the
same scene. Dust II should receive its own AA-compatible profile rather than
copying either Monte Cassino or `obj_team2`: clear Mediterranean daylight,
cream-to-neutral direct sun, slightly cool diffuse fill, visible but not black
shadows, mild distance haze, and warm local lights only where an actual
fixture or interior requires them. Spawn-following fill lights should be
removed. Retained Source lights should be selected by purpose and translated
into the normal AA intensity range instead of being globally clamped to 450.

Breakthrough-only sky assets must not be referenced by an AA package unless
they are intentionally redistributed. The underlying worldspawn techniques
are nevertheless AA-compatible because the same keys appear in retail AA map
sources. The safe approach is to use an AA sky (or a new bundled sky) and
reproduce the lighting composition with the AA compiler. Lighting changes
should be compiled as an isolated visual revision and playtested at outdoor
lanes, deep interiors, transitions, and player-model visibility before any
geometry changes are mixed in.

### Dust II revision 10: original Mediterranean daylight

Revision 10 applies the lighting study without changing geometry, props,
spawns, or collision. The worldspawn now uses:

```text
ambientlight     8 9 11
suncolor         135 116 88
sundirection     325 225 0
sundiffusecolor  58 66 84
sundiffuse       1.15
_color           1.0 0.94 0.84
farplane         8000
farplane_color   0.43 0.45 0.48
```

This is an original clear Mediterranean profile rather than a copy of V2,
`obj_team2`, or Monte Cassino. The sun is cream rather than orange, while the
diffuse and ambient components are cooler so shadows separate from the warm
surfaces. The blue-gray farplane coordinates distance haze with the sky
without importing a Breakthrough-only sky asset.

The converter deletes the loop that placed a 550-intensity point light over
every second multiplayer spawn. It retains all 25 real Source `light` and
`light_spot` entities, but maps Source brightness `b` to
`clamp(b * 0.9 + 15, 10, 200)` and adds `overbright_range 0.2`. In the current
playable bounds that produces 25 AA point lights from 24 to 150 intensity,
with median 60 and average 72.4. Their original colors and origins remain
intact. The conversion report consequently drops from 140 to 120 entities and
records zero fill lights.

Two in-engine bakes were useful. The first used `ambientlight "6 7 9"` and a
weaker `clamp(b * 0.55 + 10, 10, 180)` fixture translation. It immediately
removed the former tan wash and restored directional outdoor shading, but an
automated tunnel viewpoint was too close to black. Raising ambient to
`8 9 11` and strengthening only the real fixtures made that interior readable
without reintroducing global or spawn-following fill. This illustrates why
lighting QA must sample both the attractive courtyard view and the least-lit
playable route.

The final isolated build retained the revision 9 geometry counts. Q3map emitted
7,036 faces from 7,551 inputs without a leak or invalid brush. Fast VIS
processed 599 clusters, 1,913 portals, and 2,326 faces, with 547 clusters
visible on average. MOHlight lit all 13 stock models and emitted the same 58
non-fatal curved-patch hash warnings as revision 9.

OpenMoHAA 0.82.1 loaded the exact final PK3 with 6,740 faces and 296 meshes,
generated Recast navigation in 3.171 seconds, and ran eight bots that traversed
and killed one another. The final eight-viewpoint run sampled sunlit
courtyards, shadowed lanes, indoor/outdoor transitions, and the darkest
retained-fixture tunnel. Player silhouettes and surface shapes remained
readable while interiors stayed intentionally darker than outdoor routes.

Revision 10 artifact fingerprints:

- BSP: 6,111,568 bytes, SHA-256
  `05E0F1E96B2ABA73F2326330A42F6CD3D30D19599E6BB44E039925AA994CE442`
- PK3: 1,550,872 bytes, SHA-256
  `9B113BC0A20B26A2DFD7E89AAC56AA87712E76B37FBA2D9246968EE43686DDA9`
- source ZIP: 450,874 bytes, SHA-256
  `347B86765F960DB98F98C5CD674C03E1D6903D52CB351F2ECD30B417FB3A2A0E`

## Cobblestone conversion: choosing the tractable CS reference

The decompiled CSGO references make Cobblestone the better next target than
Cache. The measured VMFs differ substantially:

| Measurement | Cache | Cobblestone |
| --- | ---: | ---: |
| File size | 45,755,859 bytes | 12,794,064 bytes |
| World solids | 13,227 | 3,047 |
| Total solids | 16,508 | 5,841 |
| Sides | 99,612 | 37,344 |
| Displacements | 10,952 | 854 |
| Entities | 7,643 | 4,229 |
| Prop instances | 4,170 | 1,246 |
| Unique prop models | 647 | 135 |
| Unique materials | 154 | 75 |

Cobblestone is not small by AA standards, but it has roughly one quarter of
Cache's world brushes and fewer than one tenth as many displacements. It also
maps naturally onto stock AA stone, timber, roof, cobble, grass, door,
shutter, and vegetation assets.

### Reading ordinary BSPSource displacement data

The Cobblestone VMF established that BSPSource does not always write
`vertices_plus`, and an ordinary decompiled `dispinfo` block may omit
`offsets`. A converter must therefore:

1. intersect the convex backing brush's planes to recover its vertices;
2. select the four vertices lying on the displacement side;
3. order the quad from `startposition`;
4. treat missing offsets as zero vectors;
5. combine the bilinear base point, per-sample offset, and
   `normal * distance`;
6. reverse patch columns when the generated draw side faces into the backing
   solid.

That reconstruction succeeded for 839 of 840 candidate sides in the full
experimental mode; one degenerate surface had no usable normal. It produced
839 visible surface patches. Restricting boundary skirts to traversable
terrain reduced skirt meshes from 2,273 to 1,231 without removing roof or
timber surfaces.

The geometry was nevertheless impractical for the original compiler. A
3,112-patch build and a reduced 2,070-patch build each spent ten minutes in
Q3map without completing. This is a compiler-scale limit rather than invalid
VMF data. The reproducible generator retains the curved implementation behind
`--full-displacements`, while its default first-playable mode renders and
collides against the original planar backing brushes.

### Q3 portal limits and the structural-shell solution

A planar 2,721-brush import compiled its geometry quickly but failed while
loading portals:

```text
LoadPortals: NumVisBytes 2406176 exceeds 2097152
```

Disabling 1024-unit block chopping increased the failed portal data to
2,726,120 bytes. A large Source layout cannot let every imported wall and trim
become a structural Q3 split plane.

The working conversion encloses the playable bounds in six structural
`sky/mohday1` brushes and flags imported interior geometry as detail. Detail
brushes retain collision and lightmapped surfaces but do not recursively
partition visibility. This reduced the final VIS problem to 90 clusters, 161
portals, and 1,448 bytes of visibility data.

Importing none of the original `func_detail` solids compiled in 126 seconds,
but engine QA showed conspicuously absent building sections. Importing all
2,735 caused Q3map to exceed a ten-minute bound. Bounding-box volume was a
useful first-pass fidelity heuristic:

- below 4,096 cubic units: 364 solids;
- 4,096–16,383: 454;
- 16,384–65,535: 696;
- 65,536–262,143: 561;
- 262,144–1,048,575: 347;
- at least 1,048,576: 313.

The selected baseline omits the 1,514 solids below 65,536 cubic units and
keeps 1,221 larger `func_detail` solids. Q3map completed this 3,938-brush map
in 323 seconds, emitting 18,610 faces from 19,998 inputs. The threshold is a
practical initial-build policy, not an art rule: later revisions should bring
back selected long/thin façade elements by material, model context, or visible
importance instead of reducing the threshold globally.

### Cobblestone first-playable content and validation

The first compiled revision uses only AA-native assets. Its prop translation
creates non-solid stone arch/port frames, shutter/door/grate façade panels,
upright barrel cylinders, hay/coffin/crate cover, and a reduced set of stock
trees and bushes. The conversion report records:

- 3,140 converted source solids and 840 planarized displacement brushes;
- 44 neutral DM spawns, 22 Axis spawns, and 22 Allied spawns;
- 65 translated Source fixture lights and no spawn-following fills;
- 123 cover brushes, 193 arch or port replacements, and 90 façade panels;
- 26 stock trees and 48 stock bushes;
- 1,128 helper-only brushes and 18 distant-skybox brushes omitted.

Lighting follows the warm-direct/cool-fill lesson from the Dust study:
`ambientlight "9 10 12"`, `suncolor "112 101 84"`,
`sundiffusecolor "58 65 78"`, and `sundiffuse "1.2"`. Source fixtures are
translated with `clamp(b * 0.9 + 15, 10, 200)` and
`overbright_range "0.2"`. Full MOHlight completed in 239 seconds.

OpenMoHAA 0.82.1 loaded the exact final PK3. An initial QA mistake showed that
`bot_enable` alone does not create bots: the engine requires `sv_maxbots` and
`sv_numbots`. With both set to eight, bots spawned, moved, fought, traversed
outdoor grades, and used interior corridors. Eight followed-player
screenshots confirmed coherent castle walls, roofs, vegetation, exterior and
interior lighting, and working player collision. Known first-revision visual
debt remains: planar rather than sculpted terrain, omitted thin trim, and a
small number of floating or incomplete façade/prop fragments.

Artifact fingerprints:

- BSP: 14,511,848 bytes, SHA-256
  `8C7404BA4C21B45906D623208845AB7C498BF96662CCA39A4F8F953F9DF3AA7C`
- PK3: 2,857,786 bytes, SHA-256
  `C3F0455695E71001948743348C86659033D43512DA6899CDB8BDC3C517A50E7E`
- source ZIP: 312,239 bytes, SHA-256
  `BE57F404A38607406E8D9FCC504AF4BE967D89CD490F1DEB9A4A601542586DA4`

### Cobblestone revision 2: restore thin architecture

The first user playtest supplied four screenshots that exposed a systematic
failure rather than unrelated local bugs:

- large exterior wall areas opened directly to sky;
- window, door, arch, and port replacements floated without supporting walls;
- interior floors and ceilings ended abruptly;
- bridge and passage shells contained bright holes.

The cause was revision 1's bounding-box volume filter. A small-volume Source
`func_detail` solid is not necessarily cosmetic: wall skins, floor plates, and
ceiling slabs can have a large visible area but very little thickness. Leaving
their attached prop replacements in place made the failure especially
conspicuous.

Revision 2 removes the filter and retains all 2,735 `func_detail` solids. The
structural six-brush sky shell remains essential: all 4,653 imported source
solids are detail geometry, so restoring them increases compile time and face
count without returning to the 2 MiB portal overflow. Q3map completed the
5,471-brush final map in 731 seconds, emitting 25,873 faces from 27,605 inputs.
Fast VIS remained at 90 clusters. Full MOHlight completed in 388 seconds.

Cobblestone also uses modular castle models as architecture. Placement
measurement showed that `port_a` and `port_b` instances repeat at 256-unit
intervals, while `port_sect_a` repeats at roughly 128 units. The earlier
universal 112-unit approximation left rows of unsupported uprights. Revision
2 uses non-solid 256-unit major port modules, 128-unit port sections,
32-to-48-unit depth, and heavier stone surrounds. Fourteen omitted
`arch_g_pillar` instances now receive generated stone pillars. These visual
modules do not change navigation collision.

The final conversion report records 5,471 generated brushes, 4,653 converted
source solids, 840 planarized displacement backing brushes, 195 arch/port
modules, 137 cover brushes, and zero skipped detail solids. The package still
uses 44 neutral DM spawns, 22 Axis spawns, 22 Allied spawns, 65 translated
fixture lights, and 74 stock vegetation entities.

Two eight-bot OpenMoHAA runs were inspected. The first proved that complete
detail import restored continuous walls, floors, ceilings, and interior
shells. The second validated the measured port widths. Bots spawned, moved,
fought, and traversed both interior and exterior routes. Remaining fidelity
debt is now narrower: planar rather than sculpted displacement terrain and
some simplified distant arcades whose original surfaces exist only in Source
model files, not VMF brush data.

Revision 2 artifact fingerprints:

- BSP: 18,722,768 bytes, SHA-256
  `89A9FD5A42C0D3F4E998455A609764E9EA75080C66358AC6865FB768ADAE23F9`
- PK3: 3,694,818 bytes, SHA-256
  `B63199BB5A044D9ADA1A21F665D819DF899CBDA200EE722745806E97A15E99C5`
- source ZIP: 441,353 bytes, SHA-256
  `B1B9F5ABEE8933564EBF082E2797B0F66065B41128E17C128AB7DDAB5F6EFC87`

### Cobblestone revision 3: remove unmeasured model guesses

A 19-screenshot playtest, `shot0000.tga` through `shot0018.tga`, showed that
revision 2 had repaired the missing brush shells but introduced a different
systematic failure. Repeated floating U-shaped frames, ribs, arcades,
shutters, doors, black panels, and pillars came from 299 generated stand-ins
for Source architectural models. The generator knew instance origins, angles,
and repeated spacing, but did not have the source meshes, bounds, pivot
conventions, or per-family opening measurements.

Repeated spacing is not evidence of a model's shape, bounds, pivot, depth, or
architectural role. A generic three-brush frame was therefore not a measured
translation even where its width matched the distance between instances. The
release rule is now:

- retain an architectural model only when the mesh can be converted directly,
  verified bounds and pivot are available, or the receiving opening is
  measured and reconstructed per model family;
- otherwise omit it cleanly;
- keep guessed placeholders only behind an explicit diagnostic flag and never
  ship them as release geometry.

Several bright triangular floor and support cuts had a separate cause.
Source's `tools/toolsnodraw` marks a face that is expected to be hidden by an
adjacent model, displacement, or brush. Translating every such face to AA
caulk exposes holes when that expected cover is omitted or planarized.
Revision 3 gives mixed-material brushes a fallback derived from the same
brush's visible material. This repairs 5,682 potentially exposed support
faces without rendering dedicated all-nodraw helper solids.

Planar displacement conversion also changes the surface height under props.
Revision 3 extracts 448 usable displacement support quads and grounds retained
cover and foliage to them when the correction is no more than 64 units. This
adjusts 117 origins while avoiding large, speculative teleports. Cobwebs are
omitted, Source glass uses verified stock `mohcommon/window5`, and
`de_cbble/outwall02` plus `de_cbble/trimwall01` map to stock stone rather than
the overly bright generic plaster fallback.

The revision-3 generator emits:

- 4,782 world/detail/prop brushes;
- all 4,653 converted source solids and all 2,735 `func_detail` solids;
- 840 planar displacement backing brushes;
- 123 generated cover brushes and 74 stock vegetation entities;
- 44 neutral, 22 Axis, and 22 Allied spawns;
- 65 translated fixture lights;
- zero release arch frames or facade panels and 299 explicitly omitted
  architectural props.

The first structural candidate compiled to 27,079 faces, 90 fast-VIS
clusters, and a 19,726,656-byte lit BSP. OpenMoHAA 0.82.1 loaded the exact
three-entry package, generated Recast navigation in 5.098 seconds, and ran
eight bots that moved and fought. Eight bot-follow and ten fixed-camera
screenshots confirmed that the repeated frame fields, floating facade panels,
and tested support holes were gone. That QA also identified the final
`outwall02`/`trimwall01` material correction described above.

The final stone-material pass compiled 28,947 input faces to 27,062 output
faces in 1,056 seconds. Fast VIS remained at 90 clusters, 161 portals, and
1,448 visibility bytes. Full MOHlight completed in 449 seconds, producing a
19,716,348-byte lit BSP with empty stderr and only two benign per-leaf light
clamps.

The exact final three-entry PK3 then passed a new isolated OpenMoHAA 0.82.1
run. Its package hash matched the tested copy, Recast navigation generated in
4.971 seconds, eight bots produced seven recorded kills, and eight bot-follow
plus ten fixed-camera views showed no return of the diagnosed placeholder,
support-hole, or pale-facade failures.

A clean regeneration into a separate output directory produced a
byte-identical `.map`, closing the reproducibility gate independently of the
compile and runtime checks.

### Cobblestone revision 4: planar seams and source collision intent

Nine additional screenshots, `shot0019.tga` through `shot0027.tga`, confirmed
that revision 3 was a large improvement while exposing two narrower conversion
failures. Bright triangular or ribbon-like gaps remained between planar
terrain faces, and bots could reach exterior terrain islands where vegetation
floated against the sky.

The seam failure is different from revision 3's nodraw failure. A
material-matched brush side cannot cover XY area that existed only because a
Source displacement sample moved horizontally beyond its backing polygon.
Full curved reconstruction remains outside the practical Q3map patch budget.
Revision 4 therefore generates one simple visual underlay beneath each
traversable planar displacement: 24 units of outward expansion and 12 units of
downward offset. The original backing brush remains the collision surface.
Only 311 terrain surfaces qualify, avoiding the thousands of patches created
by the full-displacement experiment.

The helper audit also disproved the assumption that all tool-only solids are
editor noise. Of 1,129 skipped helper brushes, three use
`toolsplayerclip`, while 46 `toolsclip` brushes have at least one 512-unit
extent. Revision 4 preserves those measured large collision volumes as stock
AA `common/playerclip` or `common/clip`, while continuing to omit 1,080 hints,
skips, areaportals, ladders, and small helper volumes. This preserves source
route intent without importing every helper blindly.

Finally, when a vegetation origin lies over a planar displacement but requires
more than the verified grounding correction, the substitute is now omitted
instead of left floating. The candidate retains 31 grounded stock vegetation
entities and omits 128 incompatible source instances before decorative
thinning.

The same playtest noted that visible doors do not open. This matches the
reference entity data: it contains zero `func_door` or
`func_door_rotating` entities and 33 static door-model references. Interactive
AA doors should therefore be treated as a deliberate gameplay enhancement,
not assumed conversion fidelity. They require verified bounds, pivots, swing
clearance, route value, and bot testing before introduction.

The revision-4 candidate emits 5,142 brushes or patches, converts 4,702 Source
solids, retains all spawns and 65 fixture lights, and keeps the revision-3
architectural-model omission and material rules. Compile and isolated runtime
measurements are recorded in the map-specific revision report. Q3map compiled
29,258 input faces to 27,373 output faces in 1,172 seconds; fast VIS remained
at 90 clusters, 161 portals, and 1,448 visibility bytes.

Full MOHlight completed in 487 seconds and produced a 20,422,536-byte BSP. It
reported two per-leaf clamps to the 60-light limit and four `potential hash
mismatch` warnings. The build still loaded and rendered, but warning-bearing
light passes must be documented by coordinate rather than labeled clean.

The exact three-entry PK3 passed an isolated OpenMoHAA 0.82.1 run. Recast
navigation generated in 6.575 seconds; eight bots moved, fought, respawned,
and produced ten recorded kills during six automated bot-follow views. The
sampled views showed no recurrence of the incompatible floating vegetation.
They also disproved the stronger containment hypothesis: restoring the 49
measured player/general clip brushes alone does not prevent bots from reaching
all exterior terrain and edge routes. The omitted Source 3D skybox and
incomplete exterior boundary remain separate topology debt.

Automated fixed-camera work exposed a QA-specific lesson. Setting an entity's
ordinary `angles` does not set an OpenMoHAA player's rendered view; a player
uses the `viewangles` event, and client input can overwrite it before a delayed
screenshot. A reliable scripted camera harness must set `viewangles`
immediately before capture or use a dedicated camera entity. Survey views that
do not reproduce the user's exact ground-level angle are regression evidence,
not proof that every reported seam is gone.

A separate regeneration produced a byte-identical 4,237,412-byte `.map`,
closing the deterministic-source gate for revision 4.

## Nuke preproduction: VPK, embedded autocombines, and original modern art

The Nuke decompile is structurally healthy but establishes a stronger source
completeness rule than the earlier ports. The 19,262,971-byte VMF contains
8,039 solids, 48,098 sides, 761 displacement faces, 6,891 static props, and
471 ordinary/spot lights. Its brush geometry is substantial, but it is not the
complete industrial silhouette.

**OBSERVED:** all 121 visible brush materials resolve from the local Source 1
VPK. In contrast, only 695 of 1,405 unique referenced MDLs live in that VPK.
The remaining 710 are `models/props/autocombine/de_nuke/...` entries generated
into the map. Reading the BSP's embedded pak resolves all 710, and every one of
the 1,405 studio headers supplies a measurable local bounds envelope.

This separates three kinds of reference evidence:

1. VMF brush planes define primary structural geometry.
2. VPK materials/models define reusable source roles, dimensions, and ordinary
   prop families.
3. BSP-embedded autocombines define map-specific assembled geometry that a
   VMF-only importer otherwise misses.

**PROVEN audit rule:** inspect both VPK and BSP pak before calling a Source
reference complete. Do not redistribute either archive's contents. Derived
counts, dimensions, placements, material roles, and original reconstructions
are acceptable production inputs.

The source's 121 visible materials reduce to a much smaller legacy-engine
palette: light/dark/painted concrete, interior concrete floor, blue/gray
corrugated cladding, smooth trim, asphalt, ground, grating, ceiling tile,
glass, chain-link, maintained grass, and compact gravel. Six original raster
bases were generated without Valve pixel input, then a deterministic build
made fourteen 512×512 TGA materials with
mechanically continuous edges. This is a better modern-Nuke direction than
forcing stock Allied Assault stone, plaster, or Second World War props onto
the layout.

Nuke also corrects the door assumption learned from Cobblestone. The reference
contains four actual `prop_door_rotating` entities, including a paired set.
Future conversion must either recreate their measured swing behavior and test
bots, or deliberately leave a route open. A closed decorative panel that never
moves would change source flow without documenting the change.

The playable and distant clusters are measurably separate. Most solid centers
sit between Y -3,072 and 1,023, while 900 sit between Y 7,168 and 12,360.
Spawn-expanded classification identifies 7,010 candidate playable solids and
1,029 outliers. This is a starting classifier; boundary solids still require
inspection before the skybox cluster is omitted.

The first generator applies the audit conservatively. It converts 5,639
playable source solids, including fourteen `func_breakable` solids retained as
static first-playable architecture; planarizes 604 displacement faces; keeps
source player/large clip volumes; and replaces 638 simple props from parsed
studio-header bounds. It emits four real AA `func_rotatingdoor` entities with
origin brushes rather than closed decorative panels.

Twenty hero industrial models are simple enough to reconstruct from name,
bounds, placement, and the local reference preview: ten medium silos, seven
water tanks, two reactor/silo forms, and one process silo. Thirty-four original
16-sided cylinder/frustum brushes restore those forms. They deliberately
remove solid collision so a broad visual envelope cannot cut through playable
interiors; source brush/clip geometry remains the collision authority.

The 710 autocombines remain explicit debt. Their names divide into pipes,
wires, web joists, HVAC ducts, curbs, railings, roof trim, ladders, fence, and
catwalk supports. A family name plus one combined AABB does not justify a full
solid box. Those assemblies require mesh-informed or screenshot-guided
procedural templates in later revisions.

### Nuke revision 1: compiled modern palette, doors, and bot proof

The final generator emits 6,949 world brushes and 541 entities. Its
5,221,665-byte map regenerates byte-identically with SHA-256
`22D39A6E47E657F4F6B2A0FC4E9AD008DB36695E6B2119C13EC219A3C9EA91C0`.
Static validation resolves all fourteen custom materials, counts four rotating
doors, and finds 16 Axis, 16 Allied, and 32 neutral DM spawns.

Q3map compiled 35,149 input faces to 32,140 output faces in 2,115 seconds with
no missing-image, malformed-brush, or fatal warning. Fast VIS completed with
154 clusters, 283 portals, and 3,704 visibility bytes. Full MOHlight finished
in 976 seconds and produced a 23,422,268-byte lit BSP. It also reported fifteen
`potential hash mismatch` coordinates and clamped the entity-light list to 60
lights in 33 leaves.

**PROVEN lighting rule:** a restrained intensity transform is not sufficient
when the Source map contains a dense fixture field. Nuke translated all 471
ordinary/spot fixtures, and MOHlight's clamp count shows that the legacy engine
cannot retain every local light association. A later pass must spatially
cluster or deduplicate fixtures and compare the darkest interiors rather than
merely lowering every light.

The 7,059,297-byte final PK3 contains eighteen entries and SHA-256
`3E577D3711C2B3ACFA9D7665D8D7968581C90615071D145C475B221AE71AF014`.
OpenMoHAA 0.82.1 loaded that exact package, parsed the BSP in 0.118 seconds,
built Recast navigation in 10.509 seconds, admitted eight bots, and logged 27
kills during a 30-second smoke test. This proves first-playable navigation,
movement, combat, death, and respawn. It does not prove final visual fidelity
or the visible alignment/swing clearance of the four doors; those remain
human-client checks.

### Nuke revision 2: screenshot-driven fill, lighting budget, and exact-package proof

**Superseded by revision 3:** The following section records what revision 2
implemented and what the compiler/runtime proved at the time. The next
13-image human review rejected its aggregate-hull geometry and broad
`nolightmap` policy. Its two bold "PROVEN" conclusions below are retained as
historical evidence but explicitly corrected in the revision-3 section.

Twenty user screenshots established five recurring visual classes: exposed
yellow/black terrain and horizon gaps, missing railing/catwalk assemblies,
dark industrial interiors, black window placeholders, and overly blue glass.
The user authorized original fill geometry where the decompile or Source-only
model set left the map visibly incomplete.

Measured displacement normals/distances now control planar seam-underlay
expansion. The accepted terrain set emits 632 material-matched underlays and
needs at most 117 units of horizontal expansion. This replaces an arbitrary
constant with a source-derived bound. The yellow `sky/mohday1` lower
hemisphere is replaced by stock `sky/m5l2`, and former black window materials
map to a new original non-solid window backing.

The 710 BSP-only autocombines are divided by family and evidence. The accepted
generator reconstructs 419 placements as 803 original nonblocking brushes:
308 railing, 149 pipe, 123 ladder, 66 web-joist, 54 curb, 40 HVAC, 33
roof-trim, 18 chain-link, and 12 catwalk-support brushes. The remaining 291
placements and all wires stay omitted.

The first reconstruction used 1,361 fill brushes and 8,314 total brushes.
Q3map exceeded a 3,604-second bound without a clean return. Capping repeated
posts, rungs, and secondary cross-runs preserved all 419 placement families
while reducing the final source to 803 fills and 7,755 total brushes.

**THEN-CONCLUSION, NOW DISPROVEN:** preserve the measured long silhouette and
sparse recognizable sub-elements. Revision 3 established that an aggregate
hull does not prove that silhouette in the first place.

Revision 2 clusters the 471 Source point/spot candidates into 259 retained
lights using 128×128×96 cells. MOHlight later clamped 28 entity-light lists,
down from 33 in revision 1. This is an improvement, not final proof of the
visual result.

The first optimized BSP compiled with the final 39,985 input and 36,976 output
faces, but MOHlight rejected it:

```text
MAX_MAP_LIGHTING exceeded from 180 lightmaps
```

The generator now adds `surfaceparm nolightmap` to 6,126 sides belonging to
nonblocking cosmetic rails, ladders, pipes, trim, fixtures, and window
dressings. Their visible geometry remains vertex-lit. Primary architecture
keeps baked lightmaps. A repeat Q3map produced the identical face counts, and
full MOHlight completed successfully.

**THEN-CONCLUSION, NOW SUPERSEDED:** every reconstructed Source-model family
needs an explicit lighting policy, but narrow detail must not default to
vertex lighting without in-engine visual proof.

The final 6,043,387-byte map regenerates byte-identically with SHA-256
`71AC5923FDA30A6D7E067FC625F4B6CC1F1C9267D44A50C153A3EA8541347369`.
Q3map took 2,886 seconds; fast VIS retained 154 clusters, 283 portals, and
3,704 visibility bytes; MOHlight took 1,116 seconds, emitted 16 non-fatal hash
warnings and 28 clamp messages, and wrote a 25,315,896-byte BSP.

The 19-entry, 7,278,310-byte PK3 has SHA-256
`A08EF1D4A109D2465249A116566D17CFF802B4EB0CC5214A42B6408826F632EF`.
An isolated OpenMoHAA 0.82.1 homepath loaded that exact package, generated
Recast navigation in 14.754 seconds, admitted eight bots, and logged 60 combat
events with zero runtime errors.

These results prove compile, visibility, lighting, package, navigation, and
combat readiness. They do not prove that every screenshot defect is visually
closed or that the four doors align and swing correctly in a human client.
Those remain the next evidence pass.

### Nuke revision 3: human screenshots disprove aggregate-hull topology

The user's `shot0000.tga` through `shot0012.tga` review showed revision 2's
inferred geometry as giant white floating bars, crossed beams, false ladders,
rail-like runs, and arbitrary frames throughout exterior and interior spaces.
The result was not a minor alignment problem. It invalidated the construction
rule itself.

An embedded autocombine studio hull is the union envelope around potentially
many separated meshes. It does not reveal which axis contains geometry, how
many runs exist, where those runs sit inside the box, or how they connect.
Filename plus AABB was therefore insufficient evidence even for apparently
simple families such as railings, pipes, ladders, joists, curbs, and ducts.

Revision 3 removes all 803 autocombine fill brushes and all smaller
ordinary-prop principal-run substitutions. All 710 autocombines return to
explicit omission. The validator now fails if any autocombine reconstruction
or fill brush returns.

The screenshots also showed why broad `surfaceparm nolightmap` was the wrong
response to the 180-lightmap overflow: it made invalid detail render as
dominant white/fullbright clutter. Revision 3 removes all 6,126 such sides.
With the invalid fills gone, the normal-lightmapped 6,949-brush source
compiled and full MOHlight completed within budget.

**PROVEN topology rule:** a combined model hull is only an outer envelope. Use
it as a containment check after topology is independently established; never
derive an internal run or skeletal template from the hull alone.

**PROVEN lighting-correction rule:** when added detail causes a lightmap-budget
failure, first remove or reduce unproven geometry. Do not conceal geometry debt
with broad `nolightmap`; vertex-lit appearance requires representative
in-engine proof.

Revision 3 preserves only independent revision-2 changes: the measured
117-unit maximum terrain-underlay expansion, original window backing,
neutralized glass, provisional `sky/m5l2`, four rotating doors, and clustering
of 471 fixture candidates to 259 lights. Remaining exterior terrain cracks
and the flat gray sky stay open rather than receiving another broad,
unverified fill.

The deterministic map is 5,218,048 bytes with SHA-256
`9C9EAB05034C35600547F805348D0C71C1A903A5D527E3776D5AB301417838F4`.
Q3map compiled 35,149 input faces to 32,140 output faces in 2,077 seconds.
Fast VIS retained 154 clusters, 283 portals, and 3,704 visibility bytes. Full
MOHlight finished in 1,083 seconds with empty stderr, 16 non-fatal hash
warnings, and 28 entity-light-list clamps. The 23,494,100-byte BSP has
SHA-256
`F79BF2BDA45CA188A09A2C3D63646E3BEAD8CC1D43D4975685C7E5881B51ED97`.

The 19-entry PK3 is 7,093,663 bytes with SHA-256
`4790A691A592DAA7B6D35DD5BD658E02760EB994EC691152F8601D84D7FFCF63`.
An isolated OpenMoHAA homepath loaded that exact package, generated Recast
navigation in 9.515 seconds, admitted all eight bots, logged 119 combat events
in two minutes, and emitted zero engine/map/script error matches.

This revision is a regression-recovery build. It proves removal of the
machine-generated regression and technical playability; the next human
screenshot/door pass must confirm appearance and interaction.

### Nuke revision 4: measured ordinary-prop fidelity without aggregate fill

The user found the technically stable revision 3 recognizably Nuke but "very
empty" and asked for the structures, machinery, furnishings, vehicles, and
silhouette visible across the Nuke location gallery—not merely new textures.
The cause was measurable: revision 3 omitted 3,065 ordinary prop instances in
the playable cluster after correctly removing revision 2's unsafe aggregate
fills.

Revision 4 creates `fidelity-manifest.json`, a derived-fact inventory of all
4,687 model entities inside the playable envelope. Each record preserves the
entity class, model-family name, origin, angles, scale, Source `solid` setting,
and parsed studio-header envelope without copying any Source mesh or texture.

The new family-specific layer restores 1,932 ordinary instances with 2,855
original brushes. High-impact groups include 242 foliage placements, 236
chain-link components, 216 ventilation pieces, 178 cover pieces, 137
structural supports, 137 furniture pieces, 83 electrical assemblies, 76
windows, 59 control-room displays, 44 static doors, 35 chairs, 24 industrial
rails, 22 transformers, 17 cars, 8 forklifts, and the defining A/B-site
vessels, cranes, platforms, consoles, and reactor machinery.

**OBSERVED family-template rule:** ordinary model identity plus measured
transform/bounds can justify a conservative family silhouette, but not an
arbitrary filled hull. Use sparse beams for frame-like cranes, cylinders or
frustums for vessels, multi-box silhouettes for vehicles, and non-solid alpha
cross-cards for foliage. Collision comes only from the Source entity `solid`
flag or existing measured clips. All 710 BSP-only autocombines remain omitted
with zero inferred fill brushes.

Seven additional deterministic original materials bring the palette to 22:
clean white machinery metal, yellow/red safety paint, blue equipment, rubber,
control-panel material, and alpha-tested foliage. No Valve pixels or model
payload enter the repository or PK3.

The corrected deterministic revision-4 source contains 9,448 brushes and is
8,195,795 bytes with SHA-256
`5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040`.
Static validation reports 1,546 still-unsupported ordinary props, zero invalid
converted brushes, four rotating doors, and the full 16 Axis / 16 Allied / 32
neutral spawn set.

The added density made MOHlight request 210 lightmap pages against AA's hard
180-page limit. The bundled MOHTools 1.48 executables do not implement the
newer `q3map_lightmapSampleSize` shader directive, and a `-samplesize` light
probe waits at zero CPU instead of changing the atlas. The corrected source
applies `+surfaceparm nolightmap` only to 4,320 sides belonging to large
foliage cards and chain-link mesh panels; posts and every opaque architecture
or dressing family remain baked. That narrow change reduced the allocation to
194 pages but still failed the hard gate. A controlled shader-level glass flag
also left 194 pages, proving that the budget is controlled by per-surface
allocation fields rather than shader records alone.

Revision 4 therefore adds a deterministic post-VIS BSP 19 lightmap repacker
based on the actual MOHAA Q3map allocator semantics. It preserves all 42,815
baked rectangles and their dimensions, globally skyline-packs them with
one-pixel gutters, updates draw-surface page/X/Y fields, and translates owned
draw-vertex normalized lightmap UVs by the exact atlas delta. The result is 166
pages instead of 194, with 53.98% exact texel utilization and 96.12% reserved
rectangle-plus-gutter utilization. The final inspector reports 166 allocated
and 166 written pages; full MOHlight completed in 1,581 seconds with empty
stderr. Twenty-eight entity-light leaves were clamped to the retail 60-light
limit and remain documented density debt.

The canonical ordinary Q3map pass completed in 5,285 seconds with 47,591 faces
from 50,669 inputs and zero stderr errors. Fast VIS retained 154 clusters and
3,704 visibility bytes. The final BSP is 31,236,136 bytes. Its exact 26-entry,
9,567,575-byte PK3 loaded in isolated OpenMoHAA, parsed the BSP in
0.158-0.166 seconds, generated Recast in 16.404-17.370 seconds over three match
cycles, admitted eight bots each cycle, and logged 263 combat/death events with
zero fatal markers.

Two scripted client sweeps generated fifteen fixed-camera frames. Usable views
confirm that Outside is no longer the empty revision-3 shell and that lower
industrial spaces contain the intended yellow crane beams, platforms, stairs,
equipment masses, ceiling modules, and clean institutional palette. Several
measured-camera offsets landed against walls, ceilings, or black
window-backing volumes and cannot support room-level acceptance. The
provisional sky, conservative blocky substitutes, remaining autocombines, and
any alignment defects found by the user's next screenshot pass remain explicit
debt.

**PROVEN lightmap-atlas rule:** when a valid BSP exceeds AA's page ceiling due
to shader-group skyline fragmentation, do not broadly discard baked lighting
or accepted geometry. A deterministic global rectangle repack may preserve
surface dimensions and lightmap content if it validates ownership, UV bounds,
gutters, page fields, written pages, and exact output invariants before and
after MOHlight.
## Cache revision 1: three-axis filtering and omission-first conversion

Cache is substantially denser than Cobblestone: the 45,755,859-byte decompile
contains 16,508 solids, 99,612 sides, 10,952 displacement sides, 7,643
entities, 4,170 ordinary prop placements, and 647 unique prop models. Its
486,323,964-byte Source BSP contains a 446,865,276-byte embedded pak.

An unchanged Cobblestone-style probe retained 14,099 brush entries because its
playable filter checked only X and Z. Cache has distant construction at
negative Y that overlaps the playable X/Z ranges. The corrected Cache filter
uses X, Y, and Z together and excludes 3,800 solids. The surrounding AA sky
shell uses complete retained-brush extrema rather than center cutoffs because
some accepted brushes extend to X 4,565 or Z 3,258.

Cache also proves that dedicated Source deathmatch spawns must be treated as
their own set. The decompile contains 20 Terrorist, 20 Counter-Terrorist, and
24 `info_deathmatch_spawn` entities. Revision 1 emits 20 Axis, 20 Allied, and
the actual 24 neutral DM spawns instead of duplicating both teams into a
40-spawn neutral set.

The first deterministic baseline emits 10,876 world-brush entries and 268
entities. It preserves 10,787 measured playable solids, planarizes 8,165
displacement sides, adds 83 material-matched terrain seam underlays, keeps 138
measured large clip volumes, and skips 1,379 small helper brushes. Static
validation reports zero invalid brushes.

The Source map has no autocombines, but its ordinary prop inventory is still
not permission to infer topology. Revision 1 explicitly omits 2,588 playable
prop placements. The single true `prop_door_rotating` is an exception because
its source entity intent, hinge origin, yaw, and embedded IDST-v49 hull bounds
are directly measured. It becomes one AA `func_rotatingdoor`; static prop
filenames containing `door` remain non-interactive evidence.

The modern palette contains 19 original 512×512 TGA surfaces. Three new
image-generated project sources provide industrial brick, weathered
plywood/planks, and cool blue-gray painted steel. Six project-owned sources
are shared from Nuke, five surfaces are procedural, and derived colorways
complete the set. All images are deterministically mirrored, stored-edge
verified, and documented; no Valve image bytes are packaged.

**PROVEN cluster-filter rule:** Source playable-space classification must use
all relevant axes, and the structural shell must enclose full retained-brush
extents rather than accepted centers.

**PROVEN spawn rule:** preserve a reference's dedicated deathmatch positions
as neutral spawns. Duplicate team spawns only as an explicit fallback when no
dedicated set exists.

Normal Q3map proved the first hard compile boundary. It merged 63,578 input
faces to 57,622, added 84,040 T-junction vertices, reached 314,846 total
vertices, and failed `MAX_MAP_DRAWINDEXES` after 11,057 seconds. An optional
source-budget probe retained 9,058 brush entries but still failed the same
limit after merging 52,576 faces to 47,381.

The complete 10,876-brush source compiled successfully with `-notjunc` in
10,895 seconds. This preserved all 57,622 merged faces but deliberately
skipped the insertion that overflowed AA's fixed index array. Fast VIS wrote
56 clusters, 97 portals, and 456 visibility bytes. Full MOHlight completed in
1,743 seconds with one potential hash warning and six entity-light leaf clamps
from 63-103 lights down to the engine cap of 60.

The lit BSP is 32,125,316 bytes with SHA-256
`653AEF5E9AE82FEA5FD68307CD67F1842E424DC611758875CB8EA779E16EE94C`.
The 23-entry PK3 is 10,127,241 bytes with SHA-256
`90477F688E4115400813B119A2061434A1F62324381B3CC864FA7BAB29084C53`.

A fresh OpenMoHAA home contained only this package and used a clean base with
only retail Pak0-Pak6. OpenMoHAA parsed the BSP in 0.180 seconds, generated
Recast navigation in 3.567 seconds, admitted eight bots, and logged 55 combat
events with zero Cache content/runtime error matches.

The original texture contact sheet passed visual art inspection. Automated
client capture was not usable: the targetable client produced only black
frames and its cursor, including after console/Escape checks. No map-view
visual gate is claimed. Human screenshot and door review must specifically
inspect T-junction cracks, because `-notjunc` is a technical fallback rather
than a proven visual-quality setting.

**OBSERVED draw-index fallback:** `-notjunc` can preserve a dense measured
brush set when normal T-junction insertion exceeds `MAX_MAP_DRAWINDEXES`.
Until representative in-engine edge views pass, it carries explicit
crack/seam debt and must not become the default compiler recipe.

## Inferno revision 1: authored air first, complete mass second

Inferno deliberately reversed the conversion-first workflow used for
Cobblestone, Nuke, and Cache. The reference decompile contains 7,921 solids,
2,223 displacement sides, 9,934 entities, and 6,974 static props. Roof caps,
window/shutter families, supports, trim, railings, vegetation, and terrain are
so prop-dependent that preserving ordinary brushes while omitting those
families would reproduce a measured but visibly incomplete result.

The VMF was therefore used only as route-and-scale evidence. Dedicated DM
spawns bound the likely playable cluster, and the classic Mid/Alt Mid/A,
Apartments, CT, and Banana/B roles informed the circulation graph. The
generator imports zero Source solids, props, and displacements.

Revision 1 defines 20 named combat areas on a 128-unit occupancy grid. A flood
fill proves all 362 playable cells connected. The 534-cell complement is
greedily merged into 21 complete building masses. Facades, 71 inset windows,
20 flat roofs, two gables, arches, stairs, site cover, fountain, coffins, and
bell tower are authored onto that closed massing. This is the central
structural guarantee: an omitted reference model cannot create a wall or roof
hole because non-playable space already exists as a complete solid volume.

An initial compile exposed a MOHAA-specific trap. Ordinary Quake
`func_detail` brush entities were silently stripped, leaving only the shell
and 81 faces. Re-emitting all required authored brushes into `worldspawn`
produced 464 compiled world brushes and 2,050 faces. The resulting map remains
small enough for ordinary BSP splitting, so no `-notjunc` or portal-budget
fallback is needed.

The art set contains 16 original 512x512 diffuse TGAs. Four Mediterranean
source images—cream plaster, cobblestone, terracotta roof tile, and brick—were
made with the built-in image-generation workflow. Four project-owned sources
were reused from Cache, and deterministic mirrored derivation supplied the
remaining variants. Stored-edge assertions guarantee the packaged textures
tile exactly. No Valve image or mesh bytes are included.

Ordinary Q3map emitted 2,050 of 2,052 input faces. Fast VIS completed in 1.0
second with 1,127 clusters, 4,086 portals, and 3,725 faces. Full MOHlight
completed in 3.0 seconds using ambient `8 9 11`. Seven interior light origins
produced non-fatal leaf diagnostics; the BSP entity lump retains all eight
light entities and full lighting succeeds.

The exact 19-entry, 4,670,179-byte PK3 has SHA-256
`30FBE96874CC8BB2ECA4C80B047CE67E2FA3E67EE42C5153D99222ACDC82B8A2`.
A fresh OpenMoHAA 0.82.1-beta+5 home backed only by retail Pak0-Pak6 parsed the
BSP in 0.008 seconds, built Recast navigation in 0.173 seconds, admitted eight
bots, and logged 15 combat deaths in the final short sample. Explicit health
box and bazooka-explosion caches removed all runtime precache suggestions.
The stock-only environment reports absent optional `global/bot_run.scr`, but
native bots demonstrably navigate and fight.

Automated Windows visual control was blocked by the local ACL sandbox, so no
human map-view gate is claimed. Revision 2 must begin from exterior, interior,
overview, transition, sightline, and map-edge screenshots rather than assuming
the structural/runtime proof also establishes visual polish.

**PROVEN authored-mass rule:** for an original layout, define connected
playable air first and make its complement complete solid architecture before
adding decoration. This prevents omitted reference-only assets from becoming
structural gaps.

**PROVEN compiler-count rule:** valid `.map` syntax does not prove brush
entities survived Q3map. Compare input and output face/brush counts whenever
changing entity/detail policy; required geometry belongs in a compiler form
proven by the target AA toolchain.

## Next generation-system steps

- Separate topology from theme so one layout can receive multiple material and
  prop sets.
- Add deterministic seeds and a JSON layout manifest.
- Add brush validation before compile: bounds, minimum thickness, plane
  orientation, spawn-to-solid tests, and sealed-world checks.
- Parse compiler output and fail automatically on leaks or invalid brushes.
- Add optional patch-based arches while retaining simple brush collision.
- Add a headless runtime smoke test and record navigation-build success.
- Generate several small layouts—courtyard, warehouse, and compact streets—and
  compare bot heat/traffic before spending time on final art.

## External references

- [OpenMoHAA repository](https://github.com/openmoh/openmohaa)
- [OpenMoHAA bot/configuration documentation](https://docs.openmohaa.org/md_docs_2markdown_203-configuration_201-configuration.html)
- [Valve Map Format displacement documentation](https://developer.valvesoftware.com/wiki/VMF_%28Valve_Map_Format%29#Dispinfo)
- [pstngh/moh-maps](https://github.com/pstngh/moh-maps)
- [pstngh/netradiant-custom](https://github.com/pstngh/netradiant-custom)
- [pstngh/MOHTools](https://github.com/pstngh/MOHTools)
- [MoHAA basic compile tutorial](https://mohaaaa.co.uk/mohaa/tutorials/basic_compile.php)
- [EA Allied Assault level editor archive page](https://www.moddb.com/games/medal-of-honor-allied-assault/downloads/moa-allied-assault-level-editor)

## Revision log

- 2026-07-24, revision 1: repository study, source-format model, corpus counts,
  first generator, successful AA compile, OpenMoHAA load, and Recast navigation
  smoke test.
- 2026-07-24, revision 2: full-data user playtest confirmed rendering, bot
  spawning, and traversal; recorded the first visual findings and underlighting
  correction target.
- 2026-07-24, revision 3: measured Dust II brush-layout translator, V2/stock
  material remap, final BSP/VIS/light compile, 40 neutral DM spawns, and
  successful OpenMoHAA Recast navigation generation.
- 2026-07-24, revision 4: diagnosed the black-void playtest failure, required
  retail shader data during compile, restored real sky and stock props, refined
  lighting/material fallbacks, and added in-engine visual QA.
- 2026-07-24, revision 5: analyzed the six-screenshot extended playtest,
  implemented thin-slab reconstruction for 61 playable displacement faces,
  restored real caulk, grounded or omitted incompatible prop substitutions,
  rebuilt the final PK3, and validated exact-package Recast navigation with two
  bots.
- 2026-07-24, revision 6: analyzed the eight-screenshot regression, corrected
  the car-origin inference, reconstructed every VMF displacement grid, proved
  that touching triangle prisms lose faces in AA Q3map, replaced them with 868
  joined and correctly wound patch meshes, omitted unsupported rooftop
  stand-ins, and verified continuous terrain in OpenMoHAA.
- 2026-07-25, revision 7: analyzed eleven additional screenshots, replaced raw
  quadratic patch controls with midpoint-expanded bilinear spans, reduced the
  terrain to 61 continuous meshes, backed 112 omitted facade-window props,
  grounded level car substitutions, omitted incompatible tilted cars and
  clutter, and validated the exact PK3 with four fighting OpenMoHAA bots.
- 2026-07-25, revision 8: analyzed eleven additional screenshots, restored 60
  displacement support hulls, layered 112 non-solid facade backings with 112
  decorative shutters, corrected the rock material and car Z placement, used a
  clean retail compile root, and validated the exact PK3 with eight fighting
  OpenMoHAA bots.
- 2026-07-25, revision 9: analyzed seven additional screenshots, sealed all
  moved displacement boundaries with 235 material-matched patch skirts,
  corrected rectangular AA patch dimension ordering, grade-snapped four rusted
  cars from verified retail TIKI bounds, and validated 296 meshes with eight
  fighting OpenMoHAA bots and eight automated viewpoints.
- 2026-07-25, lighting study: diagnosed revision 9's oversized global and
  spawn-fill lights, compared the retail AA multiplayer corpus, identified the
  Breakthrough reference as Monte Cassino, and recorded an original
  AA-compatible warm-sun/cool-fill direction for the next Dust II lighting
  build.
- 2026-07-25, revision 10: replaced the tan-wash lighting with an original
  warm-sun/cool-fill Mediterranean profile, removed all 20 spawn-following
  lights, translated 25 real Source fixtures into the AA intensity range,
  iterated against two eight-viewpoint OpenMoHAA runs, and validated the exact
  final PK3 with eight fighting bots.
- 2026-07-25, Cobblestone revision 1: measured Cache versus Cobblestone and
  selected the smaller reference; added ordinary BSPSource displacement
  reconstruction; diagnosed patch-time and 2 MiB portal limits; introduced a
  structural sky shell, planar displacement baseline, and volume-selected
  detail import; compiled 18,610 faces; and validated the exact final package
  with eight fighting OpenMoHAA bots across eight followed-player viewpoints.
- 2026-07-26, Cobblestone revision 2: diagnosed four user screenshots as a
  thin-architecture filtering failure; restored all 2,735 `func_detail`
  solids; measured and widened modular port replacements; added missing stone
  pillars; compiled 25,873 faces; and validated continuous interior/exterior
  architecture with two eight-bot OpenMoHAA runs.
- 2026-07-26, Cobblestone revision 3: analyzed nineteen screenshots; removed
  299 unsafe architectural-model guesses; repaired exposed mixed-brush nodraw
  faces; grounded retained props against planar displacement supports; added
  verified stock window glass and source-family stone mappings; and repeated
  isolated visual and eight-bot QA.
- 2026-07-26, Cobblestone revision 4: analyzed nine additional screenshots;
  distinguished planar XY seams from exposed nodraw faces; added bounded
  material-matched terrain underlays; preserved measured large Source clip
  volumes; omitted vegetation that could not be grounded safely; completed
  Q3map/VIS/MOHlight and exact-package eight-bot QA; documented four lighting
  hash warnings; disproved complete containment; and verified byte-identical
  source regeneration.
- 2026-07-26, knowledge-system revision: separated the mandatory production
  workflow from this chronological evidence log; added repository-level
  instructions, a documentation index, a verified stock-AA asset catalog, a
  repeatable map-revision report, explicit evidence labels, and release gates
  so future map work starts from the strongest proven process.
- 2026-07-26, Nuke preproduction: audited the VMF, Source 1 VPK, and BSP
  embedded pak; resolved all 121 visible materials and all 1,405 referenced
  models; identified 710 BSP-only autocombines and four functional-door
  candidates; separated the likely playable/skybox clusters; and created a
  provenance-recorded fourteen-material original clean-industrial palette.
- 2026-07-26, Nuke revision 1: generated a deterministic full-layout map,
  compiled BSP/VIS/full lighting, packaged fourteen original textures,
  preserved four functional door entities, validated the exact PK3 with eight
  fighting bots, and promoted dense-Source-fixture budgeting into the shared
  playbook.
- 2026-07-26, Nuke revision 2: analyzed twenty user screenshots; added
  measured terrain underlays, a neutral stock sky, original window backing,
  lighter glass, clustered fixtures, and bounded nonblocking templates for 419
  embedded-model placements; rejected an over-dense one-hour compile;
  discovered and fixed the 180-lightmap MOHlight limit with vertex-lit
  cosmetic detail; completed Q3map/VIS/full lighting; and validated the exact
  19-entry PK3 with eight bots and 60 combat events.
- 2026-07-27, Nuke revision 3: analyzed thirteen rejection screenshots;
  disproved aggregate-hull topology inference and broad vertex-lighting as
  defaults; removed all 803 inferred fills and 6,126 `nolightmap` sides;
  restored explicit omission of all 710 autocombines; added permanent
  validators and shared playbook rules; completed Q3map/VIS/full lighting with
  normal lightmaps; and validated the exact 19-entry PK3 with eight bots and
  119 combat events.
- 2026-07-27, Cache revision 1: audited the playable Source cluster; preserved
  10,787 measured solids, one verified rotating door, and 64 multiplayer
  spawns; bundled nineteen original clean-industrial textures; rejected an
  ineffective reduced-detail compile probe; compiled the complete
  57,622-face layout with a documented `-notjunc` draw-index fallback;
  completed VIS/full lighting; and validated the exact 23-entry PK3 with eight
  fighting bots while retaining explicit crack/seam and human-visual debt.
- 2026-07-30, Inferno revision 1: rejected direct Source conversion; authored a
  connected 20-area occupancy layout and 21 complete building masses; created
  sixteen original Mediterranean textures; discovered that ordinary Quake
  `func_detail` brush entities are stripped by MOHAA Q3map; completed ordinary
  BSP/VIS/full lighting; and validated the exact 19-entry PK3 with Recast and
  eight fighting bots while recording the pending human visual gate.
- 2026-07-30, Inferno revision 3: restored and audited the original CS:GO BSP,
  VPK, radar, overview metadata, and private VMF; aligned the authored plan to
  the official radar; replaced rejected graph-edge extrusion with 455 complete
  callout-zoned village masses and 26 gable roofs; corrected fountain/well
  scale from parsed model envelopes; completed Q3map/VIS/full lighting under
  the original BSP budget; and validated the exact PK3 with eight fighting
  bots while retaining the human visual gate.
- 2026-07-30, Inferno revision 4: recorded the user's complete visual rejection
  of inferred massing; directly converted 5,533 playable VMF brush solids;
  planarized 1,969 displacement sides; omitted 6,200 unverified props;
  translated one measured door and 55 clustered lights; completed a documented
  `-notjunc` BSP, VIS, and full-light build; and validated the exact PK3 with
  Recast plus eight fighting bots while preserving human recognition and
  nominal BSP-budget debt.
- 2026-07-30, Nuke revision 4: recorded the user's "very empty" verdict;
  inventoried 4,687 playable model placements; restored 1,932 ordinary
  instances with 2,855 family-specific brushes and seven new original
  materials; retained all 710 autocombines as omissions; compiled 47,591
  faces; proved a deterministic 194-to-166-page lossless lightmap repack while
  preserving 42,815 baked surfaces; completed full lighting; generated fifteen
  renderer screenshots; and validated the exact 26-entry PK3 through three
  Recast/eight-bot match cycles and 263 combat events.

## Inferno revision 2: measured clone after a rejected invented layout

Date: 2026-07-30

The user's first screenshots of Inferno revision 1 proved a brief failure: the
map was a complete, playable Mediterranean arena but was not recognizable as
Inferno. The error was semantic, not merely visual. "From scratch" had been
misread as permission to invent an Inferno-like route graph.

Revision 2 retained original target-engine authorship but measured the actual
supplied VMF. Plane intersection reconstructed all 7,921 solids with zero
failures. A naive floor projection still contained rooftops and exterior pads,
so the audit added spatial collision buckets, player-headroom rejection,
neighbor-transition collision tests, and a 107-spawn flood fill. The resulting
blueprint contains 6,997 connected 32-unit cells, 13,420 permitted edges, and
zero unmatched spawns. It clearly recovers T west, A southeast, CT east, and
Banana/B north.

The generator greedily merges cells by elevation/material role into 479 floor
rectangles. It creates facade/wall geometry only on graph edges without a
permitted transition. Wood-route components receive 77 ceiling rectangles.
Measured landmark positions drive the B fountain, coffins/barrels, A hay/box
cluster, major arches, balconies, and tower silhouette. No Source brush or
asset is shipped.

The first structural compile failed with `LoadPortals: NumVisBytes 4116968
exceeds 2097152`. The proven six-brush structural shell plus MOHAA
`+surfaceparm detail` on internal worldspawn geometry reduced VIS to 36
clusters, 60 portals, and 296 bytes. The initial faithful facade build was
12.81 MB against Q3map's 10 MB budget. Merging facade materials/heights and
removing short redundant trim/roof splits reduced it from 3,595 to 2,683
brushes and from 20,827 to 15,717 draw surfaces without changing the measured
floor graph. Final Q3map `-info` reports 9.69 MB used.

Full lighting completed with ambient `8 9 12`. In a fresh home backed only by
retail Pak0-Pak6, OpenMoHAA parsed the exact packaged BSP in 0.054 seconds,
built Recast navigation in 1.916 seconds, admitted eight bots, and logged 8
combat deaths in 38 seconds with zero fatal errors.

**PROVEN brief rule:** a completed playable map can still be the wrong output.
When recognition is part of the request, topology fidelity is a release gate.
Persist a rejected revision as evidence, replace its public generator entry
point, and do not call later polish a continuation of that baseline.

### Inferno revision 2 human-review rejection

The user's `shot0021.tga` overview invalidated revision 2 as a fidelity
baseline. Although the recovered walk footprint looked plausible in a clean
2D plan and the exact PK3 passed compile, Recast, spawn, and combat tests, the
rendered map remained unrecognizable.

The screenshot shows why: 1,058 merged boundary-wall runs, 112-unit exterior
mass depth, and 294 short roof caps form a dense hollow maze. Inferno's broad
continuous streets and complete village blocks are replaced by fragmented
parallel strips, internal sky gaps, and noisy sampled elevations. Landmark
props cannot repair architecture whose massing and street composition are
wrong.

**FAILED method:** collision-grid boundary extrusion is not an architectural
reconstruction strategy. Keep the 6,997-node/13,420-edge graph only as a
connectivity oracle. The replacement must hand-author each major callout as a
coherent scene, fill bounded non-route regions with complete building masses,
and use the graph afterward to verify that openings and elevations remain
faithful.

## Inferno revision 3: route oracle plus complete semantic massing

Date: 2026-07-30

Restoring the CS:GO game files supplied a stronger private reference set than
the VMF alone: the original BSP, VPK index, embedded pak, radar DDS, and
overview transform. The VMF contains 7,921 reconstructed solids, 9,934
entities, 6,974 static props, 2,252 detail entities, 82 unique visible
materials, and 308 unique model paths. Every visible VMT and model path
resolved in the restored data. None of those commercial bytes is committed or
packaged.

The overview transform (`pos_x -2087`, `pos_y 3870`, `scale 4.9`) provides an
independent macro-layout check. When the semantic plan is placed in that frame,
its route footprint and T/A/B/CT anchors align with the official radar. This
supports topology/scale, but cannot prove elevations, wall composition,
interiors, or ground-level recognition.

Revision 3 keeps all 6,997 connected walk cells and 13,420 transitions only as
a connectivity oracle. It dilates the route footprint by ten cells,
flood-fills exterior air, fills bounded non-route pockets, assigns semantic
height/material zones for every major callout, and greedily merges the result
into 455 complete village masses. It renders zero outdoor graph-edge wall
runs, retains 222 measured indoor separation runs, and caps the village with
455 roofs including 26 gables. The output is 1,805 brushes rather than revision
2's 2,683 fragmented brushes.

Parsed model envelopes supplied a safer hero-landmark scale check. The B
fountain basin measures about 156 units in radius, the center about 43 units in
radius and 133 units high, and the CT well about 59 units in base radius with a
roughly 104 x 147 x 141 wood assembly. Revision 3 uses original AA-native
brush substitutes at those measured origins/dimensions. The audit also proves
one real Source rotating door, but does not yet prove an AA pivot/swing/bot
implementation; the route remains open in this revision.

A clean retail compile emitted 10,457 faces from 10,824, fast VIS used 36
clusters and 296 bytes, and full MOHlight completed in 73 seconds. Q3map
`-info` reports 7.45 MB of the original 10 MB budget. OpenMoHAA loaded the
exact 19-entry PK3, parsed the BSP in 0.035 seconds, generated Recast in 0.611
seconds, admitted eight bots, and logged 11 combat/death events with zero fatal
map errors.

**PROVEN method:** a collision graph and an official radar solve different
parts of recognition. Use the graph to preserve passability and openings. Use
the radar/overview transform to check macro scale, outline, and callout
relationships. Author complete buildings, streets, and silhouettes separately
at human-perceived scale, then require ground-level screenshots before
acceptance.

**PENDING visual verdict:** this revision is a playable recognition candidate,
not a claimed release. Facade windows, several slopes/roof shapes, omitted
Source-only props/displacements, and the one dynamic door remain explicit debt
until the user supplies a new screenshot pass.

## Inferno revision 4: direct VMF architecture after massing rejection

Date: 2026-07-30

The user's screenshots `shot0022.tga` through `shot0038.tga` rejected revision
3 more strongly than its predecessor. The route-aligned village dilation
created broad, nearly uniform roof fields around trench-like passages. The
method reproduced neither Inferno's facade composition nor its courtyards,
openings, and skyline. This proved that a semantic zone label plus a measured
route graph still does not contain enough information to infer architecture.

The user explicitly authorized direct conversion from the original VMF.
Revision 4 therefore reconstructs convex Source solids from their planes and
emits all playable world, `func_detail`, `func_brush`, and `func_breakable`
architecture. It preserves 5,533 source solids with zero invalid conversions.
A structural sky shell plus internal `+surfaceparm detail` controls portals.
The distant 3D skybox and 632 brushes are excluded; 1,476 helper-only brushes
are excluded while verified player/large clips remain.

Source raster/model assets are still not packaged. Material roles map to the
original project-owned Inferno texture palette. The generator planarizes 1,969
displacement-bearing sides and audits 6,200 unverified model props as omitted.
It translates all 20/20/67 team/DM spawns, clusters 75 playable light
candidates into 55 AA lights, and creates the one verified 90-degree rotating
door from its parsed local bounds. A clean temporary run reproduced the MAP,
both scripts, and machine-independent conversion report byte-for-byte.

The full direct MAP contains 5,696 world brushes. The ordinary compiler was
manually stopped after more than five CPU minutes with no actual error;
revision 4 then used the already documented `-notjunc` fallback to preserve the
architecture for visual review. That build completed in 1,910 seconds with
24,633 faces from 28,310 inputs. VIS produced 49 clusters/400 visibility bytes,
and full MOHlight completed in 222 seconds. Q3map `-info` reports a valid
14,221,508-byte BSP using 12.34 MB against the old nominal 10 MB display.

OpenMoHAA parsed the exact 19-entry PK3 BSP in 0.097 seconds, generated Recast
in 3.858 seconds, admitted all eight bots, and logged 23 combat/death events
with zero fatal map errors.

**PROVEN escalation rule:** after multiple measured/inferred reauthoring passes
remain unrecognizable, and the user authorizes direct conversion, preserve the
playable brush architecture first. Do not optimize away source classes until a
human visual gate establishes which geometry is essential. Route graphs and
radar alignment become validators only. Compile duration without an error is
not itself a geometry failure; document the duration and use a proven fallback
when necessary.

**PENDING visual verdict:** direct conversion maximizes geometric evidence but
does not automatically solve displacements, model props, material translation,
lighting, moving-door behavior, or T-junction cracks. Those are explicit
follow-up classes after the user confirms recognizable callouts.

## Inferno revision 5: measured structural prop fill

Date: 2026-07-30

The user's screenshots `shot0039.tga` through `shot0051.tga` described revision
4 as “much better.” Streets, roofs, stairs, openings, courtyards, and site
massing were recognizable, so direct VMF brush conversion became the accepted
geometry baseline. The same views exposed a different failure class: empty
window and door openings, hollow facades, sparse sites, and missing roof trim,
supports, pillars, chimneys, fountain/well pieces, and ordinary cover.

The private Inferno input references 7,036 model instances and 308 unique model
paths. A reproducible VPK/BSP/MDL audit resolves and parses all 308 IDST version
49 headers. Revision 5 persists only metadata—model paths, reference counts,
local hull bounds, versions, and source fingerprints—in
`inferno-model-bounds.json`; no commercial model, texture, sound, radar, BSP,
VMF, VPK, or embedded-pak bytes enter the repository or PK3.

Revision 5 leaves all 5,533 accepted source brush solids unchanged. It evaluates
the 6,200 playable prop candidates against measured bounds and conservatively
substitutes 1,176 high-impact instances with 1,431 authored brushes. The fill
includes windows, shutters, doors and frames, arches, roof surfaces, pillars,
chimneys, wood and balcony supports, barrels, crates, hay, coffins, the B
fountain, and the CT well. Every placement records its source model path,
origin, angles, scale, and emitted brush count.

A direct brush-stream comparison proves that rev5 preserves the complete rev4
foundation: the first 5,696 world brush blocks in both maps have the same
normalized SHA-256,
`2B3EB8EC13E6C9B229C842D98E446C22FEE53DA62103C1861233170C4BD56CDB`.

Facade, roof, trim, and structural-detail substitutes are non-solid so an
approximation cannot close a route. Collision is limited to measured gameplay
cover and simple landmark bodies. Four duplicate multi-part landmark records
are deliberately collapsed into their shared physical assemblies. The
remaining 5,024 props—principally irregular meshes, foliage, wires, vehicles,
and cosmetic clutter—remain explicitly omitted.

The first generated candidate exposed a generator syntax defect before any
geometry diagnosis was attempted: three helper functions joined brush lines
with a literal `\n` escape sequence. Q3map reported `Line 51753 is incomplete`.
Changing those helpers to emit actual newline characters repaired the MAP.
This adds a reusable preflight rule: generated maps must check balanced braces
and reject literal escaped newlines before launching a long compile.

The next full geometry pass completed in 3,815 seconds with 33,441 faces
from 37,116 inputs and zero stderr diagnostics. It was nevertheless rejected
before promotion: the isolated stage contained no authored Inferno images, and
Q3map reported thirteen `Couldn't find image` warnings. Because fallback image
dimensions can bake the wrong texture scale, a valid BSP is not sufficient.
The candidate BSP was discarded, all sixteen authored textures were copied and
hash-checked against the canonical set, and the BSP compile was repeated.

**PROVEN stage-parity rule:** verify custom texture filenames, counts, and hashes
inside the exact compile root before BSP generation. Missing-image warnings are
a failed visual build, even when Q3map emits a geometrically valid BSP.
The corrected texture-complete pass compiled 33,439 faces from 37,116 inputs
with 3,677 removed in 3,841 seconds and no warning/stderr error. Fast VIS kept
49 clusters and 400 visibility bytes. Full MOHlight finished in 339 seconds
without a warning or stderr error. Q3map `-info` reports 6,971 brushes, 33,445
draw surfaces, 108 lightmaps, 55 entity lights, and a valid 16.55 MB BSP—6.55
MB above the legacy nominal display.

The deterministic 19-entry PK3 loaded in isolated OpenMoHAA 0.82.1. BSP parse
took 0.127 seconds, Recast generation took 5.444 seconds, all eight bots joined,
22 combat/death events occurred, and no fatal map error appeared. The test
server was stopped afterward. This proves technical playability, not the
visual correctness of approximate substitutes.

**PROVEN staged-fill rule:** once direct architecture passes human recognition,
repair its measured structural prop layer without rewriting the brush
foundation. Derive placement from parsed bounds plus entity transforms, keep
approximate facade/roof art non-solid, grant collision only to clearly measured
cover, count every substitution, and preserve the omitted set. Metadata and
compile/runtime gates still do not prove the visual result; a new screenshot
pass remains mandatory.

## Nuke revision 5: CS2 topology-backed local pilot

Date: 2026-07-31

The user's revision-4 feedback asked for CS2 over CS:GO whenever possible and
for Nuke's missing machinery, objects, and clean modern appearance to be
restored. A local CS2 installation contains
`game/csgo/maps/de_nuke.vpk`; its SHA-256 is
`616286bdfba283f8026cb719321e4c2d0986f04ce925cb13b0ff7ff913c33007`.
The accompanying `pak01_dir.vpk` SHA-256 is
`f9c82be3724ee2938ef8b1538efb56b7bc252800d47d00c5da32d214ca8e7f4f`.
These commercial inputs and every derived mesh/image/package payload remain
local and ignored.

ValveResourceFormat CLI 19.2 was pinned by archive SHA-256
`53e7e8dac1ddd876078346de709c8dbe613a967e94cd0c969aa34c61ec07680d`
and executable SHA-256
`36d8c9208eefa61dd695bd577e49618bb161569941318f629294a4e4af00edc0`.
Its per-resource GLB export emits shader bytecode-version warnings because this
release recognizes versions 59-70 while the local files contain version 71.
For the selected resources it nevertheless exits zero and emits the requested
GLB plus base-color images. The pipeline therefore treats that warning as
nonfatal only when the requested output exists and passes subsequent parsing
and compiler validation.

Applying the complete glTF node transform and then mapping
`[gltf.z, gltf.x, gltf.y] / 0.025399996` produces bounds identical to the
original Source world coordinates for inspected `agg_merge` and
`agg_nomerge` world-node resources. Their models are correctly placed at
MOHAA origin zero. Inspected `agg_prop` resources instead have instance-local
bounds; a control display and forklift-wheel group appeared around their local
origins rather than their Nuke world positions. Those resources are marked
`requires-instance-transforms` and excluded rather than incorrectly stacked at
the map origin.

The retail static converter writes SKD v5 `SKMD`, SKC v13 `SKAN`, and TIKI.
Each SKD has one POSROT `ORIGIN` bone parented to `worldbone`; vertices carry
one full-weight root influence. Surfaces split at 999 vertices and 1,999
triangles. The first original-Q3map probe crashed with exit
`-1073741819`: although an older OpenMoHAA writer suggested otherwise, the
original loader requires two zero-filled int32 collapse arrays after each
surface's variable vertex/triangle data. Adding them fixed the crash. The next
probe exposed a separate binding failure at a 32-character surface name.
Limiting generated TIKI/SKD identifiers to 28 characters removed that
failure. One isolated map then loaded all twelve pilot models with Q3map exit
zero and no fatal or surface-binding diagnostic.

A follow-up extended-tier probe found a third independent retail limit. The
large airduct aggregate becomes 224 surfaces after enforcing 999 vertices and
1,999 triangles per surface. Q3map's TIKI parser allocates only 24 setup-
surface records (`dloadsurface_t loadsurfaces[24]`) and does not bounds-check
before adding another. At surface 25 the array overflow eventually presents as
`Too many skins defined` on otherwise unique surface names and then crashes
with exit `-1073741819`. The converter and inspector now reject a single TIKI
above 24 surfaces, and the airduct resource is classified
`requires-model-partitioning`. Before the two related catwalk resources were
combined into one TIKI, the remaining three extended roof-HVAC resources plus
the pilot produced 15 definitions and 13 textures; one combined original-Q3map
proof wrote exactly 15 unique origin-zero static-model BSP definitions and
reported no unexpected warning. This is historical format/loader evidence,
not the current manifest's model count.

The expected loader output contains one old-animation-format downgrade per
static model and missing `models/.../*.map` collision-helper warnings. These
are accepted for this pilot because the SKC cross-loaded with a known retail
crate, all model surfaces bind, and the existing measured Source brush/clip
layer remains the sole collision authority.

The local payload retains topology from twelve world aggregates covering
forklift bodies, forks and wheels; cargo-crane bases, carts and winches; the
B-site reactor vessel head; catwalk decks and supports; control-room tables;
and merge-safe control-display geometry. The two related catwalk resources are
combined into one TIKI, so the final manifest contains eleven models and eleven
unique referenced base-color images. Ten are static-lit; the control-room table
is retained as a runtime `script_model`. The manifest suppresses only 23
explicitly covered Source 1 brush-proxy instances and deliberately keeps
control-display proxies not proven covered by the world-space meshes.

All twelve material bindings in that composition are `OPAQUE`, single-sided,
and reference a base-color image. Direct TGA bindings therefore do not hide an
unimplemented alpha-test/double-sided shader case for this pilot.

The enhanced local MAP contains 9,407 world brushes and 340 entities, including
all four rotating doors, 16 Axis spawns, 16 Allied spawns, and 32 neutral DM
spawns. A top-level entity comparison proved that all four
`func_rotatingdoor` blocks and the complete 32/16/16 neutral/Axis/Allied
spawn sets remain byte-identical to the public revision-4 generation.
It is 8,151,345 bytes with SHA-256
`F89E7C99B2BC3AE501E06EA76982EE60D27BE778E8646D0AE1138815650934A7`
and retains 2,814 family-specific fidelity brushes after suppression. Without
the manifest, regenerating the public MAP reproduces the revision-4 SHA-256
exactly:
`5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040`.

A full VRF identifier listing counted 806 `vmdl_c` entries in the CS2 Nuke
container: 238 `agg_merge`, 41 `agg_nomerge`, 73 `agg_prop`, 353 other world-
node entries, 100 entity entries, and one world-physics entry. This changes the
next-pass strategy from guessing individual props to ranking the 279 merge/
nomerge world aggregates, then proving coordinate space and retail surface
count per candidate.

Ten high-impact candidates were exported and converted in a local-only probe.
Six stayed below the 24-surface TIKI limit: tank-top geometry (5 surfaces,
5,208 triangles), ventilation exhausts (9/3,476), office desks (15/10,796),
metal ladders (18/17,716), window assemblies (11/3,230), and the secondary HVAC
duct set (10/4,194). Original Q3map loaded all six together, wrote six unique
origin-zero BSP static-model definitions, and emitted only the six expected
animation-downgrade plus six missing optional collision-helper warnings. Silo
sets 1 and 2 require 25 and 27 surfaces; office chairs require 41; the large
roll-up-door group requires 53. Those four are not malformed assets: they are
measured inputs for a future converter feature that partitions one Source 2
resource into multiple <=24-surface TIKIs.

The hardened local pipeline also rejects empty/broad proxy-suppression
patterns, noncanonical per-ID TIKI paths, duplicate BSP model definitions,
non-finite transforms, and custom local output roots anywhere inside the Git
worktree except the exact ignored `.local-source2` root. Package creation sorts
entries, fixes ZIP timestamps, rejects duplicate/traversal names, and re-hashes
every decompressed entry against its staged source before promotion.

A converter audit found that a multi-GLB assembly originally resolved every
material image relative to the first GLB. The current catwalk pair shares one
export directory, so its pixels were already correct, but that assumption was
not reusable. Conversion manifests now retain each material's source-GLB index;
the texture stage resolves that exact source and rejects target-shader name
collisions with different pixels. A two-GLB catwalk regression retained source
indices 0 and 1, converted both textures, and reproduced the accepted
SKD/SKC/TIKI hashes byte-for-byte.

Local validation now treats `texture-conversion.json` as authoritative rather
than checking names alone. All eleven canonical/staged TGA hashes pass; a
temporary one-byte mutation of `catwalk_support_001.tga` was rejected with a
base-color hash mismatch and the test fixture was restored.

The first full local compile completed geometry in 5,998 seconds and VIS with
154 clusters/3,704 bytes, but it was rejected before lighting. Its isolated
compiler root contained zero retail PK3 files, so Q3map could not resolve five
stock shader images: common clip, caulk, playerclip, the `sky/m5l2` sky, and
origin. Fallback shader dimensions produced 22 lightmapped caulk/sky surfaces
whose 128-pixel width could not retain the repacker's mandatory one-pixel
border. This is stage-parity failure, not an atlas-packing exception; the
pre-repack BSP remains local negative evidence and is not packaged.

The corrected builder requires an Allied Assault root with Pak0-Pak6 and
stages hard links (copy fallback) into its ignored `main` compile directory.
A short original-Q3map proof then loaded 18,294 files from the seven packs and
resolved both `common/caulk` and `sky/m5l2` with no missing-image warning. The
full compile must be repeated because fallback dimensions may already have
changed UV/lightmap allocation; reusing the rejected BSP would violate the
proven stage-parity rule.

The promoted `-PreflightOnly` path now runs that retail resolution check plus
one combined Q3map/VIS/MOHlight probe containing every manifest asset. On the
final composition it completed in eight seconds, wrote exactly ten Source 2
static definitions, and lit exactly 71,507 of the enforced 75,000 static-
vertex budget before allowing the long full-map compile.

The corrected full Q3map pass then completed in 5,572 seconds against all
18,294 retail-pack files. It reduced 50,407 input faces to 47,329 output faces
(3,078 removed), emitted exactly ten expected animation-downgrade and ten
missing optional collision-helper warnings, and emitted zero unexpected
warnings. Fast VIS reproduced 154 clusters, 283 portals, and 3,704 visibility
bytes. The lossless atlas repack retained 42,559 lightmapped surfaces and
1,457,986 exact texels, reducing 192 initially allocated pages to 165 with a
one-pixel gutter. Prelight BSP inspection found 47,353 total draw surfaces,
ten unique static Source 2 definitions, 43 static-model indexes, and no
unexpected non-lightmapped surface.

A later original-MOHlight isolation found a fourth, independent retail limit.
Ten models with 68,570 post-split vertices succeeded and wrote 207,382 bytes of
static-model light data. Eleven models with 75,555 vertices also succeeded at
228,513 bytes. Adding the twelfth model raised the set to 81,002 vertices and
crashed MOHlight with access violation `-1073741819`. This was not a definition-
count ceiling: twelve unique lightweight definitions totaling 10,464 vertices
succeeded and wrote 33,360 bytes. Lossless welding of vertices with identical
position, normal, and UV reduced the complete set to 76,733 vertices, but it
still crossed the buffer boundary.

The hardened builder therefore totals `verticesAfterSplitting` from every
static conversion manifest and rejects totals above a conservative 75,000-
vertex ceiling before long Q3map. The final Nuke composition statically lights
10 models / 71,507 vertices / 63,724 triangles and retains the 5,226-
vertex control-room table as a runtime `script_model` with `testanim idle`.
The exact all-static probe succeeded with 216,227 bytes of model-light data and
112 vertices in solid leaves. All 67,766 converted triangles remain present;
brush/clip geometry remains collision authority.

Q3map `-onlyents` cannot apply this classification change. A disposable probe
showed that it updated the entity text but retained the stale 11-definition
static-model lumps; a full Q3map pass on the same MAP correctly produced ten.
Any switch between `static_*` and `script_model` therefore requires full Q3map,
not an entity-only shortcut.

An isolated OpenMoHAA probe then exercised the ten-static/one-runtime
composition. The first run loaded the control-room table but requested an
explicit `_precache.scr` entry. The generator now emits one `cache
models/.../*.tik` line per runtime manifest asset, and the validator rejects
missing, duplicate, or static-model cache lines. With that line present,
OpenMoHAA loaded the table's SKC with only the expected old-animation downgrade,
reported no source-model TIKI/Skeletor or precache error, initialized the map,
generated Recast in 0.035 seconds, and admitted `bot1`.
The probe used OpenMoHAA `0.82.1-beta+5.a72bc15`; `omohaaded.exe` SHA-256 was
`DDB7D12666560701D914FF0D26B5082D686C1CC027407A929FB4950D24FBDAFB`.

Renderer-source inspection then found a runtime-only lighting defect in that
otherwise valid probe: `R_SetupEntityLightingGrid` samples at
`ent->e.origin`. The table mesh contained world-space vertices around
`(1066, -512, -620)` but its `script_model` origin was zero. The converter now
supports deterministic bounds recentering for runtime aggregates. The table's
source bounds are
`[1047.9999237060415, -616.1351289748931, -640.0000729859001]` through
`[1084.0952640683483, -407.86458730104613, -599.805411346164]`; its emitted
entity origin is
`[1066.047593887195, -511.99985813796957, -619.9027421660321]`, and its local
bounds are
`[-18.047670181153535, -104.1352708369235, -20.097330819868034]` through
`[18.047670181153308, 104.13527083692344, 20.097330819868148]`.
Adding the local bounds to the entity origin reconstructs the source bounds
exactly. Static aggregates remain origin-zero. The recentered table's SKD,
SKC, and TIKI SHA-256 values are respectively
`FC06596696659F051A98D7C75AD2E31DCE031FF67BAD4F4ABEC1BE6375D0DBAA`,
`BF5E5124DCF9E4C5EFC88D874C26CA3427627B69E106C357DE7819CDC7582FE5`,
and
`CA53FF4F6EECD3CA3961FA06732FC75A81010E71268E109FA719D0FF302ED5BA`.
A fresh exact 70-entry probe PK3
(`492FF7F6144397B9191BC3E93398F5558CA3BD97346721F232B42EF578B822A5`,
9,541,281 bytes) then loaded this recentered table, initialized the server,
generated Recast in 0.035 seconds, and admitted `bot1`, with zero
table-specific TIKI/Skeletor/precache diagnostics. This OpenMoHAA Windows
build writes its ordinary engine console to the process stderr stream, so
stderr byte count is not itself an error gate; classify fatal and
asset-specific diagnostics from the combined console content.
The BSP inspector now requires the runtime model's exact origin and can hash
all 27 non-entity version-19 lumps across an entity-only update. A wrong-origin
negative and a one-byte shader-lump mutation were both rejected; an identical
comparison passed. The strengthened retail/all-model preflight then repeated
original Q3map, VIS, and MOHlight in six seconds and accepted the exact runtime
origin alongside ten static definitions and 71,507 static vertices.

The corrected production build then completed original Q3map in 5,572 seconds,
VIS in under one second, and original MOHlight in 4,749 seconds. Q3map reduced
50,407 input faces to 47,329 output faces, with exactly ten expected
old-animation downgrades and ten missing optional collision-helper warnings.
VIS wrote 154 clusters, 283 portals, and 3,704 bytes. The deterministic atlas
repack retained 42,559 lightmapped surfaces and reduced 192 pages to 165.
MOHlight lit ten models / 71,507 vertices, found zero static-model vertices in
solid leaves, wrote 216,247 bytes of model-light data, and clamped 28 dense
entity-light leaves to the retail limit of 60.

After that full lighting pass, only the already-proven runtime table origin
changed. Q3map `-onlyents` produced final BSP SHA-256
`150E6E27A3969493706130C82591E27E346E52CB7426D8F3F490CB207F9A7CF0`
at 31,279,504 bytes. The inspector found the exact table origin, ten static
Source2 definitions, 165 lightmap pages, and byte-identical hashes for all 27
non-entity lumps versus the pre-update lit BSP. This is the narrow condition
under which an entity-only pass is safe.

The deterministic packager exposed two reusable PowerShell/ZIP traps. Raw
hashtables do not provide stable named-property grouping for `Sort-Object` /
`Group-Object`; package records must be `PSCustomObject` instances. ZIP's DOS
timestamp preserves calendar fields but not a UTC offset, so reopen
verification must compare the stored `DateTime` fields rather than direct
`DateTimeOffset` equality. After both fixes, two package builds reproduced the
same 70-entry, 14,877,947-byte PK3 with SHA-256
`5391F57425E3E27F271876F90E42433EF58DE369A3B11F23D8A2B379DE2B7C0D`.
Every decompressed entry was re-hashed against its staged source.

The first sustained eight-bot run requested two additional stock assets not
covered by retail `DMprecache.scr`: `models/items/dm_50_healthbox.tik` and
`models/fx/bazookaexplosion_dm.tik`. Those exact cache lines now come from the
generator. The rebuilt package then ran for 180.591 seconds in an isolated root
containing exactly Pak0-Pak6 plus the one candidate. OpenMoHAA completed two
server/map cycles, parsed the BSP in 0.157 and 0.183 seconds, generated Recast
in 17.136 and 17.304 seconds, admitted all eight bots twice, and logged 154
combat/death events. Candidate-specific Source2 model, table, fatal-map, and
precache diagnostics were all zero. The retail-only environment's missing
`global/bot_run.scr` messages were recorded separately because the bots still
navigated and fought; do not misclassify unrelated stock-environment warnings
as candidate failures.

**PROVEN local-topology rule:** keep commercial payloads behind an ignored,
opt-in manifest; pin the extraction tool and inputs; classify aggregate
coordinate space before placement; prove the exact retail model encoding with
original Q3map; preserve accepted brush collision; suppress only named proxies
covered by a present replacement; prove deterministic packaging and exact
isolated bot runtime; and prove that the redistributable public build is
byte-identical when the manifest is absent. Compile and model-loader success
still require a new human screenshot verdict before visual fidelity is claimed.

## Codex Reactor revision 1: original close-range bot arena

Date: 2026-08-08

The requested follow-up was a Nuke-inspired map authored from scratch for
close-range bot action, with lanes broad enough to avoid becoming a corridor
maze. `codex_reactor` is therefore an original 3,072 by 2,560-unit industrial
arena rather than another Source conversion. Its 132 brushes form an open
loading yard, three wide reactor-hall entrances, two lower service loops, a
rear crossover, two 224-unit stairs, and an upper U-shaped combat loop. The
declared route graph contains eight zones and 17 connections; its minimum
declared width is 192 units, while the main lower openings range from 256 to
416 units. It deliberately has no moving doors. Twenty neutral DM starts, ten
Allied starts, ten Axis starts, and one intermission/start entity distribute
combat across both floors.

The generator owns the source layout and copies 16 clean, project-owned
industrial TGAs from the earlier `codex_nuke` art set. No Valve geometry,
texture, model, or other asset bytes enter the package. Two clean generation
roots reproduced the canonical MAP byte-for-byte: 90,402 bytes with SHA-256
`889A84E7A4A7712502AB9B186AC27760100A197168386B6D6025BB606055339F`.
The validator checks structural brush closure, material names, spawn clearance,
route width, route connectivity, and source counts before compilation.

Validation caught two spawn boxes intersecting the broad stair volumes and
moved them to clear floor positions. The first compile also exposed five faces
using an undefined control-panel material alias. Replacing the alias with the
generated panel material removed those warnings. Sixteen high indoor point
lights were then reported as leaking by original Q3map. Controlled variants
showed that the same layout at z=200 compiled without the diagnostics, so the
generator now pins the affected origins to that proven height instead of
silencing the compiler output.

The first fixed-camera visual survey found two spatial problems that numeric
validation did not: a decorative center pier split a 320-unit front entrance
into cramped lanes, and the lower service loops were unreadably dark because
their main fixtures sat above solid mezzanine slabs. The pier was removed and
four dedicated under-mezzanine fixtures were added at z=112. The final eight
fixed views covered the yard, threshold, reactor core, both lower loops, rear
crossover, upper loop, and overview. They confirmed readable floor boundaries,
continuous broad routes, supported props, and a clean warm-sun/cool-fill
industrial presentation.

The final retail toolchain completed Q3map in 0.454 seconds, full fast VIS in
0.412 seconds, and MOHlight in 1.332 seconds with zero Q3map warnings, zero
coordinate clamps, and zero light hash-table warnings. The version-19 BSP has
662 surfaces, six lightmap pages, 39,536 visibility bytes, and is 774,508 bytes
with SHA-256
`4A7EDE5D74338D01E26C0CC0AE3BEBA2462EDE46BAEC3F63A7C36A943F540D57`.

The deterministic packager emitted exactly 19 entries: the BSP, map script,
precache script, and 16 TGA textures. It reopened the archive and verified every
entry hash, then reproduced the same 3,290,168-byte PK3 twice with SHA-256
`3287D9C12AD1311F7CC871AFF551431E7D7FBDC911D20195DC41B453C429F6E1`.

The exact package was tested in an isolated AA root containing retail Pak0-Pak6
and no other add-on PK3. OpenMoHAA 0.82.1-beta loaded the BSP, built Recast in
0.190 seconds, admitted all eight bots, and recorded 11 combat/death events in
30 seconds with zero candidate-specific fatal or missing-asset diagnostics.
A second instrumented run sampled all eight bot positions every two seconds.
All eight designed route zones were observed, every bot moved, each bot reached
two to five zones, sampled travel ranged from roughly 4,000 to 8,500 units, and
15 combat events occurred. The instrumentation was a loose temporary script;
the BSP and candidate PK3 were the exact final release artifacts.

**PROVEN close-range topology rule:** use a compact loop graph instead of a
single central room; provide at least two ways around each major obstruction;
keep primary openings at least 256 units where crossfire is expected; seed
spawns across every loop; and validate actual bot zone coverage rather than
inferring navigation quality from a successful Recast build.

**PROVEN stacked-route lighting rule:** a light above a solid mezzanine does not
make the route below it readable. Treat each stacked walkable layer as its own
lighting problem, add local fixtures beneath overhead slabs, then inspect fixed
views from ordinary player height before raising global ambient.

## Stock AA whole-map mirrors: `mohdm6` and `obj_team2`

Date: 2026-08-08

Two separate maps were generated by reflecting the repository's supplied AA editable sources across world `x = 0`: `codex_mohdm6_mirror` from `aa/mohdm6.map` and `codex_obj_team2_mirror` from `aa/obj_team2.map`. They do not replace or rename the retail maps. The goal is a left/right gameplay inverse while retaining stock materials, scripts, target names, spawn families, lights, doors, splines, and other metadata.

The negative-determinant transform required format-specific handling. For brushes, every face point's X coordinate is negated and points zero and two are exchanged so the plane/inside direction remains valid. For legacy MOH `patchDef2`, the serialized first dimension is row count and the second is controls per row; every control X is reflected and the row order is reversed, matching NetRadiant's left-handed patch inversion. For `terrainDef`, reflecting the grid changes the origin to `-(x0 + (width - 1) * 64)`, reverses each height-sample row, and exchanges the two triangle-flag groups attached to each sample. Later `obj_team4` evidence refined material handling: controls own 8-by-8 cells and each row ends in a boundary sentinel, so corrected mirrors reverse the cell controls while retaining the sentinel. Simply negating the terrain origin would move the grid instead of mirroring it in place.

Entity origins use `x = -x`. Ordinary yaw becomes `180 - yaw`, while the special vertical values `-1` and `-2` remain unchanged. Three-component `angles` reflect yaw and roll; `sundirection` reflects its yaw and roll components. Link names and arbitrary key values are deliberately unchanged. Texture names and face texture parameters are retained rather than mirroring the bitmap payload; this is a geometry/gameplay inverse, not reversed readable text or new art.

The generator transformed 13,938 brush faces, 68 patches, two terrain blocks / 442 terrain samples, 491 origins, and 115 yaw keys for `mohdm6`. It transformed 35,217 faces, 708 patches, seven terrain blocks / 8,479 samples, 595 origins, and 249 yaw keys for `obj_team2`. Validation compares source and output entity-class counts and applies the canonical transform twice more: three applications must reproduce the first canonical mirrored output exactly. Both maps pass that involution test.

Thin map-owned scripts execute the corresponding retail scripts and precache scripts. This preserves gameplay without redistributing retail script content. Sustained DM bot startup exposed two stock assets absent from the usual retail DM cache path (`dm_50_healthbox.tik` and `bazookaexplosion_dm.tik`); the final wrapper caches them explicitly.

Both maps passed original Q3map, VIS, and full MOHlight against Pak0-Pak6. `mohdm6` completed lighting in 32.851 seconds and retained three dense-leaf clamps. `obj_team2` exposed two original-tool constraints: MOHlight needed `textures/wilderness/wldrrckset1_1.jpg` loose in the ignored build tree, and the four-thread pass access-violated late in the large job. The same BSP completed in 517.7 seconds with one light thread, zero clamps, and zero hash warnings. Build-only extracted retail inputs stay outside the package.

Compiler warnings were classified against the unmodified source instead of hidden. The DM source emits missing optional editor `.map` helpers and exterior light-leak diagnostics. The Objective source emits the same helper class plus its existing `textures/notexture` reference, but no leak or degenerate diagnostics. A successful derived compile does not make inherited source warnings clean.

The final DM PK3 ran in an exact eight-package root (Pak0-Pak6 plus the candidate), generated Recast in 0.500 seconds, admitted eight bots, and produced combat with zero candidate-specific or script errors. The Objective candidate generated Recast in 1.852 seconds and admitted eight bots in intended Objective mode. That mode logged five legacy `global/obj_dm.scr` errors. A separate retail-only Pak0-Pak6 `obj/obj_team2` baseline reproduced exactly five script errors with the same control-room/null-listener context, so they are inherited retail behavior. An FFA topology exercise on the mirrored Objective BSP generated Recast in 1.853 seconds and produced four combat events in 25 seconds; it proves bot movement/combat, not Objective-rule completion.

Automated post-load rendering could not be captured reliably in this desktop session: command-buffer captures landed on the loading screen and ordinary desktop capture returned a black hardware-rendered surface. No visual claim was promoted. Human appearance, door swing, and end-to-end Objective interaction remain explicit gates.

**PROVEN whole-map reflection rule:** a MOH mirror is not a coordinate search/replace. Preserve brush winding, reverse the correct patch dimension, translate and reverse terrain grids with triangle flags, transform orientation and sun keys, preserve the link graph, validate class-count equality and reflection involution, compile against retail data, classify warnings against the unmodified baseline, and test the exact final PK3. Texture imagery remains unmirrored unless reversed art is an explicit separate requirement.

## Stock AA whole-map mirror: `obj_team4`

Date: 2026-08-08

`codex_obj_team4_mirror` reflects `aa/obj_team4.map` across world `x = 0` as a separate Objective map. It transforms 23,671 brush faces, 174 patches, five terrain blocks / 29,229 height samples / 543 material controls, 515 origins, 247 yaw keys, one angle vector, and the sun direction. The preserved gameplay inventory includes 19 Allied starts, 17 Axis starts, 13 rotating doors, 21 windows, 176 lights, and the retail bridge target graph. The three-entry wrapper package delegates to retail `obj_team4.scr` and `_precache.scr` and adds only the stock bot bazooka explosion cache line.

This source exposed a flaw that the smaller terrain cases did not. MOH terrain material-control rows contain one control per 8-by-8 cell plus a final boundary sentinel. Reversing all controls shifts the cell owner by one. The first `obj_team4` mirror therefore made an intentional 534-unit `notexture`/`nodraw` cliff compile as visible, and Q3map rejected it against the 510-unit per-patch limit. Reversing only the cell-owning controls and retaining the sentinel preserved the hidden cliff and compiled without changing any height. The generator now records `terrainControlMode`, new maps use `cell-sentinel`, and validation requires the MAP to equal that exact configured transform. The existing published `mohdm6` and `obj_team2` configs pin `legacy-full-row` so their current bytes remain reproducible pending a deliberate migration revision.

The editable retail `obj_team4` source also cannot pass its manual-vis prepass with original Q3map: the unmodified source requests 3,089,432 bytes against a 2,097,152-byte fixed buffer. The mirror requests 3,108,152 bytes. `-nomanvis` bypasses only this prepass and preserves the complete geometry; ordinary fast VIS then completed with 283 clusters, 463 portals, and 11,328 bytes. The builder allowlists map-specific Q3map arguments and records them in its report rather than accepting arbitrary compiler switches.

Q3map completed in 9.048 seconds with 24 inherited optional-helper/image warnings and no leaks or degenerates. VIS completed in 0.224 seconds. Four-thread MOHlight access-violated; one-thread MOHlight completed in 774.05 seconds, produced 60 pages, retained five dense-leaf clamps to the retail limit of 60, and emitted no hash warning. The version-19 BSP has 8,167 surfaces and SHA-256 `467BF131E0C4D90787EA51E7B04F59B7F3417B2A52DC9455979681F9753B2989`.

The final deterministic PK3 is 1,651,141 bytes with SHA-256 `0E658E19868CB7EEC00D885F5010D1B778980472E4562886F6BBB347A81900B6`. In an exact Pak0-Pak6-plus-candidate root, Objective mode parsed it in 0.094 seconds, generated Recast in 6.202 seconds, and admitted eight bots with zero candidate-specific diagnostics. A 35-second FFA topology exercise generated Recast in 6.327 seconds and recorded seven combat events. Intended Objective mode logged ten bridge/null-listener script errors; an untouched Pak0-Pak6-only retail `obj/obj_team4` baseline logged the same ten errors and context, proving the behavior is inherited. Human visual, door-swing, bridge-destruction, and end-to-end objective completion remain explicit acceptance gates.

**PROVEN MOH terrain-control rule:** height samples are vertex data and reflect across the full row; material controls are cell-owned and carry a trailing sentinel. Reflect cell ownership without shifting that sentinel, then use a stock source with hidden high-relief terrain as a compiler regression test.

**PROVEN manual-vis exception rule:** `-nomanvis` is not a general optimization flag. Use it only after reproducing a fixed-buffer failure on the unmodified stock source, preserve all geometry, and require the subsequent ordinary VIS stage to emit valid nonzero cluster, portal, and visibility data.

## User-rejected Reactor baseline and V2 Depot revision 1

Date: 2026-08-09

The user rejected `codex_reactor` as buggy and a mess. That overrides its earlier positive visual status: compiler, Recast, bot-combat, and fixed-camera gates proved technical loadability, not stock-map construction quality or human polish. Reactor is now a negative case, not a release/design baseline.

`codex_v2_depot` restarted from the actual `aa/obj_team2.map`. A generic analyzer measured its 5,827 brushes, 35,217 faces, 708 patches, seven terrains, alignment, thickness modes, material/axis use, scales/flags, entities, lights, models, and spawns. Private contact sheets of resolved retail textures confirmed the palette; retail bytes remain ignored and unbundled.

The new original layout copies grammar rather than geometry: 189 brushes, 1,150 faces, 424 caulk faces, measured grid/thickness/stair conventions, three open bays, broad service loops, rear crossover, U-catwalk, 10 zones, 15 links, and 192-unit minimum routes. Validation caught three unsafe spawns. Changing the stock corona from an absent optional static helper to an explicitly precached runtime model removed 20 warnings.

Final Q3map/VIS/MOHlight had zero Q3map warnings, zero light clamps, and zero hash warnings. Eight views drove a restrained interior relight and camera repairs; the final run produced eight screenshots/markers and zero script errors. Exact-PK3 QA built Recast in 0.127 s, admitted eight bots, and recorded 23 combat/death events in 40 s with zero candidate/stock-model diagnostics.

**PROVEN rule:** measure the editable stock source and inspect its actual images before authoring in its style. Reproduce grid, thickness, flags, hidden-face policy, scale, palette roles, entity/light ratios, and layering - not layout.

**PROVEN acceptance rule:** technical and fixed-view passes are necessary but insufficient. User rejection demotes prior positive claims, becomes regression evidence, and requires cause-level redesign. Never call a generated map perfect before human play.

## Additive stock-map expansion: `codex_obj_team2_expanded`

Date: 2026-08-09

The first additive stock-map derivative retains `aa/obj_team2.map` and builds a new East Annex in its wooded eastern boundary. A raised deck crosses the uneven terrain and connects to the original grounds through two 288-unit-wide stepped approaches. The annex adds three permanently open maintenance bays, an internal stair and mezzanine, a loading canopy, cover, stock props, eight caged-lamp/corona/light groups, and six neutral DM starts. It adds 102 brushes and 35 entities but no door, target link, team start, or objective.

Preservation is executable rather than descriptive. The generator marks all additions and exact removals. Validation strips those ranges and requires the retained serialization to equal the original source byte-for-byte minus nine untargeted footprint foliage entities and five untargeted boundary-detail entities. The original 23 rotating doors, all 88 targetnamed entities, and 16 Allied plus 16 Axis starts remain. The source SHA-256 stays `04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f`.

The first player-height visual pass disproved the initial occupancy survey. The proposed connections looked empty in coarse source/entity bounds, but the compiled map still contained `mohcommon/secfence` and `mohcommon/barbwire` surfaces across both approaches. These were old one-sided boundary treatments: correct when viewed only from the original play space, blocking once the map extended beyond them. A BSP19 surface-zone inspector identified the exact compiled material bounds. Removing only five untargeted owner entities cleared the two gaps while leaving the surrounding fence runs intact. The final 10-view contact sheet covers both connectors, facade, two yard lanes, hall, stair, mezzanine, return, and overview.

The common stock-derived builder now accepts safe repo-local generator and validator scripts, and the visual-QA harness resolves the configured `dm` or `obj` game directory. The stock grammar analyzer now reports spatial axis-box/entity bounds and grid occupancy. These changes let additive maps reuse deterministic source generation, preservation validation, compile, BSP inspection, exact packaging, and visual/runtime gates.

Q3map completed in 110.543 seconds with 18,735 surfaces, zero leaks, and zero degenerate diagnostics. Its 132 warnings are classified against the stock mirror: 127 optional `.map` helper notices (the stock 119 plus eight new corona helpers), the inherited `textures/notexture` image warning, and four other inherited stock helper notices. VIS completed in 0.264 seconds with 47,448 visibility bytes. One-thread MOHlight completed in 342.057 seconds with 62 pages, zero clamps, and zero hash warnings. The BSP is 12,779,232 bytes with SHA-256 `7d01a19b7354278a990d940528d4666c52ced196c788a3648589feb22c9b1239`.

The three-entry PK3 was reproduced byte-identically twice: 2,280,274 bytes, SHA-256 `f7aa8769474666a16d588280c44a025b811af14dc2374993d917f59e6fca6ea7`. In an exact Pak0-Pak6-plus-candidate Objective root, the BSP parsed in 0.122 seconds, Recast completed in 1.957 seconds, all eight bots entered, and no candidate diagnostics appeared. Five script errors exactly match the retail Objective baseline. A separate FFA topology exercise parsed in 0.120 seconds, built Recast in 1.973 seconds, admitted eight bots, and produced four combat events in 45 seconds with no candidate diagnostics; its seven script errors are inherited. Human door, objective-completion, route, and Axis-side balance review remains open.

**PROVEN additive-expansion rule:** stock outskirts are authored for the original viewing direction and may contain one-sided or solid boundary dressing inside apparently empty space. Survey source occupancy, then inspect compiled surfaces/collision and player-height views from both directions. Remove only exact untargeted boundary owners, keep the target graph untouched, and prove the retained source byte-for-byte.

**PROVEN Objective-derivative rule:** preserve retail scripts, doors, targets, triggers, objectives, and team starts unless the design explicitly changes them. Put new bot coverage in neutral DM starts, test intended Objective startup separately from FFA topology, compare errors with retail, and leave end-to-end objective and balance acceptance to human play.

## `codex_obj_team2_expanded` revision 2: human-angle repair

Date: 2026-08-09

The first human screenshot overrode revision 1's automated visual acceptance. From the original stock side, the annex was visibly sparse and multiple hall/retaining/frame faces disappeared. The cause was not a missing retail texture: the generator had assigned `common/caulk` to faces assumed to be hidden from the interior-only camera set. Opening the old boundary made those faces visible. The solid-looking contact sheet had therefore tested the wrong viewing domain.

Revision 2 makes every one of 156 added brushes six-face visible and rejects `common/caulk`, `common/nodraw`, `deckgrate_set1a`, and `deckgrate_set1b` anywhere inside the marked expansion geometry. The alpha canopy/mezzanine construction became solid iron/floor material. A validator now records all six face textures per brush and requires 156/156 fully skinned brushes with zero transparent construction materials.

The compound grew from 102 brushes / 35 entities / six neutral starts to 156 brushes / 53 entities / eight neutral starts. Two two-bay service sheds, facade awnings, six ceiling ribs, three roof vents and caps, a dispatch island, eight bollards, seven utility banks, eight crates, and four additional light groups make the addition read as a complete facility. Original preservation did not loosen: only the same nine untargeted foliage and five untargeted connector-boundary entities are removed, while 23 doors, 88 targetnamed entities, the Objective graph, and all 16 Allied plus 16 Axis starts remain.

Visual QA now begins with `reported_stock_side`, matching the failed human angle, followed by a raised stock-side overview and 12 connection/shed/yard/hall/mezzanine/return views. All 14 exact-candidate frames were captured with zero script errors. The reported outside frame shows solid retaining walls, facade, lintels, canopy, side sheds, and openings without the revision-1 holes. Human re-test still outranks this result.

Q3map completed in 121.914 seconds with 19,053 surfaces, 136 classified warnings, zero leaks, and zero degenerates. The four-warning increase over revision 1 is exactly four additional optional corona-helper notices. VIS completed in 0.287 seconds with 58,528 bytes. One-thread MOHlight completed in 376.547 seconds with 63 pages, zero clamps, and zero hash warnings. The BSP SHA-256 is `48d0a46bee62f51db8164641bcc99fb26ddf5d005cce808673fe6a3e00811ba0`.

The reproduced three-entry PK3 is 2,317,942 bytes with SHA-256 `b7c55baf2002aee31c8c53c322ba3289779f55053afc6bf69ce9ae7630a2a19e`. Exact Objective QA parsed the BSP in 0.120 seconds, built Recast in 2.065 seconds, admitted eight bots, observed combat, and emitted zero candidate diagnostics; the five script errors match retail. FFA parsed in 0.135 seconds, built Recast in 2.091 seconds, admitted eight bots, and produced two combat events in 45 seconds with zero candidate diagnostics; seven script errors remain inherited.

**PROVEN changed-boundary face rule:** when an expansion changes where players can stand or look from, prior hidden-face assumptions are invalid. Fully skin every ambiguous added structural face with a solid visible material, reject caulk/nodraw and unintended alpha construction inside the added range, and inspect from both the old and new sides.

**PROVEN human-angle regression rule:** every user screenshot that disproves acceptance becomes a named mandatory camera with the same viewing domain. Never let a convenient interior contact sheet stand in for the exterior angle that actually failed.

## `codex_obj_team2_expanded` revision 3: complete boundary removal and Allied exterior route

Date: 2026-08-09

The user asked for a much larger expansion, removal of the visible east fences and their concrete/brick base, and an outdoor connection from Allied spawn to the yards behind the bunker. Source-owner inspection showed why revision 2's connector-only policy was inadequate. The east perimeter was distributed across entities 666-684 and world brushes 1109-1115/1124: fence panels, barbwire, posts, caps, rails, and a `general_structure/concretewall2` curb. Revision 3 removes that complete untargeted system plus nine footprint foliage entities. A compiled BSP19 regional query then found zero `secfence` or `barbwire` surfaces and no old bottom curb in the removed east zone.

The annex grew from 156 brushes / 53 entities to 205 fully visible solid brushes / 94 entities. Its one 1,824-unit-wide six-step apron replaces the two narrow entries. An L-shaped deck carries three-bay north and south workshops, a four-bay main hall with partitions/catwalk, canopy, arcade, roof equipment, cover, utilities, 23 fixture/light groups, and 12 neutral DM starts. Original preservation remains strict: 23 doors, 88 targetnames, the Objective graph, and 16 Allied plus 16 Axis starts are unchanged.

The Allied route required a second complete ownership audit. Entity 442 was the gate panel, entity 444 the middle post, world brush 3224 the continuous curb, brushes 3228/3229 the rails, and brush 819 a continuous player clip. Removing those exact untargeted owners plus foliage entity 453 opened Y=344..670; split solid curb/rail replacements preserve the adjacent perimeter. The new top-Z -464 route is 320 units wide and turns east behind the bunker. Compiled inspection finds no panel across the 326-unit gate. Stock barbwire entity 437 remains overhead at Z=-230..-200, providing 234 units of route-floor clearance; the neighboring panels remain on either side.

The first larger design used one rectangular northern extension and leaked. Focused Q3map probes narrowed the cause: apparently empty outdoor terrain is not equivalent to sealed playable hull. New construction west of X=3584 could not continue north of Y=2208 without cutting the decorative sky boundary, while Y=2208..2496 remained sealed east of X=3584. The final L-shaped footprint obeys this direction-dependent constraint, writes a 367,565-byte portal file, produces no line file, and completes VIS. This failed rectangle is retained as negative evidence against footprint selection by entity/terrain emptiness alone.

Full Q3map/VIS/MOHlight completed in 119.673/0.297/356.013 seconds. The BSP19 has 19,224 surfaces, 66 lightmap pages, and 68,840 visibility bytes. There are no degenerates, light clamps, or light hash warnings. The one `textures/notexture` image warning is inherited. Q3map labels four unchanged stock `static_corona_orange` helpers as leaked lights, but this is classified helper behavior rather than a structural leak because `.prt` exists, `.lin` does not, and VIS succeeds.

Exact-package Objective QA parsed the BSP in 0.137 seconds, generated Recast in 2.224 seconds, admitted eight bots, and observed two combat events in 40 seconds with zero candidate diagnostics. FFA topology QA parsed in 0.122 seconds, generated Recast in 2.125 seconds, admitted eight bots, and observed three combat events in 45 seconds. Eighteen fixed views cover the full frontage, both workshops, hall/catwalk, overview, Allied gate in both directions, outer lane, and rear turn. Two initial frontage cameras landed inside the new steps; moving them into proven playable air and repeating all views established camera-origin validation as part of geometry QA.

The final deterministic MAP/BSP/PK3 hashes are `b601d530...2553d`, `425490de...927f1`, and `93390daf...39a4`. Human revision-3 play remains authoritative for route choice, door/objective completion, balance, and final visual acceptance.

**PROVEN cooperating-boundary rule:** when removing a perimeter, enumerate the full owner system—panel, wire, posts/caps, rails, curb, collision/player clip, and foliage—then remove only documented untargeted owners and verify the compiled region for every old material/obstruction.

**PROVEN outdoor-hull rule:** stock outdoor terrain and scenery bounds do not prove sealed buildable space. Probe footprint growth with focused Q3map passes, require `.prt` with no `.lin`, and encode direction-dependent safe limits in the generator.

**PROVEN camera-origin rule:** fixed views must be revalidated after geometry changes. A captured frame from inside a new step or wall is a failed visual gate, not evidence about that area.

## `codex_obj_team2_expanded` revision 4: complete fence-free forest loop

Date: 2026-08-09

Revision 3 misunderstood “remove the fences” as a local opening. A whole-source owner audit found 59 untargeted fence-system entities: 22 on the west side and 37 along the south/east side. Thirty-three cooperating worldspawn brushes supplied curbs, rails, posts, and collision; four were invisible playerclips that remained after the visible models disappeared. Revision 4 removes all of those exact owners plus 24 route-blocking foliage entities. It preserves all 23 doors, 88 targetnames, 16 Allied starts, 16 Axis starts, Objective links, and retail script behavior.

The completed route starts in a broad Allied court and continues through a west transition, eleven-step forest climb, west ridge, 1,024-unit central causeway, east ridge, fourteen-step descent, lower lane, and the annex apron. Its minimum designed combat width is 320 units. The generator now adds 334 brushes, 152 entities, and 21 neutral starts. A revision-4 validator strips the additions and exact removals and proves equality with the retained canonical source; no retail/custom asset bytes enter the package.

The first route build revealed that the apparent forest gap was not a usable hull. Western terrain stopped near X=-192 and eastern terrain began near X=1088. Successive `.lin` traces exposed, in order, a missing central foundation, north stock-floor edge, south side enclosure, north underside, central ceiling, and a final ceiling mismatch: the west stock sky bottom was Z=832 while the proposed central ceiling began at Z=960. The accepted source completes floor/foundation, both side hulls, and a Z=832 sky ceiling joined to stock geometry. Focused and release Q3map passes both wrote `.prt` and no `.lin`.

The first sealed causeway was still not visually complete. Its south edge read as a bare map limit and the facility face was too flat. A final visual-cause pass added a retaining wall with six piers, five raised grass/oak planters, four projecting facade pilasters, three service doors/lintels, banding, and three wall-light groups. Twenty-eight player-height/overview frames then covered the original frontage, annex, Allied court, every route segment, central completion, east connection, and overheads. They captured 28 screenshots with zero visual-script errors and showed no fence/curb remnant, open void/sky seam, or floating route prop.

The release build completed Q3map/VIS/MOHlight in 119.793/0.398/320.630 seconds. BSP19 contains 19,624 surfaces, 67 lightmap pages, and 131,080 visibility bytes with zero degenerates, clamps, or light-hash warnings. Compiled-zone inspection counts 51 Allied-perimeter, 172 west-route, 288 central-causeway, 328 east-return, and 2,036 annex surfaces. Objective QA admitted eight bots, built Recast in 2.150 seconds, and produced five combat events in 60 seconds. FFA built Recast in 2.134 seconds and produced four combat events. Neither mode emitted a candidate diagnostic.

Final MAP/BSP/PK3 hashes are `871719b0...a8070`, `140ee2bf...92eb`, and `4b85f8ed...3918`. Human full-route choice, original-door behavior, Objective completion, and balance remain the release gate that automation cannot establish.

**PROVEN complete-perimeter rule:** “all fencing” includes every panel, wire, post/cap, rail, curb, collision brush/playerclip, and blocking foliage owner across the requested perimeter. A rendered model inventory alone is insufficient.

**PROVEN terrain/hull separation rule:** `terrainDef` cell/surface extent is not sealed-hull extent. A new outside route must explicitly join floor/foundation, side enclosure, and ceiling to stock structural boundaries.

**PROVEN seal-to-scenery rule:** `.prt` without `.lin` proves enclosure, not visual completion. Inspect the entire new edge and turn structural sealing planes into intentional retaining, facade, landscape, and lighting work before acceptance.

## `codex_obj_team2_expanded` revision 4: superseding human rejection

Date: 2026-08-09

A later human screenshot and explicit user rejection override revision 4's
automated visual conclusion. The screenshot showed huge beige voids,
disconnected-looking terrain/map islands, crude elevated causeway/slab
construction, unfinished visible boundaries, and an overall result far below
acceptable mapping quality.

The 28-view suite proved that selected scripted cameras captured frames without
script errors; it did not reproduce or correctly judge the human failure angle,
large-scale spatial continuity, elevated construction, or newly exposed map
edges. Compile sealing, surface counts, Recast, bot combat, and capture success
did not establish visual coherence.

`SUPERSEDED`: all revision-4 language implying a complete or finished forest
loop, visually coherent causeway/facade, no visible voids, polished boundaries,
release readiness, or acceptance. `REJECTED`: revision 4 as a positive map or
construction baseline. Preserve its technical records and failed experiment,
but do not reuse its geometry without fresh primary-evidence verification.
