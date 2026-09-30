"""Small, dependency-free 3D geometry used by the map tools.

Conventions match the Quake 3 / MOHAA .map format:

* A brush face stores three points ``a, b, c``. Its plane normal is
  ``normalize((c - a) x (b - a))`` and points *out of* the brush.
* A brush is the convex intersection of the half-spaces ``dot(n, p) <= d``.
* Z is up. Yaw 0 faces +X, yaw 90 faces +Y.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

Vec3 = tuple[float, float, float]

EPS = 1e-6
ON_EPS = 0.01  # distance treated as "on plane" when clipping windings
WORLD = 65536.0


def add(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Sequence[float], s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a: Sequence[float]) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Sequence[float]) -> Vec3:
    n = length(a)
    if n < EPS:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a: Sequence[float], b: Sequence[float], t: float) -> Vec3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def rotate_z(p: Sequence[float], yaw_deg: float, center: Sequence[float] = (0, 0, 0)) -> Vec3:
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    x, y = p[0] - center[0], p[1] - center[1]
    return (center[0] + x * c - y * s, center[1] + x * s + y * c, p[2])


class Plane:
    __slots__ = ("normal", "dist")

    def __init__(self, normal: Vec3, dist: float):
        self.normal = normal
        self.dist = dist

    @classmethod
    def from_points(cls, a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> "Plane":
        n = normalize(cross(sub(c, a), sub(b, a)))
        return cls(n, dot(n, a))

    def distance(self, p: Sequence[float]) -> float:
        return dot(self.normal, p) - self.dist

    def flipped(self) -> "Plane":
        return Plane(scale(self.normal, -1), -self.dist)

    def is_degenerate(self) -> bool:
        return length(self.normal) < 0.5

    def same_as(self, o: "Plane", eps: float = 1e-4) -> bool:
        return (abs(self.normal[0] - o.normal[0]) < eps and abs(self.normal[1] - o.normal[1]) < eps
                and abs(self.normal[2] - o.normal[2]) < eps and abs(self.dist - o.dist) < 0.01)

    def __repr__(self) -> str:
        n = self.normal
        return f"Plane(({n[0]:.4g}, {n[1]:.4g}, {n[2]:.4g}), {self.dist:.4g})"


def points_for_plane(normal: Sequence[float], dist: float, size: float = 64.0) -> tuple[Vec3, Vec3, Vec3]:
    """Three points on a plane, ordered so that ``Plane.from_points`` reproduces ``normal``.

    Points are snapped to integers when the plane is axial so written maps stay tidy.
    """
    n = normalize(normal)
    # Choose a reference axis least aligned with n.
    ax = min(range(3), key=lambda i: abs(n[i]))
    ref = [0.0, 0.0, 0.0]
    ref[ax] = 1.0
    u = normalize(cross(n, ref))
    v = cross(n, u)
    origin = scale(n, dist)
    a = origin
    b = add(origin, scale(u, size))
    c = add(origin, scale(v, size))
    # from_points gives normalize((c-a) x (b-a)) = normalize(v x u) = -(n) for right-handed u,v,n?
    if dot(normalize(cross(sub(c, a), sub(b, a))), n) < 0:
        b, c = c, b
    return (_tidy(a), _tidy(b), _tidy(c))


def _tidy(p: Sequence[float]) -> Vec3:
    return tuple(round(x) if abs(x - round(x)) < 1e-6 else x for x in p)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Windings (convex polygons)

Winding = list[Vec3]


def base_winding(plane: Plane, size: float = WORLD) -> Winding:
    n = plane.normal
    # Pick major axis to build an up vector.
    ax = max(range(3), key=lambda i: abs(n[i]))
    up = (0.0, 0.0, 1.0) if ax != 2 else (1.0, 0.0, 0.0)
    d = dot(up, n)
    up = normalize(sub(up, scale(n, d)))
    right = cross(up, n)
    org = scale(n, plane.dist)
    up = scale(up, size)
    right = scale(right, size)
    return [
        sub(add(org, up), right),
        add(add(org, up), right),
        add(sub(org, up), right),
        sub(sub(org, up), right),
    ]


def clip_winding(w: Winding, plane: Plane, keep_front: bool = False, eps: float = ON_EPS) -> Winding:
    """Clip a convex winding by a plane. Keeps the back side by default."""
    if not w:
        return w
    dists = [plane.distance(p) for p in w]
    if keep_front:
        dists = [-x for x in dists]
    sides = [1 if d > eps else (-1 if d < -eps else 0) for d in dists]
    if all(s >= 0 for s in sides) and any(s > 0 for s in sides):
        return []
    if all(s <= 0 for s in sides):
        return list(w)
    out: Winding = []
    n = len(w)
    for i in range(n):
        p, q = w[i], w[(i + 1) % n]
        dp, dq = dists[i], dists[(i + 1) % n]
        sp, sq = sides[i], sides[(i + 1) % n]
        if sp <= 0:
            out.append(p)
        if (sp > 0 and sq < 0) or (sp < 0 and sq > 0):
            t = dp / (dp - dq)
            out.append(lerp(p, q, t))
    return out


def winding_area(w: Winding) -> float:
    if len(w) < 3:
        return 0.0
    total = (0.0, 0.0, 0.0)
    for i in range(1, len(w) - 1):
        total = add(total, cross(sub(w[i], w[0]), sub(w[i + 1], w[0])))
    return 0.5 * length(total)


def winding_center(w: Winding) -> Vec3:
    n = len(w)
    return (sum(p[0] for p in w) / n, sum(p[1] for p in w) / n, sum(p[2] for p in w) / n)


def brush_windings(planes: Sequence[Plane]) -> list[Winding]:
    """Polygon for every face of a convex brush (empty list entry if the face is culled)."""
    out = []
    for i, pl in enumerate(planes):
        w = base_winding(pl)
        for j, other in enumerate(planes):
            if i == j or not w:
                continue
            if pl.same_as(other):
                w = [] if j < i else w  # duplicate plane: keep first occurrence only
                continue
            w = clip_winding(w, other)
        out.append(w)
    return out


def bounds_of(points: Iterable[Sequence[float]]) -> tuple[Vec3, Vec3]:
    xs, ys, zs = [], [], []
    for p in points:
        xs.append(p[0]); ys.append(p[1]); zs.append(p[2])
    if not xs:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def convex_volume(windings: Sequence[Winding]) -> float:
    pts = [p for w in windings for p in w]
    if not pts:
        return 0.0
    c = winding_center(pts)
    vol = 0.0
    for w in windings:
        for i in range(1, len(w) - 1):
            vol += abs(dot(sub(w[0], c), cross(sub(w[i], c), sub(w[i + 1], c)))) / 6.0
    return vol
