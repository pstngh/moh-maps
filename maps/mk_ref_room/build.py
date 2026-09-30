"""mk_ref_room: a stone room recreated from one screenshot (docs/from-reference.md).

The reference is a 1280x720 OpenMoHAA screenshot of a room in stock mohdm1 (camera
"c8"). Only the picture was used: no geometry or texture names from mohdm1.map.

Measurements from the picture (fov 80 at 16:9 -> focal length f = 572 px, eye 82
units above the floor, looking along +x, so image left is +y):

* floor line of the back wall at y = 530 px -> back wall at x = 572 * 82 / 170 = 276;
* back wall corners at x = 170 and 800 px -> left wall y = +227, right wall y = -77;
* door 388..556 x 263..530 px -> 80 wide, 128 tall, centred at y = +81;
* ceiling planks meet the beam's front edge at y = 95 px -> ceiling at z = 182; the
  beam along the back wall is 60 deep with its underside at z = 150; a nearer beam's
  face ends at y = 62 px and its underside at 97 px -> x = 130..148;
* the window's far jamb spans 990..1060 px on the right wall -> far edge x = 126,
  wall thickness 16; sill z = 30, head z = 147;
* bulb at (182, 137, 157), sconce on the left wall at x = 211, z = 106, a small
  cabinet at the left edge near (167, 183).

Materials were picked with ``mohkit looks-like`` / ``mohkit swatches``.
"""

from mohkit import kit
from mohkit.build import Air, Carver, MapBuilder, Material, aabb
from mohkit.game import Shot

META = {"name": "mk_ref_room", "title": "Reference Room", "mode": "dm"}

M = Material
WALL = M("algiers/fort_floor_cobbleflttile", (0.375, 0.375))
FLOOR = M("mohtest/brickstreet1", (0.5, 0.5))
CEILING = M("mohtest/flrwood1_rep")
BEAM = M("general_structure/beam_wood1", (0.5, 0.5))
BARS = M("general_industrial/bnkrpipe1_iron", (0.25, 0.25))
YARD_WALL = M("algiers/fort_floor_cobbleflttile", (0.5, 0.5))
YARD_GROUND = M("algiers/pierset_3ptty")
DOOR = ("central_europe/frenchdoor_wood1", (128, 256))

T = 16
X0, X1, Y0, Y1, Z1 = -96, 276, -77, 227, 182
WIN_X0, WIN_X1, WIN_Z0, WIN_Z1 = 46, 126, 30, 147


def build():
    b = MapBuilder(
        "Reference Room",
        ambientlight="15 13 11",
        suncolor="96 84 64",
        sundirection="305 300 0",  # 55 deg up, SSE: lights the yard, its patch through the window stays out of view
        sundiffuse="1.0",
        sundiffusecolor="52 56 64",
        lightmapdensity="16",
    )
    cv = Carver(T, sky_shader="sky/mohday2")
    b.carve(cv)

    room = cv.room(X0, Y0, 0, X1, Y1, Z1, floor=FLOOR, walls=WALL, ceiling=CEILING, name="room")
    # window: a real opening through the right (south) wall onto a courtyard
    cv.add(Air(aabb(WIN_X0, Y0 - T, WIN_Z0, WIN_X1, Y0, WIN_Z1), floor=BEAM, ceiling=BEAM, walls=BEAM,
               name="window"))
    cv.room(-1024, -2048, 0, 2048, Y0 - T, 640, floor=YARD_GROUND, walls=YARD_WALL, sky=True, name="yard")

    # iron bars in the middle of the wall thickness
    ym = Y0 - T / 2
    for x in range(WIN_X0 + 20, WIN_X1, 20):
        b.box((x - 1, ym - 1, WIN_Z0), (x + 1, ym + 1, WIN_Z1), BARS)
    for z in range(WIN_Z0 + 30, WIN_Z1, 30):
        b.box((WIN_X0, ym - 1, z - 1), (WIN_X1, ym + 1, z + 1), BARS)

    kit.door(cv, room, "east", 81, 0, 80, 128, DOOR[0], DOOR[1], reveal=BEAM)
    for y0, y1, z0, z1 in ((35, 41, 0, 134), (121, 127, 0, 134), (35, 127, 128, 134)):  # door frame
        b.box((X1 - 2, y0, z0), (X1, y1, z1), BEAM)
    b.box((X1 - 60, Y0, 150), (X1, Y1, Z1), BEAM)  # beam along the back wall
    b.box((130, Y0, 150), (148, Y1, Z1), BEAM)       # nearer beam: face ends at y = 62 px

    b.prop("static/lightbulb_on_wire_short.tik", 182, 137, Z1, hang=True)
    b.light((182, 137, 150), 220, (1.0, 0.84, 0.6))
    # the room continues behind the camera: a second bulb lights the near beam's face
    b.prop("static/lightbulb_on_wire_short.tik", -48, 60, Z1, hang=True)
    b.light((-48, 60, 150), 170, (1.0, 0.84, 0.6))
    b.prop("lights/wallsconce-single.tik", 211, Y1 - 6, 100, yaw=270)
    b.light((211, Y1 - 16, 108), 100, (1.0, 0.8, 0.55))
    b.prop("static/cabinet_small.tik", 180, 205, 0, yaw=270)
    b.prop("static/tree_commontree.tik", 500, -420, 0)   # seen through the window
    b.prop("static/tree_commontree.tik", 1100, -1300, 0, yaw=60)

    b.spawn((-40, 100, 1), 0)
    b.spawn((-40, -20, 1), 0, kinds=("deathmatch",))
    return b


SHOTS = [
    Shot("reference", (0, 0, 82), (0, 0, 0)),
    Shot.looking_at("room_back", (240, 180, 90), (-60, -40, 80)),
    Shot.looking_at("yard", (80, -300, 90), (80, 0, 90)),
]
