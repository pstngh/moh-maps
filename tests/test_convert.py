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

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
