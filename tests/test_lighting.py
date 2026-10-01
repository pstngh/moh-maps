"""Tests for ``mohkit.source.lighting`` (CS:GO's baked light moved into MOHAA lightmaps)
and ``mohkit.exposure``.

Synthetic tests need only numpy/Pillow. Tests that read CS:GO maps skip when the game
is missing.

    ~/Documents/moh-toolchain/venv/bin/python tests/test_lighting.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit import config, exposure  # noqa: E402
from mohkit.source import lighting as L  # noqa: E402


class SkipTest(Exception):
    pass


def _decode(offs: bytes, data: bytes, bounds) -> np.ndarray:
    """The decoder of ``staticlight.LightGrid`` on raw lumps."""
    bx, by, bz = bounds
    o16 = np.frombuffer(offs, "<u2")
    idx = np.zeros((bx, by, bz), np.uint8)
    hi = o16[:bx].astype(np.int64) << 8
    for x in range(bx):
        for y in range(by):
            o = int(o16[bx + by * x + y]) + int(hi[x])
            z = 0
            while z < bz:
                n = data[o] - 256 if data[o] > 127 else data[o]
                o += 1
                if n < 0:
                    k = min(-n, bz - z)
                    idx[x, y, z:z + k] = np.frombuffer(data, np.uint8, k, o)
                    o += -n
                    z += k
                else:
                    k = min(n + 2, bz - z)
                    idx[x, y, z:z + k] = data[o]
                    o += 1
                    z += k
    return idx


def test_grid_encoding_round_trips():
    rng = np.random.default_rng(3)
    idx = rng.integers(0, 6, (7, 5, 300)).astype(np.uint8)      # short runs and literals
    idx[:, :, 100:250] = 9                                      # a run longer than 129
    idx[2, 3, :] = np.arange(300) % 256                         # a literal stretch over 128
    offs, data = L.encode_grid(idx)
    assert len(offs) == 2 * (7 + 7 * 5)
    assert np.array_equal(_decode(offs, data, idx.shape), idx)


def test_quantize_fits_the_palette():
    rng = np.random.default_rng(1)
    cols = rng.uniform(0, 200, (20000, 3))
    pal, lab = L.quantize(cols, 255, iters=4)
    assert len(pal) <= 255 and lab.max() < len(pal) and len(lab) == len(cols)
    err = np.abs(pal[lab] - cols).mean()
    assert err < 12, err


def test_tonemap_curve():
    lum = np.array([0.0, 0.01, 0.1, 0.5, 1.0, 2.3, 10.0])
    rgb = np.repeat(lum[:, None], 3, 1)
    v = L.tonemap(rgb, 1.0)[:, 0]
    assert np.all(np.diff(v) > 0) and v[0] == 0 and v.max() <= L.CAP
    # below the knee it is plain display gamma: 127 * L^(1/2.2)
    assert abs(v[2] - 127 * 0.1 ** (1 / 2.2)) < 0.01
    # with headroom the value is divided by the gain: L = 1 reaches the old cap times gain
    g = 1.6
    vg = L.tonemap(rgb, 1.0, ceiling=g)[:, 0]
    assert np.all(vg <= L.CAP + 1e-9)
    assert abs(vg[2] * g - 127 * 0.1 ** (1 / 2.2)) < 0.01      # shading unchanged below the knee
    assert vg[5] * g > 140 and vg[6] * g < 127 * g              # sunlight passes the old cap, never the new
    # hue is kept: a warm light stays warm
    warm = L.tonemap(np.array([[2.0, 1.0, 0.5]]), 1.0)[0]
    assert warm[0] > warm[1] > warm[2]


def test_headroom_gain():
    dark = np.full((16, 16, 3), 100, np.uint8)
    white = np.full((16, 16, 3), 245, np.uint8)
    assert abs(L.headroom_gain(dark) - L.HEADROOM_MAX) < 1e-9   # capped
    assert L.headroom_gain(white) < 1.03
    mid = np.full((16, 16, 3), 200, np.uint8)
    assert abs(L.headroom_gain(mid) - 1.25) < 1e-6
    # transparent texels don't count
    rgba = np.zeros((16, 16, 4), np.uint8)
    rgba[..., :3] = 125
    rgba[:8, :, 3] = 255
    rgba[8:, :, :3] = 255
    assert abs(L.headroom_gain(rgba) - 1.6) < 1e-9
    out = L.apply_gain(np.dstack([dark, np.full((16, 16), 7, np.uint8)]), 1.5)
    assert out[0, 0, 0] == 150 and out[0, 0, 3] == 7


def test_exposure_measure():
    from PIL import Image
    a = np.zeros((720, 1280, 3), np.uint8)
    a[:, :640] = 255                                              # half white, half black
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.png"
        Image.fromarray(a).save(p)
        e = exposure.measure(p)
    assert abs(e.white - 0.5) < 0.01 and abs(e.black - 0.5) < 0.01
    assert abs(e.blown - 0.5) < 0.01 and "BLOWN" in e.flags and "CRUSHED" in e.flags


def test_translate_keeps_texture_alignment():
    """Maps moved into MOHAA's +-8192 (de_vertigo) keep every texel in place."""
    import math
    from mohkit.mapfile import Face
    from mohkit.source.convert import texture_axis, translate_face

    def tex(f, p):
        pts = np.array(f.points, float)
        n = np.cross(pts[2] - pts[0], pts[1] - pts[0])
        xv, yv = texture_axis(tuple(n / np.linalg.norm(n)))
        sv = next(i for i in range(3) if xv[i])
        tv = next(i for i in range(3) if yv[i])
        r = math.radians(f.rotate)
        c, s = math.cos(r), math.sin(r)
        return (xv[sv] * (c * p[sv] + s * p[tv]) / f.scale[0] + f.shift[0],
                yv[tv] * (-s * p[sv] + c * p[tv]) / f.scale[1] + f.shift[1])

    T = (512.0, -1024.0, -11264.0)
    for pts, rot, sc in ((((0, 0, 64), (64, 0, 64), (0, 64, 64)), 0, (1, 1)),
                         (((0, 0, 0), (0, 64, 0), (0, 0, 64)), 33, (0.5, 2)),
                         (((0, 0, 0), (64, 64, 0), (0, 0, 64)), -70, (0.25, 0.75))):
        f = Face(pts, "x", (13.0, -7.0), rot, sc)
        g = translate_face(f, T)
        for p in pts:
            q = tuple(p[i] + T[i] for i in range(3))
            assert np.allclose(tex(f, p), tex(g, q), atol=1e-3)


def _csgo_map(name: str):
    from mohkit.source.bsp import SourceBSP
    csgo = config.load().csgo_dir
    p = Path(csgo or "") / "csgo" / "maps" / f"{name}.bsp"
    if not csgo or not p.is_file():
        raise SkipTest(f"{p} missing")
    return SourceBSP(str(p))


def test_luxels_stay_on_their_polygon():
    """A face's lightmap is the rectangle around its polygon; VRAD leaves the luxels well
    outside it black. de_inferno face 333 (sunlit CT floor) has 102 of 324 luxels under
    0.3: none may survive, and those kept are lit."""
    b = _csgo_map("de_inferno")
    lux = L.source_luxels(b)
    f = lux.face == 333
    assert 120 < f.sum() < 324 - 90, f.sum()
    lum = lux.rgb[f] @ np.array([0.2126, 0.7152, 0.0722])
    assert np.percentile(lum, 5) > 0.5, np.percentile(lum, 5)
    assert abs(L.exposure_for(b) - (0.75 * 1.5) ** 0.5) < 1e-6


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except SkipTest as e:
                print("skip", name, e)
            except Exception as e:  # noqa: BLE001
                failed += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, e)
    sys.exit(1 if failed else 0)
