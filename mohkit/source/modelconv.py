"""Convert Source (CS:GO) static prop models to MOHAA static models.

    >>> fs = source_fs(bsp="csgo/maps/de_dust2.bsp")                     # doctest: +SKIP
    >>> m = convert_model(fs, "models/props/de_dust/dust_rusty_barrel.mdl")  # doctest: +SKIP
    >>> m.tik, m.vertices, m.has_collision                                # doctest: +SKIP
    ('models/csgo/props/de_dust/dust_rusty_barrel.tik', 574, True)

Output per model (all paths are game paths, every file in ``ConvertedModel.files``)::

    models/<prefix>/<dir>/<name>.tik    TIKI: scale 1, one surface line per SKD surface
    models/<prefix>/<dir>/<name>.skd    mesh (see :mod:`.skd` for the exact layout)
    models/<prefix>/<dir>/<name>.skc    one-frame idle pose with the model bounds
    models/<prefix>/<dir>/<name>.map    collision: clip brushes in model space
    textures/<prefix>/<material>.tga    $basetexture, power of two <= max_texture
    scripts/<prefix>_<name>.shader      one shader per material (+ clip shaders)

Placement convention (verified in OpenMoHAA, see ``tests/test_modelconv.py``):
a ``static_*`` entity with ``"model" "<prefix>/<dir>/<name>.tik"``, ``origin`` =
Source prop origin, ``angles`` = Source ``pitch yaw roll`` and ``scale`` =
``uniform_scale``. Model space is unchanged (X forward, Y left, Z up, 1 Source
unit = 1 MOHAA unit), both engines build the rotation the same way (yaw about Z,
then pitch about Y, then roll about X; positive pitch tilts the nose down).

Geometry: LOD 0, submodel 0 of every body part. Meshes are grouped by the
material the chosen skin family gives them, welded (identical position, normal
and UV), and split into SKD surfaces of <= 999 vertices / 1999 triangles. A model
needing more than 24 surfaces is partitioned into several TIKIs
(``<name>.tik``, ``<name>_p2.tik`` ...); place all of them with the same
transform (``ConvertedModel.tiks``). Only the first carries the collision map.

Collision: Q3map loads ``models/<model>.map`` for every static model and bakes
its brushes (model space, transformed like the model) into world collision;
static models themselves are not solid. Each convex ``.phy`` piece becomes one
detail brush built from its hull triangles' planes, textured with the clip
shader matching the surface property (``common/woodclip``, ``common/metalclip``,
...). ``solid=2`` uses the MDL hull box instead, ``solid=0`` writes a map with no
brushes (a distinct ``_nc`` TIKI so solid and non-solid instances can coexist).

Shaders: ``rgbGen static`` (MOHlight vertex lighting); ``$alphatest`` ->
``alphaFunc GE128`` + ``depthWrite`` + ``cull none``; ``$translucent`` ->
``blendFunc blend``; ``$additive`` -> ``blendFunc add``; ``$nocull`` -> ``cull
none``; ``surfaceparm`` from ``$surfaceprop`` (``rock`` for stone, concrete,
brick ...: ``surfaceparm stone`` sets no flag in MOHAA).

Limits the caller must budget (see ``ConvertedModel.vertices``): original
MOHlight 1.48 crashed once above roughly 75,000 statically lit vertices on the full
de_dust2 conversion, but 161,741 (102 converted props) lit fine in a small test map
(docs/design.md), so the real limit is unknown.
``vertices`` is exactly what MOHlight counts ("Total Vertecies Lit" equals the
sum over placements). de_dust2's 1,523 props total ~826,000, so a map
converter must keep most of them as ``script_model`` or drop them.

Verified with EA Q3map 1.34 / MOHlight 1.48 and OpenMoHAA (test room with 22
converted models, dust2 prop clusters reproduced at their Source transforms):
Q3map bakes every collision brush at ``origin + scale * R(angles) * p`` (checked
brush by brush in the BSP, incl. pitch/roll and entity ``scale``), and the
renderer uses the same rotation. Q3map, MOHlight and the game print "WARNING-
DOWNGRADING TO OLD ANIMATION FORMAT" once per ``.skc``: retail paks ship
pre-packed ``newanim/*.skc`` copies that the loader tries first; without one it
falls back to the version-13 file, which is the normal path (debug message only).
Hulls thinner than 1 unit (sheet-metal signs, gate bars) are thickened to 1 unit.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

import numpy as np

from .. import geom
from ..mapfile import Brush, Entity, Face, MapFile
from ..shaders import editor_image
from . import skd as _skd
from .studiomdl import StudioModel, load_phy, load_studio_model
from .vmt import MaterialInfo, material_info
from .vpk import SearchPath, ZipSource, normalize_path
from .vtf import VTF

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------------------
# File system


def source_fs(csgo_dir: Union[str, os.PathLike, None] = None, bsp=None) -> SearchPath:
    """Search path like the game's: map pakfile, loose files, then ``pak01_dir.vpk``.

    ``csgo_dir`` is the install root (contains ``csgo/pak01_dir.vpk``) or the
    ``csgo`` game dir itself; default from :mod:`mohkit.config`. ``bsp`` is a
    path or :class:`~mohkit.source.bsp.SourceBSP` whose pakfile is searched first.
    """
    if csgo_dir is None:
        from ..config import load
        csgo_dir = load().csgo_dir
    if csgo_dir is None:
        raise RuntimeError("CS:GO install not found (set MOHKIT_CSGO_DIR)")
    game = Path(csgo_dir)
    if (game / "csgo" / "pak01_dir.vpk").is_file():
        game = game / "csgo"
    fs = SearchPath.for_game(game)
    if bsp is not None:
        if not hasattr(bsp, "pakfile"):
            from .bsp import SourceBSP
            bsp = SourceBSP(bsp)
        fs.add(ZipSource(bsp.pakfile()), first=True)
    return fs


# ---------------------------------------------------------------------------
# Result


@dataclass
class ConvertedModel:
    tik: str                                  # game path of the (first) TIKI
    files: dict[str, bytes]                   # every file to package
    bounds: tuple[Vec3, Vec3]                 # model space, after ``scale``
    vertices: int                             # SKD vertices (welded; what MOHlight lights per instance)
    surfaces: int                             # SKD surfaces over all parts
    has_collision: bool
    warnings: list[str] = field(default_factory=list)
    tiks: list[str] = field(default_factory=list)       # all parts (>24 surfaces are partitioned)
    shaders: dict[str, str] = field(default_factory=dict)  # shader name -> script text
    materials: list[str] = field(default_factory=list)  # Source materials used (resolved names)
    triangles: int = 0
    collision_brushes: int = 0
    source: str = ""                          # the .mdl path
    pivot: Vec3 = (0.0, 0.0, 0.0)             # Source-model point now at the TIKI origin (``centre``)

    @property
    def model_key(self) -> str:
        """Value for a static entity's ``model`` key (the TIKI path without ``models/``)."""
        return self.tik[len("models/"):] if self.tik.startswith("models/") else self.tik


# The engine lights a non-solid script_model with one sun trace and one light-grid sample
# from 8 units below its origin (cg_modelanim.c: lightingOrigin = origin + centre of the
# packed box, which is (0,0,-16)..(0,0,0) for SOLID_NOT: q_math.c IntegerToBoundingBox).
# ``convert_model(centre=True)`` puts that point this far above the mesh's top, where
# neither the model's own collision nor an uneven floor can shadow it.
LIGHT_ABOVE_TOP = 8.0
_LIGHT_BELOW_ORIGIN = 8.0


# ---------------------------------------------------------------------------
# Naming

_SAFE = re.compile(r"[^a-z0-9_/.-]+")


def _slug(s: str) -> str:
    s = _SAFE.sub("_", s.lower().replace("\\", "/")).strip("/")
    return re.sub(r"_+", "_", s) or "x"


def _flat(s: str) -> str:
    """Slug without directories (script file names must sit directly in ``scripts/``)."""
    return _slug(s).replace("/", "_").replace(".", "_")


def _hash(s: str, n: int = 6) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def model_names(mdl_path: str, prefix: str = "csgo", skin: int = 0, scale: float = 1.0) -> tuple[str, str]:
    """(directory, base name) of the converted files, e.g. ``("models/csgo/props/de_dust", "dust_rusty_barrel")``.

    Every game path must fit ``MAX_QPATH`` (63 characters) with room for the
    ``_p2``/``_nc`` suffixes, otherwise the directory is shortened to
    ``models/<prefix>/x`` and the name gets a hash of the full path.
    """
    rel = _slug(normalize_path(mdl_path))
    if rel.startswith("models/"):
        rel = rel[len("models/"):]
    if rel.endswith(".mdl"):
        rel = rel[:-4]
    d, _, base = rel.rpartition("/")
    if skin:
        base += f"_skin{skin}"
    if abs(scale - 1.0) > 1e-6:
        base += "_x" + f"{scale:g}".replace(".", "p").replace("-", "m")
    directory = f"models/{prefix}/{d}" if d else f"models/{prefix}"
    reserve = len("_p2_nc.tik")
    if len(directory) + 1 + len(base) + reserve > _skd.MAX_QPATH:
        directory = f"models/{prefix}/{_hash(d, 4)}"    # directory hash keeps same-named models apart
        room = _skd.MAX_QPATH - len(directory) - 1 - reserve
        if len(base) > room:
            base = f"{base[:room - 7]}_{_hash(rel + base)}"
    return directory, base


def texture_name(material: str, prefix: str = "csgo") -> str:
    """Shader / image name (no extension) for a Source material, <= 59 characters."""
    rel = _slug(material)
    if rel.startswith("models/"):
        rel = rel[len("models/"):]
    name = f"textures/{prefix}/{rel}"
    if len(name) <= 59:  # + ".tga" fits MAX_QPATH; Q3map mishandles 60-character shader names
        return name
    base = rel.rpartition("/")[2]
    return f"textures/{prefix}/m/{base[:30]}_{_hash(rel)}"


# ---------------------------------------------------------------------------
# Surface properties

# (substrings, MOHAA surfaceparm or None, clip shader); first match wins.
_SURFACE_RULES: list[tuple[tuple[str, ...], Optional[str], str]] = [
    (("chainlink", "metalgrate", "grate", "fence", "wire"), "grill", "common/grillclip"),
    (("metal", "canister", "vent", "roller", "weapon", "computer", "solidmetal", "gunship", "combine"),
     "metal", "common/metalclip"),
    (("glass", "window"), "glass", "common/glassclip"),
    (("wood", "ladder"), "wood", "common/woodclip"),
    (("cardboard", "paper", "papercup", "book"), "paper", "common/paperclip"),
    (("carpet", "cloth", "fabric", "rug", "upholstery", "mattress", "pillow", "cushion"), "carpet",
     "common/carpetclip"),
    (("gravel",), "gravel", "common/gravelclip"),
    (("sand",), "sand", "common/sandclip"),
    (("mud",), "mud", "common/mudclip"),
    (("dirt", "soil"), "dirt", "common/dirtclip"),
    (("grass",), "grass", "common/grassclip"),
    (("foliage", "leaves", "leaf", "plant", "hay", "straw"), "foliage", "common/foliageclip"),
    (("snow", "ice"), "snow", "common/snowclip"),
    (("water", "slosh", "puddle", "wade"), "puddle", "common/puddleclip"),
    (("rock", "stone", "concrete", "brick", "boulder", "tile", "ceramic", "plaster", "porcelain", "pottery",
      "asphalt", "cinder", "marble", "clay", "brick"), "rock", "rock"),
]


def surface_type(surfaceprop: Optional[str]) -> tuple[Optional[str], str]:
    """(``surfaceparm`` for the model shader or ``None``, clip-shader kind) for a Source surfaceprop.

    The clip kind is a stock ``common/*clip`` shader name, ``"rock"`` (custom rock
    clip, since ``common/stoneclip`` uses the unknown ``surfaceparm stone``) or
    ``"solid"`` (plain solid clip for plastic, rubber, default ...).
    """
    sp = (surfaceprop or "").lower()
    if sp:
        for keys, parm, clip in _SURFACE_RULES:
            if any(k in sp for k in keys):
                return parm, clip
    return None, "solid"


def clip_shader_name(kind: str, prefix: str = "csgo") -> str:
    """Texture name written on collision brush faces (``.map`` faces omit ``textures/``)."""
    return kind if kind.startswith("common/") else f"{prefix}/clip_{kind}"


def clip_shader_text(kind: str, prefix: str = "csgo") -> Optional[str]:
    """Script for the custom clip shaders (stock ``common/*`` ones need none)."""
    if kind.startswith("common/"):
        return None
    lines = ["textures/" + clip_shader_name(kind, prefix), "{",
             f"\tqer_editorimage textures/common/{'stoneclip' if kind == 'rock' else 'clip'}.tga",
             "\tqer_keyword utility", "\tqer_trans .4"]
    if kind == "rock":
        lines.append("\tsurfaceparm rock")
    lines += ["\tsurfaceparm nodraw", "\tsurfaceparm trans", "\tsurfaceparm nomarks", "}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Textures


def _parse_color(v) -> Optional[np.ndarray]:
    if not isinstance(v, str):
        return None
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", v)
    if len(nums) < 3:
        return None
    c = np.array([float(x) for x in nums[:3]], np.float32)
    if "{" in v:  # {r g b} is 0..255
        c /= 255.0
    return c


def _pow2_at_most(n: int, cap: int) -> int:
    p = 1
    while p * 2 <= n:
        p *= 2
    if n - p > p * 2 - n and p * 2 <= cap:  # nearer to the next power of two
        p *= 2
    return max(1, min(p, cap))


def tga_bytes(rgba: np.ndarray, alpha: bool) -> bytes:
    """Uncompressed type-2 TGA, bottom-up rows (image origin bit clear), like vtf.save_tga."""
    img = np.ascontiguousarray(rgba, np.uint8)
    h, w = img.shape[:2]
    data = img[::-1, :, [2, 1, 0, 3] if alpha else [2, 1, 0]]
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32 if alpha else 24, 8 if alpha else 0)
    return header + np.ascontiguousarray(data).tobytes()


def convert_texture(fs, mi: MaterialInfo, max_texture: int = 512, keep_alpha: bool = False,
                    warnings: Optional[list[str]] = None) -> np.ndarray:
    """``$basetexture`` of a material as RGBA, tinted by ``$color``/``$color2``, resized to powers of two."""
    from PIL import Image
    rgba = None
    tex = mi.basetexture
    if tex:
        data = fs.try_read(f"materials/{tex}.vtf")
        if data is None and warnings is not None:
            warnings.append(f"{mi.name}: texture materials/{tex}.vtf not found")
        if data is not None:
            try:
                rgba = VTF(data, tex).decode()
            except Exception as e:  # noqa: BLE001
                if warnings is not None:
                    warnings.append(f"{mi.name}: cannot decode {tex}.vtf: {e}")
    elif warnings is not None:
        warnings.append(f"{mi.name}: no $basetexture (shader {mi.shader or '?'})")
    if rgba is None:
        rgba = np.full((8, 8, 4), 160, np.uint8)
        rgba[..., 3] = 255
    img = rgba.astype(np.float32)
    for key in ("$color", "$color2"):
        c = _parse_color(mi.params.get(key))
        if c is None or np.allclose(c, 1.0):
            continue
        if key == "$color2" and str(mi.params.get("$blendtintbybasealpha", "0")).strip() not in ("0", ""):
            a = img[..., 3:4] / 255.0
            img[..., :3] = img[..., :3] * (1 - a) + img[..., :3] * c * a
        else:
            img[..., :3] *= c
    rgba = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    h, w = rgba.shape[:2]
    nw, nh = _pow2_at_most(w, max_texture), _pow2_at_most(h, max_texture)
    if (nw, nh) != (w, h):
        im = Image.fromarray(rgba, "RGBA")
        im = im.resize((nw, nh), Image.LANCZOS if nw < w or nh < h else Image.BICUBIC)
        rgba = np.asarray(im, np.uint8)
    if not keep_alpha:
        rgba = rgba.copy()
        rgba[..., 3] = 255
    return rgba


@dataclass
class _Material:
    name: str                 # Source material (resolved, e.g. models/props/de_dust/dust_rusty_barrel)
    info: Optional[MaterialInfo]
    shader: str               # MOHAA shader / image name without extension
    surfaceparm: Optional[str]
    clip: str
    alphatest: bool = False
    translucent: bool = False
    additive: bool = False
    nocull: bool = False
    skip: bool = False        # tool / nodraw material
    image: str = ""           # image path written (``<shader>.tga`` or ``.jpg``)

    def __post_init__(self) -> None:
        self.image = self.image or self.shader + ".tga"


def _resolve_material(fs, info, tex_index: int, prefix: str, model_surfaceprop: str) -> _Material:
    raw = info.materials[tex_index] if 0 <= tex_index < len(info.materials) else f"missing{tex_index}"
    tex = raw.replace("\\", "/").lstrip("/")
    cands = [(cd.replace("\\", "/").strip("/") + "/" + tex).lstrip("/").lower() for cd in info.cdmaterials] or [tex.lower()]
    mi = None
    for c in cands:
        m = material_info(fs, c)
        if m.found:
            mi = m
            break
    name = mi.name if mi else cands[0]
    sp = (mi.surfaceprop if mi and mi.surfaceprop else None) or model_surfaceprop
    parm, clip = surface_type(sp)
    mat = _Material(name, mi, texture_name(name, prefix), parm, clip)
    if mi:
        mat.alphatest = mi.alphatest
        mat.translucent = mi.translucent and not mi.alphatest
        mat.additive = mi.additive
        mat.nocull = mi.nocull or mi.alphatest
        mat.skip = mi.nodraw or mi.name.startswith("tools/") or mi.shader in ("nodraw",)
    return mat


def shader_text(mat: _Material) -> str:
    img = mat.image
    lines = [mat.shader, "{", f"\tqer_editorimage {editor_image(img)}"]
    if mat.surfaceparm:
        lines.append(f"\tsurfaceparm {mat.surfaceparm}")
    if mat.nocull:
        lines.append("\tcull none")
    lines += ["\t{", f"\t\tmap {img}"]
    if mat.alphatest:
        lines += ["\t\talphaFunc GE128", "\t\tdepthWrite"]
    elif mat.additive:
        lines.append("\t\tblendFunc add")
    elif mat.translucent:
        lines.append("\t\tblendFunc blend")
    lines += ["\t\trgbGen static", "\t}", "}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Geometry


def weld(pos: np.ndarray, nrm: np.ndarray, uv: np.ndarray, tris: np.ndarray):
    """Merge vertices with identical position, normal and UV; drop degenerate triangles."""
    key = np.ascontiguousarray(np.concatenate([pos, nrm, uv], axis=1).astype(np.float32))
    _, first, inv = np.unique(key.view(np.dtype((np.void, key.dtype.itemsize * key.shape[1]))).ravel(),
                              return_index=True, return_inverse=True)
    order = np.argsort(first)            # keep the original vertex order (cache locality)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    new_idx = remap[inv.ravel()]
    keep = first[order]
    t = new_idx[tris]
    ok = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 2] != t[:, 0])
    return pos[keep], nrm[keep], uv[keep], t[ok]


def split_surface(pos, nrm, uv, tris, max_verts: int = _skd.MAX_SURFACE_VERTS,
                  max_tris: int = _skd.MAX_SURFACE_TRIS) -> list[tuple[np.ndarray, ...]]:
    """Greedy split of a triangle list into chunks under the SKD per-surface limits."""
    if len(pos) <= max_verts and len(tris) <= max_tris:
        return [(pos, nrm, uv, tris)]
    chunks = []
    local: dict[int, int] = {}
    cur: list[tuple[int, int, int]] = []

    def flush():
        if not cur:
            return
        idx = np.fromiter(local.keys(), np.int64, len(local))
        t = np.array(cur, np.int32)
        chunks.append((pos[idx], nrm[idx], uv[idx], t))
        local.clear()
        cur.clear()

    for a, b, c in tris.tolist():
        new = sum(1 for v in (a, b, c) if v not in local)
        if len(local) + new > max_verts or len(cur) + 1 > max_tris:
            flush()
        cur.append(tuple(local.setdefault(v, len(local)) for v in (a, b, c)))
    flush()
    return chunks


# ---------------------------------------------------------------------------
# Collision


def _hull_brush(points: np.ndarray, tris: np.ndarray, shader: str, min_thickness: float = 1.0) -> Optional[Brush]:
    """Convex brush from a hull's points and triangles (plane per distinct hull face).

    Hulls thinner than ``min_thickness`` (sheet-metal signs, gate bars: Source
    ships 0.4-unit pieces) are thickened along their thinnest axis by pushing each
    plane out by ``offset * |n . axis|`` (Minkowski sum with a segment), so the
    compiler gets a well-conditioned brush instead of a sliver.
    """
    pts = np.asarray(points, np.float64)
    if len(pts) < 4:
        return None
    center = pts.mean(0)
    _u, sv, vt = np.linalg.svd(pts - center, full_matrices=False)
    thin_axis = vt[-1]
    thickness = float(np.ptp(pts @ thin_axis))
    if float(np.ptp(pts @ vt[-2])) < 0.5:     # a line or a point, not a volume
        return None
    grow = max(0.0, (min_thickness - thickness) / 2)
    planes: list[tuple[np.ndarray, float, float, tuple]] = []  # normal, dist, area, points
    for a, b, c in tris.tolist():
        pa, pb, pc = pts[a], pts[b], pts[c]
        n = np.cross(pb - pa, pc - pa)
        area = float(np.linalg.norm(n))
        if area < 1e-6:
            continue
        n /= area
        d = float(n @ pa)
        if n @ center > d:          # make it point away from the hull centre
            n, d = -n, -d
            pb, pc = pc, pb
        for i, (qn, qd, qa, _q) in enumerate(planes):
            # Near-coplanar: same facing and this triangle lies on the kept plane. (Comparing
            # the two plane distances instead made the merge depend on where the origin is.)
            if qn @ n > 0.999 and max(abs(float(qn @ p) - qd) for p in (pa, pb, pc)) < 0.25:
                if area > qa:
                    planes[i] = (n, d, area, (pa, pb, pc))
                break
        else:
            planes.append((n, d, area, (pa, pb, pc)))
    if len(planes) < 4:
        return None
    # A hull plane must have every point behind it; skip anything else (non-convex input).
    good = [(n, d, ar, q) for n, d, ar, q in planes if (pts @ n - d).max() < 0.1]
    if len(good) < 4:
        return None
    faces = []
    for n, d, _ar, _q in good:
        # Each plane is written as three points 64 units apart around the projection of the
        # hull centre. Using the hull's own triangle corners (small triangles, rounded to the
        # file's precision) tilted planes by up to a degree depending on where the model sat
        # relative to its origin, and a tilted plane could then cut another face away: moving
        # the pivot changed car hulls by up to 20 units.
        if grow:
            d += grow * abs(float(n @ thin_axis))
        anchor = center - n * (float(n @ center) - d)
        ref = np.zeros(3)
        ref[int(np.argmin(np.abs(n)))] = 1.0
        u = np.cross(n, ref)
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        # Plane.from_points(a, b, c) = normalize((c - a) x (b - a)); (u x v) = n, so b = +v, c = +u.
        a, b, c = (tuple(round(float(x), 3) for x in p) for p in (anchor, anchor + 64 * v, anchor + 64 * u))
        nn = tuple(float(x) for x in n)
        pl = geom.Plane.from_points(a, b, c)
        if pl.is_degenerate() or geom.dot(pl.normal, nn) < 0.99999 or abs(pl.dist - d) > 0.01:
            a, b, c = geom.points_for_plane(nn, d)
        faces.append(Face((a, b, c), shader, (0, 0), 0, (1, 1), 0, 0, 0, ["+surfaceparm", "detail"]))
    # Drop planes that do not bound the hull (empty winding) and slivers, until stable.
    for _ in range(8):
        wins = Brush(faces).windings()
        keep = [f for f, w in zip(faces, wins) if len(w) >= 3 and geom.winding_area(w) >= 0.25]
        if len(keep) == len(faces):
            break
        faces = keep
    if len(faces) < 4 or any(len(w) < 3 for w in Brush(faces).windings()):
        return None
    return Brush(faces)


def _box_brush(mins: Sequence[float], maxs: Sequence[float], shader: str) -> Optional[Brush]:
    from ..build import Material, box
    if any(maxs[i] - mins[i] < 0.5 for i in range(3)):
        return None
    b = box(mins, maxs, Material(shader, (1, 1)), detail=True)
    return b


def collision_map(brushes: Iterable[Brush]) -> str:
    world = Entity({"classname": "worldspawn"}, list(brushes))
    return MapFile([world]).dumps()


# ---------------------------------------------------------------------------
# Conversion


def convert_model(fs, mdl_path: str, prefix: str = "csgo", skin: int = 0, scale: float = 1.0,
                  max_texture: int = 512, solid: int = 6, jpeg_quality: Optional[int] = None,
                  centre: bool = False) -> ConvertedModel:
    """Convert one Source model (``models/....mdl``) to MOHAA static-model files.

    ``fs`` reads Source files (``try_read``; see :func:`source_fs`). ``solid`` is the
    Source static-prop solidity: 6 = ``.phy`` hulls (default), 2 = MDL hull box,
    0 = no collision (writes a ``_nc`` TIKI with an empty collision map).
    Textures are TGA (32-bit only when the material uses alpha); with
    ``jpeg_quality`` opaque ones are written as JPEG instead.

    ``centre`` moves the model (and its collision) so the TIKI origin is over the centre of
    its bounds and ``LIGHT_ABOVE_TOP + 8`` above its top; ``pivot`` is where that point
    was, so place the entity at ``origin + scale * R(angles) * pivot``. A non-solid
    ``script_model`` is lit from 8 units below its origin with a single sun trace: from
    the Source pivot (on the floor) or the bounds centre (inside a car's own collision
    hull, or under a bumpy displacement floor) that trace is blocked and the whole model
    gets ambient light only. The pivot depends on the mesh alone, so the collision
    variants (``solid`` 6/2/0) still share their mesh files.
    """
    warnings: list[str] = []
    sm: StudioModel = load_studio_model(fs, mdl_path)
    info = sm.info
    if skin and not (0 <= skin < max(1, len(info.skins))):
        warnings.append(f"skin {skin} not in 0..{len(info.skins) - 1}; using 0")
        skin = 0
    directory, base = model_names(mdl_path, prefix, skin, scale)

    # --- materials and grouped geometry ---------------------------------------------
    mats: dict[int, _Material] = {}
    groups: dict[str, list] = {}
    order: list[str] = []
    for mesh in sm.meshes:
        ti = sm.material_for(mesh.skinref, skin)
        if ti not in mats:
            mats[ti] = _resolve_material(fs, info, ti, prefix, info.surfaceprop)
            if mats[ti].info is None:
                warnings.append(f"material {mats[ti].name} not found")
        mat = mats[ti]
        if mat.skip:
            continue
        if mat.shader not in groups:
            groups[mat.shader] = []
            order.append(mat.shader)
        groups[mat.shader].append((mat, mesh))

    surfaces: list[_skd.SkdSurface] = []
    bindings: list[tuple[str, str]] = []
    used: list[_Material] = []
    total_tris = 0
    for shader in order:
        items = groups[shader]
        mat = items[0][0]
        used.append(mat)
        pos, nrm, uv, tris, off = [], [], [], [], 0
        for _m, mesh in items:
            pos.append(mesh.positions)
            nrm.append(mesh.normals)
            uv.append(mesh.uvs)
            tris.append(mesh.triangles + off)
            off += len(mesh.positions)
        p = np.concatenate(pos).astype(np.float64) * scale
        n = np.concatenate(nrm).astype(np.float64)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = np.where(ln > 1e-8, n / np.maximum(ln, 1e-8), np.array([0.0, 0.0, 1.0]))
        p, n, u, t = weld(p.astype(np.float32), n.astype(np.float32), np.concatenate(uv).astype(np.float32),
                          np.concatenate(tris))
        if not len(t):
            continue
        slug = re.sub(r"[^a-z0-9_]", "_", mat.name.rpartition("/")[2].lower())[:22] or "mat"
        for cp, cn, cu, ct in split_surface(p, n, u, t):
            sname = f"{slug}_{len(surfaces):02d}"
            surfaces.append(_skd.SkdSurface(sname, cp, cn, cu, ct))
            bindings.append((sname, shader))
            total_tris += len(ct)
    if not surfaces:
        raise ValueError(f"{mdl_path}: no drawable geometry")

    allp = np.concatenate([s.positions for s in surfaces]).astype(np.float64)
    pivot = np.zeros(3)
    if centre:
        pivot = (allp.min(0) + allp.max(0)) / 2
        pivot[2] = allp[:, 2].max() + LIGHT_ABOVE_TOP + _LIGHT_BELOW_ORIGIN
        for srf in surfaces:
            srf.positions = (srf.positions.astype(np.float64) - pivot).astype(np.float32)
        allp = allp - pivot
    mins = tuple(float(x) for x in allp.min(0))
    maxs = tuple(float(x) for x in allp.max(0))

    files: dict[str, bytes] = {}
    # --- textures and shaders ------------------------------------------------------
    shaders: dict[str, str] = {}
    for mat in used:
        keep_alpha = mat.alphatest or mat.translucent or mat.additive
        if mat.info is not None:
            rgba = convert_texture(fs, mat.info, max_texture, keep_alpha, warnings)
        else:
            rgba = np.full((8, 8, 4), 160, np.uint8)
            rgba[..., 3] = 255
        if jpeg_quality and not keep_alpha:
            from PIL import Image
            buf = io.BytesIO()
            Image.fromarray(np.ascontiguousarray(rgba[..., :3])).save(buf, "JPEG", quality=int(jpeg_quality))
            mat.image = mat.shader + ".jpg"
            files[mat.image] = buf.getvalue()
        else:
            files[mat.image] = tga_bytes(rgba, keep_alpha)
        shaders[mat.shader] = shader_text(mat)

    # --- collision ------------------------------------------------------------------
    brushes: list[Brush] = []
    if solid == 6:
        phy = load_phy(fs, mdl_path)
        if phy is None:
            warnings.append("no .phy collision model; model is not solid")
        else:
            kv_props = re.findall(r'"surfaceprop"\s+"([^"]*)"', phy.keyvalues)
            if info.num_bones > 1 and len(phy.solids) > 1:
                warnings.append(f"{info.num_bones} bones / {len(phy.solids)} physics solids: solids are bone-"
                                "relative and were placed in model space (collision may be offset)")
            for si, s in enumerate(phy.solids):
                sp = kv_props[si] if si < len(kv_props) else info.surfaceprop
                kind = surface_type(sp)[1]
                cname = clip_shader_name(kind, prefix)
                for pts, tri in zip(s.pieces, s.triangles):
                    b = _hull_brush(pts * scale - pivot, tri, cname)
                    if b is None:
                        warnings.append(f"collision piece of {len(pts)} points skipped (degenerate)")
                        continue
                    brushes.append(b)
                    if not kind.startswith("common/"):
                        shaders["textures/" + cname] = clip_shader_text(kind, prefix) or ""
    elif solid == 2:
        kind = surface_type(info.surfaceprop)[1]
        cname = clip_shader_name(kind, prefix)
        hmin = [v * scale - pivot[i] for i, v in enumerate(info.hull_min)]
        hmax = [v * scale - pivot[i] for i, v in enumerate(info.hull_max)]
        b = _box_brush(hmin, hmax, cname)
        if b is not None:
            brushes.append(b)
            if not kind.startswith("common/"):
                shaders["textures/" + cname] = clip_shader_text(kind, prefix) or ""
    tik_suffix = {6: "", 2: "_bb", 0: "_nc"}.get(solid, f"_s{solid}")

    # --- SKD / SKC / TIKI (partitioned at 24 surfaces) ------------------------------
    parts = [surfaces[i : i + _skd.MAX_TIKI_SURFACES] for i in range(0, len(surfaces), _skd.MAX_TIKI_SURFACES)]
    part_bind = [bindings[i : i + _skd.MAX_TIKI_SURFACES] for i in range(0, len(bindings), _skd.MAX_TIKI_SURFACES)]
    if len(parts) > 1:
        warnings.append(f"{len(surfaces)} surfaces: partitioned into {len(parts)} TIKIs")
    tiks: list[str] = []
    for pi, (psurfs, pbind) in enumerate(zip(parts, part_bind)):
        pbase = base if pi == 0 else f"{base}_p{pi + 1}"
        pp = np.concatenate([s.positions for s in psurfs]).astype(np.float64)
        pmin, pmax = tuple(float(x) for x in pp.min(0)), tuple(float(x) for x in pp.max(0))
        files[f"{directory}/{pbase}.skd"] = _skd.build_skd(f"{pbase}.skd", psurfs)
        files[f"{directory}/{pbase}.skc"] = _skd.build_skc(pmin, pmax)
        tik = f"{directory}/{pbase}{tik_suffix}.tik"
        comment = f"converted from {normalize_path(mdl_path)} (skin {skin}) by mohkit.source.modelconv"
        files[tik] = _skd.build_tiki(directory, f"{pbase}.skd", f"{pbase}.skc", pbind, 1.0,
                                     quaked=f"static_{_flat(prefix)}_{pbase}{tik_suffix}", bounds=(pmin, pmax),
                                     comment=comment).encode("latin-1")
        tiks.append(tik)
        # Q3map loads models/<model>.map for every static model; parts after the first get an empty one.
        files[tik[:-4] + ".map"] = collision_map(brushes if pi == 0 else []).encode("latin-1")

    script = "".join(shaders[k] + "\n" for k in shaders)
    files[f"scripts/{_flat(prefix)}_{_flat(base)}{tik_suffix}.shader"] = script.encode("latin-1")
    return ConvertedModel(
        tik=tiks[0], files=files, bounds=(mins, maxs), vertices=sum(len(s.positions) for s in surfaces),
        surfaces=len(surfaces), has_collision=bool(brushes), warnings=warnings, tiks=tiks, shaders=shaders,
        materials=[m.name for m in used], triangles=total_tris, collision_brushes=len(brushes),
        source=normalize_path(mdl_path), pivot=tuple(float(x) for x in pivot))


def bundle(models: Iterable[ConvertedModel], prefix: str = "csgo", script: Optional[str] = None) -> dict[str, bytes]:
    """Merge the files of several converted models; all shaders go into one script.

    Per-model ``scripts/*.shader`` files are replaced by ``scripts/<prefix>_models.shader``
    (one definition per shader name). Raises if two models disagree on a file's bytes.
    """
    out: dict[str, bytes] = {}
    shaders: dict[str, str] = {}
    for m in models:
        for path, data in m.files.items():
            if path.startswith("scripts/") and path.endswith(".shader"):
                continue
            prev = out.get(path)
            if prev is not None and prev != data:
                raise ValueError(f"conflicting contents for {path}")
            out[path] = data
        for name, text in m.shaders.items():
            shaders.setdefault(name, text)
    if shaders:
        out[script or f"scripts/{_flat(prefix)}_models.shader"] = "".join(
            shaders[k] + "\n" for k in sorted(shaders)).encode("latin-1")
    return out
