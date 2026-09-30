# Designing and building MOHAA maps

What makes a map *work* (players, bots, compiler) and *look like MOHAA*. Numbers
come from the OpenMoHAA source and the stock maps. The cited details are in
[reference/engine.md](reference/engine.md).

## Player metrics

| | value | notes |
|---|---|---|
| player box | 30 × 30 × 94 (crouched 54) | origin at the feet |
| eye height | 82 standing, 48 crouched | use for sightline and window-sill decisions |
| max step | 18 | stairs: 8–16 rise; 8 × 16 is the stock proportion |
| walkable slope | < 45.5° (normal.z ≥ 0.7) | steeper ramps are slides |
| jump | 56 units high | ledges > 56 need stairs or a ladder |
| safe drop | 125 (no damage), 250 (−5 HP), 625+ (fatal) | |
| run speed (MP) | ~275 u/s (walk 165, crouch 99) | a 2000-unit street takes ~7 s |
| gravity | 800 | set per map by worldspawn `gravity` |

Derived minimums (give generous margins, bots are clumsy):

- Corridors ≥ 64 wide, ideally 96–128. Streets 192–320.
- Doorways ≥ 48 × 112 for play (stock doors are about 56–72 × 124–144).
- Ceilings ≥ 128 (one storey is usually 128–192; stock upper floors are often 128).
- Crouch-only gaps (56–92 tall) are invisible to bots: the navmesh agent is
  94 tall.
- Cover: 40–56 tall for crouch cover, ≥ 96 for full cover.

## Layout for deathmatch

- **Loops, not dead ends.** Every major space should have 2–3 exits. Stock DM
  maps are a web of streets, courtyards and building interiors with routes
  through windows, alleys and buildings.
- **Mix ranges.** MOHAA has rifles and snipers as well as SMGs. Pair long
  streets with interiors and short alleys. Break long sightlines with cover,
  bends or elevation changes rather than walls across them.
- **Vertical play.** Upper floors overlooking a square, balconies and stairs
  give the stock maps their character. Keep upper floors reachable from two
  sides where possible.
- **Size.** Stock DM maps are about 2500–4000 units across for 12–32 players.
- **Spawns.** Use 16–24 `info_player_deathmatch` spread around the map, plus
  16+ each of `info_player_allied`/`info_player_axis` for team modes (put each
  team on a side). Keep spawns ≥ 64 from walls, facing into the space, and not
  in view of each other when possible. Add one `info_player_start` and one
  `info_player_intermission`.

## Construction

### Structure vs detail

Q3map builds visibility (VIS) from **structural** brushes only. Keep the
structure simple (outer walls, floors, big masses) and make everything else
detail with `+surfaceparm detail` (stock maps: 81% of faces are detail). Too
much structure overflows VIS (`NumVisBytes … exceeds 2097152`) and slows
compiles; converted maps use a structural shell with everything inside it
detail.

### Sealing: the Carver method

A map must be sealed: no path from any entity to the void, or Q3map "leaks"
and skips VIS/light. mohkit's `Carver` makes leaks impossible. You describe
the **air** (the spaces players occupy) as boxes with materials:

```python
cv = Carver(thickness=16, sky_shader="sky/mohday2")
sq = cv.room(-640, -448, 0, 640, 448, 320, floor=COBBLE, walls={"north": [(0, STONE), (32, PLASTER)], ...})
cv.room(-1408, -1344, 320, 1408, 1344, 1152, floor=ROOF, sky=True)   # one sky volume over the roofs
```

The carver wraps every air box in 16-unit slabs, subtracts all air, textures
each face from the air it faces (floor, walls, ceiling, or height bands such
as stone base, plaster and timbered upper storey), caulks faces nobody can
see, and chops everything on a 512 grid. Doors, windows, arches and stairwells
are just more air boxes overlapping walls or floors. Wall thickness is the gap
between two air boxes: leave 16–32 units between a street and the room behind
it.

### Detail that makes it look like MOHAA

Compare with stock `reference/aa/mohdm1.map`, `mohdm6.map`, `obj_team2.map`:

- **Textures at scale 1**, chosen per surface role. One material everywhere
  looks like a prototype. Vary facades per building and use a stone base course
  (bottom 32 units), plaster or brick, and a timbered or different upper storey.
- **Trim**: moulding at floor lines, window sills and reveals, door frames,
  baseboards and beams inside. It is cheap (thin detail boxes) and adds a lot.
- **Windows as niches** 8 deep with a fitted window image
  (`general_structure/denmark_win2`, `window4_frame`,
  `central_europe/windowtownhall1`) plus shutters (`central_europe/shutter_set2`).
  Real openings where you want gameplay.
- **Roofs**: gable roofs with overhang over every building mass
  (`kit.gable_roof`), in shingle textures (`central_europe/redshingle`,
  `rusticshingle`). The skyline matters: it is visible from everywhere.
- **Props** from the stock set: carts, wagons, wine casks, crates, sandbags,
  bushes, lamps. Prefer props that ship a collision `.map`
  (`mohkit.props.search(...)`, `collision=True`); otherwise add clip brushes.
- **Lights where there are fixtures.** Hanging lamps indoors, bracket lanterns
  outside, not blank fill lights (see [lighting.md](lighting.md)).
- **Floors**: cobbles in squares, street sets in streets, planks and tiles
  inside.

### Grid and precision

Build on a 16-unit grid (8 for trim). Brush points should be integers. Rotated
or sloped brushes are fine as long as they are convex; `hull()` builds them
from corner points.

## Budgets and hard limits

| limit | value | what happens |
|---|---|---|
| vertices per planar face (after T-junctions) | **64** | the face renders as the default checker. Split long brushes (≤ 512) |
| lightmap pages | 170 × 128² (tested 2026-09-30: 170 pages compile, 172 fail; 0x800000 / 49152 = 170.7) | MOHlight aborts. Coarser `lightmapdensity` on big areas |
| lights reaching one leaf | 60 | clamped; lights go missing |
| VIS data | 2 MB | VIS fails. More detail, less structure |
| brushes / brush sides / planes | 32768 / 131072 / 131072 | |
| draw verts / indexes | 524288 each | `MAX_MAP_DRAWINDEXES`. Reduce detail |
| entities | 8192 (OpenMoHAA), fewer in AA | |
| statically lit prop vertices | ~75,000 per map | MOHlight crashes above ~81k |
| props per model TIKI | ≤ 24 surfaces, < 1000 verts per surface | original tools crash |
| world extent | ±8192 | origins wrap, navmesh ends |

## Bots (OpenMoHAA)

OpenMoHAA builds a Recast navmesh at map load (only when `sv_maxbots > 0` and
`g_gametype ≠ 0`). It uses:

- world brush sides that are solid/playerclip/fence (sky sides excluded);
- patches and terrain;
- `func_ladder` (as off-mesh links), 56-unit jumps and drops.

It ignores props (unless their collision map baked clip brushes), doors and
other brush entities, and crouch-only gaps. So:

- Put clip brushes around important props, or use props with collision maps.
- A door in a primary route is invisible to bots; they will walk into it.
  Prefer open doorways.
- Keep routes ≥ 64 wide, stairs ≤ 16 rise, and no 1-unit lips at doorways.
- `bot_enable` alone does nothing: set `sv_maxbots` (before the map loads) and
  `sv_numbots`.

## Checklist before calling a map done

1. `python -m mohkit validate` is clean: shaders exist, spawns are clear and
   grounded, lights aren't inside walls.
2. The compile has no leak, no bsp-check errors, and no lightmap/VIS overflow.
3. Screenshots from player height in every space, looking both ways along
   every route, plus one overview. Look for checkerboards, black faces,
   floating props, visible caulk, stretched or misaligned textures, and
   interiors that are too dark or blown out.
4. A bot match (8 bots, a couple of minutes): kills happen, and bots use more
   than one route and don't pile up anywhere.
5. The package is only your files and loads from a clean OpenMoHAA home
   (`mohkit build` / `mohkit test` do this).
