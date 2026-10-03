"""Test room for spotlights (docs/testing.md "Test rooms"): one spotlight aimed down at the floor
of a closed room: which way do MOHlight's lightmaps and light grid light it? ``SPOT=target``
(default), ``angles`` or ``point`` picks the light."""
from mohkit.build import Carver, MapBuilder, Material
from mohkit.game import Shot

META = {"name": "spottest", "title": "Spot Test", "mode": "dm"}
SHOTS = [Shot("down", (-200, 0, 256), (45, 0, 0)), Shot("up", (-200, 0, 256), (-45, 0, 0))]


def build():
    b = MapBuilder("Spot Test", ambientlight="2 2 2")
    cv = Carver(16)
    b.carve(cv)
    m = Material("mohtest/brickstreet1")
    cv.room(-256, -256, 0, 256, 256, 512, floor=m, walls=m, ceiling=m, name="room")
    b.spawn((-200, 0, 1), 0)
    import os
    kind = os.environ.get("SPOT", "target")
    if kind == "target":
        b.entity("info_null", (0, 0, 0), targetname="spotdown")
        b.light((0, 0, 256), 500, target="spotdown", spot_angle="60")
    elif kind == "angles":
        b.light((0, 0, 256), 500, angles="90 0 0", spot_angle="60", radius="150")
    else:
        b.light((0, 0, 256), 500)
    return b
