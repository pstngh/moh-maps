"""Source navigation meshes (``maps/<map>.nav``) and free-for-all spawn spots from them.

CS:GO ships a bot nav mesh beside most maps; only a few maps (de_inferno, de_cache) have
``info_deathmatch_spawn`` entities. MOHAA free-for-all wants deathmatch spawns spread over
the whole map, not the T and CT clusters at its two ends, so ``ffa_spawns`` picks them from
the nav mesh: walkable areas big and flat enough to stand in, spread by walking distance.

File layout (``CNavMesh::Load``/``CNavArea::Load``, version 16 as CS:GO writes it; checked by
reading de_nuke.nav to its last byte): magic ``0xFEEDFACE``, version, subversion, BSP size,
``isAnalyzed`` (u8), place names (u16 count, each a u16 length and that many bytes with the
NUL), ``hasUnnamedAreas`` (u8), then u32 area count and per area:

* id (u32), attribute flags (u32), north-west and south-east corners (3 floats each), the
  north-east and south-west corner heights (floats);
* connections: 4 directions (north, east, south, west), each a u32 count and area ids;
* hiding spots: u8 count, each id (u32), position (3 floats), flags (u8);
* encounter paths: u32 count, each from-area (u32), from-direction (u8), to-area (u32),
  to-direction (u8), u8 spot count and per spot an area id (u32) and a u8 position;
* place index (u16, 1-based into the names; 0 none), ladders up and down (u32 count + ids
  each), two earliest-occupy times and four light intensities (floats);
* visible areas (u32 count, each id u32 + u8 flags; CS:GO ships 0), the area it inherits
  visibility from (u32), and a u8 count of 14-byte CS:GO records (skipped).

Then the ladders (u32 count, 60 bytes each), unused here.
"""

from __future__ import annotations

import heapq
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

MAGIC = 0xFEEDFACE

# attribute flags (nav_mesh.h NavAttributeType)
CROUCH, JUMP, PRECISE, NO_JUMP, STOP, RUN, WALK, AVOID = 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80
TRANSIENT, DONT_HIDE, STAND, NO_HOSTAGES, STAIRS = 0x100, 0x200, 0x400, 0x800, 0x1000
NO_MERGE, OBSTACLE_TOP, CLIFF = 0x2000, 0x4000, 0x8000
# areas nobody should spawn in: crouch-only, jump spots, ledges, stairs, prop tops, cliffs
NO_SPAWN = CROUCH | JUMP | PRECISE | AVOID | TRANSIENT | STAIRS | OBSTACLE_TOP | CLIFF


@dataclass
class NavArea:
    id: int
    flags: int
    lo: tuple[float, float]           # x, y of the north-west corner (the smaller x and y)
    hi: tuple[float, float]           # x, y of the south-east corner
    z: tuple[float, float, float, float]   # corner heights: nw, ne, se, sw
    links: list[int] = field(default_factory=list)   # areas you can walk to (all four directions)
    place: str = ""

    @property
    def size(self) -> tuple[float, float]:
        return self.hi[0] - self.lo[0], self.hi[1] - self.lo[1]

    @property
    def centre(self) -> tuple[float, float, float]:
        return ((self.lo[0] + self.hi[0]) / 2, (self.lo[1] + self.hi[1]) / 2, sum(self.z) / 4)

    def height(self, x: float, y: float) -> float:
        """Floor height at (x, y), bilinear over the four corners."""
        w, h = self.size
        u = (x - self.lo[0]) / w if w else 0.5
        v = (y - self.lo[1]) / h if h else 0.5
        nw, ne, se, sw = self.z
        return (nw * (1 - u) + ne * u) * (1 - v) + (sw * (1 - u) + se * u) * v


@dataclass
class NavMesh:
    version: int
    areas: list[NavArea]
    places: list[str]


def read_nav(data: bytes) -> NavMesh:
    o = 0

    def take(fmt: str):
        nonlocal o
        v = struct.unpack_from("<" + fmt, data, o)
        o += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]

    magic, version = take("I"), take("I")
    if magic != MAGIC:
        raise ValueError("not a nav mesh")
    if version < 16:
        raise ValueError(f"nav version {version} (only CS:GO's 16 is read)")
    take("I")          # subversion
    take("I")          # BSP size the mesh was built for
    take("B")          # analyzed
    places = []
    for _ in range(take("H")):
        n = take("H")
        places.append(data[o:o + n].rstrip(b"\0").decode("latin-1"))
        o += n
    take("B")          # has unnamed areas
    areas = []
    for _ in range(take("I")):
        aid, flags = take("I"), take("I")
        nw, se = take("3f"), take("3f")
        ne_z, sw_z = take("f"), take("f")
        links = []
        for _d in range(4):
            n = take("I")
            links += list(struct.unpack_from(f"<{n}I", data, o))
            o += 4 * n
        # (each count is read before ``o`` moves past what it counts: ``o += take()`` would
        # add to the old ``o``)
        n = take("B")
        o += 17 * n                            # hiding spots
        for _e in range(take("I")):            # encounter paths
            o += 10
            n = take("B")
            o += 5 * n
        place = take("H")
        for _l in range(2):                    # ladders up, down
            n = take("I")
            o += 4 * n
        o += 8 + 16                            # occupy times, light intensities
        n = take("I")
        o += 5 * n + 4                         # visible areas, inherit visibility from
        n = take("B")
        o += 14 * n
        areas.append(NavArea(aid, flags, (nw[0], nw[1]), (se[0], se[1]), (nw[2], ne_z, se[2], sw_z), links,
                             places[place - 1] if 0 < place <= len(places) else ""))
    return NavMesh(version, areas, places)


def load(path) -> Optional[NavMesh]:
    p = Path(path)
    return read_nav(p.read_bytes()) if p.is_file() else None


def _walk_graph(areas: Sequence[NavArea]) -> tuple[dict, list[np.ndarray]]:
    index = {a.id: i for i, a in enumerate(areas)}
    centres = np.array([a.centre for a in areas], np.float64)
    adj: list[list[tuple[int, float]]] = [[] for _ in areas]
    for i, a in enumerate(areas):
        for t in a.links:
            j = index.get(t)
            if j is not None and j != i:
                adj[i].append((j, float(np.linalg.norm(centres[i] - centres[j]))))
    return index, adj


def _dijkstra(adj, sources: Sequence[int], n: int) -> np.ndarray:
    dist = np.full(n, np.inf)
    heap = []
    for s in sources:
        dist[s] = 0.0
        heap.append((0.0, s))
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i]:
            continue
        for j, w in adj[i]:
            nd = d + w
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(heap, (nd, j))
    return dist


def spawn_candidates(mesh: NavMesh, min_size: float = 56.0, max_slope: float = 10.0) -> list[int]:
    """Indexes of areas a player can spawn in: no ``NO_SPAWN`` flag, both sides at least
    ``min_size`` (a 32-unit player plus margin), corners within ``max_slope`` in height,
    and in the largest walk-connected part of the mesh."""
    areas = mesh.areas
    _, adj = _walk_graph(areas)
    # largest connected component (links are one-way; treat them as two-way for this)
    und: list[set] = [set() for _ in areas]
    for i, nb in enumerate(adj):
        for j, _w in nb:
            und[i].add(j)
            und[j].add(i)
    comp = [-1] * len(areas)
    sizes = []
    for s in range(len(areas)):
        if comp[s] >= 0:
            continue
        stack, comp[s], n = [s], len(sizes), 0
        while stack:
            i = stack.pop()
            n += 1
            for j in und[i]:
                if comp[j] < 0:
                    comp[j] = comp[s]
                    stack.append(j)
        sizes.append(n)
    main = int(np.argmax(sizes)) if sizes else -1
    out = []
    for i, a in enumerate(areas):
        w, h = a.size
        if (comp[i] == main and not a.flags & NO_SPAWN and min(w, h) >= min_size
                and max(a.z) - min(a.z) <= max_slope):
            out.append(i)
    return out


def walkable_area(mesh: NavMesh) -> float:
    """Floor area (square units) of the mesh's areas, flags ignored."""
    return float(sum(a.size[0] * a.size[1] for a in mesh.areas))


def _open_yaw(mesh: NavMesh, p: tuple[float, float, float], step: float = 16.0, reach: float = 2048.0,
              directions: int = 16) -> float:
    """The yaw (degrees) with the longest walk from ``p`` along a straight line on the mesh,
    smoothed over neighbouring directions so a spawn faces an opening, not a slot."""
    lo = np.array([a.lo for a in mesh.areas])
    hi = np.array([a.hi for a in mesh.areas])
    zs = np.array([a.z for a in mesh.areas])
    zmin, zmax = zs.min(1), zs.max(1)
    runs = []
    for k in range(directions):
        yaw = 360.0 * k / directions
        dx, dy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        z, d = p[2], 0.0
        while d < reach:
            x, y = p[0] + dx * (d + step), p[1] + dy * (d + step)
            inside = ((lo[:, 0] - 1 <= x) & (x <= hi[:, 0] + 1) & (lo[:, 1] - 1 <= y) & (y <= hi[:, 1] + 1)
                      & (zmin - 48 <= z) & (z <= zmax + 20))
            if not inside.any():
                break
            cand = np.nonzero(inside)[0]
            hz = [mesh.areas[i].height(x, y) for i in cand]
            best = min(range(len(cand)), key=lambda c: abs(hz[c] - z))
            if hz[best] - z > 20:          # a step up a player can't take
                break
            z, d = hz[best], d + step
        runs.append(d)
    r = np.array(runs)
    smooth = r + 0.5 * (np.roll(r, 1) + np.roll(r, -1))
    return 360.0 * int(np.argmax(smooth)) / directions


def ffa_spawns(mesh: NavMesh, count: int, keep: Sequence[tuple[float, float, float]] = ()) -> list[tuple]:
    """``count`` spawn spots ``((x, y, z), yaw)`` spread over ``mesh`` in Source units, z on
    the floor. Farthest-point sampling by walking distance over the area graph: each new
    spot is the candidate area centre farthest (on foot) from every spot so far. ``keep``
    (positions such as the map's own deathmatch spawns) are taken first, in order, and the
    rest fill the gaps between them."""
    areas = mesh.areas
    cand = spawn_candidates(mesh)
    if not cand:
        return []
    _, adj = _walk_graph(areas)
    n = len(areas)
    centres = np.array([a.centre for a in areas], np.float64)

    def nearest_area(p) -> int:
        d = np.linalg.norm(centres - np.asarray(p, np.float64), axis=1)
        return int(np.argmin(d))

    chosen: list[int] = []
    out: list[tuple] = []
    dist = np.full(n, np.inf)
    for p in keep:
        if len(out) >= count:
            break
        i = nearest_area(p)
        dist = np.minimum(dist, _dijkstra(adj, [i], n))
        out.append((tuple(float(v) for v in p), None))
    cand_arr = np.array(cand)
    if not out:
        # start from the candidate farthest (on foot) from the mesh's middle
        mid = nearest_area(centres[cand_arr].mean(axis=0))
        d0 = _dijkstra(adj, [mid], n)[cand_arr]
        d0[~np.isfinite(d0)] = -1
        first = int(cand_arr[int(np.argmax(d0))])
        chosen.append(first)
        dist = np.minimum(dist, _dijkstra(adj, [first], n))
    while len(out) + len(chosen) < count:
        d = dist[cand_arr]
        d = np.where(np.isfinite(d), d, -1.0)
        k = int(np.argmax(d))
        if d[k] <= 0:
            break
        i = int(cand_arr[k])
        chosen.append(i)
        dist = np.minimum(dist, _dijkstra(adj, [i], n))
    for i in chosen:
        c = areas[i].centre
        p = (c[0], c[1], areas[i].height(c[0], c[1]))
        out.append((p, _open_yaw(mesh, p)))
    return out


def spawn_count(mesh: NavMesh, per: float = 640.0 * 640.0, lo: int = 24, hi: int = 48) -> int:
    """How many free-for-all spawns a map gets: one per ``per`` square units of walkable
    floor, within ``lo`` .. ``hi``."""
    return int(min(hi, max(lo, round(walkable_area(mesh) / per))))
