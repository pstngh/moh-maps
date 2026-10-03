"""Test room for ladders (docs/testing.md "Test rooms"): a 160-high ledge with three CS-style
step columns (``kit.step_ladder``: 16 x 1, 8 x 1 and 8 x 2 unit steps) and a MOHAA
``func_ladder`` (``kit.ladder``) climbing onto it."""
from mohkit import kit
from mohkit.build import Carver, MapBuilder, Material
from mohkit.game import Shot

META = {"name": "laddertest", "title": "Ladder Test", "mode": "dm"}
SHOTS = [Shot("view", (-300, 0, 60), (-10, 0, 0)), Shot("ladder", (-200, -200, 60), (-10, -30, 0))]
WALL = Material("algiers/fort_floor_cobbleflttile")
# step columns: (rise, depth, y); the func_ladder at y = -260
STEPS = ((16, 1, -160), (8, 1, 0), (8, 2, 160))
LADDER_Y = -260


def build():
    b = MapBuilder("Ladder Test", ambientlight="40 40 40", suncolor="70 70 70", sundirection="315 210 0")
    cv = Carver(16)
    b.carve(cv)
    cv.room(-512, -320, 0, 256, 320, 384, floor=Material("mohtest/brickstreet1"),
            walls=WALL, ceiling=Material("mohtest/flrwood1_rep"), name="room")
    b.box((0, -320, 0), (256, 320, 160), WALL)      # the ledge: its face at x = 0, top at z = 160
    b.spawn((-300, 0, 1), 0)
    for rise, depth, y in STEPS:
        kit.step_ladder(b, "east", 0, y - 20, y + 20, 0, 160, rise, depth)
    kit.ladder(b, "east", 0, LADDER_Y, 0, 160, rails=kit.STEEL_H)
    b.light((-200, 0, 300), 400)
    return b
