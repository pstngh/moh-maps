"""mohkit.site: reference grid, building masses, outdoor air round a cliff-top plateau."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mohkit import kit, site, validate  # noqa: E402
from mohkit.build import Carver, MapBuilder, Material, aabb  # noqa: E402


def test_refgrid():
    g = site.RefGrid(12, (256, 272))
    assert g.point(256, 272) == (0, 0)
    assert g.x(266) == 128 and g.y(262) == 128          # 10 px = 120 units, snapped to 16
    assert g.rect(250, 260, 260, 270) == (g.x(250), g.y(270), g.x(260), g.y(260))


def _plateau():
    b = MapBuilder("t")
    cv = Carver(16)
    b.carve(cv)
    outer = (-2048, -2048, 2048, 2048)
    hut = site.Building("hut", (-256, -256, 256, 256), 192, Material("norway/penwall1a"))
    solids = site.plateau_solids([(-768, -768, 768, 768)], [hut], 0, -1024)
    rock, snow = Material("central_europe_winter/forstsnow_rock256"), Material("norway/norsnow_lite256")
    site.outdoor_air(cv, aabb(*outer[:2], -1024, *outer[2:], 1024), solids,
                     floor=site.floors(-1024, 0, snow, snow, snow),
                     walls=site.walls(outer, [hut], Material("sky/mohday2"), rock, 0), cuts=(0,))
    hut.room(cv, 0, 176, snow, Material("norway/wall_verts_base2"), Material("norway/nor_panelflat"))
    hut.door(b, cv, "south", 0)
    site.void_triggers(b, outer, -1024, solids)
    b.spawn((0, 0, 1), 0, kinds=("deathmatch",))           # inside the hut
    b.spawn((0, -600, 1), 0, kinds=("deathmatch",))        # on the plateau
    return b, cv, hut


def test_cliff_top_is_sealed_and_textured():
    b, cv, hut = _plateau()
    shell = cv.shell_boxes()
    rnd = random.Random(3)
    inside = lambda p, bb: all(bb[0][i] <= p[i] <= bb[1][i] for i in range(3))  # noqa: E731
    for a in cv.air:
        (x0, y0, z0), (x1, y1, z1) = a.bounds
        for _ in range(200):
            p = [rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(z0, z1)]
            ax = rnd.randrange(3)
            p[ax] = (a.bounds[0][ax] - 1) if rnd.random() < 0.5 else (a.bounds[1][ax] + 1)
            assert any(inside(p, s) for s in shell) or any(inside(p, o.bounds) for o in cv.air), (a.name, p)
    # every spawn and every trigger column centre is in air (no leak)
    assert not [i for i in validate.check_air(b) if i.severity == "error"]
    # the hut's outside walls carry its face, the cliff below the plateau carries the rock
    shaders = {f.shader for br in cv.brushes() for f in br.faces}
    assert {"norway/penwall1a", "central_europe_winter/forstsnow_rock256", "sky/mohday2"} <= shaders
    # the door made a frame and a lantern
    assert any(e.classname == "light" for e in b.entities)


def test_kit_fixtures_build_valid_brushes():
    b = MapBuilder("t")
    kit.railing(b, 0, 0, 512, 0, 0)
    kit.fence(b, 0, 64, 0, 600)
    kit.dish(b, 0, 0, 0, 64, 45)
    kit.billboard(b, 0, 0, 0, 192, "y")
    kit.catwalk(b, 0, 0, 192, 1024, 0, -512)
    kit.catwalk(b, 0, 0, 192, 1024, 0, -512, outer="west")
    kit.power_line(b, [(0, 0), (0, 600), (300, 1200)])
    kit.gondola(b, 0, 0, 160, (-96, 316, -2000, 120), 300)
    kit.antenna_mast(b, 0, 0, -64, 520)
    kit.parapet(b, 0, 0, 256, 256, 192)
    kit.dome(b, 0, 0, 0, 96, "norway/nor_panelflat")
    site.mountain_ring(b, Material("norway/norsnow_med256ns", density=256), -1536, n=4)
    for e in b.to_map().entities:
        for br in e.brushes():
            assert len(br.windings()) == len(br.faces), "every face of a fixture brush has area"
    issues = [i for i in validate.check(b.to_map()) if i.severity == "error" and "spawn" not in i.message]
    assert not issues, issues



def _bounds(br):
    pts = [p for w in br.windings() for p in w]
    return tuple(round(min(p[i] for p in pts), 3) for i in range(3)), tuple(round(max(p[i] for p in pts), 3) for i in range(3))


def test_ladders_and_breakables():
    """``kit.ladder``: a func_ladder whose origin brush sits on the climb face, angle into the
    wall, trigger 8 units in front; ``kit.step_ladder``: clip slices 1 unit shallower per
    step; ``kit.breakable``: metal/wood debris TIKIs go into ``b.files``."""
    b = MapBuilder("t")
    kit.ladder(b, "east", 0, -260, 0, 160, rails=kit.STEEL_H)          # wall at x = 0, climber west
    lad = [e for e in b.to_map().entities if e.get("classname") == "func_ladder"]
    assert len(lad) == 1 and lad[0]["angle"] == "0"
    boxes = {br.faces[0].shader: _bounds(br) for br in lad[0].brushes()}
    (olo, ohi), (tlo, thi) = boxes["common/origin"], boxes["common/trigger"]
    assert [(a + c) / 2 for a, c in zip(olo, ohi)] == [-4, -260, 80], (olo, ohi)   # on the face (depth 4)
    assert tlo == (-12, -276, 0) and thi == (0, -244, 160), (tlo, thi)
    kit.ladder(b, "north", 512, 100, 0, 128)
    assert [e for e in b.entities if e.get("classname") == "func_ladder"][-1]["angle"] == "90"
    b2 = MapBuilder("t")
    kit.step_ladder(b2, "west", 64, 0, 40, 0, 40, rise=16, depth=1)    # wall at x = 64, climber east
    slabs = sorted(_bounds(br) for br in b2.world.prims)
    assert [(lo[0], hi[0], lo[2], hi[2]) for lo, hi in slabs] == [(64, 67, 0, 16), (64, 66, 16, 32), (64, 65, 32, 40)], slabs
    assert [z for z in kit.step_slices(0, 40)] == [(0, 16, 3), (16, 32, 2), (32, 40, 1)]
    rec = b2.ladders[0]                        # what `mohkit build --ladders` climbs
    assert rec["exit"] == "forward" and rec["angle"] == 180 and rec["probe_start"] == [64 + 3 + 28, 20.0, 1]
    kit.step_ladder(b2, "west", 64, 0, 40, 0, 40, exit=None)
    assert "exit" not in b2.ladders[1]
    b3 = MapBuilder("t")
    kit.breakable(b3, (0, 0, 0), (8, 64, 64), "mohtest/flrwood1_rep", "wood")
    kit.breakable(b3, (0, 96, 0), (8, 160, 64), "glass/glass_clear", "glass")
    assert sorted(b3.files) == ["models/fx/windows/debris_8.tik"]
    assert [e["debristype"] for e in b3.entities] == ["8", "0"]
    for bb in (b, b2, b3):
        for e in bb.to_map().entities:
            for br in e.brushes():
                assert len(br.windings()) == len(br.faces)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
