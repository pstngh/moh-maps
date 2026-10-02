"""mk_summit: Summit (Call of Duty: Black Ops, 2010) rebuilt for MOHAA with stock textures:
a Soviet listening post on a snowy mountain top, with sheer drops on every side.

The layout follows the Black Ops minimap (512 px, ``local/summit_ref/Map_Summit_BO.png``,
downloaded from the CoD wiki, not in the repo): every position below is written in minimap
pixels ``(u, v)`` (u east, v south) and converted at 12 units per pixel. That is the CoD
scale (about 9.8 inches a pixel, from a 2.4 m truck and a 3 m gondola on the bird's-eye
view) times 1.3, the ratio of a MOHAA player (94 units) to a CoD player (72).
``python -m mohkit generate maps/mk_summit`` draws the plan over the minimap
(``dist/mk_summit_underlay.png``) when the reference is present.

North to south (minimap rows A-E):

* North yard (A3): the radio building, the radar dome tower (NE), a ledge behind the building.
* B row: barracks (B3), an alley, the red garage (B4); the cable-car station (B2) on the
  west edge with the gondola hanging over the drop.
* Control building (C3): a two-storey hall with galleries, a console island under a glass
  skylight, corridors with windows on the west (cliff path) and east (catwalk) sides.
* West cliff path (C2-D2): curves round the control building above the drop.
* South yard (D3) with the crane truck, the "2" garage (D2), a generator shed (D4).
* South guardhouse (E3) and the plaza where the mountain road arrives.

The plateau sits on cliffs 1,536 units above the valley floor (fatal; a trigger_hurt makes
sure). Outdoor air is everything inside the outer box minus the plateau and the building
masses, so the drops are real and the hull stays sealed (mohkit Carver).
"""

from __future__ import annotations

import math

from mohkit import kit
from mohkit.build import Air, Carver, MapBuilder, Material as M, aabb, box, merge_boxes, subtract_all
from mohkit.game import Shot

META = {"name": "mk_summit", "title": "Summit", "mode": "dm", "ambience": "mohdm4",
        "underlay": {"image": "local/summit_ref/Map_Summit_BO.png", "origin_px": [256, 272],
                     "units_per_px": 12, "alpha": 0.5, "zmin": -64}}

# --------------------------------------------------------------------------- scale
S = 12                       # units per minimap pixel
U0, V0 = 256, 272            # minimap pixel at world (0, 0)


def X(u: float) -> int:
    return 16 * round((u - U0) * S / 16)


def Y(v: float) -> int:
    return 16 * round((V0 - v) * S / 16)


def R(u0, v0, u1, v1) -> tuple[int, int, int, int]:
    """World rect (x0, y0, x1, y1) of a minimap pixel rect (u0, v0)-(u1, v1)."""
    return X(u0), Y(v1), X(u1), Y(v0)


def P(u, v) -> tuple[int, int]:
    return X(u), Y(v)


# --------------------------------------------------------------------------- levels
G = 0                # plateau ground
T = 16               # wall thickness (carver)
ST = 176             # one-storey ceiling
VOID = -1536         # valley floor
SKYTOP = 1280
OUTER = (-5376, -6400, 5376, 6656)          # far: room for the distant peaks

# --------------------------------------------------------------------------- materials
SKY = "sky/d-day2"            # grey overcast over a pale haze band
SKYM = M(SKY)
CAULK = M("common/caulk")
SNOW = M("norway/norsnow_lite256")              # plain snow
SNOWCONC = M("norway/csnowconc")               # trodden snow over concrete (yards)
ROOFSNOW = M("norway/norsnowmedium")
VALLEY = M("central_europe_winter/snow_bumpy_1")
CLIFF = M("central_europe_winter/forstsnow_rock256")
ROAD = M("norway/norroad_snow1")
GRIT = M("central_europe_winter/stset_1awinter")
GRATE = M("general_industrial/deckgrate_set1b")
CONC = M("norway/penwall1a")                    # weathered concrete
CONC_PLAIN = M("norway/norcrete1")
RESEARCH = M("norway/resrchnorway_wall1")       # concrete with snow streaks
CORR = M("general_structure/jh_corrugate4")     # grey corrugated metal
CORR_SNOW = M("central_europe_winter/corrugated_snowcovered")
CORR_RED = M("general_structure/jh_corrugate4c")
BUNKER = M("general_structure/concretewall_winter_bunker")
INWALL = M("norway/wall_verts_base2")           # interior: grey wall, dark dado
INWALL_HI = M("norway/nor_panelflat")
TILE = M("norway/nord_floortile")
CFLOOR = M("general_structure/concretefill_winter")
CEIL = M("norway/nor_panelflat")
PANEL = M("norway/nor_panel2_v2")               # control cabinets
PANEL_B = M("norway/nor_transferboxv1")
PANEL_C = M("norway/nor_panel1v1")
STEEL = M("central_europe_winter/ibeam_vertwnter")
STEEL_H = M("central_europe_winter/ibeam_horizwnter")
RAIL = M("norway/subpenrail")
GLASS = M("common/dglass")
WHITE = M("norway/nor_panelflat")
RED = M("general_structure/jh_corrugate4c")
TRIM = M("central_europe_winter/trim_set1fltw")
FRAME = M("norway/nor_panelflat")                 # plain grey steel
FENCE = M("central_europe_winter/secfence1_wntr")  # chain link (nonsolid, clips players)
WIRES = M("general_industrial/ge_wires_para")
GRID = M("general_industrial/industrialgrate1")     # antenna mesh

FLUO = (0.86, 0.92, 1.0)      # cool fluorescent
WARM = (1.0, 0.86, 0.66)


# --------------------------------------------------------------------------- the plan
class Bldg:
    def __init__(self, name, rect_px, top, face, enter=True):
        self.name = name
        self.rect = R(*rect_px)
        self.top = top
        self.face = face
        self.enter = enter

    def contains(self, x, y, z) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 <= x <= x1 and y0 <= y <= y1 and G - 1 <= z <= self.top + 1


# playable ground (all z = G), minimap pixels
FOOT_PX = [
    (222, 52, 297, 64),      # ledge behind the radio building
    (208, 62, 300, 100),     # radio building and its flanks
    (297, 57, 350, 120),     # radar dome yard
    (208, 92, 340, 142),     # north yard
    (184, 122, 212, 200),    # cable-car station strip
    (210, 138, 342, 200),    # B row
    (178, 195, 346, 232),    # central north strip
    (161, 215, 200, 262),    # west path, north bend
    (156, 255, 199, 302),    # west path, middle
    (159, 295, 200, 337),    # west path, south bend
    (171, 328, 232, 352),    # west path end
    (198, 228, 320, 320),    # control building (the east catwalk hangs over the drop)
    (195, 318, 334, 398),    # south yard
    (222, 396, 318, 432),    # guardhouse, road top
    (236, 428, 322, 482),    # south plaza
    (300, 438, 340, 472),    # road bend
]

BLDGS = [
    Bldg("radio", (230, 62, 290, 100), 208, CORR_SNOW),
    Bldg("barracks", (220, 142, 262, 195), 208, RESEARCH),
    Bldg("garage", (272, 142, 332, 195), 240, CORR_RED),
    Bldg("station", (186, 165, 207, 197), 320, CONC, enter=False),
    Bldg("control", (200, 230, 320, 318), 416, CONC),
    Bldg("garage2", (196, 344, 225, 386), 208, CORR),
    Bldg("shed", (286, 362, 311, 389), 160, CONC, enter=False),
    Bldg("guardhouse", (223, 398, 265, 430), 208, RESEARCH),
]
B = {bl.name: bl for bl in BLDGS}


OVERLAYS_PX = [(230, 322, 300, 396), (266, 398, 318, 480)]   # 2-unit floor plates
CATWALK = (768, 960)          # east catwalk x span (world), from the control building's east wall


def foot_rects():
    return [R(*r) for r in FOOT_PX]


def in_rects(x, y, rects) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)


# --------------------------------------------------------------------------- outdoor faces
def wall_fn(n, c):
    x, y, z = c
    if x <= OUTER[0] + 1 or x >= OUTER[2] - 1 or y <= OUTER[1] + 1 or y >= OUTER[3] - 1:
        return SKYM
    px, py = x - n[0] * 8, y - n[1] * 8          # a point inside the solid behind the face
    if z > G:
        for bl in BLDGS:
            if bl.contains(px, py, z):
                return bl.face
    return CLIFF


def floor_fn(n, c):
    x, y, z = c
    if z <= VOID + 1:
        return VALLEY
    if z > G + 1:
        return ROOFSNOW
    return SNOWCONC


# --------------------------------------------------------------------------- helpers
def room(cv, bl, z0, z1, floor, walls, ceiling, inset=T, name=""):
    x0, y0, x1, y1 = bl.rect
    return cv.room(x0 + inset, y0 + inset, z0, x1 - inset, y1 - inset, z1, floor=floor, walls=walls,
                   ceiling=ceiling, name=name or bl.name)


def opening(cv, bl, side, u, w, z0, z1, reveal=CONC, floor=CFLOOR, name="door"):
    """Air through the wall of ``bl`` on ``side`` centred at world ``u`` (x for N/S walls, y for E/W)."""
    x0, y0, x1, y1 = bl.rect
    a, b_ = u - w / 2, u + w / 2
    if side == "south":
        bb = (a, y0 - 8, z0, b_, y0 + T + 8, z1)
    elif side == "north":
        bb = (a, y1 - T - 8, z0, b_, y1 + 8, z1)
    elif side == "west":
        bb = (x0 - 8, a, z0, x0 + T + 8, b_, z1)
    else:
        bb = (x1 - T - 8, a, z0, x1 + 8, b_, z1)
    return cv.room(*bb, floor=floor, walls=reveal, ceiling=reveal, name=name)


def door(cv, bl, side, u, w=80, h=128, frame=FRAME, lamp=True, **kw):
    """Doorway with a steel frame round it and a cool wall lamp over it (outside)."""
    a = opening(cv, bl, side, u, w, G, G + h, **kw)
    if _B is None:
        return a
    x0, y0, x1, y1 = bl.rect
    if frame is not None:
        axis, plane = {"south": ("y", y0), "north": ("y", y1 - T), "west": ("x", x0), "east": ("x", x1 - T)}[side]
        kit.opening_frame(_B, axis, plane, T, u - w / 2, u + w / 2, G, G + h, frame, width=6)
    if lamp:
        # the lantern stands outside the wall; ``wall`` is where the wall is, seen from it
        at = {"south": (u, y0, "north"), "north": (u, y1, "south"), "west": (x0, u, "east"), "east": (x1, u, "west")}
        lx, ly, wall = at[side]
        kit.wall_lantern(_B, lx, ly, G + h + 40, wall, 170, (0.92, 0.95, 1.0))
    return a


_B = None     # the MapBuilder being filled (set in build(); door frames need it)


def window(cv, bl, side, u, w=96, z0=64, z1=136, **kw):
    return opening(cv, bl, side, u, w, z0, z1, name="window", **kw)


def railing(b, x0, y0, x1, y1, z, h=40):
    """Thin steel rail with posts every 128 along a straight run (axis aligned)."""
    if x1 - x0 >= y1 - y0:
        b.box((x0, y0 - 2, z + h - 4), (x1, y0 + 2, z + h), STEEL_H)
        n = max(1, int((x1 - x0) // 128))
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            b.box((x - 2, y0 - 2, z), (x + 2, y0 + 2, z + h - 4), STEEL)
    else:
        b.box((x0 - 2, y0, z + h - 4), (x0 + 2, y1, z + h), STEEL_H)
        n = max(1, int((y1 - y0) // 128))
        for i in range(n + 1):
            y = y0 + (y1 - y0) * i / n
            b.box((x0 - 2, y - 2, z), (x0 + 2, y + 2, z + h - 4), STEEL)


def polygon(cx, cy, r, n=16, phase=0.0):
    return [(round(cx + r * math.cos(math.radians(phase + 360 * i / n))),
             round(cy + r * math.sin(math.radians(phase + 360 * i / n)))) for i in range(n)]


def dome(b, cx, cy, z0, r, m, rings=5):
    """Hemisphere of stacked 16-gon slices on z0."""
    for i in range(rings):
        a0 = math.radians(90 * i / rings)
        a1 = math.radians(90 * (i + 1) / rings)
        rr = r * math.cos((a0 + a1) / 2)
        b.prism(polygon(cx, cy, max(rr, 8), 16, 11.25), z0 + r * math.sin(a0), z0 + r * math.sin(a1), m)


def console(b, x0, y0, x1, y1, h=72):
    """A bank of control cabinets: panel faces all round, a steel top."""
    b.box((x0, y0, G), (x1, y1, G + h), {"sides": PANEL, "top": STEEL_H, "default": CAULK})


def clip_box(b, x0, y0, z0, x1, y1, z1):
    b.box((x0, y0, z0), (x1, y1, z1), M("common/playerclip"))


# --------------------------------------------------------------------------- build
def build():
    b = MapBuilder(
        "Summit",
        suncolor="62 64 70",
        sundirection="-55 205 0",
        sundiffuse="1.5",
        sundiffusecolor="72 78 92",
        ambientlight="14 15 18",
        farplane="3800",
        farplane_color="0.71 0.71 0.73",
        farplane_cull="1",
        lightmapdensity="32",
    )
    cv = Carver(T, sky_shader=SKY)
    b.carve(cv)
    global _B
    _B = b

    # ---- outdoor air: the outer box minus the plateau and the building masses
    feet = foot_rects()
    solids = [aabb(x0, y0, VOID - 64, x1, y1, G) for x0, y0, x1, y1 in feet]
    solids += [aabb(*bl.rect[:2], G, *bl.rect[2:], bl.top) for bl in BLDGS]
    outer = aabb(OUTER[0], OUTER[1], VOID, OUTER[2], OUTER[3], SKYTOP)
    for i, p in enumerate(merge_boxes(subtract_all([outer], solids))):
        cv.add(Air(p, floor=floor_fn, walls=wall_fn, sky=True, name=f"out{i}", cuts=(G,)))

    radio(b, cv)
    barracks(b, cv)
    garage(b, cv)
    station(b, cv)
    control(b, cv)
    garage2(b, cv)
    shed(b)
    guardhouse(b, cv)
    yards(b)
    cable_car(b)
    mountains(b)
    edges(b)
    roofs(b)
    antenna_mast(b, *P(200, 112))
    power_lines(b)
    spawns(b)

    # the valley floor kills (a 1,536-unit fall is fatal anyway; this catches survivors). One
    # trigger per void column: q3map floods from a brush entity's centre, which must be in air.
    band = aabb(OUTER[0], OUTER[1], VOID, OUTER[2], OUTER[3], VOID + 256)
    for lo, hi in merge_boxes(subtract_all([band], solids)):
        hurt = b.entity("trigger_hurt", None, damage="1000")
        hurt.prims.append(box(lo, hi, M("common/trigger")))
    return b


# --------------------------------------------------------------------------- buildings
def radio(b, cv):
    bl = B["radio"]
    rm = room(cv, bl, G, ST, CFLOOR, INWALL, CEIL)
    x0, y0, x1, y1 = rm.bounds[0][0], rm.bounds[0][1], rm.bounds[1][0], rm.bounds[1][1]
    door(cv, bl, "south", X(245))
    door(cv, bl, "south", X(278))
    door(cv, bl, "west", Y(80))
    door(cv, bl, "east", Y(70))
    window(cv, bl, "north", X(255))
    window(cv, bl, "north", X(272))
    for i, u in enumerate((236, 252, 268, 284)):
        b.prop(f"static/static_radiostation{1 + i % 4}", X(u), y1 - 24, G, 270)
    b.prop("static/metaldesk", X(258), Y(85), G, 0)
    b.prop("furniture/bunkerchair", X(258), Y(80), G, 270)
    b.prop("static/static_subradio1", X(256), Y(85), G + 30, 270)
    b.prop("static/worktable", X(282), Y(92), G, 180)
    b.prop("static/cabinet_tall", x1 - 4, Y(70), G, 180)
    b.prop("static/bigfilecabinet", x0 + 24, y0 + 40, G, 0)
    for u in (242, 262, 282):
        b.light((X(u), (y0 + y1) / 2, ST - 32), 220, FLUO)
        b.prop("static/static_cagelight", X(u), (y0 + y1) / 2, ST, 0, hang=True)


def barracks(b, cv):
    bl = B["barracks"]
    rm = room(cv, bl, G, ST, CFLOOR, INWALL, CEIL)
    (x0, y0, _), (x1, y1, _) = rm.bounds
    door(cv, bl, "north", X(240))
    door(cv, bl, "south", X(234))
    door(cv, bl, "west", Y(180))
    door(cv, bl, "east", Y(155))
    door(cv, bl, "east", Y(185))
    window(cv, bl, "west", Y(155))
    for v in (150, 162, 174):
        b.prop("static/bunkbed", x1 - 48, Y(v), G, 180)
    for v in (148, 154, 160):
        b.prop("static/locker", x0 + 20, Y(v), G, 0)
    b.prop("static/bunkertable", X(236), Y(176), G + 38, 0)
    b.prop("furniture/bunkerchair", X(232), Y(176), G, 0)
    b.prop("static/metaldesk", X(250), Y(186), G, 0)
    for v in (154, 178):          # glass pyramids on the roof (bird's-eye view)
        px, py = P(238, v)
        b.hull([(px - 48, py - 48, bl.top), (px + 48, py - 48, bl.top), (px - 48, py + 48, bl.top),
                (px + 48, py + 48, bl.top), (px, py, bl.top + 56)], GLASS)
    for v in (152, 178):
        b.light((X(241), Y(v), ST - 32), 220, FLUO)
        b.prop("static/static_cagelight", X(241), Y(v), ST, 0, hang=True)


def garage(b, cv):
    bl = B["garage"]
    rm = room(cv, bl, G, 208, CFLOOR, [(G, CONC_PLAIN), (96, CORR)], CEIL)
    (x0, y0, _), (x1, y1, _) = rm.bounds
    opening(cv, bl, "south", X(296), 256, G, 176, name="garage_door")
    door(cv, bl, "west", Y(170))
    door(cv, bl, "north", X(310))
    b.prop("static/opeltruck_hoodopen", X(296), Y(172), G, 90)
    b.prop("static/static_cablespool_full", x1 - 48, y1 - 64, G, 0)
    b.prop("static/static_electricbox1", x0 + 8, y1 - 96, G, 0)
    for u in (285, 315):
        b.light((X(u), Y(165), 176), 260, FLUO)
        b.prop("static/static_cagelight", X(u), Y(165), 208, 0, hang=True)


def station(b, cv):
    """Cable-car station: a concrete tower the cable leaves from (not enterable)."""
    bl = B["station"]
    x0, y0, x1, y1 = bl.rect
    # cable wheel housing on the roof, cantilevered over the drop toward the gondola
    b.box((x0 - 96, y0 + 64, 288), (x0, y1 - 64, 320), CONC)
    b.box((x0 - 96, y0 + 64, 320), (x1, y1 - 64, 352), {"top": ROOFSNOW, "default": CORR})


def control(b, cv):
    """Two-storey control hall: galleries north and south, console island, corridors."""
    bl = B["control"]
    x0, y0, x1, y1 = bl.rect               # -672..768, -552..528
    GAL = 192
    # rooms
    west = cv.room(x0 + T, y0 + T, G, x0 + 144, y1 - T, ST, floor=TILE, walls=INWALL, ceiling=CEIL, name="c_west")
    east = cv.room(x1 - 144, y0 + T, G, x1 - T, y1 - T, ST, floor=TILE, walls=INWALL, ceiling=CEIL, name="c_east")
    hall = cv.room(x0 + 160, y0 + T, G, x1 - 160, y1 - T, 400, floor=TILE,
                   walls=[(G, INWALL), (GAL, CORR)], ceiling=CEIL, name="c_hall")
    hx0, hy0, hx1, hy1 = x0 + 160, y0 + T, x1 - 160, y1 - T
    # skylight over the centre
    sk = R(250, 258, 290, 292)
    cv.room(sk[0], sk[1], 400, sk[2], sk[3], bl.top + 8, floor=CAULK, walls=STEEL, ceiling=CAULK, name="skylight")
    # raised glass hip over the opening (the bird's-eye view's skylight), steel bars under it
    gx0, gy0, gx1, gy1 = sk[0] - 8, sk[1] - 8, sk[2] + 8, sk[3] + 8
    half = (gy1 - gy0) // 2
    b.hull([(gx0, gy0, bl.top), (gx1, gy0, bl.top), (gx0, gy1, bl.top), (gx1, gy1, bl.top),
            (gx0 + half, gy0 + half, bl.top + 112), (gx1 - half, gy0 + half, bl.top + 112)], GLASS)
    for x in range(sk[0] + 96, sk[2], 96):
        b.box((x - 4, sk[1], 392), (x + 4, sk[3], 400), STEEL_H)
    # doors and windows: corridors <-> hall, corridors <-> outside
    for v in (245, 272, 300):
        cv.room(x0 + 144 - 8, Y(v) - 48, G, hx0 + 8, Y(v) + 48, 128, floor=TILE, walls=CONC, ceiling=CONC, name="c_wdoor")
        cv.room(hx1 - 8, Y(v) - 48, G, x1 - 144 + 8, Y(v) + 48, 128, floor=TILE, walls=CONC, ceiling=CONC, name="c_edoor")
    for v in (238, 255, 290, 308):
        window(cv, bl, "west", Y(v), w=112, z0=56, z1=136)
    door(cv, bl, "west", Y(272), w=96)
    door(cv, bl, "east", Y(250), w=96)
    door(cv, bl, "east", Y(296), w=96)
    door(cv, bl, "north", X(232), w=112)
    door(cv, bl, "north", X(288), w=112)
    for u in (250, 270, 300):
        window(cv, bl, "north", X(u), w=128, z0=56, z1=136)
    for u in (222, 266):
        window(cv, bl, "south", X(u), w=128, z0=56, z1=136)
    # string course at the gallery level round the tall mass
    cap = {"top": ROOFSNOW, "default": CONC_PLAIN}
    b.box((x0 - 6, y0 - 6, 200), (x1 + 6, y0, 216), cap)
    b.box((x0 - 6, y1, 200), (x1 + 6, y1 + 6, 216), cap)
    b.box((x0 - 6, y0, 200), (x0, y1, 216), cap)
    b.box((x1, y0, 200), (x1 + 6, y1, 216), cap)
    door(cv, bl, "south", X(240), w=112)
    door(cv, bl, "south", X(292), w=112)
    # galleries: north and south, each with a stair from the hall floor
    for gy0, gy1, stair_y, d in ((hy1 - 256, hy1, hy1 - 256 - 192 * 2 + 0, "north"),
                                 (hy0, hy0 + 224, hy0 + 224 + 2 * 192, "south")):
        b.box((hx0, gy0, GAL - 16), (hx1, gy1, GAL), {"top": GRATE, "bottom": CEIL, "default": STEEL_H})
        edge_y = gy0 if d == "north" else gy1
        railing(b, hx0 + 112, edge_y, hx1 - 112, edge_y, GAL)
    # stairs: west and east, climbing north to the north gallery / south to the south gallery
    kit.stairs(b, hx0 + 56, hy1 - 256 - 384, G, "north", 96, GAL, GRATE, STEEL, step_h=16, step_d=32)
    kit.stairs(b, hx1 - 56, hy1 - 256 - 384, G, "north", 96, GAL, GRATE, STEEL, step_h=16, step_d=32)
    kit.stairs(b, hx0 + 56, hy0 + 224 + 384, G, "south", 96, GAL, GRATE, STEEL, step_h=16, step_d=32)
    kit.stairs(b, hx1 - 56, hy0 + 224 + 384, G, "south", 96, GAL, GRATE, STEEL, step_h=16, step_d=32)
    # high windows on the hall's long walls, glazed (daylight in, nobody out)
    for xx in range(hx0 + 112, hx1 - 160, 256):
        for side, yw in (("north", y1 - T // 2), ("south", y0 + T // 2)):
            opening(cv, bl, side, xx + 80, 160, 256, 352, reveal=CONC, floor=CONC, name="hall_window")
            b.box((xx, yw - 2, 256), (xx + 160, yw + 2, 352), GLASS)
            kit.opening_frame(b, "y", (y1 - T) if side == "north" else y0, T, xx, xx + 160, 256, 352, FRAME,
                              width=6, sill=True)
    # console island under the skylight, and cabinets along the gallery fronts
    cx, cy = (sk[0] + sk[2]) // 2, (sk[1] + sk[3]) // 2
    console(b, cx - 224, cy - 40, cx - 32, cy + 40)
    console(b, cx + 32, cy - 40, cx + 224, cy + 40)
    console(b, cx - 32, cy - 120, cx + 32, cy - 72, h=56)
    console(b, cx - 32, cy + 72, cx + 32, cy + 120, h=56)
    for u in (230, 300):
        b.prop("static/bigfilecabinet", X(u), hy1 - 300, G, 270)
        b.prop("static/metaldesk", X(u), hy0 + 300, G, 90)
    for i, u in enumerate((228, 244, 276, 292)):
        b.prop(f"static/static_radiostation{1 + i % 4}", X(u), hy1 - 24, GAL, 270)
    # upper office on the north gallery, a big window onto the hall (the gameplay screenshot)
    ox0, ox1, oy0, oy1, oz0, oz1 = cx - 192, cx + 192, hy1 - 160, hy1, GAL, 368
    wallm = {"default": INWALL_HI}
    for a, b_ in ((ox0, ox0 + 48), (ox0 + 112, ox0 + 128), (ox1 - 32, ox1)):
        b.box((a, oy0, oz0), (b_, oy0 + 8, oz1), wallm)
    b.box((ox0 + 48, oy0, 320), (ox0 + 112, oy0 + 8, oz1), wallm)                      # over the door
    b.box((ox0 + 128, oy0, oz0), (ox1 - 32, oy0 + 8, 232), wallm)                      # under the window
    b.box((ox0 + 128, oy0, 312), (ox1 - 32, oy0 + 8, oz1), wallm)                      # over the window
    b.box((ox0, oy0 + 8, oz0), (ox0 + 8, oy1, oz1), wallm)
    b.box((ox1 - 8, oy0 + 8, oz0), (ox1, oy1, oz1), wallm)
    b.box((ox0, oy0, oz1), (ox1, oy1, oz1 + 8), {"bottom": CEIL, "default": INWALL_HI})
    b.prop("static/metaldesk", cx + 40, oy1 - 48, GAL, 270)
    b.prop("static/bigfilecabinet", ox1 - 40, oy1 - 24, GAL, 270)
    b.light((cx, (oy0 + oy1) / 2, oz1 - 32), 200, FLUO)
    # a bank of file cabinets under the south gallery
    for i in range(5):
        b.prop("static/bigfilecabinet", cx - 160 + i * 40, hy0 + 40, G, 90)
    # pillars holding the galleries
    for xx in range(hx0 + 256, hx1 - 128, 320):
        for yy in (hy1 - 256, hy0 + 224):
            kit.column(b, xx, yy, G, GAL - 16, CONC, size=32)
    # lights: fluorescent rows under the ceiling and the galleries, corridors
    for xx in range(hx0 + 160, hx1, 288):
        for yy in (hy1 - 128, hy0 + 112):
            b.light((xx, yy, GAL - 32), 230, FLUO)
            b.prop("static/static_cagelight", xx, yy, GAL - 16, 0, hang=True)
            b.light((xx, yy, 368), 300, FLUO)
        b.light((xx, cy, 360), 260, FLUO)
    for v in (240, 272, 304):
        for xx in (x0 + 80, x1 - 80):
            b.light((xx, Y(v), ST - 32), 200, FLUO)
            b.prop("static/static_cagelight", xx, Y(v), ST, 0, hang=True)
    # satellite dome on the south-east roof corner
    dome(b, X(306), Y(306), bl.top, 96, WHITE)


def garage2(b, cv):
    """The "2" garage at the end of the cliff path: a shutter door west, doors north and east."""
    bl = B["garage2"]
    room(cv, bl, G, ST, CFLOOR, [(G, CONC_PLAIN), (64, CORR)], CEIL)
    door(cv, bl, "west", Y(352), w=112)
    door(cv, bl, "north", X(214))
    door(cv, bl, "east", Y(372))
    x0, y0, x1, y1 = bl.rect
    # roll-up shutter (decorative, closed) on the west wall
    b.box((x0 - 4, Y(374), G), (x0, Y(358), 160), {"west": CORR, "default": STEEL})
    b.prop("static/static_electricbox1", X(212), Y(380), G, 0)
    b.prop("static/static_cablespool_empty", X(204), Y(350), G, 30)
    b.light((X(210), Y(364), ST - 32), 220, FLUO)
    b.prop("static/static_cagelight", X(210), Y(364), ST, 0, hang=True)


def shed(b):
    bl = B["shed"]
    x0, y0, x1, y1 = bl.rect
    b.prop("static/static_electricbox1", x0 - 12, (y0 + y1) / 2, G, 90)
    b.prop("static/static_cablespool_full", x0 - 56, y0 + 40, G, 0)


def guardhouse(b, cv):
    bl = B["guardhouse"]
    rm = room(cv, bl, G, ST, CFLOOR, INWALL, CEIL)
    door(cv, bl, "north", X(232))
    door(cv, bl, "south", X(256))
    door(cv, bl, "east", Y(414))
    window(cv, bl, "south", X(236))
    window(cv, bl, "west", Y(414))
    x0, y0, x1, y1 = bl.rect
    # red sign band on the north face (the minimap's red line)
    b.box((x0 + 32, y1, 136), (x1 - 32, y1 + 6, 176), {"north": RED, "default": STEEL})
    b.prop("static/metaldesk", X(244), Y(420), G, 0)
    b.prop("furniture/bunkerchair", X(244), Y(425), G, 90)
    b.prop("static/cabinet_tall", x0 + 20, Y(404), G, 0)
    b.light((X(244), Y(414), ST - 32), 220, FLUO)
    b.prop("static/static_cagelight", X(244), Y(414), ST, 0, hang=True)


# --------------------------------------------------------------------------- outdoors
def yards(b):
    # radar dome tower (NE)
    cx, cy = P(328, 95)
    b.prism(polygon(cx, cy, 150, 16, 11.25), G, 240, CORR_SNOW)
    b.prism(polygon(cx, cy, 168, 16, 11.25), 240, 256, {"top": ROOFSNOW, "default": STEEL})
    dome(b, cx, cy, 256, 144, WHITE, rings=6)
    clip_box(b, cx - 168, cy - 168, 240, cx + 168, cy + 168, 600)
    # north yard clutter
    b.prop("static/indycrate", *P(254, 108), G, 10)
    b.prop("static/30cal_crate", *P(257, 112), G, 40)
    b.prop("static/sandbag_large_semicircle_winter", *P(244, 128), G, 200)
    b.prop("static/static_cablespool_full", *P(285, 108), G, 90)
    # B-row alley and the north strip
    b.prop("static/indycrate", *P(270, 185), G, 0)
    b.prop("static/exp_crate1", *P(225, 213), G, 20)
    b.prop("static/sandbag_large_semicircle_winter", *P(300, 216), G, 0)
    # south yard: the crane truck, grit underfoot
    yx0, yy0, yx1, yy1 = R(*OVERLAYS_PX[0])
    b.box((yx0, yy0, G), (yx1, yy1, G + 2), {"top": GRIT, "default": CAULK})
    b.prop("static/vehicle_opeltruck", *P(252, 360), G + 2, 70)
    b.prop("static/indycrate", *P(275, 340), G + 2, 0)
    b.prop("static/indycrate", *P(278, 344), G + 2, 30)
    b.prop("static/sandbag_large_semicircle_winter", *P(240, 385), G + 2, 90)
    # road
    rx0, ry0, rx1, ry1 = R(*OVERLAYS_PX[1])
    b.box((rx0, ry0, G), (rx1, ry1, G + 2), {"top": ROAD(rotate=90), "default": CAULK})
    catwalk(b)
    # trees on the slopes below the edges (tops visible over the rim)
    for u, v, sc in ((200, 70, 1.4), (190, 110, 1.2), (350, 160, 1.3), (353, 240, 1.5), (172, 362, 1.4),
                     (214, 452, 1.2), (330, 422, 1.3), (300, 48, 1.1), (148, 230, 1.2)):
        x, y = P(u, v)
        rock_spur(b, x, y, G - 384)
        b.prop("static/tree_winter_tallpine", x, y, G - 384, (u * 37 + v) % 360, sc)
    # lamp posts
    for u, v, wall in ((262, 141, "north"), (244, 229, "south"), (300, 319, "north"), (245, 431, "north")):
        kit.wall_lantern(b, X(u), Y(v), 150, wall, 200, (0.95, 0.95, 1.0))


def rock_spur(b, x, y, top, r=120):
    """A rock outcrop rising from the valley to ``top``, wider at the bottom, for trees to stand on."""
    rnd = (x * 7 + y * 13) % 360
    b.prism(polygon(x, y, r, 7, rnd), top - 192, top, {"top": SNOW, "default": CLIFF})
    b.prism(polygon(x, y, r * 1.5, 7, rnd + 20), top - 640, top - 192, {"top": SNOW, "default": CLIFF})
    b.prism(polygon(x, y, r * 2.2, 7, rnd + 40), VOID, top - 640, {"top": SNOW, "default": CLIFF})


def catwalk(b):
    """Steel-grate walkway along the control building's east wall, over the drop, on legs."""
    x0, x1 = CATWALK
    y0, y1 = Y(318), Y(232)
    b.box((x0, y0, G - 8), (x1, y1, G), {"top": GRATE, "bottom": GRATE, "default": STEEL_H})
    for y in range(y0 + 64, y1, 256):
        b.box((x0 + 8, y - 6, G - 24), (x1, y + 6, G - 8), STEEL_H)                   # cross beam
        b.box((x1 - 24, y - 8, VOID), (x1 - 8, y + 8, G - 24), STEEL)                 # leg to the rock
        b.hull([(x1 - 24, y - 4, G - 24), (x1 - 8, y - 4, G - 24), (x1 - 24, y + 4, G - 24), (x1 - 8, y + 4, G - 24),
                (x0 + 16, y - 4, G - 216), (x0, y - 4, G - 216), (x0 + 16, y + 4, G - 216), (x0, y + 4, G - 216)], STEEL)
    railing(b, x1 - 6, y0, x1 - 6, y1, G)


def mountains(b):
    """Snowy peaks round the plateau, far enough for the fog to turn them into pale silhouettes,
    and boulders down the cliff faces just below the rim."""
    # a ring of broad peaks (base radius 1,450, apex 400 below to 450 above the plateau) on
    # an ellipse 3,800 x 4,800 out: the fog (farplane 3,800) leaves soft silhouettes. Each
    # peak is 7 pie-slice wedges, so no brush is wider than the renderer's face limits like.
    PEAK_SNOW = M("norway/norsnow_med256ns")
    for i in range(16):
        a = 2 * math.pi * i / 16 + 0.2
        x, y = 3800 * math.cos(a), 4800 * math.sin(a)
        r = 1450
        top = -400 + 850 * abs(math.sin(2.3 * i + 0.5))
        apex = (round(x + 300 * math.cos(1.9 * i)), round(y + 300 * math.sin(1.9 * i)), round(top))
        ring = [(round(x + r * math.cos(2 * math.pi * (k + 0.37 * i) / 7)),
                 round(y + r * math.sin(2 * math.pi * (k + 0.37 * i) / 7)), VOID) for k in range(7)]
        for k in range(7):
            b.hull([(round(x), round(y), VOID), ring[k], ring[(k + 1) % 7], apex], PEAK_SNOW)
    # boulders on the cliff faces below the rim, along the plateau's outline
    rnd = [(158, 240), (157, 285), (165, 330), (186, 140), (205, 60), (296, 52), (348, 100), (344, 180),
           (334, 330), (322, 470), (238, 480), (226, 430), (190, 360), (352, 130)]
    feet = foot_rects()
    cx0, cy0 = P(256, 272)
    for i, (u, v) in enumerate(rnd):
        sc = 2.5 + (i % 2)
        rad = 70 * sc
        x, y = P(u, v)
        dx, dy = x - cx0, y - cy0
        d = math.hypot(dx, dy) or 1.0
        while any(x0 - rad < x < x1 + rad and y0 - rad < y < y1 + rad for x0, y0, x1, y1 in feet):
            x, y = x + 32 * dx / d, y + 32 * dy / d          # out from the centre until clear of the plateau
        b.prop("static/rock_winter_large", round(x), round(y), G - 48 - 114 * sc - (i % 3) * 64, (i * 67) % 360, sc)


def cable_car(b):
    """Gondola hanging west of the station, its cables running off to the west over the drop."""
    gx, gy = P(162, 181)
    z0 = 160
    body = {"sides": RED, "top": STEEL_H, "bottom": STEEL_H}
    b.box((gx - 64, gy - 44, z0), (gx + 64, gy + 44, z0 + 24), body)                 # skirt
    b.box((gx - 64, gy - 44, z0 + 72), (gx + 64, gy + 44, z0 + 112), body)           # roof band
    for sx in (-64, 60):
        b.box((gx + sx, gy - 44, z0 + 24), (gx + sx + 4, gy + 44, z0 + 72), RED)
    b.box((gx - 60, gy - 44, z0 + 24), (gx + 60, gy - 40, z0 + 72), GLASS)
    b.box((gx - 60, gy + 40, z0 + 24), (gx + 60, gy + 44, z0 + 72), GLASS)
    b.box((gx - 4, gy - 4, z0 + 112), (gx + 4, gy + 4, 300), STEEL)               # hanger
    st = B["station"].rect
    xa, za, xb, zb = st[0] - 96, 316, OUTER[0] + 32, 120
    n = 4
    for dy in (-24, 24):
        y = gy + dy
        for i in range(n):
            x0, x1 = xa + (xb - xa) * i / n, xa + (xb - xa) * (i + 1) / n
            z0, z1 = za + (zb - za) * i / n, za + (zb - za) * (i + 1) / n
            b.hull([(x0, y - 2, z0), (x0, y + 2, z0), (x0, y - 2, z0 + 4), (x0, y + 2, z0 + 4),
                    (x1, y - 2, z1), (x1, y + 2, z1), (x1, y - 2, z1 + 4), (x1, y + 2, z1 + 4)], STEEL_H)
    clip_box(b, gx - 72, gy - 52, z0 - 8, gx + 72, gy + 52, z0 + 320)


def edges(b):
    """Railings along the cliff edges people walk next to, chain-link fences elsewhere."""
    x0, y0, x1, y1 = R(222, 52, 297, 64)
    fence(b, x0 + 16, y1 - 12, x1 - 16, y1 - 12)                      # north ledge
    x0, y0, x1, y1 = R(236, 428, 322, 482)
    fence(b, x0 + 16, y0 + 12, x1 - 16, y0 + 12)                      # south plaza
    x0, y0, x1, y1 = R(297, 57, 350, 120)
    fence(b, x1 - 12, y0 + 32, x1 - 12, y1 - 16)                      # dome yard, east
    for (u0, v0, u1, v1) in ((161, 215, 161, 262), (156, 255, 156, 302), (159, 295, 159, 337)):
        xa, ya, _, yb = R(u0, v0, u1 + 1, v1)
        railing(b, xa + 8, ya + 32, xa + 8, yb - 32, G)


def dish(b, x, y, z, r, yaw, tilt=35):
    """Satellite dish: a shallow cone (convex hull of a tilted rim and a back point) on a post."""
    a, t = math.radians(yaw), math.radians(tilt)
    fx, fy, fz = math.cos(a) * math.cos(t), math.sin(a) * math.cos(t), math.sin(t)   # facing
    ux, uy, uz = -math.cos(a) * math.sin(t), -math.sin(a) * math.sin(t), math.cos(t)  # rim "up"
    sx, sy = -math.sin(a), math.cos(a)                                                # rim "side"
    cz = z + r + 24
    rim = [(x + r * (math.cos(k * math.pi / 4) * sx + math.sin(k * math.pi / 4) * ux),
            y + r * (math.cos(k * math.pi / 4) * sy + math.sin(k * math.pi / 4) * uy),
            cz + r * math.sin(k * math.pi / 4) * uz) for k in range(8)]
    back = (x - fx * r * 0.45, y - fy * r * 0.45, cz - fz * r * 0.45)
    b.hull([tuple(round(c, 1) for c in q) for q in rim] + [back], WHITE)
    b.box((x - 4, y - 4, z), (x + 4, y + 4, cz - r * 0.3), STEEL)


def billboard(b, x, y, z, w, yaw_axis="x"):
    """Red sign panel on two legs (the loading screen's roof signs)."""
    if yaw_axis == "x":
        b.box((x - w / 2, y - 3, z + 64), (x + w / 2, y + 3, z + 160), {"sides": RED, "default": STEEL_H})
        for dx in (-w / 2 + 16, w / 2 - 24):
            b.box((x + dx, y - 4, z), (x + dx + 8, y + 4, z + 64), STEEL)
    else:
        b.box((x - 3, y - w / 2, z + 64), (x + 3, y + w / 2, z + 160), {"sides": RED, "default": STEEL_H})
        for dy in (-w / 2 + 16, w / 2 - 24):
            b.box((x - 4, y + dy, z), (x + 4, y + dy + 8, z + 64), STEEL)


def roofs(b):
    """Parapets, vents, dishes and signs on the flat roofs (the skyline seen from everywhere)."""
    for bl in BLDGS:
        x0, y0, x1, y1 = bl.rect
        z = bl.top
        cap = {"top": ROOFSNOW, "default": CONC_PLAIN}
        b.box((x0, y0, z), (x1, y0 + 8, z + 24), cap)
        b.box((x0, y1 - 8, z), (x1, y1, z + 24), cap)
        b.box((x0, y0 + 8, z), (x0 + 8, y1 - 8, z + 24), cap)
        b.box((x1 - 8, y0 + 8, z), (x1, y1 - 8, z + 24), cap)
        # one vent block per roof, off-centre
        vx, vy = x0 + (x1 - x0) * 0.3, y0 + (y1 - y0) * 0.65
        b.box((vx - 40, vy - 32, z), (vx + 40, vy + 32, z + 48), {"top": ROOFSNOW, "default": CORR})
    dish(b, *P(245, 75), B["radio"].top, 72, 200)
    dish(b, *P(312, 152), B["garage"].top, 56, 120)
    dish(b, *P(232, 252), B["control"].top, 80, 160)
    dish(b, *P(214, 410), B["guardhouse"].top, 48, 260)
    billboard(b, *P(272, 146), B["garage"].top, 224)
    billboard(b, *P(262, 236), B["control"].top, 288)
    billboard(b, *P(203, 365), B["garage2"].top, 192, "y")


def antenna_mast(b, x, y):
    """Steel mast with a mesh antenna panel and coils, on a rock spur below the rim (loading screen)."""
    rock_spur(b, x, y, G - 64, r=96)
    top = 520
    b.hull([(x - 24, y - 24, G - 64), (x + 24, y - 24, G - 64), (x - 24, y + 24, G - 64), (x + 24, y + 24, G - 64),
            (x - 10, y - 10, top), (x + 10, y - 10, top), (x - 10, y + 10, top), (x + 10, y + 10, top)],
           {"sides": RED, "default": STEEL})
    for z in range(G + 64, top, 96):
        b.box((x - 26, y - 26, z), (x + 26, y + 26, z + 8), STEEL_H)
    b.box((x - 120, y - 4, top), (x + 120, y + 4, top + 176), {"north": GRID, "south": GRID, "default": STEEL_H})
    for dx in (-60, 60):
        b.prism(polygon(x + dx, y + 12, 20, 8), top + 40, top + 136, STEEL_H)
    clip_box(b, x - 128, y - 32, G - 64, x + 128, y + 32, top + 200)


def power_lines(b):
    """Wooden-post power line along the west edge of the yards, with sagging wires."""
    posts = [P(214, 96), P(212, 146), P(206, 202), P(226, 322), P(232, 392)]
    h = 320
    for x, y in posts:
        b.box((x - 6, y - 6, G), (x + 6, y + 6, G + h), {"sides": M("general_structure/beam_wood1"), "default": CAULK})
        b.box((x - 48, y - 4, G + h - 32), (x + 48, y + 4, G + h - 20), M("general_structure/beam_wood1"))
    for (xa, ya), (xb, yb) in zip(posts, posts[1:]):
        for off in (-40, 40):
            za, zb = G + h - 32, G + h - 32
            mid = ((xa + xb) / 2 + off, (ya + yb) / 2, za - 48)
            for (p0, p1) in (((xa + off, ya, za), mid), (mid, (xb + off, yb, zb))):
                b.hull([(p0[0] - 1, p0[1], p0[2]), (p0[0] + 1, p0[1], p0[2]), (p0[0], p0[1], p0[2] + 2),
                        (p1[0] - 1, p1[1], p1[2]), (p1[0] + 1, p1[1], p1[2]), (p1[0], p1[1], p1[2] + 2)], STEEL_H)


def fence(b, x0, y0, x1, y1, h=112):
    """Chain-link fence (nonsolid texture that clips players) with steel posts, along an axis."""
    if x1 - x0 >= y1 - y0:
        b.box((x0, y0 - 1, G), (x1, y0 + 1, G + h), {"north": FENCE, "south": FENCE, "default": CAULK})
        n = max(1, int((x1 - x0) // 192))
        pts = [(x0 + (x1 - x0) * i / n, y0) for i in range(n + 1)]
    else:
        b.box((x0 - 1, y0, G), (x0 + 1, y1, G + h), {"east": FENCE, "west": FENCE, "default": CAULK})
        n = max(1, int((y1 - y0) // 192))
        pts = [(x0, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    for x, y in pts:
        b.box((x - 3, y - 3, G), (x + 3, y + 3, G + h + 8), STEEL)


# --------------------------------------------------------------------------- spawns
def spawns(b):
    pts = [
        # (u, v, yaw, team)  team: a = allies (south), x = axis (north), "" = DM only
        (250, 120, 270, "x"), (300, 128, 200, "x"), (222, 112, 300, "x"), (260, 56, 0, "x"),
        (312, 100, 250, "x"), (196, 140, 270, "x"), (276, 150, 270, "x"), (240, 168, 0, ""),
        (322, 158, 180, "x"), (200, 210, 300, "x"),
        (170, 250, 270, ""), (165, 300, 90, ""), (185, 340, 0, ""), (230, 260, 0, ""),
        (280, 280, 180, ""), (328, 262, 270, ""), (290, 222, 0, ""),
        (210, 365, 90, "a"), (265, 330, 90, "a"), (275, 385, 135, "a"), (325, 350, 90, "a"),
        (236, 412, 90, "a"), (250, 455, 90, "a"), (290, 470, 120, "a"), (310, 440, 135, "a"),
        (285, 410, 90, "a"), (320, 455, 135, "a"),
    ]
    plates = [R(*r) for r in OVERLAYS_PX]
    for u, v, yaw, team in pts:
        x, y = P(u, v)
        z = G + 1 + (2 if in_rects(x, y, plates) else 0)
        if team != "a" or (u, v) in ((210, 365), (265, 330), (275, 385), (325, 350), (250, 455)):
            b.spawn((x, y, z), yaw, kinds=("deathmatch",))
        if team == "a":
            b.spawn((x, y, z), yaw, kinds=("allied",))
        elif team == "x":
            b.spawn((x, y, z), yaw, kinds=("axis",))
    b.entity("info_player_start", (*P(250, 455), G + 1), angle="90")
    b.entity("info_player_intermission", (*P(150, 420), 700), angles="25 60 0")


# --------------------------------------------------------------------------- cameras
def _eye(u, v, z=82):
    x, y = P(u, v)
    return (x, y, z)


SHOTS = [
    Shot.looking_at("north_yard", _eye(220, 135), _eye(320, 95, 120)),
    Shot.looking_at("radar_dome", _eye(260, 120), _eye(328, 95, 260)),
    Shot.looking_at("b_alley", _eye(271, 205), _eye(271, 130)),
    Shot.looking_at("cable_car", _eye(198, 210, 150), _eye(162, 181, 200)),
    Shot.looking_at("west_path_north", _eye(170, 335), _eye(175, 215)),
    Shot.looking_at("west_path_south", _eye(180, 215), _eye(180, 345)),
    Shot.looking_at("hall_from_south", _eye(262, 312), _eye(262, 240, 150)),
    Shot.looking_at("hall_gallery", _eye(220, 237, 274), _eye(300, 300, 60)),
    Shot.looking_at("hall_corridor", _eye(206, 312), _eye(206, 236)),
    Shot.looking_at("east_catwalk", _eye(334, 318), _eye(334, 205)),
    Shot.looking_at("catwalk_drop", (X(318), Y(214), 150), (X(338), Y(300), -260)),
    Shot.looking_at("view_west", _eye(165, 280), (X(60), Y(260), -200)),
    Shot.looking_at("hall_office", _eye(270, 300, 274), _eye(266, 245, 260)),
    Shot.looking_at("south_yard", _eye(300, 395), _eye(240, 330, 60)),
    Shot.looking_at("south_plaza", _eye(290, 475), _eye(260, 380, 120)),
    Shot.looking_at("radio_inside", _eye(236, 94), _eye(286, 70)),
    Shot.looking_at("garage_inside", _eye(280, 192), _eye(318, 148)),
    Shot.looking_at("overview_sw", (X(120), Y(420), 1100), (X(270), Y(250), 0)),
    Shot.looking_at("overview_n", (X(300), Y(-20), 1200), (X(260), Y(260), 0)),
]
