"""Core invariants: .map round trip, brush constructors, Carver sealing, grid splitting, texture fit.

Run: python tests/test_core.py   (pytest-compatible; no game data needed except the round-trip test,
which uses reference/ sources from the repo)
"""
import itertools
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from mohkit import geom  # noqa: E402
from mohkit.build import Air, Carver, Material, box, grid_split, hull, prism, subtract  # noqa: E402
from mohkit.kit import fit  # noqa: E402
from mohkit.mapfile import Brush, Entity, MapFile, Patch, Terrain  # noqa: E402


def _valid(b: Brush) -> bool:
    ws = b.windings()
    return len(ws) == len(b.faces) and all(len(w) >= 3 and geom.winding_area(w) > 0.01 for w in ws)


def test_roundtrip_stock():
    for name in ("reference/aa/mohdm2.map", "reference/aa/mohdm6.map"):
        m = MapFile.load(str(REPO / name))
        m2 = MapFile.parse(m.dumps())
        assert len(m.entities) == len(m2.entities)
        for a, b in zip(m.entities, m2.entities):
            assert a.props == b.props
            assert [type(p) for p in a.prims] == [type(p) for p in b.prims]
        kinds = {type(p) for _, p in m.iter_prims()}
        assert Brush in kinds


def test_constructors():
    assert _valid(box((0, 0, 0), (64, 32, 16)))
    assert _valid(prism([(0, 0), (64, 0), (80, 40), (10, 60)], 0, 32))
    assert _valid(prism([(0, 0), (10, 60), (80, 40), (64, 0)], 0, 32))  # clockwise input
    ramp = hull([(0, 0, 0), (0, 64, 0), (128, 0, 0), (128, 64, 0), (128, 0, 64), (128, 64, 64)])
    assert _valid(ramp) and len(ramp.faces) == 5
    # outward normals: every face's plane has the brush centre behind it
    for b in (box((0, 0, 0), (64, 32, 16)), ramp):
        pts = [p for w in b.windings() for p in w]
        c = geom.winding_center(pts)
        assert all(f.plane.distance(c) < 0 for f in b.faces)


def test_subtract_and_grid():
    a = ((0.0, 0.0, 0.0), (100.0, 100.0, 100.0))
    h = ((20.0, 20.0, 20.0), (40.0, 40.0, 40.0))
    parts = subtract(a, h)
    vol = sum((p[1][0] - p[0][0]) * (p[1][1] - p[0][1]) * (p[1][2] - p[0][2]) for p in parts)
    assert abs(vol - (100 ** 3 - 20 ** 3)) < 1e-6
    pieces = grid_split(((-600.0, 0.0, 0.0), (700.0, 16.0, 16.0)), 512)
    assert [p[0][0] for p in pieces] == [-600.0, -512.0, 0.0, 512.0]
    assert pieces[-1][1][0] == 700.0


def _covered(p, solids, airs) -> bool:
    inside = lambda b: all(b[0][i] <= p[i] <= b[1][i] for i in range(3))  # noqa: E731
    return any(inside(s) for s in solids) or any(inside(a.bounds) for a in airs)


def test_carver_seals():
    """Every point just outside the union of air lies inside a shell piece."""
    rnd = random.Random(7)
    cv = Carver(16)
    cv.room(0, 0, 0, 512, 512, 192)
    cv.room(528, 0, 0, 1040, 512, 256)
    cv.room(500, 192, 0, 540, 320, 112)       # door through the wall
    cv.room(0, 528, 0, 1040, 1300, 512, sky=True)
    cv.room(200, 500, 0, 312, 540, 112)
    solids = cv.shell_boxes()
    for a in cv.air:
        (x0, y0, z0), (x1, y1, z1) = a.bounds
        for _ in range(400):
            p = [rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(z0, z1)]
            ax = rnd.randrange(3)
            p[ax] = (a.bounds[0][ax] - 1) if rnd.random() < 0.5 else (a.bounds[1][ax] + 1)
            assert _covered(p, solids, cv.air), (a.name, p)
    # every exposed face of a shell piece is either caulk or faces air
    brushes = cv.brushes()
    assert all(_valid(b) for b in brushes)


def test_carver_bands():
    cv = Carver(16)
    stone, plaster = Material("general_structure/stonebricks1"), Material("general_structure/plaster_wall2")
    cv.add(Air(((0.0, 0.0, 0.0), (256.0, 256.0, 256.0)), walls=[(0, stone), (32, plaster)]))
    shaders = {f.shader for b in cv.brushes() for f in b.faces}
    assert {"general_structure/stonebricks1", "general_structure/plaster_wall2"} <= shaders


def test_brush_rejects_band_list():
    stone, plaster = Material("general_structure/stonebricks1"), Material("general_structure/plaster_wall2")
    for spec in ([(0, stone), (32, plaster)], {"sides": [(0, stone)]}):
        try:
            box((0, 0, 0), (64, 64, 64), spec)
            raise AssertionError("a band list on a brush must raise")
        except TypeError as e:
            assert "band" in str(e)


def test_spawn_under_palm_canopy():
    from mohkit import validate
    from mohkit.build import MapBuilder
    idx = validate.load_shader_index()
    if idx is None:
        print("skip test_spawn_under_palm_canopy: no game data")
        return
    b = MapBuilder("t")
    cv = Carver(16)
    cv.room(-512, -512, 0, 512, 512, 512, floor=Material("general_structure/floor4"), sky=True)
    b.carve(cv)
    b.prop("static/tree_regularpalm", 0, 0, 0)
    b.spawn((60, 0, 1), 0)    # under the canopy (foliageclip only stops bullets)
    b.spawn((0, 0, 1), 0)     # inside the trunk (woodclip)
    issues = [i for i in validate.check(b.to_map(), idx) if "overlaps solid" in i.message]
    assert len(issues) == 3 and all("(0.0, 0.0, 1.0)" in i.message for i in issues), issues  # dm + allied + axis


def test_fix_spawns_moves_out_of_walls():
    from mohkit import validate
    from mohkit.build import box
    floor = box((-256, -256, -16), (256, 256, 0), "general_structure/floor4")
    wall = box((40, -256, 0), (72, 256, 128), "general_structure/floor4")
    tomb = box((-256, -256, 0), (-200, -200, 128), "general_structure/floor4")
    world = Entity({"classname": "worldspawn"}, [floor, wall, tomb])
    spawns = [Entity({"classname": "info_player_deathmatch", "origin": o}) for o in ("30 0 1", "0 0 1", "-228 -228 1")]
    m = MapFile([world] + spawns)
    notes = validate.fix_spawns(m, reach=16)
    assert len(notes) == 2 and "moved" in notes[0] and "removed" in notes[1], notes
    assert [e.origin() for e in m.entities[1:]] == [(22.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    assert not [i for i in validate.check(m) if "overlaps solid" in i.message]


def test_fov_crop():
    from mohkit import game
    assert game.drawn_fov(30) == 65 and game.drawn_fov(None) == 80 and game.drawn_fov(140) == 120
    k = game.zoom_crop(30, 65)
    assert abs(k - 0.4207) < 1e-3
    assert game.camera_commands(game.Shot("a", (0, 0, 82), fov=30))[-1] == "cg_fov 65"


def test_fit_unmirrored():
    # +X facing wall: s runs +Y; image left edge at u0
    m = fit("x/win", (1, 0, 0), 100, 164, 200, scale=0.5)
    assert m.scale == (0.5, 0.5) and m.shift == (-200.0, 400.0)
    # -X facing wall is mirrored: negative s scale, left edge (for the viewer) at u1
    m = fit("x/win", (-1, 0, 0), 100, 164, 200, scale=0.5)
    assert m.scale[0] < 0 and m.shift[0] == 328.0


def test_kit_facade_terrain_ground():
    from mohkit import kit, validate
    from mohkit.build import MapBuilder
    b = MapBuilder("t")
    cv = Carver(16)
    street = cv.room(0, 0, 0, 1024, 256, 320, floor=Material("central_europe/strtset_cew"), sky=True)
    n_before = len(cv.air)
    placed = kit.facade(b, cv, street, "north", 0, 1024, ((64, 144), (208, 288)), doors=(512,),
                        shutters=Material("general_structure/beam_wood1"))
    niches = cv.air[n_before:]
    doors = [a for a in niches if a.bounds[0][2] == 0]
    assert placed == 9 and len(doors) == 1 and len(niches) == 10
    t = kit.terrain(b, 0, 0, 0, 2, 1, lambda x, y: 40 + (x % 256) / 8, "wilderness/m3l3grass_1")
    assert (t.width, t.height) == (17, 9) and len(t.controls) == 6
    assert all(s.height % 2 == 0 for s in t.samples)
    try:
        kit.terrain(b, 0, 0, 0, 1, 1, lambda x, y: x * 2, "x")
        raise AssertionError("expected >510 relief error")
    except ValueError:
        pass
    b.carve(cv)
    m = b.to_map()
    assert validate.ground_height(m, 500, 100, 1000) == 0


def test_editor_image_is_tga():
    from mohkit.shaders import editor_image
    assert editor_image("textures/x/wall.jpg") == "textures/x/wall.tga"
    assert editor_image("textures/x/fence.tga") == "textures/x/fence.tga"
    assert editor_image("textures/x/plain") == "textures/x/plain.tga"


def test_camera_measure():
    from mohkit.camera import Camera
    cam = Camera(1280, 720)
    assert abs(cam.focal - 572.0) < 1.0
    d = cam.floor_depth(530)
    assert abs(d - 276) < 1
    assert abs(cam.lateral(170, d) - 227) < 1
    assert abs(cam.height(263, d) - 129) < 1
    x, y = cam.project((d, cam.lateral(170, d), 0))
    assert abs(x - 170) < 0.01 and abs(y - 530) < 0.01


def test_disp_simplify_keeps_shared_edges():
    import numpy as np
    from mohkit.source.convert import _simplify_grids

    def grid(x0, bump=0.0):
        g = np.zeros((5, 5, 5))
        for i in range(5):
            for j in range(5):
                g[i, j] = (x0 + 16 * j, 16 * i, 0.0, j / 4, i / 4)
        g[2, 2, 2] = bump  # interior bump at row 2
        return g
    flat, bumpy = _simplify_grids([grid(0), grid(64, bump=10.0)], tol=1.0)
    assert bumpy.shape[:2] == (5, 5)  # the bump ramps from rows/cols 1 to 3: nothing is straight
    # the flat neighbour keeps every vertex the bumpy one keeps on their shared edge x = 64,
    # and drops its own straight interior columns
    assert flat.shape[:2] == (5, 2)
    assert sorted(round(float(r[-1, 1])) for r in flat) == [0, 16, 32, 48, 64]
    alone = _simplify_grids([grid(0)], tol=1.0)[0]
    assert alone.shape[:2] == (2, 2)


def test_compiled_difference():
    from mohkit.mapfile import compiled_difference
    def make(prop_z, clip_x, light=200):
        m = MapFile()
        m.worldspawn.prims.append(box((0, 0, 0), (clip_x, 64, 64)))
        m.entities.append(Entity({"classname": "script_model", "model": "a.tik", "origin": f"0 0 {prop_z}"}))
        m.entities.append(Entity({"classname": "light", "origin": "0 0 32", "light": str(light)}))
        return m
    base = make(6, 64)
    assert compiled_difference(base, make(16, 64)) is None            # only a runtime prop moved
    assert compiled_difference(base, make(16, 64.004)) is None        # last-digit rounding
    assert "plane moved" in compiled_difference(base, make(6, 65))    # geometry moved
    assert "keys changed" in compiled_difference(base, make(6, 64, 300))  # a baked light changed
    # the same plane through three other points is the same brush
    moved = make(6, 64)
    f = moved.worldspawn.brushes()[0].faces[0]
    a, b, c = f.points
    f.points = (b, c, a)
    assert compiled_difference(base, moved) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
