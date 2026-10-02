"""Site-scale building blocks: maps traced from a reference image, building masses with rooms,
outdoor air computed around them, and the drops, rocks and mountains of open or cliff-top sites.

First built for ``maps/mk_summit`` (a plateau on cliffs over a valley); see docs/design.md
"Cliff-top and island maps" and docs/from-reference.md "A whole map from another game".

Typical use::

    g = site.RefGrid(units_per_px=12, origin_px=(256, 272))       # positions in minimap pixels
    hall = site.Building("hall", g.rect(200, 230, 320, 318), top=416, face=CONC)
    solids = site.plateau_solids([g.rect(*r) for r in FOOT_PX], [hall], ground=0, void=-1536)
    site.outdoor_air(cv, aabb(*OUTER[:2], -1536, *OUTER[2:], 1280), solids,
                     floor=site.floors(-1536, 0, valley=SNOW, roof=SNOW, ground=YARD),
                     walls=site.walls(OUTER, [hall], sky=SKY, below=CLIFF), cuts=(0,))
    hall.room(cv, 0, 176, floor=TILE, walls=WALL, ceiling=CEIL)
    hall.door(b, cv, "south", 0)
    site.void_triggers(b, OUTER, -1536, solids)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from . import kit
from .build import AABB, Air, Carver, MapBuilder, Material, MatLike, aabb, box, merge_boxes, subtract_all

Rect = tuple[float, float, float, float]          # x0, y0, x1, y1 (world)


@dataclass(frozen=True)
class RefGrid:
    """Positions written in a reference image's pixels (u right, v down), e.g. a game's minimap
    traced at ``units_per_px``; ``origin_px`` is the pixel at world (0, 0). Every result snaps to
    ``snap`` units, so numbers in build.py can be checked against the picture
    (``META["underlay"]`` draws the plan over it)."""
    units_per_px: float
    origin_px: tuple[float, float]
    snap: int = 16

    def x(self, u: float) -> int:
        return self.snap * round((u - self.origin_px[0]) * self.units_per_px / self.snap)

    def y(self, v: float) -> int:
        return self.snap * round((self.origin_px[1] - v) * self.units_per_px / self.snap)

    def rect(self, u0: float, v0: float, u1: float, v1: float) -> tuple[int, int, int, int]:
        """World rect (x0, y0, x1, y1) of the pixel rect (u0, v0)-(u1, v1)."""
        return self.x(u0), self.y(v1), self.x(u1), self.y(v0)

    def point(self, u: float, v: float) -> tuple[int, int]:
        return self.x(u), self.y(v)


@dataclass
class Building:
    """A solid building mass from ``ground`` to ``top`` over ``rect`` (its outer walls, world
    units). It is not air: ``outdoor_air`` leaves it out, ``room`` carves rooms inside it and
    ``opening``/``door``/``window`` cut through its ``thickness``-deep walls. ``face`` is the
    outside wall material (``walls`` picks it by position). The style fields (reveal, sill,
    frame, lamp) apply to every opening made through this building."""
    name: str
    rect: tuple[int, int, int, int]
    top: float
    face: MatLike
    ground: float = 0
    thickness: float = 16
    enter: bool = True
    reveal: MatLike = "norway/penwall1a"
    sill: MatLike = "general_structure/concretefill_winter"
    frame: Optional[MatLike] = "norway/nor_panelflat"
    lamp_color: tuple[float, float, float] = (1.0, 0.82, 0.58)
    lamp_intensity: float = 160

    def contains(self, x: float, y: float, z: float) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 <= x <= x1 and y0 <= y <= y1 and self.ground - 1 <= z <= self.top + 1

    def mass(self) -> AABB:
        x0, y0, x1, y1 = self.rect
        return aabb(x0, y0, self.ground, x1, y1, self.top)

    def room(self, cv: Carver, z0: float, z1: float, floor, walls, ceiling, inset: Optional[float] = None,
             name: str = "") -> Air:
        """Air inside the walls (``inset`` = wall thickness by default) from z0 to z1."""
        t = self.thickness if inset is None else inset
        x0, y0, x1, y1 = self.rect
        return cv.room(x0 + t, y0 + t, z0, x1 - t, y1 - t, z1, floor=floor, walls=walls, ceiling=ceiling,
                       name=name or self.name)

    def opening(self, cv: Carver, side: str, u: float, w: float, z0: float, z1: float,
                reveal: Optional[MatLike] = None, floor: Optional[MatLike] = None, name: str = "door") -> Air:
        """Air through the wall on ``side`` (compass side of the building), centred at world ``u``
        (x for north/south walls, y for east/west), overlapping the air on both sides by 8."""
        t = self.thickness
        x0, y0, x1, y1 = self.rect
        a, b_ = u - w / 2, u + w / 2
        if side == "south":
            bb = (a, y0 - 8, z0, b_, y0 + t + 8, z1)
        elif side == "north":
            bb = (a, y1 - t - 8, z0, b_, y1 + 8, z1)
        elif side == "west":
            bb = (x0 - 8, a, z0, x0 + t + 8, b_, z1)
        else:
            bb = (x1 - t - 8, a, z0, x1 + 8, b_, z1)
        rv = self.reveal if reveal is None else reveal
        return cv.room(*bb, floor=self.sill if floor is None else floor, walls=rv, ceiling=rv, name=name)

    def door(self, b: MapBuilder, cv: Carver, side: str, u: float, w: float = 80, h: float = 128,
             lamp: bool = True, **kw) -> Air:
        """Doorway at ground level with a frame round it and a wall lantern over it outside."""
        a = self.opening(cv, side, u, w, self.ground, self.ground + h, **kw)
        t = self.thickness
        x0, y0, x1, y1 = self.rect
        if self.frame is not None:
            axis, plane = {"south": ("y", y0), "north": ("y", y1 - t), "west": ("x", x0), "east": ("x", x1 - t)}[side]
            kit.opening_frame(b, axis, plane, t, u - w / 2, u + w / 2, self.ground, self.ground + h, self.frame, width=6)
        if lamp:
            # the lantern stands outside the wall; ``wall`` is where the wall is, seen from it
            at = {"south": (u, y0, "north"), "north": (u, y1, "south"), "west": (x0, u, "east"), "east": (x1, u, "west")}
            lx, ly, wall = at[side]
            kit.wall_lantern(b, lx, ly, self.ground + h + 40, wall, self.lamp_intensity, self.lamp_color)
        return a

    def window(self, cv: Carver, side: str, u: float, w: float = 96, z0: float = 64, z1: float = 136, **kw) -> Air:
        """Open window (no glass) through the wall; sill at z0 (64: players can't climb through)."""
        return self.opening(cv, side, u, w, z0, z1, name="window", **kw)


def in_rects(x: float, y: float, rects: Sequence[Rect]) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)


def plateau_solids(footprint: Sequence[Rect], buildings: Sequence[Building], ground: float,
                   void: float) -> list[AABB]:
    """What is not outdoor air: the ground under every footprint rect (from below the valley
    floor up to ``ground``) and every building mass."""
    solids = [aabb(x0, y0, void - 64, x1, y1, ground) for x0, y0, x1, y1 in footprint]
    solids += [aabb(*bl.rect[:2], bl.ground, *bl.rect[2:], bl.top) for bl in buildings]
    return solids


def outdoor_air(cv: Carver, outer: AABB, solids: Sequence[AABB], floor, walls, cuts: Sequence[float] = (),
                name: str = "out") -> list[Air]:
    """Sky-topped air filling ``outer`` minus ``solids`` (merged boxes). The drops round a
    plateau are then real and the hull stays sealed. ``floor``/``walls`` are usually
    position functions (``floors``, ``walls``); ``cuts`` = heights where the wall material
    changes (ground level between cliff and facade)."""
    out = []
    for i, p in enumerate(merge_boxes(subtract_all([outer], list(solids)))):
        out.append(cv.add(Air(p, floor=floor, walls=walls, sky=True, name=f"{name}{i}", cuts=tuple(cuts))))
    return out


def walls(outer: Rect, buildings: Sequence[Building], sky: MatLike, below: MatLike, ground: float = 0):
    """Wall function for ``outdoor_air``: sky on the outer box, a building's ``face`` where the
    solid behind the face is that building (above ``ground``), ``below`` elsewhere (cliffs)."""
    def fn(n, c):
        x, y, z = c
        if x <= outer[0] + 1 or x >= outer[2] - 1 or y <= outer[1] + 1 or y >= outer[3] - 1:
            return sky
        px, py = x - n[0] * 8, y - n[1] * 8          # a point inside the solid behind the face
        if z > ground:
            for bl in buildings:
                if bl.contains(px, py, z):
                    return bl.face
        return below
    return fn


def floors(void: float, ground: float, valley: MatLike, roof: MatLike, ground_m: MatLike):
    """Floor function for ``outdoor_air``: ``valley`` on the valley floor, ``roof`` on anything
    above ground (roofs), ``ground_m`` on the plateau."""
    def fn(n, c):
        z = c[2]
        if z <= void + 1:
            return valley
        if z > ground + 1:
            return roof
        return ground_m
    return fn


def void_triggers(b: MapBuilder, outer: Rect, void: float, solids: Sequence[AABB], height: float = 256,
                  damage: str = "1000") -> None:
    """A trigger_hurt band above the valley floor, one entity per void column: q3map floods from
    a brush entity's bounding-box centre, so one trigger under the whole map (centred inside
    the plateau) leaks the compile."""
    band = aabb(outer[0], outer[1], void, outer[2], outer[3], void + height)
    for lo, hi in merge_boxes(subtract_all([band], list(solids))):
        hurt = b.entity("trigger_hurt", None, damage=damage)
        hurt.prims.append(box(lo, hi, Material("common/trigger")))


def rock_spur(b: MapBuilder, x: float, y: float, top: float, bottom: float, top_m: MatLike, side_m: MatLike,
              r: float = 120) -> None:
    """Rock outcrop from ``bottom`` (the valley floor) to ``top``: three 7-gon prisms widening
    downward, for trees or masts standing below a plateau's rim."""
    rnd = (x * 7 + y * 13) % 360
    spec = {"top": top_m, "default": side_m}
    b.prism(kit.polygon(x, y, r, 7, rnd), top - 192, top, spec)
    b.prism(kit.polygon(x, y, r * 1.5, 7, rnd + 20), top - 640, top - 192, spec)
    b.prism(kit.polygon(x, y, r * 2.2, 7, rnd + 40), bottom, top - 640, spec)


def mountain_ring(b: MapBuilder, m: MatLike, base: float, n: int = 16, rx: float = 3800, ry: float = 4800,
                  r: float = 1450, low: float = -400, span: float = 850, jitter: float = 300) -> None:
    """``n`` broad peaks on an ellipse (rx, ry) round the origin, from ``base`` to apex heights
    between ``low`` and ``low + span``. Keep the ellipse inside the farplane so the fog leaves
    soft silhouettes (docs/design.md). Each peak is 7 pie-slice wedges (centre, two rim points,
    apex), so no brush is wider than the validator's 1,536 units. Give ``m`` a coarse
    ``density`` (256): nobody sees them up close."""
    for i in range(n):
        a = 2 * math.pi * i / n + 0.2
        x, y = rx * math.cos(a), ry * math.sin(a)
        top = low + span * abs(math.sin(2.3 * i + 0.5))
        apex = (round(x + jitter * math.cos(1.9 * i)), round(y + jitter * math.sin(1.9 * i)), round(top))
        ring = [(round(x + r * math.cos(2 * math.pi * (k + 0.37 * i) / 7)),
                 round(y + r * math.sin(2 * math.pi * (k + 0.37 * i) / 7)), base) for k in range(7)]
        for k in range(7):
            b.hull([(round(x), round(y), base), ring[k], ring[(k + 1) % 7], apex], m)


def boulders_outside(b: MapBuilder, points: Sequence[tuple[float, float]], footprint: Sequence[Rect],
                     center: tuple[float, float], rim: float, model: str = "static/rock_winter_large",
                     half_width: float = 70, height: float = 114, scale: float = 2.5) -> None:
    """Rock props hanging on the cliff faces just below the rim: each point is pushed out from
    ``center`` until the rock clears the footprint, and sunk so its top stays 48 below ``rim``
    (``half_width``/``height`` are the model's at scale 1: rock_winter_large's by default).
    Scales alternate ``scale`` and ``scale + 1``; depths and yaws vary with the index."""
    cx0, cy0 = center
    for i, (x, y) in enumerate(points):
        sc = scale + (i % 2)
        rad = half_width * sc
        dx, dy = x - cx0, y - cy0
        d = math.hypot(dx, dy) or 1.0
        while any(x0 - rad < x < x1 + rad and y0 - rad < y < y1 + rad for x0, y0, x1, y1 in footprint):
            x, y = x + 32 * dx / d, y + 32 * dy / d          # out from the centre until clear of the plateau
        b.prop(model, round(x), round(y), rim - 48 - height * sc - (i % 3) * 64, (i * 67) % 360, sc)


def outside_distance(x: float, y: float, rect: Rect, p: float = 4) -> float:
    """Distance from (x, y) to the rect (0 inside) in the p-norm. p = 4 gives rounded-square
    contours: hills shaped by it slope evenly at the corners (with p = 2 a corner patch passes
    the 510 relief limit first). Use it in a ``kit.terrain`` height function."""
    x0, y0, x1, y1 = rect
    dx = max(x0 - x, 0, x - x1)
    dy = max(y0 - y, 0, y - y1)
    return (dx ** p + dy ** p) ** (1 / p)
