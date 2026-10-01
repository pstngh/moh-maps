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


def light_instance(grid: LightGrid, inst: StaticInstance, sun: Optional[np.ndarray],
                   offset: float = 6.0, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    """Vertex colours (N x 3 uint8) for one instance."""
    pos, nrm = world_mesh(inst)
    rgb = grid.sample(pos + nrm * offset)
    bad = np.isnan(rgb[:, 0])
    if bad.any():  # vertex deep in solid (or in a clip hull): sample at the model's top centre
        top = np.array([pos[:, 0].mean(), pos[:, 1].mean(), pos[:, 2].max() + 16.0])
        alt = grid.sample(top[None])[0]
        if np.isnan(alt[0]):
            alt = fallback if fallback is not None else np.array([96.0, 96.0, 96.0])
        rgb[bad] = alt
    return shade(rgb, nrm, sun).round().astype(np.uint8)


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
           light: Optional[Callable[[LightGrid, StaticInstance], np.ndarray]] = None) -> dict:
    """Add ``instances`` to the static models of a lit BSP (in place unless ``out``)."""
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
    for k, inst in enumerate(instances):
        if grid is None:
            rgb = np.full((len(inst.positions), 3), 160, np.uint8)
        elif light is not None:
            rgb = light(grid, inst)
        else:
            rgb = light_instance(grid, inst, sun)
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
