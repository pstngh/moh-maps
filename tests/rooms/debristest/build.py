"""Test room for breakables (docs/testing.md "Test rooms"): two ``func_window``s
(``kit.breakable``), metal and wood debris; shoot them to see the debris."""
from mohkit import kit
from mohkit.build import Carver, MapBuilder, Material
from mohkit.game import Shot

META = {"name": "debristest", "title": "Debris Test", "mode": "dm"}
SHOTS = [Shot("view", (-200, 0, 60), (0, 0, 0))]


def build():
    b = MapBuilder("Debris Test", ambientlight="40 40 40", suncolor="70 70 70", sundirection="315 210 0")
    cv = Carver(16)
    b.carve(cv)
    cv.room(-320, -192, 0, 256, 192, 192, floor=Material("mohtest/brickstreet1"),
            walls=Material("algiers/fort_floor_cobbleflttile"), ceiling=Material("mohtest/flrwood1_rep"), name="room")
    b.spawn((-200, 0, 1), 0)
    for kind, y, m in (("metal", -64, "general_industrial/bnkrpipe1_iron"), ("wood", 64, "mohtest/flrwood1_rep")):
        kit.breakable(b, (0, y - 32, 24), (8, y + 32, 104), m, kind)
    b.light((-100, 0, 160), 250)
    return b
