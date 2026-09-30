"""Tests and a smoke report for the Source (CS:GO) readers in ``mohkit.source``.

Run as a script (prints a per-map report)::

    /Users/pstn/Documents/moh-toolchain/venv/bin/python tests/test_source_readers.py [map ...]

or under pytest. The synthetic tests need nothing but numpy/Pillow; the map
tests skip when CS:GO is not installed. Game data is only read at runtime and
decoded images go to ``$MOHKIT_TEST_OUT`` (default ``/private/tmp/claude-501/
mohkit_source_test``) - never into the repository.

Environment: ``CSGO_DIR`` (default ``/Users/pstn/Documents/Games/csgo``).
"""

from __future__ import annotations

import collections
import io
import os
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit import geom  # noqa: E402
from mohkit.source import bsp as bspmod  # noqa: E402
from mohkit.source import mdl, vmt, vtf  # noqa: E402
from mohkit.source.bsp import SourceBSP  # noqa: E402
from mohkit.source.vpk import VPK, SearchPath, ZipSource  # noqa: E402

CSGO_ROOT = Path(os.environ.get("CSGO_DIR", "/Users/pstn/Documents/Games/csgo"))
GAME_DIR = CSGO_ROOT / "csgo"
OUT_DIR = Path(os.environ.get("MOHKIT_TEST_OUT", "/private/tmp/claude-501/mohkit_source_test"))
DEFAULT_MAPS = ("de_dust2", "cs_office", "de_inferno")

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
        d = Path(tempfile.gettempdir()) / "mohkit_source_test"
        d.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    assert repo not in d.resolve().parents, "test output must not go into the repository"
    return d


_VPK: Optional[VPK] = None


def csgo_vpk() -> VPK:
    global _VPK
    p = GAME_DIR / "pak01_dir.vpk"
    if not p.is_file():
        skip(f"CS:GO not found at {GAME_DIR}")
    if _VPK is None:
        _VPK = VPK(p)
    return _VPK


# ---------------------------------------------------------------------------
# Synthetic tests (no game data)


def test_lzma_roundtrip() -> None:
    payload = bytes(range(256)) * 300 + b"entities { }" * 50
    blob = bspmod.compress_lzma(payload)
    assert blob[:4] == b"LZMA"
    assert bspmod.decompress_lzma(blob) == payload


def test_lzma_lump_in_bsp() -> None:
    """A synthetic BSP whose entity lump is LZMA-compressed parses transparently."""
    ents = b'{\n"classname" "worldspawn"\n"skyname" "sky_x"\n}\n{\n"classname" "light"\n"OnFoo" "a,b"\n"OnFoo" "c,d"\n}\n\0'
    comp = bspmod.compress_lzma(ents)
    header = bytearray(1036)
    header[0:4] = b"VBSP"
    struct.pack_into("<i", header, 4, 21)
    struct.pack_into("<4i", header, 8, 1036, len(comp), 0, len(ents))  # lump 0
    struct.pack_into("<i", header, 8 + 16 * 64, 7)
    b = SourceBSP(bytes(header) + comp)
    assert b.lumps[0].compressed
    assert [e.classname for e in b.entities] == ["worldspawn", "light"]
    assert b.entities[1].get_all("onfoo") == ["a,b", "c,d"]


def _build_vpk(tmp: Path, version: int) -> dict[str, bytes]:
    """Write a small VPK set: preload-only, _000 archive, and 0x7fff-embedded entries."""
    files = {
        "materials/test/a.vmt": b'"UnlitGeneric" { "$basetexture" "test/a" }',
        "materials/test/big.bin": bytes(range(256)) * 40,
        "readme": b"root file without extension",
        "scripts/embedded.txt": b"stored after the tree in the _dir file",
    }
    archive = bytearray()
    embedded = bytearray()
    tree = bytearray()
    by_ext: dict[str, dict[str, list[str]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in files:
        d, _, name = path.rpartition("/")
        base, dot, ext = name.partition(".")
        by_ext[ext if dot else " "][d or " "].append(path)
    for ext, dirs in by_ext.items():
        tree += ext.encode() + b"\0"
        for d, paths in dirs.items():
            tree += d.encode() + b"\0"
            for path in paths:
                data = files[path]
                name = path.rpartition("/")[2].partition(".")[0]
                tree += name.encode() + b"\0"
                crc = zlib.crc32(data) & 0xFFFFFFFF
                if path.endswith("a.vmt"):  # all preload
                    tree += struct.pack("<IHHIIH", crc, len(data), 0x7FFF, 0, 0, 0xFFFF) + data
                elif path.startswith("scripts/"):  # embedded after the tree
                    tree += struct.pack("<IHHIIH", crc, 0, 0x7FFF, len(embedded), len(data), 0xFFFF)
                    embedded += data
                else:  # 4 preload bytes + rest in archive 000
                    tree += struct.pack("<IHHIIH", crc, 4, 0, len(archive), len(data) - 4, 0xFFFF) + data[:4]
                    archive += data[4:]
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"
    if version == 1:
        head = struct.pack("<III", 0x55AA1234, 1, len(tree))
    else:
        head = struct.pack("<7I", 0x55AA1234, 2, len(tree), len(embedded), 0, 0, 0)
    (tmp / "t_dir.vpk").write_bytes(head + tree + embedded)
    (tmp / "t_000.vpk").write_bytes(bytes(archive))
    return files


def test_vpk_synthetic() -> None:
    for version in (1, 2):
        with tempfile.TemporaryDirectory() as td:
            files = _build_vpk(Path(td), version)
            with VPK(Path(td) / "t_dir.vpk") as v:
                assert len(v) == len(files)
                for path, data in files.items():
                    assert v.read(path.upper(), verify=True) == data, path
                assert v.try_read("missing/file.txt") is None
                assert v.glob("materials/test/*") == ["materials/test/a.vmt", "materials/test/big.bin"]


def _dds(raw: bytes, w: int, h: int, fourcc: bytes) -> bytes:
    hdr = struct.pack("<4sIIIIIII44x", b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(raw), 0, 1)
    pf = struct.pack("<II4s5I", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    return hdr + pf + struct.pack("<5I", 0x1000, 0, 0, 0, 0) + raw


def test_dxt_matches_pillow() -> None:
    """Random DXT1/3/5 blocks decode like Pillow's BCn decoder (+-1 rounding)."""
    from PIL import Image
    rng = np.random.default_rng(1234)
    w, h = 64, 32
    for fmt, fourcc, bs in ((vtf.Fmt.DXT1, b"DXT1", 8), (vtf.Fmt.DXT3, b"DXT3", 16), (vtf.Fmt.DXT5, b"DXT5", 16)):
        raw = rng.integers(0, 256, (w // 4) * (h // 4) * bs, dtype=np.uint8).tobytes()
        mine = vtf.decode_image(raw, fmt, w, h).astype(int)
        ref = np.array(Image.open(io.BytesIO(_dds(raw, w, h, fourcc))).convert("RGBA")).astype(int)
        diff = np.abs(mine - ref)
        opaque = ref[..., 3] > 0  # transparent texels: colour is irrelevant
        assert diff[..., 3].max() <= 1, (fmt, diff[..., 3].max())
        assert diff[opaque][:, :3].max() <= 1, (fmt, diff[opaque].max())


def test_dxt1_one_bit_alpha() -> None:
    # c0 <= c1 selects 3-colour mode; index 3 = transparent black.
    block = struct.pack("<HHI", 0x0000, 0xFFFF, 0xFFFFFFFF)  # every texel index 3
    img = vtf.decode_image(block, vtf.Fmt.DXT1_ONEBITALPHA, 4, 4)
    assert (img[..., 3] == 0).all() and (img[..., :3] == 0).all()
    block = struct.pack("<HHI", 0xFFFF, 0x0000, 0x00000000)  # 4-colour mode, index 0 = white
    img = vtf.decode_image(block, vtf.Fmt.DXT1, 4, 4)
    assert (img == 255).all()


def test_dxt_speed() -> None:
    raw = np.random.default_rng(5).integers(0, 256, 256 * 256 * 16, dtype=np.uint8).tobytes()
    t = time.perf_counter()
    img = vtf.decode_image(raw, vtf.Fmt.DXT5, 1024, 1024)
    dt = time.perf_counter() - t
    assert img.shape == (1024, 1024, 4)
    assert dt < 1.0, f"1024x1024 DXT5 took {dt:.3f}s"


def _encode(rgba: np.ndarray, fmt: vtf.Fmt) -> tuple[bytes, np.ndarray]:
    """Encode an RGBA image into ``fmt``; also return the expected decoded RGBA."""
    r, g, b, a = (rgba[..., i].astype(np.uint16) for i in range(4))
    exp = rgba.copy()
    F = vtf.Fmt
    if fmt == F.RGBA8888:
        raw = np.stack([r, g, b, a], -1)
    elif fmt == F.ABGR8888:
        raw = np.stack([a, b, g, r], -1)
    elif fmt == F.BGRA8888:
        raw = np.stack([b, g, r, a], -1)
    elif fmt == F.BGRX8888:
        raw = np.stack([b, g, r, np.zeros_like(a)], -1)
        exp[..., 3] = 255
    elif fmt == F.RGB888:
        raw = np.stack([r, g, b], -1)
        exp[..., 3] = 255
    elif fmt == F.BGR888:
        raw = np.stack([b, g, r], -1)
        exp[..., 3] = 255
    elif fmt == F.I8:
        raw = r[..., None]
        exp[..., 0] = exp[..., 1] = exp[..., 2] = rgba[..., 0]
        exp[..., 3] = 255
    elif fmt == F.IA88:
        raw = np.stack([r, a], -1)
        exp[..., 0] = exp[..., 1] = exp[..., 2] = rgba[..., 0]
    elif fmt == F.A8:
        raw = a[..., None]
        exp[..., :3] = 0
    elif fmt == F.UV88:
        raw = np.stack([r, g], -1)
        exp[..., 2] = 0
        exp[..., 3] = 255
    elif fmt == F.BGR565:
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        exp = _expand(r >> 3, 5), _expand(g >> 2, 6), _expand(b >> 3, 5)
        exp = np.stack(list(exp) + [np.full_like(r, 255)], -1).astype(np.uint8)
        return v.astype("<u2").tobytes(), exp
    elif fmt == F.BGRA4444:
        v = ((a >> 4) << 12) | ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
        exp = np.stack([(r >> 4) * 17, (g >> 4) * 17, (b >> 4) * 17, (a >> 4) * 17], -1).astype(np.uint8)
        return v.astype("<u2").tobytes(), exp
    elif fmt == F.RGBA16161616F:
        lin = (rgba.astype(np.float32) / 255.0) ** 2.2
        lin[..., 3] = rgba[..., 3] / 255.0
        exp = rgba.copy()
        return lin.astype("<f2").tobytes(), exp
    else:
        raise AssertionError(fmt)
    return raw.astype(np.uint8).tobytes(), exp


def _expand(v: np.ndarray, bits: int) -> np.ndarray:
    return (v << (8 - bits)) | (v >> (2 * bits - 8))


def _vtf_file(raw_mips: list[bytes], fmt: int, w: int, h: int, minor: int, lowres: bytes = b"") -> bytes:
    """Minimal VTF: mips given largest first; stored smallest first."""
    body = b"".join(reversed(raw_mips))
    header_size = 80 if minor >= 2 else 64
    nres = 0
    if minor >= 3:
        nres = 2 if lowres else 1
        header_size = 80 + 8 * nres
    hdr = bytearray(header_size)
    hdr[0:4] = b"VTF\0"
    struct.pack_into("<3I", hdr, 4, 7, minor, header_size)
    struct.pack_into("<HHIHH", hdr, 16, w, h, 0, 1, 0)
    struct.pack_into("<fiBiBB", hdr, 48, 1.0, fmt, len(raw_mips), vtf.Fmt.DXT1 if lowres else -1,
                     4 if lowres else 0, 4 if lowres else 0)
    if minor >= 2:
        struct.pack_into("<H", hdr, 63, 1)
    if minor >= 3:
        struct.pack_into("<I", hdr, 68, nres)
        off = header_size
        i = 0
        if lowres:
            struct.pack_into("<3sBI", hdr, 80, vtf.RES_LOWRES, 0, off)
            off += len(lowres)
            i = 1
        struct.pack_into("<3sBI", hdr, 80 + 8 * i, vtf.RES_HIGHRES, 0, off)
    return bytes(hdr) + lowres + body


def test_vtf_uncompressed_formats() -> None:
    rng = np.random.default_rng(7)
    w, h = 8, 4
    img = rng.integers(0, 256, (h, w, 4), dtype=np.uint8)
    F = vtf.Fmt
    for fmt in (F.RGBA8888, F.ABGR8888, F.BGRA8888, F.BGRX8888, F.RGB888, F.BGR888, F.I8, F.IA88, F.A8, F.UV88,
                F.BGR565, F.BGRA4444, F.RGBA16161616F):
        raw, exp = _encode(img, fmt)
        small, _ = _encode(img[::2, ::2], fmt)  # a second mip level (content irrelevant)
        for minor in (1, 2, 5):
            lowres = b"\0" * 8 if minor != 2 else b""
            t = vtf.VTF(_vtf_file([raw, small], fmt, w, h, minor, lowres), f"synthetic-{fmt.name}-7.{minor}")
            out = t.decode()
            tol = 1 if fmt == F.RGBA16161616F else 0
            assert out.shape == (h, w, 4)
            assert np.abs(out.astype(int) - exp.astype(int)).max() <= tol, (fmt.name, minor)


def test_vtf_padded_small_mips() -> None:
    """Mip 0 is found from the end of the data when smaller mips are padded."""
    rng = np.random.default_rng(3)
    img = rng.integers(0, 256, (4, 8, 4), dtype=np.uint8)
    raw, exp = _encode(img, vtf.Fmt.RGBA8888)
    small, _ = _encode(img[::2, ::2], vtf.Fmt.RGBA8888)
    data = _vtf_file([raw, small + b"\0" * 32], vtf.Fmt.RGBA8888, 8, 4, 5)
    t = vtf.VTF(data, "padded")
    assert t.layout_mismatch
    assert (t.decode() == exp).all()


def test_save_tga_and_png() -> None:
    img = np.zeros((3, 5, 4), np.uint8)
    img[0, 0] = (255, 0, 0, 255)  # top-left red
    img[..., 3] = 255
    d = out_dir()
    p = d / "synthetic.tga"
    vtf.save_tga(img, p)
    from PIL import Image
    back = np.array(Image.open(p).convert("RGBA"))
    assert (back == img).all()
    vtf.to_pil(img).save(d / "synthetic.png")


KV_SAMPLE = r'''
// leading comment
"LightmappedGeneric"
{
    $basetexture "Brick\Wall01"      // trailing comment, backslash path kept
    "$SurfaceProp" brick
    "$envmap" "env_cubemap" [!$X360]
    "$envmap" "none" [$X360]
    "srgb?$basetexture" "brick/wall01_srgb"
    "GPU<2?$detail" "low/detail"
    "GPU>=2?$detailscale" "4"
    "!gameconsole?$phong" "1"
    "%compileClip" 1
    "Proxies" { "AnimatedTexture" { "animatedtexturevar" "$basetexture" } }
    "LightmappedGeneric_DX9" { "$bumpmap" "brick/wall01_normal" }
    "water_dx60" { "$bumpmap" "nope" }
    ">=dx90" { "$nocull" 1 }
}
'''


def test_keyvalues_quirks() -> None:
    kv = vmt.parse_keyvalues(KV_SAMPLE)
    m = kv["lightmappedgeneric"]
    assert m["$basetexture"] == "Brick\\Wall01"
    assert m["$surfaceprop"] == "brick"
    assert m["$envmap"] == "env_cubemap"
    assert m["proxies"]["animatedtexture"]["animatedtexturevar"] == "$basetexture"
    assert vmt.eval_conditional("$X360 || $WIN32") and not vmt.eval_conditional("!$WIN32 && $X360")
    r = vmt.resolve_conditions(m, "lightmappedgeneric")
    assert r["$basetexture"] == "Brick\\Wall01"       # srgb? is false on PC
    assert "$detail" not in r and r["$detailscale"] == "4"
    assert r["$phong"] == "1" and r["$bumpmap"] == "brick/wall01_normal" and r["$nocull"] == "1"
    pairs = vmt.parse_kv_pairs('a { b 1 b 2 } a { c 3 }')
    assert [k for k, _ in pairs] == ["a", "a"] and len(pairs[0][1]) == 2


class _DictSource:
    def __init__(self, files: dict[str, str]):
        self.files = {k.lower(): v.encode() for k, v in files.items()}

    def try_read(self, path: str) -> Optional[bytes]:
        return self.files.get(path.lower().replace("\\", "/"))


def test_material_patch() -> None:
    src = _DictSource({
        "materials/base/wall.vmt": KV_SAMPLE,
        "materials/maps/m/base/wall_1_2_3.vmt": '''patch { include "materials/BASE/WALL.vmt"
            insert { "$basetexture2" "base/wall2" "$translucent" 1 }
            replace { "$envmap" "maps/m/c1_2_3" "$notthere" "x" } }''',
        "materials/tools/toolsclip.vmt": '"LightmappedGeneric" { "$basetexture" "Tools/toolsclip" '
                                         '"%compileclip" 1 "%keywords" "tools" }',
    })
    mi = vmt.material_info(src, "MAPS/M/BASE/WALL_1_2_3")
    assert mi.found and mi.shader == "lightmappedgeneric"
    assert mi.includes == ["materials/base/wall.vmt"]
    assert mi.basetexture == "brick/wall01" and mi.basetexture2 == "base/wall2"
    assert mi.params["$envmap"] == "maps/m/c1_2_3" and "$notthere" not in mi.params
    assert mi.translucent and mi.nocull and mi.surfaceprop == "brick"
    assert "clip" in mi.tool_flags
    clip = vmt.material_info(src, "tools/toolsclip")
    assert clip.tool_flags == {"clip"} and clip.nodraw
    assert not vmt.material_info(src, "nope/missing").found


# ---------------------------------------------------------------------------
# Game-data tests


def test_vpk_csgo() -> None:
    v = csgo_vpk()
    assert v.version in (1, 2) and len(v) > 1000
    data = v.read("materials/tools/toolsnodraw.vmt", verify=True)
    assert b"compilenodraw" in data.lower()
    flags = vmt.tool_material_flags(v)
    assert flags["tools/toolsnodraw"].get("%compilenodraw") == "1"


def hull_is_closed(windings: list[geom.Winding], weld: float = 0.05) -> bool:
    """True when the non-degenerate faces form a closed 2-manifold (every edge used twice)."""
    faces = [w for w in windings if len(w) >= 3 and geom.winding_area(w) > 1e-4]
    if len(faces) < 4:
        return False
    verts: list[geom.Vec3] = []

    def vid(p: geom.Vec3) -> int:
        for i, q in enumerate(verts):
            if abs(p[0] - q[0]) < weld and abs(p[1] - q[1]) < weld and abs(p[2] - q[2]) < weld:
                return i
        verts.append(p)
        return len(verts) - 1

    edges: collections.Counter = collections.Counter()
    for w in faces:
        ids = [vid(p) for p in w]
        ids = [x for i, x in enumerate(ids) if x != ids[i - 1]]  # drop welded duplicates (cyclic)
        if len(ids) < 3:
            continue
        for i in range(len(ids)):
            a, b = ids[i], ids[(i + 1) % len(ids)]
            edges[(min(a, b), max(a, b))] += 1
    return bool(edges) and all(n == 2 for n in edges.values())


def _seam_ratio(grids: list[np.ndarray]) -> float:
    """Fraction of displacement boundary vertices that coincide with another displacement's."""
    owners: dict[tuple, set[int]] = collections.defaultdict(set)
    edges = []
    for i, P in enumerate(grids):
        e = np.round(np.concatenate([P[0], P[-1], P[:, 0], P[:, -1]]), 1)
        edges.append(e)
        for p in map(tuple, e):
            owners[p].add(i)
    tot = sum(len(e) for e in edges)
    shared = sum(1 for e in edges for p in map(tuple, e) if len(owners[p]) > 1)
    return shared / tot if tot else 0.0


def _mb(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


def map_report(name: str, verbose: bool = True) -> dict[str, Any]:
    path = GAME_DIR / "maps" / f"{name}.bsp"
    if not path.is_file():
        skip(f"{path} not found")
    v = csgo_vpk()
    say = print if verbose else (lambda *a, **k: None)
    times: dict[str, float] = {}
    rep: dict[str, Any] = {"map": name}

    def timed(label: str):
        class _T:
            def __enter__(self_):
                self_.t = time.perf_counter()

            def __exit__(self_, *exc):
                times[label] = time.perf_counter() - self_.t
        return _T()

    with timed("open"):
        b = SourceBSP(path)
    with timed("entities"):
        ents = b.entities
    with timed("brushes"):
        brushes = list(b.brushes())
    with timed("displacements"):
        disps = list(b.displacements())
    with timed("static_props"):
        sp = b.static_props()
    with timed("pakfile"):
        pak = b.pakfile()
        fs = SearchPath(ZipSource(pak), v)
    with timed("materials"):
        infos = {m: vmt.material_info(fs, m) for m in b.materials}

    world = [br for br in brushes if br.model == 0]
    world_tree = [br for br in world if br.in_tree]
    ent_brushes = [br for br in brushes if br.model > 0]
    consumed = [br for br in brushes if br.model < 0]
    nsides = sum(len(br.sides) for br in brushes)
    nbevel = sum(1 for br in brushes for s in br.sides if s.is_bevel)

    # Raw rebuild: every non-bevel side through geom.brush_windings.
    with timed("hulls"):
        closed = 0
        empty = 0
        for br in world:
            ws = br.windings()
            if hull_is_closed(ws):
                closed += 1
            elif not any(len(w) >= 3 for w in ws):
                empty += 1

    # Cleaned rebuild: also drop unflagged axial bevels / redundant planes.
    with timed("hulls_pruned"):
        closed_pruned = 0
        pruned_sides = 0
        geometry: dict[int, list[tuple[bspmod.BrushSide, geom.Winding]]] = {}
        for br in world:
            g = br.geometry()
            geometry[br.index] = g
            pruned_sides += len(br.real_sides()) - len(g)
            if hull_is_closed([w for _, w in g]):
                closed_pruned += 1

    with timed("skybox"):
        sky_area = b.skybox_area()
        sky_brushes = 0
        if sky_area is not None:
            for br in world_tree:
                g = geometry[br.index]
                probe = bspmod.Brush(br.index, br.contents, br.model, [sd for sd, _ in g])
                if b.brush_face_areas(probe, [w for _, w in g]) == {sky_area}:
                    sky_brushes += 1
        sky_props = sum(1 for p in sp.props if sky_area is not None and b.prop_areas(p) == {sky_area})

    with timed("mdl"):
        mdl_ok = 0
        for n in sp.names:
            try:
                mdl.load_mdl(fs, n)
                mdl_ok += 1
            except (KeyError, mdl.MDLError):
                pass

    # Seam check validates the displacement corner ordering: neighbouring
    # displacements must share boundary vertices.
    # The transposed grid (rows along p0->p3) is the classic mistake; it must share fewer.
    with timed("disp_seams"):
        seam_ratio = _seam_ratio([d.positions for d in disps])
        seam_ratio_transposed = _seam_ratio([d.flat + d.offsets.transpose(1, 0, 2) for d in disps])

    # Texture decode: the most used visible world material.
    with timed("texture"):
        face_use = collections.Counter(int(t) for t in b.texinfo["texdata"][b.faces["texinfo"]])
        tex_out = None
        for td, _ in face_use.most_common():
            mi = infos.get(b.texdata_names[td].lower())
            if not mi or not mi.found or mi.is_tool or not mi.basetexture:
                continue
            data = fs.try_read(vmt.texture_path(mi.basetexture))
            if data is None:
                continue
            t0 = time.perf_counter()
            tex = vtf.VTF(data, mi.basetexture)
            rgba = tex.decode()
            dt = time.perf_counter() - t0
            png = out_dir() / f"{name}_{mi.basetexture.replace('/', '_')}.png"
            vtf.to_pil(rgba).save(png)
            vtf.save_tga(rgba, png.with_suffix(".tga"))
            tex_out = (mi.name, repr(tex), str(png), dt)
            break

    lo, hi = b.world_bounds()
    classes = collections.Counter(e.classname for e in ents)
    tool_kinds = collections.Counter(k for br in brushes for k in br.tool_kinds)
    found = sum(1 for mi in infos.values() if mi.found)
    shaders = collections.Counter(mi.shader for mi in infos.values() if mi.found)

    rep.update(entities=len(ents), brush_entities=sum(1 for e in ents if e.model_index is not None),
               models=len(b.models), brushes=len(brushes), world_brushes=len(world), world_in_tree=len(world_tree),
               entity_brushes=len(ent_brushes), consumed_brushes=len(consumed), sides=nsides, bevel_sides=nbevel,
               displacements=len(disps), static_props=len(sp.props), sprp_version=sp.version,
               prop_models=len(sp.names), mdl_ok=mdl_ok, materials=len(b.materials), materials_found=found,
               bounds=(lo, hi), closed_hulls=closed, empty_hulls=empty, closed_hulls_pruned=closed_pruned,
               pruned_sides=pruned_sides, sky_area=sky_area,
               sky_brushes=sky_brushes, sky_props=sky_props, disp_seam_ratio=seam_ratio,
               disp_seam_ratio_transposed=seam_ratio_transposed,
               missing_materials=sorted(m for m, mi in infos.items() if not mi.found),
               pak_files=len(pak.namelist()), texture=tex_out, times=times)

    say(f"== {name}  ({_mb(path.stat().st_size)}, VBSP v{b.version} rev {b.map_revision})")
    say(f"entities       {len(ents)}  ({rep['brush_entities']} brush entities, {len(classes)} classes)")
    say(f"  top classes  {', '.join(f'{c}:{n}' for c, n in classes.most_common(8))}")
    say(f"models         {len(b.models)}")
    say(f"brushes        {len(brushes)}: world {len(world)} ({len(world_tree)} in tree, "
        f"{len(world) - len(world_tree)} CSG-culled), entity {len(ent_brushes)}, consumed-entity {len(consumed)}")
    say(f"sides          {nsides} ({nbevel} bevel, skipped for geometry)")
    say(f"tool kinds     {dict(tool_kinds.most_common())}")
    say(f"hulls          {closed}/{len(world)} world brushes rebuild to closed hulls skipping bevel sides "
        f"({empty} empty); {closed_pruned}/{len(world)} after pruning {pruned_sides} redundant/unflagged-bevel sides")
    say(f"displacements  {len(disps)} (powers {dict(collections.Counter(d.power for d in disps))}); "
        f"{seam_ratio:.0%} boundary verts shared with a neighbour ({seam_ratio_transposed:.0%} if transposed)")
    say(f"static props   {len(sp.props)} (sprp v{sp.version}, {sp.record_size} B records, {len(sp.names)} models, "
        f"{mdl_ok} MDL headers read)")
    say(f"materials      {len(b.materials)} unique, {found} resolved; shaders {dict(shaders.most_common(6))}")
    if rep["missing_materials"]:
        say(f"  missing      {rep['missing_materials'][:5]}")
    say(f"bounds         {tuple(round(x) for x in lo)} .. {tuple(round(x) for x in hi)}")
    say(f"3D skybox      area {sky_area}: {sky_brushes} brushes, {sky_props} props "
        f"(sky_camera scale {b.sky_camera.get('scale') if b.sky_camera else '-'})")
    say(f"pakfile        {len(pak.namelist())} files")
    if tex_out:
        say(f"texture        {tex_out[0]} -> {tex_out[1]}\n               decoded in {tex_out[3]*1000:.1f} ms "
            f"-> {tex_out[2]}")
    say("timings        " + ", ".join(f"{k} {v:.2f}s" for k, v in times.items()))
    say(f"total          {sum(times.values()):.2f}s\n")
    return rep


def _check(rep: dict[str, Any]) -> None:
    assert rep["entities"] > 10 and rep["brushes"] > 100 and rep["world_brushes"] > 100
    assert rep["materials_found"] >= 0.98 * rep["materials"], rep["missing_materials"]
    assert rep["closed_hulls"] >= 0.98 * (rep["world_brushes"] - rep["empty_hulls"])
    assert rep["closed_hulls_pruned"] >= 0.999 * rep["world_brushes"]
    assert rep["static_props"] > 0 and rep["mdl_ok"] == rep["prop_models"]
    if rep["displacements"] >= 20:
        assert rep["disp_seam_ratio"] > rep["disp_seam_ratio_transposed"], "displacement corner ordering"
    assert rep["texture"] is not None


def test_de_dust2() -> None:
    _check(map_report("de_dust2", verbose=False))


def test_cs_office() -> None:
    _check(map_report("cs_office", verbose=False))


def test_de_inferno() -> None:
    _check(map_report("de_inferno", verbose=False))


# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    synthetic = [test_lzma_roundtrip, test_lzma_lump_in_bsp, test_vpk_synthetic, test_dxt_matches_pillow,
                 test_dxt1_one_bit_alpha, test_dxt_speed, test_vtf_uncompressed_formats, test_vtf_padded_small_mips,
                 test_save_tga_and_png,
                 test_keyvalues_quirks, test_material_patch, test_vpk_csgo]
    failed = 0
    for fn in synthetic:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except SkipTest as e:
            print(f"SKIP {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print()
    for name in argv or DEFAULT_MAPS:
        try:
            _check(map_report(name))
        except SkipTest as e:
            print(f"SKIP {name}: {e}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print("FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
