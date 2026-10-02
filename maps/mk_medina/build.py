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
from functools import partial

from mohkit import kit, site
from mohkit.build import Carver, MapBuilder, Material as M
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
FRIEZE = "algiers/algiertrim"          # 64x64 ornamental band, for cornices
PLANKS = M("algiers/jh_portarz_bk")    # dark wood boards (balconies)
BALC_TRIM = M("algiers/wdtrimbal")

LAMP = (1.0, 0.8, 0.55)

# kit techniques in this map's palette
arcade = partial(kit.arcade, stone=STONE, column=COLM)
parapet = partial(kit.coped_wall, m=TRIM, cap=STONE)
dome = partial(kit.masonry_dome, stone=STONE, trim=TRIM)
balcony = partial(kit.mashrabiya, wood=PLANKS, trim=BALC_TRIM, beam=BEAM, roof=ROOFM, stone=STONE, grille=GRILLE)


# --------------------------------------------------------------------------- helpers
# --------------------------------------------------------------------------- hills
def dist_out(x, y):
    return site.outside_distance(x, y, (TX0, TY0, TX1, TY1))   # rounded-square contours


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
    b = MapBuilder("Medina", suncolor="160 140 104", sundirection="-55 225 0", sundiffuse="1.6",
                   sundiffusecolor="84 92 116", ambientlight="20 18 16", farplane="9000",
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
    b.prism(kit.polygon(0, -384, 144, 8, 22.5), 0, 28, {"up": STONE, "default": TILE})
    b.prism(kit.polygon(0, -384, 120, 8, 22.5), 28, 32, TILE)          # dry basin floor (raised)
    b.prism(kit.polygon(0, -384, 26, 8, 22.5), 32, 96, TILE)
    b.prism(kit.polygon(0, -384, 48, 8, 22.5), 96, 108, STONE)
    b.prism(kit.polygon(0, -384, 16, 8, 22.5), 108, 140, TILE)
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
        kit.image_panel(b, "south", 256, x - 72, x + 72, 0, 144, DOORWAY, (256, 256), WE)
    for y in (-760, -472, -184):
        kit.image_panel(b, "west", 832, y - 64, y + 64, 0, 128, DOORWAY, (256, 256), WE)

    # ---------------------------------------------------------------- gate and passage arches
    for yy in (-1088 + 16, -832 - 16):
        kit.arch_fill(b, "x", yy - 16, yy + 16, -96, 96, 100, 224, M("algiers/afrik_wall1a"), k=0.6)
    for yy in (256 + 16, 640 - 16):
        kit.arch_fill(b, "x", yy - 16, yy + 16, -96, 96, UP + 32, 352, UA, k=0.6)
    for xx in (640 + 16, 896 - 16):
        kit.arch_fill(b, "y", xx - 16, xx + 16, 640, 896, UP + 48, 384, UA, k=0.5)
    kit.arch_fill(b, "x", 896, 928, -96, 96, UP + 80, 400, UD, k=0.6)
    kit.lamp(b, 0, -960, 224, 110)
    kit.lamp(b, 0, 448, 352, 110)
    kit.lamp(b, 768, 768, 384, 120)

    # ---------------------------------------------------------------- mosque
    arcade(b, "x", 1344, [-448, -320, -192, -64, 64, 192, 320, 448], UP, UP + 96, 368, UA)
    b.prism(kit.polygon(0, 1136, 80, 8, 22.5), UP, UP + 24, {"up": STONE, "default": TILE})
    b.prism(kit.polygon(0, 1136, 20, 8, 22.5), UP + 24, UP + 64, TILE)
    for x, y, yaw in ((-300, 1040, 0), (300, 1230, 90)):
        b.prop("static/tree_regularpalm", x, y, UP, yaw)
    for x, y in ((-330, 1250), (330, 1030)):
        b.prop("static/tree_squatpalm", x, y, UP, rng.randrange(360))
    for x in (-256, 0, 256):
        kit.image_panel(b, "south", 1504, x - 64, x + 64, UP, UP + 128, DOORWAY, (256, 256), TRIM)
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
        kit.decal(b, "south", my0, x0, x1, ROOF + 250, ROOF + 316, GRILLE, (144, 128))
        kit.decal(b, "west", mx0, my0 + (x0 - mx0), my0 + (x1 - mx0), ROOF + 250, ROOF + 316, GRILLE, (144, 128))
    # dome over the prayer hall west of the court
    dome(b, -704, 1216, ROOF, 176)

    # ---------------------------------------------------------------- west quarter
    kit.stairs(b, -1152, 256, 0, "north", 128, UP, STONE, RISER)
    b.prop("static/tree_regularpalm", -1760, -600, 0, 60)
    b.prop("static/tree_squatpalm", -1420, -180, 0, 10)
    b.prism(kit.polygon(-1600, -416, 44, 8, 22.5), 0, 36, {"up": STONE, "default": M("algiers/afrik_wall1brick")})
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
        kit.awning(b, "south", -1088, x0, x1, 150)
    for x0, x1 in ((-1800, -1560), (-1040, -800), (400, 600), (1100, 1300), (1560, 1900)):
        kit.awning(b, "north", -1344, x0, x1, 150)
    for y0, y1 in ((-860, -560), (-20, 200)):
        kit.awning(b, "west", 1280, y0, y1, 150)

    # souk canopies across the market street and the east street
    for x0, x1 in ((-1400, -1240), (-520, -300), (180, 420), (1380, 1560)):
        kit.canopy(b, "x", x0, x1, -1344, -1088, 300, 28)
    for y0, y1 in ((-760, -600), (-300, -140)):
        kit.canopy(b, "y", y0, y1, 1088, 1280, 290, 24)

    # bracket lanterns in the narrow alleys (fixtures, so the shady lanes are not black)
    for x, y, z, wall in ((-1216, -700, 200, "west"), (-1216, 0, 200, "west"), (-860, -352, 200, "north"),
                          (-1536, -900, 200, "east"), (1088, -600, 220, "west"), (1728, 150, 200, "east"),
                          (-1400, 896, UP + 200, "north"), (1500, 640, UP + 200, "south")):
        kit.wall_lantern(b, x, y, z, wall, 190)

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
    kit.roof_edges(b, open_air, ROOF, (TX0, TY0, TX1, TY1), STONE, TRIM)
    for x0, y0, x1, y1, h, m in ROOF_BLOCKS:
        kit.roof_storey(b, cv, x0, y0, x1, y1, ROOF, h, m, ROOFM, BEAM, parapet, (WINDOW, (128, 144)),
                        avoid=[a.bounds for a in open_air])
    for x, y, face in STAIR_HOUSES:
        kit.stair_house(b, cv, x, y, face, ROOF, sh("algiers/afrik_wall1a", 0), ROOFM, (DOOR, (128, 256)), STONE,
                        parapet, avoid=[a.bounds for a in open_air])
    for x, y, r in SMALL_DOMES:
        dome(b, x, y, ROOF, r, rings=3, sides=10)

    # ---------------------------------------------------------------- facades
    rng2 = random.Random(11)
    for a in open_air:
        kit.dress_walls(b, cv, a, rng2, SKIP.get(a.name, {}), ROOF, (DOOR, (128, 256)), (WINDOW, (128, 144)), STONE,
                        balcony=balcony)
    rng3 = random.Random(5)
    for a in open_air:
        kit.wall_trim(b, cv, a, rng3, SKIP.get(a.name, {}), ROOF, FRIEZE, STONE, BEAM)
    for y in (-704, -448, -192):          # souk hall windows above the east arcade
        kit.decal(b, "west", 640, y - 40, y + 40, 250, 340, WINDOW, (128, 144))

    # ---------------------------------------------------------------- spawns
    south = [(-1850, -1216, 0), (-1350, -1180, 0), (-560, -1180, 0), (420, -1250, 180), (1400, -1180, 180),
             (1850, -1216, 180), (-1560, -520, 60), (-1480, -360, 300), (-1600, -900, 90), (1400, -960, 0),
             (-150, -700, 90), (250, -720, 90), (0, -1000, 90), (736, -560, 90)]
    north = [(-1850, 768, 0), (-1000, 830, 0), (-300, 760, 0), (320, 770, 180), (1200, 780, 180), (1850, 768, 180),
             (-150, 1180, 0), (150, 1080, 180), (0, 1424, 270), (300, 160, 180), (-1600, 100, 0), (1380, -420, 180),
             (1664, 0, 90), (-1152, 100, 90)]
    # 24 DM spawns (stock DM maps use 16-24); these four are team-only (a choke point, or
    # too close to a neighbour), so each team still has 14
    team_only = {(0, -1000), (736, -560), (300, 160), (1380, -420)}
    for x, y, yaw in south:
        dm = ("deathmatch",) if (x, y) not in team_only else ()
        b.spawn((x, y, 1), yaw, kinds=dm + ("allied",))
    for x, y, yaw in north:
        z = UP + 1 if y > 600 or (y > 64 and -640 < x < 640) else 1
        dm = ("deathmatch",) if (x, y) not in team_only else ()
        b.spawn((x, y, z), yaw, kinds=dm + ("axis",))
    b.entity("info_player_start", (0, -600, 1), angle="90")
    b.entity("info_player_intermission", (-500, -700, 420), angles="18 40 0")
    return b


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


SKIP = {"square": {"west": [(-340, 80)]}, "al_w": {"east": [(230, 640)], "west": [(230, 640)]},
        "st_e": {"east": [(230, 640)], "west": [(230, 640)]}, "al_e3": {"east": [(230, 640)], "west": [(230, 640)]}}




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
