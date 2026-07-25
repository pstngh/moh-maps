# MoHAA/OpenMoHAA map generation notes

Living research document — revision 1, 2026-07-24

## Goal and current result

The immediate target is an original, compiled Medal of Honor: Allied Assault
deathmatch map that also plays under OpenMoHAA and is easy for its bots to
navigate.

That target is now technically proven. `codex_arena01` was generated as text,
compiled with the original Allied Assault Q3map/VIS/MOHlight tools, loaded by
OpenMoHAA 0.82.1, and accepted by OpenMoHAA's automatic Recast navigation
builder.

The delivered map is deliberately an asset-minimal gray-box prototype. It
proves the production path; it is not yet an art-complete, play-balanced level.

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
