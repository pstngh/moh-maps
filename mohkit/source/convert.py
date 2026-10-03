"""Convert a compiled CS:GO (Source, BSP v21) map into a MOHAA .map plus assets.

Works from the shipped ``.bsp`` alone (no decompiler, no VMF):

* **Brushes** come from the BSP brush list (bevel planes pruned). World and
  ``func_detail`` brushes plus static brush entities (``func_brush``,
  ``func_wall``, ``func_breakable``, ``func_illusionary``, doors) become world
  brushes; the 3D skybox (the area around ``sky_camera``) and tool volumes
  (hint, skip, areaportal, trigger, occluder, ...) are dropped; clips map to
  MOHAA clip shaders; nodraw faces become ``common/caulk``; sky faces use a sky
  shader converted from the map's ``skyname`` cubemap.
* **Texture alignment**: Source texinfo vectors (texels) are re-expressed in
  Quake 3 "old" projection terms (shift, rotate, scale on the axis-aligned base
  plane). Exact for all non-sheared mappings.
* **Displacements** become ``patchDef2`` meshes: every Source sample is kept as
  an even control point and midpoints are inserted between samples, so each
  Source cell is a bilinear quadratic span (no bowing). Rows/columns are ordered
  so the visible side (``cross(row step, column step)``) faces the air.
* **Materials** are decoded from VTF to TGA/JPG (``textures/csgo/<map>/...``)
  with a generated shader script carrying MOHAA surfaceparms (footstep/impact
  materials from ``$surfaceprop``, alpha test, translucency, two-sided).
  These files are derived from Valve's content: keep them local, never commit
  or redistribute them.
* **Entities**: T/CT/DM spawns -> axis/allied/deathmatch, ``light``/``light_spot``
  -> MOHAA lights, ``light_environment`` -> worldspawn sun/ambient.
* **Visibility**: by default every converted brush is detail and a structural
  caulk shell encloses the map. That compiles reliably (MOHAA's VIS buffer is
  2 MB) at the cost of occlusion culling.

Scale: CS player 72 u tall vs MOHAA 94 u. ``scale=1`` keeps jump/step heights
(MOHAA jump 56, step 18) close to CS; larger scales make rooms feel less cramped
but lift CS jump spots out of reach.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from .. import geom, validate
from ..build import Material, _tri_for
from ..mapfile import Brush as MBrush, Entity as MEntity, Face, MapFile, Patch, fmt
from ..shaders import editor_image
from .bsp import Brush, Contents, SourceBSP, Surf
from .vmt import MaterialInfo, material_info
from .vpk import SearchPath, ZipSource
from .vtf import VTF, load_vtf

CAULK = "common/caulk"
# Q3map chops the BSP into blocks of this size: a converted map is all detail inside one
# structural shell, so its leaves are these blocks, and MOHlight keeps at most 60 lights per
# leaf. 512 (default 1024) gave de_nuke ~500 clusters and 31 KB of VIS data.
BSP_ARGS = ("-blocksize", "512")
MAX_SHADER_NAME = 59  # "textures/..." length; Q3map duplicates the BSP shader entry of 60-character names

DROP_KINDS = {"hint", "skip", "areaportal", "occluder", "trigger", "origin", "fog", "skyfog", "blocklight", "blocklos",
              "blockbomb", "team1", "team2", "grenadeclip", "npcclip", "water", "slime", "ladder"}
KEEP_ENTITY_BRUSHES = {"func_brush", "func_wall", "func_detail", "func_breakable", "func_breakable_surf",
                       "func_illusionary", "func_door", "func_door_rotating", "func_rotating", "func_movelinear",
                       "func_wall_toggle", "func_physbox", "func_lod"}
NONSOLID_ENTITIES = {"func_illusionary"}
BREAKABLE_ENTITIES = {"func_breakable", "func_breakable_surf"}

# $surfaceprop -> MOHAA surfaceparm (footsteps, bullet impacts). "stone" is a no-op in MOHAA; use rock.
SURFACEPROP = [
    ("wood", "wood"), ("plank", "wood"), ("crate", "wood"), ("tile", "rock"), ("concrete", "rock"), ("brick", "rock"),
    ("rock", "rock"), ("stone", "rock"), ("plaster", "rock"), ("metal", "metal"), ("vent", "metal"), ("chain", "metal"),
    ("grate", "grill"), ("dirt", "dirt"), ("mud", "mud"), ("sand", "sand"), ("gravel", "gravel"), ("grass", "grass"),
    ("foliage", "foliage"), ("snow", "snow"), ("glass", "glass"), ("carpet", "carpet"), ("cloth", "carpet"),
    ("rubber", "carpet"), ("paper", "paper"), ("cardboard", "paper"), ("water", "puddle"),
]


# func_window debris: the game sends the window's debristype and the client spawns
# models/fx/windows/debris_<n>.tik (fgame/windows.cpp WindowKilled, cgame/cg_parsemsg.cpp
# CGM_MAKE_WINDOW_DEBRIS). Retail's debris_0..3 are all glass shards, so converted maps ship
# their own metal and wood debris built from retail effect models and sound aliases.
DEBRIS_GLASS, DEBRIS_METAL, DEBRIS_WOOD = 0, 7, 8
# Files every conversion ships at the same, engine-fixed path: their content must not depend
# on the map (installed pk3s sharing a path override each other, pak.path_clashes).
SHARED_PATHS = ("models/fx/windows/debris_",)


def _debris_piece(model: str, count: int, scale: float, life: str) -> str:
    return f"""\t\toriginspawn
\t\t(
\t\t\tmodel {model}
\t\t\tcount {count}
\t\t\toffset crandom 12 crandom 12 crandom 12
\t\t\tradialvelocity 2 0 64
\t\t\trandvel 0 0 32
\t\t\taccel 0 0 -800
\t\t\tfriction 0.25
\t\t\tangles crandom 90 crandom 180 crandom 180
\t\t\tavelocity 0 0 crandom 360
\t\t\tlife {life}
\t\t\tfadedelay 4
\t\t\tcollision
\t\t\tbouncefactor 0.25
\t\t\tscale {scale}
\t\t)
"""


def debris_tiki(kind: int) -> str:
    """Client effect for a broken ``func_window`` of ``debristype`` ``kind`` (metal or wood)."""
    if kind == DEBRIS_METAL:
        models = ["models/fx/metal_section.tik", "models/fx/bh_metal_fastpiece.tik"]
        body = (_debris_piece(models[0], 4, 0.35, "5 1")
                + "\t\toriginspawn\n\t\t(\n\t\t\tmodel models/fx/bh_metal_fastpiece.tik\n\t\t\tcount 12\n"
                  "\t\t\tvelocity 150\n\t\t\trandvelaxis random 150 crandom 100 crandom 100\n"
                  "\t\t\taccel 0 0 -800\n\t\t\tlife 0.1 0.4\n\t\t\tscalemin 0.8\n\t\t\tscalemax 1.4\n"
                  "\t\t\tscalerate -1.0\n\t\t)\n")
        sound = "snd_bodyfall_metal1"
    elif kind == DEBRIS_WOOD:
        models = ["models/fx/crates/crate-jib-plank.tik", "models/fx/crates/crate-jib-smallplank.tik",
                  "models/fx/crates/crate-jib-splinter.tik"]
        body = "".join(_debris_piece(m, n, 0.5, "5 1") for m, n in zip(models, (3, 4, 6)))
        sound = "snd_crate_wood"
    else:
        raise ValueError(kind)
    cache = "".join(f"\t\tcache {m}\n" for m in models)
    return ("TIKI\nsetup\n{\n\tscale 1.0\n\tpath models/fx/dummy\n\tskelmodel dummy2.skd\n}\n\ninit\n{\n"
            f"\tclient\n\t{{\n{cache}\t\tsound {sound}\n{body}\t}}\n}}\n")


def debris_type(surfaceprops) -> int:
    """``debristype`` for a breakable made of these Source ``$surfaceprop`` values."""
    sp = " ".join(x.lower() for x in surfaceprops if x)
    if "glass" in sp:
        return DEBRIS_GLASS
    if any(w in sp for w in ("wood", "plank", "crate")):
        return DEBRIS_WOOD
    return DEBRIS_METAL


@dataclass
class Options:
    name: str                       # MOHAA map name (file name), e.g. "cs_dust2"
    scale: float = 1.0
    max_texture: int = 512          # largest texture edge written
    detail_all: bool = True         # all brushes detail + structural shell (robust VIS)
    displacements: bool = True
    disp_tolerance: float = 1.0     # drop displacement sample lines within this many units of straight (0 = keep all)
    lights: bool = True
    light_min_brightness: float = 20.0   # Source _light brightness below this: dropped
    # Source texlights (lights.rad: emissive materials) -> one point light per emitting face.
    # On by default since 2026-10-01: de_nuke's Hell and B site went from dim to lit like
    # CS:GO (q3map_surfacelight had made its light estimate ~15 hours).
    texlights: bool = True
    light_merge_distance: float = 32.0   # a light this close to a brighter one is folded into it
    # world units per lightmap texel. MOHlight time is roughly proportional to the texel
    # count (de_nuke: ~1M texels at 16), so drafts use 32 (a quarter of the texels).
    lightmap_density: int = 16
    overlays: bool = True           # info_overlay decals -> flat blended patches
    # "steps": CS-style ladders, a column of invisible 16-unit clip steps you run up and can
    # leave in any direction (MOHAA's func_ladder only lets you off forward at the top, which
    # CS maps' scaffold and hole ladders don't allow). "func_ladder": MOHAA ladders.
    ladder_style: str = "steps"
    ropes: bool = True              # move_rope/keyframe_rope cables -> crossed ribbon patches
    sprites: bool = True            # env_sprite glows -> autosprite quads
    light_scale: float = 1.0
    sky_shader: Optional[str] = None  # override (e.g. "sky/mohday2"); default converts the Source sky
    texture_quality: int = 90       # JPEG quality for opaque textures
    split: float = 1024.0           # cut brushes longer than this on a world grid (renderer 64-vertex face limit)
    props: bool = True              # convert static props (mohkit.source.modelconv)
    # "inject": every prop becomes a static model added to the lit BSP and coloured from its
    # light grid (mohkit.staticlight; no MOHlight time, no entity cost), with clip brushes.
    # "compile": the largest props up to props_static_vertices are static_* entities lit by
    # MOHlight (~190 vertices/s on one thread), the next props_runtime_max are script_models.
    props_mode: str = "inject"
    props_static_vertices: int = 70000  # budget only: one unexplained crash near ~81k on full de_dust2; 161k lit fine in a small map
    props_runtime_max: int = 600    # extra props as script_model (game entities; engine limit 1024)
    # translation applied after conversion; None = centre the map when it leaves +-WORLD_LIMIT
    offset: Optional[tuple] = None
    # the 3D skybox (the area around sky_camera): "portal" keeps it as a MOHAA portal sky (the
    # room moved next to the map inside +-8192, a script_skyorigin at sky_camera, the map's sky
    # faces common/skyportal); "drop" leaves only the 2D sky
    skybox3d: str = "portal"
    # lit textures brightened (up to lighting.HEADROOM_MAX) and their light divided by the same
    # gain, so CS:GO's transferred sunlight can exceed the texture colour (lighting="csgo" only)
    headroom: bool = False
    # how much prop detail to keep (PROP_PROFILES): "full" as CS:GO; "balanced" and "stock" trade
    # small props and mesh detail for frame rate
    prop_profile: str = "full"
    # free-for-all spawns spread over the map (``mohkit.source.nav``: from the bot nav mesh,
    # with CS:GO's own deathmatch spawns first) instead of copies of the T and CT spawns
    ffa_spawns: bool = True


# mesh_lod: the CS:GO VTX LOD converted (its artists' simpler meshes: but of de_nuke's 1,378 prop
# models only 2 ship more than one LOD, so 0 everywhere); base_error: geometric detail below this
# (units) is collapsed even up close (mohkit.lod); drop / drop_nonsolid /
# foliage: props whose largest dimension (Source units) is below this are left out (all /
# without collision / foliage models); fade_cap: a fading prop vanishes by this distance at the
# latest; fade_small: non-fading props smaller than this fade at fade_cap too; lod_tau: the
# LOD curve's screen error (pixels, mohkit.lod); split_radius / split_cell: models bigger than
# split_radius are cut into pieces merged in cells of split_cell (mohkit.staticmerge)
PROP_PROFILES = {
    "full": dict(mesh_lod=0, base_error=0.01, drop=0, drop_nonsolid=0, foliage=0, fade_cap=0, fade_small=0,
                 lod_tau=2.0),
    "balanced": dict(mesh_lod=0, base_error=0.5, drop=12, drop_nonsolid=24, foliage=0, fade_cap=2048,
                     fade_small=48, lod_tau=3.0),
    # stock: 2026-10-02 de_nuke experiments (s7): shorter fades, coarser LOD, big CS:GO
    # _autocombine_ meshes cut into pieces before merging (split_radius / split_cell)
    "stock": dict(mesh_lod=0, base_error=4.0, drop=32, drop_nonsolid=64, foliage=128, fade_cap=1024,
                  fade_small=256, lod_tau=10.0, split_radius=384.0, split_cell=768.0),
    # lean: stock, plus overhead wires dropped (is_wire_model), fades capped at no less than
    # fade_size x the prop's largest dimension (landmarks stay: s9's 768 cap lost the A silo),
    # and box-like props (box_fit >= brush_box, at least brush_min units) drawn as world brushes
    # with the model's own materials, which VIS culls (static models it never does)
    "lean": dict(mesh_lod=0, base_error=4.0, drop=32, drop_nonsolid=64, foliage=128, fade_cap=1024,
                 fade_small=256, lod_tau=10.0, split_radius=384.0, split_cell=768.0, drop_wires=True,
                 fade_size=8.0, brush_box=0.8, brush_min=32.0),
}


def is_wire_model(mdl: str) -> bool:
    """Overhead wire and power-line meshes (de_nuke's ``_autocombine_wires_*``, ``wires_*``,
    ``substation_wire_system``): "wire" or "wires" as a word of the model path. 18% of
    de_nuke's prop geometry in view; the s9 build without them ran 266 / 194 fps against
    200 / 150 (csgo-conversion.md). "barbwire" on fences is not a match."""
    return bool(set(re.split(r"[_/.\\]", mdl.lower())) & {"wire", "wires"})


def box_fit(tris: np.ndarray) -> float:
    """How box-like a mesh is: the share of its triangles' area (``tris``: N x 3 x 3, model
    space) lying on the faces of its bounding box (normal within ~18 degrees of the face's,
    centroid within max(1, 3% of the largest dimension) of its plane). 1 for a crate or a
    flat fence panel, 0.5 for a pipe or barrel (its facets facing the box sides). A brush box of the model's own faces
    (``Converter._model_slab``) draws such a prop nearly as it was."""
    tris = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    if not len(tris):
        return 0.0
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(2 * area, 1e-12)[:, None]
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    tol = max(1.0, 0.03 * float((hi - lo).max()))
    c = tris.mean(1)
    on = np.zeros(len(tris), bool)
    for ax in range(3):
        on |= (n[:, ax] > 0.95) & (np.abs(c[:, ax] - hi[ax]) < tol)
        on |= (n[:, ax] < -0.95) & (np.abs(c[:, ax] - lo[ax]) < tol)
    return float(area[on].sum() / max(area.sum(), 1e-12))
FOLIAGE_WORDS = ("foliage", "bush", "shrub", "grass", "weed", "plant", "ivy", "flower", "leaves", "hedge", "vine")


@dataclass
class ConvertedMaterial:
    shader: str                     # MOHAA shader name (without textures/)
    image: Optional[str]            # pk3 path of the image
    src_size: tuple[int, int]       # Source texture size (texinfo units)
    size: tuple[int, int]           # written image size
    info: Optional[MaterialInfo] = None
    kind: str = "opaque"            # opaque | alphatest | translucent | blend | sky | tool
    gain: float = 1.0               # texture brightened by this (``lighting.headroom_gain``)
    image2: Optional[str] = None    # blend: the second layer's image (``$basetexture2``)
    blend_mod: bool = False         # blend: layer 2 alpha-tested by a $blendmodulatetexture threshold


@dataclass
class Result:
    map: MapFile
    assets: dict[str, bytes] = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    # props for mohkit.staticlight.inject: (model key, origin, angles, scale), in placement order
    statics: list = field(default_factory=list)
    # per static: CS:GO's own per-vertex prop lighting (``Converter.prop_light``) or None
    prop_light: list = field(default_factory=list)


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n)


# Quake 3 TextureAxisFromPlane base axes: (normal, s axis, t axis); first best dot wins.
BASE_AXES = [
    ((0, 0, 1), (1, 0, 0), (0, -1, 0)), ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
    ((1, 0, 0), (0, 1, 0), (0, 0, -1)), ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
    ((0, 1, 0), (1, 0, 0), (0, 0, -1)), ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
]


def texture_axis(normal) -> tuple[tuple, tuple]:
    best, bi = -1.0, 0
    for i, (n, _, _) in enumerate(BASE_AXES):
        d = geom.dot(normal, n)
        if d > best + 1e-9:
            best, bi = d, i
    return BASE_AXES[bi][1], BASE_AXES[bi][2]


def quake_texdef(normal, dist, svec, tvec) -> tuple[tuple[float, float], float, tuple[float, float]]:
    """Q3 old-style (shift, rotate, scale) reproducing ``s = svec.xyz . p + svec.w`` (in target
    texels) for points on the plane ``normal . p = dist``."""
    xv, yv = texture_axis(normal)
    sv = next(i for i in range(3) if xv[i])
    tv = next(i for i in range(3) if yv[i])
    m = 3 - sv - tv  # major axis (projection direction)
    nm = normal[m]

    def reduce(vec):
        # express vec.p + w on the plane in terms of (p[sv], p[tv])
        c1 = vec[sv] - vec[m] * normal[sv] / nm
        c2 = vec[tv] - vec[m] * normal[tv] / nm
        off = vec[3] + vec[m] * dist / nm
        return c1, c2, off

    a1, a2, s_off = reduce(svec)
    b1, b2, t_off = reduce(tvec)
    a, b = xv[sv], yv[tv]  # +/-1
    # Q3: s = a*(cos*ps + sin*pt)/scale_s + shift_s ; t = b*(-sin*ps + cos*pt)/scale_t + shift_t
    theta = math.atan2(a * a2, a * a1)
    c, s = math.cos(theta), math.sin(theta)
    proj_a = a1 * c + a2 * s  # = a / scale_s
    proj_b = -b1 * s + b2 * c  # = b / scale_t
    scale_s = a / proj_a if abs(proj_a) > 1e-9 else 1.0
    scale_t = b / proj_b if abs(proj_b) > 1e-9 else 1.0
    return (s_off, t_off), math.degrees(theta), (scale_s, scale_t)


WORLD_LIMIT = 7900.0   # Q3map skips entities and the engine clips beyond +-8192 (CLAUDE.md)


def translate_face(f: Face, T) -> Face:
    """``f`` moved by ``T`` with its texture shift corrected so every texel stays where it was
    (the Q3 projection of ``quake_texdef``: s = a (cos r p[sv] + sin r p[tv]) / scale_s + shift_s)."""
    pts = [tuple(float(p[i]) + float(T[i]) for i in range(3)) for p in f.points]
    n = geom.cross(geom.sub(f.points[2], f.points[0]), geom.sub(f.points[1], f.points[0]))
    ln = math.sqrt(geom.dot(n, n))
    shift = f.shift
    if ln > 1e-9:
        n = tuple(c / ln for c in n)
        xv, yv = texture_axis(n)
        sv = next(i for i in range(3) if xv[i])
        tv = next(i for i in range(3) if yv[i])
        a, b = xv[sv], yv[tv]
        r = math.radians(f.rotate)
        c, si = math.cos(r), math.sin(r)
        ss = f.scale[0] or 1.0
        st = f.scale[1] or 1.0
        ds = a * (c * T[sv] + si * T[tv]) / ss
        dt = b * (-si * T[sv] + c * T[tv]) / st
        shift = (round(f.shift[0] - ds, 4), round(f.shift[1] - dt, 4))
    return Face(tuple(pts), f.shader, shift, f.rotate, f.scale, f.contents, f.flags, f.value, list(f.ext))


def translate_map(m: MapFile, T) -> None:
    """Move every brush, patch and entity origin of ``m`` by ``T`` (in place), keeping
    texture alignment."""
    for e in m.entities:
        o = e.origin()
        if o is not None:
            e["origin"] = " ".join(fmt(round(o[i] + T[i], 3)) for i in range(3))
        for k, prim in enumerate(e.prims):
            if isinstance(prim, MBrush):
                e.prims[k] = MBrush([translate_face(f, T) for f in prim.faces])
            elif isinstance(prim, Patch):
                prim.ctrl = [[(c[0] + T[0], c[1] + T[1], c[2] + T[2], c[3], c[4]) for c in row] for row in prim.ctrl]


def scale_face(f: Face, k: float, c) -> Face:
    """``f`` scaled by ``k`` about ``c`` with its texture scaled too (the same texels land on
    the same spots of the smaller face): scale x k, shift + u(c) / scale (1 - 1 / k), u being
    the projection of ``translate_face``."""
    pts = [tuple(float(c[i]) + k * (float(p[i]) - float(c[i])) for i in range(3)) for p in f.points]
    n = geom.cross(geom.sub(f.points[2], f.points[0]), geom.sub(f.points[1], f.points[0]))
    ln = math.sqrt(geom.dot(n, n))
    shift, scale = f.shift, f.scale
    if ln > 1e-9:
        n = tuple(v / ln for v in n)
        xv, yv = texture_axis(n)
        sv = next(i for i in range(3) if xv[i])
        tv = next(i for i in range(3) if yv[i])
        a, b = xv[sv], yv[tv]
        r = math.radians(f.rotate)
        co, si = math.cos(r), math.sin(r)
        ss = f.scale[0] or 1.0
        st = f.scale[1] or 1.0
        us = a * (co * c[sv] + si * c[tv])
        ut = b * (-si * c[sv] + co * c[tv])
        shift = (round(f.shift[0] + us / ss * (1 - 1 / k), 4), round(f.shift[1] + ut / st * (1 - 1 / k), 4))
        scale = (ss * k, st * k)
    return Face(tuple(pts), f.shader, shift, f.rotate, scale, f.contents, f.flags, f.value, list(f.ext))


def scale_map(m: MapFile, k: float, c) -> None:
    """Scale every brush and patch of ``m`` by ``k`` about ``c`` (in place), keeping texture
    alignment (patches carry their own texture coordinates)."""
    for e in m.entities:
        for i, prim in enumerate(e.prims):
            if isinstance(prim, MBrush):
                e.prims[i] = MBrush([scale_face(f, k, c) for f in prim.faces])
            elif isinstance(prim, Patch):
                prim.ctrl = [[(c[0] + k * (q[0] - c[0]), c[1] + k * (q[1] - c[1]), c[2] + k * (q[2] - c[2]), q[3], q[4])
                              for q in row] for row in prim.ctrl]


def _snap(p, eps=0.01):
    return tuple(round(c) if abs(c - round(c)) < eps else round(c, 4) for c in p)


class Converter:
    def __init__(self, bsp_path: str, csgo_dir: str, opt: Options):
        self.opt = opt
        self.bsp = SourceBSP(bsp_path)
        self.bsp_path = Path(bsp_path)
        game = Path(csgo_dir) / "csgo" if (Path(csgo_dir) / "csgo").is_dir() else Path(csgo_dir)
        self.fs = SearchPath(ZipSource(self.bsp.pakfile()), SearchPath.for_game(game))
        self.mapname = Path(bsp_path).stem
        self.prefix = f"csgo/{opt.name}"
        self.mats: dict[str, ConvertedMaterial] = {}
        self.assets: dict[str, bytes] = {}
        self.report: dict = {"dropped": {}, "brushes": 0, "faces": 0, "patches": 0, "materials": 0, "warnings": []}
        self.sky_area = self.bsp.skybox_area()
        self.sky_box = self._sky_box()
        self.sky_shader = opt.sky_shader or self._convert_sky()
        self._portal = opt.skybox3d == "portal" and self.sky_area is not None
        self._sky_prims: list = []        # 3D skybox brushes and patches (moved in run())
        self._sky_statics: set[int] = set()   # their props' indexes in self.statics
        self._sky_whole: list = []            # the map's unsplit sky brushes and their Source sides
        self._in_sky_room = False

    def _sky_box(self):
        """Bounds (lo, hi) of the 3D skybox's leaves, or ``None`` (no sky area, or the box
        overlaps the leaves of other areas). de_cache's skybox brushes whose faces all touch
        solid, and its func_brushes, have no area of their own: the box catches them."""
        if self.sky_area is None:
            return None
        areas = self.bsp.leaf_areas
        leafs = self.bsp.leafs
        sky, rest = leafs[areas == self.sky_area], leafs[(areas != self.sky_area) & (areas != 0)]
        if not len(sky) or not len(rest):
            return None
        lo, hi = sky["mins"].min(0).astype(np.float64), sky["maxs"].max(0).astype(np.float64)
        rlo, rhi = rest["mins"].min(0), rest["maxs"].max(0)
        if np.all(lo < rhi) and np.all(rlo < hi):
            return None
        return lo, hi

    def _in_sky(self, p) -> bool:
        """``p`` (Source world units) is in the 3D skybox."""
        if self.sky_area is None:
            return False
        if self.sky_box is not None and np.all(self.sky_box[0] <= p) and np.all(np.asarray(p) <= self.sky_box[1]):
            return True
        return self.bsp.point_area(tuple(float(v) for v in p)) == self.sky_area

    # ------------------------------------------------------------------ materials
    def _shader_name(self, src: str) -> str:
        base = self.bsp.original_material(src).lower().replace("\\", "/")
        base = re.sub(r"[^a-z0-9_/]", "_", base)
        name = f"{self.prefix}/{base}"
        # EA Q3map never matches an existing BSP shader entry whose name (with "textures/")
        # is 60 characters long, so every brush side using it adds one: de_nuke overflowed
        # MAX_MAP_SHADERS (1024) with 113 shaders. 59 is safe (docs/toolchain.md).
        if len("textures/" + name) > MAX_SHADER_NAME:
            h = hashlib.md5(base.encode()).hexdigest()[:6]
            tail = base.rsplit("/", 1)[-1][: MAX_SHADER_NAME - len("textures/" + self.prefix) - 8]
            name = f"{self.prefix}/{tail}_{h}"
        return name

    def _collect_texlights(self, br: Brush, geo, xf) -> None:
        """Remember each drawn face whose material is a Source texlight (world space)."""
        table = self._texlights()
        if not hasattr(self, "_texlight_faces"):
            self._texlight_faces = []
        for side, w in geo:
            if side is None or not side.material or side.nodraw:
                continue
            key = self.bsp.original_material(side.material).lower()
            if key not in table:
                continue
            pts = [self._apply(p, xf) for p in w]
            n = self._apply_vec(side.normal, xf)
            area = geom.winding_area(pts)
            if area >= 4.0:
                self._texlight_faces.append((key, geom.winding_center(pts), n, area))

    def texlight_lights(self) -> list[MEntity]:
        """Source texlights as point lights: one ``light`` per emitting face, 8 units out along
        its normal, intensity sqrt(area x brightness) x 4 (40-600), colour from the rad line.
        (``q3map_surfacelight`` works but made de_nuke's light estimate ~15 hours.)"""
        out: list[MEntity] = []
        rad = self._texlight_colors()
        for key, c, n, area in getattr(self, "_texlight_faces", []):
            r, g, b, bright = rad[key]
            intensity = max(40.0, min(600.0, math.sqrt(area * bright) * 4.0)) * self.opt.light_scale
            mx = max(r, g, b, 1.0)
            o = tuple(c[i] + n[i] * 8 * self.opt.scale for i in range(3))
            out.append(_ent("light", o, light=fmt(round(intensity)),
                            _color=f"{r / mx:.3f} {g / mx:.3f} {b / mx:.3f}"))
        self.report["texlight_lights"] = len(out)
        return out

    def _texlight_colors(self) -> dict:
        if not hasattr(self, "_texlight_color_table"):
            table: dict = {}
            for path in ("lights.rad", f"maps/{self.mapname}.rad"):
                data = self.fs.try_read(path)
                if not data:
                    continue
                for line in data.decode("latin-1", "replace").splitlines():
                    parts = line.split("//")[0].split()
                    if len(parts) >= 5 and not parts[0].lower().startswith(("forcetextureshadow", "noshadow")):
                        try:
                            table[parts[0].lower().replace("\\", "/")] = tuple(float(x) for x in parts[1:5])
                        except ValueError:
                            continue
            self._texlight_color_table = table
        return self._texlight_color_table

    def _texlights(self) -> dict:
        """Source texlights: ``lights.rad`` (and ``maps/<map>.rad``) lines ``material r g b
        brightness``, keyed by lower-case material name."""
        if hasattr(self, "_texlight_table"):
            return self._texlight_table
        table: dict = {}
        for path in ("lights.rad", f"maps/{self.mapname}.rad"):
            data = self.fs.try_read(path)
            if not data:
                continue
            for line in data.decode("latin-1", "replace").splitlines():
                parts = line.split("//")[0].split()
                if len(parts) >= 5 and not parts[0].lower().startswith(("forcetextureshadow", "noshadow")):
                    try:
                        table[parts[0].lower().replace("\\", "/")] = float(parts[4])
                    except ValueError:
                        continue
        self._texlight_table = table
        return table

    def material(self, src: str, texdata_size: tuple[int, int]) -> ConvertedMaterial:
        key = src.lower()
        if key in self.mats:
            return self.mats[key]
        info = material_info(self.fs, self.bsp.original_material(src))
        if not info.found:
            info = material_info(self.fs, src)
        shader = self._shader_name(src)
        cm = ConvertedMaterial(shader, None, texdata_size, texdata_size, info)
        tex = info.basetexture if info.found else None
        rgba = None
        if info.found and info.is_water:
            cm.kind = "water"
            cm.image, cm.size = self._write_image(shader, self._water_image(info), True)
            self.mats[key] = cm
            return cm
        if tex:
            try:
                rgba = load_vtf(self.fs, tex).decode()
            except Exception as e:  # noqa: BLE001
                self.report["warnings"].append(f"texture {tex}: {e}")
        see = None
        if rgba is None and info.found:
            from .modelconv import see_through_image
            rgba = see = see_through_image(self.fs, info)   # refract glass: a faint tint
        if rgba is None:
            rgba = np.full((64, 64, 4), (128, 128, 128, 255), np.uint8)
            self.report["warnings"].append(f"material {src}: no texture, grey placeholder")
        # $additive: blendFunc add. As a blend, de_cache's skylight glow (effects/trainsky, a dark
        # opaque image) drew black panes over B site.
        cm.kind = "additive" if info.additive and see is None else (
            "translucent" if info.translucent or see is not None else ("alphatest" if info.alphatest else "opaque"))
        if (info.shader or "").lower() == "decalmodulate":
            cm.kind = "modulate"   # multiplies what is under it by 2 x texture (grey 128 = no change)
            # its alpha (when $translucent) says where it applies: fold it into the colour as
            # neutral grey, since the modulate blend has no alpha (black where alpha was 0)
            f = rgba[..., 3:4].astype(np.float32) / 255.0 if info.translucent else 1.0
            rgba = rgba.copy()
            rgba[..., :3] = np.clip(128.0 + (rgba[..., :3].astype(np.float32) - 128.0) * f + 0.5, 0, 255).astype(np.uint8)
        # two-layer blends (WorldVertexTransition: $basetexture2 shown by the displacement's
        # vertex alpha; Mirage's and Dust2's ground is about 65% layer 2): a second stage drawn
        # by vertex alpha, which lighting.blend_alphas fills in after the compile
        rgba2 = None
        if (cm.kind == "opaque" and info.basetexture2
                and (info.shader or "").lower() not in ("lightmapped_4wayblend", "decalmodulate")):
            try:
                rgba2 = load_vtf(self.fs, info.basetexture2).decode()
                cm.kind = "blend"
            except Exception as e:  # noqa: BLE001
                self.report["warnings"].append(f"texture {info.basetexture2}: {e}")
        if self.opt.headroom and cm.kind in ("opaque", "alphatest", "blend"):
            from .lighting import apply_gain, headroom_gain
            cm.gain = headroom_gain(rgba) if rgba2 is None else min(headroom_gain(rgba), headroom_gain(rgba2))
            rgba = apply_gain(rgba, cm.gain)
            if rgba2 is not None:
                rgba2 = apply_gain(rgba2, cm.gain)
            self._gain("textures/" + shader, cm.gain)
        cm.image, cm.size = self._write_image(shader, rgba, cm.kind not in ("opaque", "modulate", "blend"))
        if rgba2 is not None:
            # $blendmodulatetexture: CS:GO shows layer 2 where the vertex alpha passes a per-pixel
            # threshold (its green; smoothstep(g - r, g + r, alpha)), which gives de_cache's ivy
            # its edges; a linear blend washed the ivy out. Alpha-tested here: layer 2's alpha is
            # 255 / (1 + g), the vertex alpha (1 + a) / 2 (lighting.blend_alphas), so the product
            # passes 128 exactly where a >= g. (No $blendmasktransform: the base coordinates.)
            mod = info.textures.get("$blendmodulatetexture") or info.params.get("$blendmodulatetexture")
            if isinstance(mod, str) and mod:
                try:
                    from PIL import Image
                    m = load_vtf(self.fs, mod).decode()
                    g = np.asarray(Image.fromarray(np.ascontiguousarray(m[..., 1])).resize(
                        (rgba2.shape[1], rgba2.shape[0]), Image.BILINEAR), np.float32) / 255.0
                    rgba2 = rgba2.copy()
                    rgba2[..., 3] = np.clip(np.round(255.0 / (1.0 + g)), 0, 255).astype(np.uint8)
                    cm.blend_mod = True
                except Exception as e:  # noqa: BLE001
                    self.report["warnings"].append(f"blend modulate {mod}: {e}")
            # a short name: image paths must stay under MAX_QPATH (64, tr_image.c)
            h = hashlib.md5(shader.encode()).hexdigest()[:10]
            cm.image2, _ = self._write_image(f"{self.prefix}/l2_{h}", rgba2, cm.blend_mod)
            self.report.setdefault("blend", {})["textures/" + shader] = src.lower()
            if cm.blend_mod:
                self.report.setdefault("blend_mod", []).append("textures/" + shader)
        self.assets[f"scripts/{self._script_name()}"] = b""  # placeholder, written in finish()
        self.mats[key] = cm
        return cm

    def _gain(self, shader: str, gain: float) -> None:
        """Remember a lit shader's texture gain (``report["texture_gain"]``): the light on
        its surfaces is divided by it after the transfer (``lighting.transfer``)."""
        if gain > 1.0001:
            self.report.setdefault("texture_gain", {})[shader] = round(float(gain), 4)

    def _water_image(self, info: MaterialInfo) -> np.ndarray:
        """Source water has no base texture (it is drawn from refraction, reflection and fog):
        tint the normal map's relief with ``$fogcolor``, translucent by ``$waterblendfactor``."""
        from .modelconv import _parse_color
        fog = _parse_color(info.params.get("$fogcolor")) if isinstance(info.params.get("$fogcolor"), str) else None
        fog = fog if fog is not None else np.array([0.15, 0.3, 0.35], np.float32)
        try:
            alpha = float(info.params.get("$waterblendfactor", 0.75))
        except (TypeError, ValueError):
            alpha = 0.75
        relief = np.full((64, 64), 0.5, np.float32)
        nm = info.params.get("$normalmap") or info.params.get("$bumpmap")
        if isinstance(nm, str):
            try:
                n = load_vtf(self.fs, nm).decode().astype(np.float32) / 255.0
                relief = 0.5 * n[..., 0] + 0.5 * n[..., 1]
            except Exception as e:  # noqa: BLE001
                self.report["warnings"].append(f"water normal map {nm}: {e}")
        shade = 0.75 + 0.5 * (relief - relief.mean())
        rgb = np.clip(fog[None, None, :] * 1.6 * shade[..., None], 0, 1)
        out = np.empty(relief.shape + (4,), np.uint8)
        out[..., :3] = (rgb * 255).astype(np.uint8)
        out[..., 3] = int(round(255 * max(0.4, min(0.9, alpha))))
        return out

    def _write_image(self, shader: str, rgba: np.ndarray, alpha: bool) -> tuple[str, tuple[int, int]]:
        from PIL import Image
        h, w = rgba.shape[:2]
        tw, th = self._pow2(w), self._pow2(h)
        # Pillow resizes RGBA with premultiplied alpha: an opaque texture whose alpha is a
        # Source specular/envmap mask came out darkened (black where the mask was 0)
        im = Image.fromarray(rgba, "RGBA") if alpha else Image.fromarray(np.ascontiguousarray(rgba[..., :3]), "RGB")
        if (tw, th) != (w, h):
            im = im.resize((tw, th), Image.LANCZOS)
        buf = io.BytesIO()
        if alpha:
            path = f"textures/{shader}.tga"
            im.save(buf, "TGA")
        else:
            path = f"textures/{shader}.jpg"
            im.save(buf, "JPEG", quality=self.opt.texture_quality)
        self.assets[path] = buf.getvalue()
        return path, (tw, th)

    def _pow2(self, n: int) -> int:
        p = 1
        while p * 2 <= n:
            p *= 2
        return max(8, min(p, self.opt.max_texture))

    def _script_name(self) -> str:
        return f"csgo_{self.opt.name}.shader"

    def _surfaceparm(self, info: Optional[MaterialInfo]) -> Optional[str]:
        sp = (info.surfaceprop or "").lower() if info else ""
        for key, parm in SURFACEPROP:
            if key in sp:
                return parm
        return None

    def _shader_text(self, cm: ConvertedMaterial) -> str:
        lines = [f"textures/{cm.shader}", "{", f"\tqer_editorimage {editor_image(cm.image)}"]
        parm = self._surfaceparm(cm.info)
        if parm:
            lines.append(f"\tsurfaceparm {parm}")

        if cm.info and cm.info.nocull:
            lines.append("\tcull none")
        if cm.kind == "water":  # the visible face of a water volume; its other sides are common/waterskip
            lines = [f"textures/{cm.shader}", "{", f"\tqer_editorimage {editor_image(cm.image)}", "\tqer_trans .5",
                     "\tsurfaceparm water", "\tsurfaceparm trans", "\tsurfaceparm nonsolid", "\tsurfaceparm noimpact",
                     "\tsurfaceparm nolightmap", "\tsurfaceparm nomarks", "\tcull none", "\t{",
                     f"\t\tmap {cm.image}", "\t\tblendFunc blend", "\t\trgbGen identity",
                     "\t\ttcMod scroll 0.01 0.012", "\t}", "}"]
            return "\n".join(lines)
        if cm.kind == "translucent":
            lines += ["\tsurfaceparm trans", "\tsurfaceparm nolightmap", "\tcull none", "\t{",
                      f"\t\tmap {cm.image}", "\t\tblendFunc blend", "\t\trgbGen vertex", "\t}"]
        elif cm.kind == "additive":
            lines += ["\tsurfaceparm trans", "\tsurfaceparm nolightmap", "\tsurfaceparm nomarks", "\tcull none", "\t{",
                      f"\t\tmap {cm.image}", "\t\tblendFunc add", "\t\trgbGen identity", "\t}"]
        elif cm.kind == "alphatest":
            lines += ["\tsurfaceparm trans", "\tsurfaceparm alphashadow", "\tcull none", "\t{", f"\t\tmap {cm.image}",
                      "\t\talphaFunc GE128", "\t\tdepthWrite", "\tnextbundle", "\t\tmap $lightmap", "\t}"]
        elif cm.kind == "blend":   # layer 2 over layer 1 by vertex alpha (lighting.blend_alphas)
            lines += ["\t{", f"\t\tmap {cm.image}", "\tnextbundle", "\t\tmap $lightmap", "\t}",
                      "\t{", f"\t\tmap {cm.image2}", "\t\talphaFunc GE128" if cm.blend_mod else "\t\tblendFunc blend",
                      "\t\talphaGen vertex", "\tnextbundle", "\t\tmap $lightmap", "\t}"]
        else:
            lines += ["\t{", f"\t\tmap {cm.image}", "\tnextbundle", "\t\tmap $lightmap", "\t}"]
        lines.append("}")
        return "\n".join(lines)

    def _convert_sky(self) -> str:
        name = self.bsp.worldspawn.get("skyname") or ""
        if not name:
            return "sky/mohday2"
        from PIL import Image
        faces = {"rt": "rt", "bk": "bk", "lf": "lf", "ft": "ft", "up": "up", "dn": "dn"}
        written = 0
        for q3, src in faces.items():
            for suffix in ("", "_hdr"):
                # the face material names its texture ($basetexture); de_nuke's six faces all
                # use skybox/nukeblankup, and no nukeblankft.vtf exists. de_vertigo's names an
                # LDR texture it doesn't ship: its $hdrbasetexture (RGBA16161616F) is there
                info = material_info(self.fs, f"skybox/{name}{suffix}{src}")
                cands = [info.basetexture, info.params.get("$hdrcompressedtexture"),
                         info.params.get("$hdrbasetexture")] if info.found else []
                cands = [c for c in cands if isinstance(c, str) and c] + [f"skybox/{name}{suffix}{src}"]
                v = None
                for tex in cands:
                    try:
                        v = load_vtf(self.fs, tex)
                        break
                    except Exception:  # noqa: BLE001
                        continue
                if v is None:
                    continue
                rgba = v.decode()
                im = Image.fromarray(rgba, "RGBA").convert("RGB")
                # Source rotates the up/down faces relative to Quake 3.
                if q3 == "up":
                    im = im.rotate(-90)
                elif q3 == "dn":
                    im = im.rotate(90)
                size = min(512, self._pow2(max(im.size)))
                im = im.resize((size, size), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=90)
                self.assets[f"env/{self.prefix}/sky_{q3}.jpg"] = buf.getvalue()
                written += 1
                break
        if written < 6:
            self.report["warnings"].append(f"sky {name}: only {written}/6 faces found; using sky/mohday2")
            return "sky/mohday2"
        self._sky_text = "\n".join([
            f"textures/{self.prefix}/sky", "{", f"\tqer_editorimage env/{self.prefix}/sky_ft.tga",
            "\tsurfaceparm noimpact", "\tsurfaceparm nolightmap", "\tsurfaceparm sky",
            f"\tskyParms env/{self.prefix}/sky 512 -", "}"])
        return f"{self.prefix}/sky"

    # ------------------------------------------------------------------ geometry
    def _xf(self, model: int):
        """Transform for a brush model: world = R(angles) p + origin (then scale)."""
        s = self.opt.scale
        if model <= 0:
            return None
        ent = self.bsp.model_entities.get(model)
        if ent is None:
            return None
        o = ent.origin or (0.0, 0.0, 0.0)
        ang = ent.vector("angles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        return (o, ang, s)

    @staticmethod
    def _rot(ang):
        p, y, r = (math.radians(a) for a in ang)
        cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
        # Source/Quake AngleMatrix: forward, left, up columns
        return ((cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy),
                (cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy),
                (-sp, sr * cp, cr * cp))

    def _apply(self, p, xf):
        s = self.opt.scale
        if xf is None:
            return (p[0] * s, p[1] * s, p[2] * s)
        o, ang, _ = xf
        R = self._rot(ang)
        q = tuple(R[i][0] * p[0] + R[i][1] * p[1] + R[i][2] * p[2] + o[i] for i in range(3))
        return (q[0] * s, q[1] * s, q[2] * s)

    def _apply_vec(self, v, xf):
        if xf is None:
            return v
        R = self._rot(xf[1])
        return tuple(R[i][0] * v[0] + R[i][1] * v[1] + R[i][2] * v[2] for i in range(3))

    def brushes(self) -> list[MBrush]:
        out = []
        self._extra: list[MBrush] = []
        self._ladder_src: list[Brush] = []
        self._windows: dict[int, list[MBrush]] = {}
        self._invisible_models: set[int] = set()
        ents = self.bsp.model_entities
        drop = self.report["dropped"]
        for br in self.bsp.brushes(include_culled=False):
            if br.model < 0:
                continue
            nonsolid = False
            if br.model > 0:
                ent = ents.get(br.model)
                cls = ent.classname if ent else ""
                if cls not in KEEP_ENTITY_BRUSHES:
                    drop[f"entity:{cls}"] = drop.get(f"entity:{cls}", 0) + 1
                    continue
                nonsolid = cls in NONSOLID_ENTITIES
                # func_brush keys: StartDisabled 1 = not there at the start (invisible and not
                # solid; de_nuke has 32), Solidity 1 = never solid, rendermode 10 = not drawn
                if (ent.get("startdisabled") or "0") == "1":
                    # de_nuke's disabled office-light strips lit the map in VRAD only: with
                    # texlights on, their faces still become point lights (_texlight_faces)
                    if self.opt.texlights:
                        self._collect_texlights(br, br.geometry(), self._xf(br.model))
                    drop["entity:disabled"] = drop.get("entity:disabled", 0) + 1
                    continue
                if (ent.get("solidity") or "0") == "1":
                    nonsolid = True
                if (ent.get("rendermode") or "0") == "10":
                    if nonsolid:
                        drop["entity:invisible"] = drop.get("entity:invisible", 0) + 1
                        continue
                    self._invisible_models.add(br.model)
                if cls in BREAKABLE_ENTITIES:
                    # breakable glass, wall covers, boards -> MOHAA func_window (one entity per
                    # Source brush model; mirage's wall-hole covers pair a prop with one of these)
                    geo = br.geometry()
                    if len(geo) >= 4:
                        pieces = [self._brush_piece(br, pc, br.tool_kinds, False) for pc in _split_long(geo, self.opt.split)]
                        win = self._windows.setdefault(br.model, [])
                        for pc in pieces:
                            if pc is not None:
                                for f in pc.faces:
                                    f.ext = []
                                win.append(pc)
                    continue
            kinds = br.tool_kinds
            if "ladder" in kinds:
                self._ladder_src.append(br)
            water = "water" in kinds and not (kinds & (DROP_KINDS - {"water"}))
            if kinds & DROP_KINDS and not water:
                k = sorted(kinds & DROP_KINDS)[0]
                drop[k] = drop.get(k, 0) + 1
                continue
            geo = br.geometry()
            if len(geo) < 4:
                drop["degenerate"] = drop.get("degenerate", 0) + 1
                continue
            if self.sky_area is not None:
                c = np.mean([p for _, w in geo for p in w], axis=0)
                if br.model > 0:
                    c = np.array(self._apply(tuple(c), self._xf(br.model))) / self.opt.scale
                areas = self._areas(br, geo) if br.model == 0 else set()
                if (areas and areas <= {self.sky_area}) or (self.sky_box is not None and self._in_sky(c)):
                    if not self._portal:
                        drop["skybox3d"] = drop.get("skybox3d", 0) + 1
                        continue
                    self._in_sky_room = True
            if self.opt.texlights and not self._in_sky_room:
                self._collect_texlights(br, geo, self._xf(br.model))
            mb = self._brush(br, geo, kinds, nonsolid, water)
            self._in_sky_room = False
            if mb:
                out.append(mb)
                if water:
                    self.report["water_brushes"] = self.report.get("water_brushes", 0) + 1
        out += self._extra
        self.report["brushes"] = len(out)
        self._world_brushes = out
        return out

    def _world_box_solid(self, lo, hi) -> bool:
        """Does any solid converted world brush overlap the box (world units)? Brush bounds
        are a conservative test: a sloped brush may report a near miss as a hit."""
        if not hasattr(self, "_brush_boxes"):
            self._brush_boxes = [(*b.bounds(), b) for b in getattr(self, "_world_brushes", [])
                                 if not any(f.has_parm("nonsolid") for f in b.faces)]
        for blo, bhi, b in self._brush_boxes:
            if all(blo[i] < hi[i] - 0.1 and bhi[i] > lo[i] + 0.1 for i in range(3)):
                return True
        return False

    def _floor_below(self, x: float, y: float, z: float, drop: float, props: bool = False) -> Optional[float]:
        """Top of the highest solid converted brush under (x, y) between z - drop and z
        (Source units; detail brushes count, which Source's leaf contents don't), or None.
        ``props``: prop collision brushes count too (de_rats' floors are mostly furniture)."""
        s = self.opt.scale
        if not hasattr(self, "_brush_boxes"):
            self._brush_boxes = [(*b.bounds(), b) for b in getattr(self, "_world_brushes", [])
                                 if not any(f.has_parm("nonsolid") for f in b.faces)]
        boxes = self._brush_boxes
        if props:
            if not hasattr(self, "_prop_clip_boxes"):
                self._prop_clip_boxes = [(*b.bounds(), b) for b in getattr(self, "_prop_clip_brushes", [])]
            boxes = boxes + self._prop_clip_boxes
        best = None
        px, py = x * s, y * s
        for lo, hi, b in boxes:
            if not (lo[0] <= px <= hi[0] and lo[1] <= py <= hi[1] and (z - drop) * s <= hi[2] <= z * s + 1):
                continue
            top = None
            for f in b.faces:
                n, d = f.plane.normal, f.plane.dist
                if n[2] > 0.7:
                    h = (d - n[0] * px - n[1] * py) / n[2]
                    top = h if top is None else min(top, h)
            if top is not None and all(f.plane.normal[0] * px + f.plane.normal[1] * py + f.plane.normal[2] * (top - 0.5)
                                       <= f.plane.dist + 0.01 for f in b.faces):
                best = top if best is None else max(best, top)
        best = None if best is None else best / s
        for h in self._displacement_heights(x, y):
            if z - drop <= h <= z + 1 / s and (best is None or h > best):
                best = h
        return best

    def _displacement_heights(self, x: float, y: float) -> list[float]:
        """Heights of the upward-facing displacement triangles over (x, y) (Source units).
        Displacements become solid patches; de_cbble's ground in front of a ladder is one
        (4 units under the ledge the ladder stands on, more than a step from its first step)."""
        if not hasattr(self, "_disp_tris"):
            tris = []
            try:
                disps = list(self.bsp.displacements())
            except Exception:  # noqa: BLE001
                disps = []
            for d in disps:
                if d.normal[2] <= 0.3:  # walls and ceilings
                    continue
                P = np.asarray(d.positions, np.float64)
                a, b, c, e = P[:-1, :-1], P[1:, :-1], P[1:, 1:], P[:-1, 1:]
                t = np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3),
                                    np.stack([a, c, e], -2).reshape(-1, 3, 3)])
                n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
                ln = np.linalg.norm(n, axis=1)
                ok = ln > 1e-6
                t, n = t[ok], n[ok] / ln[ok, None]
                up = np.abs(n[:, 2]) > 0.7
                tris.append((t[up], n[up]))
            T = np.concatenate([t for t, _ in tris]) if tris else np.zeros((0, 3, 3))
            N = np.concatenate([n for _, n in tris]) if tris else np.zeros((0, 3))
            self._disp_tris = (T, N, T[:, :, :2].min(1), T[:, :, :2].max(1))
        T, N, lo, hi = self._disp_tris
        m = (lo[:, 0] <= x) & (x <= hi[:, 0]) & (lo[:, 1] <= y) & (y <= hi[:, 1])
        out = []
        for t, n in zip(T[m], N[m]):
            (x0, y0), (x1, y1), (x2, y2) = t[0, :2], t[1, :2], t[2, :2]
            det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(det) < 1e-9:
                continue
            l0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / det
            l1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / det
            if min(l0, l1, 1 - l0 - l1) >= -1e-6:
                out.append(float(l0 * t[0, 2] + l1 * t[1, 2] + (1 - l0 - l1) * t[2, 2]))
        return out

    def _is_glass(self, br: Brush) -> bool:
        """Every drawn material of the brush is glass (``$surfaceprop`` glass)."""
        seen = False
        for side in br.real_sides():
            m = side.material
            if not m or m.lower().startswith("tools/") or side.nodraw:
                continue
            info = material_info(self.fs, self.bsp.original_material(m))
            if not info.found:
                info = material_info(self.fs, m)
            if "glass" not in (info.surfaceprop or "").lower():
                return False
            seen = True
        return seen

    def windows(self) -> list[MEntity]:
        """Breakable glass brush entities -> ``func_window`` (MOHAA breakable glass,
        ``fgame/windows.cpp``). CS:GO panes break from one bullet; MOHAA's default health
        is 250, so they get Source's ``health`` (at least 1) and clear debris."""
        out = []
        ents = self.bsp.model_entities
        for model, brushes in sorted(self._windows.items()):
            if not brushes:
                continue
            ent = ents.get(model)
            try:
                hp = max(1, int(float(ent.get("health", "1") or 1))) if ent else 1
            except ValueError:
                hp = 1
            if any("glass" in f.shader for b in brushes for f in b.faces):
                kind = DEBRIS_GLASS
            else:
                props = {cm.shader: (cm.info.surfaceprop if cm.info else "") for cm in self.mats.values()}
                kind = debris_type(props.get(f.shader, "") for b in brushes for f in b.faces)
            out.append(MEntity({"classname": "func_window", "health": str(hp), "debristype": str(kind)}, brushes))
            self._use_debris(kind)
        self.report["windows"] = len(out)
        return out

    def _areas(self, br: Brush, geo) -> set[int]:
        out = set()
        for side, w in geo:
            c = geom.winding_center(w)
            p = (c[0] + side.normal[0], c[1] + side.normal[1], c[2] + side.normal[2])
            a = self.bsp.point_area(p)
            if a:
                out.add(a)
        return out

    def _brush(self, br: Brush, geo, kinds: set[str], nonsolid: bool, water: bool = False) -> Optional[MBrush]:
        # a sky brush of the map with a portal sky stays whole: common/skyportal faces are never
        # drawn (no 64-vertex limit), and the renderer only checks the first 32 portal-sky
        # surfaces of a frame for being on screen (tr_sky_portal.cpp R_Sky_AddSurf): de_vertigo's
        # 742 split sky brushes (1,817 surfaces) left windows showing no sky
        sky_only = (self._portal and not self._in_sky_room
                    and any(sd is not None and sd.surface_flags & Surf.SKY for sd, _ in geo)
                    and all(sd is None or sd.surface_flags & Surf.SKY or sd.nodraw or not sd.is_drawn for sd, _ in geo))
        parts = [geo] if sky_only else _split_long(geo, self.opt.split)
        pieces = [self._brush_piece(br, pc, kinds, nonsolid, water) for pc in parts]
        pieces = [p for p in pieces if p is not None]
        if sky_only and pieces:   # split after all if the room is dropped (_place_sky_room)
            self._sky_whole.append((pieces[0], br, geo, kinds, nonsolid, water))
        self._extra.extend(pieces[1:])
        if self._in_sky_room:
            self._sky_prims.extend(pieces)
        return pieces[0] if pieces else None

    def _brush_piece(self, br: Brush, geo, kinds: set[str], nonsolid: bool, water: bool = False) -> Optional[MBrush]:
        xf = self._xf(br.model)
        hidden = "common/waterskip" if water else CAULK   # caulk is solid: it would fill a water volume
        faces = []
        clip = "common/clip" if "clip" in kinds or "invisible" in kinds or br.model in self._invisible_models else (
            "common/playerclip" if "playerclip" in kinds else None)
        # the 3D skybox room keeps Source's structural brushes: sealed by them, it is a VIS region
        # of its own, so the portal sky drawn from inside it does not also draw the map (sky
        # faces don't occlude: de_dust2's buildings hung upside down in its sky)
        detail = (self.opt.detail_all and not self._in_sky_room) or br.is_detail or br.model > 0
        for side, w in geo:
            pts = [_snap(self._apply(p, xf)) for p in w]
            n = self._apply_vec(side.normal if side is not None else w.normal, xf)
            try:
                tri = _tri_for(n, pts)
            except AssertionError:
                continue
            ext = ["+surfaceparm", "detail"] if detail else []
            if nonsolid:
                ext += ["+surfaceparm", "nonsolid"]
            if clip:
                faces.append(Face(tri, clip, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            if side is None:  # cut face created by splitting a long brush
                faces.append(Face(tri, hidden, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            if side.surface_flags & (Surf.SKY | Surf.SKY2D):
                # with a portal sky the map's sky faces show the 3D skybox room (drawn from the
                # script_skyorigin), whose own sky faces draw the 2D sky
                portal = self._portal and side.surface_flags & Surf.SKY and not self._in_sky_room
                faces.append(Face(tri, "common/skyportal" if portal else self.sky_shader, (0, 0), 0, (1, 1), 0, 0, 0,
                                  list(ext)))
                continue
            if side.nodraw or not side.is_drawn or not side.material or side.material.lower().startswith("tools/"):
                faces.append(Face(tri, hidden, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            td = self.bsp.texdata[self.bsp.texinfo[side.texinfo]["texdata"]]
            cm = self.material(side.material, (int(td["width"]), int(td["height"])))
            shift, rot, scale = self._texdef(side, n, tri, cm, xf)
            faces.append(Face(tri, cm.shader, shift, rot, scale, 0, 0, 0, list(ext) + self._density(side.texinfo)))
        if len(faces) < 4:
            return None
        self.report["faces"] += len(faces)
        return MBrush(faces)

    def _density(self, texinfo: int) -> list[str]:
        """``surfaceDensity`` for a face whose Source luxels are coarser than the map's
        lightmap density (de_vertigo's facades: 128 units): MOHAA texels finer than the
        CS:GO light they carry only cost pages."""
        if texinfo < 0:
            return []
        v = self.bsp.texinfo[texinfo]["lightmap_vecs"][0][:3]
        ln = float(np.sqrt((np.asarray(v, np.float64) ** 2).sum()))
        if ln < 1e-9:
            return []
        size = 1.0 / ln * self.opt.scale
        d = self.opt.lightmap_density
        if size <= d * 1.5:
            return []
        return ["surfaceDensity", str(int(min(256, max(d, round(size)))))]

    def _texdef(self, side, n, tri, cm: ConvertedMaterial, xf):
        (sx, sy, sz, sw), (tx, ty, tz, tw) = side.texture_vecs
        ks, kt = cm.size[0] / cm.src_size[0], cm.size[1] / cm.src_size[1]
        s = self.opt.scale
        svec = [sx, sy, sz]
        tvec = [tx, ty, tz]
        if xf is not None:
            # texture vectors act on model-space points: p_model = R^T (p_world/s - o)
            o, ang, _ = xf
            R = self._rot(ang)
            svec_w = [sum(R[i][j] * svec[j] for j in range(3)) for i in range(3)]
            tvec_w = [sum(R[i][j] * tvec[j] for j in range(3)) for i in range(3)]
            sw = sw - sum(svec_w[i] * o[i] for i in range(3))
            tw = tw - sum(tvec_w[i] * o[i] for i in range(3))
            svec, tvec = svec_w, tvec_w
        sv4 = (svec[0] * ks / s, svec[1] * ks / s, svec[2] * ks / s, sw * ks)
        tv4 = (tvec[0] * kt / s, tvec[1] * kt / s, tvec[2] * kt / s, tw * kt)
        pl = geom.Plane.from_points(*tri)
        (s0, t0), rot, (scs, sct) = quake_texdef(pl.normal, pl.dist, sv4, tv4)
        s0 %= cm.size[0]
        t0 %= cm.size[1]
        return (round(s0, 3), round(t0, 3)), round(rot, 4), (round(scs, 6), round(sct, 6))

    # ------------------------------------------------------------------ overlays
    OVERLAY_DT = np.dtype([("id", "<i4"), ("texinfo", "<i2"), ("faces_order", "<u2"), ("faces", "<i4", 64),
                           ("u", "<f4", 2), ("v", "<f4", 2), ("uv", "<f4", (4, 3)), ("origin", "<f4", 3),
                           ("normal", "<f4", 3)])

    def overlays(self) -> list[Patch]:
        """``info_overlay`` decals (signs, floor markings, stains; LUMP_OVERLAYS) -> flat
        patches half a unit in front of the surface with a lightmapped blend shader (retail
        decals do the same: ``algiers/aviation_poster``).

        vbsp stores the overlay's U axis in the z of its first three UV points; V is
        normal x U, negated when the fourth point's z is 1. Corner i is ``origin + x U + y V``
        with texture coordinates (u0,v0) (u0,v1) (u1,v1) (u1,v0). Overlays that Source wraps
        across corners or displacements are placed flat on their own plane."""
        out: list[Patch] = []
        if not self.opt.overlays:
            return out
        try:
            raw = self.bsp.lump_bytes(45)
        except Exception:  # noqa: BLE001
            return out
        if not raw or len(raw) % self.OVERLAY_DT.itemsize:
            return out
        s = self.opt.scale
        skipped = 0
        self._overlay_shaders: dict[str, str] = getattr(self, "_overlay_shaders", {})
        for r in np.frombuffer(raw, self.OVERLAY_DT):
            n = np.array(r["normal"], np.float64)
            o = np.array(r["origin"], np.float64)
            uvp = np.array(r["uv"], np.float64)
            U = uvp[:3, 2].copy()
            if np.linalg.norm(n) < 0.5 or np.linalg.norm(U) < 0.5:
                skipped += 1
                continue
            n /= np.linalg.norm(n)
            U /= np.linalg.norm(U)
            V = np.cross(n, U)
            if uvp[3, 2] == 1.0:
                V = -V
            if self._in_sky(o + n * 2):
                self.report["dropped"]["skybox3d_overlay"] = self.report["dropped"].get("skybox3d_overlay", 0) + 1
                continue
            ti = int(r["texinfo"])
            mat = self.bsp.texinfo_material(ti)
            if not mat:
                skipped += 1
                continue
            td = self.bsp.texdata[self.bsp.texinfo[ti]["texdata"]]
            cm = self.material(mat, (int(td["width"]), int(td["height"])))
            shader = self._overlay_shader(cm)
            corners = [(o + x * U + y * V + n * 0.5) * s for x, y in uvp[:, :2]]
            (u0, u1), (v0, v1) = r["u"], r["v"]
            sts = [(u0, v0), (u0, v1), (u1, v1), (u1, v0)]
            c = [np.concatenate([corners[i], sts[i]]) for i in range(4)]
            # bilinear 3x3: a runs corner 0 -> 3 (rows), b runs corner 0 -> 1 (columns)
            if np.dot(np.cross(c[3][:3] - c[0][:3], c[1][:3] - c[0][:3]), n) < 0:
                c = [c[0], c[3], c[2], c[1]]
            rows = []
            for a in (0.0, 0.5, 1.0):
                row = []
                for b in (0.0, 0.5, 1.0):
                    q = (1 - a) * (1 - b) * c[0] + (1 - a) * b * c[1] + a * b * c[2] + a * (1 - b) * c[3]
                    row.append(tuple(round(float(v), 4) for v in q))
                rows.append(row)
            out.append(Patch(shader, rows))
        self.report["overlays"] = len(out)
        if skipped:
            self.report["dropped"]["overlay_bad"] = skipped
        return out

    def _overlay_shader(self, cm: ConvertedMaterial) -> str:
        """A decal version of a converted material: non-solid, blended over the surface behind
        (when the image has alpha) and lightmapped; ``polygonOffset`` against z-fighting."""
        tail = cm.shader.rsplit("/", 1)[-1]
        name = f"{self.prefix}/ov_{tail}"
        if len("textures/" + name) > MAX_SHADER_NAME:
            h = hashlib.md5(cm.shader.encode()).hexdigest()[:6]
            name = f"{self.prefix}/ov_{tail[: MAX_SHADER_NAME - len('textures/' + self.prefix) - 11]}_{h}"
        if name not in self._overlay_shaders:
            alpha = cm.image is not None and cm.image.endswith(".tga")
            lines = [f"textures/{name}", "{", f"\tqer_editorimage {editor_image(cm.image)}", "\tsurfaceparm trans",
                     "\tsurfaceparm nonsolid", "\tsurfaceparm nomarks", "\tpolygonOffset", "\t{", f"\t\tmap {cm.image}"]
            if cm.kind == "additive":
                lines += ["\t\tblendFunc add", "\t\trgbGen identity", "\t}", "}"]
                self._overlay_shaders[name] = "\n".join(lines)
                return name
            if cm.kind == "modulate":
                # Source DecalModulate (cracks, grime): dst * 2 * src, lit by the surface below
                lines += ["\t\tblendFunc GL_DST_COLOR GL_SRC_COLOR", "\t\trgbGen identity", "\t}", "}"]
                self._overlay_shaders[name] = "\n".join(lines)
                return name
            if alpha:
                lines.append("\t\tblendFunc blend")
            lines += ["\tnextbundle", "\t\tmap $lightmap", "\t}", "}"]
            self._overlay_shaders[name] = "\n".join(lines)
            self._gain("textures/" + name, cm.gain)
        return name

    # ------------------------------------------------------------------ ropes
    def ropes(self) -> list[Patch]:
        """Cables and power lines (``move_rope`` -> ``keyframe_rope`` chains via ``NextKey``)
        -> two crossed ribbon patches per segment, ``Width`` wide, hanging in a parabola:
        a rope ``Slack`` units longer than the span D sags by about sqrt(3 D Slack / 8), and a
        3-column patch row is a quadratic Bezier, so the parabola is exact. Each segment uses
        the width, slack and material of the entity it starts from."""
        out: list[Patch] = []
        if not self.opt.ropes:
            return out
        s = self.opt.scale
        by_name = {}
        for e in self.bsp.find_entities("keyframe_rope"):
            if e.get("targetname") and e.origin is not None:
                by_name.setdefault(e.get("targetname").lower(), e)
        up = np.array([0.0, 0.0, 1.0])
        for e in self.bsp.find_entities("move_rope") + self.bsp.find_entities("keyframe_rope"):
            nxt = by_name.get((e.get("nextkey") or "").lower())
            if nxt is None or e.origin is None:
                continue
            a = np.array(e.origin, np.float64)
            b = np.array(nxt.origin, np.float64)
            if self._in_sky((a + b) / 2):
                continue
            try:
                width = max(0.5, float(e.get("width", "2") or 2))
                slack = max(0.0, float(e.get("slack", "25") or 25))
            except ValueError:
                width, slack = 2.0, 25.0
            span = float(np.linalg.norm(b - a))
            if span < 1.0:
                continue
            sag = math.sqrt(3.0 * span * slack / 8.0)
            mid = (a + b) / 2 - up * 2 * sag            # Bezier control point: the curve's middle sags by `sag`
            mat = (e.get("ropematerial") or "cable/cable").replace(".vmt", "")
            cm = self.material(mat, (64, 64))
            shader = self._rope_shader(cm)
            t = (b - a) / span
            side = np.cross(t, up)
            side = side / np.linalg.norm(side) if np.linalg.norm(side) > 1e-6 else np.array([1.0, 0.0, 0.0])
            vert = np.cross(side, t)
            length = span + slack
            smax = length / max(8.0 * width, 1.0)
            for d in (side, vert):
                rows = []
                for k, off in enumerate((-0.5, 0.0, 0.5)):
                    row = []
                    for j, p in enumerate((a, mid, b)):
                        q = (p + d * off * width) * s
                        row.append((round(float(q[0]), 3), round(float(q[1]), 3), round(float(q[2]), 3),
                                    round(smax * j / 2, 4), round(off + 0.5, 4)))
                    rows.append(row)
                out.append(Patch(shader, rows))
        self.report["ropes"] = len(out) // 2
        return out

    def _rope_shader(self, cm: ConvertedMaterial) -> str:
        """Non-solid, two-sided, lightmapped version of a converted material (alpha-tested
        when the image has alpha)."""
        tail = cm.shader.rsplit("/", 1)[-1]
        name = f"{self.prefix}/rope_{tail}"
        if len("textures/" + name) > MAX_SHADER_NAME:
            h = hashlib.md5(cm.shader.encode()).hexdigest()[:6]
            name = f"{self.prefix}/rope_{tail[: MAX_SHADER_NAME - len('textures/' + self.prefix) - 13]}_{h}"
        self._overlay_shaders = getattr(self, "_overlay_shaders", {})
        if name not in self._overlay_shaders:
            alpha = cm.image is not None and cm.image.endswith(".tga")
            lines = [f"textures/{name}", "{", f"\tqer_editorimage {editor_image(cm.image)}", "\tsurfaceparm nonsolid",
                     "\tsurfaceparm nomarks", "\tsurfaceparm trans", "\tcull none", "\t{", f"\t\tmap {cm.image}"]
            if alpha:
                lines += ["\t\talphaFunc GE128", "\t\tdepthWrite"]
            lines += ["\tnextbundle", "\t\tmap $lightmap", "\t}", "}"]
            self._overlay_shaders[name] = "\n".join(lines)
            self._gain("textures/" + name, cm.gain)
        return name

    # ------------------------------------------------------------------ sprites
    def sprites(self) -> list[MBrush]:
        """``env_sprite`` glows (lamp halos) -> a floating quad facing the viewer: a thin
        ``common/nodraw`` brush whose one visible face has an additive ``deformVertexes
        autosprite`` shader (a quad, so autosprite applies; docs/reference/engine.md).
        ``rendercolor`` x ``renderamt`` is baked into the image; the quad is 0.75 x the
        texture size x ``scale`` units wide (8-96)."""
        out: list[MBrush] = []
        if not self.opt.sprites:
            return out
        from ..build import box
        s = self.opt.scale
        self._overlay_shaders = getattr(self, "_overlay_shaders", {})
        cache: dict = {}
        for e in self.bsp.find_entities("env_sprite"):
            o = e.origin
            mat = (e.get("model") or "").replace("\\", "/")
            if o is None or not mat.endswith(".vmt"):
                continue          # .spr / .vtf sprites: rare in CS:GO maps
            if self._in_sky(o):
                continue
            try:
                col = [float(x) / 255 for x in (e.get("rendercolor") or "255 255 255").split()[:3]]
                amt = float(e.get("renderamt", "255") or 255) / 255
                scale = float(e.get("scale", "1") or 1)
            except ValueError:
                continue
            key = (mat.lower(), tuple(round(c * amt, 2) for c in col))
            if key not in cache:
                info = material_info(self.fs, mat[:-4])
                tex = info.basetexture if info.found else None
                try:
                    rgba = load_vtf(self.fs, tex).decode() if tex else None
                except Exception:  # noqa: BLE001
                    rgba = None
                if rgba is None:
                    cache[key] = None
                    continue
                img = rgba[..., :3].astype(np.float32)
                if info.params.get("$translucent") or rgba[..., 3].min() < 250:
                    img *= rgba[..., 3:4].astype(np.float32) / 255.0
                img = np.clip(img * np.array(key[1], np.float32), 0, 255).astype(np.uint8)
                h = hashlib.md5(repr(key).encode()).hexdigest()[:6]
                name = f"{self.prefix}/spr_{Path(tex).name[:20]}_{h}"
                full = np.concatenate([img, np.full(img.shape[:2] + (1,), 255, np.uint8)], axis=2)
                image, _size = self._write_image(name, full, False)
                self._overlay_shaders[name] = "\n".join([
                    f"textures/{name}", "{", f"\tqer_editorimage {editor_image(image)}", "\tsurfaceparm nonsolid",
                    "\tsurfaceparm trans", "\tsurfaceparm nolightmap", "\tsurfaceparm nomarks",
                    "\tdeformVertexes autosprite", "\tcull none", "\t{", f"\t\tmap {image}", "\t\tblendFunc add",
                    "\t\trgbGen identity", "\t}", "}"])
                cache[key] = (name, rgba.shape[1])
            if cache[key] is None:
                continue
            name, width = cache[key]
            half = max(4.0, min(48.0, width * scale * 0.75 / 2)) * s
            c = [v * s for v in o]
            spec = {"east": Material(name, (1, 1)), "default": Material("common/nodraw", (1, 1))}
            b = box((c[0] - 0.5, c[1] - half, c[2] - half), (c[0] + 0.5, c[1] + half, c[2] + half), spec, detail=True)
            for f in b.faces:
                if f.shader == name:
                    # fit the image to the quad: an east face projects s = y / scale + shift and
                    # t = -z / scale + shift (Q3 base axes), so the glow is centred and whole
                    sc = 2 * half / width
                    f.scale = (round(sc, 6), round(sc, 6))
                    f.shift = (round((-(c[1] - half) / sc) % width, 3), round(((c[2] + half) / sc) % width, 3))
            out.append(b)
        self.report["sprites"] = len(out)
        return out

    # ------------------------------------------------------------------ breakable props
    def breakables(self) -> list[MEntity]:
        """Solid interactive props (``_entity_props`` skips them: de_nuke's vent slats, opened
        by a button or broken by shooting, and its breakable vent cover) -> ``func_window``:
        a slab of the model (``_model_slab``) that blocks the opening until it is shot.
        Shooting it open spawns metal or wood debris (``debris_tiki``); CS players open these
        vents the same way."""
        out: list[MEntity] = []
        for e in getattr(self, "_interactive_props", []):
            if (e.get("solid") or "6") == "0" or e.origin is None:
                continue
            if not any(k.lower() == "onbreak" for k, _ in e.items()):
                continue      # enabled/animated later (a broken shutter's remains): left out
            ang = e.vector("angles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            slab = self._model_slab(e, e.get("model"), e.origin, ang)
            if slab is None:
                continue
            try:
                hp = max(1, int(float(e.get("health", "25") or 25)))
            except ValueError:
                hp = 25
            kind = debris_type([slab[5].info.surfaceprop or "", e.get("model")])
            out.append(MEntity({"classname": "func_window", "health": str(hp), "debristype": str(kind)}, [slab[0]]))
            self._use_debris(kind)
        self.report["breakables"] = len(out)
        return out

    def _use_debris(self, kind: int) -> None:
        """Ship the debris effect of a ``func_window`` debristype that retail lacks."""
        if kind != DEBRIS_GLASS:
            self.assets[f"models/fx/windows/debris_{kind}.tik"] = debris_tiki(kind).encode()
            self.report.setdefault("debris", {})
            self.report["debris"][kind] = self.report["debris"].get(kind, 0) + 1

    # ------------------------------------------------------------------ doors
    def _model_slab(self, e, mdl: str, o, ang, hull_align: bool = True):
        """A brush slab spanning a model's two largest opposite faces, in world space, its
        faces textured with the model's own material (each face's texdef reproduces the UVs
        of the largest mesh triangle on it). Returns (brush, lo, hi, R, origin, studiomodel)
        with lo/hi in hull-aligned model space, or None."""
        from .modelconv import _resolve_material, load_studio_model
        s = self.opt.scale
        try:
            sm = load_studio_model(self.fs, mdl)
        except Exception as ex:  # noqa: BLE001
            self.report["warnings"].append(f"model slab {mdl}: {ex}")
            return None
        skin = int(float(e.get("skin", "0") or 0))
        P, UV, M, names = [], [], [], []
        for mesh in sm.meshes:
            mat = _resolve_material(self.fs, sm.info, sm.material_for(mesh.skinref, skin), "csgo",
                                    sm.info.surfaceprop)
            if mat.skip or not len(mesh.triangles):
                continue
            if mat.name not in names:
                names.append(mat.name)
            t = mesh.triangles
            P.append(mesh.positions[t].astype(np.float64))
            UV.append(mesh.uvs[t].astype(np.float64))
            M.append(np.full(len(t), names.index(mat.name)))
        if not P:
            return None
        P, UV, M = np.concatenate(P), np.concatenate(UV), np.concatenate(M)
        # Door models carry a rotated root bone: the mesh can lie 90 degrees off the frame
        # the entity angles apply to (metal_door_001_br: mesh along +x, hull and the
        # double-door frames along +y). Turn the mesh so its bounds match the MDL hull.
        if hull_align:
            P = P @ _yaw_to_hull(P.reshape(-1, 3), sm.info.hull_min, sm.info.hull_max).T
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        area = np.linalg.norm(nrm, axis=1) / 2
        nrm = nrm / np.maximum(2 * area, 1e-9)[:, None]
        best = None
        for ax in range(3):
            plus, minus = nrm[:, ax] > 0.95, nrm[:, ax] < -0.95
            score = min(area[plus].sum(), area[minus].sum())
            if best is None or score > best[0]:
                best = (score, ax, plus, minus)
        _, ax, plus, minus = best
        if not plus.any() or not minus.any():
            return None
        lo = P[plus | minus].reshape(-1, 3).min(0)
        hi = P[plus | minus].reshape(-1, 3).max(0)
        lo[ax] = float(np.median(P[minus][:, :, ax]))
        hi[ax] = float(np.median(P[plus][:, :, ax]))
        if hi[ax] - lo[ax] < 1.0:
            c = (hi[ax] + lo[ax]) / 2
            lo[ax], hi[ax] = c - 0.5, c + 0.5
        R = np.array(self._rot(ang))
        ow = np.array(o, np.float64)
        faces = []
        for fax in range(3):
            for sgn in (-1, 1):
                n = np.zeros(3)
                n[fax] = sgn
                sel = (nrm @ n) > 0.9
                pick = int(np.argmax(np.where(sel, area, -1.0))) if sel.any() else int(np.argmax(np.where(plus, area, -1.0)))
                mname = names[int(M[pick])]
                cm = self.material(mname, (256, 256))
                w, h = cm.size
                # texture vectors (texels of the written image) of the picked triangle, in plane
                tn = np.cross(P[pick, 1] - P[pick, 0], P[pick, 2] - P[pick, 0])
                tn /= max(np.linalg.norm(tn), 1e-9)
                A = np.vstack([np.hstack([P[pick], np.ones((3, 1))]), np.append(tn, 0.0)])
                try:
                    sv = np.linalg.solve(A, np.append(UV[pick, :, 0] * w, 0.0))
                    tv = np.linalg.solve(A, np.append(UV[pick, :, 1] * h, 0.0))
                except np.linalg.LinAlgError:
                    sv, tv = np.array([1.0, 0, 0, 0]), np.array([0, 0, 1.0, 0])
                # to world space: S_w = R S / s, offset - (R S) . o
                svw, tvw = R @ sv[:3], R @ tv[:3]
                sv4 = (*(svw / s), sv[3] - svw @ ow)
                tv4 = (*(tvw / s), tv[3] - tvw @ ow)
                corners = []
                for a in (0, 1):
                    for b in (0, 1):
                        q = lo.copy() if sgn < 0 else hi.copy()
                        q[fax] = lo[fax] if sgn < 0 else hi[fax]
                        u_ax, v_ax = [i for i in range(3) if i != fax]
                        q[u_ax] = (lo, hi)[a][u_ax]
                        q[v_ax] = (lo, hi)[b][v_ax]
                        corners.append(tuple(float(x) for x in (R @ q + ow) * s))
                nw = R @ n
                tri = _tri_for(tuple(nw), [_snap(c) for c in corners])
                pl = geom.Plane.from_points(*tri)
                (s0, t0), rot, (scs, sct) = quake_texdef(pl.normal, pl.dist, sv4, tv4)
                faces.append(Face(tri, cm.shader, (round(s0 % w, 3), round(t0 % h, 3)), round(rot, 4),
                                  (round(scs, 6), round(sct, 6)), 0, 0, 0, []))
        return MBrush(faces), lo, hi, R, ow, sm

    def doors(self) -> list[MEntity]:
        """``prop_door_rotating`` -> ``func_rotatingdoor``: a brush slab spanning the door
        model's two largest opposite faces, textured with the model's own material (the
        texdef of each brush face reproduces the UVs of the largest mesh triangle on it),
        with an origin brush on the hinge (the model origin). Handles and other relief are
        lost. MOHAA opens it for players and bots that walk into it (``alwaysaway`` for
        Source's two-way doors); double doors link because their brushes touch."""
        from .modelconv import _resolve_material, load_studio_model
        out: list[MEntity] = []
        s = self.opt.scale
        for e in self.bsp.find_entities("prop_door_rotating"):
            mdl, o = e.get("model"), e.origin
            if not mdl or o is None:
                continue
            ang = e.vector("angles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            slab = self._model_slab(e, mdl, o, ang)
            if slab is None:
                continue
            brush, lo, hi, R, ow, sm = slab
            from ..build import box
            hinge = np.array([0.0, 0.0, (lo[2] + hi[2]) / 2])
            hw = (R @ hinge + ow) * s
            origin = box(tuple(hw - 2), tuple(hw + 2), "common/origin")
            mid = R @ ((lo + hi) / 2 * np.array([1, 1, 0]))
            yaw = round(math.degrees(math.atan2(mid[1], mid[0]))) % 360
            try:
                dist = float(e.get("distance", "90") or 90)
                speed = float(e.get("speed", "100") or 100)
            except ValueError:
                dist, speed = 90.0, 100.0
            keys = {"classname": "func_rotatingdoor", "angle": str(yaw), "openangle": fmt(round(dist)),
                    "time": fmt(round(max(0.2, dist / max(speed, 1.0)), 2)), "wait": "-1" if e.get("returndelay") == "-1" else "3",
                    "doortype": "metal" if "metal" in (sm.info.surfaceprop or "").lower() + mdl.lower() else "wood"}
            if e.get("opendir", "0") == "0":
                keys["alwaysaway"] = "1"
            out.append(MEntity(keys, [brush, origin]))
        self.report["doors"] = len(out)
        return out

    # ------------------------------------------------------------------ ladders
    def _solid(self, p) -> bool:
        """Source world contents at ``p`` (Source units) are solid."""
        return bool(int(self.bsp.leafs[self.bsp.point_leaf(p)]["contents"]) & Contents.SOLID)

    def _ladder_solid(self, p) -> bool:
        """Solid at ``p`` (Source units) for a player: Source world contents, or a converted
        world brush (detail and clip brushes, which Source's leaf contents leave out)."""
        if self._solid(p):
            return True
        q = np.asarray(p, dtype=np.float64) * self.opt.scale
        return self._world_box_solid(tuple(q - 0.5), tuple(q + 0.5))

    def _ladder_boxes(self) -> list:
        """Source ladder volumes as [lo, hi] boxes (Source units), stacked pieces merged."""
        if hasattr(self, "_ladder_box_cache"):
            return self._ladder_box_cache
        boxes = []
        for br in getattr(self, "_ladder_src", []):
            if br.model != 0:  # brush-entity ladders are in model space; Source compiles func_ladder into the world
                self.report["warnings"].append(f"ladder brush {br.index} in model {br.model} skipped")
                continue
            pts = np.array([p for w in br.windings() for p in w], dtype=np.float64)
            if len(pts) < 4:
                continue
            boxes.append([pts.min(0), pts.max(0)])
        boxes.sort(key=lambda b: (round(b[0][0]), round(b[0][1]), b[0][2]))
        self._ladder_box_cache = merge_ladder_boxes(boxes)
        return self._ladder_box_cache

    def ladders(self) -> list[MEntity]:
        """Source ladder volumes (``CONTENTS_LADDER`` brushes) -> step columns
        (``Options.ladder_style`` "steps", ``_ladder_steps``: world brushes in
        ``self._ladder_step_brushes``, no entity) or MOHAA ``func_ladder``s.

        MOHAA climbs a ``func_ladder`` whose ``origin`` is on the climbable face, centred
        horizontally, with ``angle`` = the direction the climber faces (into the wall); the
        player is held at ``origin - facing * 16`` (docs/reference/engine.md §1.3). The wall
        side is the side of the Source volume with solid world contents behind it, else the
        side a static prop (the visible ladder or its wall supports) is on. Stacked volumes
        of one ladder are merged. The trigger brush covers the Source volume plus 8 units
        on the climber's side.
        """
        s = self.opt.scale
        merged = self._ladder_boxes()
        self._ladder_mount_boxes: list = []
        self._ladder_step_brushes: list = []
        props = None
        out: list[MEntity] = []
        for lo, hi in merged:
            ext = hi - lo
            c = (lo + hi) / 2
            # the climb face is perpendicular to the thin axis; a square volume tries both axes
            # (mirage's leaning ladder is 32.0001 x 32: float noise picked the wrong one, facing
            # a wall 44 units away instead of the ledge it leads to). A near-square one takes
            # the other axis only when it has clearly more wall (a de_vertigo ladder is 26.7
            # deep and 24 wide, its wall on a 24-unit side; a 22 x 17.6 de_rats shaft ladder
            # climbs fine facing its 22-unit side, with about as much wall on both axes).
            thin_first = 0 if ext[0] < ext[1] else 1
            square = abs(ext[0] - ext[1]) < 2
            axes = [0, 1] if square or min(ext[0], ext[1]) > 0.75 * max(ext[0], ext[1]) else [thin_first]
            walls = {}
            for ax in axes:
                for sgn in (-1, 1):
                    hits = 0
                    for d in (2, 4, 8, 12, 16, 24, 32, 48, 64):
                        for z in np.linspace(lo[2] + 4, hi[2] - 4, 5):
                            p = c.copy()
                            p[2] = z
                            p[ax] = (hi[ax] if sgn > 0 else lo[ax]) + sgn * d
                            hits += self._ladder_solid(p)
                    walls[(ax, sgn)] = hits
            best = max(walls.values())
            thin = max((k for k in walls if walls[k] == best), key=lambda k: (k[0] == axes[0], k[1]))[0]
            if len(axes) == 2 and not square and thin != thin_first:
                own = max(walls[(thin_first, -1)], walls[(thin_first, 1)])
                if best < 1.5 * own:
                    thin = thin_first
            wide = 1 - thin
            score = {sgn: walls[(thin, sgn)] for sgn in (-1, 1)}
            how = "solid"
            if score[1] == score[-1]:
                how = "props"
                if props is None:
                    try:
                        props = [(np.array(p.origin, dtype=np.float64)) for p in self.bsp.static_props().props]
                    except Exception:  # noqa: BLE001
                        props = []
                for sgn in (-1, 1):
                    face = hi[thin] if sgn > 0 else lo[thin]
                    score[sgn] = sum(1 for o in props
                                     if lo[wide] - 8 <= o[wide] <= hi[wide] + 8 and lo[2] - 16 <= o[2] <= hi[2] + 16
                                     and 0 <= (o[thin] - face) * sgn <= 24)
                if score[1] == score[-1]:
                    how = "default"
            sgn = 1 if score[1] >= score[-1] else -1     # facing: toward the wall
            facing = [0.0, 0.0, 0.0]
            facing[thin] = float(sgn)
            near = lo[thin] if sgn > 0 else hi[thin]     # the climber's side of the Source volume
            far = hi[thin] if sgn > 0 else lo[thin]
            # trigger: Source volume + 8 units toward the climber. A ladder that hangs 32+
            # units above where you stand (de_nuke's A-site one, 47 over a ledge with a gap
            # under it; CS players jump to it) is extended down to that floor: mounting puts
            # the player at absmin + 2 (FuncLadder::PositionOnLadder, fgame/misc.cpp), in mid-air
            # otherwise, and the move there is blocked. Ladders that start lower are left alone:
            # extending one 23 units stopped it from mounting.
            t_lo, t_hi = lo.copy(), hi.copy()
            floors = []
            for back in (16, 28, 40):
                foot = c.copy()
                foot[thin] = (lo[thin] if sgn > 0 else hi[thin]) - sgn * back
                f = self._floor_below(foot[0], foot[1], lo[2], 96)
                if f is not None:
                    floors.append(f)
            if floors and max(floors) < lo[2] - 32:
                t_lo[2] = max(floors) + 1
            if self.opt.ladder_style == "steps":
                z0 = lo[2]
                if floors and max(floors) >= lo[2] - 96:
                    # from the lowest floor a step or two under the highest: the climber may
                    # stand lower than the ledge the ladder rises from (de_cbble: displacement
                    # ground 4 units down, so the first step was 20 up, over STEPSIZE 18)
                    z0 = min(f for f in floors if f >= max(floors) - 32)
                front = self._ladder_steps(lo, hi, thin, sgn, far, z0)
                org = c.copy()
                org[thin] = front
                yaw = round(math.degrees(math.atan2(facing[1], facing[0]))) % 360
                rec = {"origin": [round(float(v) * s, 1) for v in org], "angle": yaw, "height": round(float(hi[2] - z0) * s),
                       "zmin": round(float(z0) * s, 1), "zmax": round(float(hi[2]) * s, 1), "style": "steps",
                       "facing_from": how, "wall_side": [score[-1], score[1]], "far": round(float(far) * s, 1)}
                # a ladder hanging over the floor in front, more than a jump (56) below its first
                # step, is climbed down or caught from a jump, as in CS:GO (de_vertigo's hatch
                # ladder hangs 135 up; a CS:GO player reaches 72 + 57). game.ladder_probe starts
                # such a ladder in the air right at the column, which a player steps onto.
                deep = []
                for back in (16, 28, 40):   # a narrow ledge counts (a de_rats shaft ladder)
                    foot = c.copy()
                    foot[thin] = near - sgn * back
                    f = self._floor_below(foot[0], foot[1], z0, 2048, props=True)
                    if f is not None:
                        deep.append(f)
                if deep and z0 - max(deep) > 2:
                    rec["hang"] = round(float(z0 - max(deep)) * s, 1)
                start = self._probe_start(org * s, np.array(facing), wide, (hi[wide] - lo[wide]) * s / 2, z0 * s,
                                          backs=(16.0, 22.0, 28.0) if rec.get("hang", 0) > 40 else (28.0, 22.0, 16.0, 36.0))
                if start is not None:
                    rec["probe_start"] = start
                self.report.setdefault("ladders", []).append(rec)
                continue
            if sgn > 0:
                t_lo[thin] = near - 8
            else:
                t_hi[thin] = near + 8
            org = c.copy()
            org[thin] = near
            if ext[thin] > 28:
                # a deep volume (mirage's leaning ladder: 32, the ledge at its far side): climb
                # 8 units off the far face, or the top dismount (CondCanGetOffLadderTop and the
                # get-off animation) ends short of the ledge and the player falls
                org[thin] = far - sgn * 8
            # FuncLadder::CanUseLadder refuses when a player box at origin - facing * 29,
            # absmin + 16 is in solid (mirage's leaning ladder: a Source clip ledge filled it):
            # slide the origin along the ladder's width to the first clear spot
            half_w = (hi[wide] - lo[wide]) / 2
            for off in [0.0] + [d * sgn2 for d in (4.0, 8.0, 12.0, 16.0) if d < half_w for sgn2 in (-1.0, 1.0)]:
                trial = org.copy()
                trial[wide] = c[wide] + off
                mc = (trial - np.array(facing) * 29) * s
                if not self._world_box_solid((mc[0] - 15, mc[1] - 15, t_lo[2] * s), (mc[0] + 15, mc[1] + 15, t_lo[2] * s + 16 + 94)):
                    if off:
                        self.report["warnings"].append(f"ladder at {[round(float(v)) for v in c]}: origin moved {off:+g} along its width (mount box clear)")
                    org = trial
                    break
            o_lo, o_hi = org - 1, org + 1
            from ..build import box
            # where FuncLadder::CanUseLadder box-traces the player (origin - facing * 29, from
            # absmin + 16 down 16, player size): prop collision there blocks mounting
            mc = (org - np.array(facing) * 29) * s
            self._ladder_mount_boxes.append(((mc[0] - 16, mc[1] - 16, t_lo[2] * s), (mc[0] + 16, mc[1] + 16, t_lo[2] * s + 16 + 96)))
            trig = box(tuple(t_lo * s), tuple(t_hi * s), "common/trigger")
            obr = box(tuple(o_lo * s), tuple(o_hi * s), "common/origin")
            yaw = round(math.degrees(math.atan2(facing[1], facing[0]))) % 360
            e = MEntity({"classname": "func_ladder", "angle": str(yaw)}, [trig, obr])
            out.append(e)
            self.report.setdefault("ladders", []).append(
                {"origin": [round(float(v) * s, 1) for v in org], "angle": yaw, "height": round(float(ext[2]) * s),
                 "extended_down": round(float(lo[2] - t_lo[2]) * s, 1),
                 "facing_from": how, "wall_side": [score[-1], score[1]], "far": round(float(far) * s, 1)})
        return out

    def _probe_start(self, front, facing, wide: int, half_w: float, z0: float, backs=(28.0, 22.0, 16.0, 36.0)):
        """Where ``game.ladder_probe`` stands a player to climb a step ladder (world units):
        28 units in front of the column (a short run-up, as before), else 22, 16 or 36
        (``backs``; a hanging ladder: 16 first, in the air), slid along its width: the first
        spot where a standing player box is clear of world and prop-clip brushes (de_rats: a
        clip strip beside a cable ladder, an overhang 28 units out), standing on a solid up
        to a step (16) above the floor if that is what is there (de_vertigo: a pallet in
        front of a ladder). ``None`` if there is none."""
        if not hasattr(self, "_probe_solids"):
            ents = [MEntity({"classname": "worldspawn"}, list(getattr(self, "_world_brushes", []))
                            + list(getattr(self, "_prop_clip_brushes", [])))]
            self._probe_solids = [v for v in validate._solids(MapFile(ents))[0]]
        offs = [0.0] + [d * k for d in (4.0, 8.0, 12.0, 16.0, 20.0) if d <= max(half_w, 4.0) for k in (-1.0, 1.0)]
        for back in backs:
            for off in offs:
                c = np.asarray(front, np.float64) - facing * back
                c[wide] += off
                # 4 up: the probe's tele rounds to whole units, and a player put within a unit of
                # a patch (de_cbble's displacement ground) falls through its collision
                z = z0 + 4
                hits = [q for q in self._probe_solids
                        if validate.box_hits_brush((c[0] - 15, c[1] - 15, z), (c[0] + 15, c[1] + 15, z + 95), q)]
                if hits and max(q.maxs[2] for q in hits) <= z0 + 16:
                    z = max(q.maxs[2] for q in hits) + 1
                    hits = [q for q in self._probe_solids
                            if validate.box_hits_brush((c[0] - 15, c[1] - 15, z), (c[0] + 15, c[1] + 15, z + 95), q)]
                if not hits:
                    return [round(float(c[0]), 1), round(float(c[1]), 1), round(float(z), 1)]
        return None

    STEP_RISE = 16.0    # under MOHAA's STEPSIZE 18: one step up per move (bg_slidemove.cpp)
    STEP_DEPTH = 1.0
    MIN_STEP_DEPTH = 0.5

    def _ladder_steps(self, lo, hi, thin: int, sgn: int, far: float, z0: float) -> float:
        """A CS-style ladder: invisible ``common/clip`` slices from ``z0`` to the top of the
        Source volume against its wall face (``far``), each ``STEP_RISE`` high and
        ``STEP_DEPTH`` shallower than the one below, so running into the ladder climbs it
        (one step per move: about 600 units/s at 60 fps), backing off climbs down and the
        player can step off sideways or onto the ledge at the top. Returns the column's
        front (climber-side) coordinate on the ``thin`` axis (Source units)."""
        from ..build import box
        s = self.opt.scale
        wide = 1 - thin
        w0, w1 = lo[wide], hi[wide]
        if w1 - w0 < 32:  # at least a player's width
            m = (w0 + w1) / 2
            w0, w1 = m - 16, m + 16
        top = hi[2]
        n = max(1, math.ceil((top - z0) / self.STEP_RISE - 1e-6))
        depth = self._step_depth(lo, hi, thin, sgn, far, z0, n)
        for k in range(1, n + 1):
            za, zb = z0 + (k - 1) * self.STEP_RISE, min(z0 + k * self.STEP_RISE, top)
            out = (n - k + 1) * depth
            a, b = sorted((far, far - sgn * out))
            bl, bh = [0.0, 0.0, za], [0.0, 0.0, zb]
            bl[thin], bh[thin], bl[wide], bh[wide] = a, b, w0, w1
            self._ladder_step_brushes.append(box(tuple(v * s for v in bl), tuple(v * s for v in bh), "common/clip", True))
        return far - sgn * n * depth

    def _step_depth(self, lo, hi, thin: int, sgn: int, far: float, z0: float, n: int) -> float:
        """Set-back per step: ``STEP_DEPTH`` (1 unit), less where the column would leave no
        room for a climber (30 wide) before the next solid in front of it, down to
        ``MIN_STEP_DEPTH``. de_rats' shaft ladders (893 and 519 tall, 62-96 units between
        the walls) need half-unit steps; on open walls half-unit ledges climbed less well
        (17-53 units instead of 71-88 on four rats ladders)."""
        c = (lo + hi) / 2
        depth = self.STEP_DEPTH
        for k in range(1, n + 1, max(1, n // 12)):
            z = z0 + (k - 0.5) * self.STEP_RISE
            room = 0.0
            while room < 160:
                p = c.copy()
                p[2] = z + 40  # around the climber's head when standing on step k
                p[thin] = far - sgn * (room + 1)
                if self._ladder_solid(p):
                    break
                room += 2
            if room < 160:
                depth = min(depth, (room - 32) / (n - k + 1))
        return max(self.MIN_STEP_DEPTH, depth)

    # ------------------------------------------------------------------ displacements
    def patches(self) -> list[Patch]:
        out = []
        if not self.opt.displacements:
            return out
        grids: list[tuple[str, np.ndarray]] = []
        in_sky: list[bool] = []
        for d in self.bsp.displacements():
            flat = d.flat
            n = d.size
            c = d.positions.reshape(-1, 3).mean(axis=0)
            sky = False
            if self.sky_area is not None:
                if self._in_sky(c + np.array(d.normal) * 2.0):
                    if not self._portal:
                        self.report["dropped"]["skybox3d_disp"] = self.report["dropped"].get("skybox3d_disp", 0) + 1
                        continue
                    sky = True
            td = self.bsp.texdata[self.bsp.texinfo[d.texinfo]["texdata"]]
            cm = self.material(d.material, (int(td["width"]), int(td["height"])))
            ti = self.bsp.texinfo[d.texinfo]
            tv = np.array(ti["texture_vecs"], dtype=np.float64).reshape(2, 4)
            s = self.opt.scale
            pos = d.positions.astype(np.float64) * s
            st = np.empty((n, n, 2))
            st[..., 0] = (flat @ tv[0, :3] + tv[0, 3]) / cm.src_size[0]
            st[..., 1] = (flat @ tv[1, :3] + tv[1, 3]) / cm.src_size[1]
            grid = np.concatenate([pos, st], axis=2)  # (n, n, 5)
            if np.dot(np.cross(grid[1, 0, :3] - grid[0, 0, :3], grid[0, 1, :3] - grid[0, 0, :3]), d.normal) < 0:
                grid = grid.transpose(1, 0, 2)  # visible side = cross(row step, column step) faces the air
            grids.append((cm.shader, grid))
            in_sky.append(sky)
        before = sum((2 * g.shape[0] - 1) * (2 * g.shape[1] - 1) for _, g in grids)
        if self.opt.disp_tolerance > 0:
            grids = [(sh, g) for (sh, _), g in zip(grids, _simplify_grids([g for _, g in grids], self.opt.disp_tolerance))]
        for (shader, grid), sky in zip(grids, in_sky):
            # midpoint expansion -> (2r-1)x(2c-1) controls; even indices are the (kept) Source samples
            r, c = grid.shape[:2]
            ctrl = np.zeros((2 * r - 1, 2 * c - 1, 5))
            ctrl[0::2, 0::2] = grid
            ctrl[1::2, 0::2] = (grid[:-1] + grid[1:]) / 2
            ctrl[0::2, 1::2] = (grid[:, :-1] + grid[:, 1:]) / 2
            ctrl[1::2, 1::2] = (grid[:-1, :-1] + grid[1:, :-1] + grid[:-1, 1:] + grid[1:, 1:]) / 4
            for piece in _split_patch(ctrl, 17):
                rows = [[tuple(round(float(v), 3) for v in piece[i, j]) for j in range(piece.shape[1])]
                        for i in range(piece.shape[0])]
                out.append(Patch(shader, rows))
                if sky:
                    self._sky_prims.append(out[-1])
        after = sum(len(p.ctrl) * len(p.ctrl[0]) for p in out)
        self.report["patch_controls"] = {"before": before, "after": after}
        self.report["patches"] = len(out)
        return out

    # ------------------------------------------------------------------ entities
    def entities(self) -> list[MEntity]:
        s = self.opt.scale
        out: list[MEntity] = []
        spawns = {"info_player_terrorist": "info_player_axis", "info_player_counterterrorist": "info_player_allied",
                  "info_deathmatch_spawn": "info_player_deathmatch"}
        has_dm = bool(self.bsp.find_entities("info_deathmatch_spawn"))
        start = None
        team, dm = [], []
        for e in self.bsp.entities:
            cls = e.classname
            o = e.origin
            if cls in spawns and o is not None:
                yaw = (e.vector("angles", (0, 0, 0)) or (0, 0, 0))[1]
                if cls == "info_deathmatch_spawn":
                    dm.append((tuple(o), yaw))
                else:
                    team.append((tuple(o), yaw))
                org = (o[0] * s, o[1] * s, o[2] * s + 1)
                if cls != "info_deathmatch_spawn":
                    out.append(_ent(spawns[cls], org, angle=fmt(yaw % 360)))
                start = start or org
        for (o, yaw), z in self._dm_spawns(dm, team):
            out.append(_ent("info_player_deathmatch", (o[0] * s, o[1] * s, o[2] * s + z), angle=fmt(yaw % 360)))
        if self.opt.lights:
            for e, cls, gain in self._kept_lights():
                out += self._light(e, cls, gain)
            if self.opt.texlights:
                out += self.texlight_lights()
        if start:
            out.append(_ent("info_player_start", start, angle="0"))
        # landmarks for cameras: bomb sites and hostage spots
        marks = []
        models = self.bsp.models
        for e in self.bsp.find_entities("func_bomb_target"):
            mi = e.model_index
            if mi:
                c = (models[mi]["mins"] + models[mi]["maxs"]) / 2
                marks.append([float(c[0]) * s, float(c[1]) * s, float(models[mi]["mins"][2]) * s])
        for e in self.bsp.find_entities("info_hostage_spawn") + self.bsp.find_entities("hostage_entity"):
            if e.origin:
                marks.append([v * s for v in e.origin])
        self.report["landmarks"] = marks
        return out

    def _nav(self):
        """The map's bot nav mesh (``maps/<map>.nav`` beside the BSP, else in its pakfile)."""
        from . import nav
        side = self.bsp_path.with_suffix(".nav")
        try:
            if side.is_file():
                return nav.read_nav(side.read_bytes())
            z = self.bsp.pakfile()
            name = next((n for n in z.namelist() if n.lower() == f"maps/{self.mapname.lower()}.nav"), None)
            return nav.read_nav(z.read(name)) if name else None
        except (ValueError, struct.error, OSError):
            return None

    def _dm_spawns(self, dm: list, team: list) -> list:
        """Deathmatch spawns as ``((pos, yaw), z lift)`` in Source units. With
        ``Options.ffa_spawns`` and a nav mesh: ``nav.spawn_count`` spots spread by walking
        distance, CS:GO's own deathmatch spawns first (thinned when they are more); without a
        mesh, CS:GO's deathmatch spawns (thinned to 48), else copies of the team spawns."""
        from . import nav
        mesh = self._nav() if self.opt.ffa_spawns else None
        if not self.opt.ffa_spawns or (mesh is None and not dm):
            self.report["dm_spawns"] = {"source": "team spawns" if not dm else "csgo", "count": len(dm or team)}
            return [(t, 1.0) for t in (dm or team)]
        count = nav.spawn_count(mesh) if mesh is not None else min(len(dm), 48)
        keep = _spread([p for p, _ in dm], count)
        kept = [dm[i] for i in keep]
        out = [(t, 1.0) for t in kept]
        if mesh is not None and len(kept) < count:
            # nav floors are bilinear over an area's corners: start 12 up and let the player drop
            out += [((p, y), 12.0) for p, y in nav.ffa_spawns(mesh, count, [p for p, _ in kept])[len(kept):]]
        self.report["dm_spawns"] = {"source": "nav" if mesh is not None else "csgo", "count": len(out),
                                    "csgo_dm": len(dm), "csgo_dm_kept": len(kept)}
        return out

    @staticmethod
    def _brightness(e) -> float:
        v = (e.get("_light") or "255 255 255 200").split()
        try:
            return float(v[3]) if len(v) > 3 else 200.0
        except ValueError:
            return 200.0

    def _kept_lights(self) -> list:
        """Source lights worth a MOHAA light: (entity, class, intensity gain).

        CS:GO maps carry many near-zero fill lights (de_nuke: 206 of 473 have brightness
        <= 53, a quarter <= 4) and pair most fixtures' ``light_spot`` with a weak ``light``
        a few units away. MOHlight lists at most 60 lights per leaf ("Num lights per leaf
        clamped from 473 to 60"), so in a converted map's big leaves the extra lights
        crowded out real fixtures and interiors went dark. Lights below
        ``light_min_brightness`` are dropped and a light within ``light_merge_distance`` of
        a brighter one is folded into it (half its intensity added)."""
        lights = [(e, e.classname, self._brightness(e)) for e in self.bsp.entities
                  if e.classname in ("light", "light_spot") and e.origin is not None and not self._in_sky(e.origin)]
        before = len(lights)
        lights = [t for t in lights if t[2] >= self.opt.light_min_brightness]
        lights.sort(key=lambda t: -t[2])
        kept: list = []
        for e, cls, br in lights:
            o = np.array(e.origin, np.float64)
            for k in kept:
                if np.linalg.norm(np.array(k[0].origin, np.float64) - o) <= self.opt.light_merge_distance:
                    k[2] += 0.5 * br / max(self._brightness(k[0]), 1.0)
                    break
            else:
                kept.append([e, cls, 1.0])
        self.report["lights"] = {"source": before, "kept": len(kept)}
        return [tuple(k) for k in kept]

    def _light(self, e, cls, gain: float = 1.0) -> list[MEntity]:
        s = self.opt.scale
        v = (e.get("_light") or "255 255 255 200").split()
        try:
            r, g, b = (float(x) / 255 for x in v[:3])
            bright = float(v[3]) if len(v) > 3 else 200.0
        except ValueError:
            return []
        mx = max(r, g, b, 1e-3)
        color = (r / mx, g / mx, b / mx)
        # MOHAA's `light` is roughly the reach in units. 0.75 x Source brightness left de_nuke's
        # radio-room ceiling spots (175) at 131: they barely reached the floor 140 units below
        intensity = max(40.0, min(800.0, bright * 1.5 * gain)) * self.opt.light_scale
        o = e.origin
        org = (o[0] * s, o[1] * s, o[2] * s)
        le = _ent("light", org, light=fmt(round(intensity)), _color=" ".join(f"{c:.3f}" for c in color))
        out = [le]
        if cls == "light_spot":
            ang = e.vector("angles", (0, 0, 0)) or (0, 0, 0)
            pitch = float(e.get("pitch", ang[0]) or ang[0])
            # VRAD's SetupLightNormalFromProps: z = +sin(pitch), so a ceiling spot's pitch -90
            # points down. (With -sin, every downward spot in a converted map lit the ceiling:
            # de_nuke's 194 ceiling spots, its dark radio rooms and lobby.)
            fwd = (math.cos(math.radians(pitch)) * math.cos(math.radians(ang[1])),
                   math.cos(math.radians(pitch)) * math.sin(math.radians(ang[1])), math.sin(math.radians(pitch)))
            tname = f"spot{abs(hash((org, ang))) % 10**8}"
            le["target"] = tname
            cone = float(e.get("_cone", "45") or 45)
            le["spot_angle"] = fmt(max(10.0, min(90.0, cone * 2)))
            out.append(_ent("info_null", (org[0] + fwd[0] * 64, org[1] + fwd[1] * 64, org[2] + fwd[2] * 64),
                            targetname=tname))
        return out

    def worldspawn(self) -> dict[str, str]:
        ws: dict[str, str] = {"classname": "worldspawn", "message": self.mapname,
                              "ambientlight": "10 10 12", "lightmapdensity": fmt(self.opt.lightmap_density)}
        envs = self.bsp.find_entities("light_environment")
        if envs:
            e = envs[0]
            v = (e.get("_light") or "255 255 255 200").split()
            try:
                r, g, b = (float(x) / 255 for x in v[:3])
                bright = float(v[3]) if len(v) > 3 else 200
            except ValueError:
                r = g = b = 1.0
                bright = 200
            k = min(1.4, bright / 250.0) * 70.0
            ws["suncolor"] = f"{r * k:.0f} {g * k:.0f} {b * k:.0f}"
            ang = e.vector("angles", (0, 0, 0)) or (0, 0, 0)
            pitch = float(e.get("pitch", ang[0]) or ang[0])
            # Source: light travels toward (yaw, pitch<0 down). MOHAA sundirection points at the sun.
            ws["sundirection"] = f"{(pitch) % 360:.0f} {(ang[1] + 180) % 360:.0f} 0"
            a = (e.get("_ambient") or "").split()
            if len(a) >= 3:
                try:
                    ar, ag, ab = (float(x) / 255 for x in a[:3])
                    ai = float(a[3]) if len(a) > 3 else 20
                    ka = max(6.0, min(20.0, ai / 12.0))
                    ws["ambientlight"] = f"{ar * ka:.1f} {ag * ka:.1f} {ab * ka:.1f}"
                    # sky fill scaled by Source's ambient brightness (de_nuke 550: a strong blue sky
                    # that keeps shadows readable), colour normalised to its brightest channel
                    mx = max(ar, ag, ab, 1e-3)
                    ks = max(20.0, min(70.0, ai / 8.0))
                    ws["sundiffusecolor"] = f"{ar / mx * ks:.0f} {ag / mx * ks:.0f} {ab / mx * ks:.0f}"
                    ws["sundiffuse"] = "1"
                except ValueError:
                    pass

        fogs = [e for e in self.bsp.find_entities("env_fog_controller") if e.get("fogenable", "0") != "0"]
        # the map's own fog: the Master one (spawnflags 1), not one only a fog_volume switches
        # to (de_vertigo's first is "fog_shaft", black at 3000 units, for the elevator shaft:
        # it had fogged the whole map and its sky black)
        local = {(v.get("fogname") or "").lower() for v in self.bsp.find_entities("fog_volume")} - {""}
        fogs.sort(key=lambda e: (not int(e.get("spawnflags", "0") or 0) & 1, (e.get("targetname") or "").lower() in local))
        if fogs:
            # Source fog is linear from fogstart to fogend, capped at fogmaxdensity; MOHAA's
            # farplane fog reaches the full colour at farplane. Put Source's density at fogend.
            e = fogs[0]
            try:
                end = float(e.get("fogend", "0") or 0) * self.opt.scale
                dens = float(e.get("fogmaxdensity", "1") or 1)
                col = [float(x) / 255 for x in (e.get("fogcolor") or "").split()[:3]]
            except ValueError:
                end, col = 0, []
            if end > 0 and len(col) == 3 and dens > 0.05:
                ws["farplane"] = fmt(round(end / min(1.0, dens)))
                ws["farplane_color"] = " ".join(f"{c:.3f}" for c in col)
                ws["farplane_cull"] = "0"  # keep the sky; Source draws it unfogged too
        return ws

    # ------------------------------------------------------------------ props
    def props(self) -> tuple[list[MEntity], list[MBrush], list[str]]:
        """Static props -> MOHAA models. Largest props first become compiled static models
        (collision baked by Q3map from their .map) until the MOHlight vertex budget; the next
        ones become runtime ``script_model``s (non-solid, collision baked here as world clip
        brushes); the rest are dropped and counted in the report."""
        from . import modelconv
        s = self.opt.scale
        out: list[MEntity] = []
        clips: list[MBrush] = []
        precache: list[str] = []
        try:
            sp = self.bsp.static_props()
        except Exception as e:  # noqa: BLE001
            self.report["warnings"].append(f"static props unreadable: {e}")
            return out, clips, precache
        cache: dict = {}
        items = []
        self._prop_draw_brushes: list[MBrush] = []    # box-like props drawn as world brushes
        fits: dict = {}
        self.report["prop_profile"] = self.opt.prop_profile
        self.report["lod_tau"] = self._profile["lod_tau"]
        if self._profile.get("split_radius"):
            self.report["merge_split"] = [self._profile["split_radius"], self._profile["split_cell"]]
        self.report["lod_base_error"] = self._profile["base_error"]
        for p_index, p in enumerate(list(sp.props) + self._entity_props()):
            p_index = p_index if p_index < len(sp.props) else -1
            sky = False
            if self.sky_area is not None:
                areas = self.bsp.prop_areas(p) if not getattr(p, "entity", False) else {
                    self.bsp.point_area(p.origin)}
                if (areas and areas <= {self.sky_area}) or self._in_sky(p.origin):
                    if not (self._portal and self.opt.props_mode == "inject"):
                        continue
                    sky = True
            key = (p.model.lower(), p.skin, p.solid if p.solid in (0, 2, 6) else 6)
            if key not in cache:
                try:
                    # per-map names: the files are map-specific (LOD, vertex order, texture
                    # gain), and installed pk3s sharing a path override each other
                    cache[key] = modelconv.convert_model(self.fs, p.model, prefix=self.prefix, skin=p.skin,
                                                         solid=key[2], centre=True, headroom=self.opt.headroom,
                                                         max_texture=self.opt.max_texture, jpeg_quality=90,
                                                         lod=self._profile["mesh_lod"],
                                                         texture_prefix=f"{self.prefix}_p")
                    for sh, g in (cache[key].gains or {}).items():
                        self._gain(sh, g)
                    for sh, w in (cache[key].tint_mask or {}).items():
                        self.report.setdefault("tint_mask", {})[sh] = w
                except Exception as e:  # noqa: BLE001
                    self.report["warnings"].append(f"prop {p.model}: {e}")
                    cache[key] = None
            cm = cache[key]
            if cm is None:
                continue
            sc = (p.uniform_scale or 1.0)
            size = [(cm.bounds[1][i] - cm.bounds[0][i]) * sc for i in range(3)]
            pf, big = self._profile, max(size)
            if not sky and (big < pf["drop"] or (big < pf["drop_nonsolid"] and not cm.has_collision)
                            or (big < pf["foliage"] and any(w in p.model.lower() for w in FOLIAGE_WORDS))):
                self.report["profile_dropped"] = self.report.get("profile_dropped", 0) + 1
                continue
            if not sky and pf.get("drop_wires") and is_wire_model(p.model):
                self.report["wires_dropped"] = self.report.get("wires_dropped", 0) + 1
                continue
            if (not sky and pf.get("brush_box") and abs(sc - 1.0) < 1e-6 and big >= pf.get("brush_min", 0.0)
                    and self._prop_brush(p, cm, fits, pf["brush_box"])):
                clips += self._prop_clips(cm, p, sc * s)
                continue
            items.append((size[0] * size[1] * size[2], p, cm, sc, p_index, sky))
        items.sort(key=lambda t: -t[0])
        static_v, runtime, dropped, injected = 0, 0, 0, 0
        used: dict[str, object] = {}
        self.statics = []
        self.prop_light = []
        for _, p, cm, sc, p_index, sky in items:
            org = " ".join(fmt(round(c, 2)) for c in self._prop_origin(p, cm, sc * s))
            ang = " ".join(fmt(round(a, 3)) for a in p.angles)
            model_keys = [t[len("models/"):] if t.startswith("models/") else t for t in cm.tiks]
            if self.opt.props_mode == "inject":
                o = tuple(round(c, 2) for c in self._prop_origin(p, cm, sc * s))
                # CS:GO tints props per instance (sprp DiffuseModulation, prop_dynamic rendercolor):
                # de_nuke's grey pipes and yellow rails are one white model tinted
                tint = tuple(int(c) for c in getattr(p, "diffuse_modulation", (255, 255, 255, 255))[:3])
                fade = 0.0 if sky else self._fade(p, cm, sc) * s
                for part, mk in enumerate(model_keys):
                    if sky:   # a 3D skybox prop: moved with its room in run(), no collision
                        self._sky_statics.add(len(self.statics))
                    self.statics.append((mk, o, tuple(round(a, 3) for a in p.angles), round(sc * s, 4), tint, fade))
                    self.prop_light.append(self._prop_light(p_index, cm, part) if p_index >= 0 else None)
                if not sky:
                    clips += self._prop_clips(cm, p, sc * s)
                injected += 1
                static_v += cm.vertices
            elif static_v + cm.vertices <= self.opt.props_static_vertices:
                static_v += cm.vertices
                for mk in model_keys:
                    e = MEntity({"classname": "static_" + mk.rsplit("/", 1)[-1][:-4]})
                    e["model"], e["origin"], e["angles"] = mk, org, ang
                    if sc * s != 1:
                        e["scale"] = fmt(round(sc * s, 4))
                    out.append(e)
            elif runtime < self.opt.props_runtime_max:
                runtime += 1
                for mk in model_keys:
                    e = MEntity({"classname": "script_model", "model": mk, "origin": org, "angles": ang,
                                 "spawnflags": "1"})  # 1 = NOT_SOLID: collision comes from baked clip brushes
                    if sc * s != 1:
                        e["scale"] = fmt(round(sc * s, 4))
                    out.append(e)
                    precache.append("models/" + mk)
                clips += self._prop_clips(cm, p, sc * s)
            else:
                dropped += 1
                continue
            used[cm.tik] = cm
        if used:
            self.assets.update(modelconv.bundle(used.values(), script=f"scripts/csgo_{self.opt.name}_props.shader"))
        self.report["props"] = {"instances": len(items), "static": len(items) - runtime - dropped - injected,
                                "injected": injected, "static_vertices": static_v, "runtime": runtime,
                                "dropped": dropped, "models": len(used)}
        return out, clips, sorted(set(precache))

    def _prop_brush(self, p, cm, fits: dict, threshold: float) -> bool:
        """Draw static prop ``p`` as a world brush when its mesh is box-like (``box_fit`` of
        the Source mesh >= ``threshold``, cached per model and skin in ``fits``): the box of
        its two largest opposite faces, textured with its own materials (``_model_slab``),
        detail and non-solid (the prop's clip hulls stay its collision). World faces are
        VIS-culled and lightmapped; static models are neither. Returns whether it did."""
        from .modelconv import load_studio_model
        key = (p.model.lower(), p.skin)
        if key not in fits:
            try:
                sm = load_studio_model(self.fs, p.model)
                tris = [m.positions[m.triangles] for m in sm.meshes if len(m.triangles)]
                fits[key] = box_fit(np.concatenate(tris)) if tris else 0.0
            except Exception as e:  # noqa: BLE001
                self.report["warnings"].append(f"box fit {p.model}: {e}")
                fits[key] = 0.0
        if fits[key] < threshold:
            return False
        slab = self._model_slab({"skin": str(p.skin)}, p.model, p.origin, p.angles, hull_align=False)
        if slab is None:
            return False
        for f in slab[0].faces:
            f.ext = ["+surfaceparm", "detail", "+surfaceparm", "nonsolid"]
        self._prop_draw_brushes.append(slab[0])
        r = self.report.setdefault("brush_props", {"instances": 0, "vertices": 0})
        r["instances"] += 1
        r["vertices"] += cm.vertices
        return True

    # prop_hallucination: a never-solid prop; de_rats_1337_v2 draws its ladders and lamps with 97
    PROP_ENTITIES = ("prop_dynamic", "prop_dynamic_override", "prop_physics", "prop_physics_override",
                     "prop_physics_multiplayer", "prop_hallucination")

    def _entity_props(self) -> list:
        """Model entities that stand still in play (``prop_dynamic``, physics props), as
        static-prop-like records. Interactive ones are skipped: a prop another entity's
        outputs target (de_nuke's vent slats, opened by a ``func_button``) or one with
        outputs of its own (``OnBreak``: breakable vent covers), so those openings stay open."""
        from types import SimpleNamespace
        self._interactive_props = []
        # names that some output enables, breaks, kills or animates (a prop only re-skinned,
        # like mirage's TVs, stays an ordinary prop)
        targeted: set[str] = set()
        for e in self.bsp.entities:
            for k, v in e.items():
                if k.lower().startswith("on"):
                    parts = [x.strip().lower() for x in re.split(r"[,\x1b]", v)]
                    if len(parts) > 1 and parts[1] in ("enable", "disable", "toggle", "break", "kill",
                                                       "setanimation", "setdefaultanimation", "turnon", "turnoff"):
                        targeted.add(parts[0])
        out = []
        skipped = 0
        for e in self.bsp.entities:
            if e.classname not in self.PROP_ENTITIES or not e.get("model") or e.origin is None:
                continue
            if any(k.lower() == "onbreak" for k, _ in e.items()) or (e.get("startdisabled") or "0") == "1" or (
                    e.get("targetname") and e.get("targetname").lower() in targeted):
                skipped += 1
                self._interactive_props.append(e)
                continue
            try:
                solid = 0 if e.classname == "prop_hallucination" else int(float(e.get("solid", "6") or 6))
                skin = int(float(e.get("skin", "0") or 0))
                scale = float(e.get("modelscale", "1") or 1)
            except ValueError:
                solid, skin, scale = 6, 0, 1.0
            try:
                rc = tuple(int(float(v)) for v in (e.get("rendercolor") or "255 255 255").split()[:3])
                rc = rc if len(rc) == 3 else (255, 255, 255)
            except ValueError:
                rc = (255, 255, 255)
            try:
                fmin, fmax = float(e.get("fademindist") or -1), float(e.get("fademaxdist") or 0)
            except ValueError:
                fmin, fmax = -1.0, 0.0
            out.append(SimpleNamespace(model=e.get("model"), origin=e.origin,
                                       angles=e.vector("angles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0),
                                       skin=skin, solid=solid, uniform_scale=scale, entity=True,
                                       diffuse_modulation=rc + (255,), flags=1 if fmax > 0 else 0,
                                       fade_min=fmin, fade_max=fmax))
        self.report["entity_props"] = {"converted": len(out), "interactive_skipped": skipped}
        return out

    @property
    def _profile(self) -> dict:
        return PROP_PROFILES[self.opt.prop_profile]

    def _fade(self, p, cm, sc: float) -> float:
        """The prop's vanish distance (Source units, 0: never) under the prop profile."""
        f = fade_distance(p)
        cap, small = self._profile["fade_cap"], self._profile["fade_small"]
        if cap:
            big = max((cm.bounds[1][i] - cm.bounds[0][i]) * sc for i in range(3))
            cap = max(cap, self._profile.get("fade_size", 0.0) * big)
            if f > 0:
                f = min(f, cap)
            elif big < small:
                f = cap
        return round(f, 1)

    def _prop_light(self, index: int, cm, part: int) -> Optional[np.ndarray]:
        """CS:GO's baked lighting of static prop ``index`` (``sp_hdr_<index>.vhv`` in the map's
        pakfile) on the SKD vertices of ``cm``'s TIKI ``part``, as uint8 RGB in VRAD's vertex
        byte scale (127.5 * linear^(1/2.2)); None when the file or the mesh mapping is missing.

        VRAD writes one stream per (body part, model, LOD, mesh, strip group) of the prop's VTX
        (``studiomdl.vhv_layout``), 4 bytes per basis direction per vertex: B, G, R as
        ``255 * 0.5 * linear^(1/2.2)`` (mathlib ``lineartovertex`` with OVERBRIGHT 2), then
        the sun share. CS:GO bump-lights props with 3 basis directions; a flat normal weighs
        them equally, so the vertex colour is their mean in linear light."""
        import struct
        from .studiomdl import VTX_SUFFIXES, vhv_layout
        if not hasattr(self, "_vhv"):
            try:
                self._vhv = self.bsp.pakfile()
                self._vhv_names = set(self._vhv.namelist())
            except Exception:  # noqa: BLE001
                self._vhv, self._vhv_names = None, set()
            self._vhv_layouts: dict = {}
        vs = cm.vertex_source[part] if part < len(getattr(cm, "vertex_source", [])) else None
        if self._vhv is None or vs is None or not len(vs):
            return None
        name = next((n for n in (f"sp_hdr_{index}.vhv", f"sp_{index}.vhv") if n in self._vhv_names), None)
        if name is None:
            return None
        if cm.source not in self._vhv_layouts:
            mdl = self.fs.try_read(cm.source)
            base = cm.source[:-4]
            vtx = next((d for d in (self.fs.try_read(base + x) for x in VTX_SUFFIXES) if d), None)
            try:
                self._vhv_layouts[cm.source] = vhv_layout(mdl, vtx) if mdl and vtx else None
            except (struct.error, ValueError):
                self._vhv_layouts[cm.source] = None
        layout = self._vhv_layouts[cm.source]
        if not layout:
            return None
        d = self._vhv.read(name)
        _ver, _chk, _flags, vsize, _nv, nm = struct.unpack_from("<iIIIIi", d, 0)
        if nm != len(layout) or vsize % 4 or not vsize:
            return None
        table = [struct.unpack_from("<III", d, 40 + 28 * k) for k in range(nm)]
        # the stream of the LOD the mesh was converted from (studiomdl clamps to the last one)
        want = min(self._profile["mesh_lod"], max((l for l, *_ in table), default=0))
        streams: dict = {}
        for (lod, n, off), (bp, mi, lod2, me, ids) in zip(table, layout):
            if n != len(ids) or lod != lod2:
                return None
            if lod != want or not n:
                continue
            raw = np.frombuffer(d, np.uint8, count=n * vsize, offset=off).reshape(n, vsize // 4, 4)
            lin = (raw[:, :, [2, 1, 0]].astype(np.float64) / 127.5) ** 2.2   # BGR -> RGB, linear
            key = (bp, mi, me)
            if key not in streams:
                streams[key] = np.full((int(ids.max()) + 1 if len(ids) else 1, 3), np.nan)
            arr = streams[key]
            if ids.max() >= len(arr):
                arr = np.vstack([arr, np.full((int(ids.max()) + 1 - len(arr), 3), np.nan)])
                streams[key] = arr
            arr[ids] = lin.mean(1)
        out = np.full((len(vs), 3), np.nan)
        for key, arr in streams.items():
            sel = (vs[:, 0] == key[0]) & (vs[:, 1] == key[1]) & (vs[:, 2] == key[2])
            if sel.any():
                ids = vs[sel, 3]
                ok = ids < len(arr)
                rows = np.nonzero(sel)[0]
                out[rows[ok]] = arr[ids[ok]]
        found = ~np.isnan(out[:, 0])
        if found.mean() < 0.5:
            return None
        out[~found] = np.nanmean(out[found], axis=0)
        return np.clip(np.round(127.5 * np.power(out, 1 / 2.2)), 0, 255).astype(np.uint8)

    def _prop_origin(self, p, cm, scale: float) -> tuple[float, float, float]:
        """World origin of the converted model: the Source origin moved to the model's
        re-centred pivot (``ConvertedModel.pivot``, rotated and scaled)."""
        R = self._rot(p.angles)
        pv = getattr(cm, "pivot", (0.0, 0.0, 0.0))
        return tuple(p.origin[i] * self.opt.scale + scale * sum(R[i][j] * pv[j] for j in range(3))
                     for i in range(3))  # type: ignore[return-value]

    def _prop_clips(self, cm, p, scale: float) -> list[MBrush]:
        """The model's collision .map brushes placed in the world (origin + scale*R(angles)*p)."""
        text = cm.files.get(cm.tik[:-4] + ".map")
        if not text:
            return []
        R = self._rot(p.angles)
        o = self._prop_origin(p, cm, scale)
        out = []
        for b in MapFile.parse(text.decode("latin-1")).worldspawn.brushes():
            faces = []
            for f, w in zip(b.faces, b.windings()):
                if len(w) < 3:
                    continue
                pts = [_snap(tuple(o[i] + scale * sum(R[i][j] * q[j] for j in range(3)) for i in range(3))) for q in w]
                n = tuple(sum(R[i][j] * f.plane.normal[j] for j in range(3)) for i in range(3))
                try:
                    tri = _tri_for(n, pts)
                except AssertionError:
                    continue
                faces.append(Face(tri, f.shader, (0, 0), 0, (1, 1), 0, 0, 0, ["+surfaceparm", "detail"]))
            if len(faces) >= 4:
                out.append(MBrush(faces))
        return out

    # ------------------------------------------------------------------ assembly
    def shell(self, brushes: list[MBrush], patches: list[Patch], pad: float = 64) -> list[MBrush]:
        from ..build import box
        pts = [p for b in brushes for w in b.windings() for p in w]
        pts += [c[:3] for p in patches for row in p.ctrl for c in row]
        (x0, y0, z0), (x1, y1, z1) = geom.bounds_of(pts)
        x0, y0, z0, x1, y1, z1 = x0 - pad, y0 - pad, z0 - pad, x1 + pad, y1 + pad, z1 + pad
        t = 16
        return [box(a, b_, CAULK) for a, b_ in (
            ((x0 - t, y0 - t, z0 - t), (x1 + t, y1 + t, z0)), ((x0 - t, y0 - t, z1), (x1 + t, y1 + t, z1 + t)),
            ((x0 - t, y0 - t, z0), (x0, y1 + t, z1)), ((x1, y0 - t, z0), (x1 + t, y1 + t, z1)),
            ((x0, y0 - t, z0), (x1, y0, z1)), ((x0, y1, z0), (x1, y1 + t, z1)))]

    def _drop_ladder_rail_clips(self, brushes: list[MBrush]) -> list[MBrush]:
        """CS:GO rails ladders with player clips 24 units apart (de_vertigo, de_nuke): a
        channel narrower than the 32-wide step column and than a player, who got wedged
        between the rails. A pair of clip-only brushes flanking a ladder volume (touching
        opposite sides of a 16-32 unit wide axis, each beside at least half its height) goes,
        before the ladders are placed: counted as walls, they had turned a 26.7 x 24
        de_vertigo ladder away from its wall. Clips above, below or behind a ladder (ledges,
        caps, the wall it leans on) stay."""
        s = self.opt.scale
        vols = [(lo * s, hi * s) for lo, hi in self._ladder_boxes()]
        clip_only = ("common/clip", "common/playerclip")
        clips = [(i, *map(np.array, b.bounds())) for i, b in enumerate(brushes)
                 if all(f.shader in clip_only for f in b.faces)]
        drop: set[int] = set()
        for lo, hi in vols:
            for a in (0, 1):
                if not 16 <= hi[a] - lo[a] < 32:
                    continue
                o = 1 - a
                sides: dict[int, list[int]] = {-1: [], 1: []}
                for i, blo, bhi in clips:
                    if (min(bhi[2], hi[2]) - max(blo[2], lo[2]) < 0.5 * (hi[2] - lo[2])
                            or not (blo[o] < hi[o] and bhi[o] > lo[o])):
                        continue
                    if lo[a] - 2 < bhi[a] <= lo[a] + 2:
                        sides[-1].append(i)
                    elif hi[a] - 2 <= blo[a] < hi[a] + 2:
                        sides[1].append(i)
                if sides[-1] and sides[1]:
                    drop.update(sides[-1] + sides[1])
        kept = [b for i, b in enumerate(brushes) if i not in drop]
        self.report["ladder_rail_clips_dropped"] = len(drop)
        self._world_brushes = kept
        self.__dict__.pop("_brush_boxes", None)
        return kept

    def _place_sky_room(self, m: MapFile, world: MEntity, main_lo, main_hi, T) -> None:
        """Move the 3D skybox room (``self._sky_prims``, its props) beside the map so that,
        after the map's own offset ``T``, it lies inside +-WORLD_LIMIT (de_vertigo's room
        reaches x 15,008, de_cache's 10,911): below the map, else above or beside it. The
        portal sky is drawn from the ``script_skyorigin`` (at ``sky_camera``) wherever the room
        is. Allied Assault has no sky parallax (``skyboxSpeed`` is a protocol-15 field,
        ``cg_main.c``), so the room is seen from one point: where Source's skybox camera is for
        an eye at the spawns' mean. With no room for it, the room is dropped and the map's sky
        faces get the 2D sky again."""
        s = self.opt.scale
        cam = self.bsp.sky_camera
        centre = np.asarray(cam.origin, np.float64) * s     # the room is scaled about the camera
        # Source draws the skybox from sky_camera + eye / scale; AA's portal sky has one fixed
        # origin, so take the eye at the spawns' mean (de_vertigo is played 11,600 units up:
        # 725 above sky_camera in the room; at sky_camera itself its city looked street-level)
        spawns = np.asarray([e.origin for e in self.bsp.entities
                             if e.classname in ("info_player_terrorist", "info_player_counterterrorist",
                                                "info_deathmatch_spawn") and e.origin is not None], np.float64)
        eye = (spawns.mean(axis=0) + (0.0, 0.0, 64.0)) if len(spawns) else np.zeros(3)
        cam_scale = float(cam.get("scale") or 16) or 16.0
        eye_room = centre + eye / cam_scale * s
        # Seen from that one point, room objects near it land far from where a player elsewhere
        # would see them (de_dust2's houses past the walls hung huge over DD): an object closer
        # than 8 x the spawns' spread / scale (angle error over ~7 degrees at the far spawn)
        # goes, and the room goes when under a quarter of it is left. de_vertigo (all 11 far:
        # played 732 above its city, spawns 800 apart) keeps it; de_nuke would keep 27 of 303,
        # de_cbble 5 of 41, the others none: their skyboxes are rooms built around the map
        spread = float(np.max(np.linalg.norm(spawns[:, :2] - spawns[:, :2].mean(axis=0), axis=1))) if len(spawns) else 0.0
        near = 8.0 * spread / cam_scale * s

        def dist(lo, hi):
            return float(np.linalg.norm(np.maximum(np.maximum(lo - eye_room, eye_room - hi), 0.0)))

        keep, dropped, objects = [], 0, len(self._sky_statics)
        for q in self._sky_prims:
            if isinstance(q, MBrush):
                lo, hi = (np.asarray(v, np.float64) for v in q.bounds())
                shell = any(f.shader == self.sky_shader for f in q.faces)
            else:
                P = np.asarray([c[:3] for row in q.ctrl for c in row], np.float64)
                lo, hi, shell = P.min(0), P.max(0), False
            objects += not shell
            if not shell and dist(lo, hi) < near:
                dropped += 1
                continue
            keep.append(q)
        far = {id(q) for q in keep}
        world.prims = [q for q in world.prims if id(q) in far or id(q) not in {id(x) for x in self._sky_prims}]
        statics, lights, sky_statics = [], [], set()
        for n, (st, pl) in enumerate(zip(self.statics, self.prop_light)):
            if n in self._sky_statics:
                if dist(np.asarray(st[1], np.float64), np.asarray(st[1], np.float64)) < near:
                    dropped += 1
                    continue
                sky_statics.add(len(statics))
            statics.append(st)
            lights.append(pl)
        self.statics, self.prop_light, self._sky_statics = statics, lights, sky_statics
        self._sky_prims = keep
        self.report["sky_near_dropped"] = [dropped, objects]
        nothing_left = dropped > 0.75 * objects
        if nothing_left:
            self.report["warnings"].append(f"3D skybox: {dropped} of {objects} objects nearer than {near:.0f} to its eye; "
                                           "2D sky only")
        pts = []
        for q in self._sky_prims:
            if isinstance(q, MBrush):
                pts += list(q.bounds())
            else:
                pts += [c[:3] for row in q.ctrl for c in row]
        r_lo, r_hi = np.min(pts, 0), np.max(pts, 0)
        m_lo, m_hi = main_lo + T, main_hi + T
        c = (m_lo + m_hi) / 2
        gap = 512.0
        rel, k = None, 1.0
        # a perspective view does not change when the scene is scaled about the eye, so a room
        # that fits nowhere is shrunk about sky_camera (de_vertigo's 7,360-unit city: half size)
        for k in () if nothing_left else (1.0, 0.5, 0.25):
            lo_k = centre + k * (r_lo - centre)
            size = (r_hi - r_lo) * k
            cands = [(c[0] - size[0] / 2, c[1] - size[1] / 2, m_lo[2] - gap - size[2]),
                     (c[0] - size[0] / 2, c[1] - size[1] / 2, m_hi[2] + gap),
                     (m_lo[0] - gap - size[0], c[1] - size[1] / 2, c[2] - size[2] / 2),
                     (m_hi[0] + gap, c[1] - size[1] / 2, c[2] - size[2] / 2),
                     (c[0] - size[0] / 2, m_lo[1] - gap - size[1], c[2] - size[2] / 2),
                     (c[0] - size[0] / 2, m_hi[1] + gap, c[2] - size[2] / 2)]
            for cand in cands:
                d = np.round((np.asarray(cand) - (lo_k + T)) / 64.0) * 64.0
                lo = lo_k + T + d
                if np.all(lo >= -WORLD_LIMIT) and np.all(lo + size <= WORLD_LIMIT):
                    rel = d
                    break
            if rel is not None:
                break
        sky = {id(q) for q in self._sky_prims}
        if rel is None:
            if not nothing_left:
                self.report["warnings"].append("3D skybox: no room for it inside +-8192; dropped")
            world.prims = [q for q in world.prims if id(q) not in sky]
            # the 2D sky is drawn: its brushes are split like the rest (64-vertex face limit)
            self._portal = False
            whole = {id(w[0]): w for w in self._sky_whole}
            prims = []
            for q in world.prims:
                if id(q) in whole:
                    _, br, geo, kinds, nonsolid, water = whole[id(q)]
                    prims += [pc for pc in (self._brush_piece(br, g, kinds, nonsolid, water)
                                            for g in _split_long(geo, self.opt.split)) if pc is not None]
                else:
                    prims.append(q)
            world.prims = prims
            for e, prim in m.iter_prims():
                if isinstance(prim, MBrush):
                    for f in prim.faces:
                        if f.shader == "common/skyportal":
                            f.shader = self.sky_shader
            self.statics = [st for k, st in enumerate(self.statics) if k not in self._sky_statics]
            self.prop_light = [pl for k, pl in enumerate(self.prop_light) if k not in self._sky_statics]
            self._sky_prims = []
            return
        tmp = MapFile([MEntity({"classname": "worldspawn"}, list(self._sky_prims))])
        if k != 1.0:
            scale_map(tmp, k, tuple(centre))
        translate_map(tmp, tuple(rel))
        moved = tmp.entities[0].prims
        world.prims = [q for q in world.prims if id(q) not in sky] + moved
        self._sky_prims = moved
        self.statics = [(mk, tuple(centre[i] + k * (o[i] - centre[i]) + rel[i] for i in range(3)), ang, round(sc * k, 4),
                         *rest) if n in self._sky_statics else (mk, o, ang, sc, *rest)
                        for n, (mk, o, ang, sc, *rest) in enumerate(self.statics)]
        org = centre + k * (eye_room - centre) + rel
        m.entities.append(_ent("script_skyorigin", tuple(float(round(v, 1)) for v in org)))
        # lighting.place: a room point p (Source x scale) lands on centre + k (p - centre) + offset
        self.report["sky_room"] = {"box": [[round(float(v), 1) for v in r_lo], [round(float(v), 1) for v in r_hi]],
                                   "centre": [round(float(v), 2) for v in centre], "k": k,
                                   "offset": [round(float(T[i] + rel[i]), 1) for i in range(3)],
                                   "camera_scale": float(cam.get("scale") or 16), "prims": len(moved),
                                   "props": len(self._sky_statics)}

    def run(self) -> Result:
        brushes = self._drop_ladder_rail_clips(self.brushes())
        patches = self.patches()
        overlay_patches = self.overlays() + self.ropes()
        self.statics: list = []
        prop_ents, prop_clips, precache = self.props() if self.opt.props else ([], [], [])
        self._prop_clip_brushes = prop_clips
        # A ladder model's own collision (mirage's leaning ladderwood) stands inside the ladder
        # volume and stops the view trace that mounts a func_ladder (Player::CondLadder), and a
        # door model beside that ladder filled the box FuncLadder::CanUseLadder checks: drop
        # prop clips that reach into a ladder volume or its mount box.
        s = self.opt.scale
        ladder_ents = self.ladders()
        lboxes = [(lo * s - 2, hi * s + 2) for lo, hi in self._ladder_boxes()]
        lboxes += [(np.array(lo), np.array(hi)) for lo, hi in self._ladder_mount_boxes]
        if lboxes:
            kept = []
            for b in prop_clips:
                blo, bhi = b.bounds()
                if any(all(blo[i] < hi[i] and bhi[i] > lo[i] for i in range(3)) for lo, hi in lboxes):
                    continue
                kept.append(b)
            self.report["ladder_prop_clips_dropped"] = len(prop_clips) - len(kept)
            prop_clips = kept
        world = MEntity(self.worldspawn())
        world.prims = (list(brushes) + list(patches) + overlay_patches + prop_clips + self.sprites()
                       + self._ladder_step_brushes + list(getattr(self, "_prop_draw_brushes", [])))
        ents = [world] + self.entities() + ladder_ents + self.windows() + self.doors() + self.breakables() + prop_ents
        self.report["precache"] = precache
        scripts = [self._shader_text(cm) for cm in self.mats.values()]
        scripts += list(getattr(self, "_overlay_shaders", {}).values())
        if getattr(self, "_sky_text", None):
            scripts.insert(0, self._sky_text)
        self.assets[f"scripts/{self._script_name()}"] = ("\n\n".join(scripts) + "\n").encode("latin-1")
        stray = [k for k in self.assets if k.endswith(".shader") and not k.startswith("scripts/")]
        if stray:  # the engine and Q3map only read scripts/*.shader
            raise ValueError(f"shader scripts outside scripts/: {stray}")
        self.report["shaders"] = sum(t.count("\n{") for k, t in ((k, v.decode("latin-1")) for k, v in self.assets.items())
                                     if k.startswith("scripts/"))
        if self.report["shaders"] > 1500:
            self.report["warnings"].append(f"{self.report['shaders']} shaders: Q3map holds only ~1,630 beyond retail "
                                           "(MAX_SURFACE_INFO, docs/toolchain.md)")
        self.report["materials"] = len(self.mats)
        self.report["entities"] = len(ents)
        self.report["asset_bytes"] = sum(len(v) for v in self.assets.values())
        m = MapFile(ents)
        sky = {id(p) for p in self._sky_prims}
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for e, prim in m.iter_prims():
            if isinstance(prim, MBrush) and id(prim) not in sky:
                b0, b1 = prim.bounds()
                lo, hi = np.minimum(lo, b0), np.maximum(hi, b1)
        if self.opt.detail_all:   # the structural shell (below) pads the map by 64 + 16
            lo, hi = lo - 80, hi + 80
        # de_vertigo plays 11,500 units up: move maps that leave MOHAA's +-8192 to the origin
        T = self.opt.offset
        if T is None:
            T = (0.0, 0.0, 0.0)
            if np.isfinite(lo).all() and max(np.abs(lo).max(), np.abs(hi).max()) > WORLD_LIMIT:
                T = tuple(float(-512.0 * round((lo[i] + hi[i]) / 2 / 512.0)) for i in range(3))
        if self._sky_prims:
            self._place_sky_room(m, world, lo, hi, np.asarray(T, np.float64))
        if self.opt.detail_all:
            room = self._sky_prims    # moved (or dropped) by _place_sky_room
            world.prims = self.shell([b for b in brushes if id(b) not in sky] + [q for q in room if isinstance(q, MBrush)],
                                     [q for q in patches if id(q) not in sky] + [q for q in room if isinstance(q, Patch)]
                                     ) + world.prims
        if any(T):
            translate_map(m, T)
            self.statics = [(mk, tuple(o[i] + T[i] for i in range(3)), *rest) for mk, o, *rest in self.statics]
            self.report["landmarks"] = [[c + T[i] for i, c in enumerate(p)] for p in self.report.get("landmarks", [])]
            for rec in self.report.get("ladders", []):   # game.ladders_for_probe reads these
                for k in ("origin", "probe_start"):
                    if k in rec:
                        rec[k] = [round(rec[k][i] + T[i], 1) for i in range(3)]
                for k in ("zmin", "zmax"):
                    if k in rec:
                        rec[k] = round(rec[k] + T[2], 1)
        self.report["offset"] = list(T)
        moved = validate.fix_spawns(m)
        if moved:
            self.report["spawns_fixed"] = moved
        light = list(getattr(self, "prop_light", []))
        self.report["prop_light"] = {"vhv": sum(x is not None for x in light), "statics": len(self.statics)}
        return Result(m, self.assets, self.report, list(self.statics), light)


def merge_ladder_boxes(boxes, gap_xy: float = 2.0, gap_z: float = 8.0) -> list:
    """Union ladder volumes ([lo, hi] arrays) that touch: within ``gap_xy`` horizontally and
    ``gap_z`` vertically. One Source ladder is often several brushes: stacked pieces (de_nuke)
    or two rails plus a 1.5-unit brush per rung (de_cache's A-site ladder, 11 brushes)."""
    merged = [[np.array(lo, dtype=np.float64), np.array(hi, dtype=np.float64)] for lo, hi in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            for j in range(len(merged) - 1, i, -1):
                (alo, ahi), (blo, bhi) = merged[i], merged[j]
                gap = np.maximum(alo - bhi, blo - ahi)
                if gap[0] <= gap_xy and gap[1] <= gap_xy and gap[2] <= gap_z:
                    merged[i] = [np.minimum(alo, blo), np.maximum(ahi, bhi)]
                    del merged[j]
                    changed = True
    return merged


class _CutWinding(list):
    """Winding of a face created by a grid cut (no Source side); carries its plane normal."""
    normal: tuple = (0.0, 0.0, 0.0)


def _split_long(geo, grid: float):
    """Split a convex brush, given as [(side, winding)], at multiples of ``grid`` along X and Y
    and of ``min(grid, 512)`` along Z when it is longer than that. Cut faces come back as
    (None, _CutWinding). Z too: de_rats' 672-unit-tall, 24-wide wall strip collected 65
    T-junction vertices; few brushes are that tall, so the finer Z grid costs little."""
    if not grid:
        return [geo]
    pts = [p for _, w in geo for p in w]
    (x0, y0, z0), (x1, y1, z1) = geom.bounds_of(pts)
    pieces = [geo]
    for ax, lo, hi, g in ((0, x0, x1, grid), (1, y0, y1, grid), (2, z0, z1, min(grid, 512.0))):
        if hi - lo <= g:
            continue
        cuts = [k * g for k in range(math.floor(lo / g) + 1, math.ceil(hi / g))]
        nxt = []
        for pc in pieces:
            planes = [(s.plane if s is not None else geom.Plane(w.normal, geom.dot(w.normal, w[0]))) for s, w in pc]
            sides = [s for s, _ in pc]
            normals = [w.normal if s is None else None for s, w in pc]
            bounds = [-1e9] + cuts + [1e9]
            for a, b in zip(bounds, bounds[1:]):
                extra = []
                if a > -1e8:
                    n = [0.0, 0.0, 0.0]; n[ax] = -1.0
                    extra.append(geom.Plane(tuple(n), -a))
                if b < 1e8:
                    n = [0.0, 0.0, 0.0]; n[ax] = 1.0
                    extra.append(geom.Plane(tuple(n), b))
                allp = planes + extra
                ws = geom.brush_windings(allp)
                piece = []
                for i, w in enumerate(ws):
                    if len(w) < 3:
                        continue
                    if i < len(sides) and sides[i] is not None:
                        piece.append((sides[i], w))
                    else:
                        cw = _CutWinding(w)
                        cw.normal = allp[i].normal
                        piece.append((None, cw))
                if len(piece) >= 4 and any(s is not None for s, _ in piece):
                    nxt.append(piece)
        pieces = nxt
    return pieces


def _yaw_to_hull(pts: np.ndarray, hull_min, hull_max) -> np.ndarray:
    """Rotation about Z (a multiple of 90 degrees) that best maps the bounds of ``pts`` onto
    the MDL hull box; identity unless a turn fits clearly better."""
    hmin, hmax = np.array(hull_min, np.float64), np.array(hull_max, np.float64)
    if not np.all(hmax > hmin):
        return np.eye(3)
    best, best_err = np.eye(3), None
    for k in range(4):
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][k]
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)
        q = pts @ R.T
        err = float(np.abs(q.min(0) - hmin).sum() + np.abs(q.max(0) - hmax).sum())
        if best_err is None or err < best_err - 4.0:
            best, best_err = R, err
    return best


def _keep_lines(g: np.ndarray, tol: float) -> list[int]:
    """Columns of sample grid ``g`` (rows x cols x 5) to keep: a run of columns is dropped
    when every point in it lies within ``tol`` of the straight line between the kept
    columns on either side, in every row (greedy from column 0)."""
    n = g.shape[1]
    keep = [0]
    for j in range(1, n - 1):
        a, b = keep[-1], j + 1
        for k in range(a + 1, b):
            t = (k - a) / (b - a)
            if np.abs(g[:, k, :3] - ((1 - t) * g[:, a, :3] + t * g[:, b, :3])).max() > tol:
                keep.append(j)
                break
    keep.append(n - 1)
    return keep


def _simplify_grids(grids: list[np.ndarray], tol: float) -> list[np.ndarray]:
    """Drop displacement sample rows/columns that are straight within ``tol`` units.

    Q3map groups patches for LOD by comparing every control point of every patch with
    every control point of every other patch (``PatchMapDrawSurfs``, q3map ``patch.c``),
    so compile time grows with (patches x controls)^2: de_dust2's 619 patches spent 11
    minutes there. Fewer controls per patch cut that quadratically.

    Neighbouring displacements must keep the same vertices on a shared edge or cracks
    open, so the choice is a global fixed point: a line is kept if its own straightness
    test fails *or* any patch keeps a boundary vertex at the position of one of its
    boundary vertices. Texture coordinates are linear in the (flat) sample grid, so
    dropping lines leaves them exact.
    """
    def key(p):
        return (round(float(p[0]) * 4), round(float(p[1]) * 4), round(float(p[2]) * 4))

    keeps = [[set(_keep_lines(g.transpose(1, 0, 2), tol)), set(_keep_lines(g, tol))] for g in grids]  # [rows, cols]

    def kept_boundary(g, rows, cols):
        r, c = g.shape[:2]
        pts = [g[0, j] for j in cols] + [g[r - 1, j] for j in cols] + [g[i, 0] for i in rows] + [g[i, c - 1] for i in rows]
        return {key(p) for p in pts}

    changed = True
    while changed:
        changed = False
        kept = set()
        for g, (rows, cols) in zip(grids, keeps):
            kept |= kept_boundary(g, rows, cols)
        for g, (rows, cols) in zip(grids, keeps):
            r, c = g.shape[:2]
            for j in range(c):
                if j not in cols and (key(g[0, j]) in kept or key(g[r - 1, j]) in kept):
                    cols.add(j)
                    changed = True
            for i in range(r):
                if i not in rows and (key(g[i, 0]) in kept or key(g[i, c - 1]) in kept):
                    rows.add(i)
                    changed = True
    return [g[sorted(rows)][:, sorted(cols)] for g, (rows, cols) in zip(grids, keeps)]


def _split_patch(ctrl: np.ndarray, maxn: int) -> list[np.ndarray]:
    """Split an odd-sized control grid into pieces of at most ``maxn`` (odd) per side,
    sharing border rows/columns so the pieces stay seamless."""
    def spans(m):
        if m <= maxn:
            return [(0, m)]
        out, a = [], 0
        while a < m - 1:
            b = min(a + maxn - 1, m - 1)
            out.append((a, b + 1))
            a = b
        return out
    return [ctrl[r0:r1, c0:c1] for r0, r1 in spans(ctrl.shape[0]) for c0, c1 in spans(ctrl.shape[1])]


def _spread(points: Sequence, count: int) -> list[int]:
    """Indexes of ``count`` of ``points`` spread apart (farthest-point sampling from the
    first), in file order; all of them when there are no more than ``count``."""
    if len(points) <= count:
        return list(range(len(points)))
    p = np.asarray(points, np.float64)
    pick = [0]
    d = np.linalg.norm(p - p[0], axis=1)
    while len(pick) < count:
        i = int(np.argmax(d))
        pick.append(i)
        d = np.minimum(d, np.linalg.norm(p - p[i], axis=1))
    return sorted(pick)


def _ent(cls: str, origin, **keys) -> MEntity:
    e = MEntity({"classname": cls})
    e["origin"] = " ".join(fmt(round(c, 2)) for c in origin)
    for k, v in keys.items():
        e[k] = v
    return e


def convert(bsp_path: str, csgo_dir: str, opt: Options) -> Result:
    return Converter(bsp_path, csgo_dir, opt).run()


def _open_yaw(m: MapFile, eyes, rays: int = 24, reach: float = 2048.0) -> list:
    """For each eye point, the yaw (degrees) of its longest clear horizontal sightline through
    the map's brushes (exact ray/brush clipping: de_rats' vent walls are 2 units thick), or
    ``None`` when no ray gets 16 units."""
    import math as _m
    solids, _ = validate._solids(m)
    if not solids:
        return [None] * len(eyes)
    lo = np.array([s.mins for s in solids])
    hi = np.array([s.maxs for s in solids])

    def free(e, d) -> float:
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1.0 / np.where(np.abs(d) < 1e-12, 1e-12, d)
        t1, t2 = (lo - e) * inv, (hi - e) * inv
        tn = np.minimum(t1, t2).max(axis=1)
        tf = np.maximum(t1, t2).min(axis=1)
        best = reach
        for i in np.nonzero((tn <= tf) & (tf > 0) & (tn < reach))[0]:
            t0, t1_ = 0.0, reach
            for pl in solids[i].planes:
                n = np.asarray(pl.normal)
                denom, dist = float(n @ d), float(n @ e) - pl.dist
                if abs(denom) < 1e-12:
                    if dist > 0:
                        t0, t1_ = 1.0, 0.0
                        break
                    continue
                t = -dist / denom
                if denom < 0:
                    t0 = max(t0, t)
                else:
                    t1_ = min(t1_, t)
            if t0 <= t1_:
                best = min(best, t0)
        return best

    out = []
    for eye in eyes:
        e = np.asarray(eye, np.float64)
        best, best_d = None, 16.0
        for k in range(rays):
            a = 2 * _m.pi * k / rays
            t = free(e, np.array([_m.cos(a), _m.sin(a), 0.0]))
            if t > best_d:
                best, best_d = _m.degrees(a), t
        out.append(best)
    return out


def auto_cameras(m: MapFile, n: int = 9, landmarks=(), spawns: bool = True):
    """Spread-out cameras: each landmark (e.g. bomb site), then a farthest-point sample of spawn
    points (eye height), each looking down its longest clear sightline (spawns face walls in
    vents and corners: de_rats), plus one high overview. ``spawns=False`` keeps only the
    landmarks and the overview."""
    import math as _m
    from .. import game
    spawns = [e for e in m.entities if e.classname in ("info_player_deathmatch", "info_player_allied",
                                                         "info_player_axis")]
    pts = [(e.origin(), float(e.get("angle", "0") or 0)) for e in spawns if e.origin()]
    if pts:
        mx = sum(p[0][0] for p in pts) / len(pts)
        my = sum(p[0][1] for p in pts) / len(pts)
    else:
        mx = my = 0.0
    lm = [((x, y, z), _m.degrees(_m.atan2(my - y, mx - x))) for x, y, z in landmarks]
    spawn_pts = pts
    pts = lm + pts
    chosen: list = list(lm)     # every landmark, then spawns far from what is chosen
    if spawns and pts:
        if not chosen:
            chosen.append(pts[0])
        while len(chosen) < min(n - 1, len(pts)):
            far = max(pts, key=lambda p: min((p[0][0] - c[0][0]) ** 2 + (p[0][1] - c[0][1]) ** 2 for c in chosen))
            chosen.append(far)
    eyes = [(o[0], o[1], o[2] + 82) for o, _ in chosen]
    yaws = _open_yaw(m, eyes) if eyes else []
    cams = [game.Shot(f"site{i}" if i < len(lm) else f"spawn{i - len(lm)}", eye,
                      (5.0, open_yaw if open_yaw is not None else yaw, 0.0))
            for i, ((_, yaw), eye, open_yaw) in enumerate(zip(chosen, eyes, yaws))]
    pts = pts if spawns else lm + spawn_pts
    if pts:
        xs, ys, zs = [p[0][0] for p in pts], [p[0][1] for p in pts], [p[0][2] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1024)
        eye = (min(xs) - span * 0.15, min(ys) - span * 0.15, max(zs) + span * 0.45)
        cams.append(game.Shot.looking_at("overview", eye, (cx, cy, min(zs))))
    return cams


def fade_distance(p) -> float:
    """Where a CS:GO prop stops being drawn, in Source units (0: never). Source fades a prop
    (flag 1, ``fademindist``/``fademaxdist``) from opaque at the min distance to gone at the
    max, by its distance from the eye; MOHAA cuts it at the midpoint (``mohkit.lod`` vanish)."""
    fmax = float(getattr(p, "fade_max", 0) or 0)
    if not (int(getattr(p, "flags", 0) or 0) & 1) or fmax <= 0:
        return 0.0
    fmin = float(getattr(p, "fade_min", -1) or -1)
    return (fmin + fmax) / 2 if 0 < fmin < fmax else fmax


def inject_statics(bsp_path, statics, assets: dict, out, prop_light: Optional[list] = None,
                   exposure: Optional[float] = None, gains: Optional[dict] = None,
                   tint_mask: Optional[dict] = None, lod: bool = True, lod_tau: Optional[float] = None,
                   lod_base_error: Optional[float] = None, merge_split: Optional[Sequence[float]] = None) -> dict:
    """Add the converter's props (``Result.statics``) to a lit BSP as static models
    (``mohkit.staticlight``); meshes are read from ``assets``. Over
    ``staticmerge.DEFAULT_TARGET`` props, nearby copies of a model are merged into one model
    (engine limit 4,095); the merged models' files are added to ``assets``.

    With ``exposure`` (the BSP carries CS:GO's transferred lightmaps), props with CS:GO's
    own vertex lighting (``prop_light``, VRAD byte scale) get it through the same tone curve
    as the lightmaps, and the others are lit from the lightmaps at vertex scale 1.0;
    otherwise every prop is lit from MOHlight's lightmaps and grid. With ``lod``, every SKD
    the final props load gets progressive LOD (``mohkit.lod``; vertex colours follow the new
    vertex order). ``merge_split`` = (radius, cell): instances of models bigger than radius are
    cut into pieces merged in cells of that size (``staticmerge.merge`` split_radius)."""
    from .. import staticlight as SL, staticmerge
    from .lighting import tonemap
    read = SL.files_reader(assets)
    meshes: dict = {}
    vgain: dict = {}
    inst = []
    light = list(prop_light or [])
    gains = gains or {}
    used = 0
    tints = []
    tint_mask = tint_mask or {}
    vtint: dict = {}
    for k, (mk, origin, angles, scale, *_rest) in enumerate(statics):
        if mk not in meshes:
            meshes[mk] = SL.tiki_mesh(read, mk)
            g = np.ones(len(meshes[mk][0]))
            w = np.ones(len(g))
            if gains or tint_mask:
                try:
                    parts = staticmerge.tiki_parts(read, mk)
                    if sum(len(s.positions) for s, _ in parts) == len(g):
                        g = np.concatenate([np.full(len(s.positions), gains.get(sh, 1.0)) for s, sh in parts])
                        w = np.concatenate([np.full(len(s.positions), tint_mask.get(sh, 1.0)) for s, sh in parts])
                except (FileNotFoundError, ValueError):
                    pass
            vgain[mk] = g
            vtint[mk] = w
        pos, nrm = meshes[mk]
        if not len(pos):
            continue
        col = None
        if exposure is not None and k < len(light) and light[k] is not None and len(light[k]) == len(pos):
            lin = (np.asarray(light[k], np.float64) / 127.5) ** 2.2
            col = tonemap(lin, exposure, ceiling=vgain[mk])
            used += 1
        inst.append(SL.StaticInstance(mk, origin, angles, scale, pos, nrm, col,
                                      fade=float(_rest[1]) if len(_rest) > 1 and _rest[1] else 0.0))
        tints.append(_rest[0] if _rest and _rest[0] is not None else None)
    if exposure is not None:
        # props without CS:GO's vertex light: the lightmaps at the vertex (texture scale), divided
        # by the gain of each vertex's texture like the VRAD-lit ones
        from ..bsp import BSP as _BSP
        todo = [i for i in inst if i.colors is None]
        if todo:
            field = SL.LightmapField(_BSP(Path(bsp_path)))
            for i, rgb in zip(todo, SL.field_colours(field, todo)):
                bad = np.isnan(rgb[:, 0])
                if bad.all():
                    rgb[:] = 48.0
                elif bad.any():
                    rgb[bad] = np.nanmedian(rgb[~bad], axis=0)
                i.colors = np.clip(rgb / vgain[i.model][:, None], 0, 255)
        for i, t in zip(inst, tints):
            if t is not None and tuple(t) != (255, 255, 255) and i.colors is not None:
                w = vtint[i.model][:, None]
                i.colors = i.colors * (1.0 - w + w * (np.asarray(t, np.float64) / 255.0)[None, :])
    split = dict(split_radius=float(merge_split[0]), split_cell=float(merge_split[1])) if merge_split else {}
    inst, files, merged = staticmerge.merge(inst, read, f"models/csgo/m_{Path(out).stem}", **split)
    assets.update(files)
    if files:
        merged["pruned"] = staticmerge.prune(assets, {mk for mk, *_ in statics}, {i.model for i in inst}, read)
    lod_info = None
    if lod:
        from .. import lod as _lod
        cols: dict = {}
        for i in inst:
            cols.setdefault(i.model, []).append(i.colors)
        perms = _lod.apply_to_assets(assets, [i.model for i in inst], SL.files_reader(assets),
                                     vanish=_lod.vanish_by_tiki(inst), tau=lod_tau or _lod.TAU_PX,
                                     base_error=lod_base_error or _lod.FREE_ERROR, colors=cols)
        for i in inst:
            pm = perms.get(i.model)
            if pm is not None and len(pm) == len(i.positions):
                i.positions, i.normals = i.positions[pm], i.normals[pm]
                if i.colors is not None:
                    i.colors = np.asarray(i.colors)[pm]
        lod_info = {"skds": sum(1 for k in assets if k.endswith(".lod")), "tikis_reordered": len(perms),
                    "fading_instances": sum(1 for i in inst if i.fade > 0)}
    info = SL.inject(bsp_path, inst, out, field_scale=1.0 if exposure is not None else SL.LIGHTMAP_TO_VERTEX)
    info["merge"] = merged
    info["lod"] = lod_info
    info["csgo_vertex_light"] = used
    return info


_CAMERA_RE = re.compile(r'"([^"]+)"\s+"\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*"')


def named_cameras(path, scale: float = 1.0):
    """Spectator viewpoints from a CS:GO ``maps/<map>_cameras.txt``.

    The file is KeyValues: ``"Cameras" { "T Spawn" "x y z pitch yaw" ... }`` where x y z
    is the eye position in Source units (``spec_pos`` output) and pitch/yaw follow the
    Quake convention MOHAA shares (positive pitch looks down). Returns ``game.Shot``s
    named after the entries, in file order.
    """
    from .. import game
    text = Path(path).read_text(encoding="latin-1", errors="replace")
    text = re.sub(r"//[^\n]*", "", text)
    out = []
    for m in _CAMERA_RE.finditer(text):
        x, y, z, pitch, yaw = (float(v) for v in m.groups()[1:])
        out.append(game.Shot(m.group(1).strip(), (x * scale, y * scale, z * scale), (pitch, yaw, 0.0)))
    return out


def finish_local(name: str, src: Path, compiled_bsp: Path, assets: dict, statics: list, map_: MapFile,
                 convert_report: dict, test: bool = True, shots: int = 9, scale: float = 1.0, log=print,
                 prop_light: Optional[list] = None, lighting: str = "csgo", exposure: Optional[float] = None,
                 lod: bool = True) -> dict:
    """After a compile: light it (``lighting="csgo"``: CS:GO's own baked lighting moved into
    the lightmaps, light grid and props, ``mohkit.source.lighting``; ``"mohlight"``: keep
    MOHlight's), inject the static props, package ``local/csgo/<name>/<name>.pk3`` and
    (optionally) shoot the contact sheet. ``build_local`` calls it; ``resume_local`` runs it on
    the files a build left on disk (after re-running a stage by hand)."""
    import json

    from .. import config, game, project
    out = config.REPO / "local" / "csgo" / name
    report: dict = {}
    # the compile root keeps the BSP as compiled (props-only updates re-inject into it)
    lit = out / f"{name}.bsp"
    base = Path(compiled_bsp)
    gains = dict(convert_report.get("texture_gain") or {})
    divided = None
    if lighting == "csgo":
        from . import lighting as _lighting
        info = _lighting.transfer(compiled_bsp, SourceBSP(str(src)), lit, scale=scale, log=log, gains=gains,
                                  offset=convert_report.get("offset") or (0, 0, 0), exposure=exposure,
                                  sky_room=convert_report.get("sky_room"))
        divided = info.pop("divided_lightmaps", None)
        report["lighting"] = info
        exposure = info["exposure"]
        base = lit
    if convert_report.get("blend"):
        from ..bsp import BSP as _BSP
        from ..staticlight import write_lumps
        from .lighting import blend_alphas
        b = _BSP(base)
        write_lumps(b, {"drawverts": blend_alphas(b, SourceBSP(str(src)), convert_report["blend"], scale,
                                                  convert_report.get("offset") or (0, 0, 0),
                                                  convert_report.get("sky_room"),
                                                  convert_report.get("blend_mod"))}, lit)
        base = lit
    bsp_bytes = base.read_bytes()
    if statics:
        info = inject_statics(base, statics, assets, lit, prop_light, exposure, gains,
                              convert_report.get("tint_mask"), lod=lod, lod_tau=convert_report.get("lod_tau"),
                              lod_base_error=convert_report.get("lod_base_error"),
                              merge_split=convert_report.get("merge_split"))
        report["statics"] = info
        log(f"== static models injected: {json.dumps(info)}")
        from ..staticmerge import DEFAULT_MAX_SKD
        skd = (info.get("merge") or {}).get("skd", 0)
        if skd > DEFAULT_MAX_SKD:
            # split pieces always merge, so the budget can't pull them back: de_nuke with
            # 512-unit piece cells had 678 prop SKDs (768: 597); past the 1,024-SKD skeleton
            # cache (shared with players and weapons) props never load
            log(f"!! {skd} prop SKDs, over the {DEFAULT_MAX_SKD} budget: props may not load"
                f" ('No free spots open in skel cache'); use a larger split cell (merge_split)")
        bsp_bytes = lit.read_bytes()
    if divided is not None:
        # the BSP so far holds the light at texture scale (the light grid and the props were
        # sampled from it); surfaces whose texture was brightened get it divided by that gain
        from ..bsp import BSP as _BSP
        from ..staticlight import write_lumps
        write_lumps(_BSP(lit), {"lightmaps": divided}, lit)
        bsp_bytes = lit.read_bytes()
    proj = project.Project(name=name, folder=out, title=src.stem, ambience="mohdm2",
                           precache=list(convert_report.get("precache", ())))
    files = {f"maps/dm/{name}.bsp": bsp_bytes, **proj.scripts(),
             **{k: (v if isinstance(v, bytes) else Path(v).read_bytes()) for k, v in assets.items()}}
    pk3 = out / f"{name}.pk3"
    from ..pak import unowned_paths
    shared = unowned_paths(files, name, SHARED_PATHS)
    if shared:
        # another installed map can hold the same path with other contents: one copy wins
        # for every map (pak.path_clashes; builds before 2026-10-02 shared all prop files)
        report["unowned_paths"] = len(shared)
        log(f"== WARNING: {len(shared)} packaged files are not under the map's name and can clash with"
            f" another installed map's (rebuild without --resume): {shared[:5]}")
    pairs = sorted({k[:-4] for k in files if k.lower().endswith(".jpg")} & {k[:-4] for k in files if k.lower().endswith(".tga")})
    if pairs:
        log(f"== WARNING: {len(pairs)} images exist as both .jpg and .tga (the .jpg wins in game): {pairs[:5]}")
    project.write_pk3(pk3, files)
    report["pk3"] = str(pk3)
    log(f"== packaged {pk3} ({pk3.stat().st_size // 1024} KB)")
    if test:
        # CS:GO ships named spectator viewpoints for most maps (maps/<map>_cameras.txt);
        # they cover every callout, so prefer them to spawn samples. With named cameras only
        # the overview is added (landmark shots stand inside the bomb-site props).
        cams = map_cameras(src, map_, convert_report.get("landmarks", ()), shots, scale,
                           convert_report.get("offset") or (0, 0, 0))
        report.update(shoot(name, pk3, cams, out, log=log))
    return report


def shoot(name: str, pk3: Path, cams, out: Path, log=print) -> dict:
    """Screenshot ``pk3`` from ``cams``: contact sheets ``<out>/<name>_shots*.png``, the
    full-size shots in ``<out>/shots/`` and their exposure (``mohkit.exposure``) in
    ``<out>/exposure.json``."""
    import shutil

    from .. import exposure, game
    run = game.run([pk3], f"dm/{name}", cams, run_name=name, timeout=300 + 3 * len(cams))
    sheets = game.contact_sheets(run.screenshots, out / f"{name}_shots.png")
    shots = out / "shots"
    if shots.is_dir():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)
    for k, p in run.screenshots.items():
        shutil.copy2(p, shots / Path(p).name)
    rows = exposure.measure_all(exposure.groups_in([shots]).get(name, {}))
    exposure.save(rows, out / "exposure.json", name)
    log(run.summary())
    log(exposure.table(rows))
    log(f"== contact sheet {sheets[0] if sheets else None}")
    return {"contact_sheet": str(sheets[0]) if sheets else None, "contact_sheets": [str(p) for p in sheets],
            "run_problems": run.problems, "exposure": exposure.summary(rows, name)}


def map_cameras(src: Path, map_: MapFile, landmarks=(), shots: int = 9, scale: float = 1.0, offset=(0, 0, 0)) -> list:
    """The cameras a conversion is shot from: CS:GO's named spectator viewpoints
    (``maps/<map>_cameras.txt``, moved by the conversion's ``offset``) plus an overview, or
    spread-out spawn cameras."""
    cam_file = src.with_name(src.stem + "_cameras.txt")
    named = named_cameras(cam_file, scale) if cam_file.is_file() else []
    for c in named:
        c.origin = tuple(c.origin[i] + float(offset[i]) for i in range(3))
    return named + auto_cameras(map_, 1 if named else shots, () if named else landmarks, spawns=not named)


def _local_cameras(map_name: str, name: Optional[str] = None, scale: float = 1.0) -> tuple[str, Path, list]:
    """(name, ``local/csgo/<name>``, cameras) of the last conversion of ``map_name``."""
    import json

    from .. import config
    cfg = config.load()
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    prev = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else {}
    cams = map_cameras(src, MapFile.load(str(out / f"{name}.map")), prev.get("convert", {}).get("landmarks", ()),
                       scale=scale, offset=prev.get("convert", {}).get("offset") or (0, 0, 0))
    return name, out, cams


def shoot_local(map_name: str, name: Optional[str] = None, scale: float = 1.0, log=print) -> dict:
    """Re-shoot the packaged ``local/csgo/<name>/<name>.pk3`` from its cameras (no rebuild)."""
    name, out, cams = _local_cameras(map_name, name, scale)
    return shoot(name, out / f"{name}.pk3", cams, out, log=log)


def ab_local(map_name: str, a: list, b: list, name: Optional[str] = None, scale: float = 1.0,
             labels: tuple[str, str] = ("A", "B"), out: Optional[Path] = None, shots: bool = True,
             perf_ms: int = 0, rounds: int = 2, cvars: Optional[dict] = None, log=print) -> dict:
    """Two pk3 sets at a conversion's cameras, into ``local/csgo/<name>/ab/`` unless ``out``:
    what changed in the shots (``game.shots_ab``) and, with ``perf_ms``, interleaved frame
    rates (``game.perf_ab``)."""
    from .. import game
    name, base, cams = _local_cameras(map_name, name, scale)
    out = Path(out) if out else base / "ab"
    res: dict = {}
    if shots:
        res["shots"] = game.shots_ab(a, b, f"dm/{name}", cams, out, labels, cvars=cvars, log=log)
    if perf_ms:
        res["perf"] = game.perf_ab(a, b, f"dm/{name}", cams, out, labels, rounds, perf_ms, cvars=cvars, log=log)
    return res


def perf_local(map_name: str, name: Optional[str] = None, scale: float = 1.0, ms: int = 3000,
               toggles=(), pk3: Optional[Path] = None, label: str = "perf", log=print) -> dict:
    """Frame times of the packaged ``local/csgo/<name>/<name>.pk3`` (or ``pk3``) at its
    cameras (``game.perf_commands``): ``<out>/<label>.json`` and a table."""
    import json

    from .. import config, game
    cfg = config.load()
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    prev = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else {}
    cams = map_cameras(src, MapFile.load(str(out / f"{name}.map")), prev.get("convert", {}).get("landmarks", ()),
                       scale=scale, offset=prev.get("convert", {}).get("offset") or (0, 0, 0))
    run = game.run([Path(pk3) if pk3 else out / f"{name}.pk3"], f"dm/{name}", cams, run_name=f"{name}_{label}",
                   perf_ms=ms, perf_toggles=toggles, screenshots=False)
    (out / f"{label}.json").write_text(json.dumps(run.perf, indent=1))
    log(run.summary())
    log(game.perf_table(run.perf))
    return run.perf


def save_prop_light(path: Path, light: list) -> None:
    """``Result.prop_light`` (per static: uint8 N x 3 or None) as one npz."""
    starts = np.full(len(light), -1, np.int64)
    parts, k = [], 0
    for i, c in enumerate(light):
        if c is not None:
            starts[i] = k
            parts.append(np.asarray(c, np.uint8))
            k += len(c)
    lengths = np.array([len(c) if c is not None else 0 for c in light], np.int64)
    colors = np.concatenate(parts) if parts else np.zeros((0, 3), np.uint8)
    np.savez_compressed(path, starts=starts, lengths=lengths, colors=colors)


def load_prop_light(path: Path) -> Optional[list]:
    if not Path(path).is_file():
        return None
    d = np.load(path)
    c = d["colors"]
    return [c[s:s + n] if s >= 0 else None for s, n in zip(d["starts"], d["lengths"])]


def write_assets(out: Path, assets: dict) -> None:
    """Write a conversion's ``assets`` under ``<out>/assets``, delete the files earlier builds
    left there that it no longer has, and list them in ``<out>/assets.json`` (what
    ``resume_local`` packages). A leftover is not harmless: the renderer loads ``x.jpg``
    before ``x.tga`` for either name (``renderergl1/tr_image.c`` R_LoadImage), so an old
    opaque JPG hid every texture that later gained alpha (threshold blends, masked decals)."""
    import json
    root = out / "assets"
    for rel, data in assets.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else Path(data).read_bytes())
    keep = {str(Path(r)) for r in assets}
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and str(p.relative_to(root)) not in keep:
                p.unlink()
    (out / "assets.json").write_text(json.dumps(sorted(keep), indent=0))


def saved_assets(out: Path, log=print) -> dict:
    """``{game path: file}`` of the assets the last build wrote (``assets.json``). Folders
    from before the manifest: every file, keeping only the newer of an ``x.jpg`` / ``x.tga``
    pair (see ``write_assets``)."""
    import json
    root = out / "assets"
    man = out / "assets.json"
    if man.is_file():
        return {rel: root / rel for rel in json.loads(man.read_text()) if (root / rel).is_file()}
    files = {str(p.relative_to(root)): p for p in root.rglob("*") if p.is_file()}
    stems: dict = {}
    for rel, p in files.items():
        if rel.lower().endswith((".jpg", ".tga")):
            stems.setdefault(rel[:-4].lower(), []).append(rel)
    dropped = []
    for rels in stems.values():
        if len(rels) > 1:
            rels.sort(key=lambda r: files[r].stat().st_mtime)
            dropped += rels[:-1]
    for rel in dropped:
        del files[rel]
    if dropped:
        log(f"== assets: {len(dropped)} stale images left out (an older .jpg/.tga of the same name)")
    return files


def resume_local(map_name: str, name: Optional[str] = None, test: bool = True, log=print,
                 exposure: Optional[float] = None, lod: bool = True) -> dict:
    """Finish a build from what it left on disk: ``local/csgo/<name>/`` (map, assets,
    ``statics.json``, ``report.json``) and the compile root's BSP. Use it after re-running
    a stage of the compile by hand (e.g. a light stage that was killed)."""
    import json

    from .. import config
    cfg = config.load()
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    root_bsp = Path(cfg.build_dir) / "roots" / f"dm_{name}" / "main" / "maps" / "dm" / f"{name}.bsp"
    assets = saved_assets(out, log)
    statics = [tuple(x) for x in json.loads((out / "statics.json").read_text())]
    prev = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else {}
    report = dict(prev)
    report.update(finish_local(name, src, root_bsp, assets, statics, MapFile.load(str(out / f"{name}.map")),
                               prev.get("convert", {}), test=test, log=log,
                               scale=float(prev.get("scale", 1.0)), prop_light=load_prop_light(out / "prop_light.npz"),
                               lighting=prev.get("lighting_mode", "csgo"), exposure=exposure, lod=lod))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


def final_checks(map_name: str, name: Optional[str] = None, bots: int = 8, seconds: float = 90,
                 log=print) -> dict:
    """The play checks of a finished conversion (csgo-conversion.md "When a conversion is
    done"), on ``local/csgo/<name>/<name>.pk3``: ``bots`` bots for ``seconds`` (kills), then
    every ladder climbed by ``game.ladder_probe``. Stored as ``report.json["final"]``.
    Never installs."""
    import json

    from .. import game
    name, out, _ = _local_cameras(map_name, name)
    pk3, bsp = out / f"{name}.pk3", out / f"{name}.bsp"
    run = game.run([pk3], f"dm/{name}", (), bots=bots, match_seconds=seconds, run_name=f"{name}_bots",
                   timeout=300 + seconds)
    log(run.summary())
    lads = game.ladder_probe([pk3], f"dm/{name}", game.ladders_for_probe(bsp), run_name=f"ladp_{name}_")
    for r in lads:
        log(f"ladder {r['ok']} climbed {r['climbed']} at {r['origin']} angle {r['angle']}")
    res = {"kills": run.kills, "bots": bots, "seconds": seconds, "bot_run": run.summary().splitlines()[0],
           "ladders": len(lads), "ladders_ok": sum(1 for r in lads if r["ok"]),
           "ladders_failed": [[r["origin"], r["climbed"]] for r in lads if not r["ok"]]}
    rp = out / "report.json"
    rep = json.loads(rp.read_text()) if rp.is_file() else {}
    rep["final"] = res
    rp.write_text(json.dumps(rep, indent=2))
    log(f"== final checks {name}: {res['kills']} kills ({bots} bots, {seconds:g} s), "
        f"ladders {res['ladders_ok']}/{res['ladders']} climb")
    return res


def _ref_ratio(ref_dir: Path, shots_dir: Path) -> tuple[float, int]:
    """Median over the cameras both folders share of reference mean / shot mean (display
    brightness), and the number of cameras. The median ignores a camera or two that look
    at something the conversion lacks (de_inferno's "Construct": the 3D skybox)."""
    from .. import exposure as X
    imgs = (".png", ".jpg", ".tga")
    ref = {p.stem: X.measure(p).mean for p in sorted(ref_dir.iterdir()) if p.suffix.lower() in imgs}
    got = {p.stem: X.measure(p).mean for p in sorted(shots_dir.iterdir()) if p.suffix.lower() in imgs}
    logs = [math.log(ref[k] / got[k]) for k in ref if k in got and ref[k] > 2 and got[k] > 2]
    if not logs:
        raise SystemExit(f"no cameras shared by {ref_dir} and {shots_dir}")
    return math.exp(float(np.median(logs))), len(logs)


def fit_exposure(map_name: str, name: Optional[str] = None, tol: float = 0.02, rounds: int = 3,
                 log=print) -> dict:
    """Fit the exposure of a converted map (CS:GO lighting) to CS:GO's own screenshots of the
    same cameras (``mohkit csgo-ref``): re-light the last build (``resume_local``) until the
    median per-camera brightness ratio is within ``tol`` of 1, and keep the exposure in
    ``data/csgo_exposure.json``, which later builds use instead of the tonemap-controller
    rule (``lighting.exposure_for``). Brightness ~ exposure^(1/2.2) below the roll-off, so
    the first step is ratio^2.2; then secant steps in log space. CS:GO auto-exposes per view
    within the controller's range, so no single value is exact; all seven maps measured
    0.83-0.95x CS:GO's brightness at the range's geometric mean."""
    import json

    from .. import config
    cfg = config.load()
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    ref_dir, shots_dir = out / "csgo_ref", out / "shots"
    if not ref_dir.is_dir():
        raise SystemExit(f"no CS:GO reference shots in {ref_dir} (python -m mohkit csgo-ref {src.stem})")
    rep = json.loads((out / "report.json").read_text())
    e0 = float(rep.get("lighting", {}).get("exposure") or 1.0)
    r0, n = _ref_ratio(ref_dir, shots_dir)
    steps = [{"exposure": e0, "ratio": round(r0, 4)}]
    log(f"== fit exposure {name}: exposure {e0:.3f}, CS:GO / MOHAA brightness {r0:.3f} (median of {n} cameras)")
    e, r = e0, r0
    slope = -1 / 2.2                      # d log(ratio) / d log(exposure)
    for _ in range(rounds):
        if abs(math.log(r)) <= math.log1p(tol):
            break
        e_new = math.exp(math.log(e) - math.log(r) / slope)
        e_new = min(max(e_new, e / 3), e * 3)
        resume_local(str(src), name, test=True, log=lambda *_: None, exposure=e_new)
        r_new, n = _ref_ratio(ref_dir, shots_dir)
        log(f"   exposure {e_new:.3f}: brightness ratio {r_new:.3f}")
        steps.append({"exposure": round(e_new, 4), "ratio": round(r_new, 4)})
        if abs(math.log(e_new) - math.log(e)) > 1e-6:
            s = (math.log(r_new) - math.log(r)) / (math.log(e_new) - math.log(e))
            slope = min(max(s, -1.0), -0.1)
        e, r = e_new, r_new
    best = min(steps, key=lambda st: abs(math.log(st["ratio"])))
    if best["exposure"] != e:         # the last step overshot: re-light with the best one
        resume_local(str(src), name, test=True, log=lambda *_: None, exposure=best["exposure"])
    from .lighting import FITTED_EXPOSURE, exposure_for
    table = json.loads(FITTED_EXPOSURE.read_text()) if FITTED_EXPOSURE.is_file() else {}
    table[src.stem] = {"exposure": round(best["exposure"], 4), "ratio": best["ratio"], "cameras": n,
                       "rule": round(exposure_for(SourceBSP(str(src))), 4)}
    FITTED_EXPOSURE.write_text(json.dumps(dict(sorted(table.items())), indent=1) + "\n")
    log(f"== {name}: exposure {best['exposure']:.3f} (ratio {best['ratio']:.3f}), saved in {FITTED_EXPOSURE}")
    return {"name": name, "steps": steps, "best": best}


def refresh_assets(map_name: str, name: Optional[str] = None, quality: str = "draft", test: bool = True,
                   log=print, lighting: str = "csgo", **opts) -> dict:
    """Re-convert and re-package with the last compile's BSP when only assets changed
    (textures, shader scripts, models): refuses unless the new ``.map`` text equals the
    compiled one exactly. Minutes instead of a full compile."""
    import json

    from .. import config
    cfg = config.load()
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    root_map = Path(cfg.build_dir) / "roots" / f"dm_{name}" / "main" / "maps" / "dm" / f"{name}.map"
    if lighting == "csgo":
        opts.setdefault("lightmap_density", 16)
        opts.setdefault("texlights", False)
        opts.setdefault("headroom", True)
    if quality in ("draft", "unlit", "fastrad"):
        opts.setdefault("props_static_vertices", 0)
        opts.setdefault("lightmap_density", 32)
    log(f"== re-converting {src.name} -> {name} (assets only)")
    res = convert(str(src), cfg.csgo_dir, Options(name=name, **opts))
    if not root_map.is_file() or root_map.read_text(encoding="latin-1") != res.map.dumps():
        raise SystemExit("--refresh-assets: the map changed since the last compile; run a full build")
    write_assets(out, res.assets)
    (out / "statics.json").write_text(json.dumps(res.statics))
    save_prop_light(out / "prop_light.npz", res.prop_light)
    prev = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else {}
    report = dict(prev)
    report["convert"] = res.report
    report.update(finish_local(name, src, root_map.with_suffix(".bsp"), res.assets, res.statics, res.map, res.report,
                               test=test, scale=opts.get("scale", 1.0), log=log, prop_light=res.prop_light,
                               lighting=lighting))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


def build_local(map_name: str, name: Optional[str] = None, quality: str = "draft", test: bool = True,
                shots: int = 9, log=print, props_only: bool = False, lighting: str = "csgo", **opts) -> dict:
    """Convert ``csgo/maps/<map_name>.bsp``, compile, package and (optionally) screenshot it.

    Everything is written under ``local/csgo/<name>/`` (gitignored: it contains
    decoded Valve textures and must not be committed or shared).

    ``props_only`` re-places the runtime props in the last compile (``Q3map -onlyents``,
    seconds instead of up to an hour) and refuses when anything else in the map changed;
    the lighting stays that of the last compile.
    """
    import json
    import math as _m

    from .. import compile as C
    from .. import config, game, project, validate

    cfg = config.load()
    if not cfg.csgo_dir:
        raise SystemExit("CS:GO not found (set MOHKIT_CSGO_DIR)")
    src = Path(map_name)
    if not src.is_file():
        src = Path(cfg.csgo_dir) / "csgo" / "maps" / f"{map_name}.bsp"
    name = name or ("cs_" + src.stem.split("_", 1)[-1] if src.stem.startswith("de_") else src.stem)
    out = config.REPO / "local" / "csgo" / name
    out.mkdir(parents=True, exist_ok=True)
    log(f"== converting {src.name} -> {name}")
    if quality == "unlit":
        lighting = "none"
    if quality in ("draft", "unlit", "fastrad"):
        # MOHlight lights static-model vertices on one thread (~190/s at best; de_dust2's 70k took
        # hours), so "compile" drafts make every prop a runtime script_model unless a budget is given.
        opts.setdefault("props_static_vertices", 0)
        if lighting != "csgo":
            opts.setdefault("lightmap_density", 32)
    if lighting == "csgo":
        # CS:GO's lighting is transferred, not computed: no light entities or texlights for
        # MOHlight, and the lightmap density costs nothing but pages (Source luxels are ~16 units)
        opts.setdefault("lightmap_density", 16)
        opts.setdefault("texlights", False)
        opts.setdefault("headroom", True)
    res = convert(str(src), cfg.csgo_dir, Options(name=name, **opts))
    if props_only:
        from ..mapfile import MapFile, compiled_difference
        prev = out / f"{name}.map"
        diff = compiled_difference(MapFile.load(str(prev)), res.map) if prev.is_file() else "no previous map"
        if diff:
            raise SystemExit(f"--props-only: more than runtime props changed ({diff}); run a full build")
    (out / f"{name}.map").write_text(res.map.dumps(), encoding="latin-1")
    write_assets(out, res.assets)
    log(json.dumps({k: v for k, v in res.report.items() if k != "warnings"}))
    removed = [n for n in res.report.get("spawns_fixed", []) if "removed" in n]
    if removed:
        # validate.fix_spawns drops spawns with no clear spot within 48 units; a tight map at
        # this scale loses some silently otherwise (de_rats lost 4 at --scale 1.0)
        log(f"  WARNING {len(removed)} spawn(s) removed, no clear spot near them: the map may be too "
            f"tight at this scale (try --scale 1.1). " + "; ".join(removed[:4]))
    issues = [i for i in validate.check(res.map) if i.severity == "error"]
    for i in issues:
        log(f"  {i}")
    if props_only:
        log("== updating the entity lump of the last compile (lighting unchanged)")
        cr = C.update_entities(res.map.dumps(), f"dm/{name}")
    elif quality == "unlit":
        # geometry, props, doors and ladders in minutes: no light stage (the game draws the
        # world fullbright) and props get a flat grey instead of light-grid colours
        log("== compiling (unlit: BSP and fast VIS only)")
        cr = C.compile_map(res.map.dumps(), f"dm/{name}", assets=res.assets, quality="draft", light=False,
                           bsp_args=BSP_ARGS)
    elif lighting == "csgo":
        log(f"== compiling ({quality}: BSP and VIS; lighting transferred from CS:GO)")
        cr = C.compile_map(res.map.dumps(), f"dm/{name}", assets=res.assets, quality=quality, light=False,
                           bsp_args=BSP_ARGS)
    else:
        log(f"== compiling ({quality})")
        cr = C.compile_map(res.map.dumps(), f"dm/{name}", assets=res.assets, quality=quality, bsp_args=BSP_ARGS)
    log(cr.summary())
    (out / "statics.json").write_text(json.dumps(res.statics))
    save_prop_light(out / "prop_light.npz", res.prop_light)
    report = {"name": name, "source": str(src), "convert": res.report, "compile_ok": cr.ok, "stats": cr.stats,
              "problems": cr.problems, "lighting_mode": lighting, "scale": opts.get("scale", 1.0)}
    if cr.ok:
        report.update(finish_local(name, src, cr.bsp, res.assets, res.statics, res.map, res.report,
                                   test=test, shots=shots, scale=opts.get("scale", 1.0), log=log,
                                   prop_light=res.prop_light, lighting=lighting))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report
