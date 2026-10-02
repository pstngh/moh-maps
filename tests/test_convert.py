"""Small tests for the CS:GO converter's helpers (no game data needed).

    ~/Documents/moh-toolchain/venv/bin/python tests/test_convert.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit.source import convert as C  # noqa: E402
from mohkit.source import modelconv as mc  # noqa: E402


def test_named_cameras() -> None:
    text = '''// comment "Not" "1 2 3 4 5"
"Cameras"
{
\t"T Spawn"\t\t"-2385.6 -1200.0 -230.2 29.1 151.1"
\t"B1"\t"548.7 -118.7 -457.9 30.2 -69.9"
}
'''
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "de_x_cameras.txt"
        p.write_text(text)
        cams = C.named_cameras(p, scale=2.0)
    assert [c.name for c in cams] == ["T Spawn", "B1"]
    assert cams[0].origin == (-4771.2, -2400.0, -460.4) and cams[0].angles == (29.1, 151.1, 0.0)


def test_shader_names_fit_q3map() -> None:
    """Q3map duplicates BSP shader entries of 60-character names (docs/toolchain.md)."""
    assert C.MAX_SHADER_NAME == 59
    long = "models/props/de_nuke/hr_nuke/nuke_light_fixture/nuke_fluorescent_light_cable_32"
    assert len(mc.texture_name(long)) <= 59
    assert len(mc.texture_name("metal/hr_metal/hr_metal_corrugated_001x")) <= 59


def test_yaw_to_hull() -> None:
    """A door mesh along +x whose MDL hull runs along +y is turned 90 degrees."""
    import numpy as np
    pts = np.array([[0, -2, 0], [60, 2, 110], [30, 0, 50]], float)
    R = C._yaw_to_hull(pts, (-2, 0, 0), (2, 60, 110))
    q = pts @ R.T
    assert np.allclose(q.min(0), (-2, 0, 0)) and np.allclose(q.max(0), (2, 60, 110))
    assert np.allclose(C._yaw_to_hull(pts, (0, -2, 0), (60, 2, 110)), np.eye(3))  # already matching


def test_rope_sag_is_parabola() -> None:
    """A 3-column patch row is a quadratic Bezier: with the control point 2 * sag below the
    chord's middle, the curve's middle hangs exactly `sag` below it."""
    import numpy as np
    a, b, sag = np.array([0.0, 0, 100]), np.array([400.0, 0, 100]), 50.0
    mid = (a + b) / 2 - np.array([0, 0, 2 * sag])
    curve_mid = 0.25 * a + 0.5 * mid + 0.25 * b
    assert np.allclose(curve_mid, (a + b) / 2 - np.array([0, 0, sag]))


def test_converter_methods_exist() -> None:
    """Every ``self.x(...)`` call in the converter names something the class defines (a
    cleanup once deleted ``_is_glass``/``windows`` and only a full conversion noticed)."""
    import re
    src = Path(C.__file__).read_text()
    called = set(re.findall(r"self\.([A-Za-z_]\w*)\(", src))
    missing = sorted(n for n in called if not hasattr(C.Converter, n))
    assert not missing, missing


def test_merge_ladder_boxes() -> None:
    """de_cache's A-site ladder (two rails + a 1.5-unit brush per rung) is one ladder;
    de_nuke's stacked pieces merge; a ladder 3 units to the side stays separate."""
    rails = [((-101, 1099, 1702), (-100, 1100, 1847)), ((-76, 1099, 1702), (-72, 1100, 1847))]
    rungs = [((-100, 1099, z), (-76, 1100, z + 1.5)) for z in range(1708, 1840, 16)]
    stacked = [((233, -860, -399), (234, -836, -288)), ((233, -860, -284), (234, -836, -56))]
    apart = [((-69, 1099, 1702), (-60, 1100, 1847))]
    got = sorted((lo.tolist(), hi.tolist()) for lo, hi in C.merge_ladder_boxes(rungs + rails + stacked + apart))
    assert got == [([-101, 1099, 1702], [-72, 1100, 1847]), ([-69, 1099, 1702], [-60, 1100, 1847]),
                   ([233, -860, -399], [234, -836, -56])], got


def test_open_yaw_sees_thin_walls() -> None:
    """Auto cameras look down the longest clear sightline; a 2-unit wall must block it."""
    from mohkit.build import box
    from mohkit.mapfile import Entity, MapFile
    m = "general_structure/floor4"
    walls = [box((-512, -128, -16), (512, 128, 0), m), box((-512, 128, 0), (512, 144, 128), m),
             box((-512, -144, 0), (512, -128, 128), m), box((-528, -144, 0), (-512, 144, 128), m),
             box((512, -144, 0), (528, 144, 128), m), box((64, -128, 0), (66, 128, 128), m)]
    mf = MapFile([Entity({"classname": "worldspawn"}, walls)])
    assert C._open_yaw(mf, [(0.0, 0.0, 50.0)]) == [180.0]


def test_ladder_facing() -> None:
    """Converted ladders (de_mirage, if CS:GO is installed). The leaning ladder's square
    volume must face the ledge (+x); as a func_ladder it climbs 8 units off its far face.
    All were verified in game with game.ladder_probe."""
    import os
    root = Path(os.environ.get("CSGO_DIR", "/Users/pstn/Documents/Games/csgo"))
    bsp = root / "csgo" / "maps" / "de_mirage.bsp"
    if not bsp.is_file():
        print("skip test_ladder_facing: no de_mirage.bsp")
        return
    cv = C.Converter(str(bsp), str(root), C.Options(name="cs_ladtest", ladder_style="func_ladder"))
    cv.brushes()
    cv.ladders()
    got = [(r["angle"], r["origin"][:2]) for r in cv.report["ladders"]]
    assert got == [(270, [-992.0, -206.0]), (0, [156.0, -1972.0]), (0, [456.0, 668.0])], got
    # default: CS-style step columns against the same walls, from the floor to the volume top
    cv = C.Converter(str(bsp), str(root), C.Options(name="cs_ladtest"))
    cv.brushes()
    assert cv.ladders() == []
    got = [(r["angle"], r["origin"][:2], r["zmin"], r["zmax"]) for r in cv.report["ladders"]]
    assert got == [(270, [-992.0, -220.0], -168.0, -20.0), (0, [158.0, -1972.0], -168.0, -8.0),
                   (0, [454.0, 668.0], -258.0, -112.0)], got
    assert len(cv._ladder_step_brushes) == 10 + 10 + 10


def test_prop_assets_are_per_map() -> None:
    """Every prop file a conversion writes is under the map's own name: installed pk3s that
    share a path override each other (cs_cache's trucks were drawn with another map's LOD
    and vertex order, 2026-10-02). A few de_dust2 props, if CS:GO is installed."""
    import os
    from types import SimpleNamespace
    from mohkit.pak import unowned_paths
    root = Path(os.environ.get("CSGO_DIR", "/Users/pstn/Documents/Games/csgo"))
    bsp = root / "csgo" / "maps" / "de_dust2.bsp"
    if not bsp.is_file():
        print("skip test_prop_assets_are_per_map: no de_dust2.bsp")
        return
    cv = C.Converter(str(bsp), str(root), C.Options(name="cs_pertest"))
    props = cv.bsp.static_props().props
    pick = {}
    for p in sorted(props, key=lambda p: p.model):    # a few models, one with collision
        pick.setdefault(p.model, p)
    few = [pick[m] for m in sorted(pick)[:4]]
    cv.bsp.static_props = lambda: SimpleNamespace(props=few)
    cv._entity_props = lambda: []
    cv.props()
    assert any(k.endswith(".skd") for k in cv.assets) and any(k.endswith((".jpg", ".tga")) for k in cv.assets)
    assert unowned_paths(cv.assets, "cs_pertest", C.SHARED_PATHS) == []
    assert all(k.startswith(("models/csgo/cs_pertest/", "textures/csgo/cs_pertest_p/"))
               for k in cv.assets if k.startswith(("models/", "textures/"))), sorted(cv.assets)


def _st(f, p):
    """Texture coordinates (texels / scale) of point ``p`` on face ``f`` (Q3 projection)."""
    import math
    from mohkit import geom
    n = geom.cross(geom.sub(f.points[2], f.points[0]), geom.sub(f.points[1], f.points[0]))
    ln = math.sqrt(geom.dot(n, n))
    xv, yv = C.texture_axis(tuple(v / ln for v in n))
    sv = next(i for i in range(3) if xv[i])
    tv = next(i for i in range(3) if yv[i])
    r = math.radians(f.rotate)
    co, si = math.cos(r), math.sin(r)
    return (xv[sv] * (co * p[sv] + si * p[tv]) / f.scale[0] + f.shift[0],
            yv[tv] * (-si * p[sv] + co * p[tv]) / f.scale[1] + f.shift[1])


def test_scale_face_keeps_texels() -> None:
    """A face scaled about a point (the 3D skybox room shrunk about sky_camera) shows the same
    texel at each scaled point, for any rotation and mirrored scales."""
    from mohkit.mapfile import Face
    c = (5000.0, -1600.0, 400.0)
    for pts, rot, sc, sh in [(((0, 0, 64), (0, 64, 64), (64, 0, 64)), 0, (1, 1), (0, 0)),
                             (((10, 0, 0), (10, 0, 64), (10, 64, 0)), 33, (0.5, -2), (7, -3)),
                             (((0, 5, 0), (64, 5, 0), (0, 5, 64)), -71, (1.25, 0.75), (12.5, 40))]:
        f = Face(tuple(tuple(float(v) for v in q) for q in pts), "x", sh, rot, sc)
        for k in (0.5, 0.25):
            g = C.scale_face(f, k, c)
            for p in f.points:
                q = tuple(c[i] + k * (p[i] - c[i]) for i in range(3))
                a, b = _st(f, p), _st(g, q)
                assert abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3, (a, b, k, rot)


def _bare_converter(scale: float = 1.0):
    """A Converter with no BSP behind it, for the geometry helpers."""
    cv = C.Converter.__new__(C.Converter)
    cv.opt = C.Options(name="t", scale=scale)
    cv.report = {"warnings": [], "dropped": {}}
    return cv


def test_ladder_rail_clips() -> None:
    """Clips flanking a 24-wide ladder (de_vertigo's rails) go; a clip block under it, a cap
    on top and the backing clip of a 6-deep ladder stay (de_rats, de_nuke)."""
    import numpy as np
    from mohkit.build import box
    cv = _bare_converter()
    cv._ladder_box_cache = [[np.array([0.0, 0.0, 0.0]), np.array([26.0, 24.0, 186.0])],     # vertigo-like
                            [np.array([500.0, 0.0, 0.0]), np.array([546.0, 6.6, 172.0])]]   # rats-like, 6.6 deep
    rails = [box((-30, 24, 0), (26, 56, 186), "common/clip"), box((-30, -32, 0), (26, 0, 186), "common/clip")]
    keep = [box((13, -12, -94), (110, 92, 0), "common/clip"),           # a block under the ladder
            box((0, 0, 186), (26, 24, 190), "common/playerclip"),       # a cap
            box((499, 6.6, 0), (548, 11, 170), "common/clip"),          # backing of the 6.6-deep one
            box((498, -4, 0), (502, 1, 172), "common/clip"),            # a post at its front corner
            box((-30, -32, 0), (26, 0, 186), "csgo/wall")]              # drawn: not a clip
    out = cv._drop_ladder_rail_clips(rails + keep)
    assert out == keep and cv.report["ladder_rail_clips_dropped"] == 2, cv.report


def test_displacement_heights() -> None:
    """Floor heights over displacement triangles (de_cbble's ground in front of a ladder);
    walls and ceilings don't count."""
    import numpy as np
    from types import SimpleNamespace
    xs = np.linspace(0, 64, 3)
    floor = np.stack(list(np.meshgrid(xs, xs, indexing="ij")) + [np.zeros((3, 3))], -1)
    floor[..., 2] = -140 - floor[..., 0] / 16      # slopes down 4 units over 64 along x
    ceiling = floor.copy()
    ceiling[..., 2] = 100
    cv = _bare_converter()
    cv.bsp = SimpleNamespace(displacements=lambda: [SimpleNamespace(positions=floor, normal=(0.0, 0.0, 1.0)),
                                                    SimpleNamespace(positions=ceiling, normal=(0.0, 0.0, -1.0))])
    hs = cv._displacement_heights(40, 10)
    assert len(hs) == 1 and abs(hs[0] - (-142.5)) < 1e-6, hs
    assert cv._displacement_heights(80, 10) == []
    cv._world_brushes = []
    assert abs(cv._floor_below(48, 50, -100, 96) - (-143)) < 1e-6


def test_light_spot_points_along_vrad() -> None:
    """A ceiling spot (pitch -90) aims at the floor: VRAD's z = +sin(pitch). With -sin every
    converted ceiling spot lit the ceiling (de_nuke's dark radio rooms, 2026-10-01)."""
    from mohkit.source.bsp import Entity
    cv = _bare_converter()
    e = Entity([("classname", "light_spot"), ("origin", "0 0 100"), ("angles", "-90 0 0"),
                ("_light", "255 255 255 200"), ("_cone", "30")])
    light, target = cv._light(e, "light_spot")
    assert light["target"] == target["targetname"]
    assert float(target["origin"].split()[2]) < 100 - 60, target["origin"]


def test_opaque_resize_keeps_colour() -> None:
    """Pillow resizes RGBA premultiplied: an opaque texture whose alpha is a Source specular
    mask (alpha 0) came out black (decals as black squares, darkened props, 2026-10-01)."""
    import io
    import numpy as np
    from PIL import Image
    rgba = np.zeros((1024, 1024, 4), np.uint8)
    rgba[..., :3] = 200
    rgba[::7, ::7, 3] = 255                 # a sparse mask, mostly 0
    cv = _bare_converter()
    cv.opt.max_texture = 512
    cv.assets = {}
    path, size = cv._write_image("t/x", rgba, False)
    assert size == (512, 512)
    got = np.asarray(Image.open(io.BytesIO(cv.assets[path])).convert("RGB"), np.float32)
    assert abs(got.mean() - 200) < 3, got.mean()


def test_debris_type_by_surfaceprop() -> None:
    """Retail func_window debris 0-3 are all glass: metal and wood breakables need their own."""
    assert C.debris_type(["glass"]) == C.DEBRIS_GLASS
    assert C.debris_type(["Wood_Panel"]) == C.DEBRIS_WOOD
    assert C.debris_type(["metalvent"]) == C.DEBRIS_METAL
    assert "metal_section" in C.debris_tiki(C.DEBRIS_METAL) and "crate-jib" in C.debris_tiki(C.DEBRIS_WOOD)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
