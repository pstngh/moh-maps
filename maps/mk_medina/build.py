"""mk_medina: TODO one-line description.

Layout: TODO (describe the spaces and routes).
"""

from mohkit import kit
from mohkit.build import Carver, MapBuilder, Material as M
from mohkit.game import Shot

META = {"name": "mk_medina", "title": "Medina", "mode": "dm", "ambience": "mohdm2"}

FLOOR = M("central_europe/small_cobble")
PLASTER = M("general_structure/plaster_wall2")
STONE = M("general_structure/stonebricks1", (0.5, 0.5))
WOOD = M("general_structure/floor4")
CEIL = M("general_structure/plank_flat")


def build():
    b = MapBuilder("Medina", suncolor="70 66 58", sundirection="315 210 0", sundiffuse="1.2",
                   sundiffusecolor="56 62 78", ambientlight="10 10 12", farplane="6000",
                   farplane_color="0.62 0.66 0.72", farplane_cull="0")
    cv = Carver(16, sky_shader="sky/mohday2")
    b.carve(cv)
    yard = cv.room(-768, -768, 0, 768, 768, 320, floor=FLOOR, walls=[(0, STONE), (32, PLASTER)], sky=True)
    hall = cv.room(800, -256, 0, 1408, 256, 176, floor=WOOD, walls=PLASTER, ceiling=CEIL)
    cv.room(768, -64, 0, 800, 64, 128, floor=STONE, walls=STONE, ceiling=STONE)       # doorway
    kit.facade(b, cv, yard, "north", -768, 768, ((64, 144), (208, 288)), shutters=M("general_structure/beam_wood1"))
    kit.lamp(b, 1104, 0, 176)
    b.prop("static/winecasks", 1360, 200, 0, 180)
    b.prop("static/indycrate", -200, 100, 0, 20)
    spawns = [(-600, -600, 45), (600, 600, 225), (-600, 600, 315), (600, -600, 135), (0, -500, 90),
              (0, 500, 270), (1300, -180, 180), (900, 180, 0)]
    for i, (x, y, yaw) in enumerate(spawns):
        b.spawn((x, y, 1), yaw, kinds=("deathmatch", "allied" if i % 2 else "axis"))
    b.entity("info_player_start", (0, 0, 1), angle="0")
    return b


SHOTS = [
    Shot.looking_at("yard", (-700, -700, 80), (400, 400, 60)),
    Shot.looking_at("hall", (840, -220, 80), (1380, 220, 40)),
    Shot.looking_at("overview", (-900, -900, 900), (300, 0, 0)),
]
