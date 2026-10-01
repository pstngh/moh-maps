"""Static models without MOHlight: add them to a lit BSP and colour them from its light grid.

MOHlight lights static-model vertices on one thread at about 190 vertices a second
(docs/toolchain.md), so a CS:GO map with thousands of props would light for hours.
This module adds static models to a BSP **after** the light stage instead:

1. ``LightGrid`` decodes the BSP's light grid (lumps 16-18, ``docs/reference/engine.md``
   §7.5): one palette colour per 32-unit cell (v19), index 0 = inside solid.
2. Each vertex gets the grid colour trilinearly sampled a few units out along its
   normal (cells inside solid are skipped and the weights renormalised, as
   ``R_GetLightingGridValue`` does), times a facing term from the worldspawn sun
   direction (``shade``), so a crate is lit like the floor it stands on, darker in
   shadow and on the side away from the sun.
3. ``inject`` appends the models to STATICMODELDEF (25), their colours to
   STATICMODELDATA (24, 3 bytes per vertex, in TIKI surface/vertex order) and lists
   every model in the leaves its bounds touch (STATICMODELINDEXES, 26, and the leaf
   ``firstStaticModel``/``numStaticModels`` fields).

Collision is not part of this: static models never collide (``cm_load.c`` doesn't read
them), so callers add clip brushes to the map before compiling, as the CS:GO converter
does for every prop.

    >>> grid = LightGrid(BSP("cs_nuke.bsp"))                      # doctest: +SKIP
    >>> inject("cs_nuke.bsp", [StaticInstance("csgo/x.tik", (0, 0, 0), (0, 90, 0), 1.0, pos, nrm)])  # doctest: +SKIP
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Union

import numpy as np

from .bsp import BSP, LUMPS

LEAF_DT = np.dtype([("cluster", "<i4"), ("area", "<i4"), ("mins", "<i4", 3), ("maxs", "<i4", 3),
                    ("first_surface", "<i4"), ("num_surfaces", "<i4"), ("first_brush", "<i4"), ("num_brushes", "<i4"),
                    ("first_terrain", "<i4"), ("num_terrain", "<i4"), ("first_static", "<i4"), ("num_static", "<i4")])
STATIC_DT = np.dtype([("model", "S128"), ("origin", "<f4", 3), ("angles", "<f4", 3), ("scale", "<f4"),
                      ("first_vertex_data", "<i4"), ("num_vertex_data", "<i4")])
assert LEAF_DT.itemsize == 64 and STATIC_DT.itemsize == 164


@dataclass
class StaticInstance:
    """One static model: ``model`` as written in a ``static_*`` entity (``models/`` is
    prepended by the engine unless present), its placement, and its mesh in model space
    (all SKD surfaces' vertices in file order, after the TIKI ``scale``)."""
    model: str
    origin: Sequence[float]
    angles: Sequence[float]
    scale: float
    positions: np.ndarray
    normals: np.ndarray
    # vertex colours to use as they are (N x 3, lightmap byte scale; NaN rows are lit from the
    # BSP like an instance without colours), e.g. CS:GO's own baked prop lighting
    colors: Optional[np.ndarray] = None


# ---------------------------------------------------------------------------- geometry


def axes(angles: Sequence[float]) -> np.ndarray:
    """Rows forward, left, up for pitch/yaw/roll in degrees (``AngleVectorsLeft``)."""
    p, y, r = (math.radians(float(a)) for a in angles)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    forward = (cp * cy, cp * sy, -sp)
    left = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp)
    up = (cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp)
    return np.array([forward, left, up], np.float64)


def world_mesh(inst: StaticInstance) -> tuple[np.ndarray, np.ndarray]:
    """World-space vertex positions and unit normals of an instance."""
    ax = axes(inst.angles)
    pos = np.asarray(inst.positions, np.float64) * float(inst.scale) @ ax + np.asarray(inst.origin, np.float64)
    nrm = np.asarray(inst.normals, np.float64) @ ax
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    return pos, np.where(ln > 1e-6, nrm / np.maximum(ln, 1e-6), np.array([0.0, 0.0, 1.0]))


# ---------------------------------------------------------------------------- light grid


class LightGrid:
    """The BSP light grid as a dense array of palette indices (x, y, z)."""

    def __init__(self, bsp: BSP):
        self.cell = np.array({21: (80.0, 80.0, 80.0), 20: (48.0, 48.0, 64.0)}.get(bsp.version, (32.0, 32.0, 32.0)))
        m = bsp.models()[0]
        mins, maxs = np.array(m["mins"], np.float64), np.array(m["maxs"], np.float64)
        self.mins = self.cell * np.ceil(mins / self.cell)
        top = self.cell * np.floor(maxs / self.cell)
        self.bounds = ((top - self.mins) / self.cell + 1).astype(int)
        pal = bsp.lump("lightgridpalette")
        offs = np.frombuffer(bsp.lump("lightgridoffsets"), "<u2")
        data = bsp.lump("lightgriddata")
        bx, by, bz = (int(v) for v in self.bounds)
        if len(pal) != 768 or len(offs) != bx * by + bx or not data:
            raise ValueError("BSP has no usable light grid (compile with light, without -nogrid)")
        self.palette = np.frombuffer(pal, np.uint8).reshape(256, 3).astype(np.float64)
        idx = np.zeros((bx, by, bz), np.uint8)
        hi = offs[:bx].astype(np.int64) << 8
        for x in range(bx):
            base = bx + by * x
            for y in range(by):
                o = int(offs[base + y]) + int(hi[x])
                col = idx[x, y]
                z = 0
                while z < bz:
                    n = data[o] - 256 if data[o] > 127 else data[o]
                    o += 1
                    if n < 0:
                        k = min(-n, bz - z)
                        col[z:z + k] = np.frombuffer(data, np.uint8, k, o)
                        o += -n
                        z += k
                    else:
                        k = min(n + 2, bz - z)
                        col[z:z + k] = data[o]
                        o += 1
                        z += k
        self.index = idx

    def sample(self, points: np.ndarray) -> np.ndarray:
        """Grid colour (0..255 floats, N x 3) at world ``points`` (N x 3), like
        ``R_GetLightingGridValue``: trilinear over the 8 surrounding cells, cells inside
        solid skipped and the rest renormalised. Points with no lit cell around get NaN."""
        p = (np.asarray(points, np.float64) - self.mins) / self.cell
        g = np.floor(p).astype(int)
        f = p - g
        g = np.clip(g, 0, self.bounds - 2)
        f = np.clip(f, 0.0, 1.0)
        acc = np.zeros((len(p), 3))
        tot = np.zeros(len(p))
        for dx in (0, 1):
            wx = f[:, 0] if dx else 1 - f[:, 0]
            for dy in (0, 1):
                wy = f[:, 1] if dy else 1 - f[:, 1]
                for dz in (0, 1):
                    wz = f[:, 2] if dz else 1 - f[:, 2]
                    i = self.index[g[:, 0] + dx, g[:, 1] + dy, g[:, 2] + dz]
                    w = wx * wy * wz * (i != 0)
                    acc += w[:, None] * self.palette[i]
                    tot += w
        out = np.full((len(p), 3), np.nan)
        ok = tot > 1e-6
        out[ok] = acc[ok] / tot[ok, None]
        return out


# ---------------------------------------------------------------------------- lightmap field


DRAWVERT_DT = np.dtype([("xyz", "<f4", 3), ("st", "<f4", 2), ("lm", "<f4", 2), ("normal", "<f4", 3),
                        ("rgba", "u1", 4)])
AXES6 = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], np.float64)


@dataclass
class Texels:
    """Lightmap texels of a BSP's surfaces: world position, unit normal, page and pixel
    (x right, y down in the 128 x 128 page), and ``inside``: the texel centre lies on the
    surface (within about half a texel) rather than in the padding around it."""
    pos: np.ndarray
    nrm: np.ndarray
    page: np.ndarray
    x: np.ndarray
    y: np.ndarray
    inside: np.ndarray
    surf: Optional[np.ndarray] = None   # surface index of each texel


def _grid_triangles(w: int, h: int) -> np.ndarray:
    """Two triangles per cell of a w x h (columns x rows) patch control grid."""
    t = []
    for r in range(h - 1):
        for c in range(w - 1):
            k = r * w + c
            t += [(k, k + w, k + 1), (k + 1, k + w, k + w + 1)]
    return np.array(t, np.int64).reshape(-1, 3)


def lightmap_texels(bsp: BSP, all_texels: bool = False) -> Texels:
    """Every lightmap texel of the world's planar, triangle-soup and patch surfaces.

    Each texel centre is located on the surface's triangles in lightmap space (patches: the
    triangulated control grid) and given the barycentric world position and normal, clamped
    onto the surface. By default only texels on the surface are returned; ``all_texels``
    also returns the padding texels of each surface's rectangle (to write them)."""
    dv = np.frombuffer(bsp.lump("drawverts"), DRAWVERT_DT)
    ix = np.frombuffer(bsp.lump("drawindexes"), "<i4")
    P, N, PG, X, Y, IN, SI = [], [], [], [], [], [], []
    for si, s in enumerate(bsp.surfaces()):
        if s.lightmap < 0 or s.num_verts == 0 or s.lm_w <= 0 or s.lm_h <= 0:
            continue
        v = dv[s.first_vert:s.first_vert + s.num_verts]
        if s.type == 2:
            if s.patch_w * s.patch_h != s.num_verts or s.patch_w < 2 or s.patch_h < 2:
                continue
            tri = _grid_triangles(s.patch_w, s.patch_h)
        elif s.type in (1, 3) and s.num_indexes >= 3:
            tri = ix[s.first_index:s.first_index + s.num_indexes].reshape(-1, 3)
        else:
            continue
        uv = v["lm"].astype(np.float64) * 128.0
        gu, gt = np.meshgrid(np.arange(s.lm_x, s.lm_x + s.lm_w) + 0.5, np.arange(s.lm_y, s.lm_y + s.lm_h) + 0.5)
        q = np.stack([gu.ravel(), gt.ravel()], 1)
        best = np.full(len(q), -np.inf)
        bary = np.zeros((len(q), 3))
        tris = np.zeros((len(q), 3), int)
        for a, b, c in tri:
            e1, e2 = uv[b] - uv[a], uv[c] - uv[a]
            det = e1[0] * e2[1] - e1[1] * e2[0]
            if abs(det) < 1e-9:
                continue
            d = q - uv[a]
            l1 = (d[:, 0] * e2[1] - d[:, 1] * e2[0]) / det
            l2 = (e1[0] * d[:, 1] - e1[1] * d[:, 0]) / det
            bb = np.stack([1 - l1 - l2, l1, l2], 1)
            m = bb.min(1)
            better = m > best
            best[better], bary[better], tris[better] = m[better], bb[better], (a, b, c)
        # inside, or within about half a texel of the edge (best is in barycentric units)
        inside = best > -0.5 / max(1.0, min(s.lm_w, s.lm_h))
        keep = np.isfinite(best) & (inside | all_texels)
        if not keep.any():
            continue
        bb = np.clip(bary[keep], 0.0, None)
        bb /= np.maximum(bb.sum(1, keepdims=True), 1e-12)
        t3 = tris[keep]
        xyz = v["xyz"].astype(np.float64)
        nrm = v["normal"].astype(np.float64)
        P.append(np.einsum("nk,nkj->nj", bb, xyz[t3]))
        N.append(np.einsum("nk,nkj->nj", bb, nrm[t3]))
        qi = q[keep].astype(int)
        PG.append(np.full(len(qi), s.lightmap, np.int32))
        X.append(np.clip(qi[:, 0], 0, 127))
        Y.append(np.clip(qi[:, 1], 0, 127))
        IN.append(inside[keep])
        SI.append(np.full(len(qi), si, np.int32))
    if not P:
        z = np.zeros((0, 3))
        e = np.zeros(0, np.int64)
        return Texels(z, z, e, e, e, np.zeros(0, bool), e)
    p, n = (np.concatenate(a).astype(np.float64) for a in (P, N))
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return Texels(p, n / np.maximum(ln, 1e-6), np.concatenate(PG), np.concatenate(X), np.concatenate(Y),
                  np.concatenate(IN), np.concatenate(SI))


def lightmap_samples(bsp: BSP) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every lightmap texel of the world as a sample: world position, unit normal and RGB
    (N x 3 each), for texels whose centre falls on the surface (positions clamped onto it,
    so padding texels don't reach through walls). Patches use their triangulated control
    grid."""
    pages = np.frombuffer(bsp.lump("lightmaps"), np.uint8).reshape(-1, 128, 128, 3)
    t = lightmap_texels(bsp)
    ok = t.page < len(pages)
    c = pages[t.page[ok], t.y[ok], t.x[ok]].astype(np.float64)
    return t.pos[ok], t.nrm[ok], c


class LightmapField:
    """Light at any point from the BSP's own lightmaps, per facing direction.

    MOHlight's light grid is no stand-in for its lightmaps under spotlights: it ignores the
    cone and ramps up with depth below the lamp (docs/lighting.md), so props near a CS:GO
    ceiling spot came out black. The lightmaps are right (cones, shadows, bounce). Each texel
    is splatted 4 units out from its surface into 16-unit cells, into six axis slots
    weighted by its normal (like Source's ambient cubes). For each slot ``sample`` marches
    from the vertex against the slot's direction (down for the up slot, toward -x for +x,
    ...) to the first cells with texels facing that way: the floor under a crate lights its
    top, the wall behind it the side facing away from that wall. Props have no lightmaps,
    so the march passes through them. Slots that find nothing within ``reach`` units take
    the mean of the slots that did."""

    CELL = 16.0

    def __init__(self, bsp: BSP, reach: float = 256.0):
        p, n, c = lightmap_samples(bsp)
        self.count = len(p)
        self.steps = int(reach // self.CELL) + 1
        w = np.clip(n @ AXES6.T, 0.0, None) ** 2
        keys = self._keys(np.floor((p + n * 4.0) / self.CELL).astype(np.int64))
        self.uniq, inv = np.unique(keys, return_inverse=True)
        self.sums = np.zeros((len(self.uniq), 6, 3))
        self.wts = np.zeros((len(self.uniq), 6))
        np.add.at(self.sums, inv, w[:, :, None] * c[:, None, :])
        np.add.at(self.wts, inv, w)

    @staticmethod
    def _keys(g: np.ndarray) -> np.ndarray:
        g = g + (1 << 20)
        return (g[:, 0] << 42) | (g[:, 1] << 21) | g[:, 2]

    def _lookup(self, cells: np.ndarray, slot: int) -> tuple[np.ndarray, np.ndarray]:
        k = self._keys(cells)
        i = np.clip(np.searchsorted(self.uniq, k), 0, len(self.uniq) - 1)
        hit = self.uniq[i] == k
        S = np.where(hit[:, None], self.sums[i, slot], 0.0)
        W = np.where(hit, self.wts[i, slot], 0.0)
        return S, W

    def slots(self, points: np.ndarray) -> np.ndarray:
        """Slot colours (N x 6 x 3, NaN where nothing was found) at points."""
        base = np.floor(np.asarray(points, np.float64) / self.CELL).astype(np.int64)
        cells, inv = np.unique(base, axis=0, return_inverse=True)
        inv = inv.ravel()
        out = np.full((len(cells), 6, 3), np.nan)
        for slot in range(6):
            d = AXES6[slot].astype(np.int64)
            lat = [np.array(o, np.int64) for o in
                   ((a, b, 0) if d[2] else (a, 0, b) if d[1] else (0, a, b) for a in (-1, 0, 1) for b in (-1, 0, 1))]
            todo = np.arange(len(cells))
            for step in range(self.steps):
                if not len(todo):
                    break
                at = cells[todo] - d * step
                S = np.zeros((len(todo), 3))
                W = np.zeros(len(todo))
                for o in lat:
                    s_, w_ = self._lookup(at + o, slot)
                    S += s_
                    W += w_
                found = W > 1e-6
                out[todo[found], slot] = S[found] / W[found][:, None]
                todo = todo[~found]
        return out[inv]

    def sample(self, points: np.ndarray, normals: np.ndarray) -> np.ndarray:
        """Lightmap-scale colour (N x 3) for points with unit normals: their slots blended by
        the squared normal components. NaN where no slot found anything."""
        points = np.asarray(points, np.float64)
        normals = np.asarray(normals, np.float64)
        if not self.count or not len(points):
            return np.full((len(points), 3), np.nan)
        sl = self.slots(points)
        known = ~np.isnan(sl[:, :, 0])
        n_known = known.sum(1)
        iso = np.where(known[:, :, None], sl, 0.0).sum(1) / np.maximum(n_known, 1)[:, None]
        val = np.where(known[:, :, None], sl, iso[:, None, :])
        a = np.clip(normals @ AXES6.T, 0.0, None) ** 2
        out = (a[:, :, None] * val).sum(1) / np.maximum(a.sum(1), 1e-6)[:, None]
        out[n_known == 0] = np.nan
        return out


# ---------------------------------------------------------------------------- shading


def sun_direction(bsp: BSP) -> Optional[np.ndarray]:
    """Unit vector toward the sun from worldspawn ``sundirection`` (Quake angles: pitch
    -45 or 315 is 45 degrees above the horizon; docs/lighting.md), or ``None``."""
    ws = next((e for e in bsp.entities() if e.get("classname") == "worldspawn"), {})
    v = ws.get("sundirection")
    if not v:
        return None
    try:
        pitch, yaw = (float(x) for x in v.split()[:2])
    except ValueError:
        return None
    p, y = math.radians(pitch), math.radians(yaw)
    return np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)])


def shade(grid_rgb: np.ndarray, normals: np.ndarray, sun: Optional[np.ndarray],
          direct: float = 0.16, sky: float = 0.08) -> np.ndarray:
    """Vertex colour from the grid colour at the vertex and its normal.

    Measured against MOHlight's own static-model colours (``calibrate``): in an
    ambient-only test map the vertex colours equal the grid (40.3 vs 40.5 mean, 161k
    vertices); in sunlit mk_medina they are 0.55-0.73 of it whatever the facing (23k
    vertices binned by sun facing and grid value). So the grid is scaled by 1.0 up to
    60 and 0.64 from 160 up, and a mild facing term (``direct`` toward the sun, ``sky``
    for faces looking up, zero on average) keeps shapes readable."""
    g = grid_rgb.max(axis=1, keepdims=True)
    k = np.interp(g, [0.0, 60.0, 160.0, 255.0], [1.0, 1.0, 0.64, 0.64])
    f = np.zeros(len(normals))
    if sun is not None:
        f += direct * (np.clip(normals @ sun, 0.0, 1.0) - 0.25)
    f += sky * (np.clip(normals[:, 2], 0.0, 1.0) - 0.25)
    return np.clip(grid_rgb * k * (1.0 + f)[:, None], 0, 255)


# MOHlight static-model vertex colour per lightmap texel value: least-squares fit over
# mk_medina's 21k MOHlight-lit prop vertices that ``LightmapField`` reaches (lightmaps are
# stored at about half brightness, overbright).
LIGHTMAP_TO_VERTEX = 1.78


def light_instance(grid: LightGrid, inst: StaticInstance, sun: Optional[np.ndarray],
                   offset: float = 6.0, fallback: Optional[np.ndarray] = None,
                   field_rgb: Optional[np.ndarray] = None, field_scale: float = LIGHTMAP_TO_VERTEX) -> np.ndarray:
    """Vertex colours (N x 3 uint8) for one instance: from ``field_rgb`` (the instance's
    ``LightmapField.sample``) where it found light, else from the light grid."""
    pos, nrm = world_mesh(inst)
    rgb = grid.sample(pos + nrm * offset)
    bad = np.isnan(rgb[:, 0])
    if bad.any():  # vertex deep in solid (or in a clip hull): sample at the model's top centre
        top = np.array([pos[:, 0].mean(), pos[:, 1].mean(), pos[:, 2].max() + 16.0])
        alt = grid.sample(top[None])[0]
        if np.isnan(alt[0]):
            alt = fallback if fallback is not None else np.array([96.0, 96.0, 96.0])
        rgb[bad] = alt
    rgb = shade(rgb, nrm, sun)
    if field_rgb is not None:
        ok = ~np.isnan(field_rgb[:, 0])
        rgb[ok] = np.clip(field_rgb[ok] * field_scale, 0, 255)
    if inst.colors is not None:
        known = ~np.isnan(inst.colors[:, 0])
        rgb[known] = inst.colors[known]
    return np.clip(rgb, 0, 255).round().astype(np.uint8)


def field_colours(field: "LightmapField", instances: Sequence[StaticInstance], offset: float = 6.0,
                  batch: int = 300_000):
    """``LightmapField.sample`` for every vertex of every instance, in batches of about
    ``batch`` vertices; yields one array per instance, in order."""
    group: list = []
    size = 0

    def flush(group):
        meshes = [world_mesh(i) for i in group]
        pos = np.concatenate([m[0] for m in meshes])
        nrm = np.concatenate([m[1] for m in meshes])
        rgb = field.sample(pos + nrm * offset, nrm)
        k = 0
        for m in meshes:
            yield rgb[k:k + len(m[0])]
            k += len(m[0])

    for inst in instances:
        group.append(inst)
        size += len(inst.positions)
        if size >= batch:
            yield from flush(group)
            group, size = [], 0
    if group:
        yield from flush(group)


# ---------------------------------------------------------------------------- BSP writing


def write_lumps(bsp: BSP, replace: dict[str, bytes], out: Union[str, Path]) -> None:
    """Write ``bsp`` to ``out`` with some lumps replaced (version 19 layout)."""
    if bsp.version != 19:
        raise ValueError(f"writing BSP version {bsp.version} is not supported")
    blobs = [replace[name] if name in replace else bsp.lump(name) for name in LUMPS]
    header = bytearray(struct.pack("<4sii", b"2015", bsp.version, bsp.checksum))
    ofs = 12 + 8 * len(LUMPS)
    table, body = [], bytearray()
    for b in blobs:
        table.append((ofs + len(body), len(b)))
        body += b
        body += b"\0" * (-len(body) % 4)
    for o, n in table:
        header += struct.pack("<ii", o, n)
    Path(out).write_bytes(bytes(header) + bytes(body))


def inject(bsp_path: Union[str, Path], instances: Sequence[StaticInstance], out: Optional[Union[str, Path]] = None,
           light: Optional[Callable[[LightGrid, StaticInstance], np.ndarray]] = None,
           field_scale: float = LIGHTMAP_TO_VERTEX) -> dict:
    """Add ``instances`` to the static models of a lit BSP (in place unless ``out``).

    Vertices without ``colors`` take the BSP's lightmaps (``LightmapField``) times
    ``field_scale``: 1.78 matches MOHlight's own prop lighting; lightmaps transferred from
    CS:GO (``mohkit.source.lighting``) are in vertex scale already (1.0)."""
    bsp = BSP(Path(bsp_path))
    try:
        grid: Optional[LightGrid] = LightGrid(bsp)
    except ValueError:
        grid = None  # an unlit compile (geometry checks): every vertex gets a flat grey
    sun = sun_direction(bsp)
    defs = np.frombuffer(bsp.lump("staticmodeldef"), STATIC_DT).copy()
    data = bytearray(bsp.lump("staticmodeldata"))
    leafs = np.frombuffer(bsp.lump("leafs"), LEAF_DT).copy()
    old_idx = np.frombuffer(bsp.lump("staticmodelindexes"), "<u2")
    lists: list[list[int]] = [list(old_idx[l["first_static"]:l["first_static"] + l["num_static"]]) for l in leafs]
    open_leaf = leafs["cluster"] >= 0
    lmins = leafs["mins"].astype(np.float64)
    lmaxs = leafs["maxs"].astype(np.float64)
    new = np.zeros(len(instances), STATIC_DT)
    placed = unplaced = 0
    # the lit BSP's own lightmaps (the grid ignores spotlight cones); grid where they don't reach
    field = LightmapField(bsp) if grid is not None and light is None and bsp.count("lightmaps") else None
    need = [i for i in instances if i.colors is None or np.isnan(i.colors[:, 0]).any()]
    fields = field_colours(field, need) if field is not None and field.count else None
    for k, inst in enumerate(instances):
        complete = inst.colors is not None and not np.isnan(inst.colors[:, 0]).any()
        f_rgb = next(fields) if fields is not None and not complete else None
        if complete:
            rgb = np.clip(inst.colors, 0, 255).round().astype(np.uint8)
        elif grid is None:
            rgb = np.full((len(inst.positions), 3), 160, np.uint8)
        elif light is not None:
            rgb = light(grid, inst)
        else:
            rgb = light_instance(grid, inst, sun, field_rgb=f_rgb, field_scale=field_scale)
        model = inst.model.encode("latin-1")
        if len(model) >= 128:
            raise ValueError(f"model path too long: {inst.model}")
        rec = new[k]
        rec["model"] = model
        rec["origin"] = inst.origin
        rec["angles"] = inst.angles
        rec["scale"] = inst.scale
        rec["first_vertex_data"] = len(data)
        rec["num_vertex_data"] = len(rgb)
        data += np.ascontiguousarray(rgb, np.uint8).tobytes()
        pos, _ = world_mesh(inst)
        lo, hi = pos.min(0) - 1, pos.max(0) + 1
        hit = np.nonzero(open_leaf & np.all(lmins <= hi, axis=1) & np.all(lmaxs >= lo, axis=1))[0]
        index = len(defs) + k
        if index > 0xFFFF:
            raise ValueError("more than 65535 static models")
        for li in hit:
            lists[li].append(index)
        placed += bool(len(hit))
        unplaced += not len(hit)
    all_defs = np.concatenate([defs, new])
    if len(all_defs) > 4095:
        # staticModelNumIndexes[4095] and the 12-bit sort-key field (mohkit/staticmerge.py)
        raise ValueError(f"{len(all_defs)} static models: the engine draws at most 4095 (use staticmerge.merge)")
    idx_out: list[int] = []
    for li, lst in enumerate(lists):
        leafs[li]["first_static"] = len(idx_out)
        leafs[li]["num_static"] = len(lst)
        idx_out += lst
    write_lumps(bsp, {"staticmodeldef": all_defs.tobytes(), "staticmodeldata": bytes(data),
                      "staticmodelindexes": np.array(idx_out, "<u2").tobytes(), "leafs": leafs.tobytes()},
                out or bsp_path)
    return {"models": len(instances), "vertices": int(sum(len(i.positions) for i in instances)),
            "in_leaves": placed, "outside_leaves": unplaced, "index_entries": len(idx_out),
            "total_models": len(all_defs)}


# ---------------------------------------------------------------------------- meshes


_TIKI_KEYS = re.compile(r"^\s*(scale|path|skelmodel)\s+(\S+)", re.M)


def tiki_mesh(read: Callable[[str], Optional[bytes]], tik: str) -> tuple[np.ndarray, np.ndarray]:
    """Model-space positions and normals of a TIKI's meshes (every SKD surface, in file
    order), scaled by its setup ``scale``. ``read(game_path)`` returns file bytes or None.
    Only single-bone (rigid) meshes are exact; that covers static props."""
    from .source.skd import read_skd
    name = tik if tik.startswith("models/") else "models/" + tik
    text = read(name)
    if text is None:
        raise FileNotFoundError(name)
    keys = {"scale": "1", "path": str(Path(name).parent)}
    skds = []
    for k, v in _TIKI_KEYS.findall(text.decode("latin-1")):
        if k == "skelmodel":
            skds.append(v)
        else:
            keys[k] = v
    scale = float(keys["scale"])
    pos, nrm = [], []
    for s in skds:
        path = s if "/" in s else f"{keys['path'].rstrip('/')}/{s}"
        blob = read(path)
        if blob is None:
            raise FileNotFoundError(path)
        info = read_skd(blob)
        for srf in info.surfaces:
            pos.append(srf.positions.astype(np.float64) * scale)
            nrm.append(srf.normals.astype(np.float64))
    if not pos:
        return np.zeros((0, 3)), np.zeros((0, 3))
    return np.concatenate(pos), np.concatenate(nrm)


def files_reader(*roots: Union[str, Path, dict]) -> Callable[[str], Optional[bytes]]:
    """``read(game_path)`` over directories and/or ``{game_path: bytes}`` dicts, first hit wins."""
    def read(path: str) -> Optional[bytes]:
        for r in roots:
            if isinstance(r, dict):
                if path in r:
                    v = r[path]
                    return v if isinstance(v, bytes) else Path(v).read_bytes()
                continue
            p = Path(r) / path
            if p.is_file():
                return p.read_bytes()
        return None
    return read


# ---------------------------------------------------------------------------- maps with static_* props


def entity_angles(e) -> tuple[float, float, float]:
    """``angles`` "p y r", else ``angle`` (yaw), of a map entity."""
    if e.get("angles"):
        v = [float(x) for x in e.get("angles").split()[:3]]
        return (v[0], v[1], v[2]) if len(v) == 3 else (0.0, 0.0, 0.0)
    return (0.0, float(e.get("angle", "0") or 0), 0.0)


def take_statics(m, read: Callable[[str], Optional[bytes]]) -> tuple[list, list]:
    """Remove the ``static_*`` entities from map ``m`` for injection after the light stage.

    Returns ``(statics, clips)``: ``(model, origin, angles, scale)`` per entity, and the
    model's collision brushes (``models/<model>.map``, which Q3map would have baked into the
    world) placed as world brushes, so collision is unchanged."""
    from . import geom
    from .build import _tri_for
    from .mapfile import Brush, Face, MapFile
    statics, clips, keep = [], [], []
    maps: dict = {}
    for e in m.entities:
        if not e.classname.startswith("static_") or not e.get("model"):
            keep.append(e)
            continue
        model = e.get("model")
        o = e.origin() or (0.0, 0.0, 0.0)
        ang = entity_angles(e)
        sc = float(e.get("scale", "1") or 1)
        statics.append((model, tuple(o), ang, sc))
        key = model if model.startswith("models/") else "models/" + model
        key = key[:-4] + ".map" if key.endswith(".tik") else key + ".map"
        if key not in maps:
            data = read(key)
            maps[key] = MapFile.parse(data.decode("latin-1")).worldspawn.brushes() if data else []
        if not maps[key]:
            continue
        ax = axes(ang)
        for b in maps[key]:
            faces = []
            for f, w in zip(b.faces, b.windings()):
                if len(w) < 3:
                    continue
                pts = [tuple(float(v) for v in np.asarray(q, np.float64) * sc @ ax + np.asarray(o, np.float64))
                       for q in w]
                n = tuple(float(v) for v in np.asarray(f.plane.normal, np.float64) @ ax)
                try:
                    tri = _tri_for(n, pts)
                except AssertionError:
                    continue
                faces.append(Face(tri, f.shader, (0, 0), 0, (1, 1), 0, 0, 0, ["+surfaceparm", "detail"]))
            if len(faces) >= 4:
                clips.append(Brush(faces))
    m.entities = keep
    return statics, clips


def inject_statics(bsp_path, statics: Sequence[tuple], read: Callable[[str], Optional[bytes]],
                   out: Optional[Union[str, Path]] = None) -> dict:
    """``inject`` for ``(model, origin, angles, scale)`` tuples, meshes read with ``read``."""
    meshes: dict = {}
    inst = []
    skipped = 0
    for model, origin, angles, scale in statics:
        if model not in meshes:
            try:
                meshes[model] = tiki_mesh(read, model)
            except (FileNotFoundError, ValueError):
                meshes[model] = (np.zeros((0, 3)), np.zeros((0, 3)))
        pos, nrm = meshes[model]
        if len(pos):
            inst.append(StaticInstance(model, origin, angles, scale, pos, nrm))
        else:
            skipped += 1
    info = inject(bsp_path, inst, out)
    info["unreadable"] = skipped
    return info
