"""Progressive-mesh LOD for static models: SKD collapse tables and ``.lod`` curves.

How the engine draws a static model surface (``renderergl1/tr_model.cpp`` RB_StaticMesh,
``GetLodCutoff``; ``tiki/tiki_skel.cpp`` GetLODFile, TIKI_CalcLodConsts):

* Each model gets a metric ``m = R * (100 / fovX) / d`` (``ProjectRadius``): ``R`` its
  radius (the SKC frame radius times the TIKI scale), ``d`` the eye distance. The engine
  shrinks it by ``r_lodscale`` and caps it (``r_lodcap``): ``m' = (m - maxM) * lodscale +
  maxM``, at most ``maxM + (minM - maxM) * lodcap``. Retail's high preset uses 0.55 / 0.55.
* The ``.lod`` file beside the ``.skd`` (``lodControl_t``: minMetric, maxMetric, five
  ``(pos, val)`` curve points, four derived constants; 96 bytes) maps ``m'`` to a cutoff:
  ``val`` interpolated linearly, ``pos`` 0 at ``minMetric`` and 1 at ``maxMetric``.
* Every vertex has a ``collapseIndex``; vertices are sorted so it never increases, and the
  ones with ``collapseIndex >= cutoff`` (a prefix) are drawn. A dropped vertex follows
  ``collapse[i]`` (always a lower index) until it reaches a drawn one; triangles are drawn
  in file order until the first one that became degenerate, so triangles are sorted by the
  step at which they vanish. A surface whose ``collapseIndex[2] < cutoff`` is not drawn.
* The engine only builds a LOD table when a surface's first and last ``collapseIndex``
  differ; otherwise the whole mesh is always drawn (our converted props until now).

Static models are only frustum-culled (``tr_staticmodels.cpp``), so a converted map's props
were drawn at full detail at any distance: 0.3-0.9 M vertices per frame on de_cache.

``simplify`` builds the collapse sequence with quadric error metrics (Garland-Heckbert
half-edge collapses, so every vertex keeps its original position, as the format needs):
positions are welded across surfaces, open and seam edges (texture or normal splits,
material borders) get perpendicular penalty planes, collapses that flip a triangle are
refused, and a position can only collapse into one that exists in every surface it is in.
Each step's error is the RMS distance of the moved vertex to its accumulated planes.
``lod_control`` turns the errors into a curve that keeps the on-screen error near
``TAU_PX`` pixels (1920 wide, fov 80, the high preset), and never simplifies more than
the error allows at the five curve points.
"""

from __future__ import annotations

import hashlib
import heapq
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from .source import skd as _skd

VERSION = 1                   # bump when the output changes (cache key)
TAU_PX = 2.0                  # target screen error (pixels)
REF_WIDTH = 1920.0            # ... at this screen width
REF_FOV = 80.0                # ... and this fovX
REF_LODSCALE = 0.55           # retail high preset r_lodscale
REF_LODCAP = 0.55             # retail high preset r_lodcap
MAX_DISTANCE = 12000.0        # farther than any view in a +-8192 map: the curve ends here
WELD = 1e-3                   # positions closer than this (units) are one position
SEAM_WEIGHT = 1.0             # penalty plane weight (x edge length^2) on open and seam edges
FLIP_DOT = 0.2                # refuse collapses that turn a triangle more than ~78 degrees
FREE_ERROR = 0.01             # collapses below this error (units) are made even at full detail


@dataclass
class Simplified:
    surfaces: list[_skd.SkdSurface]     # vertices and triangles reordered (with collapse data)
    perms: list[np.ndarray]             # per surface: new vertex i was old vertex perm[i]
    errors: np.ndarray                  # error (units) of collapse steps 1..K, non-decreasing
    steps: int = 0

    @property
    def perm(self) -> np.ndarray:
        """One permutation over all surfaces' vertices (file order), as ``tiki_mesh`` reads them."""
        out, base = [], 0
        for p in self.perms:
            out.append(p + base)
            base += len(p)
        return np.concatenate(out) if out else np.zeros(0, np.int64)


def _quadrics(pts: np.ndarray, n: np.ndarray, w: np.ndarray) -> np.ndarray:
    """10-coefficient plane quadrics (a^2 ab ac ad b^2 bc bd c^2 cd d^2) * w for unit normals n
    through points pts."""
    d = -(n * pts).sum(1)
    a, b, c = n[:, 0], n[:, 1], n[:, 2]
    return np.stack([a * a, a * b, a * c, a * d, b * b, b * c, b * d, c * c, c * d, d * d], 1) * w[:, None]


def simplify(surfaces: Sequence[_skd.SkdSurface]) -> Simplified:
    """Collapse sequence for a model's surfaces (one global step numbering, as the engine
    compares every surface's ``collapseIndex`` with one cutoff)."""
    ns = len(surfaces)
    counts = [len(s.positions) for s in surfaces]
    allpos = np.concatenate([np.asarray(s.positions, np.float64) for s in surfaces])
    keys = np.round(allpos / WELD).astype(np.int64)
    _, first, inv = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    P = allpos[first]                       # welded positions
    npos = len(P)
    offs = np.concatenate([[0], np.cumsum(counts)])
    pos_of = [inv[offs[s]:offs[s + 1]].tolist() for s in range(ns)]

    # faces (surface, vertex triple), their position triples
    face_s, face_v = [], []
    for s, srf in enumerate(surfaces):
        t = np.asarray(srf.triangles, np.int64).reshape(-1, 3)
        face_s += [s] * len(t)
        face_v += t.tolist()
    nf = len(face_v)
    fs = np.asarray(face_s, np.int64)
    fv = np.asarray(face_v, np.int64).reshape(-1, 3)
    fp = inv[fv + offs[fs][:, None]] if nf else np.zeros((0, 3), np.int64)
    death = np.full(nf, -1, np.int64)       # -1 alive; 0 degenerate from the start
    degen = (fp[:, 0] == fp[:, 1]) | (fp[:, 1] == fp[:, 2]) | (fp[:, 2] == fp[:, 0])
    death[degen] = 0

    # initial quadrics: area-weighted face planes ...
    Q = np.zeros((npos, 10))
    W = np.zeros(npos)
    live = np.nonzero(~degen)[0]
    if len(live):
        a, b, c = P[fp[live, 0]], P[fp[live, 1]], P[fp[live, 2]]
        cr = np.cross(b - a, c - a)
        ln = np.linalg.norm(cr, axis=1)
        ok = ln > 1e-12
        nrm = np.where(ok[:, None], cr / np.maximum(ln, 1e-12)[:, None], 0.0)
        area = 0.5 * ln
        fq = _quadrics(a, nrm, area)
        for k in range(3):
            np.add.at(Q, fp[live, k], fq)
            np.add.at(W, fp[live, k], area)
        # ... plus planes along open and seam edges (perpendicular to the face)
        e_pos, e_face, e_vkey = [], [], []
        for k in range(3):
            i, j = fp[live, k], fp[live, (k + 1) % 3]
            e_pos.append(np.stack([np.minimum(i, j), np.maximum(i, j)], 1))
            vi, vj = fv[live, k], fv[live, (k + 1) % 3]
            e_vkey.append(np.stack([fs[live], np.minimum(vi, vj), np.maximum(vi, vj)], 1))
            e_face.append(np.stack([np.arange(len(live)), np.full(len(live), k)], 1))
        e_pos, e_vkey, e_face = np.concatenate(e_pos), np.concatenate(e_vkey), np.concatenate(e_face)
        ue, eidx, ecount = np.unique(e_pos, axis=0, return_inverse=True, return_counts=True)
        eidx = eidx.reshape(-1)
        # an edge is a seam when its faces don't all share the same vertex pair of one surface
        uv_keys = np.unique(np.concatenate([eidx[:, None], e_vkey], 1), axis=0)
        variants = np.bincount(uv_keys[:, 0], minlength=len(ue))
        hard = (ecount[eidx] == 1) | (variants[eidx] > 1)
        if hard.any():
            fi, k = e_face[hard, 0], e_face[hard, 1]
            pa, pb = e_pos[hard, 0], e_pos[hard, 1]
            ev = P[pb] - P[pa]
            el2 = (ev * ev).sum(1)
            pn = np.cross(ev, nrm[fi])
            pl = np.linalg.norm(pn, axis=1)
            good = (pl > 1e-12) & ok[fi]
            pn = pn[good] / pl[good][:, None]
            w = el2[good] * SEAM_WEIGHT
            eq = _quadrics(P[pa[good]], pn, w)
            np.add.at(Q, pa[good], eq)
            np.add.at(Q, pb[good], eq)
            np.add.at(W, pa[good], w)
            np.add.at(W, pb[good], w)

    # --- Python state for the collapse loop
    Pl = P.tolist()
    Ql = Q.tolist()
    Wl = W.tolist()
    fvl = fv.tolist()
    fsl = fs.tolist()
    pfaces: list[set] = [set() for _ in range(npos)]
    vfaces = [[set() for _ in range(c)] for c in counts]
    copies: list[dict] = [dict() for _ in range(npos)]
    for s in range(ns):
        po = pos_of[s]
        for v in range(counts[s]):
            copies[po[v]].setdefault(s, set()).add(v)
    for f in live.tolist():
        s = fsl[f]
        for v in fvl[f]:
            vfaces[s][v].add(f)
            pfaces[pos_of[s][v]].add(f)
    uvs = [np.asarray(srf.uvs, np.float64).tolist() for srf in surfaces]
    stamp = [0] * npos
    alive = [True] * npos
    step_of = [[-1] * c for c in counts]     # -1: never removed; 0: in no triangle at all
    target = [[-1] * c for c in counts]      # -1: none (or vertex 0 when it only lost its triangles)
    for s in range(ns):
        used = set(v for f in live.tolist() if fsl[f] == s for v in fvl[f]) if counts[s] else set()
        for v in range(counts[s]):
            if v not in used:
                step_of[s][v] = 0
                cs = copies[pos_of[s][v]].get(s)
                if cs is not None:
                    cs.discard(v)
                    if not cs:
                        del copies[pos_of[s][v]][s]
    errors: list[float] = []

    def cost(p: int, q: int) -> float:
        a, b = Ql[p], Ql[q]
        x, y, z = Pl[q]
        q0, q1, q2, q3, q4, q5, q6, q7, q8, q9 = (a[i] + b[i] for i in range(10))
        return (q0 * x * x + 2 * q1 * x * y + 2 * q2 * x * z + 2 * q3 * x + q4 * y * y + 2 * q5 * y * z
                + 2 * q6 * y + q7 * z * z + 2 * q8 * z + q9)

    def fpos(f: int) -> list[int]:
        po = pos_of[fsl[f]]
        return [po[v] for v in fvl[f]]

    heap: list = []

    def push_edges(p: int) -> None:
        nb = set()
        for f in pfaces[p]:
            nb.update(fpos(f))
        nb.discard(p)
        for n in nb:
            heapq.heappush(heap, (cost(p, n), p, n, stamp[p], stamp[n]))
            heapq.heappush(heap, (cost(n, p), n, p, stamp[n], stamp[p]))

    seen = set()
    for f in live.tolist():
        a, b, c = fpos(f)
        for p, q in ((a, b), (b, c), (c, a), (b, a), (c, b), (a, c)):
            if (p, q) not in seen:
                seen.add((p, q))
                heapq.heappush(heap, (cost(p, q), p, q, 0, 0))
    seen.clear()

    def valid(p: int, q: int) -> bool:
        cq = copies[q]
        for s in copies[p]:
            if not cq.get(s):
                return False
        x, y, z = Pl[q]
        for f in pfaces[p]:
            ps = fpos(f)
            if q in ps:
                continue
            A, B, C = (Pl[i] for i in ps)
            # normal before
            ux, uy, uz = B[0] - A[0], B[1] - A[1], B[2] - A[2]
            vx, vy, vz = C[0] - A[0], C[1] - A[1], C[2] - A[2]
            n0 = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            k = ps.index(p)
            pts = [A, B, C]
            pts[k] = (x, y, z)
            A, B, C = pts
            ux, uy, uz = B[0] - A[0], B[1] - A[1], B[2] - A[2]
            vx, vy, vz = C[0] - A[0], C[1] - A[1], C[2] - A[2]
            n1 = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            d = n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]
            l0 = n0[0] * n0[0] + n0[1] * n0[1] + n0[2] * n0[2]
            l1 = n1[0] * n1[0] + n1[1] * n1[1] + n1[2] * n1[2]
            if l1 <= 1e-18 * max(l0, 1e-30):
                continue            # becomes a sliver; harmless
            if d <= FLIP_DOT * math.sqrt(l0 * l1):
                return False
        return True

    k = 0
    while heap:
        c, p, q, sp, sq = heapq.heappop(heap)
        if not alive[p] or not alive[q] or stamp[p] != sp or stamp[q] != sq:
            continue
        if not valid(p, q):
            continue
        k += 1
        errors.append(math.sqrt(max(c, 0.0) / max(Wl[p], 1e-12)))
        # move every copy of p onto a copy of q in the same surface: the one it shares a
        # triangle with, else the nearest in texture space
        for s, vs in copies[p].items():
            qs = copies[q][s]
            po = pos_of[s]
            uv = uvs[s]
            for a in vs:
                b = -1
                for f in vfaces[s][a]:
                    for v in fvl[f]:
                        if po[v] == q:
                            b = v
                            break
                    if b >= 0:
                        break
                if b < 0:
                    ua = uv[a]
                    b = min(qs, key=lambda v: (uv[v][0] - ua[0]) ** 2 + (uv[v][1] - ua[1]) ** 2)
                target[s][a] = b
                step_of[s][a] = k
                for f in vfaces[s][a]:
                    fvf = fvl[f]
                    fvf[fvf.index(a)] = b
                    vfaces[s][b].add(f)
                vfaces[s][a] = set()
        copies[p] = {}
        orphans = set()
        for f in pfaces[p]:
            ps = fpos(f)
            vv = fvl[f]
            if ps.count(q) > 1 or vv[0] == vv[1] or vv[1] == vv[2] or vv[2] == vv[0]:
                death[f] = k
                s = fsl[f]
                for v in vv:
                    vfaces[s][v].discard(f)
                    if not vfaces[s][v]:
                        orphans.add((s, v))
                for i in ps:
                    if i != p:
                        pfaces[i].discard(f)
            else:
                pfaces[q].add(f)
        pfaces[p] = set()
        # vertices no triangle uses any more are dropped at this step too (else every part
        # that collapsed away would leave its last vertices drawn forever); they point at
        # vertex 0, which no drawn triangle can then reach through them
        for s, v in orphans:
            if step_of[s][v] < 0:
                step_of[s][v] = k
                target[s][v] = -2
                r = pos_of[s][v]
                cs = copies[r].get(s)
                if cs is not None:
                    cs.discard(v)
                    if not cs:
                        del copies[r][s]
        qq, qp = Ql[q], Ql[p]
        Ql[q] = [qq[i] + qp[i] for i in range(10)]
        Wl[q] += Wl[p]
        alive[p] = False
        stamp[q] += 1
        push_edges(q)

    K = k
    err = np.maximum.accumulate(np.asarray(errors, np.float64)) if errors else np.zeros(0)
    death[death < 0] = K + 1
    out, perms = [], []
    face_off = 0
    for s, srf in enumerate(surfaces):
        n = counts[s]
        cidx = np.array([K + 1 if st < 0 else st for st in step_of[s]], np.int64)
        perm = np.array(sorted(range(n), key=lambda v: (-cidx[v], v)), np.int64)
        newi = np.empty(n, np.int64)
        newi[perm] = np.arange(n)
        tg = np.array(target[s], np.int64)
        # a vertex whose target was dropped at the same step (its triangles all vanished with
        # that collapse) is referenced by nothing: it points at vertex 0 like other orphans
        stale = (tg >= 0) & (cidx[np.maximum(tg, 0)] <= cidx)
        tg[stale] = -2
        col = np.zeros(n, np.int64)
        moved = tg[perm] >= 0
        col[moved] = newi[tg[perm][moved]]
        assert (col[moved] < np.nonzero(moved)[0]).all(), "collapse target after the vertex"
        assert (cidx[perm][col[moved]] > cidx[perm][moved]).all(), "collapse target dropped first"
        nt = len(srf.triangles)
        fd = death[face_off:face_off + nt]
        face_off += nt
        torder = np.array(sorted(range(nt), key=lambda f: (-fd[f], f)), np.int64)
        tris = newi[np.asarray(srf.triangles, np.int64).reshape(-1, 3)[torder]]
        ns_ = _skd.SkdSurface(srf.name, np.asarray(srf.positions)[perm], np.asarray(srf.normals)[perm],
                              np.asarray(srf.uvs)[perm], tris)
        ns_.collapse = col.astype(np.int32)
        ns_.collapse_index = cidx[perm].astype(np.int32)
        out.append(ns_)
        perms.append(perm)
    return Simplified(out, perms, err, K)


def metric_scale() -> float:
    """Screen pixels per unit of (error / R) per unit of engine metric m', at the reference view."""
    px_per_rad = (REF_WIDTH / 2) / math.tan(math.radians(REF_FOV) / 2)
    # m = R * (100 / fov) / d  ->  1/d = m / (R * 100 / fov); m' ~ lodscale * m
    return px_per_rad / (100.0 / REF_FOV) / REF_LODSCALE


def cutoff_at(errors: np.ndarray, radius: float, m: float, tau: float = TAU_PX) -> float:
    """Highest cutoff (1 + steps made) whose error stays under ``tau`` pixels at metric ``m``."""
    allowed = tau * radius / (metric_scale() * max(m, 1e-9))
    return 1.0 + float(np.searchsorted(errors, allowed, side="right"))


def _fit_under(grid: np.ndarray, true: np.ndarray, idx: Sequence[int]) -> np.ndarray:
    """Values at the curve points ``grid[idx]`` (near to far) whose straight segments (in
    metric, as the engine interpolates) stay at or under ``true`` on every grid point: each
    point's value is lowered until the segment before it fits."""
    vals = [float(true[idx[0]])]
    for a, b in zip(idx, idx[1:]):
        xa, xb, va = grid[a], grid[b], vals[-1]
        vb = float(true[b])
        g = np.arange(a + 1, b)
        if len(g):
            t = (xa - grid[g]) / (xa - xb)
            vb = min(vb, float(np.min(va + (true[g] - va) / t)))
        vals.append(max(vb, va))
    return np.array(vals)


def lod_control(errors: np.ndarray, radius: float, tau: float = TAU_PX) -> Optional[bytes]:
    """``.lod`` bytes (lodControl_t) for a model's collapse errors, or None when nothing
    collapses. The curve keeps error <= ``tau`` pixels at its points, starts at full detail
    (only the error-free collapses, < ``FREE_ERROR`` units) where the high preset's cap lands
    for near objects, and ends at ``MAX_DISTANCE``."""
    K = len(errors)
    if K == 0 or radius <= 0:
        return None
    S = metric_scale()
    free = 1.0 + float(np.searchsorted(errors, FREE_ERROR, side="right"))
    nz = errors[errors > FREE_ERROR]
    m_far = radius * (100.0 / REF_FOV) / MAX_DISTANCE * REF_LODSCALE
    if not len(nz):
        m_first = m_far * 4
    else:
        m_first = tau * radius / (S * nz[0])          # beyond this, the first real collapse shows
    m_first = max(m_first, m_far * 1.5)
    # metrics where the curve is evaluated (log spaced, near -> far)
    grid = np.exp(np.linspace(math.log(m_first), math.log(m_far), 32))
    true = np.array([cutoff_at(errors, radius, m, tau) for m in grid])
    true = np.maximum(true, free)
    best, best_pts, best_vals = -1.0, None, None
    for i in range(1, len(grid) - 2):
        for j in range(i + 1, len(grid) - 1):
            idx = [0, i, j, len(grid) - 1]
            vals = _fit_under(grid, true, idx)
            curve = np.interp(grid[::-1], grid[idx][::-1], vals[::-1])[::-1]
            area = curve.sum()
            if area > best:
                best, best_pts, best_vals = area, idx, vals
    m1, m2, m3, m4 = (float(grid[i]) for i in best_pts)
    v1, v2, v3, v4 = (float(v) for v in best_vals)
    if v4 <= 1.0:
        return None
    # minMetric so that the high preset's cap (maxM + cap * (minM - maxM)) lands on m1
    minm = m4 + (m1 - m4) / REF_LODCAP
    maxm = m4
    pos = [0.0] + [(minm - m) / (minm - maxm) for m in (m1, m2, m3)] + [1.0]
    val = [free, v1, v2, v3, v4]
    for i in range(1, 5):
        pos[i] = max(pos[i], pos[i - 1] + 1e-4)
        val[i] = max(val[i], val[i - 1])
    pos[4] = 1.0
    consts = []
    for i in range(4):
        common = (val[i + 1] - val[i]) / (pos[i + 1] - pos[i])
        base = val[i] + (minm / (minm - maxm) - pos[i]) * common
        scale = common / (maxm - minm)
        cutoff = minm + (maxm - minm) * pos[i]
        consts += [base, scale, cutoff]
    data = [minm, maxm] + [x for pv in zip(pos, val) for x in pv] + consts
    return struct.pack("<24f", *data)


def read_lod(data: bytes) -> dict:
    f = struct.unpack("<24f", data[:96])
    return {"minMetric": f[0], "maxMetric": f[1], "curve": [(f[2 + 2 * i], f[3 + 2 * i]) for i in range(5)]}


def engine_cutoff(lod: bytes, m: float, lodscale: float = REF_LODSCALE, lodcap: float = REF_LODCAP) -> float:
    """The cutoff ``GetLodCutoff`` returns for metric ``m`` (for tests and tables)."""
    f = struct.unpack("<24f", lod[:96])
    minm, maxm = f[0], f[1]
    curve = [(f[2 + 2 * i], f[3 + 2 * i]) for i in range(5)]
    consts = [(f[12 + 3 * i], f[13 + 3 * i], f[14 + 3 * i]) for i in range(4)]
    cap = (minm - maxm) * lodcap + maxm
    x = min((m - maxm) * lodscale + maxm, cap)
    if x >= minm:
        return curve[0][1]
    if x <= maxm:
        return curve[4][1]
    for i in (3, 2, 1):
        if x <= consts[i][2]:
            return x * consts[i][1] + consts[i][0]
    return x * consts[0][1] + consts[0][0]


def drawn(srf: _skd.SkdSurface, cutoff: float) -> tuple[int, int]:
    """(vertices, triangles) the engine draws of a simplified surface at ``cutoff``."""
    ci = srf.collapse_index
    n = len(ci)
    if n <= 3:
        return n, len(srf.triangles)
    if ci[2] < cutoff:
        return 0, 0
    rc = int(np.sum(ci >= cutoff))
    if rc == n:
        return n, len(srf.triangles)
    m = np.arange(n)
    for i in range(rc, n):
        m[i] = m[srf.collapse[i]]
    t = m[np.asarray(srf.triangles)]
    bad = (t[:, 0] == t[:, 1]) | (t[:, 1] == t[:, 2]) | (t[:, 2] == t[:, 0])
    first = int(np.argmax(bad)) if bad.any() else len(t)
    return rc, first


# --------------------------------------------------------------------------- assets


@dataclass
class LodResult:
    skd: bytes
    lod: Optional[bytes]
    perm: np.ndarray            # over all vertices in file order
    steps: int = 0
    stats: dict = field(default_factory=dict)


def _cache_dir() -> Path:
    from . import config
    d = Path(config.load().build_dir) / "lod"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lod_skd(name: str, data: bytes, tiki_scale: float = 1.0, cache: bool = True) -> LodResult:
    """Simplify an SKD's surfaces: new SKD bytes (vertices reordered, collapse data filled),
    its ``.lod`` and the vertex permutation. Already-simplified SKDs come back unchanged."""
    info = _skd.read_skd(data)
    n = sum(len(s.positions) for s in info.surfaces)
    if any(len(ci) and ci[0] != ci[-1] for _, ci in info.collapse):
        return LodResult(data, None, np.arange(n))
    key = hashlib.md5(data + struct.pack("<if", VERSION, tiki_scale) + struct.pack("<3f", TAU_PX, REF_WIDTH, REF_FOV)
                      ).hexdigest()
    cf = _cache_dir() / f"{key}.npz" if cache else None
    if cf is not None and cf.is_file():
        z = np.load(cf)
        lod = z["lod"].tobytes() if len(z["lod"]) else None
        return LodResult(z["skd"].tobytes(), lod, z["perm"], int(z["steps"]))
    surfs = [_skd.SkdSurface(s.name, s.positions, s.normals, s.uvs, s.triangles) for s in info.surfaces]
    res = simplify(surfs)
    allp = np.concatenate([np.asarray(s.positions, np.float64) for s in surfs]) * tiki_scale
    radius = _skd.bounds_radius(allp.min(0), allp.max(0))
    lod = lod_control(res.errors / 1.0 * tiki_scale, radius) if res.steps else None
    skd_bytes = _skd.build_skd(info.name, res.surfaces) if lod else data
    perm = res.perm if lod else np.arange(n)
    if cf is not None:
        np.savez(cf, skd=np.frombuffer(skd_bytes, np.uint8), lod=np.frombuffer(lod or b"", np.uint8), perm=perm,
                 steps=res.steps)
    return LodResult(skd_bytes, lod, perm, res.steps)


def apply_to_assets(assets: dict, tikis: Sequence[str], read: Callable[[str], Optional[bytes]],
                    log: Optional[Callable] = None) -> dict[str, np.ndarray]:
    """Simplify every SKD the ``tikis`` load, in place in ``assets`` (``<skd>`` replaced,
    ``<skd minus 'skd'>lod`` added). Returns ``{tiki: permutation}`` over the TIKI's
    vertices in ``staticlight.tiki_mesh`` order, for TIKIs whose vertices moved; apply it
    to per-vertex data (instance colours) made before."""
    import re
    keys = re.compile(r"^\s*(scale|path|skelmodel)\s+(\S+)", re.M)
    done: dict[str, LodResult] = {}
    out: dict[str, np.ndarray] = {}
    for tik in sorted(set(tikis)):
        name = tik if tik.startswith("models/") else "models/" + tik
        text = read(name)
        if text is None:
            continue
        kv = {"scale": "1", "path": str(Path(name).parent)}
        skds = []
        for k, v in keys.findall(text.decode("latin-1")):
            if k == "skelmodel":
                skds.append(v)
            else:
                kv[k] = v
        perms, base, moved = [], 0, False
        for s in skds:
            path = s if "/" in s else f"{kv['path'].rstrip('/')}/{s}"
            if path not in done:
                blob = read(path)
                if blob is None or path not in assets:
                    done[path] = None
                else:
                    r = lod_skd(path, blob, float(kv["scale"]))
                    done[path] = r
                    if r.lod is not None:
                        assets[path] = r.skd
                        # GetLODFile: strstr(path, "skd") -> "lod", cut there
                        assets[path[: path.find("skd")] + "lod"] = r.lod
            r = done[path]
            if r is None:
                blob = read(path)
                nv = sum(len(x.positions) for x in _skd.read_skd(blob).surfaces) if blob else 0
                perms.append(np.arange(nv) + base)
                base += nv
                continue
            perms.append(r.perm + base)
            base += len(r.perm)
            moved = moved or r.lod is not None
        if moved:
            out[tik] = np.concatenate(perms)
    if log:
        made = [r for r in done.values() if r is not None and r.lod is not None]
        log(f"== LOD: {len(made)} of {len(done)} SKDs simplified")
    return out
