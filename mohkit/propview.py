"""Render stock props in a test room to learn their look, size, pivot and facing.

Each prop stands on a grey floor next to a red arrow pointing +X (yaw 0) and a
64-unit white ruler; two cameras per prop (front 3/4 and side). One compile for
the whole batch.

    python -m mohkit.propview static/wagon static/produce_cart lights/hanglamp
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from . import compile as C
from . import config, game, props
from .build import Carver, MapBuilder, Material
from .project import write_pk3

FLOOR = Material("general_structure/jh_conc512a")
WALL = Material("general_structure/plaster_wall2")
ARROW = Material("general_structure/handrail1c")  # plain dark red
RULER = Material("general_structure/plaster_wall2", (0.25, 0.25))


def view(names: list[str], out: Path | None = None, run_name: str = "propview") -> Path | None:
    infos = [(n, props.get(n)) for n in names]
    cell = max([256] + [int(max(p.size[0], p.size[1]) * 1.6) + 96 for _, p in infos if p])
    cols = max(1, math.ceil(math.sqrt(len(infos))))
    rows = math.ceil(len(infos) / cols)
    tallest = max([128] + [int(p.maxs[2] - min(0, p.mins[2])) for _, p in infos if p])
    h = tallest + 256
    b = MapBuilder("propview", ambientlight="60 60 60", suncolor="0 0 0")
    cv = Carver(16)
    cv.room(0, 0, 0, cols * cell, rows * cell, h, floor=FLOOR, walls=WALL, ceiling=WALL)
    b.carve(cv)
    shots = []
    for i, (name, info) in enumerate(infos):
        cx, cy = (i % cols) * cell + cell / 2, (i // cols) * cell + cell / 2
        b.box((cx, cy - 4, 0), (cx + cell * 0.4, cy + 4, 2), ARROW)            # +X arrow
        b.box((cx - 64, cy - cell * 0.4, 0), (cx, cy - cell * 0.4 + 4, 4), RULER)  # 64-unit ruler
        b.static_model(name, (cx, cy, 0), 0)
        b.light((cx - cell * 0.3, cy - cell * 0.3, tallest + 96), 350)
        d = max(160, (max(info.size) if info else 128) * 1.4)
        zc = (info.maxs[2] / 2) if info else 48
        tag = name.split("/")[-1].replace(".tik", "")
        shots.append(game.Shot.looking_at(f"{tag}_front", (cx + d * 0.8, cy - d * 0.6, zc + d * 0.35), (cx, cy, zc)))
        shots.append(game.Shot.looking_at(f"{tag}_side", (cx - d * 0.1, cy + d, zc + d * 0.25), (cx, cy, zc)))
    b.spawn((8 + 32, 8 + 32, 1), 45)
    res = C.compile_map(b.to_map().dumps(), f"dm/{run_name}", quality="draft")
    if not res.ok:
        print(res.summary())
        return None
    pk3 = Path(config.load().build_dir) / f"{run_name}.pk3"
    write_pk3(pk3, {f"maps/dm/{run_name}.bsp": res.bsp.read_bytes()})
    run = game.run([pk3], f"dm/{run_name}", shots, run_name=run_name)
    out = out or Path(config.load().build_dir) / f"{run_name}.png"
    game.contact_sheet(run.screenshots, out, cols=4, thumb_w=480)
    return out


if __name__ == "__main__":
    print(view(sys.argv[1:]))
