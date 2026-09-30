"""Author MOHAA maps in Python.

Two layers:

* **Brush constructors** (`box`, `prism`, `hull`) that write exact, on-grid face points
  with correct winding, and per-face materials.
* **Carver**: describe the playable *air* as axis-aligned boxes, each with floor /
  wall / ceiling materials (or sky). The carver wraps every air box in structural
  slabs and subtracts all air from them, so the world is sealed by construction
  (no leaks), every face that no player can see becomes ``common/caulk``, and
  textures stay world-aligned. Everything else (stairs, cover, trim, props) is
  added as detail inside the air.

Coordinates: Z up, 1 unit ~ 1 inch. Player box is 30x30 wide and ~94 tall
standing; keep corridors >= 96 wide and doorways >= 64x112 (see docs/design.md).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Mapping, Optional, Sequence, Union

from . import geom
from .geom import Vec3
from .mapfile import Brush, Entity, Face, MapFile, Patch, fmt

CAULK = "common/caulk"
NODRAW = "common/nodraw"
CLIP = "common/clip"
PLAYERCLIP = "common/playerclip"
SKY = "sky/mohday1"


@dataclass(frozen=True)
class Material:
    """A shader plus how it is laid on a face.

    ``scale`` is world units per texel (Q3 convention). Stock MOHAA textures are laid
    at 1.0 (a 256 px texture repeats every 256 units); only use smaller values for
    deliberately finer detail. ``parms`` are extra ``+surfaceparm`` names written on the face.
    """
    shader: str
    scale: tuple[float, float] = (1.0, 1.0)
    rotate: float = 0.0
    shift: tuple[float, float] = (0.0, 0.0)
    parms: tuple[str, ...] = ()

    def __call__(self, **kw) -> "Material":
        return replace(self, **kw)

    def face(self, pts: tuple[Vec3, Vec3, Vec3], detail: bool = False) -> Face:
        ext: list[str] = []
        for p in self.parms + (("detail",) if detail else ()):
            ext += ["+surfaceparm", p]
        return Face(pts, self.shader, self.shift, self.rotate, self.scale, 0, 0, 0, ext)


MatLike = Union[Material, str]


def mat(m: MatLike, scale: Optional[float] = None) -> Material:
    if isinstance(m, Material):
        return m if scale is None else m(scale=(scale, scale))
    return Material(m, (scale, scale) if scale is not None else (1.0, 1.0))


CAULK_M = Material(CAULK, (1, 1))
SKY_M = Material(SKY, (1, 1))

# Side names for axis-aligned boxes.
SIDES = {
    "west": (-1, 0, 0), "east": (1, 0, 0), "south": (0, -1, 0),
    "north": (0, 1, 0), "bottom": (0, 0, -1), "top": (0, 0, 1),
}
_AXIS_OF = {n: i for n, v in SIDES.items() for i in range(3) if v[i]}

MatSpec = Union[MatLike, Mapping[str, MatLike], Callable[[Vec3, Vec3], MatLike]]


def _pick(spec: MatSpec, normal: Vec3, center: Vec3) -> Material:
    """Resolve a material spec for a face with ``normal``.

    Mapping keys: side names, ``sides`` (all vertical faces), ``up``/``down`` (any
    face whose normal z > 0.7 / < -0.7), ``default``.
    """
    if callable(spec) and not isinstance(spec, Material):
        return mat(spec(normal, center))
    if not isinstance(spec, Mapping):
        return mat(spec)
    nz = normal[2]
    for name, v in SIDES.items():
        if all(abs(normal[i] - v[i]) < 1e-6 for i in range(3)) and name in spec:
            return mat(spec[name])
    if nz > 0.7 and "up" in spec:
        return mat(spec["up"])
    if nz > 0.7 and "top" in spec:
        return mat(spec["top"])
    if nz < -0.7 and "down" in spec:
        return mat(spec["down"])
    if nz < -0.7 and "bottom" in spec:
        return mat(spec["bottom"])
    if abs(nz) <= 0.7 and "sides" in spec:
        return mat(spec["sides"])
    return mat(spec.get("default", CAULK_M))


# ---------------------------------------------------------------------------
# Brush constructors

def _tri_for(normal: Vec3, poly: Sequence[Vec3]) -> tuple[Vec3, Vec3, Vec3]:
    """Three polygon vertices ordered so the face plane normal equals ``normal``."""
    a = poly[0]
    best = None
    for i in range(1, len(poly) - 1):
        for j in range(i + 1, len(poly)):
            b, c = poly[i], poly[j]
            n = geom.cross(geom.sub(c, a), geom.sub(b, a))
            mag = geom.length(n)
            if best is None or mag > best[0]:
                best = (mag, b, c, n)
    assert best is not None and best[0] > 1e-9, "degenerate face polygon"
    _, b, c, n = best
    if geom.dot(n, normal) < 0:
        b, c = c, b
    return (a, b, c)


def box(mins: Sequence[float], maxs: Sequence[float], m: MatSpec = CAULK_M, detail: bool = False) -> Brush:
    """Axis-aligned box brush. ``m`` may map side names to materials."""
    x0, y0, z0 = mins
    x1, y1, z1 = maxs
    if not (x1 > x0 and y1 > y0 and z1 > z0):
        raise ValueError(f"empty box {tuple(mins)} {tuple(maxs)}")
    faces = []
    for name, n in SIDES.items():
        u, v = _TANGENTS[n]
        p = (x1 if n[0] > 0 else x0, y1 if n[1] > 0 else y0, z1 if n[2] > 0 else z0)
        a = p
        b = (p[0] + u[0] * 64, p[1] + u[1] * 64, p[2] + u[2] * 64)
        c = (p[0] + v[0] * 64, p[1] + v[1] * 64, p[2] + v[2] * 64)
        center = ((x0 + x1) / 2 if not n[0] else p[0], (y0 + y1) / 2 if not n[1] else p[1],
                  (z0 + z1) / 2 if not n[2] else p[2])
        faces.append(_pick(m, n, center).face((a, b, c), detail))
    return Brush(faces)


# outward normal -> (u, v) with cross(v, u) == normal, so (p, p+u, p+v) is correctly wound
_TANGENTS = {
    (1, 0, 0): ((0, 0, 1), (0, 1, 0)), (-1, 0, 0): ((0, 1, 0), (0, 0, 1)),
    (0, 1, 0): ((1, 0, 0), (0, 0, 1)), (0, -1, 0): ((0, 0, 1), (1, 0, 0)),
    (0, 0, 1): ((0, 1, 0), (1, 0, 0)), (0, 0, -1): ((1, 0, 0), (0, 1, 0)),
}


def prism(poly: Sequence[tuple[float, float]], z0: float, z1: float, m: MatSpec = CAULK_M,
          detail: bool = False) -> Brush:
    """Vertical extrusion of a convex XY polygon (any winding)."""
    pts = [(float(x), float(y)) for x, y in poly]
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts.reverse()
    faces = []
    top = [(x, y, z1) for x, y in pts]
    bot = [(x, y, z0) for x, y in pts]
    faces.append(_pick(m, (0, 0, 1), _centroid(top)).face(_tri_for((0, 0, 1), top), detail))
    faces.append(_pick(m, (0, 0, -1), _centroid(bot)).face(_tri_for((0, 0, -1), bot), detail))
    for i in range(len(pts)):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
        n = geom.normalize((by - ay, -(bx - ax), 0))
        quad = [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)]
        faces.append(_pick(m, n, _centroid(quad)).face(_tri_for(n, quad), detail))
    return Brush(faces)


def hull(points: Iterable[Sequence[float]], m: MatSpec = CAULK_M, detail: bool = False) -> Brush:
    """Convex hull of a small point set as a brush (ramps, wedges, roofs, frustums)."""
    pts = list({tuple(float(c) for c in p) for p in points})
    if len(pts) < 4:
        raise ValueError("hull needs >= 4 points")
    planes: list[tuple[Vec3, float, list[Vec3]]] = []
    for a, b, c in itertools.combinations(pts, 3):
        n = geom.cross(geom.sub(b, a), geom.sub(c, a))
        if geom.length(n) < 1e-9:
            continue
        n = geom.normalize(n)
        d = geom.dot(n, a)
        side = [geom.dot(n, p) - d for p in pts]
        if all(s >= -1e-6 for s in side) and not all(s <= 1e-6 for s in side):
            n, d = geom.scale(n, -1), -d   # all points behind: flip so the normal points out
        elif not all(s <= 1e-6 for s in side):
            continue                         # points on both sides: not a hull face
        if any(abs(n[0] - q[0][0]) < 1e-6 and abs(n[1] - q[0][1]) < 1e-6 and abs(n[2] - q[0][2]) < 1e-6
               and abs(d - q[1]) < 1e-6 for q in planes):
            continue
        onp = [p for p in pts if abs(geom.dot(n, p) - d) < 1e-6]
        planes.append((n, d, onp))
    faces = []
    for n, d, onp in planes:
        # order coplanar points around their centroid to pick a well-shaped triangle
        c = _centroid(onp)
        u = geom.normalize(geom.sub(onp[0], c)) if geom.length(geom.sub(onp[0], c)) > 1e-9 else (1, 0, 0)
        v = geom.cross(n, u)
        onp.sort(key=lambda p: math.atan2(geom.dot(geom.sub(p, c), v), geom.dot(geom.sub(p, c), u)))
        faces.append(_pick(m, n, c).face(_tri_for(n, onp), detail))
    if len(faces) < 4:
        raise ValueError("flat hull")
    return Brush(faces)


def _centroid(pts: Sequence[Sequence[float]]) -> Vec3:
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


def set_detail(b: Brush, detail: bool = True) -> Brush:
    for f in b.faces:
        (f.add_parm if detail else f.remove_parm)("detail")
    return b


# ---------------------------------------------------------------------------
# Axis-aligned box algebra

AABB = tuple[tuple[float, float, float], tuple[float, float, float]]


def aabb(x0, y0, z0, x1, y1, z1) -> AABB:
    return ((float(x0), float(y0), float(z0)), (float(x1), float(y1), float(z1)))


def overlaps(a: AABB, b: AABB, eps: float = 0.0) -> bool:
    return all(a[0][i] < b[1][i] - eps and b[0][i] < a[1][i] - eps for i in range(3))


def subtract(a: AABB, h: AABB) -> list[AABB]:
    """``a`` minus ``h`` as up to six disjoint boxes."""
    if not overlaps(a, h):
        return [a]
    (ax0, ay0, az0), (ax1, ay1, az1) = a
    (hx0, hy0, hz0), (hx1, hy1, hz1) = h
    out = []
    if az0 < hz0:
        out.append(((ax0, ay0, az0), (ax1, ay1, hz0)))
    if hz1 < az1:
        out.append(((ax0, ay0, hz1), (ax1, ay1, az1)))
    z0, z1 = max(az0, hz0), min(az1, hz1)
    if ay0 < hy0:
        out.append(((ax0, ay0, z0), (ax1, hy0, z1)))
    if hy1 < ay1:
        out.append(((ax0, hy1, z0), (ax1, ay1, z1)))
    y0, y1 = max(ay0, hy0), min(ay1, hy1)
    if ax0 < hx0:
        out.append(((ax0, y0, z0), (hx0, y1, z1)))
    if hx1 < ax1:
        out.append(((hx1, y0, z0), (ax1, y1, z1)))
    return out


def subtract_all(boxes: Iterable[AABB], holes: Sequence[AABB]) -> list[AABB]:
    cur = list(boxes)
    for h in holes:
        nxt = []
        for b in cur:
            nxt.extend(subtract(b, h))
        cur = nxt
    return cur


def grid_split(b: AABB, grid: float, axes: Sequence[int] = (0, 1)) -> list[AABB]:
    """Split a box at multiples of ``grid`` along ``axes``."""
    out = [b]
    for ax in axes:
        nxt = []
        for p in out:
            lo, hi = p[0][ax], p[1][ax]
            cuts = [lo] + [k * grid for k in range(math.floor(lo / grid) + 1, math.ceil(hi / grid))] + [hi]
            for a, c in zip(cuts, cuts[1:]):
                if c - a > 1e-6:
                    mn, mx = list(p[0]), list(p[1])
                    mn[ax], mx[ax] = a, c
                    nxt.append((tuple(mn), tuple(mx)))
        out = nxt
    return out  # type: ignore[return-value]


def merge_boxes(boxes: list[AABB]) -> list[AABB]:
    """Greedy merge of boxes that share a full face (reduces brush count)."""
    changed = True
    boxes = list(boxes)
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                m = _merge2(boxes[i], boxes[j])
                if m:
                    boxes[i] = m
                    del boxes[j]
                    changed = True
                    break
            if changed:
                break
    return boxes


def _merge2(a: AABB, b: AABB) -> Optional[AABB]:
    for ax in range(3):
        o = [i for i in range(3) if i != ax]
        if all(a[0][i] == b[0][i] and a[1][i] == b[1][i] for i in o):
            if a[1][ax] == b[0][ax] or b[1][ax] == a[0][ax]:
                lo = tuple(min(a[0][i], b[0][i]) for i in range(3))
                hi = tuple(max(a[1][i], b[1][i]) for i in range(3))
                return (lo, hi)  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------------------
# Carver

Bands = Sequence[tuple[float, MatLike]]
WallSpec = Union[MatLike, Bands, Mapping[str, Union[MatLike, Bands]]]


def _is_bands(v) -> bool:
    return isinstance(v, (list, tuple)) and bool(v) and isinstance(v[0], (list, tuple))


@dataclass
class Air:
    """A playable volume. ``floor``/``walls``/``ceiling`` are what players see on the
    surrounding shell; ``sky=True`` makes the top a sky face.

    ``walls`` may be a material, a list of height bands ``[(z_from, material), ...]``
    (absolute z, ascending), or a mapping of side names (north/south/east/west,
    ``default``) to either. The side name is the compass side of *this* air box.
    """
    bounds: AABB
    floor: MatLike = CAULK_M
    walls: WallSpec = CAULK_M
    ceiling: MatLike = CAULK_M
    sky: bool = False
    name: str = ""
    priority: int = 0

    def band_levels(self) -> set[float]:
        specs = list(self.walls.values()) if isinstance(self.walls, Mapping) else [self.walls]
        return {float(z) for sp in specs if _is_bands(sp) for z, _ in sp}

    def material_for(self, inward_normal: Vec3, z: float = 0.0) -> Material:
        """Material of the shell face whose normal (pointing into this air) is given;
        ``z`` is the face centre height, used to pick a wall band."""
        nz = inward_normal[2]
        if nz > 0.5:
            return mat(self.floor)
        if nz < -0.5:
            return SKY_M if self.sky else mat(self.ceiling)
        spec = self.walls
        if isinstance(spec, Mapping):
            chosen = spec.get("default", CAULK_M)
            for name in ("north", "south", "east", "west"):
                v = SIDES[name]
                # the wall on this air's north side faces south (inward normal -y)
                if all(abs(-inward_normal[i] - v[i]) < 1e-6 for i in range(3)) and name in spec:
                    chosen = spec[name]
            spec = chosen
        if _is_bands(spec):
            pick = spec[0][1]
            for z0, m in spec:
                if z >= z0 - 1e-6:
                    pick = m
            return mat(pick)
        return mat(spec)


class Carver:
    def __init__(self, thickness: float = 16.0, sky_shader: str = SKY, grid: float = 512.0):
        self.air: list[Air] = []
        self.t = thickness
        self.grid = grid
        self.sky = Material(sky_shader, (1, 1))
        self.solids: list[tuple[AABB, MatSpec]] = []

    def add(self, a: Air) -> Air:
        self.air.append(a)
        return a

    def room(self, x0, y0, z0, x1, y1, z1, **kw) -> Air:
        return self.add(Air(aabb(x0, y0, z0, x1, y1, z1), **kw))

    def solid(self, x0, y0, z0, x1, y1, z1, m: MatSpec) -> None:
        """Extra structural mass that is not derived from air (e.g. a pillar block)."""
        self.solids.append((aabb(x0, y0, z0, x1, y1, z1), m))

    def shell_boxes(self) -> list[AABB]:
        t = self.t
        slabs: list[AABB] = []
        for a in self.air:
            (x0, y0, z0), (x1, y1, z1) = a.bounds
            slabs += [
                ((x0 - t, y0 - t, z0 - t), (x1 + t, y1 + t, z0)),   # below
                ((x0 - t, y0 - t, z1), (x1 + t, y1 + t, z1 + t)),   # above
                ((x0 - t, y0 - t, z0), (x0, y1 + t, z1)),           # west
                ((x1, y0 - t, z0), (x1 + t, y1 + t, z1)),           # east
                ((x0, y0 - t, z0), (x1, y0, z1)),                   # south
                ((x0, y1, z0), (x1, y1 + t, z1)),                   # north
            ]
        holes = [a.bounds for a in self.air]
        pieces = subtract_all(slabs, holes)
        cuts = sorted(set().union(*(a.band_levels() for a in self.air))) if self.air else []
        if cuts:
            split = []
            for p in pieces:
                zs = [p[0][2]] + [c for c in cuts if p[0][2] < c < p[1][2]] + [p[1][2]]
                split += [((p[0][0], p[0][1], za), (p[1][0], p[1][1], zb)) for za, zb in zip(zs, zs[1:])]
            pieces = split
        uniq = list(dict.fromkeys(pieces))
        uniq = [p for p in uniq if all(p[1][i] - p[0][i] > 0.01 for i in range(3))]
        uniq = _dedupe_contained(uniq)
        # Chop on a world grid: the renderer drops any face with > 64 vertices after
        # T-junction fixing (MAX_FACE_POINTS), which long faces easily exceed.
        return [q for p in uniq for q in grid_split(p, self.grid)] if self.grid else uniq

    def brushes(self) -> list[Brush]:
        out = []
        for piece in self.shell_boxes():
            out.append(box(piece[0], piece[1], self._face_mats(piece)))
        for bb, m in self.solids:
            out.append(box(bb[0], bb[1], m))
        return out

    def _face_mats(self, piece: AABB) -> dict[str, Material]:
        mats: dict[str, Material] = {}
        zc = (piece[0][2] + piece[1][2]) / 2
        for name, n in SIDES.items():
            ax = _AXIS_OF[name]
            coord = piece[1][ax] if n[ax] > 0 else piece[0][ax]
            best, best_area = None, 0.0
            for a in self.air:
                # the air must lie on the outer side of this face, touching it
                acoord = a.bounds[0][ax] if n[ax] > 0 else a.bounds[1][ax]
                if abs(acoord - coord) > 1e-6:
                    continue
                o = [i for i in range(3) if i != ax]
                w = min(piece[1][o[0]], a.bounds[1][o[0]]) - max(piece[0][o[0]], a.bounds[0][o[0]])
                h = min(piece[1][o[1]], a.bounds[1][o[1]]) - max(piece[0][o[1]], a.bounds[0][o[1]])
                if w > 0 and h > 0 and (w * h > best_area or (w * h == best_area and best and a.priority > best.priority)):
                    best, best_area = a, w * h
            if best is None:
                mats[name] = CAULK_M
            else:
                m = best.material_for(n, zc)
                mats[name] = self.sky if m.shader == SKY else m
        return mats

    def contains(self, p: Sequence[float]) -> bool:
        return any(all(a.bounds[0][i] <= p[i] <= a.bounds[1][i] for i in range(3)) for a in self.air)


def _dedupe_contained(boxes: list[AABB]) -> list[AABB]:
    out = []
    for i, b in enumerate(boxes):
        inside = False
        for j, c in enumerate(boxes):
            if i != j and all(c[0][k] <= b[0][k] and b[1][k] <= c[1][k] for k in range(3)) and (c != b or j < i):
                inside = True
                break
        if not inside:
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Map builder

class MapBuilder:
    """Collects world geometry and entities and writes a MapFile."""

    def __init__(self, message: str = "", **worldspawn):
        self.world = Entity({"classname": "worldspawn"})
        if message:
            self.world["message"] = message
        for k, v in worldspawn.items():
            self.world[k] = v
        self.entities: list[Entity] = []
        self.carver: Optional[Carver] = None

    # geometry -----------------------------------------------------------------
    def add(self, *prims) -> None:
        for p in prims:
            if isinstance(p, (list, tuple)):
                self.add(*p)
            else:
                self.world.prims.append(p)

    def box(self, mins, maxs, m: MatSpec, detail: bool = True, grid: float = 512.0) -> Brush:
        """Axis-aligned brush; boxes longer than ``grid`` are split on the world grid
        (keeps faces under the renderer's 64-vertex limit). Returns the last piece."""
        pieces = grid_split((tuple(mins), tuple(maxs)), grid) if grid else [(tuple(mins), tuple(maxs))]
        for lo, hi in pieces:
            b = box(lo, hi, m, detail)
            self.world.prims.append(b)
        return b

    def prism(self, poly, z0, z1, m: MatSpec, detail: bool = True) -> Brush:
        b = prism(poly, z0, z1, m, detail)
        self.world.prims.append(b)
        return b

    def hull(self, points, m: MatSpec, detail: bool = True) -> Brush:
        b = hull(points, m, detail)
        self.world.prims.append(b)
        return b

    def carve(self, carver: Carver) -> None:
        self.carver = carver

    # entities -------------------------------------------------------------------
    def entity(self, classname: str, origin: Optional[Sequence[float]] = None, **keys) -> Entity:
        e = Entity({"classname": classname})
        if origin is not None:
            e["origin"] = tuple(origin)
        for k, v in keys.items():
            e[k.replace("__", "$")] = v
        self.entities.append(e)
        return e

    def spawn(self, origin, yaw: float, kinds: Iterable[str] = ("deathmatch", "allied", "axis")) -> None:
        """Player spawns. ``origin`` is at the player's feet (z = floor + 1 is fine)."""
        for k in kinds:
            self.entity(f"info_player_{k}", origin, angle=fmt(yaw % 360))

    def light(self, origin, intensity: float = 150, color=None, **keys) -> Entity:
        e = self.entity("light", origin, light=fmt(intensity), **keys)
        if color:
            e["_color"] = " ".join(f"{c:.3f}" for c in color)
        return e

    def static_model(self, tik: str, origin, yaw: float = 0, scale: float = 1.0, classname: Optional[str] = None,
                     **keys) -> Entity:
        """Stock prop, compiled into the BSP's static-model lump (vertex lit by MOHlight).

        Collision exists only if the model ships a companion ``.map`` (see mohkit.props);
        otherwise add clip brushes. ``origin`` is the model pivot (usually its base).
        """
        from . import props
        info = props.get(tik)
        name = info.model_key if info else tik.replace("\\", "/").removeprefix("models/")
        cls = classname or (info.classname if info else "static_" + name.rsplit("/", 1)[-1].replace(".tik", ""))
        e = self.entity(cls, origin, model=name, angle=fmt(yaw % 360), **keys)
        if scale != 1.0:
            e["scale"] = fmt(scale)
        return e

    def prop(self, tik: str, x: float, y: float, z: float, yaw: float = 0, scale: float = 1.0,
             hang: bool = False, **keys) -> Entity:
        """Place a stock prop so its base sits on ``z`` (or, with ``hang``, its top touches ``z``)."""
        from . import props
        info = props.get(tik)
        oz = z
        if info:
            oz = z - info.maxs[2] * scale if hang else z - info.mins[2] * scale
        return self.static_model(tik, (x, y, oz), yaw, scale, **keys)

    # output ---------------------------------------------------------------------
    def to_map(self) -> MapFile:
        world = Entity(dict(self.world.props), list(self.world.prims))
        if self.carver:
            world.prims = self.carver.brushes() + world.prims
        return MapFile([world] + self.entities)

    def save(self, path: str) -> MapFile:
        m = self.to_map()
        m.save(path)
        return m
