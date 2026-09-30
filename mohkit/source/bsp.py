"""Read Source engine BSP files (version 21 as shipped with CS:GO).

Only reads; the converter decides what to do with the data.

File header (1036 bytes)::

    char   ident[4]        "VBSP"
    int32  version         21 (CS:GO, L4D2, Portal 2); 19/20 also parse
    lump_t lumps[64]       16 bytes each, see below
    int32  map_revision

    lump_t (CS:GO order):  int32 fileofs, int32 filelen, int32 version, int32 uncompressed_size
    (L4D2 swaps to version, fileofs, filelen, fourCC - detected heuristically.)

LZMA lumps: when ``uncompressed_size != 0`` the lump starts with Valve's
17-byte header ``'LZMA' uint32 actual_size, uint32 lzma_size, uint8 props[5]``
followed by a raw LZMA1 stream without end marker. ``props[0]`` encodes
``lc + 9 * (lp + 5 * pb)`` and ``props[1:5]`` the dictionary size; it is decoded
with :mod:`lzma` using ``FORMAT_RAW`` and an explicit ``FILTER_LZMA1`` filter.
Game lumps flagged compressed (``flags & 1``) use the same header per lump.
(No stock CS:GO map on disk uses compression, but workshop/other builds do.)

Lumps used here (index: record layout, little endian)::

     0 ENTITIES      text: { "key" "value" ... } blocks; keys may repeat (outputs).
                     CS:GO outputs separate fields with ESC (0x1B), older maps with ','.
     1 PLANES        20 B: float normal[3], float dist, int32 type
     2 TEXDATA       32 B: float reflectivity[3], int32 name_string_id, int32 w, h, view_w, view_h
     3 VERTEXES      12 B: float xyz
     5 NODES         32 B: int32 planenum, int32 children[2] (<0: leaf -1-child),
                           int16 mins[3], maxs[3], uint16 firstface, numfaces, int16 area, pad
     6 TEXINFO       72 B: float texture_vecs[2][4], lightmap_vecs[2][4], int32 flags, int32 texdata
                     texel (s, t) = dot(vec.xyz, p) + vec.w  (texel units; divide by texture size)
     7 FACES         56 B: uint16 planenum, uint8 side, on_node, int32 firstedge, int16 numedges,
                           int16 texinfo, dispinfo, fog_volume, uint8 styles[4], int32 lightofs,
                           float area, int32 lm_mins[2], lm_size[2], int32 orig_face,
                           uint16 num_prims, first_prim, uint32 smoothing_groups
    10 LEAFS         v1 32 B: int32 contents, int16 cluster, int16 area:9|flags:7, int16 mins[3], maxs[3],
                              uint16 firstleafface, numleaffaces, firstleafbrush, numleafbrushes,
                              int16 leaf_water_data_id, pad       (v0 is 56 B: +24 B light cube)
    12 EDGES         4 B: uint16 v[2]
    13 SURFEDGES     int32; >= 0 -> edges[e].v[0], < 0 -> edges[-e].v[1]
    14 MODELS        48 B: float mins[3], maxs[3], origin[3], int32 headnode, firstface, numfaces
    17 LEAFBRUSHES   uint16 brush index
    18 BRUSHES       12 B: int32 firstside, numsides, contents
    19 BRUSHSIDES    8 B: uint16 planenum, int16 texinfo, int16 dispinfo, uint8 bevel, uint8 thin
    20 AREAS         8 B: int32 numareaportals, firstareaportal
    26 DISPINFO      176 B: float start_position[3], int32 disp_vert_start, disp_tri_start, power,
                           min_tess (CS:GO: high bits are flags, 0x40000000 = has multiblend),
                           float smoothing_angle, int32 contents, uint16 map_face, pad,
                           int32 lightmap_alpha_start, lightmap_sample_position_start,
                           neighbours (88 B), uint32 allowed_verts[10]
    33 DISP_VERTS    20 B: float vec[3], float dist, float alpha
    35 GAME_LUMP     int32 count, then 16 B: char id[4] (reversed fourCC, e.g. 'prps' = "sprp"),
                     uint16 flags, uint16 version, int32 fileofs (absolute), int32 filelen
    40 PAKFILE       an uncompressed (store) zip archive
    43 TEXDATA_STRING_DATA   NUL-terminated names
    44 TEXDATA_STRING_TABLE  int32 offsets into STRING_DATA
    48 DISP_TRIS     uint16 tags per displacement triangle
    63 DISP_MULTIBLEND (CS:GO) 80 B per vertex of multiblend displacements

Brushes and models
------------------
Brush planes use the Quake convention (normal points out, solid where
``dot(n, p) <= d``), the same as :mod:`mohkit.geom`. vbsp appends *bevel* sides
(``bevel != 0``) for collision; they are redundant for geometry and must be
skipped when rebuilding windings. ``func_detail`` brushes are merged into model
0 (world) and carry ``CONTENTS_DETAIL``. Brush entities (``func_brush``,
``func_door``, triggers, ``func_buyzone`` ...) have ``"model" "*N"`` and own the
brushes reachable from ``models[N].headnode``: walk the node tree to its leafs,
then ``leafbrushes[leaf.firstleafbrush : +numleafbrushes]``. Each entity's
brushes are written contiguously, so brushes no leaf lists (CSG-culled, fully
inside other solids) are attributed to the model on both sides of them; those in
a gap between models belong to entities vbsp consumed (``func_areaportal``,
``func_viscluster``) and get model ``-1``.

CS:GO pitfalls (verified on de_dust2, cs_office, de_inferno)
------------------------------------------------------------
* Brush-entity models are stored in *entity space*: world = rotate(angles) *
  p + entity ``origin`` (entities without ``origin`` are already in world space).
* Bevel sides point at texinfo 0 (whatever material that is, often
  ``TOOLS/TOOLSTRIGGER``) - never read materials from bevels.
* vbsp shares one texinfo among nodraw-like sides: in de_dust2 every hidden
  face (plain nodraw and player clip alike) says ``TOOLS/TOOLSPLAYERCLIP``, in
  cs_office ``TOOLS/TOOLSNODRAW``. Take clip semantics from *contents*
  (PLAYERCLIP, MONSTERCLIP, CURRENT_90 = grenade clip) and draw semantics from
  ``SURF_*``; see :func:`brush_tool_kinds`.
* Some axial bevel planes are *not* flagged (hundreds in de_inferno, on
  rotated brushes) and sit ~0.01 units inside the hull, producing sliver faces;
  :func:`prune_redundant_sides` / :meth:`Brush.geometry` remove them.
* Displacement parent brushes are not kept in the brush lump and
  ``brushside.dispinfo`` is always 0; build displacements from DISPINFO + faces.
* Solid leaves all have area 0, so the 3D skybox is found by probing just in
  front of brush faces (:meth:`SourceBSP.brush_face_areas`) and by static prop
  leaf lists, compared with the area of the ``sky_camera`` origin. Skybox
  contents are drawn scaled by ``sky_camera.scale`` (16) about that origin.
* Texdata names include vbsp patch materials from the pakfile
  (``maps/<map>/<material>_<x>_<y>_<z>`` cubemap patches, ``_wvt_patch``,
  ``_depth_<n>`` water); :meth:`SourceBSP.original_material` strips them.

Displacements
-------------
Each ``dispinfo`` belongs to a 4-edge face (``faces[i].dispinfo == index``).
Algorithm (matches vbsp/engine ``CCoreDispSurface``):

1. Take the face's 4 corners in surfedge order.
2. Rotate the list so it starts at the corner closest to ``start_position``.
3. With ``n = 2**power + 1`` and corners ``p0..p3``: for row ``i`` in ``0..n-1``
   interpolate ``a = lerp(p0, p1, i/(n-1))`` and ``b = lerp(p3, p2, i/(n-1))``;
   for column ``j`` the flat point is ``lerp(a, b, j/(n-1))``.
4. Vertex ``k = i*n + j`` is ``flat + disp_verts[start + k].vec * dist``
   (``vec``/``dist`` already include the VMF offsets and elevation).

Static props (game lump ``sprp``)
---------------------------------
::

    int32 dict_count; char name[128][dict_count]
    int32 leaf_count; uint16 leaf[leaf_count]
    int32 prop_count; StaticPropLump_t[prop_count]

CS:GO v10 record (76 B): origin[3], angles[3] (pitch yaw roll), uint16 prop_type,
first_leaf, leaf_count, uint8 solid, flags, int32 skin, float fade_min, fade_max,
lighting_origin[3], forced_fade_scale, uint8 min_cpu, max_cpu, min_gpu, max_gpu,
color32 diffuse_modulation, bool disable_x360 (1 byte + 3 bytes of garbage
padding - read only the first byte), uint32 flags_ex.
v11 drops ``disable_x360`` and appends ``float uniform_scale`` (76 B; 80 B if a
build kept ``disable_x360``). Other versions (4-9, TF2's 72 B v10) are handled
from the record size.
"""

from __future__ import annotations

import io
import lzma
import os
import re
import struct
import zipfile
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterator, Optional, Sequence, Union

import numpy as np

from .. import geom

HEADER_LUMPS = 64


class Lump:
    ENTITIES = 0
    PLANES = 1
    TEXDATA = 2
    VERTEXES = 3
    VISIBILITY = 4
    NODES = 5
    TEXINFO = 6
    FACES = 7
    LIGHTING = 8
    OCCLUSION = 9
    LEAFS = 10
    FACEIDS = 11
    EDGES = 12
    SURFEDGES = 13
    MODELS = 14
    WORLDLIGHTS = 15
    LEAFFACES = 16
    LEAFBRUSHES = 17
    BRUSHES = 18
    BRUSHSIDES = 19
    AREAS = 20
    AREAPORTALS = 21
    DISPINFO = 26
    ORIGINALFACES = 27
    PHYSDISP = 28
    PHYSCOLLIDE = 29
    VERTNORMALS = 30
    VERTNORMALINDICES = 31
    DISP_LIGHTMAP_ALPHAS = 32
    DISP_VERTS = 33
    DISP_LIGHTMAP_SAMPLE_POSITIONS = 34
    GAME_LUMP = 35
    LEAFWATERDATA = 36
    PRIMITIVES = 37
    PRIMVERTS = 38
    PRIMINDICES = 39
    PAKFILE = 40
    CLIPPORTALVERTS = 41
    CUBEMAPS = 42
    TEXDATA_STRING_DATA = 43
    TEXDATA_STRING_TABLE = 44
    OVERLAYS = 45
    LEAFMINDISTTOWATER = 46
    FACE_MACRO_TEXTURE_INFO = 47
    DISP_TRIS = 48
    WATEROVERLAYS = 50
    LIGHTING_HDR = 53
    WORLDLIGHTS_HDR = 54
    FACES_HDR = 58
    MAP_FLAGS = 59
    OVERLAY_FADES = 60
    OVERLAY_SYSTEM_LEVELS = 61
    PHYSLEVEL = 62
    DISP_MULTIBLEND = 63


class Contents:
    """``CONTENTS_*`` brush/leaf flags (bspflags.h, CS:GO)."""
    EMPTY = 0
    SOLID = 0x1
    WINDOW = 0x2
    AUX = 0x4
    GRATE = 0x8
    SLIME = 0x10
    WATER = 0x20
    BLOCKLOS = 0x40
    OPAQUE = 0x80
    TESTFOGVOLUME = 0x100
    UNUSED = 0x200
    BLOCKLIGHT = 0x400
    TEAM1 = 0x800
    TEAM2 = 0x1000
    IGNORE_NODRAW_OPAQUE = 0x2000
    MOVEABLE = 0x4000
    AREAPORTAL = 0x8000
    PLAYERCLIP = 0x10000
    MONSTERCLIP = 0x20000
    CURRENT_0 = 0x40000
    CURRENT_90 = 0x80000   # CS:GO grenade clip reuses this bit (see brush_tool_kinds)
    CURRENT_180 = 0x100000
    CURRENT_270 = 0x200000
    CURRENT_UP = 0x400000
    CURRENT_DOWN = 0x800000
    ORIGIN = 0x1000000
    MONSTER = 0x2000000
    DEBRIS = 0x4000000
    DETAIL = 0x8000000
    TRANSLUCENT = 0x10000000
    LADDER = 0x20000000
    HITBOX = 0x40000000


class Surf:
    """``SURF_*`` texinfo flags."""
    LIGHT = 0x1
    SKY2D = 0x2
    SKY = 0x4
    WARP = 0x8
    TRANS = 0x10
    NOPORTAL = 0x20
    TRIGGER = 0x40
    NODRAW = 0x80
    HINT = 0x100
    SKIP = 0x200
    NOLIGHT = 0x400
    BUMPLIGHT = 0x800
    NOSHADOWS = 0x1000
    NODECALS = 0x2000
    NOCHOP = 0x4000
    HITBOX = 0x8000


def flag_names(value: int, flags: type) -> list[str]:
    """Names of the set bits of ``value`` in a ``Contents``/``Surf`` style class."""
    out = []
    for name, bit in vars(flags).items():
        if name.isupper() and isinstance(bit, int) and bit and value & bit == bit:
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Record dtypes

PLANE_DT = np.dtype([("normal", "<f4", 3), ("dist", "<f4"), ("type", "<i4")])
TEXDATA_DT = np.dtype([("reflectivity", "<f4", 3), ("name_id", "<i4"), ("width", "<i4"), ("height", "<i4"),
                       ("view_width", "<i4"), ("view_height", "<i4")])
NODE_DT = np.dtype([("planenum", "<i4"), ("children", "<i4", 2), ("mins", "<i2", 3), ("maxs", "<i2", 3),
                    ("firstface", "<u2"), ("numfaces", "<u2"), ("area", "<i2"), ("pad", "<i2")])
TEXINFO_DT = np.dtype([("texture_vecs", "<f4", (2, 4)), ("lightmap_vecs", "<f4", (2, 4)), ("flags", "<i4"),
                       ("texdata", "<i4")])
FACE_DT = np.dtype([("planenum", "<u2"), ("side", "u1"), ("on_node", "u1"), ("firstedge", "<i4"),
                    ("numedges", "<i2"), ("texinfo", "<i2"), ("dispinfo", "<i2"), ("fog_volume", "<i2"),
                    ("styles", "u1", 4), ("lightofs", "<i4"), ("area", "<f4"), ("lm_mins", "<i4", 2),
                    ("lm_size", "<i4", 2), ("orig_face", "<i4"), ("num_prims", "<u2"), ("first_prim", "<u2"),
                    ("smoothing_groups", "<u4")])
LEAF_V1_DT = np.dtype([("contents", "<i4"), ("cluster", "<i2"), ("area_flags", "<i2"), ("mins", "<i2", 3),
                       ("maxs", "<i2", 3), ("firstleafface", "<u2"), ("numleaffaces", "<u2"),
                       ("firstleafbrush", "<u2"), ("numleafbrushes", "<u2"), ("water_data", "<i2"), ("pad", "<i2")])
LEAF_V0_DT = np.dtype([("contents", "<i4"), ("cluster", "<i2"), ("area_flags", "<i2"), ("mins", "<i2", 3),
                       ("maxs", "<i2", 3), ("firstleafface", "<u2"), ("numleaffaces", "<u2"),
                       ("firstleafbrush", "<u2"), ("numleafbrushes", "<u2"), ("water_data", "<i2"),
                       ("ambient", "u1", 24), ("pad", "<i2")])
EDGE_DT = np.dtype([("v", "<u2", 2)])
MODEL_DT = np.dtype([("mins", "<f4", 3), ("maxs", "<f4", 3), ("origin", "<f4", 3), ("headnode", "<i4"),
                     ("firstface", "<i4"), ("numfaces", "<i4")])
BRUSH_DT = np.dtype([("firstside", "<i4"), ("numsides", "<i4"), ("contents", "<i4")])
BRUSHSIDE_DT = np.dtype([("planenum", "<u2"), ("texinfo", "<i2"), ("dispinfo", "<i2"), ("bevel", "u1"),
                         ("thin", "u1")])
AREA_DT = np.dtype([("numareaportals", "<i4"), ("firstareaportal", "<i4")])
AREAPORTAL_DT = np.dtype([("portal_key", "<u2"), ("other_area", "<u2"), ("first_clip_vert", "<u2"),
                          ("num_clip_verts", "<u2"), ("planenum", "<i4")])
DISPINFO_DT = np.dtype({
    "names": ["start_position", "vert_start", "tri_start", "power", "min_tess", "smoothing_angle", "contents",
              "map_face", "lightmap_alpha_start", "lightmap_sample_start", "neighbors", "allowed_verts"],
    "formats": [("<f4", 3), "<i4", "<i4", "<i4", "<i4", "<f4", "<i4", "<u2", "<i4", "<i4", ("u1", 88),
                ("<u4", 10)],
    "offsets": [0, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 136],
    "itemsize": 176,
})
DISPVERT_DT = np.dtype([("vec", "<f4", 3), ("dist", "<f4"), ("alpha", "<f4")])
MULTIBLEND_DT = np.dtype([("multiblend", "<f4", 4), ("alphablend", "<f4", 4), ("colors", "<f4", (4, 3))])

DISP_FLAG_HAS_MULTIBLEND = 0x40000000
DISP_FLAG_MAGIC = 0x80000000


# ---------------------------------------------------------------------------
# LZMA

LZMA_ID = b"LZMA"


def decompress_lzma(data: bytes) -> bytes:
    """Decode Valve's LZMA wrapper (17-byte header + raw LZMA1 stream)."""
    if data[:4] != LZMA_ID:
        raise ValueError("not a Valve LZMA block")
    actual, lzma_size = struct.unpack_from("<II", data, 4)
    props = data[12:17]
    d = props[0]
    lc, d = d % 9, d // 9
    lp, pb = d % 5, d // 5
    dict_size = struct.unpack_from("<I", props, 1)[0]
    filt = {"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[filt])
    out = dec.decompress(data[17 : 17 + lzma_size], max_length=actual)
    if len(out) != actual:
        raise ValueError(f"LZMA: expected {actual} bytes, got {len(out)}")
    return out


def compress_lzma(data: bytes, preset: int = 6) -> bytes:
    """Encode ``data`` in Valve's LZMA wrapper (used by tests and re-packers)."""
    lc, lp, pb, dict_size = 3, 0, 2, 1 << 20
    filt = {"id": lzma.FILTER_LZMA1, "preset": preset, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}
    comp = lzma.compress(data, format=lzma.FORMAT_RAW, filters=[filt])
    props = bytes([(pb * 5 + lp) * 9 + lc]) + struct.pack("<I", dict_size)
    return LZMA_ID + struct.pack("<II", len(data), len(comp)) + props + comp


# ---------------------------------------------------------------------------
# Public records


@dataclass(frozen=True)
class LumpInfo:
    index: int
    offset: int
    length: int
    version: int
    uncompressed_size: int  # 0 = stored uncompressed

    @property
    def compressed(self) -> bool:
        return self.uncompressed_size != 0


@dataclass
class Entity:
    """One entity. ``props`` maps lower-cased keys to the *last* value; ``pairs`` keeps all."""
    pairs: list[tuple[str, str]]
    props: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.props:
            self.props = {k.lower(): v for k, v in self.pairs}

    @property
    def classname(self) -> str:
        return self.props.get("classname", "")

    def get(self, key: str, default: str = "") -> str:
        return self.props.get(key.lower(), default)

    def get_all(self, key: str) -> list[str]:
        k = key.lower()
        return [v for kk, v in self.pairs if kk.lower() == k]

    def __getitem__(self, key: str) -> str:
        return self.props[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self.props

    def __iter__(self) -> Iterator[str]:
        return iter(self.props)

    def items(self):
        return self.props.items()

    def vector(self, key: str, default: Optional[tuple[float, float, float]] = None):
        v = self.props.get(key.lower())
        if v is None:
            return default
        try:
            x = [float(t) for t in v.split()[:3]]
        except ValueError:
            return default
        return (x[0], x[1], x[2]) if len(x) == 3 else default

    @property
    def origin(self) -> Optional[tuple[float, float, float]]:
        return self.vector("origin")

    @property
    def model_index(self) -> Optional[int]:
        """``N`` for ``"model" "*N"`` brush entities, else ``None``."""
        m = self.props.get("model", "")
        if m.startswith("*") and m[1:].isdigit():
            return int(m[1:])
        return None

    def __repr__(self) -> str:
        return f"Entity({self.classname!r}, {len(self.pairs)} keys)"


@dataclass
class BrushSide:
    index: int                 # brushside index
    plane_index: int
    normal: tuple[float, float, float]
    dist: float
    texinfo: int               # -1 = none
    material: str              # texdata name as stored (often upper case); "" if no texinfo.
                               # Unreliable on bevels (texinfo 0) and on SURF_NODRAW sides (see
                               # module notes: vbsp shares one texinfo among nodraw-like sides).
    texture_vecs: Optional[tuple[tuple[float, float, float, float], tuple[float, float, float, float]]]
    surface_flags: int         # SURF_* from texinfo
    is_bevel: bool
    is_thin: bool
    dispinfo: int              # as stored; CS:GO writes 0 everywhere (displacement brushes are not
                               # kept as brushes - use SourceBSP.displacements())

    @property
    def plane(self) -> geom.Plane:
        return geom.Plane(self.normal, self.dist)

    @property
    def is_axial(self) -> bool:
        return max(abs(self.normal[0]), abs(self.normal[1]), abs(self.normal[2])) >= 0.99999

    @property
    def nodraw(self) -> bool:
        return bool(self.surface_flags & Surf.NODRAW)

    @property
    def is_drawn(self) -> bool:
        """False for nodraw/hint/skip/trigger/sky faces (sky shows the skybox instead)."""
        return not self.surface_flags & (Surf.NODRAW | Surf.HINT | Surf.SKIP | Surf.TRIGGER | Surf.SKY | Surf.SKY2D)


@dataclass
class Brush:
    index: int
    contents: int
    model: int                 # 0 = world (incl. func_detail), N = "*N", -1 = consumed entity / unknown
    sides: list[BrushSide]
    in_tree: bool = True       # False: no leaf lists this brush (CSG-culled or consumed entity)

    def planes(self, skip_bevels: bool = True) -> list[geom.Plane]:
        return [s.plane for s in self.sides if not (skip_bevels and s.is_bevel)]

    def real_sides(self) -> list[BrushSide]:
        """Sides without the bevel flag (may still contain unflagged axial bevels)."""
        return [s for s in self.sides if not s.is_bevel]

    def windings(self) -> list[geom.Winding]:
        """One winding per non-bevel side (same order as :meth:`real_sides`)."""
        return geom.brush_windings(self.planes())

    def geometry_sides(self, eps: float = 0.05) -> list[BrushSide]:
        """Non-bevel sides minus redundant planes; see :func:`prune_redundant_sides`."""
        return prune_redundant_sides(self.real_sides(), eps)

    def geometry(self, eps: float = 0.05) -> list[tuple[BrushSide, geom.Winding]]:
        """``(side, winding)`` for every face of the cleaned brush (windings non-empty)."""
        sides = self.geometry_sides(eps)
        return [(s, w) for s, w in zip(sides, geom.brush_windings([x.plane for x in sides])) if w]

    @property
    def materials(self) -> set[str]:
        return {s.material.lower() for s in self.sides if s.material and not s.is_bevel}

    @property
    def contents_names(self) -> list[str]:
        return flag_names(self.contents, Contents)

    @property
    def is_detail(self) -> bool:
        return bool(self.contents & Contents.DETAIL)

    @property
    def is_tool(self) -> bool:
        """No side is drawn (every non-bevel side is nodraw/hint/skip/trigger/sky)."""
        rs = self.real_sides()
        return bool(rs) and not any(s.is_drawn for s in rs)

    @property
    def tool_kinds(self) -> set[str]:
        return brush_tool_kinds(self)


def prune_redundant_sides(sides: Sequence[BrushSide], eps: float = 0.05) -> list[BrushSide]:
    """Drop planes that do not shape the brush.

    * sides whose winding is empty (fully redundant or duplicate planes);
    * axial sides of brushes that also have non-axial sides when the hull of the
      remaining planes lies within ``eps`` of them. vbsp leaves some axial bevel
      planes (the brush AABB) *without* the bevel flag - common on rotated
      brushes in de_inferno - and float rounding puts them up to ~0.01 units
      inside the true hull, which yields sliver faces and open hulls.
    """
    sides = list(sides)
    if not sides:
        return sides
    planes = [s.plane for s in sides]
    ws = geom.brush_windings(planes)
    keep = [i for i, w in enumerate(ws) if w]
    if any(not sides[i].is_axial for i in keep):
        for i in [i for i in keep if sides[i].is_axial]:
            others = [planes[j] for j in keep if j != i]
            pts = [p for w in geom.brush_windings(others) for p in w]
            if pts and max(planes[i].distance(p) for p in pts) <= eps:
                keep.remove(i)
    return [sides[i] for i in keep]


def brush_tool_kinds(brush: Brush) -> set[str]:
    """Classify a brush. An empty set means an ordinary visible solid brush.

    Evidence, in order of reliability:

    * contents flags: ``clip`` (PLAYERCLIP|MONSTERCLIP), ``playerclip``, ``npcclip``,
      ``grenadeclip`` (CS:GO reuses CONTENTS_CURRENT_90), ``areaportal``, ``origin``,
      ``water``, ``slime``, ``ladder``, ``blocklos``, ``blocklight``, ``team1``/``team2``,
      ``window``/``grate`` (translucent solids);
    * surface flags on non-bevel sides: ``skybox`` (SURF_SKY), ``skybox2d``,
      ``hint``, ``skip``, ``trigger``; ``nodraw`` when *every* side is SURF_NODRAW;
    * ``tools/*`` material names, only on sides *without* SURF_NODRAW (names of
      nodraw sides are shared/unreliable), e.g. ``fogvolume``, ``black``.
    """
    kinds: set[str] = set()
    c = brush.contents
    pc, mc = bool(c & Contents.PLAYERCLIP), bool(c & Contents.MONSTERCLIP)
    if pc and mc:
        kinds.add("clip")
    elif pc:
        kinds.add("playerclip")
    elif mc:
        kinds.add("npcclip")
    for bit, name in ((Contents.AREAPORTAL, "areaportal"), (Contents.ORIGIN, "origin"), (Contents.WATER, "water"),
                      (Contents.SLIME, "slime"), (Contents.LADDER, "ladder"), (Contents.BLOCKLOS, "blocklos"),
                      (Contents.BLOCKLIGHT, "blocklight"), (Contents.CURRENT_90, "grenadeclip"),
                      (Contents.TEAM1, "team1"), (Contents.TEAM2, "team2"), (Contents.WINDOW, "window"),
                      (Contents.GRATE, "grate")):
        if c & bit:
            kinds.add(name)
    real = brush.real_sides()
    if real and all(s.nodraw for s in real):
        kinds.add("nodraw")
    for side in real:
        f = side.surface_flags
        for bit, name in ((Surf.SKY, "skybox"), (Surf.SKY2D, "skybox2d"), (Surf.HINT, "hint"),
                          (Surf.SKIP, "skip"), (Surf.TRIGGER, "trigger")):
            if f & bit:
                kinds.add(name)
        if side.nodraw:
            continue
        m = side.material.lower()
        if m.startswith("tools/"):
            t = m[len("tools/"):]
            kinds.add(_TOOL_NAMES.get(t, t[len("tools"):] if t.startswith("tools") else t))
    return kinds


_TOOL_NAMES = {
    "toolsnodraw": "nodraw", "toolsskybox": "skybox", "toolsskybox2d": "skybox2d", "toolshint": "hint",
    "toolsskip": "skip", "toolstrigger": "trigger", "toolsareaportal": "areaportal",
    "toolsinvisible": "invisible", "toolsinvisibleladder": "ladder", "toolsplayerclip": "playerclip",
    "toolsnpcclip": "npcclip", "toolsgrenadeclip": "grenadeclip", "toolsblocklight": "blocklight",
    "toolsblock_los": "blocklos", "toolsorigin": "origin", "toolsfog": "fog", "toolsoccluder": "occluder",
    "toolsblockbullets": "blockbullets", "toolsblockbomb": "blockbomb", "toolsskyfog": "skyfog",
    "toolsblack": "black", "climb": "ladder", "climb_alpha": "ladder", "climb_versus": "ladder",
}


@dataclass
class Displacement:
    index: int
    face: int
    power: int
    corners: np.ndarray        # (4, 3) float64, rotated so corners[0] is nearest start_position
    start_position: np.ndarray  # (3,)
    positions: np.ndarray      # (n, n, 3) world-space vertices; [i, j] = row i (p0->p1), column j (p0->p3)
    flat: np.ndarray           # (n, n, 3) undisplaced grid
    offsets: np.ndarray        # (n, n, 3) displacement vectors (vec * dist)
    alphas: np.ndarray         # (n, n) blend alpha 0..255 ($basetexture2 weight)
    tri_tags: np.ndarray       # (2*(n-1)^2,) uint16 DISPTRI_TAG_* flags
    material: str
    texinfo: int
    contents: int
    flags: int                 # high bits of min_tess (CS:GO), 0 otherwise
    normal: tuple[float, float, float]  # face plane normal
    multiblend: Optional[np.ndarray] = None  # (n*n,) MULTIBLEND_DT records, CS:GO 4-way blends

    @property
    def size(self) -> int:
        return (1 << self.power) + 1

    def triangles(self) -> np.ndarray:
        """(2*(n-1)^2, 3) vertex indices into ``positions.reshape(-1, 3)``, wound so the
        flat surface faces ``normal`` (counter-clockwise seen from the front)."""
        n = self.size
        tris = []
        for i in range(n - 1):
            for j in range(n - 1):
                k = i * n + j
                if k % 2:
                    tris.append((k, k + n, k + 1))
                    tris.append((k + 1, k + n, k + n + 1))
                else:
                    tris.append((k, k + n, k + n + 1))
                    tris.append((k, k + n + 1, k + 1))
        t = np.array(tris, np.int32)
        flat = self.flat.reshape(-1, 3)
        a, b, c = flat[t[0, 0]], flat[t[0, 1]], flat[t[0, 2]]
        if np.dot(np.cross(b - a, c - a), self.normal) < 0:
            t = t[:, [0, 2, 1]]
        return t


@dataclass
class StaticProp:
    index: int
    model: str
    origin: tuple[float, float, float]
    angles: tuple[float, float, float]  # pitch yaw roll (degrees)
    solid: int                 # 0 none, 2 bbox, 6 vphysics
    skin: int
    flags: int                 # STATIC_PROP_* (0x1 fades, 0x2 use lighting origin, 0x10 no shadow, ...)
    fade_min: float
    fade_max: float
    lighting_origin: tuple[float, float, float]
    forced_fade_scale: float = 1.0
    first_leaf: int = 0
    leaf_count: int = 0
    leaves: tuple[int, ...] = ()
    cpu_level: tuple[int, int] = (0, 0)
    gpu_level: tuple[int, int] = (0, 0)
    diffuse_modulation: tuple[int, int, int, int] = (255, 255, 255, 255)
    disable_x360: bool = False
    flags_ex: int = 0
    uniform_scale: float = 1.0


@dataclass
class StaticProps:
    version: int
    record_size: int
    names: list[str]
    leaves: np.ndarray
    props: list[StaticProp]


@dataclass
class GameLump:
    id: str          # e.g. "sprp"
    flags: int
    version: int
    offset: int
    length: int
    data: bytes


# ---------------------------------------------------------------------------


class SourceBSP:
    """Lazy reader for a Source BSP file (arrays are parsed on first access)."""

    def __init__(self, path: Union[str, os.PathLike, bytes]):
        if isinstance(path, (bytes, bytearray)):
            self.path = "<memory>"
            self.data = bytes(path)
        else:
            self.path = str(path)
            with open(path, "rb") as fh:
                self.data = fh.read()
        d = self.data
        if d[:4] != b"VBSP":
            raise ValueError(f"{self.path}: not a Source BSP (ident {d[:4]!r})")
        self.version = struct.unpack_from("<i", d, 4)[0]
        raw = [struct.unpack_from("<4i", d, 8 + 16 * i) for i in range(HEADER_LUMPS)]
        self.lumps: list[LumpInfo] = self._lump_table(raw)
        self.map_revision = struct.unpack_from("<i", d, 8 + 16 * HEADER_LUMPS)[0]
        self._cache: dict[int, bytes] = {}

    def _lump_table(self, raw: list[tuple[int, int, int, int]]) -> list[LumpInfo]:
        size = len(self.data)

        def plausible(ofs: int, ln: int) -> bool:
            return ln == 0 or (0 < ofs and ofs + ln <= size and ln > 0)

        std = all(plausible(o, ln) for o, ln, _, _ in raw)
        if std:
            return [LumpInfo(i, o, ln, v, u) for i, (o, ln, v, u) in enumerate(raw)]
        # L4D2 order: version, fileofs, filelen, fourCC
        return [LumpInfo(i, o, ln, v, u) for i, (v, o, ln, u) in enumerate(raw)]

    # ------------------------------------------------------------------ lumps
    def lump_bytes(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        li = self.lumps[index]
        data = self.data[li.offset : li.offset + li.length]
        if li.length >= 17 and data[:4] == LZMA_ID:
            data = decompress_lzma(data)
        self._cache[index] = data
        return data

    def lump_array(self, index: int, dtype: np.dtype) -> np.ndarray:
        data = self.lump_bytes(index)
        dt = np.dtype(dtype)
        n = len(data) // dt.itemsize
        if n * dt.itemsize != len(data):
            raise ValueError(f"{self.path}: lump {index} size {len(data)} is not a multiple of {dt.itemsize}")
        return np.frombuffer(data, dt, n)

    # ------------------------------------------------------------------ basic arrays
    @cached_property
    def planes(self) -> np.ndarray:
        return self.lump_array(Lump.PLANES, PLANE_DT)

    @cached_property
    def vertices(self) -> np.ndarray:
        return self.lump_array(Lump.VERTEXES, np.dtype(("<f4", 3)))

    @cached_property
    def edges(self) -> np.ndarray:
        return self.lump_array(Lump.EDGES, np.dtype(("<u2", 2)))

    @cached_property
    def surfedges(self) -> np.ndarray:
        return self.lump_array(Lump.SURFEDGES, np.dtype("<i4"))

    @cached_property
    def faces(self) -> np.ndarray:
        f = self.lump_array(Lump.FACES, FACE_DT)
        return f if len(f) else self.lump_array(Lump.FACES_HDR, FACE_DT)

    @cached_property
    def original_faces(self) -> np.ndarray:
        return self.lump_array(Lump.ORIGINALFACES, FACE_DT)

    @cached_property
    def texinfo(self) -> np.ndarray:
        return self.lump_array(Lump.TEXINFO, TEXINFO_DT)

    @cached_property
    def texdata(self) -> np.ndarray:
        return self.lump_array(Lump.TEXDATA, TEXDATA_DT)

    @cached_property
    def nodes(self) -> np.ndarray:
        return self.lump_array(Lump.NODES, NODE_DT)

    @cached_property
    def leafs(self) -> np.ndarray:
        dt = LEAF_V0_DT if self.lumps[Lump.LEAFS].version == 0 else LEAF_V1_DT
        return self.lump_array(Lump.LEAFS, dt)

    @cached_property
    def leaf_areas(self) -> np.ndarray:
        """Area index of every leaf (low 9 bits of the packed field)."""
        return (self.leafs["area_flags"].astype(np.int32) & 0x1FF)

    @cached_property
    def leafbrushes(self) -> np.ndarray:
        return self.lump_array(Lump.LEAFBRUSHES, np.dtype("<u2"))

    @cached_property
    def leaffaces(self) -> np.ndarray:
        return self.lump_array(Lump.LEAFFACES, np.dtype("<u2"))

    @cached_property
    def models(self) -> np.ndarray:
        return self.lump_array(Lump.MODELS, MODEL_DT)

    @cached_property
    def brush_array(self) -> np.ndarray:
        return self.lump_array(Lump.BRUSHES, BRUSH_DT)

    @cached_property
    def brushside_array(self) -> np.ndarray:
        return self.lump_array(Lump.BRUSHSIDES, BRUSHSIDE_DT)

    @cached_property
    def areas(self) -> np.ndarray:
        return self.lump_array(Lump.AREAS, AREA_DT)

    @cached_property
    def areaportals(self) -> np.ndarray:
        return self.lump_array(Lump.AREAPORTALS, AREAPORTAL_DT)

    @cached_property
    def dispinfo(self) -> np.ndarray:
        return self.lump_array(Lump.DISPINFO, DISPINFO_DT)

    @cached_property
    def disp_verts(self) -> np.ndarray:
        return self.lump_array(Lump.DISP_VERTS, DISPVERT_DT)

    @cached_property
    def disp_tris(self) -> np.ndarray:
        return self.lump_array(Lump.DISP_TRIS, np.dtype("<u2"))

    # ------------------------------------------------------------------ strings / materials
    @cached_property
    def texdata_strings(self) -> list[str]:
        """Strings of TEXDATA_STRING_TABLE, in table order."""
        blob = self.lump_bytes(Lump.TEXDATA_STRING_DATA)
        table = self.lump_array(Lump.TEXDATA_STRING_TABLE, np.dtype("<i4"))
        out = []
        for ofs in table:
            end = blob.find(b"\0", int(ofs))
            out.append(blob[int(ofs) : end if end >= 0 else len(blob)].decode("utf-8", "replace"))
        return out

    @cached_property
    def texdata_names(self) -> list[str]:
        """Material name for every texdata record (as stored, usually upper case)."""
        strings = self.texdata_strings
        return [strings[i] if 0 <= i < len(strings) else "" for i in self.texdata["name_id"]]

    def texinfo_material(self, texinfo: int) -> str:
        if texinfo < 0 or texinfo >= len(self.texinfo):
            return ""
        td = int(self.texinfo[texinfo]["texdata"])
        names = self.texdata_names
        return names[td] if 0 <= td < len(names) else ""

    @cached_property
    def materials(self) -> list[str]:
        """Unique material names (lower case) referenced by texdata."""
        return sorted({n.lower() for n in self.texdata_names})

    @property
    def map_name(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0].lower()

    def original_material(self, name: str) -> str:
        """Strip vbsp's per-map patch naming from a material name.

        ``maps/de_dust2/de_dust/stonewall02_-1024_512_64`` -> ``de_dust/stonewall02``;
        also removes ``_wvt_patch`` and ``_depth_<n>`` suffixes. Names that are not
        under ``maps/<map>/`` are returned unchanged (lower case).
        """
        n = name.replace("\\", "/").lower()
        m = re.match(r"^maps/[^/]+/(.*)$", n)
        if not m:
            return n
        n = m.group(1)
        n = re.sub(r"_wvt_patch$", "", n)
        n = re.sub(r"_depth_-?\d+$", "", n)
        n = re.sub(r"_-?\d+_-?\d+_-?\d+$", "", n)
        return n

    # ------------------------------------------------------------------ entities
    @cached_property
    def entities(self) -> list[Entity]:
        text = self.lump_bytes(Lump.ENTITIES).decode("utf-8", "replace")
        ents: list[Entity] = []
        cur: Optional[list[tuple[str, str]]] = None
        key: Optional[str] = None
        for m in _ENT_TOKEN.finditer(text):
            tok = m.group(0)
            if tok == "{":
                cur, key = [], None
            elif tok == "}":
                if cur is not None:
                    ents.append(Entity(cur))
                cur, key = None, None
            elif cur is not None:
                s = m.group(1)
                if key is None:
                    key = s
                else:
                    cur.append((key, s))
                    key = None
        return ents

    def find_entities(self, classname: str) -> list[Entity]:
        c = classname.lower()
        return [e for e in self.entities if e.classname.lower() == c]

    @property
    def worldspawn(self) -> Entity:
        return self.entities[0]

    @cached_property
    def model_entities(self) -> dict[int, Entity]:
        """Owning entity of every brush model (``0`` -> worldspawn, ``N`` -> ``"model" "*N"``).

        Brush coordinates of model ``N > 0`` are relative to that entity's ``origin``
        and ``angles``.
        """
        out = {0: self.worldspawn} if self.entities else {}
        for e in self.entities:
            mi = e.model_index
            if mi is not None:
                out[mi] = e
        return out

    # ------------------------------------------------------------------ tree walking
    def model_leaves(self, model: int) -> list[int]:
        """Leaf indices of a model's BSP tree."""
        head = int(self.models[model]["headnode"])
        children = self.nodes["children"]
        out: list[int] = []
        stack = [head]
        while stack:
            n = stack.pop()
            if n < 0:
                out.append(-1 - n)
                continue
            c0, c1 = children[n]
            stack.append(int(c0))
            stack.append(int(c1))
        return out

    def leaf_brushes(self, leaf: int) -> np.ndarray:
        lf = self.leafs[leaf]
        a = int(lf["firstleafbrush"])
        return self.leafbrushes[a : a + int(lf["numleafbrushes"])]

    @cached_property
    def brush_models(self) -> np.ndarray:
        """Model index for every brush (-1 if no model tree references it)."""
        out = np.full(len(self.brush_array), -1, np.int32)
        for mi in range(len(self.models)):
            leaves = np.array(self.model_leaves(mi), np.int64)
            if not len(leaves):
                continue
            lf = self.leafs[leaves]
            idx = [self.leafbrushes[int(a) : int(a) + int(n)] for a, n in zip(lf["firstleafbrush"], lf["numleafbrushes"]) if n]
            if not idx:
                continue
            bs = np.unique(np.concatenate(idx))
            unset = bs[out[bs] < 0]
            out[unset] = mi
        return out

    @cached_property
    def brush_owner_models(self) -> np.ndarray:
        """Like :attr:`brush_models`, but unreferenced brushes inherit the model of
        their neighbours when the nearest referenced brush before and after agree.

        vbsp writes each entity's brushes contiguously, so a brush culled from the
        tree (fully inside other solids, or outside the hull) that sits inside the
        world range is a world brush. Brushes in a gap *between* two models belong
        to entities vbsp consumed (``func_areaportal``, ``func_viscluster`` ...)
        and stay ``-1``.
        """
        tree = self.brush_models
        out = tree.copy()
        ref = np.nonzero(tree >= 0)[0]
        if not len(ref):
            return out
        for i in np.nonzero(tree < 0)[0]:
            k = int(np.searchsorted(ref, i))
            if 0 < k < len(ref) and tree[ref[k - 1]] == tree[ref[k]]:
                out[i] = tree[ref[k - 1]]
        return out

    def model_brush_indices(self, model: int, include_culled: bool = True) -> np.ndarray:
        """Brush indices owned by ``model`` (see :attr:`brush_owner_models`)."""
        arr = self.brush_owner_models if include_culled else self.brush_models
        return np.nonzero(arr == model)[0]

    @cached_property
    def brush_leaves(self) -> list[list[int]]:
        """For every brush, the leaves that list it in their leafbrush range."""
        out: list[list[int]] = [[] for _ in range(len(self.brush_array))]
        lf = self.leafs
        for li, (a, n) in enumerate(zip(lf["firstleafbrush"], lf["numleafbrushes"])):
            for b in self.leafbrushes[int(a) : int(a) + int(n)]:
                out[int(b)].append(li)
        return out

    def point_leaf(self, point: Sequence[float], model: int = 0) -> int:
        node = int(self.models[model]["headnode"])
        planes = self.planes
        nodes = self.nodes
        px, py, pz = float(point[0]), float(point[1]), float(point[2])
        while node >= 0:
            nd = nodes[node]
            pl = planes[int(nd["planenum"])]
            n = pl["normal"]
            d = float(n[0]) * px + float(n[1]) * py + float(n[2]) * pz - float(pl["dist"])
            node = int(nd["children"][0] if d >= 0 else nd["children"][1])
        return -1 - node

    def point_area(self, point: Sequence[float]) -> int:
        return int(self.leaf_areas[self.point_leaf(point)])

    @cached_property
    def sky_camera(self) -> Optional[Entity]:
        cams = self.find_entities("sky_camera")
        return cams[0] if cams else None

    def skybox_area(self) -> Optional[int]:
        """Area containing the ``sky_camera`` (the 3D skybox), or ``None``."""
        cam = self.sky_camera
        if cam is None or cam.origin is None:
            return None
        return self.point_area(cam.origin)

    def brush_face_areas(self, brush: Brush, windings: Optional[Sequence[geom.Winding]] = None,
                         offset: float = 1.0) -> set[int]:
        """Areas that a brush's faces look into (area 0 = outside/solid is dropped).

        Solid leaves always have area 0, so a brush's own leaves say nothing; instead
        each non-bevel face centre is pushed ``offset`` units along its normal and
        located in the world tree. A brush whose set is ``{skybox_area()}`` belongs to
        the 3D skybox. ``windings`` may be passed if already computed (same order as
        ``brush.real_sides()``); brush-entity brushes are in model space, so only
        world brushes (model 0) give meaningful results.
        """
        sides = brush.real_sides()
        ws = windings if windings is not None else geom.brush_windings([s.plane for s in sides])
        out: set[int] = set()
        for s, w in zip(sides, ws):
            if len(w) < 3:
                continue
            c = geom.winding_center(w)
            p = (c[0] + s.normal[0] * offset, c[1] + s.normal[1] * offset, c[2] + s.normal[2] * offset)
            a = self.point_area(p)
            if a:
                out.add(a)
        return out

    def prop_areas(self, prop: "StaticProp") -> set[int]:
        """Areas of the leaves a static prop touches (from its sprp leaf list)."""
        la = self.leaf_areas
        return {int(la[i]) for i in prop.leaves if 0 <= i < len(la) and la[i]}

    # ------------------------------------------------------------------ faces
    def face_vertices(self, face: int) -> np.ndarray:
        """(numedges, 3) float64 polygon of a face, in surfedge order."""
        f = self.faces[face]
        a, n = int(f["firstedge"]), int(f["numedges"])
        se = self.surfedges[a : a + n]
        e = self.edges[np.abs(se)]
        vi = np.where(se >= 0, e[:, 0], e[:, 1])
        return self.vertices[vi].astype(np.float64)

    # ------------------------------------------------------------------ brushes
    def brush(self, index: int) -> Brush:
        b = self.brush_array[index]
        first, num = int(b["firstside"]), int(b["numsides"])
        planes = self.planes
        ti_arr = self.texinfo
        sides = []
        for si in range(first, first + num):
            s = self.brushside_array[si]
            pn = int(s["planenum"])
            pl = planes[pn]
            ti = int(s["texinfo"])
            if 0 <= ti < len(ti_arr):
                t = ti_arr[ti]
                tv = t["texture_vecs"].astype(np.float64)
                vecs = (tuple(tv[0].tolist()), tuple(tv[1].tolist()))
                sflags = int(t["flags"])
            else:
                vecs, sflags = None, 0
            nrm = pl["normal"].astype(np.float64)
            sides.append(BrushSide(si, pn, (float(nrm[0]), float(nrm[1]), float(nrm[2])), float(pl["dist"]), ti,
                                   self.texinfo_material(ti), vecs, sflags, bool(s["bevel"]), bool(s["thin"]),
                                   int(s["dispinfo"])))
        return Brush(index, int(b["contents"]), int(self.brush_owner_models[index]), sides,
                     in_tree=bool(self.brush_models[index] >= 0))

    def brushes(self, model: Optional[int] = None, include_culled: bool = True) -> Iterator[Brush]:
        """Every brush (or only those of ``model``), with resolved sides.

        ``include_culled=False`` drops brushes no leaf references (``in_tree`` False).
        """
        if model is None:
            idx: Sequence[int] = range(len(self.brush_array))
            if not include_culled:
                idx = np.nonzero(self.brush_models >= 0)[0].tolist()
        else:
            idx = self.model_brush_indices(model, include_culled).tolist()
        for i in idx:
            yield self.brush(i)

    # ------------------------------------------------------------------ displacements
    @cached_property
    def dispinfo_faces(self) -> np.ndarray:
        """Face index for every dispinfo (-1 if no face references it)."""
        out = np.full(len(self.dispinfo), -1, np.int32)
        fd = self.faces["dispinfo"]
        ids = np.nonzero(fd >= 0)[0]
        out[fd[ids]] = ids
        return out

    @cached_property
    def _multiblend_starts(self) -> Optional[np.ndarray]:
        li = self.lumps[Lump.DISP_MULTIBLEND] if len(self.lumps) > Lump.DISP_MULTIBLEND else None
        if li is None or li.length == 0:
            return None
        n = (1 << self.dispinfo["power"].astype(np.int64)) + 1
        has = (self.dispinfo["min_tess"].astype(np.int64) & DISP_FLAG_HAS_MULTIBLEND) != 0
        counts = np.where(has, n * n, 0)
        return np.concatenate([[0], np.cumsum(counts)])

    def displacement(self, index: int) -> Displacement:
        di = self.dispinfo[index]
        face = int(self.dispinfo_faces[index])
        if face < 0:
            face = int(di["map_face"])
        corners = self.face_vertices(face)
        if len(corners) != 4:
            raise ValueError(f"{self.path}: displacement {index} face {face} has {len(corners)} corners")
        start = di["start_position"].astype(np.float64)
        k = int(np.argmin(((corners - start) ** 2).sum(axis=1)))
        corners = np.roll(corners, -k, axis=0)
        power = int(di["power"])
        n = (1 << power) + 1
        t = np.linspace(0.0, 1.0, n)
        p0, p1, p2, p3 = corners
        a = p0[None, :] + (p1 - p0)[None, :] * t[:, None]     # (n, 3) along p0 -> p1 (rows)
        b = p3[None, :] + (p2 - p3)[None, :] * t[:, None]     # (n, 3) along p3 -> p2
        flat = a[:, None, :] + (b - a)[:, None, :] * t[None, :, None]   # (n, n, 3)
        vs = int(di["vert_start"])
        dv = self.disp_verts[vs : vs + n * n]
        offsets = (dv["vec"].astype(np.float64) * dv["dist"].astype(np.float64)[:, None]).reshape(n, n, 3)
        ts = int(di["tri_start"])
        f = self.faces[face]
        ti = int(f["texinfo"])
        pl = self.planes[int(f["planenum"])]
        nrm = pl["normal"].astype(np.float64)
        if f["side"]:
            nrm = -nrm
        min_tess = int(di["min_tess"]) & 0xFFFFFFFF
        flags = min_tess & 0xFF000000 if min_tess & DISP_FLAG_MAGIC else 0
        mb = None
        starts = self._multiblend_starts
        if starts is not None and flags & DISP_FLAG_HAS_MULTIBLEND:
            raw = self.lump_array(Lump.DISP_MULTIBLEND, MULTIBLEND_DT)
            mb = raw[int(starts[index]) : int(starts[index]) + n * n]
        return Displacement(
            index=index, face=face, power=power, corners=corners, start_position=start,
            positions=flat + offsets, flat=flat, offsets=offsets,
            alphas=dv["alpha"].astype(np.float32).reshape(n, n),
            tri_tags=self.disp_tris[ts : ts + 2 * (n - 1) ** 2].copy(),
            material=self.texinfo_material(ti), texinfo=ti, contents=int(di["contents"]), flags=flags,
            normal=(float(nrm[0]), float(nrm[1]), float(nrm[2])), multiblend=mb)

    def displacements(self) -> Iterator[Displacement]:
        for i in range(len(self.dispinfo)):
            yield self.displacement(i)

    # ------------------------------------------------------------------ game lumps
    @cached_property
    def game_lumps(self) -> dict[str, GameLump]:
        li = self.lumps[Lump.GAME_LUMP]
        if li.length < 4:
            return {}
        hdr = self.data[li.offset : li.offset + li.length]
        if hdr[:4] == LZMA_ID:  # never expected, but be tolerant
            hdr = decompress_lzma(hdr)
        count = struct.unpack_from("<i", hdr, 0)[0]
        recs = [struct.unpack_from("<4sHHii", hdr, 4 + 16 * i) for i in range(count)]
        out: dict[str, GameLump] = {}
        for gid, gflags, gver, gofs, glen in recs:
            name = gid[::-1].decode("latin-1")
            if gofs <= 0 and glen <= 0:
                continue
            raw = self.data[gofs : gofs + glen]
            if gflags & 1 and raw[:4] == LZMA_ID:
                raw = decompress_lzma(raw)
            out[name] = GameLump(name, gflags, gver, gofs, glen, raw)
        return out

    def static_props(self) -> StaticProps:
        gl = self.game_lumps.get("sprp")
        if gl is None:
            return StaticProps(0, 0, [], np.zeros(0, np.uint16), [])
        return parse_static_props(gl.data, gl.version)

    # ------------------------------------------------------------------ pakfile
    def pakfile_bytes(self) -> bytes:
        return self.lump_bytes(Lump.PAKFILE)

    def pakfile(self) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(self.pakfile_bytes()))

    # ------------------------------------------------------------------ bounds
    def world_bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        m = self.models[0]
        return (tuple(float(x) for x in m["mins"]), tuple(float(x) for x in m["maxs"]))  # type: ignore[return-value]

    def __repr__(self) -> str:
        return (f"SourceBSP({self.path!r}, v{self.version}, rev {self.map_revision}, "
                f"{len(self.brush_array)} brushes, {len(self.models)} models)")


_ENT_TOKEN = re.compile(r'[{}]|"([^"]*)"')


# ---------------------------------------------------------------------------
# Static props

_SPRP_BASE = struct.Struct("<3f3fHHHBB")  # origin, angles, prop_type, first_leaf, leaf_count, solid, flags (32 B)


def parse_static_props(data: bytes, version: int) -> StaticProps:
    pos = 0
    (ndict,) = struct.unpack_from("<i", data, pos)
    pos += 4
    names = []
    for i in range(ndict):
        raw = data[pos : pos + 128]
        names.append(raw.split(b"\0", 1)[0].decode("utf-8", "replace"))
        pos += 128
    (nleaf,) = struct.unpack_from("<i", data, pos)
    pos += 4
    leaves = np.frombuffer(data, "<u2", nleaf, pos).copy()
    pos += 2 * nleaf
    (nprops,) = struct.unpack_from("<i", data, pos)
    pos += 4
    remaining = len(data) - pos
    size = remaining // nprops if nprops else 0
    props: list[StaticProp] = []
    for i in range(nprops):
        props.append(_parse_prop(data, pos + i * size, size, version, i, names, leaves))
    return StaticProps(version, size, names, leaves, props)


def _parse_prop(data: bytes, o: int, size: int, version: int, index: int, names: list[str],
                leaves: np.ndarray) -> StaticProp:
    ox, oy, oz, ax, ay, az, ptype, first_leaf, leaf_count, solid, flags = _SPRP_BASE.unpack_from(data, o)
    p = o + 32
    skin, fade_min, fade_max, lx, ly, lz = struct.unpack_from("<i2f3f", data, p)
    p += 24
    rec = dict(skin=skin, fade_min=fade_min, fade_max=fade_max, lighting_origin=(lx, ly, lz))
    if version >= 5:
        rec["forced_fade_scale"] = struct.unpack_from("<f", data, p)[0]
        p += 4
    tf2_style = version in (6, 7) or (version == 10 and size == 72)
    if tf2_style:
        p += 4  # min/max DX level
        if version == 10:
            rec["flags_ex"] = struct.unpack_from("<I", data, p)[0]
            p += 8  # uint32 flags + lightmap res x/y
    if version >= 8 and not tf2_style:
        c0, c1, g0, g1 = struct.unpack_from("<4B", data, p)
        rec["cpu_level"], rec["gpu_level"] = (c0, c1), (g0, g1)
        p += 4
    if version >= 7 and not tf2_style:
        rec["diffuse_modulation"] = tuple(struct.unpack_from("<4B", data, p))
        p += 4
    if version in (9, 10) and not tf2_style:
        rec["disable_x360"] = bool(data[p])  # 1-byte bool + 3 bytes of uninitialised padding
        p += 4
    if version >= 10 and not tf2_style:
        rec["flags_ex"] = struct.unpack_from("<I", data, p)[0]
        p += 4
    if version >= 11:
        # Some builds keep disable_x360 in v11 (80 B records): skip it when the size says so.
        if size - (p - o) >= 8:
            rec["disable_x360"] = bool(data[p - 4])
            rec["flags_ex"] = struct.unpack_from("<I", data, p)[0]
            p += 4
        rec["uniform_scale"] = struct.unpack_from("<f", data, p)[0]
        p += 4
    name = names[ptype] if 0 <= ptype < len(names) else ""
    lv = tuple(int(x) for x in leaves[first_leaf : first_leaf + leaf_count])
    return StaticProp(index=index, model=name, origin=(ox, oy, oz), angles=(ax, ay, az), solid=solid, flags=flags,
                      first_leaf=first_leaf, leaf_count=leaf_count, leaves=lv, **rec)
