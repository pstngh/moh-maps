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


def _engine_tris(srf, cutoff):
    """Triangles RB_StaticMesh draws at ``cutoff`` (with its break), as index triples."""
    ci = np.asarray(srf.collapse_index)
    if ci[2] < cutoff:
        return np.zeros((0, 3), int)
    rc = int((ci >= cutoff).sum())
    m = np.arange(len(ci))
    for i in range(rc, len(ci)):
        m[i] = m[srf.collapse[i]]
    t = m[np.asarray(srf.triangles)]
    bad = (t[:, 0] == t[:, 1]) | (t[:, 1] == t[:, 2]) | (t[:, 2] == t[:, 0])
    return t[: int(np.argmax(bad)) if bad.any() else len(t)]


def test_no_shards_from_seams_or_slivers():
    """Every triangle the engine draws, at every cutoff, has no area or lies near the
    original surface: a UV seam (two vertices per position) and zero-area strip leftovers
    (one with a vertex nothing else uses) once drew triangles to vertex 0 across the model
    (de_nuke's grey shards)."""
    g = _grid(10, 64.0, bump=12.0)
    pos, uv, tris = [p for p in g.positions], [u for u in g.uvs], [tuple(t) for t in g.triangles]
    n = 10
    # a UV seam down the middle column: right-hand triangles use copies of those vertices
    seam = {j * n + 5: None for j in range(n)}
    for k in seam:
        seam[k] = len(pos)
        pos.append(pos[k])
        uv.append(uv[k] + np.array([0.5, 0], np.float32))
    tris = [tuple(seam.get(v, v) if all(pos[w][0] >= pos[5][0] - 1e-3 for w in t) else v for v in t) for t in tris]
    # strip leftovers: zero-area triangles over two grid vertices far apart, the third corner
    # a copy of the first that nothing else uses (always dropped by the LOD)
    for k, j in ((11, 88), (23, 76), (34, 65)):
        pos.append(pos[k])
        uv.append(uv[k])
        tris.append((k, len(pos) - 1, j))
    nrm = np.tile([0.0, 0.0, 1.0], (len(pos), 1)).astype(np.float32)
    s0 = skd.SkdSurface("s", np.array(pos, np.float32), nrm, np.array(uv, np.float32), np.array(tris))
    res = L.simplify([s0])
    s = res.surfaces[0]
    _check(s)
    P = np.asarray(s.positions, np.float64)

    def area(p, t):
        return 0.5 * np.linalg.norm(np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]]), axis=1).sum()
    full = area(np.asarray(s0.positions, np.float64), np.asarray(s0.triangles))
    # simplifying a bumpy sheet changes its area by a little; a shard adds a lot (+35% before)
    for cut in sorted(set(np.asarray(s.collapse_index).tolist())):
        t = _engine_tris(s, cut)
        assert area(P, t) <= full * 1.02, (cut, area(P, t), full)


def test_vertex_colours_are_kept():
    """A flat grid lit dark in the middle (baked vertex lighting) simplifies for free without
    colours; with them, the free collapses (under 0.5 units) keep the dark spot."""
    g = _grid(12, 64.0)
    r = np.linalg.norm(np.asarray(g.positions, np.float64)[:, :2], axis=1)
    col = np.where(r < 20, 20.0, 200.0)[None, :, None] * np.ones((1, 1, 3))
    plain = L.simplify([g])
    lit = L.simplify([g], [col])
    free_plain = int(np.searchsorted(plain.errors, 0.5, "right"))
    free_lit = int(np.searchsorted(lit.errors, 0.5, "right"))
    assert free_lit < free_plain, (free_lit, free_plain)
    # at the free level, the vertices drawn near the middle are still the dark ones
    s = lit.surfaces[0]
    keep = np.asarray(s.collapse_index) >= free_lit + 1
    perm = lit.perms[0]
    dark = r[perm] < 20
    assert (keep & dark).sum() >= 1


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
        x = min((m - maxm) * L.REF_LODSCALE + maxm, cap)        # where the engine reads the curve
        m_eff = (x - maxm) / L.REF_LODSCALE + maxm              # the raw metric that x stands for
        cut = int(L.engine_cutoff(lod, m))
        assert cut <= max(L.cutoff_at(res.errors, R, m_eff * 0.75), val[0]), (m, cut)


def test_engine_table_like_the_engine():
    """``GetLODFile`` copies only the curve (48 bytes: all many stock .lod files hold, e.g.
    static/30cal_crate) and recomputes the constants; with no .lod file a collapsing model
    gets a default curve from ``lodIndex``. engine_cutoff read stored constants and raised
    on stock files before 2026-10-02."""
    res = L.simplify([_grid(bump=20.0)])
    lod = L.lod_control(res.errors, 100.0)
    for m in (5.0, 0.3, 0.05, 1e-3):
        assert abs(L.engine_cutoff(lod[:48], m) - L.engine_cutoff(lod, m)) < 1e-3, m
    t = L.engine_table(None, (40, 30, 20, 10, 0, 0, 0, 0, 0, 0))
    assert t == (1.0, 0.2, [(0.0, 0.0), (0.5, 30.0), (0.8, 30.0), (0.95, 30.0), (1.0, 0.0)]), t
    # near: r_lodcap keeps x <= 0.64, in the first segment (val 0 -> 30 over metric 1.0 -> 0.6):
    # 75 - 75 x = 27; far (x <= maxMetric): the last value, 0
    assert abs(L.engine_cutoff(t, 10.0) - 27.0) < 1e-6 and L.engine_cutoff(t, 1e-4) == 0.0
    assert L.can_lod(res.surfaces) and not L.can_lod([_grid()])


def test_propcost_reads_stock_models_under_the_map():
    """``propcost`` reads models from the map's pk3, then the retail paks under it (the map
    wins; later paks win, as the game loads them)."""
    import tempfile
    import zipfile

    from mohkit import propcost
    with tempfile.TemporaryDirectory() as d:
        paks = [Path(d) / f"{n}.pk3" for n in ("pak0", "pak1", "map")]
        for p, files in zip(paks, ({"a.tik": b"0", "b.tik": b"0", "c.tik": b"0"}, {"b.tik": b"1", "c.tik": b"1"},
                                   {"c.tik": b"map", "maps/x.bsp": b"bsp"})):
            with zipfile.ZipFile(p, "w") as z:
                for k, v in files.items():
                    z.writestr(k, v)
        read, bsp = propcost.pk3_reader(paks[2], paks[:2])
        assert (read("A.tik"), read("b.tik"), read("c.tik"), read("d.tik"), bsp) == (b"0", b"1", b"map", None, b"bsp")
    vc = propcost.ViewCost(verts=10, tris=5, models=1, by_model={"static/x.tik": 10})
    assert "x 10" in propcost.table({"cam": vc}) and "mean 10 vertices" in propcost.table({"cam": vc})


def test_vanish_distance():
    """A vanish distance drops every surface from there on, at any r_lodscale."""
    res = L.simplify([_grid(bump=20.0)])
    s = res.surfaces[0]
    R = 100.0
    lod = L.lod_control(res.errors, R, vanish=1500.0)
    k = 100.0 / L.VANISH_FOV
    for lodscale in (0.35, 0.45, 0.55, 1.1):
        near = int(L.engine_cutoff(lod, R * k / 1450.0, lodscale=lodscale))
        far = int(L.engine_cutoff(lod, R * k / 1550.0, lodscale=lodscale))
        assert L.drawn(s, near)[1] > 0 and L.drawn(s, far) == (0, 0), (lodscale, near, far)
    assert L.lod_control(res.errors, R, vanish=1e6) == L.lod_control(res.errors, R)   # beyond any view


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
