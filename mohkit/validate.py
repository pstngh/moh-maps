"""Static checks on a MapFile before spending time in the compiler.

Catches common defects before compiling:
invalid brushes, unknown shaders (render as checkerboards), spawns inside
geometry or floating, lights embedded in walls, missing spawn classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import geom
from .mapfile import Brush, MapFile, Patch, Terrain

PLAYER_MINS = (-15.0, -15.0, 0.0)
PLAYER_MAXS = (15.0, 15.0, 94.0)

NONSOLID_TOOLS = {"common/hint", "common/skip", "common/trigger", "common/areaportal", "common/origin",
                  "common/nodrawnonsolid", "common/nodraw_nonsolid"}

LIMITS = {"brushes": 32768, "entities": 8192, "brushsides": 131072, "shaders": 1024}


@dataclass
class Issue:
    severity: str  # error | warning | info
    message: str
    where: str = ""

    def __str__(self) -> str:
        return f"{self.severity.upper():7s} {self.where + ': ' if self.where else ''}{self.message}"


class _Solid:
    __slots__ = ("planes", "mins", "maxs", "where")

    def __init__(self, planes, mins, maxs, where):
        self.planes, self.mins, self.maxs, self.where = planes, mins, maxs, where


def _solids(m: MapFile, shaders=None) -> tuple[list[_Solid], list[Issue]]:
    solids, issues = [], []
    for ei, e in enumerate(m.entities):
        for bi, p in enumerate(e.prims):
            if not isinstance(p, Brush):
                continue
            where = f"entity {ei} brush {bi}"
            planes = p.planes()
            if any(pl.is_degenerate() for pl in planes):
                issues.append(Issue("error", "degenerate face plane (collinear points)", where))
                continue
            ws = geom.brush_windings(planes)
            bad = [i for i, w in enumerate(ws) if len(w) < 3 or geom.winding_area(w) < 0.01]
            if len(bad) == len(ws) or sum(1 for w in ws if len(w) >= 3) < 4:
                issues.append(Issue("error", "brush has no volume (inside-out or empty)", where))
                continue
            if bad:
                issues.append(Issue("info", f"{len(bad)} redundant face(s)", where))
            if e.classname.startswith("trigger"):
                continue
            names = {f.shader.lower() for f in p.faces}
            if names <= NONSOLID_TOOLS:
                continue
            if shaders is not None and all(_nonsolid(shaders, n) for n in names):
                continue
            mins, maxs = geom.bounds_of(pt for w in ws for pt in w)
            if max(maxs[i] - mins[i] for i in range(2)) > 1536 and not all(
                    f.shader.lower().startswith(("common/", "sky/")) for f in p.faces):
                issues.append(Issue("warning", "brush longer than 1536 units: its faces may exceed the renderer's "
                                    "64-vertex limit (split it)", where))
            solids.append(_Solid(planes, mins, maxs, where))
    return solids, issues


def _nonsolid(shaders, name: str) -> bool:
    try:
        parms = {s.lower() for s in shaders.surfaceparms(name)}
    except Exception:
        return False
    return bool(parms & {"nonsolid", "trigger", "areaportal", "hint", "skip"})


def _blocks_players(shaders, name: str) -> bool:
    """True unless the shader is nonsolid without playerclip (e.g. ``common/foliageclip``, bullets only)."""
    try:
        parms = {s.lower() for s in shaders.surfaceparms(name)}
    except Exception:  # noqa: BLE001
        return True
    return "playerclip" in parms or not parms & {"nonsolid", "trigger", "areaportal", "hint", "skip"}


_COLLISION_BOXES: dict[str, list[tuple[tuple, tuple]]] = {}


def _collision_boxes(info, shaders) -> list[tuple[tuple, tuple]]:
    """Model-space bounds of each player-blocking brush in the prop's collision .map.

    A palm's collision is a woodclip trunk plus a foliageclip canopy that only stops
    bullets; using the whole model (or the whole .map) rejects spawns under the canopy.
    Without the game files this falls back to the bounds of the whole collision .map.
    """
    if info.path in _COLLISION_BOXES:
        return _COLLISION_BOXES[info.path]
    boxes: Optional[list[tuple[tuple, tuple]]] = None
    fs = getattr(shaders, "fs", None)
    cpath = info.path[:-4] + ".map"
    if fs is not None and fs.exists(cpath):
        try:
            cm = MapFile.parse(fs.read_text(cpath), cpath)
            boxes = []
            for _, p in cm.iter_prims():
                if isinstance(p, Brush) and any(_blocks_players(shaders, f.shader) for f in p.faces):
                    pts = [pt for w in p.windings() for pt in w]
                    if pts:
                        boxes.append(geom.bounds_of(pts))
        except Exception:  # noqa: BLE001
            boxes = None
    if boxes is None:
        from . import props
        c = props.collision_bounds(info.path)
        boxes = [c] if c else [(info.mins, info.maxs)]
    _COLLISION_BOXES[info.path] = boxes
    return boxes


def _prop_solids(m: MapFile, shaders=None) -> list[_Solid]:
    """Approximate collision of props that ship a collision .map: each player-blocking
    brush as its rotated, scaled bounding box."""
    try:
        from . import props
    except Exception:  # noqa: BLE001
        return []
    out = []
    for ei, e in enumerate(m.entities):
        if not e.classname.startswith("static_") or not e.get("model"):
            continue
        info = props.get(e["model"])
        if not info or not info.collision:
            continue
        o = e.origin() or (0.0, 0.0, 0.0)
        sc = float(e.get("scale", "1") or 1)
        yaw = float(e.get("angle", "0") or 0)
        if e.get("angles"):
            yaw = float(e["angles"].split()[1])
        for bmin, bmax in _collision_boxes(info, shaders):
            corners = [(x, y) for x in (bmin[0], bmax[0]) for y in (bmin[1], bmax[1])]
            rc = [geom.rotate_z((x * sc, y * sc, 0), yaw) for x, y in corners]
            mins = (o[0] + min(p[0] for p in rc), o[1] + min(p[1] for p in rc), o[2] + bmin[2] * sc)
            maxs = (o[0] + max(p[0] for p in rc), o[1] + max(p[1] for p in rc), o[2] + bmax[2] * sc)
            planes = [geom.Plane((-1.0, 0.0, 0.0), -mins[0]), geom.Plane((1.0, 0.0, 0.0), maxs[0]),
                      geom.Plane((0.0, -1.0, 0.0), -mins[1]), geom.Plane((0.0, 1.0, 0.0), maxs[1]),
                      geom.Plane((0.0, 0.0, -1.0), -mins[2]), geom.Plane((0.0, 0.0, 1.0), maxs[2])]
            out.append(_Solid(planes, mins, maxs, f"entity {ei} ({info.path.rsplit('/', 1)[-1]})"))
    return out


def box_hits_brush(mins, maxs, s: _Solid, eps: float = 0.5) -> bool:
    if any(maxs[i] <= s.mins[i] + eps or mins[i] >= s.maxs[i] - eps for i in range(3)):
        return False
    for pl in s.planes:
        n = pl.normal
        support = tuple(mins[i] if n[i] > 0 else maxs[i] for i in range(3))
        if geom.dot(n, support) - pl.dist >= -eps:
            return False
    return True


def point_in_brush(p, s: _Solid, eps: float = 0.1) -> bool:
    return all(pl.distance(p) < -eps for pl in s.planes)


def check(m: MapFile, shaders=None, min_dm_spawns: int = 8) -> list[Issue]:
    issues: list[Issue] = []
    if not m.entities or m.entities[0].classname != "worldspawn":
        issues.append(Issue("error", "first entity must be worldspawn"))
    solids, bi = _solids(m, shaders)
    issues += bi
    brush_solids = list(solids)
    solids += _prop_solids(m, shaders)
    patch_boxes = [p.bounds() for _, p in m.iter_prims() if isinstance(p, Patch)]

    nbrush = sum(1 for _, p in m.iter_prims() if isinstance(p, Brush))
    nsides = sum(len(p.faces) for _, p in m.iter_prims() if isinstance(p, Brush))
    for key, n in (("brushes", nbrush), ("entities", len(m.entities)), ("brushsides", nsides)):
        if n > LIMITS[key]:
            issues.append(Issue("error", f"{n} {key} exceeds engine limit {LIMITS[key]}"))

    if shaders is not None:
        missing: dict[str, int] = {}
        for _, p in m.iter_prims():
            names = [f.shader for f in p.faces] if isinstance(p, Brush) else ([p.shader] if isinstance(p, Patch) else [])
            for n in names:
                if not shaders.exists(n):
                    missing[n] = missing.get(n, 0) + 1
        for n, c in sorted(missing.items()):
            issues.append(Issue("error", f"unknown shader/texture '{n}' on {c} face(s) (renders as checkerboard)"))

    counts: dict[str, int] = {}
    for ei, e in enumerate(m.entities):
        cn = e.classname
        counts[cn] = counts.get(cn, 0) + 1
        o = e.origin()
        if cn in ("info_player_deathmatch", "info_player_allied", "info_player_axis", "info_player_start") and o is not None:
            mins = geom.add(o, PLAYER_MINS)
            maxs = geom.add(o, PLAYER_MAXS)
            hit = next((s for s in solids if box_hits_brush(mins, maxs, s)), None)
            if hit:
                issues.append(Issue("error", f"{cn} at {o} overlaps solid {hit.where}", f"entity {ei}"))
                continue
            below = (o[0], o[1], o[2] - 1.0)
            grounded = any(box_hits_brush((below[0] - 14, below[1] - 14, o[2] - 40), (below[0] + 14, below[1] + 14, o[2] + 0.5), s, eps=0.0)
                           for s in solids)
            if not grounded:
                grounded = any(0 <= o[2] - h <= 40 for h in terrain_heights(m, o[0], o[1]))
            if not grounded:
                grounded = any(pb[0][0] <= o[0] <= pb[1][0] and pb[0][1] <= o[1] <= pb[1][1]
                               and pb[0][2] - 8 <= o[2] <= pb[1][2] + 40 for pb in patch_boxes)
            if not grounded:
                issues.append(Issue("warning", f"{cn} at {o} has no floor within 40 units", f"entity {ei}"))
        elif cn == "light" and o is not None:
            hit = next((s for s in brush_solids if point_in_brush(o, s)), None)
            if hit:
                issues.append(Issue("warning", f"light at {o} is inside {hit.where} (it will be black/wasted)", f"entity {ei}"))
        elif cn.startswith("static_") and shaders is not None and e.get("model"):
            fs = getattr(shaders, "fs", None)
            model = "models/" + e["model"].replace("//", "/").lstrip("/")
            if fs is not None and not fs.exists(model):
                issues.append(Issue("error", f"static model '{e['model']}' not found in paks", f"entity {ei}"))

    ndm = counts.get("info_player_deathmatch", 0)
    if ndm and ndm < min_dm_spawns:
        issues.append(Issue("warning", f"only {ndm} info_player_deathmatch (stock DM maps use 11-25)"))
    if not ndm and not counts.get("info_player_allied"):
        issues.append(Issue("error", "no player spawns"))
    if (counts.get("info_player_allied", 0) == 0) != (counts.get("info_player_axis", 0) == 0):
        issues.append(Issue("warning", "team spawns only for one side"))
    if not counts.get("info_player_start"):
        issues.append(Issue("info", "no info_player_start (spectators start at a spawn point)"))
    return issues


def terrain_heights(m: MapFile, x: float, y: float) -> list[float]:
    """Heights of all terrainDef grids under (x, y) (nearest sample; rows run along +Y)."""
    out = []
    for _, p in m.iter_prims():
        if isinstance(p, Terrain):
            ox, oy, oz = p.origin
            col, row = round((x - ox) / 64), round((y - oy) / 64)
            if 0 <= col < p.width and 0 <= row < p.height:
                out.append(oz + p.samples[row * p.width + col].height)
    return out


def load_shader_index():
    """Best effort: a ShaderIndex over the configured retail paks, or None."""
    try:
        from . import config, pak, shaders
        fs = pak.GameFS(config.load().game_dir)
        idx = shaders.ShaderIndex.from_fs(fs)
        idx.fs = fs  # type: ignore[attr-defined]
        return idx
    except Exception:
        return None


def ground_height(m: MapFile, x: float, y: float, z_from: float = 1e9) -> Optional[float]:
    """Highest walkable surface (upward brush face or patch control) at (x, y) below ``z_from``."""
    best: Optional[float] = None
    for _, p in m.iter_prims():
        if isinstance(p, Brush):
            for f, w in zip(p.faces, p.windings()):
                sh = f.shader.lower()
                if len(w) < 3 or f.plane.normal[2] < 0.7 or sh.startswith(("common/", "sky/")) or sh.endswith("/sky"):
                    continue
                if not _inside_xy(w, x, y):
                    continue
                pl = f.plane
                z = (pl.dist - pl.normal[0] * x - pl.normal[1] * y) / pl.normal[2]
                if z <= z_from and (best is None or z > best):
                    best = z
        elif isinstance(p, Patch):
            (x0, y0, z0), (x1, y1, z1) = p.bounds()
            if x0 <= x <= x1 and y0 <= y <= y1:
                near = min((c for row in p.ctrl for c in row), key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
                if near[2] <= z_from and (best is None or near[2] > best):
                    best = near[2]
    return best


def _inside_xy(w, x, y) -> bool:
    n = len(w)
    sign = 0.0
    for i in range(n):
        ax, ay = w[i][0], w[i][1]
        bx, by = w[(i + 1) % n][0], w[(i + 1) % n][1]
        c = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if abs(c) < 1e-9:
            continue
        if sign == 0.0:
            sign = c
        elif (c > 0) != (sign > 0):
            return False
    return True
