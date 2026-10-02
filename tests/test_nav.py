"""Source nav meshes (mohkit.source.nav): reading and spread free-for-all spawns."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from mohkit.source import nav as N


def _area(aid, lo, hi, z=0.0, links=(), flags=0, place=0) -> bytes:
    b = struct.pack("<II3f3fff", aid, flags, lo[0], lo[1], z, hi[0], hi[1], z, z, z)
    # all links in the first direction; the reader merges the four
    b += struct.pack("<I", len(links)) + struct.pack(f"<{len(links)}I", *links) + struct.pack("<III", 0, 0, 0)
    b += struct.pack("<B", 0)                     # hiding spots
    b += struct.pack("<I", 0)                     # encounter paths
    b += struct.pack("<H", place)
    b += struct.pack("<II", 0, 0)                 # ladders
    b += struct.pack("<2f4f", 0, 0, 1, 1, 1, 1)
    b += struct.pack("<I", 0) + struct.pack("<I", 0) + struct.pack("<B", 1) + b"\0" * 14
    return b


def _mesh(areas: list[bytes], places=("Hall",)) -> bytes:
    b = struct.pack("<IIIIB", N.MAGIC, 16, 1, 123, 1)
    b += struct.pack("<H", len(places))
    for p in places:
        raw = p.encode() + b"\0"
        b += struct.pack("<H", len(raw)) + raw
    b += struct.pack("<B", 0) + struct.pack("<I", len(areas)) + b"".join(areas)
    return b + struct.pack("<I", 0)               # no ladders


def _grid(nx, ny, size=128.0):
    """A walkable nx x ny grid of square areas, 4-connected."""
    out = []
    for j in range(ny):
        for i in range(nx):
            aid = 1 + j * nx + i
            links = [1 + jj * nx + ii for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                     if 0 <= ii < nx and 0 <= jj < ny]
            out.append(_area(aid, (i * size, j * size), ((i + 1) * size, (j + 1) * size), links=links, place=1))
    return out


def test_read():
    m = N.read_nav(_mesh(_grid(3, 2)))
    assert len(m.areas) == 6 and m.places == ["Hall"]
    a = m.areas[4]
    assert a.id == 5 and a.lo == (128.0, 128.0) and a.hi == (256.0, 256.0) and a.place == "Hall"
    assert sorted(a.links) == [2, 4, 6]
    assert abs(a.height(150, 200)) < 1e-6


def test_spread():
    m = N.read_nav(_mesh(_grid(12, 12)))
    spots = N.ffa_spawns(m, 8)
    assert len(spots) == 8
    p = np.array([s[0][:2] for s in spots])
    d = np.linalg.norm(p[:, None] - p[None], axis=2) + np.eye(len(p)) * 1e9
    assert d.min() >= 384, d.min()               # 8 spots over 1536^2 sit far apart
    # the first one is in a corner (farthest from the middle), facing into the room
    (x, y, _), yaw = spots[0]
    to_mid = np.degrees(np.arctan2(768 - y, 768 - x)) % 360
    assert min(abs(yaw - to_mid), 360 - abs(yaw - to_mid)) <= 50, (yaw, to_mid)


def test_flags_and_keep():
    areas = _grid(6, 1)
    # a crouch area and a tiny area are never spawn spots
    areas[0] = _area(1, (0, 0), (128, 128), links=[2], flags=N.CROUCH, place=1)
    areas[5] = _area(6, (640, 0), (680, 40), links=[5], place=1)
    m = N.read_nav(_mesh(areas))
    cand = N.spawn_candidates(m)
    assert 0 not in cand and 5 not in cand and len(cand) == 4
    spots = N.ffa_spawns(m, 3, keep=[(200.0, 64.0, 0.0)])
    assert spots[0][0] == (200.0, 64.0, 0.0) and spots[0][1] is None
    xs = sorted(s[0][0] for s in spots[1:])
    assert xs[-1] >= 576 - 1                      # the far end is filled first


def test_csgo_nav():
    path = Path.home() / "Documents/Games/csgo/csgo/maps/de_nuke.nav"
    if not path.is_file():
        print("skip: no de_nuke.nav")
        return
    m = N.load(path)
    assert len(m.areas) > 1000 and "BombsiteA" in m.places
    n = N.spawn_count(m)
    assert 24 <= n <= 48
    spots = N.ffa_spawns(m, n)
    assert len(spots) == n
    places = {m.areas[int(np.argmin([np.linalg.norm(np.subtract(a.centre[:2], s[0][:2])) for a in m.areas]))].place
              for s in spots}
    assert len(places) >= 10, places             # all over the map, not two clusters


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
