"""Architectural building blocks on top of mohkit.build.

Everything here adds *detail* geometry (``+surfaceparm detail``) or entities to a
MapBuilder; structure (the sealed hull) comes from the Carver. Dimensions follow
the player: 30 wide, ~94 tall standing, eye ~82, max step 18 (see docs/design.md).

Directions are compass names: ``north`` = +Y, ``east`` = +X.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from .build import CAULK_M, Carver, Air, MapBuilder, Material, MatLike, aabb, box, mat, overlaps

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


# ---------------------------------------------------------------------------
# Fixtures and site furniture (first built for mk_summit; generic). Materials default to
# stock AA winter/industrial textures; pass your own palette.

STEEL_V = Material("central_europe_winter/ibeam_vertwnter")      # posts, legs
STEEL_H = Material("central_europe_winter/ibeam_horizwnter")     # rails, beams
CHAIN_LINK = Material("central_europe_winter/secfence1_wntr")    # nonsolid texture, clips players
GRATE = Material("general_industrial/deckgrate_set1b")           # see-through steel deck
PANEL_GREY = Material("norway/nor_panelflat")
CONTROL_PANEL = Material("norway/nor_panel2_v2")
SIGN_RED = Material("general_structure/jh_corrugate4c")
MESH = Material("general_industrial/industrialgrate1")
GLASS = Material("common/dglass")
WOOD_POLE = Material("general_structure/beam_wood1")
PLAYERCLIP = Material("common/playerclip")
CLIP_M = Material("common/clip")             # players and bots (ladder faces and steps)


def polygon(cx: float, cy: float, r: float, n: int = 16, phase: float = 0.0) -> list[tuple[int, int]]:
    """Regular n-gon (integer points) for ``b.prism``; ``phase`` in degrees."""
    return [(round(cx + r * math.cos(math.radians(phase + 360 * i / n))),
             round(cy + r * math.sin(math.radians(phase + 360 * i / n)))) for i in range(n)]


def dome(b: MapBuilder, cx: float, cy: float, z0: float, r: float, m: MatLike, rings: int = 5) -> None:
    """Hemisphere of stacked 16-gon slices standing on z0 (radar domes, observatory caps)."""
    for i in range(rings):
        a0 = math.radians(90 * i / rings)
        a1 = math.radians(90 * (i + 1) / rings)
        rr = r * math.cos((a0 + a1) / 2)
        b.prism(polygon(cx, cy, max(rr, 8), 16, 11.25), z0 + r * math.sin(a0), z0 + r * math.sin(a1), m)


def clip_box(b: MapBuilder, x0, y0, z0, x1, y1, z1) -> None:
    """Playerclip block (keeps players off props without collision, masts, roofs)."""
    b.box((x0, y0, z0), (x1, y1, z1), PLAYERCLIP)


# ---------------------------------------------------------------------------- ladders

def _span(side: str, plane: float, u0, u1, z0, z1, d0, d1):
    """(mins, maxs) of a box ``d0..d1`` out from the wall on ``side`` (toward the street)."""
    s = _OUT[side]
    a, c = sorted((plane + s * d0, plane + s * d1))
    if side in ("north", "south"):
        return (u0, a, z0), (u1, c, z1)
    return (a, u0, z0), (c, u1, z1)


def ladder(b: MapBuilder, side: str, plane: float, u: float, z0: float, z1: float, width: float = 32,
           depth: float = 4, rails: Optional[MatLike] = None, rung: float = 16) -> None:
    """A MOHAA ladder on the wall on ``side`` (the climber faces that way), centred at ``u``,
    from the floor ``z0`` to ``z1``, the top of the ledge the player steps off onto: a
    ``func_ladder`` (a ``common/trigger`` over the ladder and 8 units in front, a
    ``common/origin`` brush on the climb face, ``angle`` into the wall), the ladder's rails
    and rungs (``rails``; none: the wall's own texture is the ladder) and a clip face over
    them so nothing snags. The player gets off at the top only forward onto clear floor
    (docs/entities.md "Ladders"); bots climb ``func_ladder`` (their navmesh links it).
    tests/rooms/laddertest: climbed 170 onto a 160 ledge (2026-10-02)."""
    h = width / 2
    if rails is not None:
        for e in (-h, h - 2):
            b.box(*_span(side, plane, u + e, u + e + 2, z0, z1, 0, depth), rails)
        z = z0 + rung
        while z < z1 - 4:
            b.box(*_span(side, plane, u - h + 2, u + h - 2, z - 1, z + 1, 1, depth - 1), rails)
            z += rung
    b.box(*_span(side, plane, u - h, u + h, z0, z1, 0, depth), CLIP_M)
    face = plane + _OUT[side] * depth
    org = (u, face, (z0 + z1) / 2) if side in ("north", "south") else (face, u, (z0 + z1) / 2)
    e = b.entity("func_ladder", angle=str(YAW[side]))
    e.prims.append(box(*_span(side, plane, u - h, u + h, z0, z1, 0, depth + 8), "common/trigger"))
    e.prims.append(box(tuple(v - 1 for v in org), tuple(v + 1 for v in org), "common/origin"))


STEP_RISE, STEP_DEPTH = 16.0, 1.0


def step_count(z0: float, top: float, rise: float = STEP_RISE) -> int:
    return max(1, math.ceil((top - z0) / rise - 1e-6))


def step_slices(z0: float, top: float, rise: float = STEP_RISE, depth: float = STEP_DEPTH):
    """A CS-style ladder's clip slices, bottom first: ``(z_bottom, z_top, out)``, each
    ``rise`` high and ``depth`` shallower than the one below (``out``: how far it reaches
    from the wall), so running into the column climbs it (shared with the CS:GO converter)."""
    n = step_count(z0, top, rise)
    return [(z0 + (k - 1) * rise, min(z0 + k * rise, top), (n - k + 1) * depth) for k in range(1, n + 1)]


def step_ladder(b: MapBuilder, side: str, plane: float, u0: float, u1: float, z0: float, z1: float,
                rise: float = STEP_RISE, depth: float = STEP_DEPTH, exit: Optional[str] = "forward") -> None:
    """A CS-style ladder: invisible ``common/clip`` slices against the wall on ``side`` from
    ``z0`` to ``z1``. Running into it climbs it, backing off climbs down, and the player
    can step off sideways or onto a ledge at any side of the top, where a ``func_ladder``
    lets them off only forward (use it under floor holes and beside platforms). Bots can't
    climb it. ``exit`` is how a player leaves it at the top ("forward" onto a ledge, "left" /
    "right" onto a platform beside it, as the climber sees it; None: not checked), which
    ``mohkit build --ladders`` tries. The CS:GO converter's ladders (csgo-conversion.md); in tests/rooms/laddertest
    16 x 1, 8 x 1 and 8 x 2 unit columns each climbed 162 onto a 160 ledge (2026-10-02)."""
    slices = step_slices(z0, z1, rise, depth)
    for za, zb, out in slices:
        b.box(*_span(side, plane, u0, u1, za, zb, 0, out), CLIP_M)
    front, uc = plane + _OUT[side] * slices[0][2], (u0 + u1) / 2
    at = lambda d, z: [uc, front + _OUT[side] * d, z] if side in ("north", "south") else [front + _OUT[side] * d, uc, z]  # noqa: E731
    rec = {"style": "steps", "origin": at(0, z0), "angle": YAW[side], "zmin": z0, "zmax": z1,
           "probe_start": at(28, z0 + 1)}
    b.ladders.append({**rec, "exit": exit} if exit else rec)


# ------------------------------------------------------------------------- breakables

# func_window debris: the game sends the window's debristype and the client spawns
# models/fx/windows/debris_<n>.tik (fgame/windows.cpp WindowKilled, cgame/cg_parsemsg.cpp
# CGM_MAKE_WINDOW_DEBRIS). Retail's debris_0..3 are all glass shards, so maps ship their own
# metal and wood debris built from retail effect models and sound aliases.
DEBRIS_GLASS, DEBRIS_METAL, DEBRIS_WOOD = 0, 7, 8
DEBRIS = {"glass": DEBRIS_GLASS, "metal": DEBRIS_METAL, "wood": DEBRIS_WOOD}
# Files shipped at the same, engine-fixed path by every map that uses them: their content
# must not depend on the map (installed pk3s sharing a path override each other,
# pak.path_clashes).
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


def breakable(b: MapBuilder, mins, maxs, m: MatLike, kind: str = "glass", health: int = 5):
    """A ``func_window`` that breaks when shot (``health``), with ``kind`` debris: glass
    (retail shards), metal or wood (``debris_tiki``, packaged through ``b.files``; the CS:GO
    converter's, checked in game in tests/rooms/debristest, csgo-conversion.md)."""
    k = DEBRIS[kind]
    if k != DEBRIS_GLASS:
        b.files[f"models/fx/windows/debris_{k}.tik"] = debris_tiki(k).encode()
    e = b.entity("func_window", health=str(health), debristype=str(k))
    e.prims.append(box(mins, maxs, m))
    return e


def railing(b: MapBuilder, x0, y0, x1, y1, z: float, h: float = 40, rail: MatLike = STEEL_H,
            post: MatLike = STEEL_V) -> None:
    """Thin steel rail with posts every 128 along a straight axis-aligned run (x0..x1 at y0, or
    y0..y1 at x0, whichever is longer). Waist high (40): players can't fall past it by walking."""
    if x1 - x0 >= y1 - y0:
        b.box((x0, y0 - 2, z + h - 4), (x1, y0 + 2, z + h), rail)
        n = max(1, int((x1 - x0) // 128))
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            b.box((x - 2, y0 - 2, z), (x + 2, y0 + 2, z + h - 4), post)
    else:
        b.box((x0 - 2, y0, z + h - 4), (x0 + 2, y1, z + h), rail)
        n = max(1, int((y1 - y0) // 128))
        for i in range(n + 1):
            y = y0 + (y1 - y0) * i / n
            b.box((x0 - 2, y - 2, z), (x0 + 2, y + 2, z + h - 4), post)


def fence(b: MapBuilder, x0, y0, x1, y1, z: float = 0, h: float = 112, mesh: MatLike = CHAIN_LINK,
          post: MatLike = STEEL_V) -> None:
    """Chain-link fence along an axis-aligned run with posts every ~192. The mesh shader is
    nonsolid but clips players (``secfence1_wntr``), so bullets pass and people don't."""
    if x1 - x0 >= y1 - y0:
        b.box((x0, y0 - 1, z), (x1, y0 + 1, z + h), {"north": mesh, "south": mesh, "default": CAULK_M})
        n = max(1, int((x1 - x0) // 192))
        pts = [(x0 + (x1 - x0) * i / n, y0) for i in range(n + 1)]
    else:
        b.box((x0 - 1, y0, z), (x0 + 1, y1, z + h), {"east": mesh, "west": mesh, "default": CAULK_M})
        n = max(1, int((y1 - y0) // 192))
        pts = [(x0, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    for x, y in pts:
        b.box((x - 3, y - 3, z), (x + 3, y + 3, z + h + 8), post)


def dish(b: MapBuilder, x: float, y: float, z: float, r: float, yaw: float, tilt: float = 35,
         m: MatLike = PANEL_GREY, post: MatLike = STEEL_V) -> None:
    """Satellite dish on a post standing on z: a shallow cone (convex hull of a tilted 8-point rim
    and a back point) facing ``yaw``, tilted ``tilt`` degrees up. ``static/dish.tik`` is a tiny
    bowl (31 units), not a satellite dish."""
    a, t = math.radians(yaw), math.radians(tilt)
    fx, fy, fz = math.cos(a) * math.cos(t), math.sin(a) * math.cos(t), math.sin(t)   # facing
    ux, uy, uz = -math.cos(a) * math.sin(t), -math.sin(a) * math.sin(t), math.cos(t)  # rim "up"
    sx, sy = -math.sin(a), math.cos(a)                                                # rim "side"
    cz = z + r + 24
    rim = [(x + r * (math.cos(k * math.pi / 4) * sx + math.sin(k * math.pi / 4) * ux),
            y + r * (math.cos(k * math.pi / 4) * sy + math.sin(k * math.pi / 4) * uy),
            cz + r * math.sin(k * math.pi / 4) * uz) for k in range(8)]
    back = (x - fx * r * 0.45, y - fy * r * 0.45, cz - fz * r * 0.45)
    b.hull([tuple(round(c, 1) for c in q) for q in rim] + [back], m)
    b.box((x - 4, y - 4, z), (x + 4, y + 4, cz - r * 0.3), post)


def billboard(b: MapBuilder, x: float, y: float, z: float, w: float, axis: str = "x",
              panel: MatLike = SIGN_RED, frame: MatLike = STEEL_H, leg: MatLike = STEEL_V) -> None:
    """Sign panel (96 tall) on two 64-unit legs standing on z, ``w`` wide along ``axis``."""
    if axis == "x":
        b.box((x - w / 2, y - 3, z + 64), (x + w / 2, y + 3, z + 160), {"sides": panel, "default": frame})
        for dx in (-w / 2 + 16, w / 2 - 24):
            b.box((x + dx, y - 4, z), (x + dx + 8, y + 4, z + 64), leg)
    else:
        b.box((x - 3, y - w / 2, z + 64), (x + 3, y + w / 2, z + 160), {"sides": panel, "default": frame})
        for dy in (-w / 2 + 16, w / 2 - 24):
            b.box((x - 4, y + dy, z), (x + 4, y + dy + 8, z + 64), leg)


def console(b: MapBuilder, x0, y0, x1, y1, z: float = 0, h: float = 72, panel: MatLike = CONTROL_PANEL,
            top: MatLike = STEEL_H) -> None:
    """A bank of control cabinets: panel texture on every side, a steel top (solid cover)."""
    b.box((x0, y0, z), (x1, y1, z + h), {"sides": panel, "top": top, "default": CAULK_M})


def parapet(b: MapBuilder, x0, y0, x1, y1, z: float, h: float = 24, t: float = 8,
            m: MatLike = "norway/norcrete1", top: Optional[MatLike] = None) -> None:
    """Low wall round a flat roof's edge (outer rect x0..x1, y0..y1) standing on z, ``t`` thick."""
    cap = {"top": top, "default": m} if top is not None else m
    b.box((x0, y0, z), (x1, y0 + t, z + h), cap)
    b.box((x0, y1 - t, z), (x1, y1, z + h), cap)
    b.box((x0, y0 + t, z), (x0 + t, y1 - t, z + h), cap)
    b.box((x1 - t, y0 + t, z), (x1, y1 - t, z + h), cap)


def catwalk(b: MapBuilder, x0, y0, x1, y1, z: float, legs_to: float, outer: str = "east",
            deck: MatLike = GRATE, beam: MatLike = STEEL_H, leg: MatLike = STEEL_V) -> None:
    """Steel-grate walkway running north-south (x0..x1 wide) with its deck top at z, hanging off
    a wall on the side opposite ``outer``: cross beams every 256, a leg on the ``outer`` edge
    down to ``legs_to`` and a brace back to the wall, a railing on the ``outer`` edge."""
    b.box((x0, y0, z - 8), (x1, y1, z), {"top": deck, "bottom": deck, "default": beam})
    for y in range(int(y0) + 64, int(y1), 256):
        if outer == "east":
            b.box((x0 + 8, y - 6, z - 24), (x1, y + 6, z - 8), beam)
            b.box((x1 - 24, y - 8, legs_to), (x1 - 8, y + 8, z - 24), leg)
            b.hull([(x1 - 24, y - 4, z - 24), (x1 - 8, y - 4, z - 24), (x1 - 24, y + 4, z - 24), (x1 - 8, y + 4, z - 24),
                    (x0 + 16, y - 4, z - 216), (x0, y - 4, z - 216), (x0 + 16, y + 4, z - 216), (x0, y + 4, z - 216)], leg)
        else:
            b.box((x0, y - 6, z - 24), (x1 - 8, y + 6, z - 8), beam)
            b.box((x0 + 8, y - 8, legs_to), (x0 + 24, y + 8, z - 24), leg)
            b.hull([(x0 + 8, y - 4, z - 24), (x0 + 24, y - 4, z - 24), (x0 + 8, y + 4, z - 24), (x0 + 24, y + 4, z - 24),
                    (x1 - 16, y - 4, z - 216), (x1, y - 4, z - 216), (x1 - 16, y + 4, z - 216), (x1, y + 4, z - 216)], leg)
    railing(b, (x1 - 6) if outer == "east" else (x0 + 6), y0, (x1 - 6) if outer == "east" else (x0 + 6), y1, z)


def power_line(b: MapBuilder, posts: Sequence[tuple[float, float]], z: float = 0, h: float = 320,
               pole: MatLike = WOOD_POLE, wire: MatLike = STEEL_H, sag: float = 48, spread: float = 40) -> None:
    """Wooden poles with a crossarm at each point and two sagging wires (two straight segments
    per span) between consecutive poles."""
    for x, y in posts:
        b.box((x - 6, y - 6, z), (x + 6, y + 6, z + h), {"sides": pole, "default": CAULK_M})
        b.box((x - 48, y - 4, z + h - 32), (x + 48, y + 4, z + h - 20), pole)
    for (xa, ya), (xb, yb) in zip(posts, posts[1:]):
        for off in (-spread, spread):
            za, zb = z + h - 32, z + h - 32
            mid = ((xa + xb) / 2 + off, (ya + yb) / 2, za - sag)
            for (p0, p1) in (((xa + off, ya, za), mid), (mid, (xb + off, yb, zb))):
                b.hull([(p0[0] - 1, p0[1], p0[2]), (p0[0] + 1, p0[1], p0[2]), (p0[0], p0[1], p0[2] + 2),
                        (p1[0] - 1, p1[1], p1[2]), (p1[0] + 1, p1[1], p1[2]), (p1[0], p1[1], p1[2] + 2)], wire)


def gondola(b: MapBuilder, x: float, y: float, z0: float, cable: tuple[float, float, float, float],
            hanger_top: float, body: MatLike = SIGN_RED, trim: MatLike = STEEL_H, glass: MatLike = GLASS,
            segments: int = 4) -> None:
    """Cable-car cabin (128 long on x, 88 wide, 112 tall, windows on both long sides) with its
    floor at z0, hung from ``hanger_top``, and two cables 48 apart running along x from
    (xa, za) to (xb, zb) = ``cable`` in ``segments`` pieces (each under the 1,536-unit brush
    limit). Not enterable: add a clip box."""
    gx, gy = x, y
    sides = {"sides": body, "top": trim, "bottom": trim}
    b.box((gx - 64, gy - 44, z0), (gx + 64, gy + 44, z0 + 24), sides)                 # skirt
    b.box((gx - 64, gy - 44, z0 + 72), (gx + 64, gy + 44, z0 + 112), sides)           # roof band
    for sx in (-64, 60):
        b.box((gx + sx, gy - 44, z0 + 24), (gx + sx + 4, gy + 44, z0 + 72), body)
    b.box((gx - 60, gy - 44, z0 + 24), (gx + 60, gy - 40, z0 + 72), glass)
    b.box((gx - 60, gy + 40, z0 + 24), (gx + 60, gy + 44, z0 + 72), glass)
    b.box((gx - 4, gy - 4, z0 + 112), (gx + 4, gy + 4, hanger_top), STEEL_V)          # hanger
    xa, za, xb, zb = cable
    for dy in (-24, 24):
        cy = gy + dy
        for i in range(segments):
            x0, x1 = xa + (xb - xa) * i / segments, xa + (xb - xa) * (i + 1) / segments
            c0, c1 = za + (zb - za) * i / segments, za + (zb - za) * (i + 1) / segments
            b.hull([(x0, cy - 2, c0), (x0, cy + 2, c0), (x0, cy - 2, c0 + 4), (x0, cy + 2, c0 + 4),
                    (x1, cy - 2, c1), (x1, cy + 2, c1), (x1, cy - 2, c1 + 4), (x1, cy + 2, c1 + 4)], trim)


def antenna_mast(b: MapBuilder, x: float, y: float, base: float, top: float, paint: MatLike = SIGN_RED,
                 steel: MatLike = STEEL_V, ring: MatLike = STEEL_H, mesh: MatLike = MESH) -> None:
    """Tapered steel mast from ``base`` to ``top`` with brace rings every 96, a mesh antenna panel
    (240 x 176, facing north/south) and two coil cylinders on top, all wrapped in playerclip."""
    b.hull([(x - 24, y - 24, base), (x + 24, y - 24, base), (x - 24, y + 24, base), (x + 24, y + 24, base),
            (x - 10, y - 10, top), (x + 10, y - 10, top), (x - 10, y + 10, top), (x + 10, y + 10, top)],
           {"sides": paint, "default": steel})
    for z in range(int(base) + 128, int(top), 96):
        b.box((x - 26, y - 26, z), (x + 26, y + 26, z + 8), ring)
    b.box((x - 120, y - 4, top), (x + 120, y + 4, top + 176), {"north": mesh, "south": mesh, "default": ring})
    for dx in (-60, 60):
        b.prism(polygon(x + dx, y + 12, 20, 8), top + 40, top + 136, ring)
    clip_box(b, x - 128, y - 32, base, x + 128, y + 32, top + 200)


# ---------------------------------------------------------------------------
# Street walls, arches, cloth and roofscapes (first built for mk_medina; generic). ``side`` is
# the compass side of the street air box where the wall is; ``facing`` is the direction a
# wall face looks toward; ``plane`` is the wall face's coordinate.

NODRAW = Material("common/nodraw")
CLOTH = Material("algiers/desertcloth")      # lightmapped (alpha-tested tentdsrt stayed black underneath)
BEAM = Material("general_structure/beam_wood1")
_OUT = {"north": -1, "south": 1, "east": -1, "west": 1}     # street side of a wall, along its normal axis
_FACING = {"north": "south", "south": "north", "east": "west", "west": "east"}


def wall_box(b: MapBuilder, side: str, plane: float, u0, u1, z0, z1, d0, d1, m) -> None:
    """Box against the wall on ``side`` of a street, ``d0..d1`` out from the wall plane."""
    s = _OUT[side]
    a, c = sorted((plane + s * d0, plane + s * d1))
    if side in ("north", "south"):
        b.box((u0, a, z0), (u1, c, z1), m)
    else:
        b.box((a, u0, z0), (c, u1, z1), m)


def behind_wall(side: str, plane: float, u: float, z: float, d: float = 40) -> tuple[float, float, float]:
    """A point ``d`` behind the wall on ``side`` (inside the building)."""
    if side == "north":
        return (u, plane + d, z)
    if side == "south":
        return (u, plane - d, z)
    if side == "east":
        return (plane + d, u, z)
    return (plane - d, u, z)


def solid_spans(cv: Carver, a: Air, side: str, z: float, lo: float, hi: float, step: float = 16):
    """Intervals along a wall of air ``a`` (at height z) that are really wall, not openings."""
    (x0, y0, _), (x1, y1, _) = a.bounds
    spans, cur = [], None
    u = lo
    while u <= hi:
        if side == "north":
            p = (u, y1 + 8, z)
        elif side == "south":
            p = (u, y0 - 8, z)
        elif side == "east":
            p = (x1 + 8, u, z)
        else:
            p = (x0 - 8, u, z)
        wall = not cv.contains(p)
        if wall and cur is None:
            cur = u
        elif not wall and cur is not None:
            spans.append((cur, u - step))
            cur = None
        u += step
    if cur is not None:
        spans.append((cur, hi))
    return spans


def decal(b: MapBuilder, facing: str, plane: float, u0, u1, z0, z1, image: str, px, proud: float = 1.0,
          hidden: MatLike = NODRAW) -> None:
    """Blended/alpha image (window, grille, sign) on a thin non-solid slab ``proud`` in front of
    a wall, fitted to u0..u1 x z0..z1 (``px`` = the image's pixel size)."""
    n = {"north": (0, 1, 0), "south": (0, -1, 0), "east": (1, 0, 0), "west": (-1, 0, 0)}[facing]
    img = fit(image, n, u0, u1, z1, scale=(u1 - u0) / px[0], scale_t=(z1 - z0) / px[1])
    img = img(parms=("nonsolid",))
    other = mat(hidden)(parms=("nonsolid",))
    spec = {facing: img, "default": other}
    if facing == "north":
        b.box((u0, plane, z0), (u1, plane + proud, z1), spec, grid=0)
    elif facing == "south":
        b.box((u0, plane - proud, z0), (u1, plane, z1), spec, grid=0)
    elif facing == "east":
        b.box((plane, u0, z0), (plane + proud, u1, z1), spec, grid=0)
    else:
        b.box((plane - proud, u0, z0), (plane, u1, z1), spec, grid=0)


def image_panel(b: MapBuilder, facing: str, plane: float, u0, u1, z0, z1, image: str, px, edge: MatLike,
                proud: float = 2) -> None:
    """Solid image panel (a doorway picture) standing ``proud`` in front of a wall."""
    n = {"north": (0, 1, 0), "south": (0, -1, 0), "east": (1, 0, 0), "west": (-1, 0, 0)}[facing]
    img = fit(image, n, u0, u1, z1, scale=(u1 - u0) / px[0], scale_t=(z1 - z0) / px[1])
    spec = {facing: img, "default": edge}
    if facing == "north":
        b.box((u0, plane, z0), (u1, plane + proud, z1), spec, grid=0)
    elif facing == "south":
        b.box((u0, plane - proud, z0), (u1, plane, z1), spec, grid=0)
    elif facing == "east":
        b.box((plane, u0, z0), (plane + proud, u1, z1), spec, grid=0)
    else:
        b.box((plane - proud, u0, z0), (plane, u1, z1), spec, grid=0)


def arch_fill(b: MapBuilder, axis: str, t0, t1, u0, u1, zs, ztop, m: MatLike, k: float = 0.72, segs: int = 5,
              cap: bool = True) -> int:
    """Masonry between a pointed-arch intrados (span u0..u1 springing at zs) and ztop.

    ``axis`` is the axis the span runs along ("x" or "y"); t0..t1 is the wall thickness on the
    other axis. k = radius / span (0.5 = round arch). The curved voussoir pieces stop just above
    the apex (``z_mid``, returned); one plain block (``cap``) fills z_mid..ztop. Keeping the many
    curve vertices off the ceiling plane avoids > 64-vertex ceiling faces after T-junction
    fixing (mk_medina's first build: 83 vertices on an arcade ceiling)."""
    span = u1 - u0
    r = k * span
    cx = u0 + r
    th_m = math.acos((span / 2 - r) / r)
    left = []
    for i in range(segs + 1):
        th = math.pi + (th_m - math.pi) * i / segs
        left.append((cx + r * math.cos(th), zs + r * math.sin(th)))
    left[-1] = ((u0 + u1) / 2, left[-1][1])
    right = [(u0 + u1 - u, z) for u, z in reversed(left)]
    curve = left + right[1:]
    curve = [(round(u), round(z)) for u, z in curve]
    apex = max(z for _, z in curve)
    z_mid = int(math.ceil((apex + 6) / 4.0) * 4)
    assert z_mid <= ztop, "arch apex above ztop"

    def P(u, t, z):
        return (u, t, z) if axis == "x" else (t, u, z)

    seg_m = {"up": CAULK_M, "default": m}
    for (ua, za), (ub, zb) in zip(curve, curve[1:]):
        if ub - ua < 1:
            continue
        pts = []
        for t in (t0, t1):
            pts += [P(ua, t, za), P(ub, t, zb), P(ub, t, z_mid), P(ua, t, z_mid)]
        b.hull(pts, seg_m)
    if cap and z_mid < ztop:
        lo, hi = P(u0, t0, z_mid), P(u1, t1, ztop)
        b.box(lo, hi, {"down": CAULK_M, "default": m})
    return z_mid


def arcade(b: MapBuilder, axis: str, tc, posts, z0, zs, ztop, wall_m: MatLike, stone: MatLike, column: MatLike,
           k: float = 0.72, depth: float = 32, skip=()) -> None:
    """Pillars at ``posts`` (coordinates along ``axis``) on the line ``tc`` with arches between
    them: octagonal shafts (``column``), plinths and capitals (``stone``), then one lintel up to
    ``ztop`` and a cornice on the open (lower-coordinate) side."""
    h = depth / 2

    def B(ua, ub, ta, tb, za, zb, m):
        if axis == "x":
            b.box((ua, ta, za), (ub, tb, zb), m)
        else:
            b.box((ta, ua, za), (tb, ub, zb), m)

    z_mid = ztop
    for a, c in zip(posts, posts[1:]):
        z_mid = arch_fill(b, axis, tc - h, tc + h, a + h, c - h, zs, ztop, wall_m, k=k, cap=False)
    for u in posts:
        if u in skip:
            continue
        B(u - 18, u + 18, tc - 18, tc + 18, z0, z0 + 14, stone)                  # plinth
        cx, cy = (u, tc) if axis == "x" else (tc, u)
        b.prism(polygon(cx, cy, 13, 8, 22.5), z0 + 14, zs - 10, column)          # shaft
        B(u - 18, u + 18, tc - 18, tc + 18, zs - 10, zs, stone)                  # capital
        B(u - h, u + h, tc - h, tc + h, zs, z_mid, {"up": CAULK_M, "default": wall_m})   # pier
    lo, hi = min(posts) - h, max(posts) + h
    if z_mid < ztop:
        B(lo, hi, tc - h, tc + h, z_mid, ztop, {"down": CAULK_M, "default": wall_m})  # lintel
    B(lo, hi, tc - h - 6, tc - h, ztop - 4, ztop + 16, stone)                   # cornice


def coped_wall(b: MapBuilder, x0, y0, x1, y1, z, h: float = 40, m: MatLike = "algiers/afrik_wall1c",
               cap: MatLike = "algiers/doccrtset_1b") -> None:
    """A low wall box with a coping slab 3 wider on each side (roof edges, terrace walls)."""
    b.box((x0, y0, z), (x1, y1, z + h), m)
    b.box((x0 - 3, y0 - 3, z + h), (x1 + 3, y1 + 3, z + h + 5), cap)


def awning(b: MapBuilder, facing: str, plane: float, u0, u1, z_wall, depth: float = 80, drop: float = 28,
           cloth: MatLike = CLOTH, batten: MatLike = BEAM) -> None:
    """Opaque cloth awning sloping away from a wall, with a wooden batten on its edge. (The
    alpha-tested algiers/tentdsrt stayed black underneath in draft and preview lighting.)"""
    zin, zout = z_wall, z_wall - drop
    pts = []
    if facing in ("north", "south"):
        out = plane + (depth if facing == "north" else -depth)
        for x in (u0, u1):
            pts += [(x, plane, zin), (x, plane, zin + 2), (x, out, zout), (x, out, zout + 2)]
        ya, yb = sorted((out, out + (-4 if facing == "north" else 4)))
        b.box((u0, ya, zout - 4), (u1, yb, zout + 2), batten, grid=0)
    else:
        out = plane + (depth if facing == "east" else -depth)
        for y in (u0, u1):
            pts += [(plane, y, zin), (plane, y, zin + 2), (out, y, zout), (out, y, zout + 2)]
        xa, xb = sorted((out, out + (-4 if facing == "east" else 4)))
        b.box((xa, u0, zout - 4), (xb, u1, zout + 2), batten, grid=0)
    b.hull(pts, mat(cloth))


def canopy(b: MapBuilder, axis: str, a0, a1, c0, c1, z, sag, cloth: MatLike = CLOTH,
           hidden: MatLike = NODRAW) -> None:
    """Sagging cloth across a street: spans a0..a1 along ``axis`` (the street direction), wall to
    wall c0..c1 across it, hung at z with its middle ``sag`` lower (two slabs)."""
    cm = (c0 + c1) / 2
    spec = {"up": mat(cloth), "down": mat(cloth), "default": mat(hidden)}

    def P(a, c, zz):
        return (a, c, zz) if axis == "x" else (c, a, zz)

    for ca, cb, za, zb in ((c0, cm, z, z - sag), (cm, c1, z - sag, z)):
        pts = []
        for a in (a0, a1):
            pts += [P(a, ca, za), P(a, ca, za + 2), P(a, cb, zb), P(a, cb, zb + 2)]
        b.hull(pts, spec)


def masonry_dome(b: MapBuilder, cx, cy, z, r, stone: MatLike, trim: MatLike, rings: int = 4, sides: int = 12) -> None:
    """Drum (48 tall), a dome of hulled rings (0.8 x r high) and a finial (mosques, tombs)."""
    b.prism(polygon(cx, cy, r + 8, sides, 15), z, z + 48, {"up": stone, "default": trim})
    z += 48
    prev_r, prev_z = r, z
    for i in range(1, rings + 1):
        a = math.pi / 2 * i / rings
        rr, zz = r * math.cos(a), z + r * 0.8 * math.sin(a)
        ring0 = [(x, y, prev_z) for x, y in polygon(cx, cy, prev_r, sides, 15)]
        ring1 = [(x, y, round(zz)) for x, y in polygon(cx, cy, rr, sides, 15)] if rr > 8 else [(cx, cy, round(zz))]
        b.hull(ring0 + ring1, trim)
        prev_r, prev_z = rr, round(zz)
    b.prism(polygon(cx, cy, 6, 8, 22.5), prev_z, prev_z + 40, stone)


def mashrabiya(b: MapBuilder, side: str, plane: float, c: float, z: float, wood: MatLike, trim: MatLike,
               beam: MatLike, roof: MatLike, stone: MatLike, grille: str, grille_px=(144, 128)) -> None:
    """Enclosed wooden balcony on an upper storey: plank box with a grille front, corbels below
    and a thin roof slab, centred at ``c`` along the wall on ``side`` of a street, floor at z."""
    facing = _FACING[side]
    wall_box(b, side, plane, c - 56, c + 56, z, z + 100, 0, 28, {"down": trim, "up": beam, "default": wood})
    for u in (c - 48, c + 40):
        wall_box(b, side, plane, u, u + 8, z - 16, z, 0, 22, beam)
    wall_box(b, side, plane, c - 62, c + 62, z + 100, z + 106, 0, 34, {"up": roof, "default": stone})
    decal(b, facing, plane + _OUT[side] * 28, c - 44, c + 44, z + 12, z + 92, grille, grille_px)


def dress_walls(b: MapBuilder, cv: Carver, a: Air, rng, skip, roof_z: float, door_img: tuple, window_img: tuple,
                reveal: MatLike, balcony=None) -> None:
    """Windows, doors and balconies on the walls of a street/plaza air box, bay by bay (224).

    Ground floor: a door niche (``door_img`` = (image, px)) where the wall is thick, a window
    decal (``window_img`` = (image, px)) or blank wall; upper floor windows where the wall is tall, some
    of them ``balcony(b, side, plane, c, z)``. ``skip`` = {side: [(u0, u1)]} spans to leave
    blank (stairs against the wall). ``rng`` drives the choices (deterministic per seed)."""
    (x0, y0, z), (x1, y1, _) = a.bounds
    h = roof_z - z
    for side in ("north", "south", "east", "west"):
        facing = _FACING[side]
        plane = {"north": y1, "south": y0, "east": x1, "west": x0}[side]
        lo, hi = (x0, x1) if side in ("north", "south") else (y0, y1)
        for s0, s1 in solid_spans(cv, a, side, z + 60, lo, hi):
            if s1 - s0 < 160:
                continue
            upper = [(u0, u1) for u0, u1 in solid_spans(cv, a, side, z + 280, s0, s1) if u1 - u0 >= 160]
            n = int((s1 - s0) // 224)
            if n < 1:
                continue
            step = (s1 - s0) / n
            for i in range(n):
                c = round(s0 + step * (i + 0.5))
                r = rng.random()
                behind = behind_wall(side, plane, c, z + 60)
                thick = not cv.contains(behind)
                if any(k0 - 48 <= c <= k1 + 48 for k0, k1 in skip.get(side, ())):
                    r = 1.0
                if r < 0.35 and thick and h >= 256:
                    door(cv, a, side, c, z, 56, 112, door_img[0], door_img[1], reveal, depth=8)
                elif r < 0.7:
                    decal(b, facing, plane, c - 28, c + 28, z + 96, z + 159, window_img[0], window_img[1])
                if h >= 256 and any(u0 + 64 <= c <= u1 - 64 for u0, u1 in upper) and rng.random() < 0.8:
                    if h > 300 and rng.random() < 0.3 and balcony is not None:
                        balcony(b, side, plane, c, z + 272)
                    else:
                        wz = z + 280 if h > 300 else z + 150
                        decal(b, facing, plane, c - 40, c + 40, wz, wz + 90, window_img[0], window_img[1])


def wall_trim(b: MapBuilder, cv: Carver, a: Air, rng, skip, roof_z: float, frieze: str, stone: MatLike,
              beam: MatLike) -> None:
    """Break up tall plain street walls: an ornamental cornice (``frieze``, a 64x64 band) under
    the roof edge, rows of beam ends (vigas) under it on tall walls, and a string course at z 256
    on ground-level walls over 300 tall (hides the texture seam). Pieces stop short of each other
    (no shared faces, no T-junction pile-ups) and skip the ``skip`` spans."""
    (x0, y0, z), (x1, y1, _) = a.bounds
    h = roof_z - z
    if h < 200:
        return
    tall = h > 300
    ch = 24 if tall else 12                                  # cornice height
    for side in ("north", "south", "east", "west"):
        plane = {"north": y1, "south": y0, "east": x1, "west": x0}[side]
        lo, hi = (x0, x1) if side in ("north", "south") else (y0, y1)
        front = _FACING[side]
        fr = Material(frieze, (ch / 64, ch / 64), 0.0, (0.0, roof_z / (ch / 64)))
        for s0, s1 in solid_spans(cv, a, side, roof_z - ch / 2, lo, hi):
            if s1 - s0 < 64:
                continue
            wall_box(b, side, plane, s0, s1, roof_z - ch, roof_z, 0, 6, {front: fr, "default": stone})
            if tall and rng.random() < 0.7:
                for u in range(int(s0) + 40, int(s1) - 32, 64):
                    wall_box(b, side, plane, u - 5, u + 5, roof_z - ch - 40, roof_z - ch - 30, 0, 16, beam)
        if not (tall and z == 0):
            continue
        for span in solid_spans(cv, a, side, 256, lo, hi):
            pieces = [span]
            for k0, k1 in skip.get(side, ()):                # stairs against the wall: no course over them
                pieces = [q for p0, p1 in pieces for q in ((p0, min(p1, k0 - 16)), (max(p0, k1 + 16), p1))]
            for s0, s1 in pieces:
                if s1 - s0 >= 64:
                    wall_box(b, side, plane, s0, s1, 252, 260, 0, 4, stone)


def fountain(b: MapBuilder, cx, cy, z: float, stone: MatLike, base: MatLike = "general_structure/jh_conc512bw",
             water: MatLike = Material("misc_outside/pond", (0.5, 0.5)), light: bool = True) -> None:
    """Octagonal basin (8 convex rim segments), water surface, central pedestal, and a soft light."""
    r_out, r_in, h = 112, 96, 32
    for i in range(8):
        a0, a1 = math.radians(i * 45 + 22.5), math.radians(i * 45 + 67.5)
        poly = [(cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)), (cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)),
                (cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)), (cx + r_in * math.cos(a1), cy + r_in * math.sin(a1))]
        poly = [(round(x), round(y)) for x, y in poly]
        b.prism(poly, z, z + h, stone)
    octo = [(round(cx + r_in * math.cos(math.radians(i * 45 + 22.5))), round(cy + r_in * math.sin(math.radians(i * 45 + 22.5))))
            for i in range(8)]
    b.prism(octo, z, z + 12, mat(base))
    b.prism(octo, z + 12, z + 24, {"top": mat(water), "default": Material("common/waterskip")})
    b.prism([(cx - 24, cy - 24), (cx + 24, cy - 24), (cx + 24, cy + 24), (cx - 24, cy + 24)], z + 12, z + 96, stone)
    b.prism([(cx - 36, cy - 36), (cx + 36, cy - 36), (cx + 36, cy + 36), (cx - 36, cy + 36)], z + 96, z + 108, stone)
    if light:
        b.light((cx, cy, z + 160), 120, (1.0, 0.95, 0.85))


def _clear_of(bb, avoid, what: str) -> None:
    for fp in avoid:
        grown = ((fp[0][0] - 16, fp[0][1] - 16, bb[0][2]), (fp[1][0] + 16, fp[1][1] + 16, bb[0][2] + 2))
        assert not overlaps(bb, grown), f"{what} overlaps open air {fp}"


def roof_storey(b: MapBuilder, cv: Carver, x0, y0, x1, y1, roof_z: float, h: float, m: MatLike, roof: MatLike,
                beam: MatLike, coping, window_img: tuple, avoid=()) -> None:
    """An extra storey on a flat roof (structural, ``cv.solid``): ``m`` walls, ``roof`` top, a
    coping round its edge (``coping(b, x0, y0, x1, y1, z, h=24)``, e.g. ``coped_wall``), beam ends
    (vigas) on the long sides and a window decal each side when tall enough. ``avoid`` = open-air
    footprints (AABBs) it must stay 16 clear of (asserted)."""
    _clear_of(aabb(x0, y0, roof_z - 1, x1, y1, roof_z + h), avoid, f"roof block {x0, y0, x1, y1}")
    cv.solid(x0, y0, roof_z, x1, y1, roof_z + h, {"up": roof, "down": CAULK_M, "sides": m})
    coping(b, x0, y0, x1, y0 + 12, roof_z + h, h=24)
    coping(b, x0, y1 - 12, x1, y1, roof_z + h, h=24)
    coping(b, x0, y0 + 12, x0 + 12, y1 - 12, roof_z + h, h=24)
    coping(b, x1 - 12, y0 + 12, x1, y1 - 12, roof_z + h, h=24)
    for x in range(int(x0) + 32, int(x1) - 16, 64):
        b.box((x - 4, y0 - 14, roof_z + h - 24), (x + 4, y0, roof_z + h - 16), beam)
        b.box((x - 4, y1, roof_z + h - 24), (x + 4, y1 + 14, roof_z + h - 16), beam)
    cx = (x0 + x1) / 2
    z0 = roof_z + h - 100
    if z0 > roof_z + 8:
        decal(b, "south", y0, cx - 36, cx + 36, z0, z0 + 81, window_img[0], window_img[1])
        decal(b, "north", y1, cx - 36, cx + 36, z0, z0 + 81, window_img[0], window_img[1])


def stair_house(b: MapBuilder, cv: Carver, x, y, face: str, roof_z: float, wall: MatLike, roof: MatLike,
                door_img: tuple, edge: MatLike, coping, w: float = 96, h: float = 112, avoid=()) -> None:
    """Small roof hut over a stairwell (structural) with a door picture on ``face`` and a coping."""
    x0, y0, x1, y1 = x - w / 2, y - w / 2, x + w / 2, y + w / 2
    _clear_of(aabb(x0 - 8, y0 - 8, roof_z - 1, x1 + 8, y1 + 8, roof_z + h), avoid, f"stair house {x, y}")
    cv.solid(x0, y0, roof_z, x1, y1, roof_z + h, {"up": roof, "down": CAULK_M, "sides": wall})
    coping(b, x0 - 4, y0 - 4, x1 + 4, y1 + 4, roof_z + h, h=8)
    plane = {"south": y0, "north": y1, "west": x0, "east": x1}[face]
    u = x if face in ("south", "north") else y
    image_panel(b, face, plane, u - 28, u + 28, roof_z, roof_z + 104, door_img[0], door_img[1], edge)


def roof_edges(b: MapBuilder, open_air, roof_z: float, town, top: MatLike, m: MatLike) -> None:
    """Low walls (32) on a flat roofscape along every edge of the open air below (streets,
    plazas) and round the ``town`` rect (x0, y0, x1, y1), broken where open air meets the
    roof and clipped to the town."""
    from .build import subtract
    tx0, ty0, tx1, ty1 = town
    fps = [a.bounds for a in open_air]
    strips = []
    for a in open_air:
        (x0, y0, _), (x1, y1, _) = a.bounds
        strips += [((x0 - 16, y1, roof_z), (x1 + 16, y1 + 16, roof_z + 32)), ((x0 - 16, y0 - 16, roof_z), (x1 + 16, y0, roof_z + 32)),
                   ((x0 - 16, y0, roof_z), (x0, y1, roof_z + 32)), ((x1, y0, roof_z), (x1 + 16, y1, roof_z + 32))]
    strips += [((tx0, ty0, roof_z), (tx0 + 16, ty1, roof_z + 32)), ((tx1 - 16, ty0, roof_z), (tx1, ty1, roof_z + 32)),
               ((tx0 + 16, ty0, roof_z), (tx1 - 16, ty0 + 16, roof_z + 32)), ((tx0 + 16, ty1 - 16, roof_z), (tx1 - 16, ty1, roof_z + 32))]
    for lo, hi in strips:
        pieces = [(lo, hi)]
        for f in fps:
            hole = ((f[0][0], f[0][1], roof_z - 1), (f[1][0], f[1][1], roof_z + 64))
            nxt = []
            for q in pieces:
                nxt += subtract(q, hole)
            pieces = nxt
        for q in pieces:
            lo2 = (max(q[0][0], tx0), max(q[0][1], ty0), q[0][2])
            hi2 = (min(q[1][0], tx1), min(q[1][1], ty1), q[1][2])
            if all(hi2[i] - lo2[i] >= 8 for i in range(3)):
                b.box(lo2, hi2, {"up": top, "default": m})
