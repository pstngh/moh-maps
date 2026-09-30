"""Architectural building blocks on top of mohkit.build.

Everything here adds *detail* geometry (``+surfaceparm detail``) or entities to a
MapBuilder; structure (the sealed hull) comes from the Carver. Dimensions follow
the player: 30 wide, ~94 tall standing, eye ~82, max step 18 (see docs/design.md).

Directions are compass names: ``north`` = +Y, ``east`` = +X.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from .build import CAULK_M, Carver, Air, MapBuilder, Material, MatLike, aabb, mat

DIRS = {"north": (0, 1), "south": (0, -1), "east": (1, 0), "west": (-1, 0)}
YAW = {"east": 0, "north": 90, "west": 180, "south": 270}


def stairs(b: MapBuilder, x: float, y: float, z: float, direction: str, width: float, rise: float,
           tread: MatLike, riser: Optional[MatLike] = None, step_h: float = 8, step_d: float = 16,
           solid_under: bool = True) -> tuple[float, float, float]:
    """Straight flight starting at (x, y, z) (the near edge centre, floor level) climbing
    ``rise`` units toward ``direction``. Returns the top landing edge centre.

    Steps are separate detail boxes that reach down to ``z`` (``solid_under``) so no
    gap opens underneath. 8 high x 16 deep is the stock AA proportion.
    """
    n = max(1, round(rise / step_h))
    h = rise / n
    dx, dy = DIRS[direction]
    riser = riser or tread
    top_m = {"top": tread, "default": riser}
    for i in range(n):
        z1 = z + h * (i + 1)
        z0 = z if solid_under else z1 - h
        a0, a1 = i * step_d, (i + 1) * step_d
        if dx:
            xa, xb = sorted((x + dx * a0, x + dx * a1))
            b.box((xa, y - width / 2, z0), (xb, y + width / 2, z1), top_m)
        else:
            ya, yb = sorted((y + dy * a0, y + dy * a1))
            b.box((x - width / 2, ya, z0), (x + width / 2, yb, z1), top_m)
    run = n * step_d
    return (x + dx * run, y + dy * run, z + rise)


def ramp(b: MapBuilder, x0, y0, x1, y1, z0, z1, direction: str, m: MatLike, surface: Optional[MatLike] = None) -> None:
    """Wedge rising from z0 to z1 toward ``direction`` over the XY rectangle."""
    if direction == "east":
        pts = [(x0, y0, z0), (x0, y1, z0), (x1, y0, z0), (x1, y1, z0), (x1, y0, z1), (x1, y1, z1)]
    elif direction == "west":
        pts = [(x1, y0, z0), (x1, y1, z0), (x0, y0, z0), (x0, y1, z0), (x0, y0, z1), (x0, y1, z1)]
    elif direction == "north":
        pts = [(x0, y0, z0), (x1, y0, z0), (x0, y1, z0), (x1, y1, z0), (x0, y1, z1), (x1, y1, z1)]
    else:
        pts = [(x0, y1, z0), (x1, y1, z0), (x0, y0, z0), (x1, y0, z0), (x0, y0, z1), (x1, y0, z1)]
    b.hull(pts, {"up": surface or m, "default": m})


def opening_frame(b: MapBuilder, wall_axis: str, plane: float, wall_t: float, u0: float, u1: float, z0: float,
                  z1: float, m: MatLike, width: float = 8, proud: float = 2, sill: bool = False) -> None:
    """Trim around a rectangular opening in a wall.

    ``wall_axis`` is ``"x"`` for a wall whose faces are perpendicular to X (the wall
    runs along Y) or ``"y"``. ``plane`` is the wall's lower coordinate on that axis and
    ``wall_t`` its thickness; ``u0..u1`` is the opening span along the wall.
    The frame protrudes ``proud`` units from both wall faces.
    """
    a0, a1 = plane - proud, plane + wall_t + proud
    pieces = [(u0 - width, u0, z0, z1 + width), (u1, u1 + width, z0, z1 + width), (u0, u1, z1, z1 + width)]
    if sill:
        pieces.append((u0 - width, u1 + width, z0 - 4, z0))
    for pu0, pu1, pz0, pz1 in pieces:
        if wall_axis == "x":
            b.box((a0, pu0, pz0), (a1, pu1, pz1), m)
        else:
            b.box((pu0, a0, pz0), (pu1, a1, pz1), m)


def baseboard(b: MapBuilder, room: Air, m: MatLike, height: float = 8, depth: float = 2,
              gaps: Sequence[tuple[str, float, float]] = ()) -> None:
    """Skirting along the four walls of an air box. ``gaps`` = (side, u0, u1) spans to skip
    (doorways). Side names are the wall's compass side of the room."""
    (x0, y0, z0), (x1, y1, _) = room.bounds

    def run(side, a, c, emit):
        cuts = sorted((g[1], g[2]) for g in gaps if g[0] == side)
        cur = a
        for g0, g1 in cuts:
            if g0 > cur:
                emit(cur, min(g0, c))
            cur = max(cur, g1)
        if cur < c:
            emit(cur, c)

    run("south", x0, x1, lambda u0, u1: b.box((u0, y0, z0), (u1, y0 + depth, z0 + height), m))
    run("north", x0, x1, lambda u0, u1: b.box((u0, y1 - depth, z0), (u1, y1, z0 + height), m))
    run("west", y0 + depth, y1 - depth, lambda u0, u1: b.box((x0, u0, z0), (x0 + depth, u1, z0 + height), m))
    run("east", y0 + depth, y1 - depth, lambda u0, u1: b.box((x1 - depth, u0, z0), (x1, u1, z0 + height), m))


def beams(b: MapBuilder, room: Air, axis: str, spacing: float, m: MatLike, size: float = 12, drop: float = 12) -> None:
    """Ceiling beams across an air box, running along ``axis`` ("x" or "y")."""
    (x0, y0, _), (x1, y1, z1) = room.bounds
    if axis == "x":
        n = int((y1 - y0) // spacing)
        off = (y1 - y0 - (n - 1) * spacing) / 2 if n > 0 else 0
        for i in range(max(0, n)):
            yc = y0 + off + i * spacing
            b.box((x0, yc - size / 2, z1 - drop), (x1, yc + size / 2, z1), m)
    else:
        n = int((x1 - x0) // spacing)
        off = (x1 - x0 - (n - 1) * spacing) / 2 if n > 0 else 0
        for i in range(max(0, n)):
            xc = x0 + off + i * spacing
            b.box((xc - size / 2, y0, z1 - drop), (xc + size / 2, y1, z1), m)


def column(b: MapBuilder, x: float, y: float, z0: float, z1: float, m: MatLike, size: float = 24,
           base: Optional[MatLike] = None, cap: bool = True) -> None:
    s = size / 2
    b.box((x - s, y - s, z0), (x + s, y + s, z1), m)
    if base is not None or cap:
        bm = base or m
        b.box((x - s - 4, y - s - 4, z0), (x + s + 4, y + s + 4, z0 + 12), bm)
        if cap:
            b.box((x - s - 4, y - s - 4, z1 - 8), (x + s + 4, y + s + 4, z1), bm)


def gable_roof(b: MapBuilder, x0, y0, x1, y1, z: float, rise: float, ridge_axis: str, roof: MatLike,
               gable: MatLike, overhang: float = 16, thickness: float = 8, soffit: Optional[MatLike] = None,
               segment: float = 512) -> None:
    """Pitched roof over the rectangle (x0,y0)-(x1,y1) whose walls end at height ``z``.

    Two sloped slabs meet at a ridge ``rise`` above ``z`` running along ``ridge_axis``;
    eaves and gable ends overhang the walls by ``overhang``; triangular gable walls close
    the ends. Long roofs are cut into ``segment``-long pieces (the renderer drops faces
    with more than 64 vertices). For a ridge along Y pass a roof material rotated 90 so
    shingle rows follow the eaves.
    """
    o = overhang
    spec = {"up": roof, "default": soffit or gable}
    if ridge_axis == "x":
        a0, a1, c0, c1 = x0, x1, y0, y1
    else:
        a0, a1, c0, c1 = y0, y1, x0, x1
    cm, half = (c0 + c1) / 2, (c1 - c0) / 2
    drop = o * rise / half
    n = max(1, math.ceil((a1 - a0 + 2 * o) / segment))
    edges = [a0 - o + (a1 - a0 + 2 * o) * i / n for i in range(n + 1)]

    def P(a, c, zz):
        return (a, c, zz) if ridge_axis == "x" else (c, a, zz)

    for sa, sb in zip(edges, edges[1:]):
        for ce in (c0 - o, c1 + o):
            pts = []
            for aa in (sa, sb):
                pts += [P(aa, ce, z - drop), P(aa, ce, z - drop + thickness), P(aa, cm, z + rise),
                        P(aa, cm, z + rise + thickness)]
            b.hull(pts, spec)
    for ga, gb in ((a0, a0 + 8), (a1 - 8, a1)):
        b.hull([P(ga, c0, z), P(gb, c0, z), P(ga, c1, z), P(gb, c1, z), P(ga, cm, z + rise), P(gb, cm, z + rise)],
               gable)


def lamp(b: MapBuilder, x: float, y: float, ceiling_z: float, intensity: float = 180,
         color=(1.0, 0.86, 0.66), model: str = "lights/hanglamp.tik") -> None:
    """Lamp hanging from a ceiling at ``ceiling_z`` with its light just under the shade."""
    from . import props
    b.prop(model, x, y, ceiling_z, hang=True)
    info = props.get(model)
    height = (info.maxs[2] - info.mins[2]) if info else 40
    b.light((x, y, ceiling_z - height - 8), intensity, color)


# lightpost_sidemounted: bracket lantern whose wall mount points -Y at yaw 0 (measured with propview)
_BRACKET_YAW = {"south": 0, "east": 90, "north": 180, "west": 270}


def wall_lantern(b: MapBuilder, x: float, y: float, z: float, wall: str, intensity: float = 160,
                 color=(1.0, 0.82, 0.58)) -> None:
    """Street lantern on a wall bracket. (x, y) is a point on the wall face, ``wall`` is the
    compass side the wall is on (seen from the lantern), ``z`` the lantern height."""
    dx, dy = DIRS[wall]
    lx, ly = x - dx * 20, y - dy * 20
    b.static_model("static/lightpost_sidemounted.tik", (lx, ly, z), _BRACKET_YAW[wall])
    b.light((lx, ly, z + 4), intensity, color)


def crate_stack(b: MapBuilder, x: float, y: float, z: float, m: MatLike, size: float = 48, layout: str = "L") -> None:
    """Brush crates as cover (func_crate breakables are entity work; these are static)."""
    s = size
    cells = {"1": [(0, 0, 0)], "2": [(0, 0, 0), (s, 0, 0)], "L": [(0, 0, 0), (s, 0, 0), (0, s, 0), (0, 0, s)],
             "3": [(0, 0, 0), (s, 0, 0), (s / 2, 0, s)]}[layout]
    for cx, cy, cz in cells:
        b.box((x + cx, y + cy, z + cz), (x + cx + s, y + cy + s, z + cz + s), m)


# ---------------------------------------------------------------------------
# Texture fitting and facade openings

def fit(shader: str, normal: tuple, u0: float, u1: float, top: float, scale: float = 1.0,
        scale_t: Optional[float] = None) -> Material:
    """Material whose image top-left corner lands on a wall panel's top-left corner as seen
    by a viewer facing the wall (so windows/doors/signs are not mirrored).

    ``normal`` is the visible face's normal (pointing at the viewer). ``u0..u1`` is the
    panel span along the wall's texture axis (Y for X-facing walls, X for Y-facing walls)
    and ``top`` its top z. Q3 projection: s = dot(p, axis_s)/scale + shift.
    """
    st = scale_t or scale
    nx, ny = normal[0], normal[1]
    mirrored = nx < -0.5 or ny > 0.5
    if mirrored:
        return Material(shader, (-scale, st), 0.0, (u1 / scale, top / st))
    return Material(shader, (scale, st), 0.0, (-u0 / scale, top / st))


_SIDE_AXIS = {"north": ("y", 1), "south": ("y", -1), "east": ("x", 1), "west": ("x", -1)}
_INWARD = {"north": (0, -1, 0), "south": (0, 1, 0), "east": (-1, 0, 0), "west": (1, 0, 0)}


def recess(cv: Carver, air: Air, side: str, u0: float, u1: float, z0: float, z1: float, depth: float,
           back: MatLike, reveal: MatLike, sill: Optional[MatLike] = None, lintel: Optional[MatLike] = None,
           name: str = "") -> Air:
    """Carve a shallow opening into the wall on ``side`` of ``air`` (a window/door niche).

    ``u0..u1`` spans along the wall (x for north/south walls, y for east/west), ``z0..z1``
    vertically. ``back`` is the material of the niche's back face; use ``fit`` so an
    image of a window or door lands exactly in the niche. Keep ``depth + carver thickness``
    below the wall thickness so the niche does not open into the room behind.
    """
    (x0, y0, _), (x1, y1, _) = air.bounds
    if side == "north":
        bb = aabb(u0, y1, z0, u1, y1 + depth, z1)
    elif side == "south":
        bb = aabb(u0, y0 - depth, z0, u1, y0, z1)
    elif side == "east":
        bb = aabb(x1, u0, z0, x1 + depth, u1, z1)
    else:
        bb = aabb(x0 - depth, u0, z0, x0, u1, z1)
    return cv.add(Air(bb, floor=sill or reveal, ceiling=lintel or reveal,
                      walls={side: back, "default": reveal}, name=name or f"recess_{side}"))


def window(cv: Carver, air: Air, side: str, u0: float, u1: float, z0: float, z1: float, image: str,
           image_px: tuple[int, int], reveal: MatLike, sill: Optional[MatLike] = None,
           lintel: Optional[MatLike] = None, depth: float = 8) -> Air:
    """Niche with ``image`` (a window or door picture, e.g. general_structure/denmark_win2,
    ``image_px`` = its pixel size) stretched exactly over the niche's back face."""
    n = _INWARD[side]
    back = fit(image, n, u0, u1, z1, scale=(u1 - u0) / image_px[0], scale_t=(z1 - z0) / image_px[1])
    return recess(cv, air, side, u0, u1, z0, z1, depth, back, reveal, sill, lintel)


# ---------------------------------------------------------------------------
# Terrain (MOHAA LOD terrain, terrainDef)

def terrain(b: MapBuilder, x0: float, y0: float, z0: float, patches_x: int, patches_y: int, height,
            shader: str, texture_size: float = 512, scale: float = 1.0):
    """Heightfield terrain: ``patches_x`` x ``patches_y`` patches of 512x512 units (8x8 cells of
    64) starting at (x0, y0, z0). ``height(x, y)`` returns the ground height above ``z0``
    (world x, y). Heights are rounded to the engine's 2-unit steps; each 512x512 patch may
    span at most 510 units of height.

    ``texture_size`` is the repeat size in world units of the texture (the terrainDef control
    field that stock maps set to 256 or 512; 0 smears the texture across the whole patch).
    Terrain collides and is in the bot navmesh, but does not seal the map: keep it inside
    Carver air whose floor is below it.
    """
    from .mapfile import Terrain, TerrainControl, TerrainSample
    w, h = patches_x * 8 + 1, patches_y * 8 + 1
    grid = [[max(0.0, round(float(height(x0 + c * 64, y0 + r * 64)) / 2) * 2) for c in range(w)] for r in range(h)]
    for py in range(patches_y):
        for px in range(patches_x):
            cells = [grid[r][c] for r in range(py * 8, py * 8 + 9) for c in range(px * 8, px * 8 + 9)]
            if max(cells) - min(cells) > 510:
                raise ValueError(f"terrain patch ({px},{py}) spans {max(cells) - min(cells):.0f} > 510 units")
    samples = [TerrainSample(grid[r][c], [], []) for r in range(h) for c in range(w)]
    ctl = ["0", "0", "0.00", f"{texture_size:g}", f"{scale:g}", f"{scale:g}", "0", "0", "0"]
    controls = [TerrainControl(0, 0, shader, list(ctl)) for _ in range((patches_x + 1) * (patches_y + 1))]
    t = Terrain(w, h, 0, (float(x0), float(y0), float(z0)), controls, samples)
    b.world.prims.append(t)
    return t


# ---------------------------------------------------------------------------
# Facades

_FACE_OF = {"north": "south", "south": "north", "east": "west", "west": "east"}


def strip(b: MapBuilder, air: Air, side: str, u0: float, u1: float, z0: float, z1: float, depth: float,
          m) -> None:
    """A thin detail box laid against the wall on ``side`` of ``air`` (mouldings, base courses,
    shutters). ``u0..u1`` runs along the wall (x for north/south walls, y for east/west)."""
    (x0, y0, _), (x1, y1, _) = air.bounds
    if side == "north":
        b.box((u0, y1 - depth, z0), (u1, y1, z1), m)
    elif side == "south":
        b.box((u0, y0, z0), (u1, y0 + depth, z1), m)
    elif side == "east":
        b.box((x1 - depth, u0, z0), (x1, u1, z1), m)
    else:
        b.box((x0, u0, z0), (x0 + depth, u1, z1), m)


def shutter(b: MapBuilder, air: Air, side: str, u0: float, u1: float, z0: float, z1: float, frame: MatLike,
            image: str = "central_europe/shutter_set2", image_px: tuple[int, int] = (64, 128)) -> None:
    """An open shutter panel (image fitted to the panel) standing proud of the wall."""
    img = fit(image, _INWARD[side], u0, u1, z1, scale=(u1 - u0) / image_px[0], scale_t=(z1 - z0) / image_px[1])
    strip(b, air, side, u0, u1, z0, z1, 2, {"default": frame, _FACE_OF[side]: img})


def facade(b: MapBuilder, cv: Carver, air: Air, side: str, u0: float, u1: float,
           storeys: Sequence[tuple[float, float]], skip: Sequence[tuple[float, float]] = (), *,
           window_image: str = "general_structure/denmark_win2", window_px: tuple[int, int] = (128, 180),
           reveal: MatLike = "general_structure/stonebricks1", shutters: Optional[MatLike] = None,
           moulding: Optional[MatLike] = None, moulding_z: Optional[float] = None,
           spacing: float = 192, win_w: float = 56, depth: float = 8,
           doors: Sequence[float] = (), door_image: str = "general_structure/doubledoor2",
           door_px: tuple[int, int] = (128, 256), door_size: tuple[float, float] = (64, 128)) -> int:
    """Decorate one outdoor wall: window niches in regular bays for every storey
    ``(sill_z, top_z)``, optional shutters either side, and an optional moulding strip at
    ``moulding_z`` broken around ``skip`` spans (real openings). ``doors`` lists wall
    positions; the nearest bay gets a (decorative) door instead of its ground-floor window.
    Keep niche ``depth`` + carver thickness below the wall thickness. Returns windows placed.
    """
    axis = 0 if side in ("north", "south") else 1
    lo, hi = max(u0, air.bounds[0][axis]), min(u1, air.bounds[1][axis])
    n = int((hi - lo) // spacing)
    placed = 0
    if n > 0:
        start = lo + ((hi - lo) - (n - 1) * spacing) / 2
        for i in range(n):
            c = start + i * spacing
            a, e = c - win_w / 2, c + win_w / 2
            if any(a < s1 + 24 and e > s0 - 24 for s0, s1 in skip):
                continue
            is_door = any(abs(c - d) <= spacing / 2 for d in doors)
            for si, (z0, z1) in enumerate(storeys):
                if si == 0 and is_door:
                    door(cv, air, side, c, air.bounds[0][2], door_size[0], door_size[1], door_image,
                         door_px, reveal, depth)
                    continue
                window(cv, air, side, a, e, z0, z1, window_image, window_px, reveal, sill=reveal, depth=depth)
                if shutters is not None:
                    shutter(b, air, side, a - 28, a - 4, z0, z1, shutters)
                    shutter(b, air, side, e + 4, e + 28, z0, z1, shutters)
                placed += 1
    if moulding is not None and moulding_z is not None:
        cur, segs = lo, []
        for s0, s1 in sorted(skip):
            if s0 > cur:
                segs.append((cur, min(s0, hi)))
            cur = max(cur, s1)
        if cur < hi:
            segs.append((cur, hi))
        for sa, sb in segs:
            if sb - sa >= 8:
                strip(b, air, side, sa, sb, moulding_z - 4, moulding_z + 8, 4, moulding)
    return placed


def door(cv: Carver, air: Air, side: str, u: float, z: float = 0, width: float = 64, height: float = 128,
         image: str = "general_structure/doubledoor2", image_px: tuple[int, int] = (128, 256),
         reveal: MatLike = "general_structure/stonebricks1", depth: float = 8) -> Air:
    """A closed (decorative) door: a niche centred at ``u`` on the wall with a door image."""
    return window(cv, air, side, u - width / 2, u + width / 2, z, z + height, image, image_px, reveal,
                  sill=reveal, depth=depth)
