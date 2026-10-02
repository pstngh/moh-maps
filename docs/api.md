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

`floor`, `walls` and `ceiling` may also be **functions** `(inward_normal, face_centre) ->
material`: for air computed by subtraction (`subtract_all` + `merge_boxes`), whose faces
belong to many buildings, the function looks up what is behind the face (`mk_summit`'s
`wall_fn`: sky at the outer box, the building's facade above ground, cliff rock below).
Shell pieces are cut only at band heights, so pass `cuts=(z, ...)` to cut them where the
function's answer changes with height (ground level between cliff and facade).

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
| `polygon(cx, cy, r, n=16, phase=0)` | integer n-gon for `b.prism` |
| `dome(b, cx, cy, z0, r, m, rings=5)` | hemisphere of stacked 16-gon slices (radar domes) |
| `clip_box(b, x0, y0, z0, x1, y1, z1)` | playerclip block |
| `railing(b, x0, y0, x1, y1, z, h=40, rail, post)` | steel rail with posts every 128 along an axis-aligned run |
| `fence(b, x0, y0, x1, y1, z=0, h=112, mesh, post)` | chain-link fence (nonsolid mesh that clips players) with posts every ~192 |
| `parapet(b, x0, y0, x1, y1, z, h=24, t=8, m, top=None)` | low wall round a flat roof's edge |
| `console(b, x0, y0, x1, y1, z=0, h=72, panel, top)` | control-cabinet block (panel texture all round) |
| `dish(b, x, y, z, r, yaw, tilt=35, m, post)` | satellite dish on a post (`static/dish.tik` is a 31-unit bowl) |
| `billboard(b, x, y, z, w, axis="x", panel, frame, leg)` | sign panel on two legs |
| `catwalk(b, x0, y0, x1, y1, z, legs_to, outer="east", deck, beam, leg)` | steel-grate walkway off a wall: beams, legs to `legs_to`, braces, railing |
| `power_line(b, posts, z=0, h=320, pole, wire, sag=48, spread=40)` | wooden poles with crossarms and two sagging wires |
| `gondola(b, x, y, z0, (xa, za, xb, zb), hanger_top, body, trim, glass)` | cable-car cabin with its hanger and two cables along x (add a clip box) |
| `antenna_mast(b, x, y, base, top, paint, steel, ring, mesh)` | tapered mast with brace rings, mesh antenna panel, coils, clipped |

Street walls, arches, cloth and roofscapes (`side` = compass side of the street air box where
the wall is; `facing` = the way a wall face looks; `plane` = its coordinate):

| call | makes |
|---|---|
| `solid_spans(cv, air, side, z, lo, hi, step=16)` | intervals along a wall of an air box that are wall, not openings |
| `wall_box(b, side, plane, u0, u1, z0, z1, d0, d1, m)` / `behind_wall(side, plane, u, z, d=40)` | box against a street wall `d0..d1` out from it / a point inside the building |
| `decal(b, facing, plane, u0, u1, z0, z1, image, px, proud=1)` | blended/alpha image on a thin non-solid slab (windows, grilles, signs) |
| `image_panel(b, facing, plane, u0, u1, z0, z1, image, px, edge, proud=2)` | solid image panel (doorway pictures) |
| `arch_fill(b, axis, t0, t1, u0, u1, zs, ztop, m, k=0.72)` / `arcade(b, axis, tc, posts, z0, zs, ztop, wall_m, stone, column)` | pointed or round arch masonry under the 64-vertex limit / a row of columns with arches, lintel, cornice |
| `coped_wall(b, x0, y0, x1, y1, z, h=40, m, cap)` | low wall with a coping slab |
| `awning(b, facing, plane, u0, u1, z_wall)` / `canopy(b, axis, a0, a1, c0, c1, z, sag)` | cloth awning off a wall / sagging cloth across a street |
| `masonry_dome(b, cx, cy, z, r, stone, trim, rings=4, sides=12)` | drum, hulled dome, finial |
| `mashrabiya(b, side, plane, c, z, wood, trim, beam, roof, stone, grille)` | enclosed wooden balcony |
| `dress_walls(b, cv, air, rng, skip, roof_z, door_img, window_img, reveal, balcony=None)` | doors, windows and balconies bay by bay on every wall of a street air box |
| `wall_trim(b, cv, air, rng, skip, roof_z, frieze, stone, beam)` | cornice, beam ends and string course on tall street walls |
| `roof_storey(...)` / `stair_house(...)` / `roof_edges(b, open_air, roof_z, town, top, m)` | rooftop storey blocks, stair huts, low walls along the roofscape's edges |
| `fountain(b, cx, cy, z, stone, base, water)` | octagonal basin with water, pedestal and a soft light |

Fixture materials default to stock AA winter/industrial textures (`kit.STEEL_V`, `STEEL_H`,
`CHAIN_LINK`, `GRATE`, `SIGN_RED`, ...); pass the map's palette to change them.

## site (reference grids, building masses, open and cliff-top sites)

`mohkit.site` holds what a whole site needs; `maps/mk_summit/build.py` uses all of it.

| call | does |
|---|---|
| `RefGrid(units_per_px, origin_px, snap=16)` | `.x(u)`, `.y(v)`, `.rect(u0, v0, u1, v1)`, `.point(u, v)`: positions written in a reference image's pixels (v down), snapped |
| `Building(name, rect, top, face, ground=0, thickness=16, reveal, sill, frame, lamp_color, lamp_intensity)` | a solid mass; `.room(cv, z0, z1, floor, walls, ceiling)`, `.opening(cv, side, u, w, z0, z1)`, `.door(b, cv, side, u, w=80, h=128, lamp=True)` (frame + wall lantern), `.window(cv, side, u, w=96, z0=64, z1=136)` |
| `plateau_solids(footprint, buildings, ground, void)` | the boxes that are not outdoor air: ground under each footprint rect, every building mass |
| `outdoor_air(cv, outer_box, solids, floor, walls, cuts=())` | sky-topped air = outer box minus solids (real drops, sealed hull) |
| `walls(outer, buildings, sky, below, ground=0)` / `floors(void, ground, valley, roof, ground_m)` | position functions for `outdoor_air`: sky at the outer box, each building's `face`, cliff `below`; valley / roof / ground floors |
| `void_triggers(b, outer, void, solids, height=256)` | trigger_hurt per void column above the valley floor (one big trigger leaks) |
| `rock_spur(b, x, y, top, bottom, top_m, side_m, r=120)` | rock outcrop from the valley to `top` (trees, masts below a rim) |
| `mountain_ring(b, m, base, n=16, rx=3800, ry=4800, r=1450, low=-400, span=850)` | broad peaks on an ellipse, each 7 wedges under the brush-length limit |
| `boulders_outside(b, points, footprint, center, rim)` | rock props pushed off the plateau, sunk below the rim |
| `in_rects(x, y, rects)` | point in any rect |
| `outside_distance(x, y, rect, p=4)` | p-norm distance to a rect: rounded-square hill contours for `kit.terrain` |

Recipes that worked: an arcade is pillars (`prism`) plus arch pieces (`hull`)
that stop just above the apex and one lintel box to the ceiling (`kit.arcade`, see
[map-format.md](map-format.md#64-vertex-faces));
a decal or alpha image goes on a thin non-solid slab 1 unit off the wall (see
[materials.md](materials.md)).

## Cameras (`SHOTS`)

`Shot.looking_at(name, eye, target, fov=None)` or `Shot(name, eye, (pitch, yaw, roll))`.
`eye` is the eye position (the harness subtracts 82). The engine draws fov 65–120;
see [testing.md](testing.md#cameras).

## The loop

```sh
python -m mohkit generate maps/<name>          # .map + validate + dist/<name>_plan.png, seconds
                                               # (+ dist/<name>_underlay.png with META["underlay"], see from-reference.md)
python -m mohkit build maps/<name> -q draft    # compile, package, screenshots
```
