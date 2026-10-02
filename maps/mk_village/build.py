"""mk_village: a Normandy crossroads for DM/TDM, built entirely with mohkit.

Layout (plan, +Y north)::

    +-------------------- north street --------------------+
    |  |   house A    |lane|        block NE          |    |
    | w|--------------+    +--------------------------| e  |
    | e|                 square          | town hall  | a  |
    | s|  (fountain)                     | (2 floors) | s  |
    | t|---------------------+lane+-------------------| t  |
    |  |     warehouse       |    |     block SE      |    |
    +-------------------- south street --------------------+

All playable space is described as air boxes (mohkit.build.Carver), so the hull is
sealed by construction. Facades, windows, roofs and props are detail.
"""


from mohkit.build import Carver, MapBuilder, Material
from mohkit import kit
from mohkit.game import Shot

META = {"name": "mk_village", "title": "Village Crossroads", "mode": "dm", "ambience": "mohdm1"}

M = Material
# --- palette (all retail Allied Assault) -------------------------------------
COBBLE = M("central_europe/small_cobble")
STREET = M("central_europe/strtset_cew")
STONE = M("general_structure/stonebricks1", (0.5, 0.5))
PLASTER_TAN = M("central_europe/exterior_wall_2")
PLASTER_WHITE = M("general_structure/plaster_wall2")
PLASTER_OLD = M("general_structure/plaster_wall3b")
BRICK = M("central_europe/normndybrik1")
TUDOR = M("central_europe/tudor_set1_exwall1a", (0.625, 0.625))
ROOF_RED = M("central_europe/redshingle")
ROOF_RUSTIC = M("central_europe/rusticshingle")
BEAM = M("general_structure/beam_wood1", (0.5, 0.5))
FLOOR_WOOD = M("general_structure/floor4")
FLOOR_PLANK = M("central_europe/flrwood2")
INT_WALL = M("general_structure/plaster_wall2a")
INT_WAINSCOT = M("central_europe/interiorwall_set2")
CEILING = M("general_structure/plank_flat")
MOLDING = M("general_structure/building_molding", (1, 0.25))
CONC = M("general_structure/jh_conc512b")
WARE_WALL = M("general_structure/jh_brick4")
CRATE = M("general_structure/jh_oldwood1")

WIN = ("general_structure/denmark_win2", (128, 180))
WIN_HALL = ("central_europe/windowtownhall1", (256, 256))
DOOR = ("general_structure/doubledoor2", (128, 256))
DOOR_B = ("general_structure/door_rorng2", (128, 256))

GROUND, STOREY, FACADE_TOP, SKY_TOP = 0, 160, 320, 1152
T = 16  # carver wall thickness


def build():
    b = MapBuilder(
        "Village Crossroads",
        ambientlight="14 14 16",
        suncolor="72 64 52",
        sundirection="315 235 0",
        sundiffuse="1.2",
        sundiffusecolor="56 62 78",
        lightmapdensity="16",
        farplane="6000",
        farplane_color="0.62 0.66 0.72",
        farplane_cull="0",
    )
    cv = Carver(T, sky_shader="sky/mohday2")
    b.carve(cv)

    def band(upper):
        return [(GROUND, STONE), (32, upper)]

    def band2(lower, upper):
        return [(GROUND, STONE), (32, lower), (STOREY, upper)]

    # --- outdoor air --------------------------------------------------------------
    sq = cv.room(-640, -448, GROUND, 640, 448, FACADE_TOP, floor=COBBLE, name="square", priority=2,
                 walls={"north": band2(PLASTER_TAN, TUDOR), "south": band(PLASTER_WHITE),
                        "west": band2(PLASTER_OLD, PLASTER_OLD), "east": band(BRICK)})
    ns = cv.room(-1152, 832, GROUND, 1152, 1088, FACADE_TOP, floor=STREET, name="north_st",
                 walls={"south": band2(PLASTER_WHITE, TUDOR), "north": band(PLASTER_OLD), "default": band(PLASTER_TAN)})
    ss = cv.room(-1152, -1088, GROUND, 1152, -832, FACADE_TOP, floor=STREET, name="south_st",
                 walls={"north": band(WARE_WALL), "south": band2(PLASTER_TAN, TUDOR), "default": band(PLASTER_WHITE)})
    ws = cv.room(-1152, -832, GROUND, -896, 832, FACADE_TOP, floor=STREET, name="west_st",
                 walls={"west": band(BRICK), "east": band2(PLASTER_OLD, PLASTER_OLD)})
    es = cv.room(896, -832, GROUND, 1152, 832, FACADE_TOP, floor=STREET, name="east_st",
                 walls={"east": band2(PLASTER_TAN, TUDOR), "west": band(BRICK)})
    nl = cv.room(-96, 448, GROUND, 96, 832, FACADE_TOP, floor=STREET, name="north_lane",
                 walls=band(PLASTER_WHITE))
    sl = cv.room(256, -832, GROUND, 448, -448, FACADE_TOP, floor=STREET, name="south_lane",
                 walls=band(PLASTER_TAN))
    # arched passage through the west block
    wl = cv.room(-896, -64, GROUND, -640, 64, 176, floor=STREET, walls=STONE, ceiling=BEAM, name="west_passage")

    # one sky volume over everything; its floor is the flat roof of every building mass
    cv.room(-1408, -1344, FACADE_TOP, 1408, 1344, SKY_TOP, floor=CONC, sky=True, walls=M("sky/mohday2"),
            name="sky")

    # --- town hall (east of the square, two floors) ------------------------------------
    hall = cv.room(672, -352, GROUND, 864, 352, STOREY, floor=FLOOR_WOOD, ceiling=CEILING,
                   walls=[(GROUND, INT_WAINSCOT), (48, INT_WALL)], name="hall_ground")
    hall_up = cv.room(672, -352, STOREY + T, 864, 352, FACADE_TOP - T, floor=FLOOR_PLANK, ceiling=CEILING,
                      walls=INT_WALL, name="hall_upper")
    # doors: square -> hall, hall -> east street
    cv.room(640, -64, GROUND, 672, 64, 128, floor=STONE, walls=STONE, ceiling=BEAM, name="hall_door_w")
    cv.room(864, 128, GROUND, 896, 256, 128, floor=STONE, walls=STONE, ceiling=BEAM, name="hall_door_e")
    # stairwell: open the floor slab over the stair run (north end of the hall)
    cv.room(768, 128, GROUND, 864, 352, FACADE_TOP - T, floor=FLOOR_WOOD, walls=INT_WALL, ceiling=CEILING,
            name="stairwell")
    kit.stairs(b, 816, 144, GROUND, "north", 96, STOREY + T, FLOOR_WOOD, BEAM, step_h=16, step_d=16)
    # upper-floor windows over the square and the east street (real openings)
    for y0 in (-288, -96, 160):
        cv.room(640, y0, 224, 672, y0 + 64, 288, floor=STONE, walls=STONE, ceiling=STONE, name="hall_win")
    for y0 in (-288, -96):
        cv.room(864, y0, 224, 896, y0 + 64, 288, floor=STONE, walls=STONE, ceiling=STONE, name="hall_win_e")
    kit.lamp(b, 768, -160, STOREY, 260)
    kit.lamp(b, 720, 160, FACADE_TOP - T, 240)
    kit.lamp(b, 720, -200, FACADE_TOP - T, 240)
    b.prop("furniture/table", 704, -224, GROUND, 90)
    b.prop("furniture/simplechair", 704, -176, GROUND, 270)
    b.prop("static/bunkershelves", 852, -300, GROUND, 180)
    kit.beams(b, hall, "x", 96, BEAM, size=12, drop=12)

    # --- house A (north-west block) -----------------------------------------------
    house = cv.room(-864, 480, GROUND, -128, 800, STOREY, floor=FLOOR_PLANK, ceiling=CEILING,
                    walls=[(GROUND, INT_WAINSCOT), (48, INT_WALL)], name="house_a")
    cv.room(-608, 448, GROUND, -512, 480, 128, floor=STONE, walls=STONE, ceiling=BEAM, name="house_door_s")
    cv.room(-896, 624, GROUND, -864, 720, 128, floor=STONE, walls=STONE, ceiling=BEAM, name="house_door_w")
    cv.room(-128, 560, GROUND, -96, 656, 128, floor=STONE, walls=STONE, ceiling=BEAM, name="house_door_e")
    kit.beams(b, house, "y", 128, BEAM)
    kit.lamp(b, -672, 640, STOREY, 240)
    kit.lamp(b, -320, 640, STOREY, 240)
    b.prop("static/winecasks", -820, 740, GROUND, 180)
    b.prop("static/winecasks", -760, 740, GROUND, 180)
    b.prop("furniture/table", -400, 700, GROUND)

    # --- warehouse (south-west block) ---------------------------------------------
    ware = cv.room(-864, -800, GROUND, 224, -480, 288, floor=CONC, ceiling=BEAM,
                   walls=[(GROUND, CONC), (96, WARE_WALL)], name="warehouse")
    cv.room(-320, -480, GROUND, -160, -448, 144, floor=CONC, walls=STONE, ceiling=BEAM, name="ware_door_n")
    cv.room(224, -704, GROUND, 256, -576, 144, floor=CONC, walls=STONE, ceiling=BEAM, name="ware_door_e")
    cv.room(-896, -704, GROUND, -864, -576, 144, floor=CONC, walls=STONE, ceiling=BEAM, name="ware_door_w")
    kit.beams(b, ware, "y", 192, BEAM, size=16, drop=16)
    for x, y, yaw in ((-736, -720, 0), (-690, -720, 0), (-713, -720, 90), (-448, -560, 30), (-160, -740, 0),
                      (64, -560, 90), (110, -560, 90)):
        b.prop("static/indycrate", x, y, GROUND, yaw)
    b.prop("static/indycrate", -713, -720, 47, 15)
    b.prop("static/indycrate", 87, -560, 47, 80)
    for x, y in ((-560, -770), (-300, -770)):
        b.prop("static/winecasks", x, y, GROUND, 90)
    for x in (-576, -128):
        kit.lamp(b, x, -640, 288, 320)

    # --- facades: windows, doors, base and string courses ---------------------------
    storeys = ((64, 144), (208, 288))
    decorate(b, cv, sq, "north", -640, 640, storeys, skip=[(-608, -512), (-96, 96)])
    decorate(b, cv, sq, "south", -640, 640, storeys, skip=[(-320, -160), (256, 448)])
    decorate(b, cv, sq, "west", -448, 448, storeys, skip=[(-64, 64)])
    decorate(b, cv, sq, "east", -448, 448, ((64, 144),), skip=[(-352, 352)])
    decorate(b, cv, ns, "south", -1152, 1152, storeys, skip=[(-896, -864), (-96, 96), (896, 1152), (-1152, -896)])
    decorate(b, cv, ns, "north", -1152, 1152, storeys, skip=[], doors=(-864, -96, 672))
    decorate(b, cv, ss, "north", -1152, 1152, ((208, 288),), skip=[(-896, 256), (256, 448), (896, 1152), (-1152, -896)])
    decorate(b, cv, ss, "south", -1152, 1152, storeys, skip=[], doors=(-672, 96, 864))
    decorate(b, cv, ws, "east", -832, 832, storeys, skip=[(-704, -576), (-64, 64), (624, 720)])
    decorate(b, cv, ws, "west", -832, 832, storeys, skip=[], doors=(-480, 288))
    decorate(b, cv, es, "west", -832, 832, storeys, skip=[(-352, 352)])
    decorate(b, cv, es, "east", -832, 832, storeys, skip=[], doors=(-288, 480))
    decorate(b, cv, nl, "east", 448, 832, storeys, skip=[])
    decorate(b, cv, sl, "west", -832, -448, storeys, skip=[(-704, -576)])
    decorate(b, cv, sl, "east", -832, -448, storeys, skip=[])

    # --- roofs over the building masses ----------------------------------------------
    for (x0, y0, x1, y1, axis, m) in (
        (-896, 448, -96, 832, "x", ROOF_RED), (96, 448, 896, 832, "x", ROOF_RUSTIC),
        (-896, -832, 256, -448, "x", ROOF_RUSTIC), (448, -832, 896, -448, "x", ROOF_RED),
        (640, -448, 896, 448, "y", ROOF_RED), (-896, -448, -640, 448, "y", ROOF_RUSTIC),
        (-1408, -1344, 1408, -1088, "x", ROOF_RED), (-1408, 1088, 1408, 1344, "x", ROOF_RUSTIC),
        (-1408, -1088, -1152, 1088, "y", ROOF_RED), (1152, -1088, 1408, 1088, "y", ROOF_RUSTIC),
    ):
        kit.gable_roof(b, x0, y0, x1, y1, FACADE_TOP, 96 if min(x1 - x0, y1 - y0) >= 384 else 64, axis,
                       m if axis == "x" else m(rotate=90), PLASTER_OLD, overhang=16)

    # --- square: fountain, cover, lamps -------------------------------------------
    kit.fountain(b, 0, 0, GROUND, STONE)
    b.prop("static/produce_cart", -400, 250, GROUND, 200)
    b.prop("static/indycrate", 380, -240, GROUND, 10)
    b.prop("static/nazi_crate", 380, -200, 47, 80)
    b.prop("static/sandbag_large_semicircle", 470, 300, GROUND, 225)
    b.prop("static/sandbag_large_semicircle", -470, -300, GROUND, 45)
    b.prop("static/winecasks", -600, -380, GROUND, 45)
    b.prop("static/wagon", 1024, -500, GROUND, 0)
    b.prop("static/produce_cart", -1030, 300, GROUND, 90)
    b.prop("static/indycrate", 700, 960, GROUND, 0)
    b.prop("static/indycrate", -350, -960, GROUND, 25)
    for x, y in ((-590, 400), (590, -400), (-1100, -780), (1100, 780), (-120, 1040)):
        b.prop("static/bush_full", x, y, GROUND, (x * 7 + y) % 360, 0.6)
    b.box((-160, 256, GROUND), (-96, 288, 40), STONE)  # low walls
    b.box((96, -288, GROUND), (160, -256, 40), STONE)

    # --- lights over the streets (warm wall lamps) ----------------------------------
    for x, y, wall in ((-1152, -416, "west"), (-1152, 416, "west"), (1152, 0, "east"), (0, 1088, "north"),
                       (-640, -1088, "south"), (640, 1088, "north"), (-640, 256, "west"), (640, -256, "east"),
                       (-256, 448, "north"), (256, -448, "south"), (1152, -600, "east"), (-1152, 700, "west")):
        kit.wall_lantern(b, x, y, 176, wall, 180)

    # --- spawns ------------------------------------------------------------------------------
    spawns = [
        (-1024, 640, 270), (-1024, -640, 90), (1024, 640, 270), (1024, -740, 90), (-800, 960, 0),
        (800, 960, 180), (-800, -960, 0), (800, -960, 180), (0, 960, 270), (352, -960, 90),
        (-250, -120, 45), (250, 120, 225), (-448, 320, 315), (448, -320, 135), (768, -256, 90),
        (704, 256, 270), (-704, 560, 0), (-256, 720, 180), (-700, -640, 0), (80, -700, 180),
        (-768, 0, 0), (0, 640, 270), (352, -640, 90), (1024, 0, 180),
    ]
    for i, (x, y, yaw) in enumerate(spawns):
        b.spawn((x, y, GROUND + 1), yaw, kinds=("deathmatch",))
        b.spawn((x, y, GROUND + 1), yaw, kinds=("allied",) if (x + y) < 0 else ("axis",))
    b.entity("info_player_start", (0, -300, 1), angle="90")
    b.entity("info_player_intermission", (0, -380, 260), angles="20 90 0")
    return b


def decorate(b, cv, air, side, u0, u1, storeys, skip, doors=()):
    """Windows with shutters in 192-unit bays, doors in some bays, a moulding at the first floor."""
    kit.facade(b, cv, air, side, u0, u1, storeys, skip, window_image=WIN[0], window_px=WIN[1], reveal=STONE,
               shutters=BEAM, moulding=MOLDING, moulding_z=STOREY, doors=doors,
               door_image=DOOR_B[0] if len(doors) % 2 else DOOR[0])


SHOTS = [
    Shot.looking_at("square_from_south", (0, -420, 90), (0, 200, 120)),
    Shot.looking_at("square_from_ne", (600, 420, 150), (-300, -200, 60)),
    Shot.looking_at("north_street", (-1100, 960, 90), (1000, 960, 120)),
    Shot.looking_at("west_street", (-1024, -800, 90), (-1024, 800, 120)),
    Shot.looking_at("town_hall_inside", (700, -330, 90), (820, 300, 60)),
    Shot.looking_at("hall_upper", (700, -320, 260), (800, 300, 220)),
    Shot.looking_at("warehouse", (-840, -780, 120), (200, -500, 40)),
    Shot.looking_at("house_a", (-840, 500, 90), (-150, 780, 60)),
    Shot.looking_at("overview", (-600, -700, 700), (300, 300, 0)),
]
