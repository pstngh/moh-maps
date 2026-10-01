"""Tests for ``mohkit.staticlight`` (static models added after the light stage).

Synthetic tests need only numpy. Tests that read compiled BSPs from the build cache
(``~/Library/Caches/mohkit/build/roots``) skip when those are missing.

    ~/Documents/moh-toolchain/venv/bin/python tests/test_staticlight.py
"""

from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit import config, staticlight as SL  # noqa: E402
from mohkit.bsp import BSP  # noqa: E402
from mohkit.source.convert import Converter  # noqa: E402

ROOTS = Path(config.load().build_dir) / "roots"


class SkipTest(Exception):
    pass


def _bsp(root: str, name: str) -> Path:
    p = ROOTS / root / "main" / "maps" / "dm" / f"{name}.bsp"
    if not p.is_file():
        raise SkipTest(f"{p} not built")
    return p


def test_axes_match_source_rotation() -> None:
    """Static models use AngleVectorsLeft (forward, left, up); the converter places props with
    Source's AngleMatrix columns. Both must agree or props rotate wrongly."""
    for ang in ((0, 0, 0), (0, 90, 0), (30, 45, 0), (-20, 200, 15), (90, 115, 0)):
        R = np.array(Converter._rot(ang))
        assert np.allclose(SL.axes(ang), R.T, atol=1e-9), ang


def test_world_mesh() -> None:
    inst = SL.StaticInstance("x.tik", (100, 0, 0), (0, 90, 0), 2.0, np.array([[1.0, 0, 0]]), np.array([[1.0, 0, 0]]))
    pos, nrm = SL.world_mesh(inst)
    assert np.allclose(pos, [[100, 2, 0]]) and np.allclose(nrm, [[0, 1, 0]])


def test_shade_neutral_on_average() -> None:
    """The facing term averages to ~1 over all directions; the grid scale follows the fit."""
    rng = np.random.default_rng(1)
    n = rng.normal(size=(20000, 3))
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    sun = np.array([0.0, 0.0, 1.0])
    low = SL.shade(np.full((len(n), 3), 40.0), n, sun)
    assert abs(low.mean() - 40.0) < 1.0
    high = SL.shade(np.full((len(n), 3), 200.0), n, sun)
    assert abs(high.mean() - 200 * 0.64) < 3.0


def test_take_statics_moves_collision() -> None:
    """static_* entities leave the map; their collision .map brushes come back placed in the
    world (translated, turned by the yaw, scaled), as Q3map would have baked them."""
    from mohkit.mapfile import Entity, MapFile
    from mohkit.build import box
    coll = MapFile([Entity({"classname": "worldspawn"}, [box((0, 0, 0), (32, 16, 8), "common/woodclip")])]).dumps()
    m = MapFile([Entity({"classname": "worldspawn"}),
                 Entity({"classname": "static_crate", "model": "static/crate.tik", "origin": "100 200 0",
                         "angle": "90", "scale": "2"}),
                 Entity({"classname": "info_player_deathmatch", "origin": "0 0 0"})])
    read = SL.files_reader({"models/static/crate.map": coll.encode()})
    statics, clips = SL.take_statics(m, read)
    assert [e.classname for e in m.entities] == ["worldspawn", "info_player_deathmatch"]
    assert statics == [("static/crate.tik", (100.0, 200.0, 0.0), (0.0, 90.0, 0.0), 2.0)]
    assert len(clips) == 1
    lo, hi = clips[0].bounds()
    # yaw 90 turns +x into +y: x 0..32, y 0..16 (x2) -> x -32..0, y 0..64 around (100, 200)
    assert np.allclose(lo, (68, 200, 0), atol=0.01) and np.allclose(hi, (100, 264, 16), atol=0.01), (lo, hi)


def _reference_grid(bsp: BSP, grid: SL.LightGrid, x: int, y: int) -> list[int]:
    """Palette indices of one grid column, walked exactly like R_GetLightingGridValue."""
    offs = np.frombuffer(bsp.lump("lightgridoffsets"), "<u2")
    data = bsp.lump("lightgriddata")
    bx, by, bz = (int(v) for v in grid.bounds)
    o = int(offs[bx + y + by * x]) + (int(offs[x]) << 8)
    out = []
    while len(out) < bz:
        n = data[o] - 256 if data[o] > 127 else data[o]
        o += 1
        if n < 0:
            out += list(data[o:o - n])
            o += -n
        else:
            out += [data[o]] * (n + 2)
            o += 1
    return out[:bz]


def test_grid_decode_matches_engine_walk() -> None:
    p = _bsp("dm_mk_medina", "mk_medina")
    bsp = BSP(p)
    grid = SL.LightGrid(bsp)
    rng = np.random.default_rng(0)
    for _ in range(200):
        x, y = int(rng.integers(grid.bounds[0])), int(rng.integers(grid.bounds[1]))
        assert list(grid.index[x, y]) == _reference_grid(bsp, grid, x, y), (x, y)


def test_inject_roundtrip() -> None:
    src = _bsp("dm_mk_medina", "mk_medina")
    with tempfile.TemporaryDirectory() as d:
        dst = Path(d) / "t.bsp"
        shutil.copy2(src, dst)
        before = BSP(dst)
        n0 = len(before.static_models())
        pos = np.array([[0, 0, 0], [16, 0, 0], [0, 16, 32]], np.float64)
        nrm = np.array([[0, 0, 1], [0, 0, 1], [1, 0, 0]], np.float64)
        origin = np.array(before.models()[0]["mins"]) / 2 + np.array(before.models()[0]["maxs"]) / 2
        info = SL.inject(dst, [SL.StaticInstance("static/test.tik", tuple(origin), (0, 45, 0), 1.0, pos, nrm)])
        after = BSP(dst)
        sms = after.static_models()
        assert len(sms) == n0 + 1 and sms[-1].model == "static/test.tik"
        assert sms[-1].num_vertex_data == 3
        assert sms[-1].first_vertex_data == before.lumps["staticmodeldata"][1]
        # every other lump is unchanged
        for name in ("shaders", "planes", "surfaces", "drawverts", "lightmaps", "entities", "nodes"):
            assert after.lump(name) == before.lump(name), name
        # the old models keep their leaf lists; the new one is listed in at least one leaf
        leafs = np.frombuffer(after.lump("leafs"), SL.LEAF_DT)
        idx = np.frombuffer(after.lump("staticmodelindexes"), "<u2")
        assert info["index_entries"] == len(idx)
        listed = {int(i) for l in leafs for i in idx[l["first_static"]:l["first_static"] + l["num_static"]]}
        assert n0 in listed


def test_matches_mohlight_means() -> None:
    """Grid-based colours have MOHlight's mean on a map lit by ambient only (161k vertices of
    converted props) and on sunlit mk_medina (retail props)."""
    from mohkit.pak import GameFS
    for root, name, tol in (("dm_smx_csgo160000", "smx_csgo160000", 0.05), ("dm_mk_medina", "mk_medina", 0.08)):
        p = _bsp(root, name)
        bsp = BSP(p)
        grid = SL.LightGrid(bsp)
        sun = SL.sun_direction(bsp)
        fs = GameFS(config.load().game_dir, loose=False)

        def rd(path, _fs=fs):
            try:
                return _fs.read(path)
            except Exception:  # noqa: BLE001
                return None
        local = SL.files_reader(ROOTS / root / "main")
        read = lambda q: local(q) or rd(q)  # noqa: E731
        data = np.frombuffer(bsp.lump("staticmodeldata"), np.uint8).reshape(-1, 3).astype(float)
        got, want = [], []
        for sm in bsp.static_models():
            try:
                pos, nrm = SL.tiki_mesh(read, sm.model)
            except FileNotFoundError:
                continue
            if len(pos) != sm.num_vertex_data:
                continue
            inst = SL.StaticInstance(sm.model, sm.origin, sm.angles, sm.scale, pos, nrm)
            got.append(SL.light_instance(grid, inst, sun).astype(float))
            f = sm.first_vertex_data // 3
            want.append(data[f:f + len(pos)])
        if not got:
            raise SkipTest(f"{name}: no readable static models")
        g, w = np.concatenate(got).mean(), np.concatenate(want).mean()
        assert abs(g - w) / w < tol, (name, g, w)


def _field(samples) -> SL.LightmapField:
    """A LightmapField from (position, normal, colour) samples, without a BSP."""
    f = SL.LightmapField.__new__(SL.LightmapField)
    p = np.array([s[0] for s in samples], float)
    n = np.array([s[1] for s in samples], float)
    c = np.array([s[2] for s in samples], float)
    f.count, f.steps = len(p), 17
    w = np.clip(n @ SL.AXES6.T, 0.0, None) ** 2
    keys = f._keys(np.floor((p + n * 4.0) / f.CELL).astype(np.int64))
    f.uniq, inv = np.unique(keys, return_inverse=True)
    f.sums = np.zeros((len(f.uniq), 6, 3))
    f.wts = np.zeros((len(f.uniq), 6))
    np.add.at(f.sums, inv, w[:, :, None] * c[:, None, :])
    np.add.at(f.wts, inv, w)
    return f


def test_lightmap_field_marches_to_facing_texels() -> None:
    """An up-facing vertex takes the first up-facing texels below it (a crate top over the
    floor), a side-facing one the wall behind it; slots that find nothing use the mean of
    those that did, and nothing in reach gives NaN."""
    floor = [((x, y, 0.0), (0, 0, 1), (100, 80, 60)) for x in range(-64, 65, 16) for y in range(-64, 65, 16)]
    shelf = [((x, y, 120.0), (0, 0, 1), (10, 10, 10)) for x in range(200, 300, 16) for y in range(-16, 17, 16)]
    wall = [((-96.0, y, z), (1, 0, 0), (40, 40, 40)) for y in range(-64, 65, 16) for z in range(0, 129, 16)]
    f = _field(floor + shelf + wall)
    pts = np.array([[0, 0, 100], [0, 0, 100], [0, 0, 100], [250, 0, 200], [5000, 0, 0]], float)
    nrm = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 1]], float)
    got = f.sample(pts, nrm)
    assert np.allclose(got[0], (100, 80, 60))            # floor 100 units below
    assert np.allclose(got[1], (40, 40, 40))             # the wall 96 units behind (-x)
    assert np.allclose(got[2], ((100 + 40) / 2, (80 + 40) / 2, (60 + 40) / 2))   # no +y texels: mean
    assert np.allclose(got[3], (10, 10, 10))             # the shelf is the first thing below
    assert np.isnan(got[4]).all()


def test_lightmap_field_beats_grid_on_medina() -> None:
    """On mk_medina (MOHlight-lit static props), lightmap-field colours correlate better with
    MOHlight's own vertex colours than the light grid's, at a scale near LIGHTMAP_TO_VERTEX."""
    from mohkit.pak import GameFS
    p = _bsp("dm_mk_medina", "mk_medina")
    bsp = BSP(p)
    field, grid, sun = SL.LightmapField(bsp), SL.LightGrid(bsp), SL.sun_direction(bsp)
    fs = GameFS(config.load().game_dir, loose=False)

    def rd(path):
        try:
            return fs.read(path)
        except Exception:  # noqa: BLE001
            return None
    local = SL.files_reader(ROOTS / "dm_mk_medina" / "main")
    read = lambda q: local(q) or rd(q)  # noqa: E731
    data = np.frombuffer(bsp.lump("staticmodeldata"), np.uint8).reshape(-1, 3).astype(float)
    F, G, W = [], [], []
    for sm in bsp.static_models():
        try:
            pos, nrm = SL.tiki_mesh(read, sm.model)
        except FileNotFoundError:
            continue
        if len(pos) != sm.num_vertex_data:
            continue
        inst = SL.StaticInstance(sm.model, sm.origin, sm.angles, sm.scale, pos, nrm)
        wp, wn = SL.world_mesh(inst)
        F.append(field.sample(wp + wn * 6, wn))
        G.append(SL.light_instance(grid, inst, sun).astype(float))
        W.append(data[sm.first_vertex_data // 3:sm.first_vertex_data // 3 + len(pos)])
    if not F:
        raise SkipTest("mk_medina: no readable static models")
    F, G, W = (np.concatenate(x) for x in (F, G, W))
    ok = ~np.isnan(F[:, 0])
    assert ok.mean() > 0.6, ok.mean()
    f, g, w = F[ok].mean(1), G[ok].mean(1), W[ok].mean(1)
    assert np.corrcoef(f, w)[0, 1] > np.corrcoef(g, w)[0, 1] + 0.05
    k = (w * f).sum() / (f * f).sum()
    assert abs(k - SL.LIGHTMAP_TO_VERTEX) < 0.1, k


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
