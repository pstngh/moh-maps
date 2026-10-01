"""CS:GO's own baked lighting, moved into a converted map's MOHAA lightmaps.

Every CS:GO map ships VRAD's lighting: per-face lightmaps in linear HDR (``LIGHTING_HDR``,
lump 53, addressed by ``FACES_HDR``). Re-lighting the converted map with MOHlight from
converted ``light`` entities can only approximate it: MOHlight's point light is
``7500 * I * cos / d^2`` in display (gamma) space, capped at a stored 127 (texture colour;
measured, docs/lighting.md), while VRAD's falls off with d^2 in *linear* space, which
the display gamma turns into roughly 1/d^0.9. Converted lights were either flat white near
the lamp or dark between lamps; sky, bounce, texlights and spot cones all needed their own
guesses. This module transfers the real thing instead:

1. ``source_luxels`` decodes every luxel of every lit Source face (style 0, the flat
   lightmap of bumped faces) to a world position, the face normal and a linear RGB colour.
   Planar faces solve the lightmap vectors for the luxel centre (``lm_mins + (s, t)``);
   displacements map luxel (s, t) uniformly over their vertex grid (VBSP gives the base
   corners luxel coords (0,0), (0,T), (S,T), (S,0) from the start corner).
2. ``tonemap`` turns linear light into a MOHAA lightmap byte: display gamma 1/2.2 (Source
   lights in linear space, MOHAA multiplies the sRGB texture by the lightmap), times the
   exposure, with a soft shoulder below MOHlight's cap of 127 so bright areas keep
   their gradients instead of going flat.
3. ``transfer`` fills every texel of every lightmapped MOHAA surface with the luxels
   within a few units that face the same way (spatial hash), falling back to wider
   searches and finally to the nearest luxel of any facing.

The light grid (players, dynamic models) and the injected props are then lit from these
lightmaps (``mohkit.staticlight``), so everything shares one exposure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from .bsp import FACE_DT, Lump, SourceBSP, Surf

GAMMA = 2.2
CAP = 127.0          # MOHlight never stores more (the renderer doubles it: texture colour)
SHOULDER = 0.82      # start of the soft roll-off, as a share of CAP


@dataclass
class Luxels:
    pos: np.ndarray      # (N, 3) world position
    nrm: np.ndarray      # (N, 3) unit normal
    rgb: np.ndarray      # (N, 3) linear light (1.0 = the texture at full brightness)
    face: np.ndarray     # (N,) Source face index


def _decode(raw: np.ndarray) -> np.ndarray:
    """ColorRGBExp32 records (N x 4 bytes) -> linear RGB: c / 255 * 2^exp."""
    c = raw[:, :3].astype(np.float64)
    e = raw[:, 3].astype(np.int8).astype(np.float64)
    return c / 255.0 * np.exp2(e)[:, None]


def source_luxels(bsp: SourceBSP, scale: float = 1.0, model_faces: Optional[set] = None) -> Luxels:
    """Every style-0 luxel of the world's lit faces (HDR lighting when the map has it)."""
    hdr = bsp.lumps[Lump.LIGHTING_HDR].length > 0 if len(bsp.lumps) > Lump.LIGHTING_HDR else False
    light = np.frombuffer(bsp.lump_bytes(Lump.LIGHTING_HDR if hdr else Lump.LIGHTING), np.uint8)
    faces = bsp.lump_array(Lump.FACES_HDR, FACE_DT) if hdr else bsp.faces
    if not len(faces):
        faces = bsp.faces
    tex = bsp.texinfo
    planes = bsp.planes
    surfedges, edges, verts = bsp.surfedges, bsp.edges, bsp.vertices
    P, N, C, F = [], [], [], []
    for fi, f in enumerate(faces):
        ofs = int(f["lightofs"])
        if ofs < 0 or f["styles"][0] == 255 or f["texinfo"] < 0:
            continue
        if model_faces is not None and fi not in model_faces:
            continue
        ti = tex[int(f["texinfo"])]
        if ti["flags"] & (Surf.SKY | Surf.SKY2D | Surf.NODRAW | Surf.NOLIGHT):
            continue
        S, T = int(f["lm_size"][0]), int(f["lm_size"][1])
        n = (S + 1) * (T + 1)
        if ofs + 4 * n > len(light):
            continue
        rgb = _decode(light[ofs:ofs + 4 * n].reshape(n, 4))
        ss, tt = np.meshgrid(np.arange(S + 1, dtype=np.float64), np.arange(T + 1, dtype=np.float64))
        ss, tt = ss.ravel(), tt.ravel()        # index = t * (S + 1) + s
        normal = planes[int(f["planenum"])]["normal"].astype(np.float64)
        if f["dispinfo"] >= 0:
            d = bsp.displacement(int(f["dispinfo"]))
            g = d.positions                    # [row i: p0 -> p1, column j: p0 -> p3]
            m = d.size - 1
            # luxel t runs p0 -> p1 (rows), s runs p0 -> p3 (columns)
            r = tt / max(T, 1) * m
            c = ss / max(S, 1) * m
            r0 = np.clip(np.floor(r).astype(int), 0, m - 1)
            c0 = np.clip(np.floor(c).astype(int), 0, m - 1)
            fr, fc = (r - r0)[:, None], (c - c0)[:, None]
            pos = (g[r0, c0] * (1 - fr) * (1 - fc) + g[r0 + 1, c0] * fr * (1 - fc)
                   + g[r0, c0 + 1] * (1 - fr) * fc + g[r0 + 1, c0 + 1] * fr * fc)
            # per-luxel normal from the grid's local slope
            du = g[r0, np.minimum(c0 + 1, m)] - g[r0, c0]
            dv = g[np.minimum(r0 + 1, m), c0] - g[r0, c0]
            nn = np.cross(dv, du)
            if np.dot(nn.sum(0), normal) < 0:
                nn = -nn
            ln = np.linalg.norm(nn, axis=1, keepdims=True)
            nrm = np.where(ln > 1e-9, nn / np.maximum(ln, 1e-9), normal)
        else:
            lv = ti["lightmap_vecs"].astype(np.float64)
            A = np.array([lv[0, :3], lv[1, :3], normal])
            if abs(np.linalg.det(A)) < 1e-9:
                continue
            dist = float(planes[int(f["planenum"])]["dist"])
            rhs = np.stack([ss + f["lm_mins"][0] - lv[0, 3], tt + f["lm_mins"][1] - lv[1, 3],
                            np.full(n, dist)], 1)
            pos = rhs @ np.linalg.inv(A).T
            nrm = np.broadcast_to(normal, (n, 3))
            # a face's lightmap is the rectangle around its polygon; VRAD leaves the luxels
            # well outside the polygon black (de_inferno's sunlit CT floor got dark blotches
            # where those overlapped the next face). Keep luxels within ~0.75 luxel of it.
            se = surfedges[int(f["firstedge"]):int(f["firstedge"]) + int(f["numedges"])]
            ed = edges[np.abs(se)]
            poly = verts[np.where(se >= 0, ed[:, 0], ed[:, 1])].astype(np.float64)
            ps = poly @ lv[0, :3] + lv[0, 3] - f["lm_mins"][0]
            pt = poly @ lv[1, :3] + lv[1, 3] - f["lm_mins"][1]
            keep = np.ones(n, bool)
            area = np.sum(ps * np.roll(pt, -1) - np.roll(ps, -1) * pt)
            sgn = 1.0 if area > 0 else -1.0
            for k in range(len(poly)):
                ax, ay = ps[k], pt[k]
                bx, by = ps[(k + 1) % len(poly)], pt[(k + 1) % len(poly)]
                ex, ey = bx - ax, by - ay
                ln = math.hypot(ex, ey)
                if ln < 1e-9:
                    continue
                # signed distance (luxels) of each luxel to the edge, positive inside
                dist_in = sgn * (ex * (tt - ay) - ey * (ss - ax)) / ln
                keep &= dist_in >= -0.75
            if not keep.any():
                continue
            pos, nrm, rgb, n = pos[keep], nrm[keep], rgb[keep], int(keep.sum())
        P.append(pos * scale)
        N.append(np.asarray(nrm, np.float64))
        C.append(rgb)
        F.append(np.full(n, fi, np.int32))
    if not P:
        z = np.zeros((0, 3))
        return Luxels(z, z, z, np.zeros(0, np.int32))
    return Luxels(np.concatenate(P), np.concatenate(N), np.concatenate(C), np.concatenate(F))


def tonemap(rgb: np.ndarray, exposure: float = 1.0, shoulder: float = SHOULDER, ceiling=1.0) -> np.ndarray:
    """Linear light -> MOHAA lightmap value (0..127, float).

    The display-space multiplier is (exposure * L)^(1/2.2) (1.0 = the texture's own colour).
    MOHAA can't show more than 1.0 from a lightmap (MOHlight stores at most 127, which the
    renderer doubles), so it rolls off smoothly towards ``ceiling`` from a knee at
    ``shoulder`` (at most 1.0); the value returned is that multiplier / ``ceiling`` x 127.
    ``ceiling`` > 1 is the headroom of a texture brightened by that gain (``headroom_gain``):
    sunlit surfaces can then reach ``ceiling`` x the original texture colour, as in CS:GO.
    ``ceiling`` may be an array (one per sample). Hue is kept by applying the curve to the
    brightest channel and scaling the others with it."""
    x = np.clip(np.asarray(rgb, np.float64) * exposure, 0.0, None)
    mx = x.max(axis=-1, keepdims=True)
    y = np.power(mx, 1.0 / GAMMA)        # display-space multiplier, 1.0 = texture colour
    g = np.maximum(np.asarray(ceiling, np.float64), 1.0)
    if g.ndim:
        g = g.reshape(g.shape + (1,) * (y.ndim - g.ndim))
    k = np.minimum(shoulder * g, np.where(g > 1.0, 1.0, shoulder))
    yr = np.where(y > k, k + (g - k) * (1 - np.exp(-(y - k) / (g - k))), y)
    ratio = np.where(mx > 1e-12, np.power(np.clip(x / np.maximum(mx, 1e-12), 0, 1), 1.0 / GAMMA), 0.0)
    return np.clip(yr * ratio * CAP / g, 0.0, CAP)


HEADROOM_MAX = 1.6


def headroom_gain(rgba: np.ndarray, limit: float = HEADROOM_MAX) -> float:
    """Gain for a lit texture so its brightest texels (99.5th percentile of the brightest
    channel, opaque texels only) reach about 250: the surface's lightmap is divided by the
    same gain (``tonemap(ceiling=gain)``), so shading is unchanged below the old cap and
    sunlight can show up to ``gain`` x the texture colour, like CS:GO's HDR (sunlit floors
    are lit 1.5-2.5x there). White textures get no gain: they would clip."""
    a = np.asarray(rgba)
    rgb = a[..., :3].reshape(-1, 3)
    if a.shape[-1] == 4:
        op = a[..., 3].reshape(-1) >= 128
        if op.any():
            rgb = rgb[op]
    if not len(rgb):
        return 1.0
    p = float(np.percentile(rgb.max(1), 99.5))
    return float(np.clip(250.0 / max(p, 1.0), 1.0, limit))


def apply_gain(rgba: np.ndarray, gain: float) -> np.ndarray:
    """``rgba`` with RGB multiplied by ``gain`` (clipped), alpha unchanged."""
    if gain <= 1.0001:
        return rgba
    out = np.array(rgba, copy=True)
    out[..., :3] = np.clip(np.round(out[..., :3].astype(np.float32) * gain), 0, 255).astype(np.uint8)
    return out


class LuxelIndex:
    """Spatial hash of luxels for nearest-with-facing lookups."""

    def __init__(self, lux: Luxels, cell: float = 8.0):
        self.lux = lux
        self.cell = cell
        g = np.floor(lux.pos / cell).astype(np.int64)
        self.keys = self._keys(g)
        order = np.argsort(self.keys, kind="stable")
        self.order = order
        self.sorted = self.keys[order]

    @staticmethod
    def _keys(g: np.ndarray) -> np.ndarray:
        g = g + (1 << 20)
        return (g[:, 0] << 42) | (g[:, 1] << 21) | g[:, 2]

    def query(self, pts: np.ndarray, nrm: np.ndarray, radius: float, min_dot: float,
              plane_tol: Optional[float] = None) -> tuple[np.ndarray, np.ndarray]:
        """Weighted mean luxel colour within ``radius`` of each point among luxels whose
        normal is within ``min_dot`` of the point's (and, with ``plane_tol``, that lie within
        that distance of the point's plane). Returns (rgb N x 3, found N bool)."""
        r = int(math.ceil(radius / self.cell))
        base = np.floor(pts / self.cell).astype(np.int64)
        acc = np.zeros((len(pts), 3))
        wsum = np.zeros(len(pts))
        L = self.lux
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    k = self._keys(base + np.array([dx, dy, dz]))
                    lo = np.searchsorted(self.sorted, k, "left")
                    hi = np.searchsorted(self.sorted, k, "right")
                    cnt = hi - lo
                    if not cnt.any():
                        continue
                    # expand (point, luxel) pairs for this neighbour cell
                    pi = np.repeat(np.nonzero(cnt)[0], cnt[cnt > 0])
                    starts = np.repeat(lo[cnt > 0], cnt[cnt > 0])
                    offs = np.arange(len(pi)) - np.repeat(np.cumsum(cnt[cnt > 0]) - cnt[cnt > 0], cnt[cnt > 0])
                    li = self.order[starts + offs]
                    d = L.pos[li] - pts[pi]
                    dist = np.sqrt((d * d).sum(1))
                    dot = (L.nrm[li] * nrm[pi]).sum(1)
                    ok = (dist <= radius) & (dot >= min_dot)
                    if plane_tol is not None:
                        ok &= np.abs((d * nrm[pi]).sum(1)) <= plane_tol
                    if not ok.any():
                        continue
                    w = 1.0 / (1.0 + dist[ok]) * np.clip(dot[ok], 0.05, 1.0)
                    np.add.at(acc, pi[ok], L.rgb[li[ok]] * w[:, None])
                    np.add.at(wsum, pi[ok], w)
        found = wsum > 0
        out = np.zeros((len(pts), 3))
        out[found] = acc[found] / wsum[found, None]
        return out, found


def _pairs(index: LuxelIndex, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(point, luxel) index pairs for every luxel in the 27 hash cells around each point."""
    base = np.floor(pts / index.cell).astype(np.int64)
    PI, LI = [], []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                k = index._keys(base + np.array([dx, dy, dz]))
                lo = np.searchsorted(index.sorted, k, "left")
                cnt = np.searchsorted(index.sorted, k, "right") - lo
                has = cnt > 0
                if not has.any():
                    continue
                c = cnt[has]
                pi = np.repeat(np.nonzero(has)[0], c)
                offs = np.arange(len(pi)) - np.repeat(np.cumsum(c) - c, c)
                PI.append(pi)
                LI.append(index.order[np.repeat(lo[has], c) + offs])
    if not PI:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    return np.concatenate(PI), np.concatenate(LI)


# (radius, min normal dot, max distance off the texel's plane) per pass, nearest first
PASSES = ((24.0, 0.9, 2.0), (24.0, 0.7, 8.0), (24.0, 0.5, None))


def lookup(index: LuxelIndex, pts: np.ndarray, nrm: np.ndarray, batch: int = 40_000,
           far: Optional[LuxelIndex] = None) -> tuple[np.ndarray, np.ndarray]:
    """Light (linear RGB) at MOHAA texels from the luxels around them (``index`` hashed in
    cells of at least 24 units): luxels on the texel's plane facing the same way first, then
    near it, then any within 24 units facing within 60 degrees; texels with none of those
    take any luxel within 96 units (``far``, built on demand). Luxels are weighted by
    1 / (1 + distance)^2 and their facing. Returns (rgb, level): level is the pass that
    found it (0-3; 4 = nothing)."""
    out = np.zeros((len(pts), 3))
    level = np.full(len(pts), 4, np.int8)
    L = index.lux
    for s in range(0, len(pts), batch):
        p, n = pts[s:s + batch], nrm[s:s + batch]
        pi, li = _pairs(index, p)
        if len(pi):
            d = L.pos[li] - p[pi]
            dist = np.sqrt((d * d).sum(1))
            dot = (L.nrm[li] * n[pi]).sum(1)
            off = np.abs((d * n[pi]).sum(1))
            w = np.clip(dot, 0.05, 1.0) / (1.0 + dist) ** 2
            todo = np.ones(len(p), bool)
            for lvl, (rad, mind, tol) in enumerate(PASSES):
                ok = todo[pi] & (dist <= rad) & (dot >= mind)
                if tol is not None:
                    ok &= off <= tol
                if not ok.any():
                    continue
                acc = np.zeros((len(p), 3))
                ws = np.bincount(pi[ok], weights=w[ok], minlength=len(p))
                for c in range(3):
                    acc[:, c] = np.bincount(pi[ok], weights=w[ok] * L.rgb[li[ok], c], minlength=len(p))
                got = (ws > 0) & todo
                out[s + np.nonzero(got)[0]] = acc[got] / ws[got, None]
                level[s + np.nonzero(got)[0]] = lvl
                todo &= ~got
    rest = np.nonzero(level == 4)[0]
    if len(rest):
        far = far or LuxelIndex(L, cell=96.0)
        rgb, found = far.query(pts[rest], nrm[rest], 96.0, -1.0)
        out[rest[found]] = rgb[found]
        level[rest[found]] = 3
    return out, level


def exposure_for(bsp: SourceBSP) -> float:
    """Tonemap scale for a map: the middle of its ``env_tonemap_controller`` auto-exposure
    range when the map sets one (keyvalues or logic_auto outputs), else 1."""
    lo = hi = None
    for e in bsp.entities:
        if e.classname == "env_tonemap_controller":
            for k, attr in (("SetAutoExposureMin", "lo"), ("SetAutoExposureMax", "hi")):
                v = e.get(k.lower()) or e.get(k)
                if v:
                    try:
                        if attr == "lo":
                            lo = float(v)
                        else:
                            hi = float(v)
                    except ValueError:
                        pass
        for key, val in [(k, v) for k in {k for k, _ in e.items()} for v in e.get_all(k)]:
            if not key.lower().startswith("on"):
                continue
            parts = val.replace("\x1b", ",").split(",")
            if len(parts) >= 3:
                inp, arg = parts[1].strip().lower(), parts[2].strip()
                try:
                    if inp == "setautoexposuremin":
                        lo = float(arg)
                    elif inp == "setautoexposuremax":
                        hi = float(arg)
                except ValueError:
                    pass
    if lo is not None and hi is not None:
        if lo < 0.05:          # de_cbble: min 0, max 0.9 (no floor): take half the ceiling
            lo = 0.5 * hi
        return math.sqrt(max(lo, 1e-3) * max(hi, 1e-3))
    return lo if lo is not None else hi if hi is not None else 1.0


# ---------------------------------------------------------------------------- MOHAA side


def encode_grid(index: np.ndarray) -> tuple[bytes, bytes]:
    """Light-grid offsets and RLE data lumps for a (bx, by, bz) palette-index array
    (docs/reference/engine.md §7.5): each (x, y) column is run-length coded along z
    (n >= 0: n + 2 copies of the next byte; n < 0: -n literal bytes), and column (x, y)
    starts at ``offsets[bx + y + by * x] + (offsets[x] << 8)``."""
    bx, by, bz = index.shape
    data = bytearray()
    high = np.zeros(bx, np.uint16)
    low = np.zeros(bx * by, np.uint16)
    for x in range(bx):
        base = len(data) >> 8
        high[x] = base
        for y in range(by):
            o = len(data) - (base << 8)
            if o > 0xFFFF:
                raise ValueError("light grid slice too large for 16-bit offsets")
            low[y + by * x] = o
            col = index[x, y]
            z = 0
            lit: list[int] = []
            while z < bz:
                run = 1
                while z + run < bz and col[z + run] == col[z] and run < 129:
                    run += 1
                if run >= 2:
                    if lit:
                        data.append((-len(lit)) & 0xFF)
                        data += bytes(lit)
                        lit = []
                    data.append(run - 2)
                    data.append(int(col[z]))
                    z += run
                else:
                    lit.append(int(col[z]))
                    z += 1
                    if len(lit) == 128:
                        data.append((-128) & 0xFF)
                        data += bytes(lit)
                        lit = []
            if lit:
                data.append((-len(lit)) & 0xFF)
                data += bytes(lit)
    return np.concatenate([high, low]).astype("<u2").tobytes(), bytes(data)


def quantize(colors: np.ndarray, k: int = 255, iters: int = 12, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """k-means palette for N x 3 colours (0..255): (palette k x 3, label per colour)."""
    cols = np.clip(np.round(colors), 0, 255).astype(np.int64)
    key = (cols[:, 0] << 16) | (cols[:, 1] << 8) | cols[:, 2]
    uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    u = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], 1).astype(np.float64)
    if len(u) <= k:
        return u, inv.ravel()
    rng = np.random.default_rng(seed)
    # luminance-sorted quantiles as the start: dark and bright cells both get entries
    order = np.argsort(u @ np.array([0.3, 0.59, 0.11]))
    cent = u[order[np.linspace(0, len(u) - 1, k).astype(int)]].copy()
    w = cnt.astype(np.float64)
    for _ in range(iters):
        d = ((u[:, None, :] - cent[None, :, :]) ** 2).sum(2) if len(u) * k < 4e7 else None
        if d is None:
            lab = np.empty(len(u), np.int64)
            for s in range(0, len(u), 50000):
                lab[s:s + 50000] = ((u[s:s + 50000, None, :] - cent[None]) ** 2).sum(2).argmin(1)
        else:
            lab = d.argmin(1)
        sums = np.zeros((k, 3))
        np.add.at(sums, lab, u * w[:, None])
        ws = np.bincount(lab, weights=w, minlength=k)
        empty = ws == 0
        cent[~empty] = sums[~empty] / ws[~empty, None]
        if empty.any():
            cent[empty] = u[rng.choice(len(u), int(empty.sum()))]
    lab = np.empty(len(u), np.int64)
    for s in range(0, len(u), 50000):
        lab[s:s + 50000] = ((u[s:s + 50000, None, :] - cent[None]) ** 2).sum(2).argmin(1)
    return cent, lab[inv.ravel()]


def grid_colours(field, points: np.ndarray, batch: int = 200_000) -> np.ndarray:
    """Light-grid colour at points from a ``staticlight.LightmapField``: the mean of the
    light arriving from the six axis directions that found any (a point in space is lit
    from all sides; NaN where none did)."""
    out = np.full((len(points), 3), np.nan)
    for s in range(0, len(points), batch):
        sl = field.slots(points[s:s + batch])
        known = ~np.isnan(sl[:, :, 0])
        n = known.sum(1)
        mean = np.where(known[:, :, None], sl, 0.0).sum(1) / np.maximum(n, 1)[:, None]
        mx = np.where(known[:, :, None], sl, -1.0).max(1)
        v = 0.5 * (mean + mx)
        v[n == 0] = np.nan
        out[s:s + batch] = v
    return out


def recolour_grid(bsp, field, fill: Sequence[float] = (40.0, 40.0, 40.0)) -> dict[str, bytes]:
    """New light-grid lumps for a BSP that has a grid: same open/solid cells, colours from
    ``field`` (``_grid_lumps``)."""
    from ..staticlight import LightGrid
    g = LightGrid(bsp)
    return _grid_lumps(bsp, field, g.mins, g.cell, g.bounds, g.index != 0, fill)


def transfer(bsp_path, source: SourceBSP, out, scale: float = 1.0, exposure: Optional[float] = None,
             log=print, gains: Optional[dict] = None, offset=(0.0, 0.0, 0.0)) -> dict:
    """Replace the lightmaps (and light grid) of a compiled converted map with the Source
    map's own baked lighting. Returns statistics.

    ``gains`` (shader name -> texture gain, ``headroom_gain``): those surfaces' light is
    tone-mapped with that ceiling. ``out`` gets the light at texture scale (values may pass
    127 where a gain allows it; the light grid and props are sampled from it) and
    ``stats["divided_lightmaps"]`` the final lump, each surface divided by its gain."""
    import time
    from pathlib import Path

    from ..bsp import BSP
    from ..staticlight import LightmapField, lightmap_texels, write_lumps
    t0 = time.time()
    bsp = BSP(Path(bsp_path))
    exposure = exposure_for(source) if exposure is None else exposure
    lux = source_luxels(source, scale)
    if any(offset):              # the conversion moved the map (``Options.offset``)
        lux.pos = lux.pos + np.asarray(offset, np.float64)
    tex = lightmap_texels(bsp, all_texels=True)
    index = LuxelIndex(lux, cell=24.0 * scale)
    rgb, level = lookup(index, tex.pos, tex.nrm)
    names = [sh.name for sh in bsp.shaders()]
    surf_shader = np.array([s.shader for s in bsp.surfaces()], np.int64)
    gains = gains or {}
    sg = np.array([float(gains.get(n, 1.0)) for n in names] or [1.0])
    g = sg[surf_shader[tex.surf]] if len(tex.surf) else np.ones(0)
    stored = tonemap(rgb, exposure, ceiling=g)
    found = level < 4
    # nothing nearby (MOHAA-only faces): keep a dim neutral rather than black
    stored[~found] = 24.0 / g[~found, None]
    old = np.frombuffer(bsp.lump("lightmaps"), np.uint8).reshape(-1, 128, 128, 3)
    npages = max(int(tex.page.max()) + 1 if len(tex.page) else 0, len(old))
    pages = np.zeros((npages, 128, 128, 3), np.uint8)
    pages[:len(old)] = old
    divided = pages.copy()
    divided[tex.page, tex.y, tex.x] = np.clip(np.round(stored), 0, 255).astype(np.uint8)
    pages[tex.page, tex.y, tex.x] = np.clip(np.round(stored * g[:, None]), 0, 255).astype(np.uint8)
    replace = {"lightmaps": pages.tobytes()}
    stats = {"luxels": len(lux.pos), "texels": len(tex.pos), "exposure": round(exposure, 3),
             "levels": np.bincount(level, minlength=5).tolist(), "pages": npages,
             "gained_texels": int((g > 1.0001).sum())}
    replace["drawverts"] = vertex_colours(bsp, index, exposure)
    write_lumps(bsp, replace, out)
    lit = BSP(Path(out))
    field = LightmapField(lit)
    try:
        replace.update(recolour_grid(lit, field) if bsp.lump("lightgriddata") else build_grid(lit, field))
        stats["grid"] = "recoloured" if bsp.lump("lightgriddata") else "built"
    except ValueError as e:
        replace.update(build_grid(lit, field))
        stats["grid"] = f"built ({e})"
    write_lumps(bsp, replace, out)
    stats["divided_lightmaps"] = divided.tobytes()
    stats["seconds"] = round(time.time() - t0, 1)
    log(f"== CS:GO lighting transferred: { {k: v for k, v in stats.items() if k != 'divided_lightmaps'} }")
    return stats


def point_leaves(bsp, points: np.ndarray) -> np.ndarray:
    """Leaf index of each point (BSP tree descent on the MOHAA world model)."""
    nodes = np.frombuffer(bsp.lump("nodes"), np.dtype([("plane", "<i4"), ("children", "<i4", 2),
                                                      ("mins", "<i4", 3), ("maxs", "<i4", 3)]))
    planes = np.frombuffer(bsp.lump("planes"), np.dtype([("normal", "<f4", 3), ("dist", "<f4")]))
    pts = np.asarray(points, np.float64)
    cur = np.zeros(len(pts), np.int64)
    active = np.ones(len(pts), bool)
    for _ in range(4096):
        if not active.any():
            break
        a = np.nonzero(active)[0]
        nd = nodes[cur[a]]
        pl = planes[nd["plane"]]
        side = (pts[a] * pl["normal"].astype(np.float64)).sum(1) - pl["dist"] >= 0
        nxt = np.where(side, nd["children"][:, 0], nd["children"][:, 1]).astype(np.int64)
        cur[a] = nxt
        active[a] = nxt >= 0
    return -(cur + 1)


def _near_surfaces(bsp, mins: np.ndarray, cell: np.ndarray, bounds, reach: int = 3) -> np.ndarray:
    """Dense bool (bounds) mask: cells within ``reach`` cells of a lightmap texel."""
    from ..staticlight import lightmap_texels
    t = lightmap_texels(bsp)
    near = np.zeros(tuple(bounds), bool)
    if not len(t.pos):
        return near
    ijk = np.clip(np.round((t.pos - mins) / cell).astype(int), 0, np.array(bounds) - 1)
    near[tuple(ijk.T)] = True
    for ax in range(3):            # separable dilation: a box of (2 * reach + 1) cells
        acc = near.copy()
        for sh in range(1, reach + 1):
            for sgn in (-1, 1):
                r = np.roll(near, sgn * sh, axis=ax)
                if sgn > 0:
                    r[(slice(None),) * ax + (slice(0, sh),)] = False
                else:
                    r[(slice(None),) * ax + (slice(-sh, None),)] = False
                acc |= r
        near = acc
    return near


def _grid_lumps(bsp, field, mins, cell, bounds, open_mask: np.ndarray,
                fill: Sequence[float] = (40.0, 40.0, 40.0)) -> dict[str, bytes]:
    """Colour the open cells of a light grid from ``field`` and encode it. Only cells within
    ~96 units of a surface (where players and models are) are sampled; the others take
    their sampled neighbours' mean (a few steps), then the median of the sampled cells."""
    near = _near_surfaces(bsp, mins, cell, bounds) & open_mask
    dense = np.full(tuple(bounds) + (3,), np.nan)
    pick = np.argwhere(near)
    if len(pick):
        dense[tuple(pick.T)] = grid_colours(field, mins + pick * cell)
    for _ in range(3):
        todo = np.isnan(dense[..., 0]) & open_mask
        if not todo.any():
            break
        acc = np.zeros(dense.shape)
        cnt = np.zeros(dense.shape[:3])
        for ax in range(3):
            for sh in (-1, 1):
                r = np.roll(dense, sh, axis=ax)
                ok = ~np.isnan(r[..., 0])
                acc[ok] += r[ok]
                cnt[ok] += 1
        fillable = todo & (cnt > 0)
        dense[fillable] = acc[fillable] / cnt[fillable, None]
    lit = np.argwhere(open_mask)
    col = dense[tuple(lit.T)]
    known = ~np.isnan(col[:, 0])
    col[~known] = np.median(col[known], axis=0) if known.any() else fill
    index = np.zeros(tuple(bounds), np.uint8)
    if len(lit):
        pal, lab = quantize(col, 255)
        index[tuple(lit.T)] = (lab + 1).astype(np.uint8)
    else:
        pal = np.zeros((0, 3))
    palette = np.zeros((256, 3), np.uint8)
    palette[1:len(pal) + 1] = np.clip(np.round(pal), 0, 255).astype(np.uint8)
    offs, data = encode_grid(index)
    return {"lightgridpalette": palette.tobytes(), "lightgridoffsets": offs, "lightgriddata": data}


def build_grid(bsp, field, fill: Sequence[float] = (40.0, 40.0, 40.0)) -> dict[str, bytes]:
    """Light-grid lumps for a BSP compiled without a light stage: the grid MOHlight would
    lay out (32-unit cells over model 0's bounds, docs/reference/engine.md §7.5), cells
    whose centre lies in a leaf with a cluster open (others are solid, palette index 0),
    coloured from ``field`` (``_grid_lumps``)."""
    from ..staticlight import LEAF_DT
    cell = np.array({21: (80.0, 80.0, 80.0), 20: (48.0, 48.0, 64.0)}.get(bsp.version, (32.0, 32.0, 32.0)))
    m = bsp.models()[0]
    mins = cell * np.ceil(np.array(m["mins"], np.float64) / cell)
    top = cell * np.floor(np.array(m["maxs"], np.float64) / cell)
    bounds = ((top - mins) / cell + 1).astype(int)
    leafs = np.frombuffer(bsp.lump("leafs"), LEAF_DT)
    ii = np.indices(tuple(bounds)).reshape(3, -1).T
    leaf = point_leaves(bsp, mins + ii * cell)
    open_mask = (leafs["cluster"][leaf] >= 0).reshape(tuple(bounds))
    return _grid_lumps(bsp, field, mins, cell, bounds, open_mask, fill)


def vertex_colours(bsp, index: "LuxelIndex", exposure: float) -> bytes:
    """The drawverts lump with every vertex colour set from the CS:GO light at the vertex
    (``rgbGen vertex`` surfaces: converted translucent and decal materials)."""
    from ..staticlight import DRAWVERT_DT
    dv = np.frombuffer(bsp.lump("drawverts"), DRAWVERT_DT).copy()
    if not len(dv):
        return bsp.lump("drawverts")
    nrm = dv["normal"].astype(np.float64)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(ln > 1e-6, nrm / np.maximum(ln, 1e-6), np.array([0.0, 0.0, 1.0]))
    rgb, level = lookup(index, dv["xyz"].astype(np.float64) + nrm * 0.5, nrm)
    # vertex colours are drawn like lightmaps: doubled by the renderer (overbright shift)
    v = tonemap(rgb, exposure)
    v[level == 4] = 64.0
    dv["rgba"][:, :3] = np.clip(np.round(v), 0, 255).astype(np.uint8)
    return dv.tobytes()
