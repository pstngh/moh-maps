# The MOHAA `.map` format

The editable source of a level: plain text, parsed by EA's Q3map 1.34 and by
`mohkit.mapfile` (which round-trips all 94 stock sources in `reference/`).

## Coordinates

- Units: 1 unit ≈ 1 inch; EA's own comment: *"world is in 16 units per foot"*.
  The player is 30 × 30 × 94 (details in [design.md](design.md)).
- Z is up. `angle`/yaw 0 faces +X (east), 90 faces +Y (north).
- Keep everything within ±8192 on every axis: entity origins are networked as
  16-bit fixed point, and the bot navmesh assumes that range.

## File structure

A sequence of entities. The first is always `worldspawn`, which owns the static
world geometry.

```text
// comments run to end of line
{
"classname" "worldspawn"
"message" "My Map"
"suncolor" "70 64 52"
{                                    <- a brush
( 0 0 0 ) ( 0 64 0 ) ( 64 0 0 ) general_structure/jh_conc512b 0 0 0 1 1 0 0 0
...
}
{                                    <- a patch (curved surface)
patchDef2
{ ... }
}
}
{
"classname" "info_player_deathmatch"
"origin" "256 128 1"
"angle" "90"
}
```

Keys and values are double-quoted strings **without escape sequences** (a value
may even end in a backslash). Keys are unique per entity in practice.

## Brushes

A brush is a convex solid: the intersection of the half-spaces behind each face
plane. Each face is one line:

```text
( x1 y1 z1 ) ( x2 y2 z2 ) ( x3 y3 z3 ) SHADER shiftS shiftT rotate scaleS scaleT CONTENTS FLAGS VALUE [extensions]
```

**Plane from points.** normal = normalize((p3 − p1) × (p2 − p1)), pointing *out*
of the brush; the solid side satisfies `normal · p ≤ normal · p1`. Getting the
order wrong turns the brush inside out, which the compiler reports as a
degenerate or empty brush. Use integer (grid) points whenever possible; the
three points only define the plane, and they need not be vertices of the brush.

**Shader** is a name relative to `textures/`, e.g. `general_structure/plaster_wall2`
(a shader script entry, or an image `textures/<name>.tga|.jpg`).

**Texture fields** use the Quake 3 "old" projection. The face is projected
along the world axis closest to its normal. Ties go to Z first, then X, then Y.
The base axes are:

| face normal closest to | s axis | t axis |
|---|---|---|
| ±Z (floor/ceiling) | +X | −Y |
| ±X (walls facing east/west) | +Y | −Z |
| ±Y (walls facing north/south) | +X | −Z |

After rotating those axes by `rotate` degrees, the texel coordinates are
`s = (p·s_axis)/scaleS + shiftS` and `t = (p·t_axis)/scaleT + shiftT`, then
divided by the image size. Consequences:

- **Scale 1 is the stock convention** (92% of stock faces): one texel per unit,
  so a 256 px texture repeats every 256 units. 0.5 (3%) and 0.25 (1%) are used
  for finer detail.
- Textures are world-aligned automatically: adjacent brushes line up with
  shift 0.
- Walls whose normal is −X or +Y show the image mirrored left-right. Use a
  negative `scaleS` to fix that when it matters (signs, doors). `mohkit.kit.fit`
  does it for you.

**CONTENTS FLAGS VALUE**: MOHRadiant copies the shader's content and surface bits
here (e.g. `common/clip … 196608 2193 0`). **Q3map derives the real flags from
the shader script**, so generators can write `0 0 0`. This was verified by
reading the compiled BSP shader lump: caulk gets nodraw+nomarks, sky gets
sky+nolightmap, and `+surfaceparm detail` gets CONTENTS_DETAIL.

**Extensions** after the eight numbers, any order:

| token | meaning |
|---|---|
| `+surfaceparm detail` | detail brush: collides and draws, but doesn't split visibility. On 81% of stock faces |
| `+surfaceparm X` / `-surfaceparm X` | add/remove any surfaceparm on this face (`nonsolid`, `playerclip`, `weaponclip`, `noimpact`, `nomarks`, ...) |
| `surfaceDensity N` | lightmap density for this face (units per lightmap texel; worldspawn `lightmapdensity` is the default) |
| `subdivisions N` | tessellation hint |
| `surfaceColor r g b` | seen on origin brushes (`-1 -1 -1`) |

**MOHAA has no `func_detail`.** Q3map compiles a Quake `func_detail` brush entity
as an ordinary brush model (`*1`); the game doesn't know the class, logs
`Classname func_detail used, but model was not a TIKI, using Object.` and spawns
it as a generic entity, which renders **black** (unlit, even with radiosity and
ambient 40). Tested 2026-09-30 with a sealed room holding one `func_detail` box
and one world box. Mark detail per face with `+surfaceparm detail`, as stock maps
do. The `detail` entity is editor grouping only.

## Patches (`patchDef2`)

Curved surfaces: a grid of quadratic Bézier control points.

```text
{
patchDef2
{
general_structure/jh_brick4
( 3 5 0 0 0 )                       <- ( ROWS COLS contents flags value [extensions] )
(
( ( x y z s t ) ( x y z s t ) ( x y z s t ) ( x y z s t ) ( x y z s t ) )
( ... 5 points ... )
( ... 5 points ... )
)
}
}
```

- The first number is the number of row records and the second the number of
  points per row. Both must be odd (3, 5, 7, ...). Keep each ≤ 17 (split bigger
  surfaces into several patches that share border rows).
- `s t` are normalized texture coordinates (1.0 = one repeat).
- **Visible side**: the side the normal `cross(P[r+1][c] − P[r][c], P[r][c+1] − P[r][c])`
  points to, with r the row index and c the column index. Verified in engine;
  transpose the grid to flip.
- Every other control point lies on the surface; the ones between are pulls.
  To make a patch pass exactly through sample points (terrain, converted
  displacements), put the samples on even indices and use arithmetic midpoints
  for the odd ones. Each cell is then bilinear, with no overshoot.
- Patches collide (and are in the bot navmesh) but never seal the map, and
  they are always non-structural.
- Header extensions like `subdivisions 6.5`, `+surfaceparm detail`,
  `-surfaceparm solid`, `+surfaceparm weaponclip` appear in stock maps.

## Terrain (`terrainDef`)

MOHAA's LOD heightfield, used heavily outdoors in stock maps. It compiles to
388-byte terrain patches of 9 × 9 heights (8 × 8 cells of 64 units = 512 × 512
units each).

```text
{
terrainDef
{
W H 0                                <- vertex counts; (W-1) and (H-1) multiples of 8
X Y Z                                <- origin (south-west corner)
{                                    <- material controls: ((W-1)/8+1) * ((H-1)/8+1) lines
F 0 ( shader shiftS shiftT rot SIZE scaleS scaleT contents flags value )
...
}
{                                    <- W*H samples, row-major, rows run along +Y
height ( tokens ) ( tokens )         <- height relative to Z; tokens e.g. nodraw
...
}
}
}
```

- Samples are 64 units apart; the vertex at column c, row r is at
  (X + 64c, Y + 64r, Z + height).
- Material controls belong to 8 × 8 cells, plus a trailing sentinel row and
  column. When mirroring, reverse the cell-owning controls but keep the
  sentinel.
- Height resolution is 2 units, and a single 512 × 512 patch may span at most
  510 units of height; the compiler errors otherwise.
- `SIZE` is the texture's repeat size in world units: 256 or 512 with scale 1
  gives stock-looking ground. `0` smears one texel across the whole patch
  (verified in engine).
- Height tokens seen: `nodraw` (hidden cells), `invisible`, `important`,
  `trivial`, `maxdetail`, `nodetail`, `locked`.
- Terrain collides and is in the bot navmesh, but doesn't seal the map. Keep it
  inside Carver air with a caulk floor under it.
- Generate it with `mohkit.kit.terrain(b, x0, y0, z0, patches_x, patches_y,
  height_fn, "wilderness/m3l3grass_1")`. Stock terrain materials include
  `wilderness/m3l3grass_1(rough)`, `algiers/grndset_2af`, `mohtest/rubble2c`,
  `misc_outside/bocagegrass_1uf` and `central_europe_winter/forstsnow_lite256`.

## Entities with brushes

Brush entities (`func_rotatingdoor`, `func_ladder`, `trigger_*`, `script_object`)
contain brushes like worldspawn. Their geometry is stored relative to the
entity origin in the BSP. That origin comes from a `common/origin` brush if
present, otherwise from the bounds centre. Always give rotating things an
origin brush on the hinge (see [entities.md](entities.md)).

## Static models (props)

`static_*` entities (`"model" "static/indycrate.tik"`) are baked into the BSP by
Q3map and lit per-vertex by MOHlight. They are removed from the entity list, so
scripts can't see them. See [entities.md](entities.md#props) for collision.

## Tools

- `mohkit.mapfile.MapFile.load(path)` / `.save(path)`: parse and write
  (entities, brushes, patches, terrain).
- `python -m mohkit inspect file.map`: summary, `validate`: static checks,
  `plan`: top-down image.
