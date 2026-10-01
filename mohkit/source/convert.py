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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .. import geom
from ..build import _tri_for
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
    light_merge_distance: float = 32.0   # a light this close to a brighter one is folded into it
    # world units per lightmap texel. MOHlight time is roughly proportional to the texel
    # count (de_nuke: ~1M texels at 16), so drafts use 32 (a quarter of the texels).
    lightmap_density: int = 16
    overlays: bool = True           # info_overlay decals -> flat blended patches
    ropes: bool = True              # move_rope/keyframe_rope cables -> crossed ribbon patches
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
    props_static_vertices: int = 70000  # MOHlight's static-model lighting buffer crashes above ~75-81k
    props_runtime_max: int = 600    # extra props as script_model (game entities; engine limit 1024)


@dataclass
class ConvertedMaterial:
    shader: str                     # MOHAA shader name (without textures/)
    image: Optional[str]            # pk3 path of the image
    src_size: tuple[int, int]       # Source texture size (texinfo units)
    size: tuple[int, int]           # written image size
    info: Optional[MaterialInfo] = None
    kind: str = "opaque"            # opaque | alphatest | translucent | sky | tool


@dataclass
class Result:
    map: MapFile
    assets: dict[str, bytes] = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    # props for mohkit.staticlight.inject: (model key, origin, angles, scale), in placement order
    statics: list = field(default_factory=list)


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


def _snap(p, eps=0.01):
    return tuple(round(c) if abs(c - round(c)) < eps else round(c, 4) for c in p)


class Converter:
    def __init__(self, bsp_path: str, csgo_dir: str, opt: Options):
        self.opt = opt
        self.bsp = SourceBSP(bsp_path)
        game = Path(csgo_dir) / "csgo" if (Path(csgo_dir) / "csgo").is_dir() else Path(csgo_dir)
        self.fs = SearchPath(ZipSource(self.bsp.pakfile()), SearchPath.for_game(game))
        self.mapname = Path(bsp_path).stem
        self.prefix = f"csgo/{opt.name}"
        self.mats: dict[str, ConvertedMaterial] = {}
        self.assets: dict[str, bytes] = {}
        self.report: dict = {"dropped": {}, "brushes": 0, "faces": 0, "patches": 0, "materials": 0, "warnings": []}
        self.sky_area = self.bsp.skybox_area()
        self.sky_shader = opt.sky_shader or self._convert_sky()

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
        if rgba is None:
            rgba = np.full((64, 64, 4), (128, 128, 128, 255), np.uint8)
            self.report["warnings"].append(f"material {src}: no texture, grey placeholder")
        cm.kind = "translucent" if info.translucent or info.additive else ("alphatest" if info.alphatest else "opaque")
        if (info.shader or "").lower() == "decalmodulate":
            cm.kind = "modulate"   # multiplies what is under it by 2 x texture (grey 128 = no change)
            # its alpha (when $translucent) says where it applies: fold it into the colour as
            # neutral grey, since the modulate blend has no alpha (black where alpha was 0)
            f = rgba[..., 3:4].astype(np.float32) / 255.0 if info.translucent else 1.0
            rgba = rgba.copy()
            rgba[..., :3] = np.clip(128.0 + (rgba[..., :3].astype(np.float32) - 128.0) * f + 0.5, 0, 255).astype(np.uint8)
        cm.image, cm.size = self._write_image(shader, rgba, cm.kind not in ("opaque", "modulate"))
        self.assets[f"scripts/{self._script_name()}"] = b""  # placeholder, written in finish()
        self.mats[key] = cm
        return cm

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
        im = Image.fromarray(rgba, "RGBA")
        if (tw, th) != (w, h):
            im = im.resize((tw, th), Image.LANCZOS)
        buf = io.BytesIO()
        if alpha:
            path = f"textures/{shader}.tga"
            im.save(buf, "TGA")
        else:
            path = f"textures/{shader}.jpg"
            im.convert("RGB").save(buf, "JPEG", quality=self.opt.texture_quality)
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
        elif cm.kind == "alphatest":
            lines += ["\tsurfaceparm trans", "\tsurfaceparm alphashadow", "\tcull none", "\t{", f"\t\tmap {cm.image}",
                      "\t\talphaFunc GE128", "\t\tdepthWrite", "\tnextbundle", "\t\tmap $lightmap", "\t}"]
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
                # use skybox/nukeblankup, and no nukeblankft.vtf exists
                info = material_info(self.fs, f"skybox/{name}{suffix}{src}")
                tex = info.basetexture if info.found and info.basetexture else f"skybox/{name}{suffix}{src}"
                try:
                    v = load_vtf(self.fs, tex)
                except Exception:  # noqa: BLE001
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
                    drop["entity:disabled"] = drop.get("entity:disabled", 0) + 1
                    continue
                if (ent.get("solidity") or "0") == "1":
                    nonsolid = True
                if (ent.get("rendermode") or "0") == "10":
                    if nonsolid:
                        drop["entity:invisible"] = drop.get("entity:invisible", 0) + 1
                        continue
                    self._invisible_models.add(br.model)
                if cls in BREAKABLE_ENTITIES and self._is_glass(br):
                    # breakable glass -> MOHAA func_window (one entity per Source brush model)
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
            if br.model == 0 and self.sky_area is not None:
                areas = self.bsp.brush_face_areas(br, [w for _, w in geo]) if False else self._areas(br, geo)
                if areas and areas <= {self.sky_area}:
                    drop["skybox3d"] = drop.get("skybox3d", 0) + 1
                    continue
            mb = self._brush(br, geo, kinds, nonsolid, water)
            if mb:
                out.append(mb)
                if water:
                    self.report["water_brushes"] = self.report.get("water_brushes", 0) + 1
        out += self._extra
        self.report["brushes"] = len(out)
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
            out.append(MEntity({"classname": "func_window", "health": str(hp), "debristype": "0"}, brushes))
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
        pieces = [self._brush_piece(br, pc, kinds, nonsolid, water) for pc in _split_long(geo, self.opt.split)]
        pieces = [p for p in pieces if p is not None]
        self._extra.extend(pieces[1:])
        return pieces[0] if pieces else None

    def _brush_piece(self, br: Brush, geo, kinds: set[str], nonsolid: bool, water: bool = False) -> Optional[MBrush]:
        xf = self._xf(br.model)
        hidden = "common/waterskip" if water else CAULK   # caulk is solid: it would fill a water volume
        faces = []
        clip = "common/clip" if "clip" in kinds or "invisible" in kinds or br.model in self._invisible_models else (
            "common/playerclip" if "playerclip" in kinds else None)
        detail = self.opt.detail_all or br.is_detail or br.model > 0
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
                faces.append(Face(tri, self.sky_shader, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            if side.nodraw or not side.is_drawn or not side.material or side.material.lower().startswith("tools/"):
                faces.append(Face(tri, hidden, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            td = self.bsp.texdata[self.bsp.texinfo[side.texinfo]["texdata"]]
            cm = self.material(side.material, (int(td["width"]), int(td["height"])))
            shift, rot, scale = self._texdef(side, n, tri, cm, xf)
            faces.append(Face(tri, cm.shader, shift, rot, scale, 0, 0, 0, list(ext)))
        if len(faces) < 4:
            return None
        self.report["faces"] += len(faces)
        return MBrush(faces)

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
            if self.sky_area is not None and self.bsp.point_area(tuple(o + n * 2)) == self.sky_area:
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
            if cm.kind == "modulate":
                # Source DecalModulate (cracks, grime): dst * 2 * src, lit by the surface below
                lines += ["\t\tblendFunc GL_DST_COLOR GL_SRC_COLOR", "\t\trgbGen identity", "\t}", "}"]
                self._overlay_shaders[name] = "\n".join(lines)
                return name
            if alpha:
                lines.append("\t\tblendFunc blend")
            lines += ["\tnextbundle", "\t\tmap $lightmap", "\t}", "}"]
            self._overlay_shaders[name] = "\n".join(lines)
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
            if self.sky_area is not None and self.bsp.point_area(tuple((a + b) / 2)) == self.sky_area:
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
        return name

    # ------------------------------------------------------------------ doors
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
            try:
                sm = load_studio_model(self.fs, mdl)
            except Exception as ex:  # noqa: BLE001
                self.report["warnings"].append(f"door {mdl}: {ex}")
                continue
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
                continue
            P, UV, M = np.concatenate(P), np.concatenate(UV), np.concatenate(M)
            # Door models carry a rotated root bone: the mesh can lie 90 degrees off the frame
            # the entity angles apply to (metal_door_001_br: mesh along +x, hull and the
            # double-door frames along +y). Turn the mesh so its bounds match the MDL hull.
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
                continue
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
            out.append(MEntity(keys, [MBrush(faces), origin]))
        self.report["doors"] = len(out)
        return out

    # ------------------------------------------------------------------ ladders
    def _solid(self, p) -> bool:
        """Source world contents at ``p`` (Source units) are solid."""
        return bool(int(self.bsp.leafs[self.bsp.point_leaf(p)]["contents"]) & Contents.SOLID)

    def ladders(self) -> list[MEntity]:
        """Source ladder volumes (``CONTENTS_LADDER`` brushes) -> MOHAA ``func_ladder``.

        MOHAA climbs a ``func_ladder`` whose ``origin`` is on the climbable face, centred
        horizontally, with ``angle`` = the direction the climber faces (into the wall); the
        player is held at ``origin - facing * 16`` (docs/reference/engine.md §1.3). The wall
        side is the side of the Source volume with solid world contents behind it, else the
        side a static prop (the visible ladder or its wall supports) is on. Stacked volumes
        of one ladder are merged. The trigger brush covers the Source volume plus 8 units
        on the climber's side.
        """
        s = self.opt.scale
        boxes = []
        for br in self._ladder_src:
            if br.model != 0:  # brush-entity ladders are in model space; Source compiles func_ladder into the world
                self.report["warnings"].append(f"ladder brush {br.index} in model {br.model} skipped")
                continue
            pts = np.array([p for w in br.windings() for p in w], dtype=np.float64)
            if len(pts) < 4:
                continue
            boxes.append([pts.min(0), pts.max(0)])
        # merge stacked pieces (same footprint, vertical gap <= 8)
        boxes.sort(key=lambda b: (round(b[0][0]), round(b[0][1]), b[0][2]))
        merged: list = []
        for lo, hi in boxes:
            for m in merged:
                if (np.abs(m[0][:2] - lo[:2]).max() < 1 and np.abs(m[1][:2] - hi[:2]).max() < 1
                        and lo[2] <= m[1][2] + 8 and hi[2] >= m[0][2] - 8):
                    m[0] = np.minimum(m[0], lo)
                    m[1] = np.maximum(m[1], hi)
                    break
            else:
                merged.append([lo.copy(), hi.copy()])
        props = None
        out: list[MEntity] = []
        for lo, hi in merged:
            ext = hi - lo
            thin = 0 if ext[0] <= ext[1] else 1          # the climb face is perpendicular to the thin axis
            wide = 1 - thin
            c = (lo + hi) / 2
            score = {}
            for sgn in (-1, 1):
                hits = 0
                for d in (2, 4, 8, 12, 16, 24, 32):
                    for z in np.linspace(lo[2] + 4, hi[2] - 4, 5):
                        p = c.copy()
                        p[2] = z
                        p[thin] = (hi[thin] if sgn > 0 else lo[thin]) + sgn * d
                        hits += self._solid(p)
                score[sgn] = hits
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
            # trigger: Source volume + 8 units toward the climber. (Extending it down to the
            # floor stopped a working ladder from mounting: AT_LADDER traces from the eye, and
            # FuncLadder::CanUseLadder / PositionOnLadder work from absmin, fgame/misc.cpp.)
            t_lo, t_hi = lo.copy(), hi.copy()
            if sgn > 0:
                t_lo[thin] = near - 8
            else:
                t_hi[thin] = near + 8
            org = c.copy()
            org[thin] = near
            o_lo, o_hi = org - 1, org + 1
            from ..build import box
            trig = box(tuple(t_lo * s), tuple(t_hi * s), "common/trigger")
            obr = box(tuple(o_lo * s), tuple(o_hi * s), "common/origin")
            yaw = round(math.degrees(math.atan2(facing[1], facing[0]))) % 360
            e = MEntity({"classname": "func_ladder", "angle": str(yaw)}, [trig, obr])
            out.append(e)
            self.report.setdefault("ladders", []).append(
                {"origin": [round(float(v) * s, 1) for v in org], "angle": yaw, "height": round(float(ext[2]) * s),
                 "facing_from": how, "wall_side": [score[-1], score[1]], "far": round(float(far) * s, 1)})
        return out

    # ------------------------------------------------------------------ displacements
    def patches(self) -> list[Patch]:
        out = []
        if not self.opt.displacements:
            return out
        grids: list[tuple[str, np.ndarray]] = []
        for d in self.bsp.displacements():
            flat = d.flat
            n = d.size
            c = d.positions.reshape(-1, 3).mean(axis=0)
            if self.sky_area is not None:
                a = self.bsp.point_area(tuple(c + np.array(d.normal) * 2.0))
                if a == self.sky_area:
                    self.report["dropped"]["skybox3d_disp"] = self.report["dropped"].get("skybox3d_disp", 0) + 1
                    continue
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
        before = sum((2 * g.shape[0] - 1) * (2 * g.shape[1] - 1) for _, g in grids)
        if self.opt.disp_tolerance > 0:
            grids = [(sh, g) for (sh, _), g in zip(grids, _simplify_grids([g for _, g in grids], self.opt.disp_tolerance))]
        for shader, grid in grids:
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
        for e in self.bsp.entities:
            cls = e.classname
            o = e.origin
            if cls in spawns and o is not None:
                yaw = (e.vector("angles", (0, 0, 0)) or (0, 0, 0))[1]
                org = (o[0] * s, o[1] * s, o[2] * s + 1)
                out.append(_ent(spawns[cls], org, angle=fmt(yaw % 360)))
                if not has_dm and cls != "info_deathmatch_spawn":
                    out.append(_ent("info_player_deathmatch", org, angle=fmt(yaw % 360)))
                start = start or org
        if self.opt.lights:
            for e, cls, gain in self._kept_lights():
                out += self._light(e, cls, gain)
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
                  if e.classname in ("light", "light_spot") and e.origin is not None]
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
        intensity = max(40.0, min(600.0, bright * 0.75 * gain)) * self.opt.light_scale
        o = e.origin
        org = (o[0] * s, o[1] * s, o[2] * s)
        le = _ent("light", org, light=fmt(round(intensity)), _color=" ".join(f"{c:.3f}" for c in color))
        out = [le]
        if cls == "light_spot":
            ang = e.vector("angles", (0, 0, 0)) or (0, 0, 0)
            pitch = float(e.get("pitch", ang[0]) or ang[0])
            fwd = (math.cos(math.radians(pitch)) * math.cos(math.radians(ang[1])),
                   math.cos(math.radians(pitch)) * math.sin(math.radians(ang[1])), -math.sin(math.radians(pitch)))
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
        for p in list(sp.props) + self._entity_props():
            if self.sky_area is not None:
                areas = self.bsp.prop_areas(p) if not getattr(p, "entity", False) else {
                    self.bsp.point_area(p.origin)}
                if areas and areas <= {self.sky_area}:
                    continue
            key = (p.model.lower(), p.skin, p.solid if p.solid in (0, 2, 6) else 6)
            if key not in cache:
                try:
                    cache[key] = modelconv.convert_model(self.fs, p.model, prefix="csgo", skin=p.skin, solid=key[2],
                                                         centre=True,
                                                         max_texture=self.opt.max_texture, jpeg_quality=90)
                except Exception as e:  # noqa: BLE001
                    self.report["warnings"].append(f"prop {p.model}: {e}")
                    cache[key] = None
            cm = cache[key]
            if cm is None:
                continue
            sc = (p.uniform_scale or 1.0)
            size = [(cm.bounds[1][i] - cm.bounds[0][i]) * sc for i in range(3)]
            items.append((size[0] * size[1] * size[2], p, cm, sc))
        items.sort(key=lambda t: -t[0])
        static_v, runtime, dropped, injected = 0, 0, 0, 0
        used: dict[str, object] = {}
        self.statics = []
        for _, p, cm, sc in items:
            org = " ".join(fmt(round(c, 2)) for c in self._prop_origin(p, cm, sc * s))
            ang = " ".join(fmt(round(a, 3)) for a in p.angles)
            model_keys = [t[len("models/"):] if t.startswith("models/") else t for t in cm.tiks]
            if self.opt.props_mode == "inject":
                o = tuple(round(c, 2) for c in self._prop_origin(p, cm, sc * s))
                for mk in model_keys:
                    self.statics.append((mk, o, tuple(round(a, 3) for a in p.angles), round(sc * s, 4)))
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
            self.assets.update(modelconv.bundle(used.values(), prefix="csgo", script=f"scripts/csgo_{self.opt.name}_props.shader"))
        self.report["props"] = {"instances": len(items), "static": len(items) - runtime - dropped - injected,
                                "injected": injected, "static_vertices": static_v, "runtime": runtime,
                                "dropped": dropped, "models": len(used)}
        return out, clips, sorted(set(precache))

    PROP_ENTITIES = ("prop_dynamic", "prop_dynamic_override", "prop_physics", "prop_physics_override",
                     "prop_physics_multiplayer")

    def _entity_props(self) -> list:
        """Model entities that stand still in play (``prop_dynamic``, physics props), as
        static-prop-like records. Interactive ones are skipped: a prop another entity's
        outputs target (de_nuke's vent slats, opened by a ``func_button``) or one with
        outputs of its own (``OnBreak``: breakable vent covers), so those openings stay open."""
        from types import SimpleNamespace
        targeted: set[str] = set()
        for e in self.bsp.entities:
            for k, v in e.items():
                if k.lower().startswith("on"):
                    targeted.add(re.split(r"[,\x1b]", v, 1)[0].strip().lower())
        out = []
        skipped = 0
        for e in self.bsp.entities:
            if e.classname not in self.PROP_ENTITIES or not e.get("model") or e.origin is None:
                continue
            if any(k.lower().startswith("on") for k, _ in e.items()) or (
                    e.get("targetname") and e.get("targetname").lower() in targeted):
                skipped += 1
                continue
            try:
                solid = int(float(e.get("solid", "6") or 6))
                skin = int(float(e.get("skin", "0") or 0))
                scale = float(e.get("modelscale", "1") or 1)
            except ValueError:
                solid, skin, scale = 6, 0, 1.0
            out.append(SimpleNamespace(model=e.get("model"), origin=e.origin,
                                       angles=e.vector("angles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0),
                                       skin=skin, solid=solid, uniform_scale=scale, entity=True))
        self.report["entity_props"] = {"converted": len(out), "interactive_skipped": skipped}
        return out

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

    def run(self) -> Result:
        brushes = self.brushes()
        patches = self.patches()
        overlay_patches = self.overlays() + self.ropes()
        self.statics: list = []
        prop_ents, prop_clips, precache = self.props() if self.opt.props else ([], [], [])
        world = MEntity(self.worldspawn())
        world.prims = list(brushes) + list(patches) + overlay_patches + prop_clips
        if self.opt.detail_all:
            world.prims = self.shell(brushes, patches) + world.prims
        ents = [world] + self.entities() + self.ladders() + self.windows() + self.doors() + prop_ents
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
        return Result(MapFile(ents), self.assets, self.report, list(self.statics))


class _CutWinding(list):
    """Winding of a face created by a grid cut (no Source side); carries its plane normal."""
    normal: tuple = (0.0, 0.0, 0.0)


def _split_long(geo, grid: float):
    """Split a convex brush, given as [(side, winding)], at multiples of ``grid`` along X and Y
    when it is longer than ``grid``. Cut faces come back as (None, _CutWinding)."""
    if not grid:
        return [geo]
    pts = [p for _, w in geo for p in w]
    (x0, y0, _), (x1, y1, _) = geom.bounds_of(pts)
    pieces = [geo]
    for ax, lo, hi in ((0, x0, x1), (1, y0, y1)):
        if hi - lo <= grid:
            continue
        cuts = [k * grid for k in range(math.floor(lo / grid) + 1, math.ceil(hi / grid))]
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


def _ent(cls: str, origin, **keys) -> MEntity:
    e = MEntity({"classname": cls})
    e["origin"] = " ".join(fmt(round(c, 2)) for c in origin)
    for k, v in keys.items():
        e[k] = v
    return e


def convert(bsp_path: str, csgo_dir: str, opt: Options) -> Result:
    return Converter(bsp_path, csgo_dir, opt).run()


def auto_cameras(m: MapFile, n: int = 9, landmarks=(), spawns: bool = True):
    """Spread-out cameras: each landmark (e.g. bomb site, looking toward the map centre), then a
    farthest-point sample of spawn points (eye height, spawn facing), plus one high overview.
    ``spawns=False`` keeps only the landmarks and the overview."""
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
    chosen: list = []
    if not spawns:
        chosen = list(lm)
    elif pts:
        chosen.append(pts[0])
        while len(chosen) < min(n - 1, len(pts)):
            far = max(pts, key=lambda p: min((p[0][0] - c[0][0]) ** 2 + (p[0][1] - c[0][1]) ** 2 for c in chosen))
            chosen.append(far)
    cams = [game.Shot(f"spawn{i}", (o[0], o[1], o[2] + 82), (5.0, yaw, 0.0)) for i, (o, yaw) in enumerate(chosen)]
    pts = pts if spawns else lm + spawn_pts
    if pts:
        xs, ys, zs = [p[0][0] for p in pts], [p[0][1] for p in pts], [p[0][2] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1024)
        eye = (min(xs) - span * 0.15, min(ys) - span * 0.15, max(zs) + span * 0.45)
        cams.append(game.Shot.looking_at("overview", eye, (cx, cy, min(zs))))
    return cams


def inject_statics(bsp_path, statics, assets: dict, out) -> dict:
    """Add the converter's props (``Result.statics``) to a lit BSP as static models coloured
    from its light grid (``mohkit.staticlight``); meshes are read from ``assets``."""
    from .. import staticlight as SL
    read = SL.files_reader(assets)
    meshes: dict = {}
    inst = []
    for mk, origin, angles, scale in statics:
        if mk not in meshes:
            meshes[mk] = SL.tiki_mesh(read, mk)
        pos, nrm = meshes[mk]
        if len(pos):
            inst.append(SL.StaticInstance(mk, origin, angles, scale, pos, nrm))
    return SL.inject(bsp_path, inst, out)


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
                 convert_report: dict, test: bool = True, shots: int = 9, scale: float = 1.0, log=print) -> dict:
    """After a compile: inject the static props, package ``local/csgo/<name>/<name>.pk3`` and
    (optionally) shoot the contact sheet. ``build_local`` calls it; ``resume_local`` runs it on
    the files a build left on disk (after re-running a stage by hand)."""
    import json

    from .. import config, game, project
    out = config.REPO / "local" / "csgo" / name
    report: dict = {}
    bsp_bytes = Path(compiled_bsp).read_bytes()
    if statics:
        # the compile root keeps the BSP as compiled (props-only updates re-inject into it)
        lit = out / f"{name}.bsp"
        info = inject_statics(compiled_bsp, statics, assets, lit)
        report["statics"] = info
        log(f"== static models injected: {json.dumps(info)}")
        bsp_bytes = lit.read_bytes()
    proj = project.Project(name=name, folder=out, title=src.stem, ambience="mohdm2",
                           precache=list(convert_report.get("precache", ())))
    files = {f"maps/dm/{name}.bsp": bsp_bytes, **proj.scripts(), **assets}
    pk3 = out / f"{name}.pk3"
    project.write_pk3(pk3, files)
    report["pk3"] = str(pk3)
    log(f"== packaged {pk3} ({pk3.stat().st_size // 1024} KB)")
    if test:
        # CS:GO ships named spectator viewpoints for most maps (maps/<map>_cameras.txt);
        # they cover every callout, so prefer them to spawn samples.
        cam_file = src.with_name(src.stem + "_cameras.txt")
        named = named_cameras(cam_file, scale) if cam_file.is_file() else []
        # with named cameras only the overview is added (landmark shots stand inside the
        # bomb-site props)
        cams = auto_cameras(map_, 1 if named else shots, () if named else convert_report.get("landmarks", ()),
                            spawns=not named)
        cams = named + cams
        run = game.run([pk3], f"dm/{name}", cams, run_name=name, timeout=300 + 3 * len(cams))
        sheets = game.contact_sheets(run.screenshots, out / f"{name}_shots.png")
        report["contact_sheet"] = str(sheets[0]) if sheets else None
        report["contact_sheets"] = [str(p) for p in sheets]
        report["run_problems"] = run.problems
        log(run.summary())
        log(f"== contact sheet {report['contact_sheet']}")
    return report


def resume_local(map_name: str, name: Optional[str] = None, test: bool = True, log=print) -> dict:
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
    assets = {str(p.relative_to(out / "assets")): p for p in (out / "assets").rglob("*") if p.is_file()}
    statics = [tuple(x) for x in json.loads((out / "statics.json").read_text())]
    prev = json.loads((out / "report.json").read_text()) if (out / "report.json").is_file() else {}
    report = dict(prev)
    report.update(finish_local(name, src, root_bsp, assets, statics, MapFile.load(str(out / f"{name}.map")),
                               prev.get("convert", {}), test=test, log=log))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


def build_local(map_name: str, name: Optional[str] = None, quality: str = "draft", test: bool = True,
                shots: int = 9, log=print, props_only: bool = False, **opts) -> dict:
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
    if quality in ("draft", "unlit", "fastrad"):
        # MOHlight lights static-model vertices on one thread (~190/s at best; de_dust2's 70k took
        # hours), so "compile" drafts make every prop a runtime script_model unless a budget is given.
        opts.setdefault("props_static_vertices", 0)
        opts.setdefault("lightmap_density", 32)
    res = convert(str(src), cfg.csgo_dir, Options(name=name, **opts))
    if props_only:
        from ..mapfile import MapFile, compiled_difference
        prev = out / f"{name}.map"
        diff = compiled_difference(MapFile.load(str(prev)), res.map) if prev.is_file() else "no previous map"
        if diff:
            raise SystemExit(f"--props-only: more than runtime props changed ({diff}); run a full build")
    (out / f"{name}.map").write_text(res.map.dumps(), encoding="latin-1")
    for rel, data in res.assets.items():
        p = out / "assets" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    log(json.dumps({k: v for k, v in res.report.items() if k != "warnings"}))
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
    else:
        log(f"== compiling ({quality})")
        cr = C.compile_map(res.map.dumps(), f"dm/{name}", assets=res.assets, quality=quality, bsp_args=BSP_ARGS)
    log(cr.summary())
    (out / "statics.json").write_text(json.dumps(res.statics))
    report = {"name": name, "source": str(src), "convert": res.report, "compile_ok": cr.ok, "stats": cr.stats,
              "problems": cr.problems}
    if cr.ok:
        report.update(finish_local(name, src, cr.bsp, res.assets, res.statics, res.map, res.report,
                                   test=test, shots=shots, scale=opts.get("scale", 1.0), log=log))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report
