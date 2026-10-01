"""Write (and read back) MOHAA static-model files: ``.skd`` mesh, ``.skc`` pose, ``.tik`` definition.

The layout reproduces what the retail Allied Assault paks ship for every one of
their 303 ``models/static/*.skd`` files (all ``SKMD`` version 5, 148-byte header,
bones right after the header, then the surfaces; every surface ``SKL `` with its
arrays in the order triangles, vertices, collapse map, collapse index) and 303
``.skc`` files (all ``SKAN`` version 13, flags 0, ``frameTime`` 1/30, one frame).
It is also the layout the original EA Q3map 1.34 / MOHlight 1.48 were proven to
accept for converted models: a single POSROT bone ``ORIGIN`` parented to
``worldbone``, zero-filled collapse arrays and ``lodIndex`` (no progressive LOD,
so ``GetLODFile`` never builds a LOD table and the whole mesh is always drawn).

SKD (little endian)::

    header (148 B)
      0 "SKMD"   4 version 5   8 name[64]
     72 numSurfaces   76 numBones (1)   80 ofsBones (148)   84 ofsSurfaces   88 ofsEnd
     92 lodIndex[10] (0)   132 numBoxes (0)   136 ofsBoxes (= ofsEnd)
    140 numMorphTargets (0)   144 ofsMorphTargets (= ofsEnd)
    bone (boneFileData_t, 84 B + data)
      0 name[32] "ORIGIN"   32 parent[32] "worldbone"   64 boneType 1 (POSROT)
     68 ofsBaseData 84   72 ofsChannelNames 96   76 ofsBoneNames   80 ofsEnd
     84 float[3] 1 1 1   96 "ORIGIN rot\\0ORIGIN pos\\0"   (record padded to 4 bytes)
    surface (100 B header, offsets relative to the surface)
      0 "SKL "   4 name[64]   68 numTriangles   72 numVerts   76 staticSurfProcessed 0
     80 ofsTriangles (100)   84 ofsVerts   88 ofsCollapse   92 ofsEnd   96 ofsCollapseIndex
      triangles int32[3 * numTriangles]  (clockwise w.r.t. the vertex normals, as retail)
      vertices  48 B each: normal[3], texCoords[2] (s, t; t = 0 at the image top),
                numWeights 1, numMorphs 0, then {boneIndex 0, boneWeight 1.0, offset[3]}
      collapse int32[numVerts], collapseIndex int32[numVerts]: zero (no LOD) unless the
      surface carries ``mohkit.lod`` data; then a ``.lod`` file goes beside the ``.skd``

The engine limits each surface to 1000 vertices / 2000 triangles
(``TIKI_MAX_VERTEXES`` / ``TIKI_MAX_TRIANGLES``); :data:`MAX_SURFACE_VERTS` and
:data:`MAX_SURFACE_TRIS` stay one below.

SKC::

      0 "SKAN"   4 version 13   8 flags 0   12 nBytesUsed (file size)   16 frameTime 1/30
     20 totalDelta[3] 0   32 totalAngleDelta 0   36 numChannels 2   40 ofsChannelNames
     44 numFrames 1
     48 frame: bounds[2][3], radius, delta[3] 0, angleDelta 0, iOfsChannels (96)
     96 channel data float[4] per channel: "ORIGIN pos" (0 0 0 0), "ORIGIN rot" (0 0 0 1)
    128 channel names char[32] each

``bounds`` are the model-space vertex bounds and ``radius`` is the length of the
largest-magnitude corner, as in retail files (``indycrate.skc``: 126.56 for
bounds (-50.4 -70.8 0) (49.3 72.4 90.7)). The engine builds static-model bounds
from this frame; a TIKI without an ``idle`` animation logs "no 'idle' animation
found, model bounds not set".

TIKI::

    TIKI
    setup
    {
        scale 1
        path models/csgo/props/de_dust
        skelmodel dust_rusty_barrel.skd
        surface <surface name> shader <shader name>     (<= 24 lines, see below)
    }
    init { server { classname object } }
    animations { idle dust_rusty_barrel.skc }

Name limits: TIKI surface names are copied into ``char[32]`` (use <= 28), the
setup parser has a fixed array of 24 surfaces (more corrupts memory in the
original tools), shader names and image paths are ``MAX_QPATH`` (<= 63).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

SKD_IDENT = b"SKMD"
SKD_VERSION = 5
SKD_SURFACE_IDENT = b"SKL "
SKC_IDENT = b"SKAN"
SKC_VERSION = 13
BONE_NAME = "ORIGIN"
MAX_SURFACE_VERTS = 999
MAX_SURFACE_TRIS = 1999
MAX_TIKI_SURFACES = 24
MAX_SURFACE_NAME = 28
MAX_QPATH = 63
FRAME_TIME = 1.0 / 30.0

_SKD_VERTEX = np.dtype([("normal", "<f4", 3), ("st", "<f4", 2), ("nweights", "<i4"), ("nmorphs", "<i4"),
                        ("bone", "<i4"), ("weight", "<f4"), ("offset", "<f4", 3)])
assert _SKD_VERTEX.itemsize == 48


def _fixed(s: str, n: int) -> bytes:
    b = s.encode("latin-1")
    if len(b) >= n:
        raise ValueError(f"name {s!r} does not fit in char[{n}]")
    return b + b"\0" * (n - len(b))


@dataclass
class SkdSurface:
    name: str
    positions: np.ndarray   # (n, 3) model space, final units
    normals: np.ndarray     # (n, 3)
    uvs: np.ndarray         # (n, 2) s, t
    triangles: np.ndarray   # (m, 3) counter-clockwise (right-handed w.r.t. the normals)
    # progressive LOD (``mohkit.lod``): per vertex, the lower-index vertex it collapses into and
    # the cutoff below which it is drawn; None writes zeros (no LOD, always fully drawn)
    collapse: Optional[np.ndarray] = None
    collapse_index: Optional[np.ndarray] = None

    def check(self) -> None:
        if not self.name or len(self.name) > MAX_SURFACE_NAME:
            raise ValueError(f"surface name {self.name!r} must be 1..{MAX_SURFACE_NAME} characters")
        n, m = len(self.positions), len(self.triangles)
        if not 0 < n <= MAX_SURFACE_VERTS or not 0 < m <= MAX_SURFACE_TRIS:
            raise ValueError(f"surface {self.name}: {n} vertices / {m} triangles exceed "
                             f"{MAX_SURFACE_VERTS} / {MAX_SURFACE_TRIS}")
        if self.triangles.min() < 0 or self.triangles.max() >= n:
            raise ValueError(f"surface {self.name}: triangle index out of range")


def _bone_record(name: str = BONE_NAME) -> bytes:
    chans = f"{name} rot\0{name} pos\0".encode("latin-1")
    ofs_chan = 84 + 12
    ofs_names = ofs_chan + len(chans)
    end = (ofs_names + 3) & ~3
    head = _fixed(name, 32) + _fixed("worldbone", 32) + struct.pack("<5i", 1, 84, ofs_chan, ofs_names, end)
    rec = head + struct.pack("<3f", 1.0, 1.0, 1.0) + chans
    return rec + b"\0" * (end - len(rec))


def _surface_record(s: SkdSurface) -> bytes:
    s.check()
    n, m = len(s.positions), len(s.triangles)
    tris = np.ascontiguousarray(np.asarray(s.triangles, np.int32)[:, [0, 2, 1]]).astype("<i4")  # retail: clockwise
    verts = np.zeros(n, _SKD_VERTEX)
    verts["normal"] = s.normals
    verts["st"] = s.uvs
    verts["nweights"] = 1
    verts["bone"] = 0
    verts["weight"] = 1.0
    verts["offset"] = s.positions
    ofs_tri = 100
    ofs_vert = ofs_tri + 12 * m
    ofs_col = ofs_vert + 48 * n
    ofs_colidx = ofs_col + 4 * n
    end = ofs_colidx + 4 * n
    head = SKD_SURFACE_IDENT + _fixed(s.name, 64) + struct.pack("<8i", m, n, 0, ofs_tri, ofs_vert, ofs_col, end,
                                                                ofs_colidx)
    if s.collapse is None or s.collapse_index is None:
        return head + tris.tobytes() + verts.tobytes() + bytes(8 * n)
    col = np.asarray(s.collapse, "<i4").reshape(n)
    cidx = np.asarray(s.collapse_index, "<i4").reshape(n)
    return head + tris.tobytes() + verts.tobytes() + col.tobytes() + cidx.tobytes()


def build_skd(name: str, surfaces: Sequence[SkdSurface], bone: str = BONE_NAME) -> bytes:
    """SKD version 5 bytes; ``name`` goes in the header (retail: the file name, e.g. ``indycrate.skd``)."""
    if not surfaces:
        raise ValueError("an SKD needs at least one surface")
    names = [s.name.lower() for s in surfaces]
    if len(set(names)) != len(names):
        raise ValueError("surface names must be unique")
    bone_rec = _bone_record(bone)
    surf_recs = [_surface_record(s) for s in surfaces]
    ofs_bones = 148
    ofs_surf = ofs_bones + len(bone_rec)
    end = ofs_surf + sum(len(r) for r in surf_recs)
    head = (SKD_IDENT + struct.pack("<i", SKD_VERSION) + _fixed(name, 64)
            + struct.pack("<5i", len(surfaces), 1, ofs_bones, ofs_surf, end) + bytes(40)
            + struct.pack("<4i", 0, end, 0, end))
    assert len(head) == 148
    return head + bone_rec + b"".join(surf_recs)


def bounds_radius(mins: Sequence[float], maxs: Sequence[float]) -> float:
    corner = [max(abs(a), abs(b)) for a, b in zip(mins, maxs)]
    return float(np.sqrt(sum(c * c for c in corner)))


def build_skc(mins: Sequence[float], maxs: Sequence[float], bone: str = BONE_NAME) -> bytes:
    """One-frame identity pose (SKAN version 13) with the given model bounds."""
    nch = 2
    ofs_names = 96 + 16 * nch
    size = ofs_names + 32 * nch
    head = (SKC_IDENT + struct.pack("<iii", SKC_VERSION, 0, size) + struct.pack("<f", FRAME_TIME)
            + struct.pack("<3ff", 0, 0, 0, 0) + struct.pack("<3i", nch, ofs_names, 1))
    frame = struct.pack("<3f3ff3ffi", *mins, *maxs, bounds_radius(mins, maxs), 0, 0, 0, 0, 96)
    chans = struct.pack("<4f", 0, 0, 0, 0) + struct.pack("<4f", 0, 0, 0, 1)
    names = _fixed(f"{bone} pos", 32) + _fixed(f"{bone} rot", 32)
    out = head + frame + chans + names
    assert len(out) == size
    return out


def build_tiki(path: str, skd: str, skc: str, bindings: Sequence[tuple[str, str]], scale: float = 1.0,
               quaked: Optional[str] = None, bounds: Optional[tuple[Sequence[float], Sequence[float]]] = None,
               comment: str = "") -> str:
    """TIKI text. ``path`` is the directory of ``skd``/``skc`` (e.g. ``models/csgo/props``);
    ``bindings`` are ``(surface, shader)`` pairs."""
    if len(bindings) > MAX_TIKI_SURFACES:
        raise ValueError(f"{len(bindings)} surfaces exceed the TIKI setup limit of {MAX_TIKI_SURFACES}")
    lines = ["TIKI"]
    if comment:
        lines += [f"// {c}" for c in comment.splitlines()]
    lines += ["setup", "{", f"\tscale {scale:g}", f"\tpath {path}", f"\tskelmodel {skd}"]
    for surf, shader in bindings:
        if len(surf) > MAX_SURFACE_NAME or len(shader) > MAX_QPATH:
            raise ValueError(f"surface {surf!r} / shader {shader!r} too long")
        lines.append(f"\tsurface {surf} shader {shader}")
    lines += ["}", "", "init", "{", "\tserver", "\t{", "\t\tclassname object", "\t}", "}", "",
              "animations", "{", f"\tidle     {skc}", "}", ""]
    if quaked:
        b = bounds or ((-16, -16, 0), (16, 16, 32))
        mn = " ".join(str(int(np.floor(v))) for v in b[0])
        mx = " ".join(str(int(np.ceil(v))) for v in b[1])
        lines += [f"/*QUAKED {quaked} (0.5 0.0 0.5) ({mn}) ({mx})", "*/", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Readers (tests, inspection of retail files)


@dataclass
class SkdInfo:
    version: int
    name: str
    bones: list[tuple[str, str, int]]           # (name, parent, type)
    surfaces: list[SkdSurface]                   # triangles converted back to counter-clockwise
    lod_index: tuple[int, ...]
    collapse: list[tuple[np.ndarray, np.ndarray]]


def read_skd(data: bytes) -> SkdInfo:
    if data[:4] != SKD_IDENT:
        raise ValueError("not an SKD")
    version = struct.unpack_from("<i", data, 4)[0]
    name = data[8:72].split(b"\0", 1)[0].decode("latin-1")
    ns, nb, ob, osf, _end = struct.unpack_from("<5i", data, 72)
    lod = struct.unpack_from("<10i", data, 92)
    bones = []
    p = ob
    for _ in range(nb):
        bname, parent, btype, _b, _c, _n, bend = struct.unpack_from("<32s32s5i", data, p)
        bones.append((bname.split(b"\0")[0].decode("latin-1"), parent.split(b"\0")[0].decode("latin-1"), btype))
        p += bend
    surfaces, collapse = [], []
    o = osf
    for _ in range(ns):
        _sid, sname, ntri, nvert, _ssp, otri, overt, ocol, oend, ocolidx = struct.unpack_from("<4s64s8i", data, o)
        tris = np.frombuffer(data, "<i4", 3 * ntri, o + otri).reshape(-1, 3)[:, [0, 2, 1]]
        pos, nrm, st = [], [], []
        q = o + overt
        for _v in range(nvert):
            nx, ny, nz, s, t, nw, nm = struct.unpack_from("<5f2i", data, q)
            q += 28 + 16 * nm
            _bi, _w, x, y, z = struct.unpack_from("<if3f", data, q)
            q += 20 * nw
            pos.append((x, y, z))
            nrm.append((nx, ny, nz))
            st.append((s, t))
        surfaces.append(SkdSurface(sname.split(b"\0")[0].decode("latin-1"), np.array(pos, np.float32),
                                   np.array(nrm, np.float32), np.array(st, np.float32), np.array(tris)))
        collapse.append((np.frombuffer(data, "<i4", nvert, o + ocol), np.frombuffer(data, "<i4", nvert, o + ocolidx)))
        o += oend
    return SkdInfo(version, name, bones, surfaces, lod, collapse)


@dataclass
class SkcInfo:
    version: int
    flags: int
    size: int
    frame_time: float
    num_frames: int
    channels: list[str]
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    radius: float
    data: list[tuple[float, float, float, float]]


def read_skc(data: bytes) -> SkcInfo:
    if data[:4] != SKC_IDENT:
        raise ValueError("not an SKC")
    ver, flags, size, ftime = struct.unpack_from("<iiif", data, 4)
    nch, ofsn, nfr = struct.unpack_from("<3i", data, 36)
    b = struct.unpack_from("<7f", data, 48)
    chans = [data[ofsn + 32 * i : ofsn + 32 * (i + 1)].split(b"\0")[0].decode("latin-1") for i in range(nch)]
    base = 48 + 48 * nfr
    vals = [struct.unpack_from("<4f", data, base + 16 * i) for i in range(nch)]
    return SkcInfo(ver, flags, size, ftime, nfr, chans, (b[0:3], b[3:6]), b[6], vals)
