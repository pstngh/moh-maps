# mohkit authoring API (`build`, `kit`, `game.Shot`)

The calls a `maps/<name>/build.py` uses, with the conventions that are easy to
get wrong. Signatures are abbreviated; the docstrings in `mohkit/build.py` and
`mohkit/kit.py` have every argument. Coordinates: Z up, 1 unit ≈ 1 inch,
`north` = +Y, `east` = +X.

## Materials

`Material(shader, scale=(1, 1), rotate=0, shift=(0, 0), parms=())`, usually
imported as `M`. `scale` is world units per texel (1.0 is the stock norm);
`parms` adds `+surfaceparm` names to every face that uses it. A material is
callable to copy it with changes: `STONE(rotate=90)`. A plain shader name
string works anywhere a material does.

## Two ways to say which face gets which material

They look alike but mean different things.

**Brush faces (`MatSpec`)**: `b.box`, `b.prism`, `b.hull`, `cv.solid`, `kit.strip`.
A spec is one material, or a mapping whose keys name the face by its **outward
normal**:

| key | faces |
|---|---|
| `north` `south` `east` `west` `top` `bottom` | the face whose normal points that way (axis-aligned faces only) |
| `up` / `down` | any face with normal z > 0.7 / < −0.7 (ramps, roof slopes) |
| `sides` | every face with \|normal z\| ≤ 0.7 |
| `default` | everything else (caulk if omitted) |

Exact side names win, then `up`/`top`, `down`/`bottom`, then `sides`, then
`default`. A spec can also be a function `(normal, centre) -> material`.
A box standing against a room's north wall shows its **south** face to the room.
Brushes take **one material per face**: a band list raises `TypeError` (stack
boxes to band a brush).

**Carver walls (`WallSpec`)**: the `walls=` of `cv.room`. The value is one
material, a **band list** `[(z_from, material), ...]` (absolute z, ascending:
`[(0, STONE), (32, PLASTER)]` is a 32-unit stone base course), or a mapping
whose keys are the **compass side of the air box** where the wall stands
(`north` is the wall along the box's +Y edge, seen from inside) plus `default`.
Mapping values may be band lists. The shell is cut at every band height, so
each piece gets one material.

## MapBuilder (`b`)

```python
b = MapBuilder("Title", suncolor=..., sundirection=..., ambientlight=..., farplane=...)  # worldspawn keys
```

| call | does |
|---|---|
| `b.carve(cv)` | use a Carver for the sealed shell (call once) |
| `b.box(mins, maxs, spec, detail=True, grid=512)` | axis-aligned brush, split on the 512 grid (64-vertex limit) |
| `b.prism(poly_xy, z0, z1, spec)` | vertical extrusion of a convex polygon (columns, octagonal shafts) |
| `b.hull(points, spec)` | convex hull of ≥ 4 points (ramps, wedges, arch pieces, roof slabs) |
| `b.add(*prims)` | raw `Brush`/`Patch`/`Terrain` objects |
| `b.prop(tik, x, y, z, yaw, scale=1, hang=False)` | stock prop with its **base** on `z` (`hang`: its top touches `z`) |
| `b.static_model(tik, origin, yaw)` | prop by pivot instead of base |
| `b.light(origin, intensity, color=(r, g, b), **keys)` | point light |
| `b.spawn(origin, yaw, kinds=("deathmatch", "allied", "axis"))` | one entity per kind at the feet position (z = floor + 1) |
| `b.entity(classname, origin, **keys)` | any entity; `__` in a key becomes `$` |

Detail is the default for `box`/`prism`/`hull` (`+surfaceparm detail`); never
use `func_detail`. Props have no collision unless `mohkit.props.get(x).collision`;
check pivots with `python -m mohkit.propview static/x`.

## Carver (`cv`)

```python
cv = Carver(thickness=16, sky_shader="sky/mohday2", grid=512)
yard = cv.room(x0, y0, z0, x1, y1, z1, floor=F, walls=W, ceiling=C, sky=False, name="yard", priority=0)
```

Rooms are **air**: the carver wraps each one in `thickness`-deep slabs,
subtracts all air from all slabs, caulks every face no air touches, and splits
the rest on the grid. So the map is sealed by construction. Overlapping or
touching rooms join (a 32-unit room through a wall is a doorway); where two
rooms touch the same shell face, the larger contact wins, then the higher
`priority`. A sky room needs a sky top above everything the player can see.

| call | does |
|---|---|
| `cv.room(...) -> Air` | add air; returns it (kit calls take it to find walls) |
| `cv.add(Air(...))` | same, from an `Air` |
| `cv.solid(x0, y0, z0, x1, y1, z1, spec)` | extra **structural** box not derived from air (a pillar mass); the spec uses brush keys, and nothing is caulked for you |
| `cv.contains(point)` | is the point in any air |

A wall between two rooms is as thick as the gap between them. Each room's
shell is `thickness` deep, so a gap wider than 2 × `thickness` is hollow (and
caulked). Niches cut into that gap: keep `depth + thickness` at or below it.

## kit (architecture)

`side` in every kit call is the **compass side of the air box** where the wall
is. `u0..u1` runs along that wall: **x for north/south walls, y for east/west**.
`z` values are absolute.

| call | makes |
|---|---|
| `stairs(b, x, y, z, direction, width, rise, tread, riser=None, step_h=8, step_d=16)` | straight flight from the near-edge centre; returns the top landing point |
| `ramp(b, x0, y0, x1, y1, z0, z1, direction, m, surface=None)` | wedge rising toward `direction` |
| `recess(cv, air, side, u0, u1, z0, z1, depth, back, reveal, sill, lintel)` | niche carved into a wall (air, so it stays sealed); keep `depth + thickness` below the wall's thickness |
| `window(cv, air, side, u0, u1, z0, z1, image, image_px, reveal, depth=8)` | niche with a window image fitted to its back |
| `door(cv, air, side, u, z=0, width=64, height=128, image=..., image_px=...)` | decorative closed door niche centred at `u` |
| `facade(b, cv, air, side, u0, u1, storeys, skip=(), doors=(), shutters=None, moulding=None, moulding_z=None, spacing=192, win_w=56)` | a whole outdoor wall: window bays for each `(sill_z, top_z)` storey, doors at the bays nearest `doors`, optional shutters and a moulding broken at `skip` spans; returns windows placed |
| `strip(b, air, side, u0, u1, z0, z1, depth, m)` | thin box against the wall (mouldings, base courses, signs) |
| `shutter(b, air, side, u0, u1, z0, z1, frame, image=..., image_px=...)` | open shutter panel, image fitted |
| `opening_frame(b, wall_axis, plane, wall_t, u0, u1, z0, z1, m)` | trim round an opening through a wall (`wall_axis` "x": the wall runs along Y) |
| `baseboard(b, room, m, height=8, gaps=[(side, u0, u1)])` | skirting round a room, skipping doorways |
| `beams(b, room, axis, spacing, m)` | ceiling beams running along `axis` |
| `column(b, x, y, z0, z1, m, size=24)` | square column with base and cap |
| `gable_roof(b, x0, y0, x1, y1, z, rise, ridge_axis, roof, gable, overhang=16)` | pitched roof on walls ending at `z`; rotate the roof material 90 for a ridge along Y |
| `lamp(b, x, y, ceiling_z, intensity=180)` | hanging lamp prop plus its light |
| `wall_lantern(b, x, y, z, wall, intensity=160)` | bracket lantern on the wall at (x, y) |
| `crate_stack(b, x, y, z, m, size=48, layout="L")` | brush crates as cover |
| `terrain(b, x0, y0, z0, patches_x, patches_y, height_fn, shader, texture_size=512)` | LOD terrain, 512×512 per patch, ≤ 510 relief per patch (see [map-format.md](map-format.md#terrain-terraindef)) |
| `fit(shader, normal, u0, u1, top, scale)` | material that puts an image's top-left on a panel's top-left, unmirrored |

Recipes that worked: an arcade is pillars (`prism`) plus arch pieces (`hull`)
that stop just above the apex and one lintel box to the ceiling (see
[map-format.md](map-format.md#64-vertex-faces) and `maps/mk_medina/build.py`);
a decal or alpha image goes on a thin non-solid slab 1 unit off the wall (see
[materials.md](materials.md)).

## Cameras (`SHOTS`)

`Shot.looking_at(name, eye, target, fov=None)` or `Shot(name, eye, (pitch, yaw, roll))`.
`eye` is the eye position (the harness subtracts 82). The engine draws fov 65–120;
see [testing.md](testing.md#cameras).

## The loop

```sh
python -m mohkit generate maps/<name>          # .map + validate + dist/<name>_plan.png, seconds
python -m mohkit build maps/<name> -q draft    # compile, package, screenshots
```
