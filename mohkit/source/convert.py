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

DROP_KINDS = {"hint", "skip", "areaportal", "occluder", "trigger", "origin", "fog", "skyfog", "blocklight", "blocklos",
              "blockbomb", "team1", "team2", "grenadeclip", "npcclip", "water", "slime", "ladder"}
KEEP_ENTITY_BRUSHES = {"func_brush", "func_wall", "func_detail", "func_breakable", "func_breakable_surf",
                       "func_illusionary", "func_door", "func_door_rotating", "func_rotating", "func_movelinear",
                       "func_wall_toggle", "func_physbox", "func_lod"}
NONSOLID_ENTITIES = {"func_illusionary"}

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
    light_scale: float = 1.0
    sky_shader: Optional[str] = None  # override (e.g. "sky/mohday2"); default converts the Source sky
    texture_quality: int = 90       # JPEG quality for opaque textures
    split: float = 1024.0           # cut brushes longer than this on a world grid (renderer 64-vertex face limit)
    props: bool = True              # convert static props (mohkit.source.modelconv)
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
        if len("textures/" + name) > 60:
            h = hashlib.md5(base.encode()).hexdigest()[:6]
            tail = base.rsplit("/", 1)[-1][: 60 - len("textures/" + self.prefix) - 9]
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
        if tex:
            try:
                rgba = load_vtf(self.fs, tex).decode()
            except Exception as e:  # noqa: BLE001
                self.report["warnings"].append(f"texture {tex}: {e}")
        if rgba is None:
            rgba = np.full((64, 64, 4), (128, 128, 128, 255), np.uint8)
            self.report["warnings"].append(f"material {src}: no texture, grey placeholder")
        cm.kind = "translucent" if info.translucent or info.additive else ("alphatest" if info.alphatest else "opaque")
        cm.image, cm.size = self._write_image(shader, rgba, cm.kind != "opaque")
        self.assets[f"scripts/{self._script_name()}"] = b""  # placeholder, written in finish()
        self.mats[key] = cm
        return cm

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
                try:
                    v = load_vtf(self.fs, f"skybox/{name}{suffix}{src}")
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
            kinds = br.tool_kinds
            if kinds & DROP_KINDS:
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
            mb = self._brush(br, geo, kinds, nonsolid)
            if mb:
                out.append(mb)
        out += self._extra
        self.report["brushes"] = len(out)
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

    def _brush(self, br: Brush, geo, kinds: set[str], nonsolid: bool) -> Optional[MBrush]:
        pieces = [self._brush_piece(br, pc, kinds, nonsolid) for pc in _split_long(geo, self.opt.split)]
        pieces = [p for p in pieces if p is not None]
        self._extra.extend(pieces[1:])
        return pieces[0] if pieces else None

    def _brush_piece(self, br: Brush, geo, kinds: set[str], nonsolid: bool) -> Optional[MBrush]:
        xf = self._xf(br.model)
        faces = []
        clip = "common/clip" if "clip" in kinds or "invisible" in kinds else (
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
                faces.append(Face(tri, CAULK, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            if side.surface_flags & (Surf.SKY | Surf.SKY2D):
                faces.append(Face(tri, self.sky_shader, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
                continue
            if side.nodraw or not side.is_drawn or not side.material or side.material.lower().startswith("tools/"):
                faces.append(Face(tri, CAULK, (0, 0), 0, (1, 1), 0, 0, 0, list(ext)))
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
            elif cls in ("light", "light_spot") and self.opt.lights and o is not None:
                out += self._light(e, cls)
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

    def _light(self, e, cls) -> list[MEntity]:
        s = self.opt.scale
        v = (e.get("_light") or "255 255 255 200").split()
        try:
            r, g, b = (float(x) / 255 for x in v[:3])
            bright = float(v[3]) if len(v) > 3 else 200.0
        except ValueError:
            return []
        mx = max(r, g, b, 1e-3)
        color = (r / mx, g / mx, b / mx)
        intensity = max(40.0, min(600.0, bright * 0.75)) * self.opt.light_scale
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
                              "ambientlight": "10 10 12", "lightmapdensity": "16"}
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
                    ws["sundiffusecolor"] = f"{ar * 60:.0f} {ag * 60:.0f} {ab * 60:.0f}"
                    ws["sundiffuse"] = "1"
                except ValueError:
                    pass
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
        for p in sp.props:
            if self.sky_area is not None:
                areas = self.bsp.prop_areas(p)
                if areas and areas <= {self.sky_area}:
                    continue
            key = (p.model.lower(), p.skin, p.solid if p.solid in (0, 2, 6) else 6)
            if key not in cache:
                try:
                    cache[key] = modelconv.convert_model(self.fs, p.model, prefix="csgo", skin=p.skin, solid=key[2],
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
        static_v, runtime, dropped = 0, 0, 0
        used: dict[str, object] = {}
        for _, p, cm, sc in items:
            org = " ".join(fmt(round(c * s, 2)) for c in p.origin)
            ang = " ".join(fmt(round(a, 3)) for a in p.angles)
            model_keys = [t[len("models/"):] if t.startswith("models/") else t for t in cm.tiks]
            if static_v + cm.vertices <= self.opt.props_static_vertices:
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
        self.report["props"] = {"instances": len(items), "static": len(items) - runtime - dropped,
                                "static_vertices": static_v, "runtime": runtime, "dropped": dropped,
                                "models": len(used)}
        return out, clips, sorted(set(precache))

    def _prop_clips(self, cm, p, scale: float) -> list[MBrush]:
        """The model's collision .map brushes placed in the world (origin + scale*R(angles)*p)."""
        text = cm.files.get(cm.tik[:-4] + ".map")
        if not text:
            return []
        R = self._rot(p.angles)
        o = [c * self.opt.scale for c in p.origin]
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
        prop_ents, prop_clips, precache = self.props() if self.opt.props else ([], [], [])
        world = MEntity(self.worldspawn())
        world.prims = list(brushes) + list(patches) + prop_clips
        if self.opt.detail_all:
            world.prims = self.shell(brushes, patches) + world.prims
        ents = [world] + self.entities() + prop_ents
        self.report["precache"] = precache
        scripts = [self._shader_text(cm) for cm in self.mats.values()]
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
        return Result(MapFile(ents), self.assets, self.report)


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


def auto_cameras(m: MapFile, n: int = 9, landmarks=()):
    """Spread-out cameras: each landmark (e.g. bomb site, looking toward the map centre), then a
    farthest-point sample of spawn points (eye height, spawn facing), plus one high overview."""
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
    pts = lm + pts
    chosen: list = []
    if pts:
        chosen.append(pts[0])
        while len(chosen) < min(n - 1, len(pts)):
            far = max(pts, key=lambda p: min((p[0][0] - c[0][0]) ** 2 + (p[0][1] - c[0][1]) ** 2 for c in chosen))
            chosen.append(far)
    cams = [game.Shot(f"spawn{i}", (o[0], o[1], o[2] + 82), (5.0, yaw, 0.0)) for i, (o, yaw) in enumerate(chosen)]
    if pts:
        xs, ys, zs = [p[0][0] for p in pts], [p[0][1] for p in pts], [p[0][2] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1024)
        eye = (min(xs) - span * 0.15, min(ys) - span * 0.15, max(zs) + span * 0.45)
        cams.append(game.Shot.looking_at("overview", eye, (cx, cy, min(zs))))
    return cams


def build_local(map_name: str, name: Optional[str] = None, quality: str = "draft", test: bool = True,
                shots: int = 9, log=print, **opts) -> dict:
    """Convert ``csgo/maps/<map_name>.bsp``, compile, package and (optionally) screenshot it.

    Everything is written under ``local/csgo/<name>/`` (gitignored: it contains
    decoded Valve textures and must not be committed or shared).
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
    if quality == "draft":
        # MOHlight lights static-model vertices on one thread (~190/s at best; de_dust2's 70k took
        # hours), so drafts make every prop a runtime script_model unless a budget is given.
        opts.setdefault("props_static_vertices", 0)
    res = convert(str(src), cfg.csgo_dir, Options(name=name, **opts))
    (out / f"{name}.map").write_text(res.map.dumps(), encoding="latin-1")
    for rel, data in res.assets.items():
        p = out / "assets" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    log(json.dumps({k: v for k, v in res.report.items() if k != "warnings"}))
    issues = [i for i in validate.check(res.map) if i.severity == "error"]
    for i in issues:
        log(f"  {i}")
    log(f"== compiling ({quality})")
    cr = C.compile_map(res.map.dumps(), f"dm/{name}", assets=res.assets, quality=quality)
    log(cr.summary())
    report = {"name": name, "source": str(src), "convert": res.report, "compile_ok": cr.ok, "stats": cr.stats,
              "problems": cr.problems}
    if cr.ok:
        proj = project.Project(name=name, folder=out, title=src.stem, ambience="mohdm2",
                               precache=list(res.report.get("precache", ())))
        files = {f"maps/dm/{name}.bsp": cr.bsp.read_bytes(), **proj.scripts(), **res.assets}
        pk3 = out / f"{name}.pk3"
        project.write_pk3(pk3, files)
        report["pk3"] = str(pk3)
        log(f"== packaged {pk3} ({pk3.stat().st_size // 1024} KB)")
        if test:
            cams = auto_cameras(res.map, shots, res.report.get("landmarks", ()))
            run = game.run([pk3], f"dm/{name}", cams, run_name=name)
            sheet = game.contact_sheet(run.screenshots, out / f"{name}_shots.png")
            report["contact_sheet"] = str(sheet)
            report["run_problems"] = run.problems
            log(run.summary())
            log(f"== contact sheet {sheet}")
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report
