"""Progressive LOD (mohkit.lod): collapse tables obey the engine's rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from mohkit import lod as L
from mohkit.source import skd


def _grid(n=12, size=64.0, z=0.0, name="g", bump=0.0):
    xs = np.linspace(-size, size, n)
    pos = np.array([(x, y, z + bump * np.exp(-(x * x + y * y) / (size * size / 8))) for y in xs for x in xs])
    uv = np.array([(i / (n - 1), j / (n - 1)) for j in range(n) for i in range(n)])
    tris = []
    for j in range(n - 1):
        for i in range(n - 1):
            a, b, c, d = j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i
            tris += [(a, b, c), (a, c, d)]
    nrm = np.tile([0.0, 0.0, 1.0], (len(pos), 1))
    return skd.SkdSurface(name, pos.astype(np.float32), nrm.astype(np.float32), uv.astype(np.float32),
                          np.array(tris))


def _check(srf):
    ci, col = np.asarray(srf.collapse_index), np.asarray(srf.collapse)
    assert (np.diff(ci) <= 0).all(), "collapseIndex must not increase"
    top = ci[0]
    for i in range(1, len(ci)):
        if ci[i] < top:
            assert col[i] < i, "collapse target must come first"


def _simulate(srf, cutoff):
    """Triangles still non-degenerate at ``cutoff`` (the engine's loop, without the break)."""
    ci = np.asarray(srf.collapse_index)
    rc = int((ci >= cutoff).sum())
    m = np.arange(len(ci))
    for i in range(rc, len(ci)):
        m[i] = m[srf.collapse[i]]
    t = m[np.asarray(srf.triangles)]
    return ~((t[:, 0] == t[:, 1]) | (t[:, 1] == t[:, 2]) | (t[:, 2] == t[:, 0]))


def test_flat_grid_collapses_for_free():
    res = L.simplify([_grid()])
    s = res.surfaces[0]
    _check(s)
    assert res.steps > 100
    # a flat grid loses its inner vertices at no error; the border is kept by its penalty planes
    assert (res.errors[: res.steps // 2] < 1e-6).all()


def test_triangles_vanish_in_order():
    res = L.simplify([_grid(bump=20.0)])
    s = res.surfaces[0]
    _check(s)
    for cut in (1, res.steps // 3, res.steps // 2, res.steps):
        ok = _simulate(s, cut)
        # every surviving triangle comes before every vanished one (the engine stops at the first)
        if (~ok).any():
            assert ok[: np.argmax(~ok)].all() and not ok[np.argmax(~ok):].any()
        v, t = L.drawn(s, cut)
        assert t == int(ok.sum())


def test_two_surfaces_share_a_seam():
    a = _grid(8, 32.0, name="a")
    b = _grid(8, 32.0, name="b")
    b.positions = b.positions + np.array([64.0, 0, 0], np.float32)    # touching along x = 32
    res = L.simplify([a, b])
    for s in res.surfaces:
        _check(s)
    perm = res.perm
    assert sorted(perm.tolist()) == list(range(128))
    data = skd.build_skd("t.skd", res.surfaces)
    back = skd.read_skd(data)
    for (col, ci), s in zip(back.collapse, res.surfaces):
        assert (col == s.collapse).all() and (ci == s.collapse_index).all()


def test_lod_curve():
    res = L.simplify([_grid(bump=20.0)])
    R = 100.0
    lod = L.lod_control(res.errors, R)
    assert lod is not None and len(lod) == 96
    c = L.read_lod(lod)
    pos = [p for p, _ in c["curve"]]
    val = [v for _, v in c["curve"]]
    assert pos == sorted(pos) and val == sorted(val) and c["minMetric"] > c["maxMetric"]
    assert L.engine_cutoff(lod, 10.0) <= L.engine_cutoff(lod, 1e-4)
    # where the engine evaluates the curve (m' = (m - maxM) * lodscale + maxM, capped), it never
    # allows more error than the target (the grid fit can be off by one grid step: 0.75x)
    minm, maxm = c["minMetric"], c["maxMetric"]
    cap = maxm + (minm - maxm) * L.REF_LODCAP
    for m in np.exp(np.linspace(np.log(5.0), np.log(1e-3), 200)):
        mp = min((m - maxm) * L.REF_LODSCALE + maxm, cap)
        cut = int(L.engine_cutoff(lod, m))
        assert cut <= max(L.cutoff_at(res.errors, R, mp * 0.75), val[0]), (m, cut)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
