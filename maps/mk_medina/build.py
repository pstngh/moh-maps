"""mk_medina: a North African hill town (DM / TDM) under a hot afternoon sun.

Layout (X east, Y north; lower town at z 0, upper town at z 192, flat roofs at 448):

* Souk square (centre) with a dry tiled fountain and palms. An L-shaped arcade of
  pointed arches runs along its north and east sides; the north arcade carries a
  roof terrace (z 192) reached by a stone stair along the square's west wall and by
  a covered passage from the upper town.
* South market street (x -2048..2048) with awnings; both ends open onto the rocky
  hillside that rings the town. A covered gate joins it to the square.
* West quarter: a narrow stepped alley climbing to the upper town, a small palm
  plaza with a well, a house interior and dog-leg alleys.
* East quarter: a street with a stair to the upper town, a side plaza, a second
  stepped alley and a cafe interior that cuts the corner to the market street.
* Upper town: a long street broken by a covered bridge (sabat), and a mosque court
  with a riwaq arcade and a minaret. Its ends also open onto the hillside.
* Terrain hills rise on all sides behind the houses (playerclip keeps players near
  the town).
"""

from __future__ import annotations

import math
import random

from mohkit import kit
from mohkit.build import Carver, MapBuilder, Material as M, aabb, overlaps
from mohkit.game import Shot

META = {"name": "mk_medina", "title": "Medina", "mode": "dm", "ambience": "mohdm7",
        # MOHlight 1.48 access-violates at 0x00433F3A with several threads on this map (twice, in
        # different phases) and Wine then parks it in winedbg; a trailing -threads 1 wins.
        "compile": {"light_args": ["-threads", "1"]}}

# --------------------------------------------------------------------------- levels
UP = 192            # upper-town ground
ROOF = 448          # flat roofs (floor of the sky volume)
SKYTOP = 1088
TX0, TX1, TY0, TY1 = -2048, 2048, -1536, 1536      # town footprint
RING = 1024                                          # hillside ring width
SKY = "sky/mohday2"

# --------------------------------------------------------------------------- materials
CAULK = M("common/caulk")
NODRAW = M("common/nodraw")
SKYM = M(SKY)
PCLIP = M("common/playerclip")

def sh(name, t):
    """Material whose texture repeats vertically every 256 with its top on z = t (mod 256)."""
    return M(name, shift=(0, t % 256))

WA = [(0, M("algiers/afrik_wall1b")), (256, M("algiers/afrik_wall1a"))]             # whitewash, grimy base
WB = [(0, M("algiers/algierwall_set5")), (256, sh("algiers/algierwall_set5wtrim", ROOF))]  # blue dado
WC = [(0, M("algiers/walarzset_1trmpc")), (256, M("algiers/walarzset_1flt"))]        # pink Arzew plaster
WD = [(0, M("algiers/algierwall1drk_1flat")), (256, sh("algiers/algierwall1drk_1wthrd", ROOF))]  # ochre
WE = M("algiers/afrikwall7_set1base")                                                # clean sand plaster
WF = [(0, M("algiers/afrik_wall2des1")), (256, M("algiers/afrik_wall1a"))]           # brown base course
# upper town: walls start at z 192, one 256 repeat to the roof
UA = sh("algiers/afrik_wall1b", UP)
UB = sh("algiers/algierwall_set5", UP)
UC = sh("algiers/walarzset_1trmpc", UP)
UD = sh("algiers/algierwall1drk_blumozwd", ROOF)
UE = sh("algiers/algierwall1drk_1wthrd", ROOF)
BACK = M("algiers/afrik_wall1a")          # building backs seen from the hillside
INT = M("algiers/interiorwall_afrika1trim")

SQUARE = M("algiers/stset_2sand")
STREET = M("algiers/stset_2base")
ALLEY = M("algiers/grndset_1a")
FLAGS = M("algiers/fort_floor_outsidesml")
TILE = M("algiers/afriktile1")
CHECK = M("algiers/afrika_floor_set1")
IFLOOR = M("algiers/whsflrset1_1b")
ROOFM = M("algiers/fort_floor_outside")
PLANK = M("general_structure/plank_flat")
CEIL = M("algiers/algier_ceiling")
BEAM = M("general_structure/beam_wood1")
STONE = M("algiers/doccrtset_1b")
COLM = M("algiers/column_2")
TRIM = M("algiers/afrik_wall1c")
RISER = M("algiers/afrik_wall1a")
CLOTH = "algiers/tentdsrt"
DOOR = "algiers/afrikadoorwrk"
WINDOW = "algiers/afrika_windecal"
DOORWAY = "algiers/afrikwall7_set1doorway"
GRILLE = "algiers/window_decor_set1"
HILL = "algiers/grndset_2af"

LAMP = (1.0, 0.8, 0.55)


# --------------------------------------------------------------------------- helpers
def octagon(cx, cy, r, n=8, phase=22.5):
    return [(round(cx + r * math.cos(math.radians(phase + 360 * i / n))),
             round(cy + r * math.sin(math.radians(phase + 360 * i / n)))) for i in range(n)]


def arch_fill(b, axis, t0, t1, u0, u1, zs, ztop, m, k=0.72, segs=5, cap=True):
    """Masonry between a pointed-arch intrados (span u0..u1 springing at zs) and ztop.

    ``axis`` is the axis the span runs along ("x" or "y"); t0..t1 is the wall thickness
    on the other axis. k = radius / span (0.5 = round arch). The curved voussoir pieces stop
    just above the apex (``z_mid``, returned); one plain block (``cap``) fills z_mid..ztop.
    Keeping the many curve vertices off the ceiling plane avoids > 64-vertex ceiling faces
    after T-junction fixing (seen on the first build: 83 vertices on an arcade ceiling)."""
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

    seg_m = {"up": CAULK, "default": m}
    for (ua, za), (ub, zb) in zip(curve, curve[1:]):
        if ub - ua < 1:
            continue
        pts = []
        for t in (t0, t1):
            pts += [P(ua, t, za), P(ub, t, zb), P(ub, t, z_mid), P(ua, t, z_mid)]
        b.hull(pts, seg_m)
    if cap and z_mid < ztop:
        lo, hi = P(u0, t0, z_mid), P(u1, t1, ztop)
        b.box(lo, hi, {"down": CAULK, "default": m})
    return z_mid


def arcade(b, axis, tc, posts, z0, zs, ztop, wall_m, k=0.72, depth=32, skip=()):
    """Pillars at ``posts`` (coordinates along ``axis``) on the line ``tc`` with arches
    between them: octagonal shafts, plinths and capitals, then one lintel up to ``ztop``."""
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
        B(u - 18, u + 18, tc - 18, tc + 18, z0, z0 + 14, STONE)                  # plinth
        cx, cy = (u, tc) if axis == "x" else (tc, u)
        b.prism(octagon(cx, cy, 13), z0 + 14, zs - 10, COLM)                     # shaft
        B(u - 18, u + 18, tc - 18, tc + 18, zs - 10, zs, STONE)                  # capital
        B(u - h, u + h, tc - h, tc + h, zs, z_mid, {"up": CAULK, "default": wall_m})   # pier
    lo, hi = min(posts) - h, max(posts) + h
    if z_mid < ztop:
        B(lo, hi, tc - h, tc + h, z_mid, ztop, {"down": CAULK, "default": wall_m})  # lintel
    # cornice on the open (front) side: the square side is the lower coordinate
    B(lo, hi, tc - h - 6, tc - h, ztop - 4, ztop + 16, STONE)


def parapet(b, x0, y0, x1, y1, z, h=40, m=TRIM, cap=STONE):
    b.box((x0, y0, z), (x1, y1, z + h), m)
    b.box((x0 - 3, y0 - 3, z + h), (x1 + 3, y1 + 3, z + h + 5), cap)


def decal(b, facing, plane, u0, u1, z0, z1, image, px, proud=1.0):
    """Blended/alpha image on a thin non-solid slab in front of a wall. ``facing`` is the
    compass direction the wall face looks toward; ``plane`` its coordinate."""
    n = {"north": (0, 1, 0), "south": (0, -1, 0), "east": (1, 0, 0), "west": (-1, 0, 0)}[facing]
    img = kit.fit(image, n, u0, u1, z1, scale=(u1 - u0) / px[0], scale_t=(z1 - z0) / px[1])
    img = img(parms=("nonsolid",))
    other = NODRAW(parms=("nonsolid",))
    spec = {facing: img, "default": other}
    if facing == "north":
        b.box((u0, plane, z0), (u1, plane + proud, z1), spec, grid=0)
    elif facing == "south":
        b.box((u0, plane - proud, z0), (u1, plane, z1), spec, grid=0)
    elif facing == "east":
        b.box((plane, u0, z0), (plane + proud, u1, z1), spec, grid=0)
    else:
        b.box((plane - proud, u0, z0), (plane, u1, z1), spec, grid=0)


def panel(b, facing, plane, u0, u1, z0, z1, image, px, edge, proud=2):
    """Solid image panel standing ``proud`` in front of a wall (doorway pictures)."""
    n = {"north": (0, 1, 0), "south": (0, -1, 0), "east": (1, 0, 0), "west": (-1, 0, 0)}[facing]
    img = kit.fit(image, n, u0, u1, z1, scale=(u1 - u0) / px[0], scale_t=(z1 - z0) / px[1])
    spec = {facing: img, "default": edge}
    if facing == "north":
        b.box((u0, plane, z0), (u1, plane + proud, z1), spec, grid=0)
    elif facing == "south":
        b.box((u0, plane - proud, z0), (u1, plane, z1), spec, grid=0)
    elif facing == "east":
        b.box((plane, u0, z0), (plane + proud, u1, z1), spec, grid=0)
    else:
        b.box((plane - proud, u0, z0), (plane, u1, z1), spec, grid=0)


def awning(b, facing, plane, u0, u1, z_wall, depth=80, drop=28):
    """Opaque cloth awning sloping away from a wall, with a wooden batten on its edge.

    (The first version used the alpha-tested algiers/tentdsrt; its underside stayed black in
    both draft and preview lighting, so the lightmapped algiers/desertcloth is used.)"""
    cloth = M("algiers/desertcloth")
    zin, zout = z_wall, z_wall - drop
    pts = []
    if facing in ("north", "south"):
        out = plane + (depth if facing == "north" else -depth)
        for x in (u0, u1):
            pts += [(x, plane, zin), (x, plane, zin + 2), (x, out, zout), (x, out, zout + 2)]
        ya, yb = sorted((out, out + (-4 if facing == "north" else 4)))
        b.box((u0, ya, zout - 4), (u1, yb, zout + 2), BEAM, grid=0)
    else:
        out = plane + (depth if facing == "east" else -depth)
        for y in (u0, u1):
            pts += [(plane, y, zin), (plane, y, zin + 2), (out, y, zout), (out, y, zout + 2)]
        xa, xb = sorted((out, out + (-4 if facing == "east" else 4)))
        b.box((xa, u0, zout - 4), (xb, u1, zout + 2), BEAM, grid=0)
    b.hull(pts, cloth)


def canopy(b, axis, a0, a1, c0, c1, z, sag):
    """Sagging cloth stretched across a street: spans a0..a1 along ``axis`` (the street
    direction), wall to wall c0..c1 across it, hung at z with its middle ``sag`` lower."""
    cm = (c0 + c1) / 2
    cloth = {"up": M("algiers/desertcloth"), "down": M("algiers/desertcloth"), "default": NODRAW}

    def P(a, c, zz):
        return (a, c, zz) if axis == "x" else (c, a, zz)

    for ca, cb, za, zb in ((c0, cm, z, z - sag), (cm, c1, z - sag, z)):
        pts = []
        for a in (a0, a1):
            pts += [P(a, ca, za), P(a, ca, za + 2), P(a, cb, zb), P(a, cb, zb + 2)]
        b.hull(pts, cloth)


# --------------------------------------------------------------------------- hills
def dist_out(x, y):
    dx = max(TX0 - x, 0, x - TX1)
    dy = max(TY0 - y, 0, y - TY1)
    return (dx ** 4 + dy ** 4) ** 0.25          # rounded-square contours: even slopes in the corners


def ground_base(y):
    t = min(1.0, max(0.0, (y + 600) / 1160))
    return UP * t * t * (3 - 2 * t)


def hill(x, y):
    """Terrain height above z -64."""
    d = dist_out(x, y)
    base = ground_base(y) + 64
    if d < 176:
        return base
    f = min(1.0, (d - 176) / (RING - 176))
    n = 34 * math.sin(x / 290.0 + 1.3) * math.cos(y / 260.0) + 22 * math.sin((x - y) / 170.0)
    base = base * (1 - f) + (UP / 2 + 64) * f   # the ridge ignores the town's two levels
    return base + 580 * f ** 1.08 + n * min(1.0, (d - 176) / 320)


# --------------------------------------------------------------------------- the map
def build():
    b = MapBuilder("Medina", suncolor="160 140 104", sundirection="-55 225 0", sundiffuse="1.25",
                   sundiffusecolor="84 92 116", ambientlight="16 15 15", farplane="9000",
                   farplane_color="0.74 0.68 0.58", farplane_cull="0")
    cv = Carver(16, sky_shader=SKY)
    b.carve(cv)
    rng = random.Random(7)

    def room(x0, y0, z0, x1, y1, z1, floor, walls, ceiling=CAULK, sky=False, name=""):
        return cv.room(x0, y0, z0, x1, y1, z1, floor=floor, walls=walls, ceiling=ceiling, sky=sky, name=name)

    # ---------------------------------------------------------------- sky + hillside ring
    room(TX0, TY0, ROOF, TX1, TY1, SKYTOP, ROOFM, CAULK, sky=True, name="skyvol")
    room(TX0 - RING, TY0 - RING, -64, TX0, TY1 + RING, SKYTOP, CAULK, {"east": BACK, "default": SKYM}, sky=True, name="ring_w")
    room(TX1, TY0 - RING, -64, TX1 + RING, TY1 + RING, SKYTOP, CAULK, {"west": BACK, "default": SKYM}, sky=True, name="ring_e")
    room(TX0, TY0 - RING, -64, TX1, TY0, SKYTOP, CAULK, {"north": BACK, "default": SKYM}, sky=True, name="ring_s")
    room(TX0, TY1, -64, TX1, TY1 + RING, SKYTOP, CAULK, {"south": BACK, "default": SKYM}, sky=True, name="ring_n")

    # ---------------------------------------------------------------- lower town
    sq = room(-640, -832, 0, 640, 64, ROOF, SQUARE, {"west": WA, "south": WC, "default": WA}, name="square")
    arc_n = room(-640, 64, 0, 640, 256, 176, FLAGS, WE, PLANK, name="arc_n")
    arc_ne = room(640, 64, 0, 832, 256, 176, FLAGS, WE, PLANK, name="arc_ne")
    arc_e = room(640, -832, 0, 832, 64, 176, FLAGS, WE, PLANK, name="arc_e")
    terr = room(-640, 64, UP, 640, 256, ROOF, FLAGS, {"north": WD, "default": WA}, name="terrace")
    gate_s = room(-96, -1088, 0, 96, -832, 224, STREET, WF, CEIL, name="gate_s")
    st_s_w = room(TX0, -1344, 0, -640, -1088, ROOF, STREET, {"north": WB, "south": WA, "default": WA}, name="st_s_w")
    st_s_m = room(-640, -1344, 0, 640, -1088, ROOF, STREET, {"north": WF, "south": WD, "default": WA}, name="st_s_m")
    st_s_e = room(640, -1344, 0, TX1, -1088, ROOF, STREET, {"north": WC, "south": WB, "default": WA}, name="st_s_e")

    # west quarter
    al_w = room(-1216, -1088, 0, -1088, 640, ROOF, ALLEY, {"west": WA, "east": WD}, name="al_w")
    al_w1 = room(-1088, -448, 0, -640, -352, ROOF, ALLEY, {"north": WB, "south": WC, "default": WA}, name="al_w1")
    pl_w = room(-1856, -704, 0, -1344, -128, ROOF, SQUARE, {"north": WF, "west": WC, "south": WA, "east": WB}, name="pl_w")
    al_w2 = room(-1344, -352, 0, -1216, -256, ROOF, ALLEY, WA, name="al_w2")
    al_w3 = room(-1664, -1088, 0, -1536, -704, ROOF, ALLEY, {"west": WD, "east": WA}, name="al_w3")
    house_w = room(-1856, -112, 0, -1232, 240, 192, IFLOOR, INT, PLANK, name="house_w")
    room(-1680, -128, 0, -1584, -112, 128, IFLOOR, TRIM, BEAM, name="house_w_door_s")
    room(-1232, 96, 0, -1216, 192, 128, IFLOOR, TRIM, BEAM, name="house_w_door_e")
    for x0 in (-1824, -1520):
        room(x0, -128, 64, x0 + 64, -112, 136, TRIM, TRIM, TRIM, name="house_w_window")

    # east quarter
    al_e1 = room(832, -352, 0, 1088, -256, ROOF, ALLEY, {"north": WD, "south": WA}, name="al_e1")
    st_e = room(1088, -1088, 0, 1280, 640, ROOF, STREET, {"west": WB, "east": WA}, name="st_e")
    pl_e = room(1280, -512, 0, 1792, -64, ROOF, SQUARE, {"north": WC, "east": WD, "south": WA}, name="pl_e")
    al_e3 = room(1600, -64, 0, 1728, 640, ROOF, ALLEY, {"west": WA, "east": WF}, name="al_e3")
    cafe = room(1296, -1072, 0, 1728, -720, 176, CHECK, INT, CEIL, name="cafe")
    room(1280, -976, 0, 1296, -880, 128, CHECK, TRIM, BEAM, name="cafe_door_w")
    room(1440, -1088, 0, 1536, -1072, 128, CHECK, TRIM, BEAM, name="cafe_door_s")
    for x0 in (1328, 1616):
        room(x0, -1088, 64, x0 + 64, -1072, 136, TRIM, TRIM, TRIM, name="cafe_window")

    # ---------------------------------------------------------------- upper town
    pas = room(-96, 256, UP, 96, 640, 352, FLAGS, UA, CEIL, name="passage")
    st_u_w = room(TX0, 640, UP, 640, 896, ROOF, STREET, {"north": UC, "south": UA, "default": UA}, name="st_u_w")
    sabat = room(640, 640, UP, 896, 896, 384, STREET, UA, PLANK, name="sabat")
    st_u_e = room(896, 640, UP, TX1, 896, ROOF, STREET, {"north": UB, "south": UE, "default": UA}, name="st_u_e")
    mgate = room(-96, 896, UP, 96, 928, 400, FLAGS, UD, CEIL, name="mosque_gate")
    court = room(-448, 928, UP, 448, 1344, ROOF, FLAGS, UD, name="court")
    riwaq = room(-448, 1344, UP, 448, 1504, 368, FLAGS, UA, CEIL, name="riwaq")

    # ---------------------------------------------------------------- terrain hills + clip
    kit.terrain(b, TX0 - RING, TY0 - RING, -64, RING // 512, (TY1 - TY0 + 2 * RING) // 512, hill, HILL)
    kit.terrain(b, TX1, TY0 - RING, -64, RING // 512, (TY1 - TY0 + 2 * RING) // 512, hill, HILL)
    kit.terrain(b, TX0, TY0 - RING, -64, (TX1 - TX0) // 512, RING // 512, hill, HILL)
    kit.terrain(b, TX0, TY1, -64, (TX1 - TX0) // 512, RING // 512, hill, HILL)
    c = 176
    for bb in ((TX0 - c - 16, TY0 - c - 16, TX0 - c, TY1 + c + 16), (TX1 + c, TY0 - c - 16, TX1 + c + 16, TY1 + c + 16),
               (TX0 - c, TY0 - c - 16, TX1 + c, TY0 - c), (TX0 - c, TY1 + c, TX1 + c, TY1 + c + 16)):
        b.box((bb[0], bb[1], -64), (bb[2], bb[3], SKYTOP), PCLIP)

    # ---------------------------------------------------------------- square
    # north arcade (pointed) under the terrace, east arcade (round) under the souk hall
    arcade(b, "x", 64, [-512, -368, -224, -80, 64, 208, 352, 496, 640], 0, 92, 176, WE, k=0.6)
    arcade(b, "y", 640, [-832, -704, -576, -448, -320, -192, -64, 64], 0, 104, 176, WE, k=0.5, skip=(64,))
    b.box((-640, 64, 0), (-528, 80, 176), WE)            # closes the bay behind the stair
    kit.beams(b, arc_n, "y", 144, BEAM, size=10, drop=10)
    kit.beams(b, arc_e, "x", 128, BEAM, size=10, drop=10)
    # stone stair along the west wall up to the terrace
    kit.stairs(b, -576, -320, 0, "north", 128, UP, STONE, RISER)
    parapet(b, -512, 64, 640, 80, UP, h=40)
    # terrace furniture
    b.prop("static/south_africa_ceramic_pot_7", -440, 230, UP, 30)
    b.prop("static/south_africa_ceramic_pot_7", 580, 225, UP, 200)
    b.prop("static/wicker_basket_1", 200, 232, UP, 0)
    b.prop("static/basket1", 230, 228, UP, 90)
    # fountain
    b.prism(octagon(0, -384, 144), 0, 28, {"up": STONE, "default": TILE})
    b.prism(octagon(0, -384, 120), 28, 32, TILE)          # dry basin floor (raised)
    b.prism(octagon(0, -384, 26), 32, 96, TILE)
    b.prism(octagon(0, -384, 48), 96, 108, STONE)
    b.prism(octagon(0, -384, 16), 108, 140, TILE)
    # palms and market clutter
    for x, y, yaw in ((-430, -640, 20), (430, -640, 140), (-430, -140, 250), (440, -120, 75)):
        b.prop("static/tree_regularpalm", x, y, 0, yaw)
    b.prop("static/produce_cart", -300, -760, 0, 10)
    b.prop("static/produce_cart", 320, -250, 0, 200)
    b.prop("static/indycrate", 560, -780, 0, 15)
    b.prop("static/indycrate", 560, -736, 0, 40)
    b.prop("static/wicker_basket_2", 520, -780, 0)
    b.prop("static/wicker_basket_3", -560, -780, 0)
    b.prop("static/south_africa_ceramic_pot_7", -600, -600, 0, 0)
    b.prop("static/south_africa_ceramic_pot_7", -596, -560, 0, 120)
    for x in (-450, -150, 150, 450):
        kit.lamp(b, x, 160, 176, 90)
    for y in (-700, -380, -60):
        kit.lamp(b, 736, y, 176, 90)
    # shop doorways on the arcade back walls
    for x in (-440, -150, 136, 424):
        panel(b, "south", 256, x - 72, x + 72, 0, 144, DOORWAY, (256, 256), WE)
    for y in (-760, -472, -184):
        panel(b, "west", 832, y - 64, y + 64, 0, 128, DOORWAY, (256, 256), WE)

    # ---------------------------------------------------------------- gate and passage arches
    for yy in (-1088 + 16, -832 - 16):
        arch_fill(b, "x", yy - 16, yy + 16, -96, 96, 100, 224, M("algiers/afrik_wall1a"), k=0.6)
    for yy in (256 + 16, 640 - 16):
        arch_fill(b, "x", yy - 16, yy + 16, -96, 96, UP + 32, 352, UA, k=0.6)
    for xx in (640 + 16, 896 - 16):
        arch_fill(b, "y", xx - 16, xx + 16, 640, 896, UP + 48, 384, UA, k=0.5)
    arch_fill(b, "x", 896, 928, -96, 96, UP + 80, 400, UD, k=0.6)
    kit.lamp(b, 0, -960, 224, 110)
    kit.lamp(b, 0, 448, 352, 110)
    kit.lamp(b, 768, 768, 384, 120)

    # ---------------------------------------------------------------- mosque
    arcade(b, "x", 1344, [-448, -320, -192, -64, 64, 192, 320, 448], UP, UP + 96, 368, UA)
    b.prism(octagon(0, 1136, 80), UP, UP + 24, {"up": STONE, "default": TILE})
    b.prism(octagon(0, 1136, 20), UP + 24, UP + 64, TILE)
    for x, y, yaw in ((-300, 1040, 0), (300, 1230, 90)):
        b.prop("static/tree_regularpalm", x, y, UP, yaw)
    for x, y in ((-330, 1250), (330, 1030)):
        b.prop("static/tree_squatpalm", x, y, UP, rng.randrange(360))
    for x in (-256, 0, 256):
        panel(b, "south", 1504, x - 64, x + 64, UP, UP + 128, DOORWAY, (256, 256), TRIM)
    b.prop("static/sandbag_large_semicircle", 0, 730, UP, 90)
    b.prop("static/sandbag_small_semicircle", 1300, -1150, 0, 180)
    b.prop("static/sandbag_large_semicircle", -1650, 700, UP, 0)
    kit.lamp(b, -200, 1424, 368, 90)
    kit.lamp(b, 200, 1424, 368, 90)
    # minaret on the roof east of the court
    mx0, my0 = 496, 1344
    mside = {"up": ROOFM, "down": CAULK, "sides": TRIM}
    cv.solid(mx0, my0, ROOF, mx0 + 128, my0 + 128, ROOF + 400, {"up": ROOFM, "down": CAULK, "sides": sh("algiers/afrik_wall1a", 0)})
    b.box((mx0 - 12, my0 - 12, ROOF + 400), (mx0 + 140, my0 + 140, ROOF + 416), STONE)
    b.box((mx0 - 4, my0 - 4, ROOF + 330), (mx0 + 132, my0 + 132, ROOF + 362), TILE)
    b.box((mx0 + 24, my0 + 24, ROOF + 416), (mx0 + 104, my0 + 104, ROOF + 520), mside)
    b.box((mx0 + 16, my0 + 16, ROOF + 520), (mx0 + 112, my0 + 112, ROOF + 530), STONE)
    b.hull([(mx0 + 16, my0 + 16, ROOF + 530), (mx0 + 112, my0 + 16, ROOF + 530), (mx0 + 16, my0 + 112, ROOF + 530),
            (mx0 + 112, my0 + 112, ROOF + 530), (mx0 + 64, my0 + 64, ROOF + 600)], TILE)
    for x0, x1 in ((mx0 + 8, mx0 + 56), (mx0 + 72, mx0 + 120)):
        decal(b, "south", my0, x0, x1, ROOF + 250, ROOF + 316, GRILLE, (144, 128))
        decal(b, "west", mx0, my0 + (x0 - mx0), my0 + (x1 - mx0), ROOF + 250, ROOF + 316, GRILLE, (144, 128))
    # dome over the prayer hall west of the court
    dome(b, -704, 1216, ROOF, 176)

    # ---------------------------------------------------------------- west quarter
    kit.stairs(b, -1152, 256, 0, "north", 128, UP, STONE, RISER)
    b.prop("static/tree_regularpalm", -1760, -600, 0, 60)
    b.prop("static/tree_squatpalm", -1420, -180, 0, 10)
    b.prism(octagon(-1600, -416, 44), 0, 36, {"up": STONE, "default": M("algiers/afrik_wall1brick")})
    b.box((-1640, -420, 36), (-1632, -412, 110), BEAM)
    b.box((-1568, -420, 36), (-1560, -412, 110), BEAM)
    b.box((-1644, -424, 110), (-1556, -408, 118), BEAM)
    b.prop("static/woodbucket", -1580, -380, 36)
    b.prop("static/wagon", -1700, -300, 0, 95)
    b.prop("static/wicker_basket_2", -1400, -660, 0)
    # house interior
    for x in (-1600, -1408):
        kit.column(b, x, 64, 0, 192, TRIM, size=24, base=STONE)
    kit.beams(b, house_w, "y", 128, BEAM, size=12, drop=12)
    kit.baseboard(b, house_w, STONE, gaps=[("south", -1680, -1584), ("east", 96, 192)])
    kit.lamp(b, -1700, 64, 192, 180)
    kit.lamp(b, -1500, 64, 192, 180)
    b.prop("static/round_table", -1700, 150, 0)
    b.prop("furniture/woodchair", -1740, 150, 0, 0)
    b.prop("static/bigbed", -1800, -40, 0, 0)
    b.prop("static/cabinet_dark", -1260, -60, 0, 180)
    b.prop("static/indycrate", -1300, 200, 0, 10)

    # ---------------------------------------------------------------- east quarter
    kit.stairs(b, 1184, 256, 0, "north", 192, UP, STONE, RISER)
    kit.stairs(b, 1664, 256, 0, "north", 128, UP, STONE, RISER)
    b.prop("static/tree_regularpalm", 1650, -400, 0, 200)
    b.prop("static/tree_regularpalm", 1340, -130, 0, 10)
    b.prop("static/vehicle_car_rusted", 1560, -200, 0, 30)
    b.prop("static/produce_cart", 1740, -150, 0, 270)
    # cafe
    for x, y in ((1420, -900), (1600, -900)):
        kit.lamp(b, x, y, 176, 120)
    kit.baseboard(b, cafe, STONE, gaps=[("west", -976, -880), ("south", 1440, 1536)])
    for x, y in ((1380, -800), (1520, -800), (1660, -960)):
        b.prop("static/round_table", x, y, 0)
        b.prop("furniture/woodchair", x - 30, y, 0, 0)
        b.prop("furniture/woodchair", x + 30, y, 0, 180)
    b.prop("static/bshelf-tall-thin", 1710, -760, 0, 180)

    # ---------------------------------------------------------------- streets: clutter and cover
    b.prop("static/vehicle_dtruck_rusted", -300, -1220, 0, 5)
    b.prop("static/wagon", 900, -1180, 0, 88)
    b.prop("static/produce_cart", -1500, -1300, 0, 180)
    b.prop("static/indycrate", 1700, -1300, 0, 0)
    b.prop("static/indycrate", 1700, -1250, 0, 20)
    b.prop("static/indycrate", 1700, -1275, 47, 45)
    b.prop("static/vehicle_car_burnt", -600, 820, UP, 8)
    b.prop("static/produce_cart", 100, 860, UP, 180)
    b.prop("static/indycrate", 1500, 700, UP, 0)
    b.prop("static/indycrate", 1540, 700, UP, 30)
    b.prop("static/wicker_basket_1", -1000, -600, 0)
    # awnings along the market street
    for x0, x1 in ((-1900, -1760), (-1500, -1300), (-980, -760), (-500, -200), (240, 560), (800, 1000), (1360, 1720)):
        awning(b, "south", -1088, x0, x1, 150)
    for x0, x1 in ((-1800, -1560), (-1040, -800), (400, 600), (1100, 1300), (1560, 1900)):
        awning(b, "north", -1344, x0, x1, 150)
    for y0, y1 in ((-860, -560), (-20, 200)):
        awning(b, "west", 1280, y0, y1, 150)

    # souk canopies across the market street and the east street
    for x0, x1 in ((-1400, -1240), (-520, -300), (180, 420), (1380, 1560)):
        canopy(b, "x", x0, x1, -1344, -1088, 300, 28)
    for y0, y1 in ((-760, -600), (-300, -140)):
        canopy(b, "y", y0, y1, 1088, 1280, 290, 24)

    # bracket lanterns in the narrow alleys (fixtures, so the shady lanes are not black)
    for x, y, z, wall in ((-1216, -700, 200, "west"), (-1216, 0, 200, "west"), (-860, -352, 200, "north"),
                          (-1536, -900, 200, "east"), (1088, -600, 220, "west"), (1728, 150, 200, "east"),
                          (-1400, 896, UP + 200, "north"), (1500, 640, UP + 200, "south")):
        kit.wall_lantern(b, x, y, z, wall, 150)

    # ---------------------------------------------------------------- hillside dressing
    for x, y, yaw, big in ((-2300, -1500, 30, 1), (-2450, -900, 120, 0), (-2600, 400, 200, 1), (-2350, 900, 10, 0),
                           (2320, -1400, 80, 1), (2500, -700, 250, 0), (2380, 1000, 300, 1), (2650, 300, 40, 0),
                           (-1200, -1900, 160, 1), (300, -2000, 20, 0), (1300, -1850, 90, 1), (-800, 1950, 60, 1),
                           (800, 2000, 140, 0)):
        z = hill(x, y) - 64
        b.prop("static/rock_large" if big else "static/rock_medium", x, y, z - 12, yaw, scale=2.0 if big else 3.0)
    for x, y in ((-2250, -1180), (-2300, 820), (2260, -1250), (2280, 700), (-600, -1760), (900, -1780)):
        b.prop("static/tree_squatpalm", x, y, hill(x, y) - 64, rng.randrange(360))
    for x, y in ((-2500, -1250), (2550, 820), (0, -2100), (-2700, -200), (2700, -300), (-300, 2100)):
        b.prop("static/tree_regularpalm", x, y, hill(x, y) - 70, rng.randrange(360))

    # ---------------------------------------------------------------- roofscape
    open_air = [a for a in cv.air if a.bounds[1][2] == ROOF and a.name not in ("skyvol",)]
    roof_parapets(b, open_air)
    for x0, y0, x1, y1, h, m in ROOF_BLOCKS:
        add_storey(b, cv, open_air, x0, y0, x1, y1, h, m)
    for x, y, face in STAIR_HOUSES:
        stair_house(b, cv, open_air, x, y, face)
    for x, y, r in SMALL_DOMES:
        dome(b, x, y, ROOF, r, rings=3, sides=10)

    # ---------------------------------------------------------------- facades
    rng2 = random.Random(11)
    for a in open_air:
        dress_facades(b, cv, a, rng2, SKIP.get(a.name, {}))
    for y in (-704, -448, -192):          # souk hall windows above the east arcade
        decal(b, "west", 640, y - 40, y + 40, 250, 340, WINDOW, (128, 144))

    # ---------------------------------------------------------------- spawns
    south = [(-1850, -1216, 0), (-1350, -1180, 0), (-560, -1180, 0), (420, -1250, 180), (1400, -1180, 180),
             (1850, -1216, 180), (-1560, -520, 60), (-1480, -360, 300), (-1600, -900, 90), (1400, -960, 0),
             (-150, -700, 90), (250, -720, 90), (0, -1000, 90), (736, -560, 90)]
    north = [(-1850, 768, 0), (-1000, 830, 0), (-300, 760, 0), (320, 770, 180), (1200, 780, 180), (1850, 768, 180),
             (-150, 1180, 0), (150, 1080, 180), (0, 1424, 270), (300, 160, 180), (-1600, 100, 0), (1380, -420, 180),
             (1664, 0, 90), (-1152, 100, 90)]
    for i, (x, y, yaw) in enumerate(south):
        b.spawn((x, y, 1), yaw, kinds=("deathmatch", "allied"))
    for x, y, yaw in north:
        z = UP + 1 if y > 600 or (y > 64 and -640 < x < 640) else 1
        b.spawn((x, y, z), yaw, kinds=("deathmatch", "axis"))
    b.entity("info_player_start", (0, -600, 1), angle="90")
    b.entity("info_player_intermission", (-500, -700, 420), angles="18 40 0")
    return b


def dome(b, cx, cy, z, r, rings=4, sides=12):
    b.prism(octagon(cx, cy, r + 8, sides, 15), z, z + 48, {"up": STONE, "default": TRIM})
    z += 48
    prev_r, prev_z = r, z
    for i in range(1, rings + 1):
        a = math.pi / 2 * i / rings
        rr, zz = r * math.cos(a), z + r * 0.8 * math.sin(a)
        ring0 = [(x, y, prev_z) for x, y in octagon(cx, cy, prev_r, sides, 15)]
        ring1 = [(x, y, round(zz)) for x, y in octagon(cx, cy, rr, sides, 15)] if rr > 8 else [(cx, cy, round(zz))]
        b.hull(ring0 + ring1, TRIM)
        prev_r, prev_z = rr, round(zz)
    b.prism(octagon(cx, cy, 6), prev_z, prev_z + 40, STONE)


# rooftop extra storeys (x0, y0, x1, y1, height above the roof, wall material)
ROOF_BLOCKS = [
    (-1072, -320, -832, -64, 128, sh("algiers/afrik_wall1a", 0)),
    (-2032, -1520, -1728, -1360, 96, sh("algiers/walarzset_1flt", 0)),
    (-400, -1520, -96, -1360, 160, sh("algiers/afrik_wall1a", 0)),
    (880, -816, 1072, -560, 144, sh("algiers/algierwall1b", 0)),
    (1312, 16, 1584, 240, 128, sh("algiers/walarzset_1flt", 0)),
    (-2032, 912, -1600, 1200, 128, sh("algiers/afrik_wall1a", 0)),
    (1024, 912, 1408, 1136, 176, sh("algiers/algierwall1drk_1flat", 0)),
    (1760, 912, 2032, 1300, 96, sh("algiers/afrik_wall1a", 0)),
    (-1072, 272, -848, 624, 112, sh("algiers/algierwall1b", 0)),
    (112, 272, 400, 624, 96, sh("algiers/afrik_wall1a", 0)),
]


# rooftop stair houses (centre x, y, side with the door) and small domes (x, y, radius)
STAIR_HOUSES = [(-900, -800, "south"), (400, -980, "north"), (-1700, 100, "east"), (-1200, 1300, "south"),
                (-400, 450, "south"), (1900, -800, "west")]
SMALL_DOMES = [(-1380, -900, 64), (1600, 1380, 80), (560, -960, 56)]


def stair_house(b, cv, open_air, x, y, face, w=96, h=112):
    x0, y0, x1, y1 = x - w / 2, y - w / 2, x + w / 2, y + w / 2
    bb = aabb(x0 - 8, y0 - 8, ROOF - 1, x1 + 8, y1 + 8, ROOF + h)
    for a in open_air:
        fp = ((a.bounds[0][0] - 16, a.bounds[0][1] - 16, ROOF - 1), (a.bounds[1][0] + 16, a.bounds[1][1] + 16, ROOF + 1))
        assert not overlaps(bb, fp), f"stair house {x, y} overlaps {a.name}"
    cv.solid(x0, y0, ROOF, x1, y1, ROOF + h, {"up": ROOFM, "down": CAULK, "sides": sh("algiers/afrik_wall1a", 0)})
    parapet(b, x0 - 4, y0 - 4, x1 + 4, y1 + 4, ROOF + h, h=8)
    plane = {"south": y0, "north": y1, "west": x0, "east": x1}[face]
    u = x if face in ("south", "north") else y
    panel(b, face, plane, u - 28, u + 28, ROOF, ROOF + 104, DOOR, (128, 256), STONE)


def roof_parapets(b, open_air):
    """Low walls on the roof along every street edge, broken where streets meet."""
    fps = [a.bounds for a in open_air]
    strips = []
    for a in open_air:
        (x0, y0, _), (x1, y1, _) = a.bounds
        strips += [((x0 - 16, y1, ROOF), (x1 + 16, y1 + 16, ROOF + 32)), ((x0 - 16, y0 - 16, ROOF), (x1 + 16, y0, ROOF + 32)),
                   ((x0 - 16, y0, ROOF), (x0, y1, ROOF + 32)), ((x1, y0, ROOF), (x1 + 16, y1, ROOF + 32))]
    # the town's outer roof edge, seen against the hills
    strips += [((TX0, TY0, ROOF), (TX0 + 16, TY1, ROOF + 32)), ((TX1 - 16, TY0, ROOF), (TX1, TY1, ROOF + 32)),
               ((TX0 + 16, TY0, ROOF), (TX1 - 16, TY0 + 16, ROOF + 32)), ((TX0 + 16, TY1 - 16, ROOF), (TX1 - 16, TY1, ROOF + 32))]
    if True:
        for lo, hi in strips:
            pieces = [(lo, hi)]
            for f in fps:
                hole = ((f[0][0], f[0][1], ROOF - 1), (f[1][0], f[1][1], ROOF + 64))
                nxt = []
                for p in pieces:
                    nxt += _sub(p, hole)
                pieces = nxt
            for p in pieces:
                # clip to the town footprint
                l = (max(p[0][0], TX0), max(p[0][1], TY0), p[0][2])
                h = (min(p[1][0], TX1), min(p[1][1], TY1), p[1][2])
                if all(h[i] - l[i] >= 8 for i in range(3)):
                    b.box(l, h, {"up": STONE, "default": TRIM})


def _sub(a, h):
    from mohkit.build import subtract
    return subtract(a, h)


def add_storey(b, cv, open_air, x0, y0, x1, y1, h, m):
    bb = aabb(x0, y0, ROOF - 1, x1, y1, ROOF + h)
    for a in open_air:
        fp = ((a.bounds[0][0] - 16, a.bounds[0][1] - 16, ROOF - 1), (a.bounds[1][0] + 16, a.bounds[1][1] + 16, ROOF + 1))
        assert not overlaps(bb, fp), f"roof block {x0, y0, x1, y1} overlaps {a.name}"
    cv.solid(x0, y0, ROOF, x1, y1, ROOF + h, {"up": ROOFM, "down": CAULK, "sides": m})
    parapet(b, x0, y0, x1, y0 + 12, ROOF + h, h=24)
    parapet(b, x0, y1 - 12, x1, y1, ROOF + h, h=24)
    parapet(b, x0, y0 + 12, x0 + 12, y1 - 12, ROOF + h, h=24)
    parapet(b, x1 - 12, y0 + 12, x1, y1 - 12, ROOF + h, h=24)
    # beam ends (vigas) below the roof line on the long sides
    for x in range(int(x0) + 32, int(x1) - 16, 64):
        b.box((x - 4, y0 - 14, ROOF + h - 24), (x + 4, y0, ROOF + h - 16), BEAM)
        b.box((x - 4, y1, ROOF + h - 24), (x + 4, y1 + 14, ROOF + h - 16), BEAM)
    # a window each side
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    z0 = ROOF + h - 100
    if z0 > ROOF + 8:
        decal(b, "south", y0, cx - 36, cx + 36, z0, z0 + 81, WINDOW, (128, 144))
        decal(b, "north", y1, cx - 36, cx + 36, z0, z0 + 81, WINDOW, (128, 144))


def _solid_spans(cv, a, side, z, lo, hi, step=16):
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


# wall spans (along the wall) where no doors/grilles go: stairs against the wall
SKIP = {"square": {"west": [(-340, 80)]}, "al_w": {"east": [(230, 640)], "west": [(230, 640)]},
        "st_e": {"east": [(230, 640)], "west": [(230, 640)]}, "al_e3": {"east": [(230, 640)], "west": [(230, 640)]}}


def dress_facades(b, cv, a, rng, skip):
    """Windows, doors, grilles and beam ends on the walls of a street/plaza air box."""
    (x0, y0, z), (x1, y1, _) = a.bounds
    h = ROOF - z
    for side in ("north", "south", "east", "west"):
        facing = {"north": "south", "south": "north", "east": "west", "west": "east"}[side]
        plane = {"north": y1, "south": y0, "east": x1, "west": x0}[side]
        lo, hi = (x0, x1) if side in ("north", "south") else (y0, y1)
        for s0, s1 in _solid_spans(cv, a, side, z + 60, lo, hi):
            if s1 - s0 < 160:
                continue
            upper = [(u0, u1) for u0, u1 in _solid_spans(cv, a, side, z + 280, s0, s1) if u1 - u0 >= 160]
            n = int((s1 - s0) // 224)
            if n < 1:
                continue
            step = (s1 - s0) / n
            for i in range(n):
                c = round(s0 + step * (i + 0.5))
                r = rng.random()
                # ground floor: door niche, grilled window, or blank wall
                behind = _behind(side, plane, c, z + 60)
                thick = not cv.contains(behind)
                if any(k0 - 48 <= c <= k1 + 48 for k0, k1 in skip.get(side, ())):
                    r = 1.0
                if r < 0.35 and thick and h >= 256:
                    kit.door(cv, a, side, c, z, 56, 112, DOOR, (128, 256), STONE, depth=8)
                elif r < 0.7:
                    decal(b, facing, plane, c - 28, c + 28, z + 96, z + 159, WINDOW, (128, 144))
                # upper floor windows where the wall is tall enough
                if h >= 256 and any(u0 + 40 <= c <= u1 - 40 for u0, u1 in upper) and rng.random() < 0.8:
                    wz = z + 200 if h > 300 else z + 150
                    decal(b, facing, plane, c - 40, c + 40, wz, wz + 90, WINDOW, (128, 144))


def _behind(side, plane, u, z, d=40):
    if side == "north":
        return (u, plane + d, z)
    if side == "south":
        return (u, plane - d, z)
    if side == "east":
        return (plane + d, u, z)
    return (plane - d, u, z)


SHOTS = [
    Shot.looking_at("square_from_sw", (-560, -780, 82), (400, 100, 120)),
    Shot.looking_at("square_from_arcade", (300, 150, 82), (-100, -800, 60)),
    Shot.looking_at("terrace", (-560, 120, UP + 82), (500, -500, 40)),
    Shot.looking_at("north_arcade", (560, 180, 70), (-500, 150, 70)),
    Shot.looking_at("east_arcade", (736, -780, 70), (736, 50, 70)),
    Shot.looking_at("market_west_exit", (-1200, -1216, 82), (-2600, -1216, 260)),
    Shot.looking_at("market_east", (-600, -1150, 82), (1600, -1250, 100)),
    Shot.looking_at("stepped_alley_w", (-1152, -300, 82), (-1152, 640, 240)),
    Shot.looking_at("upper_street", (1900, 768, UP + 82), (-1000, 768, UP + 60)),
    Shot.looking_at("mosque_court", (-380, 960, UP + 82), (500, 1450, UP + 300)),
    Shot.looking_at("west_plaza", (-1400, -680, 82), (-1800, -200, 100)),
    Shot.looking_at("cafe", (1320, -1050, 82), (1700, -740, 40)),
    Shot.looking_at("east_plaza", (1330, -480, 82), (1700, -40, 120)),
    Shot.looking_at("house_interior", (-1260, 220, 82), (-1840, -100, 40)),
    Shot.looking_at("upper_east_exit", (1500, 800, UP + 82), (2800, 700, 500)),
    Shot.looking_at("south_gate", (0, -1250, 82), (0, -700, 100)),
    Shot.looking_at("covered_passage", (0, 300, UP + 82), (0, 700, UP + 60)),
    Shot.looking_at("upper_street_sandbags", (300, 800, UP + 82), (-100, 720, UP + 20)),
    Shot.looking_at("roofscape", (-1900, -1400, 700), (500, 600, 450)),
    Shot("overview", (-2500, -2450, 1000), (24, 48, 0)),
]
