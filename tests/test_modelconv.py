"""Tests for the Source prop -> MOHAA static model converter (``mohkit.source.modelconv``).

Run as a script (prints a per-model report)::

    /Users/pstn/Documents/moh-toolchain/venv/bin/python tests/test_modelconv.py

or under pytest. Synthetic tests need only numpy/Pillow. Tests against the
retail MOHAA paks (layout comparison) skip when the game is not installed, and
conversion tests skip when CS:GO is not installed. Converted files go to
``$MOHKIT_TEST_OUT`` (default ``/private/tmp/claude-501/modelconv``) - never into
the repository.

In-game verification (compile + OpenMoHAA screenshots) is not part of this file;
it was done with a scratch harness, see the module docstring of modelconv for
the conventions it established.
"""

from __future__ import annotations

import math
import os
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit import geom  # noqa: E402
from mohkit.mapfile import MapFile  # noqa: E402
from mohkit.source import modelconv as mc  # noqa: E402
from mohkit.source import skd  # noqa: E402
from mohkit.source.studiomdl import read_phy  # noqa: E402

CSGO_ROOT = Path(os.environ.get("CSGO_DIR", "/Users/pstn/Documents/Games/csgo"))
MOH_MAIN = Path(os.environ.get("MOH_MAIN", "/Users/pstn/Documents/Games/moh/main"))
OUT_DIR = Path(os.environ.get("MOHKIT_TEST_OUT", "/private/tmp/claude-501/modelconv"))
DUST2 = CSGO_ROOT / "csgo" / "maps" / "de_dust2.bsp"

# Diverse de_dust2 props: crate, barrel, car, palm (alpha), door, facade/arch pieces, glass, weeds.
SAMPLE_PROPS = (
    "models/props/props_crates/wooden_crate_64x64.mdl",
    "models/props/de_dust/dust_rusty_barrel.mdl",
    "models/props_vehicles/car002a.mdl",
    "models/props_foliage/tree_palm_dust.mdl",
    "models/props/de_dust/dust_metal_door.mdl",
    "models/props/de_dust/dust_arch_large.mdl",
    "models/props/de_dust/du_window_4x8_arch.mdl",
    "models/props_vehicles/hmmwv.mdl",
    "models/props_vehicles/hmmwv_glass.mdl",
    "models/props/cs_italy/weed_tuft02.mdl",
    "models/props/de_dust/sign_shop01.mdl",
    "models/props_fortifications/concrete_wall001_96_reference.mdl",
)

try:  # pytest is optional
    import pytest
except ImportError:  # pragma: no cover
    pytest = None  # type: ignore[assignment]


class SkipTest(Exception):
    pass


def skip(msg: str) -> None:
    if pytest is not None:
        pytest.skip(msg)
    raise SkipTest(msg)


def out_dir() -> Path:
    d = OUT_DIR
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(tempfile.gettempdir()) / "modelconv"
        d.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    assert repo not in d.resolve().parents, "test output must not go into the repository"
    return d


# ---------------------------------------------------------------------------
# Synthetic tests


def _cube(size: float = 32.0):
    """A 24-vertex cube (hard edges) with outward CCW triangles and 0..1 UVs per face."""
    pos, nrm, uv, tris = [], [], [], []
    for axis in range(3):
        for sgn in (-1, 1):
            n = [0.0, 0.0, 0.0]
            n[axis] = sgn
            u_ax, v_ax = [a for a in range(3) if a != axis]
            base = len(pos)
            for cu, cv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                p = [0.0, 0.0, 0.0]
                p[axis] = sgn * size / 2
                p[u_ax] = (cu - 0.5) * size
                p[v_ax] = (cv - 0.5) * size
                pos.append(p)
                nrm.append(n)
                uv.append((cu, cv))
            a, b, c, d = base, base + 1, base + 2, base + 3
            t1, t2 = (a, b, c), (a, c, d)
            pa, pb, pc = (np.array(pos[i]) for i in t1)
            if np.dot(np.cross(pb - pa, pc - pa), n) < 0:
                t1, t2 = (a, c, b), (a, d, c)
            tris += [t1, t2]
    return (np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uv, np.float32),
            np.array(tris, np.int32))


def test_skd_roundtrip_and_layout() -> None:
    pos, nrm, uv, tris = _cube()
    surf = skd.SkdSurface("cube_00", pos, nrm, uv, tris)
    data = skd.build_skd("cube.skd", [surf, skd.SkdSurface("cube_01", pos + 64, nrm, uv, tris)])
    assert data[:4] == b"SKMD" and struct.unpack_from("<i", data, 4)[0] == 5
    ns, nb, ob, osf, end = struct.unpack_from("<5i", data, 72)
    assert (ns, nb, ob) == (2, 1, 148) and end == len(data)
    assert struct.unpack_from("<10i", data, 92) == (0,) * 10
    assert struct.unpack_from("<4i", data, 132) == (0, end, 0, end)
    # bone record: ORIGIN / worldbone / POSROT, 84-byte header, channel names, 4-byte aligned
    name, parent, btype, obase, ochan, onames, bend = struct.unpack_from("<32s32s5i", data, ob)
    assert name.rstrip(b"\0") == b"ORIGIN" and parent.rstrip(b"\0") == b"worldbone"
    assert (btype, obase, ochan) == (1, 84, 96) and osf == ob + bend and bend % 4 == 0
    assert data[ob + 96 : ob + onames] == b"ORIGIN rot\0ORIGIN pos\0"
    # surface arrays in retail order: triangles, vertices, collapse, collapse index
    sid, sname, ntri, nvert, ssp, otri, overt, ocol, oend, ocolidx = struct.unpack_from("<4s64s8i", data, osf)
    assert sid == b"SKL " and sname.rstrip(b"\0") == b"cube_00" and (ntri, nvert, ssp) == (12, 24, 0)
    assert otri == 100 < overt < ocol < ocolidx < oend
    assert overt - otri == 12 * ntri and ocol - overt == 48 * nvert and oend - ocolidx == 4 * nvert
    assert not any(data[osf + ocol : osf + oend])  # zero-filled collapse arrays
    info = skd.read_skd(data)
    assert info.version == 5 and info.bones == [("ORIGIN", "worldbone", 1)]
    got = info.surfaces[0]
    assert np.allclose(got.positions, pos) and np.allclose(got.normals, nrm) and np.allclose(got.uvs, uv)
    assert (got.triangles == tris).all()  # read_skd flips back to CCW
    # on disk the winding is clockwise w.r.t. the normals, like every retail SKD
    raw = np.frombuffer(data, "<i4", 3 * ntri, osf + otri).reshape(-1, 3)
    a, b, c = pos[raw[:, 0]], pos[raw[:, 1]], pos[raw[:, 2]]
    assert (np.einsum("ij,ij->i", np.cross(b - a, c - a), nrm[raw[:, 0]]) < 0).all()


def test_skd_limits() -> None:
    pos, nrm, uv, tris = _cube()
    for bad in ("", "x" * 29):
        try:
            skd.build_skd("a.skd", [skd.SkdSurface(bad, pos, nrm, uv, tris)])
        except ValueError:
            pass
        else:
            raise AssertionError(f"surface name {bad!r} accepted")
    try:
        skd.build_tiki("models/x", "a.skd", "a.skc", [(f"s{i}", "x") for i in range(25)])
    except ValueError:
        pass
    else:
        raise AssertionError("25 TIKI surfaces accepted")
    try:
        skd.build_skd("a.skd", [skd.SkdSurface("s", pos, nrm, uv, tris), skd.SkdSurface("S", pos, nrm, uv, tris)])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate (case-insensitive) surface names accepted")


def test_skc_layout() -> None:
    data = skd.build_skc((-50.4, -70.84, 0.0), (49.33, 72.41, 90.73))
    assert len(data) == 192
    info = skd.read_skc(data)
    assert (info.version, info.flags, info.size, info.num_frames) == (13, 0, 192, 1)
    assert abs(info.frame_time - 1 / 30) < 1e-7
    assert info.channels == ["ORIGIN pos", "ORIGIN rot"]
    assert info.data == [(0, 0, 0, 0), (0, 0, 0, 1)]
    assert abs(info.radius - 126.56) < 0.01  # retail indycrate.skc has 126.5569 for these bounds
    assert struct.unpack_from("<i", data, 92)[0] == 96  # iOfsChannels


def test_tiki_text() -> None:
    t = skd.build_tiki("models/csgo/props", "crate.skd", "crate.skc", [("crate_00", "textures/csgo/crate")],
                       quaked="static_csgo_crate", bounds=((-8, -8, 0), (8, 8, 16)))
    assert re.search(r"setup\s*\{\s*scale 1\s*path models/csgo/props\s*skelmodel crate.skd\s*"
                     r"surface crate_00 shader textures/csgo/crate\s*\}", t)
    assert re.search(r"animations\s*\{\s*idle\s+crate.skc\s*\}", t)
    assert "classname object" in t and "/*QUAKED static_csgo_crate (0.5 0.0 0.5) (-8 -8 0) (8 8 16)" in t


def test_weld_and_split() -> None:
    pos, nrm, uv, tris = _cube()
    # duplicate every vertex: weld must restore 24 vertices and 12 triangles
    p2 = np.concatenate([pos, pos])
    n2 = np.concatenate([nrm, nrm])
    u2 = np.concatenate([uv, uv])
    t2 = np.concatenate([tris, tris + 24])
    wp, wn, wu, wt = mc.weld(p2, n2, u2, t2)
    assert len(wp) == 24 and len(wt) == 24 and wt.max() < 24
    assert np.allclose(wp, pos)  # first-occurrence order is kept
    # a 40x40 grid (1681 vertices, 3200 triangles) must split under the SKD limits
    g = 41
    xs, ys = np.meshgrid(np.arange(g), np.arange(g))
    gp = np.stack([xs.ravel(), ys.ravel(), np.zeros(g * g)], 1).astype(np.float32)
    gn = np.tile([0, 0, 1], (g * g, 1)).astype(np.float32)
    gu = gp[:, :2] / g
    quads = [(i * g + j, i * g + j + 1, (i + 1) * g + j + 1, (i + 1) * g + j) for i in range(g - 1) for j in range(g - 1)]
    gt = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))], np.int32)
    chunks = mc.split_surface(gp, gn, gu, gt)
    assert len(chunks) >= 2
    assert sum(len(c[3]) for c in chunks) == len(gt)
    for cp, cn, cu, ct in chunks:
        assert len(cp) <= skd.MAX_SURFACE_VERTS and len(ct) <= skd.MAX_SURFACE_TRIS and ct.max() < len(cp)
    # geometry preserved: every chunk triangle maps to an original triangle's positions
    orig = {tuple(sorted(map(tuple, gp[t].tolist()))) for t in gt}
    for cp, _cn, _cu, ct in chunks:
        for t in ct:
            assert tuple(sorted(map(tuple, cp[t].tolist()))) in orig


def test_hull_brush() -> None:
    pos, _nrm, _uv, tris = _cube(40)
    brush = mc._hull_brush(pos.astype(np.float64) + (10, 20, 30), tris, "common/woodclip")
    assert brush is not None and len(brush.faces) == 6
    lo, hi = brush.bounds()
    assert np.allclose(lo, (-10, 0, 10), atol=1e-3) and np.allclose(hi, (30, 40, 50), atol=1e-3)
    for f in brush.faces:  # every plane points away from the centre
        assert f.plane.distance((10, 20, 30)) < 0 and f.has_parm("detail")
    text = mc.collision_map([brush])
    m = MapFile.parse(text)
    assert len(m.worldspawn.brushes()) == 1 and m.worldspawn.brushes()[0].shaders() == {"common/woodclip"}


def test_thin_hull_is_thickened() -> None:
    """Sheet-metal hulls (0.4 units thick in Source) become 1-unit brushes instead of slivers."""
    pos, _nrm, _uv, tris = _cube(1.0)
    pts = pos.astype(np.float64) * (0.4, 30, 30)
    brush = mc._hull_brush(pts, tris, "common/metalclip")
    assert brush is not None and len(brush.faces) == 6
    lo, hi = brush.bounds()
    assert np.allclose(np.array(hi) - np.array(lo), (1.0, 30, 30), atol=1e-3)
    assert mc._hull_brush(pos.astype(np.float64) * (0.01, 0.01, 30), tris, "x") is None  # a line


def test_phy_synthetic() -> None:
    """A one-solid, one-ledge PHY: a unit IVP box (metres, IVP axes) -> Source inches."""
    pts_src = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], np.float64) * 0.0254 * 32
    ivp = np.stack([pts_src[:, 0], -pts_src[:, 2], pts_src[:, 1]], 1)  # inverse of (x, z, -y)
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
             (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    ledge_size = 16 + 16 * len(faces)
    points = b"".join(struct.pack("<4f", *p, 0) for p in ivp)
    tri_bytes = b"".join(struct.pack("<4I", i, a, b, c) for i, (a, b, c) in enumerate(faces))
    # layout after the 48-byte surface header: ledge (+ triangles), points, one leaf node
    ledge = struct.pack("<iiIhh", ledge_size, 0, 0, len(faces), 0) + tri_bytes
    node_ofs = 48 + len(ledge) + len(points)
    node = struct.pack("<ii3ff4B", 0, 48 - node_ofs, 0, 0, 0, 1, 0, 0, 0, 0)
    surface = (struct.pack("<7f", 0, 0, 0, 0, 0, 0, 1) + struct.pack("<ii", 0, node_ofs) + bytes(12)
               + ledge + points + node)
    solid = b"VPHY" + struct.pack("<hhi3fi", 0x100, 0, len(surface), 0, 0, 0, 0) + surface
    data = struct.pack("<4i", 16, 0, 1, 0) + struct.pack("<i", len(solid)) + solid + b'solid {\n"index" "0"\n}\0'
    phy = read_phy(data)
    assert len(phy.solids) == 1 and len(phy.pieces) == 1
    lo, hi = phy.bounds()
    assert np.allclose(lo, (0, 0, 0), atol=1e-4) and np.allclose(hi, (32, 32, 32), atol=1e-4)
    assert '"index" "0"' in phy.keyvalues


def test_names_and_surface_types() -> None:
    d, b = mc.model_names("models/props/de_dust/Dust_Rusty_Barrel.mdl")
    assert (d, b) == ("models/csgo/props/de_dust", "dust_rusty_barrel")
    d, b = mc.model_names("models/props/de_dust/dust_rusty_barrel.mdl", skin=1, scale=1.5)
    assert b == "dust_rusty_barrel_skin1_x1p5"
    long = "models/props_fortifications/some_really_long_model_name_that_goes_on_and_on_forever.mdl"
    for pre in ("csgo", "csgo/de_dust2"):
        d, b = mc.model_names(long, pre)
        assert len(f"{d}/{b}_p2_nc.tik") <= skd.MAX_QPATH
    assert mc.model_names(long)[1] != mc.model_names(long.replace("forever", "forevex"))[1]
    t = mc.texture_name("models/props/de_dust/hr_dust/dust_crates/dust_crate_style_01_72x36x87_a_really_long")
    assert len(t) + 4 <= skd.MAX_QPATH and t.startswith("textures/csgo/")
    assert mc.surface_type("metal_sand_barrel") == ("metal", "common/metalclip")
    assert mc.surface_type("wood_crate") == ("wood", "common/woodclip")
    assert mc.surface_type("concrete") == ("rock", "rock")
    assert mc.surface_type("chainlink") == ("grill", "common/grillclip")
    assert mc.surface_type("default") == (None, "solid")
    assert mc.clip_shader_name("rock") == "csgo/clip_rock"
    assert mc.clip_shader_text("rock").startswith("textures/csgo/clip_rock\n{")
    assert "surfaceparm rock" in mc.clip_shader_text("rock")
    assert mc.clip_shader_text("common/woodclip") is None


# ---------------------------------------------------------------------------
# Retail MOHAA layout comparison


def _retail_file(name: str) -> bytes:
    pak = MOH_MAIN / "Pak0.pk3"
    if not pak.is_file():
        skip(f"retail paks not found at {MOH_MAIN}")
    with zipfile.ZipFile(pak) as z:
        return z.read(name)


def test_matches_retail_layout() -> None:
    """Our SKD/SKC headers use the same idents, versions, offsets and array order as retail indycrate."""
    rskd = _retail_file("models/static/indycrate/indycrate.skd")
    rskc = _retail_file("models/static/indycrate/indycrate.skc")
    pos, nrm, uv, tris = _cube()
    ours = skd.build_skd("cube.skd", [skd.SkdSurface("cube_00", pos, nrm, uv, tris)])
    for data in (rskd, ours):
        assert data[:4] == b"SKMD" and struct.unpack_from("<i", data, 4)[0] == 5
        ns, nb, ob, osf, end = struct.unpack_from("<5i", data, 72)
        assert ob == 148 and nb == 1 and end == len(data)
        assert struct.unpack_from("<4i", data, 132) == (0, end, 0, end)
        _n, _p, btype, obase, ochan, _bn, _be = struct.unpack_from("<32s32s5i", data, ob)
        assert (btype, obase, ochan) == (1, 84, 96)
        sid, _s, ntri, nvert, ssp, otri, overt, ocol, oend, ocolidx = struct.unpack_from("<4s64s8i", data, osf)
        assert sid == b"SKL " and ssp == 0 and otri == 100 and otri < overt < ocol < ocolidx < oend
        assert ocol - overt == 48 * nvert  # one weight, no morphs per vertex
    ours_skc = skd.build_skc((-1, -1, 0), (1, 1, 2))
    for data in (rskc, ours_skc):
        info = skd.read_skc(data)
        assert data[:4] == b"SKAN" and (info.version, info.flags, info.num_frames) == (13, 0, 1)
        assert info.size == len(data) and abs(info.frame_time - 1 / 30) < 1e-7
        assert len(info.channels) == 2 and info.channels[0].endswith(" pos") and info.channels[1].endswith(" rot")
    # retail triangles are clockwise w.r.t. their normals, like ours on disk
    r = skd.read_skd(rskd).surfaces[0]  # read_skd returns CCW
    a, b, c = (r.positions[r.triangles[:, i]] for i in range(3))
    nsum = sum(r.normals[r.triangles[:, i]] for i in range(3))
    dots = np.einsum("ij,ij->i", np.cross(b - a, c - a), nsum)
    agree = (dots > 0).sum() / max(1, (dots != 0).sum())   # 303 of 372 non-degenerate triangles
    assert agree > 0.75, agree


# ---------------------------------------------------------------------------
# CS:GO conversions

_FS = None


def csgo_fs():
    global _FS
    if not (CSGO_ROOT / "csgo" / "pak01_dir.vpk").is_file():
        skip(f"CS:GO not found at {CSGO_ROOT}")
    if _FS is None:
        _FS = mc.source_fs(CSGO_ROOT, bsp=DUST2 if DUST2.is_file() else None)
    return _FS


def _check_converted(m: mc.ConvertedModel, mdl: str) -> None:
    f = m.files
    assert m.tik in f and m.tiks[0] == m.tik
    nverts = 0
    for tik in m.tiks:
        text = f[tik].decode("latin-1")
        path = re.search(r"^\s*path (\S+)", text, re.M).group(1)
        skd_name = re.search(r"^\s*skelmodel (\S+)", text, re.M).group(1)
        skc_name = re.search(r"^\s*idle\s+(\S+)", text, re.M).group(1)
        binds = re.findall(r"^\s*surface (\S+) shader (\S+)", text, re.M)
        assert 0 < len(binds) <= skd.MAX_TIKI_SURFACES
        info = skd.read_skd(f[f"{path}/{skd_name}"])
        nverts += sum(len(s.positions) for s in info.surfaces)
        assert [s.name for s in info.surfaces] == [b for b, _ in binds]
        for s in info.surfaces:
            assert len(s.name) <= skd.MAX_SURFACE_NAME
            assert 0 < len(s.positions) <= skd.MAX_SURFACE_VERTS and 0 < len(s.triangles) <= skd.MAX_SURFACE_TRIS
            assert np.allclose(np.linalg.norm(s.normals, axis=1), 1, atol=1e-3)
        skc = skd.read_skc(f[f"{path}/{skc_name}"])
        allp = np.concatenate([s.positions for s in info.surfaces])
        assert np.allclose(skc.bounds[0], allp.min(0), atol=1e-3) and np.allclose(skc.bounds[1], allp.max(0), atol=1e-3)
        for _surf, shader in binds:
            assert len(shader) <= skd.MAX_QPATH and shader in m.shaders
        cmap = MapFile.parse(f[tik[:-4] + ".map"].decode("latin-1"))
        for br in cmap.worldspawn.brushes():
            assert all(len(w) >= 3 for w in br.windings())
            assert all(fc.has_parm("detail") for fc in br.faces)
    for name, text in m.shaders.items():
        assert len(name) <= skd.MAX_QPATH
        img = re.search(r"^\s*map (\S+)", text, re.M)
        if img:
            assert img.group(1) in f, img.group(1)
            assert "rgbGen static" in text
    for path in f:
        assert len(path) <= skd.MAX_QPATH or path.startswith("scripts/"), path
        if path.endswith(".tga"):
            w, h = struct.unpack_from("<HH", f[path], 12)
            assert w & (w - 1) == 0 and h & (h - 1) == 0 and max(w, h) <= 512
    assert m.vertices == nverts, (m.vertices, nverts)


def test_convert_samples(report: bool = False) -> None:
    fs = csgo_fs()
    out = out_dir() / "samples"
    models = []
    for mdl in SAMPLE_PROPS:
        if fs.try_read(mdl) is None:
            continue
        m = mc.convert_model(fs, mdl)
        _check_converted(m, mdl)
        models.append(m)
        if report:
            print(f"  {mdl}\n     -> {m.tik}  v={m.vertices} tri={m.triangles} surf={m.surfaces} "
                  f"parts={len(m.tiks)} brushes={m.collision_brushes} mats={len(m.materials)}")
            for w in m.warnings:
                print(f"     ! {w}")
    assert len(models) >= 6, "sample props missing from the CS:GO install"
    by = {m.source: m for m in models}
    barrel = by["models/props/de_dust/dust_rusty_barrel.mdl"]
    assert barrel.has_collision and "common/metalclip" in barrel.files[barrel.tik[:-4] + ".map"].decode()
    (lo, hi) = barrel.bounds
    assert abs(lo[2]) < 0.5 and 44 < hi[2] < 46 and 14 < hi[0] < 16  # 30 wide, 45 tall, origin at the base
    palm = by["models/props_foliage/tree_palm_dust.mdl"]
    fronds = [t for n, t in palm.shaders.items() if "branches" in n]
    assert fronds and "alphaFunc GE128" in fronds[0] and "cull none" in fronds[0]
    frond_img = re.search(r"map (\S+)", fronds[0]).group(1)
    assert palm.files[frond_img][16] == 32  # 32-bit TGA keeps alpha
    glass = by.get("models/props_vehicles/hmmwv_glass.mdl")
    if glass:
        assert any("blendFunc blend" in t for t in glass.shaders.values())
    window = by["models/props/de_dust/du_window_4x8_arch.mdl"]
    assert not window.has_collision and any("no .phy" in w for w in window.warnings)
    bundled = mc.bundle(models)
    scripts = [p for p in bundled if p.startswith("scripts/")]
    assert scripts == ["scripts/csgo_models.shader"]
    names = re.findall(r"^(\S+)\s*\n\{", bundled[scripts[0]].decode(), re.M)
    assert len(names) == len(set(names))
    for path, data in bundled.items():
        p = out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def test_convert_variants() -> None:
    fs = csgo_fs()
    mdl = "models/props/de_dust/dust_rusty_barrel.mdl"
    base = mc.convert_model(fs, mdl)
    nc = mc.convert_model(fs, mdl, solid=0)
    bb = mc.convert_model(fs, mdl, solid=2)
    assert nc.tik.endswith("_nc.tik") and not nc.has_collision
    assert bb.tik.endswith("_bb.tik") and bb.collision_brushes == 1
    assert "{" not in nc.files[nc.tik[:-4] + ".map"].decode().split('"worldspawn"', 1)[1]  # no brushes
    # variants share the mesh files byte for byte, so they can be packaged together
    skd_path = base.tik[:-4] + ".skd"
    assert nc.files[skd_path] == base.files[skd_path] == bb.files[skd_path]
    merged = mc.bundle([base, nc, bb])
    assert base.tik in merged and nc.tik in merged and bb.tik in merged
    big = mc.convert_model(fs, mdl, scale=2.0)
    assert np.allclose(np.array(big.bounds), 2 * np.array(base.bounds), atol=1e-3)
    assert big.tik != base.tik
    jpg = mc.convert_model(fs, mdl, jpeg_quality=85)
    assert any(p.endswith(".jpg") for p in jpg.files) and not any(p.endswith(".tga") for p in jpg.files)
    assert all(".jpg" in t for t in jpg.shaders.values() if "map " in t)
    # centre: bounds symmetric about the TIKI origin in x/y, the origin above the top (the
    # engine lights the model from 8 below it), collision moved with the mesh
    c = mc.convert_model(fs, mdl, solid=2, centre=True)
    pv = np.array(c.pivot)
    assert np.allclose((np.array(c.bounds[0]) + np.array(c.bounds[1]))[:2], 0, atol=1e-3)
    assert abs(c.bounds[1][2] + mc.LIGHT_ABOVE_TOP + 8) < 1e-3
    # the pivot comes from the mesh alone: centred variants still share their mesh files
    c_nc = mc.convert_model(fs, mdl, solid=0, centre=True)
    assert c_nc.pivot == c.pivot and c_nc.files[skd_path] == c.files[skd_path]
    assert np.allclose(np.array(c.bounds) + pv, np.array(bb.bounds), atol=1e-3)
    from mohkit.mapfile import MapFile
    def clip_box(m):
        b = MapFile.parse(m.files[m.tik[:-4] + ".map"].decode()).worldspawn.brushes()[0]
        pts = np.array([q for w in b.windings() for q in w])
        return pts.min(0), pts.max(0)
    assert np.allclose(np.array(clip_box(c)) + pv, np.array(clip_box(bb)), atol=0.5)


def test_partition_over_24_surfaces() -> None:
    fs = csgo_fs()
    mdl = "models/props_vehicles/hmmwv.mdl"
    if fs.try_read(mdl) is None:
        skip(f"{mdl} not in this install")
    old = skd.MAX_TIKI_SURFACES
    skd.MAX_TIKI_SURFACES = 5  # the real model has 14 surfaces; force a split
    try:
        m = mc.convert_model(fs, mdl)
    finally:
        skd.MAX_TIKI_SURFACES = old
    assert len(m.tiks) == math.ceil(m.surfaces / 5) and m.tiks[1].endswith("_p2.tik")
    assert any("partitioned" in w for w in m.warnings)
    first = MapFile.parse(m.files[m.tiks[0][:-4] + ".map"].decode())
    rest = MapFile.parse(m.files[m.tiks[1][:-4] + ".map"].decode())
    assert first.worldspawn.brushes() and not rest.worldspawn.brushes()  # collision only once


def test_phy_matches_mesh() -> None:
    """Collision hulls line up with the render mesh (IVP axes/units converted correctly)."""
    fs = csgo_fs()
    for mdl in ("models/props/props_crates/wooden_crate_64x64.mdl", "models/props_vehicles/car002a.mdl"):
        m = mc.convert_model(fs, mdl)
        cmap = MapFile.parse(m.files[m.tik[:-4] + ".map"].decode())
        pts = [p for br in cmap.worldspawn.brushes() for w in br.windings() for p in w]
        lo, hi = geom.bounds_of(pts)
        assert np.allclose(lo, m.bounds[0], atol=2.0) and np.allclose(hi, m.bounds[1], atol=2.0), (mdl, lo, hi, m.bounds)


SYNTHETIC = [test_skd_roundtrip_and_layout, test_skd_limits, test_skc_layout, test_tiki_text, test_weld_and_split,
             test_hull_brush, test_thin_hull_is_thickened, test_phy_synthetic, test_names_and_surface_types, test_matches_retail_layout]
GAME = [test_convert_variants, test_partition_over_24_surfaces, test_phy_matches_mesh]


def main() -> int:
    failed = 0
    for fn in SYNTHETIC + GAME + [lambda: test_convert_samples(report=True)]:
        name = getattr(fn, "__name__", "test_convert_samples")
        name = "test_convert_samples" if name == "<lambda>" else name
        try:
            fn()
            print(f"PASS {name}")
        except SkipTest as e:
            print(f"SKIP {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print("FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
