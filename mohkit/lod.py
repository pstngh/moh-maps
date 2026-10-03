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
  in file order until the first one that became degenerate (two equal indices: one whose
  corners are different vertices at one position is drawn on), so triangles are sorted by
  the step at which they vanish. A surface whose ``collapseIndex[2] < cutoff`` is not drawn.
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

VERSION = 10                  # bump when the output changes (cache key)
TAU_PX = 2.0                  # target screen error (pixels)
REF_WIDTH = 1920.0            # ... at this screen width
REF_FOV = 80.0                # ... and this fovX
REF_LODSCALE = 0.55           # retail high preset r_lodscale
REF_LODCAP = 0.55             # retail high preset r_lodcap
PLAYER_LODSCALE = 0.45        # the owner's own settings (r_lodscale, r_lodcap): installs must look
PLAYER_LODCAP = 0.35          # and run right there too (``propcost --player``, ``ab --cvar``)
VANISH_FOV = 90.0             # fovX for vanish distances (80 at 4:3, ~96 at 16:9 with cg_fov 80)
MAX_DISTANCE = 12000.0        # farther than any view in a +-8192 map: the curve ends here
WELD = 1e-3                   # positions closer than this (units) are one position
SEAM_WEIGHT = 1.0             # penalty plane weight (x edge length^2) on open and seam edges
FLIP_DOT = 0.2                # refuse collapses that turn a triangle more than ~78 degrees
FREE_ERROR = 0.01             # collapses below this error (units) are made even at full detail
COLOR_STEP = 12.0             # a vertex-colour change of this many levels (0-255) costs a collapse its length
COLOR_INSTANCES = 8           # instances whose vertex colours a shared mesh's collapses must keep
ATTR_FAR = 0.0                # how much texture slide and shade change count in the distance curve


@dataclass
class Simplified:
    surfaces: list[_skd.SkdSurface]     # vertices and triangles reordered (with collapse data)
    perms: list[np.ndarray]             # per surface: new vertex i was old vertex perm[i]
    errors: np.ndarray                  # error (units) of collapse steps 1..K, non-decreasing
    steps: int = 0
    geometric: Optional[np.ndarray] = None   # the same without texture slide and shade change

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


def simplify(surfaces: Sequence[_skd.SkdSurface], colors: Optional[Sequence[np.ndarray]] = None,
             color_step: float = COLOR_STEP) -> Simplified:
    """Collapse sequence for a model's surfaces (one global step numbering, as the engine
    compares every surface's ``collapseIndex`` with one cutoff). ``colors``: per surface, the
    vertex colours of the instances drawn with it (instances x vertices x 3, 0-255): a
    collapse that changes how a surviving triangle shades by ``color_step`` levels costs the
    move's length (less in proportion), like the texture slide: a visibly wrong shade is
    wrong wherever the patch it covers is a pixel or more (converted props carry CS:GO's
    baked per-vertex lighting, and a flat panel collapsed to a few triangles spread its
    darkest corners over all of it). Slides and shade changes add up along collapse chains."""
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
    # per surface, per vertex: the instances' colours flattened (r, g, b, r, g, b, ...)
    cols = None
    if colors is not None and len(colors) == ns:
        cols = []
        for s_, c in enumerate(colors):
            c = np.asarray(c, np.float64)
            if c.ndim != 3 or c.shape[1] != counts[s_] or not c.shape[0]:
                cols = None
                break
            cols.append(np.transpose(c, (1, 0, 2)).reshape(counts[s_], -1).tolist())
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
    geo: list[float] = []

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

    def pick(s: int, a: int, q: int) -> int:
        """The copy of position q in surface s that vertex a moves onto: the one it shares a
        triangle with, else the nearest in texture space."""
        po = pos_of[s]
        for f in vfaces[s][a]:
            for v in fvl[f]:
                if po[v] == q:
                    return v
        uv = uvs[s]
        ua = uv[a]
        return min(copies[q][s], key=lambda v: (uv[v][0] - ua[0]) ** 2 + (uv[v][1] - ua[1]) ** 2)

    def uv_slide(p: int, q: int) -> float:
        """How far (world units) the texture slides on the triangles that survive moving p
        onto q: each keeps its corners' texture coordinates, so the moved corner takes q's
        copy's, where the triangle's old mapping would have put another (planar collapses
        cost no geometric error but smear tiled or atlased textures)."""
        worst = 0.0
        X = Pl[q]
        move = math.dist(Pl[p], X)
        for s, vs in copies[p].items():
            po = pos_of[s]
            uv = uvs[s]
            for a in vs:
                bv = pick(s, a, q)
                ub = uv[bv]
                for f in vfaces[s][a]:
                    vv = fvl[f]
                    if po[vv[0]] == q or po[vv[1]] == q or po[vv[2]] == q:
                        continue            # the triangle dies
                    i = vv.index(a)
                    o1, o2 = vv[(i + 1) % 3], vv[(i + 2) % 3]
                    A, B, C = Pl[p], Pl[po[o1]], Pl[po[o2]]
                    e0 = (B[0] - A[0], B[1] - A[1], B[2] - A[2])
                    e1 = (C[0] - A[0], C[1] - A[1], C[2] - A[2])
                    e2 = (X[0] - A[0], X[1] - A[1], X[2] - A[2])
                    d00 = e0[0] * e0[0] + e0[1] * e0[1] + e0[2] * e0[2]
                    d01 = e0[0] * e1[0] + e0[1] * e1[1] + e0[2] * e1[2]
                    d11 = e1[0] * e1[0] + e1[1] * e1[1] + e1[2] * e1[2]
                    den = d00 * d11 - d01 * d01
                    ua, u1, u2 = uv[a], uv[o1], uv[o2]
                    uva = abs((u1[0] - ua[0]) * (u2[1] - ua[1]) - (u1[1] - ua[1]) * (u2[0] - ua[0]))
                    if den <= 1e-12:
                        continue
                    d20 = e2[0] * e0[0] + e2[1] * e0[1] + e2[2] * e0[2]
                    d21 = e2[0] * e1[0] + e2[1] * e1[1] + e2[2] * e1[2]
                    wb = (d11 * d20 - d01 * d21) / den
                    wc = (d00 * d21 - d01 * d20) / den
                    wa = 1.0 - wb - wc
                    du = wa * ua[0] + wb * u1[0] + wc * u2[0] - ub[0]
                    dv = wa * ua[1] + wb * u1[1] + wc * u2[1] - ub[1]
                    if uva > 1e-12:
                        # the texture offset back through the triangle's own mapping (texture
                        # space -> its two edges), so stretched mappings (around a wire vs
                        # along it) weigh each direction right
                        d0x, d0y = u1[0] - ua[0], u1[1] - ua[1]
                        d1x, d1y = u2[0] - ua[0], u2[1] - ua[1]
                        det = d0x * d1y - d1x * d0y
                        sx = (d1y * du - d1x * dv) / det
                        tx = (d0x * dv - d0y * du) / det
                        wx = sx * e0[0] + tx * e1[0]
                        wy = sx * e0[1] + tx * e1[1]
                        wz = sx * e0[2] + tx * e1[2]
                        worst = max(worst, math.sqrt(wx * wx + wy * wy + wz * wz))
                    if cols is not None:
                        cs_ = cols[s]
                        ca, c1, c2, cb = cs_[a], cs_[o1], cs_[o2], cs_[bv]
                        dc = max(abs(wa * x + wb * y + wc * z - w) for x, y, z, w in zip(ca, c1, c2, cb))
                        worst = max(worst, min(1.0, dc / color_step) * move)
        return worst

    # texture slide and shade change accumulated at each position: each collapse is judged
    # against the mesh as it is, so small changes would add up unseen along a chain
    acc = [0.0] * npos
    k = 0
    while heap:
        c, p, q, sp, sq = heapq.heappop(heap)
        if not alive[p] or not alive[q] or stamp[p] != sp or stamp[q] != sq:
            continue
        if not valid(p, q):
            continue
        # the texture slide counts like geometric error: raise the cost and requeue
        slide = uv_slide(p, q)
        if slide <= 1e-3:                   # float32 noise of exact mappings
            slide = 0.0
        drift = max(acc[p] + slide, acc[q]) if (slide or acc[p]) else acc[q]
        if drift > 0.0:
            need = drift * drift * max(Wl[p], 1e-12)
            if need > c * (1.0 + 1e-9) + 1e-12:
                heapq.heappush(heap, (need, p, q, sp, sq))
                continue
        acc[q] = max(acc[q], acc[p] + slide)
        k += 1
        errors.append(math.sqrt(max(c, 0.0) / max(Wl[p], 1e-12)))
        geo.append(math.sqrt(max(cost(p, q), 0.0) / max(Wl[p], 1e-12)))
        # move every copy of p onto a copy of q in the same surface (``pick``)
        for s, vs in copies[p].items():
            for a in vs:
                b = pick(s, a, q)
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
        # that collapsed away would leave its last vertices drawn forever). Each points at
        # another live copy of its position in the surface: the engine keeps drawing a dead
        # triangle whose vertices coincide only in position (a seam: different indices) until
        # it meets an index-degenerate one, so its vertices must stay together. Pointed at
        # vertex 0 instead, such a sliver stretched into a shard across the model (de_nuke's
        # grey panels). With no copy left they go to vertex 0, all together.
        for s, v in sorted(orphans):
            if step_of[s][v] < 0:
                step_of[s][v] = k
                r = pos_of[s][v]
                cs = copies[r].get(s)
                if cs is not None:
                    cs.discard(v)
                    if not cs:
                        del copies[r][s]
                cs = copies[r].get(s)
                target[s][v] = min(cs) if cs else -2
        qq, qp = Ql[q], Ql[p]
        Ql[q] = [qq[i] + qp[i] for i in range(10)]
        Wl[q] += Wl[p]
        alive[p] = False
        stamp[q] += 1
        push_edges(q)

    K = k
    err = np.maximum.accumulate(np.asarray(errors, np.float64)) if errors else np.zeros(0)
    geo_err = np.maximum.accumulate(np.asarray(geo, np.float64)) if geo else np.zeros(0)
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
        # that collapse) follows the target's own target, so it stays where its target goes
        for _ in range(64):
            stale = (tg >= 0) & (cidx[np.maximum(tg, 0)] <= cidx)
            if not stale.any():
                break
            nxt = tg[np.maximum(tg, 0)]
            tg = np.where(stale, nxt, tg)
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
        # triangles of no area from the start (two corners at one position: strip leftovers)
        # are left out: the engine only stops at index-degenerate triangles, so it could reach
        # one whose lone vertex was dropped (pointing at vertex 0) and draw it as a shard
        keep = [f for f in range(nt) if fd[f] != 0] or list(range(nt))
        torder = np.array(sorted(keep, key=lambda f: (-fd[f], f)), np.int64)
        tris = newi[np.asarray(srf.triangles, np.int64).reshape(-1, 3)[torder]] if len(torder) else \
            np.zeros((0, 3), np.int64)
        ns_ = _skd.SkdSurface(srf.name, np.asarray(srf.positions)[perm], np.asarray(srf.normals)[perm],
                              np.asarray(srf.uvs)[perm], tris)
        ns_.collapse = col.astype(np.int32)
        ns_.collapse_index = cidx[perm].astype(np.int32)
        out.append(ns_)
        perms.append(perm)
    return Simplified(out, perms, err, K, geo_err)


# --------------------------------------------------------------------------- measured error


def _surface_samples(pos: np.ndarray, tris: np.ndarray, h: float) -> np.ndarray:
    """Points on triangles: along each edge about ``h`` apart, and inside, one per ``h``
    squared of area (a Halton pattern), so thin triangles are covered by their edges."""
    if not len(tris):
        return np.zeros((0, 3))
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    out = []
    for p0, p1 in ((a, b), (b, c), (c, a)):
        n = np.clip(np.ceil(np.linalg.norm(p1 - p0, axis=1) / h).astype(np.int64), 1, 4096)
        idx = np.repeat(np.arange(len(n)), n)
        t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n, n)
        out.append(p0[idx] + (p1[idx] - p0[idx]) * t[:, None])
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    m = np.clip(np.floor(area / (h * h)).astype(np.int64), 0, 1 << 16)
    if m.sum():
        idx = np.repeat(np.arange(len(m)), m)
        j = np.arange(m.sum()) - np.repeat(np.cumsum(m) - m, m) + 1
        r1, r2 = _halton(j, 2), _halton(j, 3)
        sq = np.sqrt(r1)[:, None]
        out.append(a[idx] * (1 - sq) + b[idx] * (sq * (1 - r2[:, None])) + c[idx] * (sq * r2[:, None]))
    return np.concatenate(out)


def _halton(i: np.ndarray, base: int) -> np.ndarray:
    f, r, i = 1.0, np.zeros(len(i)), i.copy()
    while i.any():
        f /= base
        r += f * (i % base)
        i //= base
    return r


class _NearIndex:
    """Distance from query points to a point set, exact up to ``cell`` (27 neighbouring grid
    cells), ``cell`` or more beyond it."""

    def __init__(self, pts: np.ndarray, cell: float):
        self.cell = float(cell)
        self.pts = pts
        keys = self._keys(np.floor(pts / self.cell).astype(np.int64))
        self.order = np.argsort(keys, kind="stable")
        self.sorted = keys[self.order]

    @staticmethod
    def _keys(ijk: np.ndarray) -> np.ndarray:
        ijk = ijk + (1 << 20)
        return (ijk[:, 0] << 42) | (ijk[:, 1] << 21) | ijk[:, 2]

    def distance(self, q: np.ndarray, chunk: int = 4096) -> np.ndarray:
        out = np.full(len(q), self.cell)
        offs = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], np.int64)
        for s0 in range(0, len(q), chunk):
            qq = q[s0:s0 + chunk]
            base = np.floor(qq / self.cell).astype(np.int64)
            best = np.full(len(qq), np.inf)
            for o in offs:
                k = self._keys(base + o)
                lo = np.searchsorted(self.sorted, k, "left")
                hi = np.searchsorted(self.sorted, k, "right")
                cnt = hi - lo
                if not cnt.any():
                    continue
                qi = np.repeat(np.arange(len(qq)), cnt)
                starts = np.repeat(lo - np.concatenate([[0], np.cumsum(cnt)[:-1]]), cnt)
                si = self.order[starts + np.arange(cnt.sum())]
                d2 = ((qq[qi] - self.pts[si]) ** 2).sum(1)
                np.minimum.at(best, qi, d2)
            out[s0:s0 + chunk] = np.minimum(np.sqrt(best), self.cell)
        return out


def measured_errors(surfaces: Sequence[_skd.SkdSurface], errors: np.ndarray, levels: int = 16) -> np.ndarray:
    """``errors`` (one per collapse step, non-decreasing) raised to what the engine would
    really draw: at ``levels`` steps the surfaces are replayed like ``RB_StaticMesh`` and
    sampled, and the farthest sample from the original surface is that step's error (less the
    sampling slack); steps in between take the next measured one. The quadric error is the
    distance to the original *planes*, so collapses that close the gaps of a flat open object
    (a railing, a fence, a grate) or slide along a crease past where the surface ends cost
    nothing; measured, they cost the size of what they cover. A safety net: on every model
    checked (2026-10-02: a merged railing, two wire clusters) it returned exactly the quadric
    errors. The railing that was drawn in its coarsest form at every distance (a few
    triangles, its grate smeared grey) was fixed by the texture-slide cost instead (free
    collapses at base error 4: 1,631 -> 1,230). Dense interior sampling (h = sqrt(area /
    60000)) took minutes per mesh; edge + Halton samples of moved triangles, capped at 20k
    queries a level, take ~0.6 s."""
    K = len(errors)
    if K == 0:
        return errors
    full = []
    for srf in surfaces:
        full.append((np.asarray(srf.positions, np.float64), np.asarray(srf.triangles, np.int64)))
    area = sum(0.5 * np.linalg.norm(np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]]), axis=1).sum()
               for p, t in full if len(t))
    perimeter = sum(sum(np.linalg.norm(p[t[:, (k + 1) % 3]] - p[t[:, k]], axis=1).sum() for k in range(3))
                    for p, t in full if len(t))
    h = max(1.0, math.sqrt(max(area, 1e-9) / 20000.0), perimeter / 60000.0)
    orig = np.concatenate([_surface_samples(p, t, h) for p, t in full])
    if not len(orig):
        return errors
    # exact to 3h on all samples; beyond, on one sample per 8h cell (slack 7h), up to 48h,
    # and beyond that the error is just "large" (48h)
    fine = _NearIndex(orig, 3 * h)
    _, one = np.unique(np.floor(orig / (8 * h)).astype(np.int64), axis=0, return_index=True)
    coarse = _NearIndex(orig[np.sort(one)], 48 * h)
    slack = 0.75 * h          # original samples are about h apart
    steps = np.unique(np.round(np.geomspace(1, K, levels)).astype(np.int64))
    meas = np.zeros(len(steps))
    for n, k in enumerate(steps):
        cut = k + 1                       # steps 1..k made
        pts = []
        for srf, (p, _) in zip(surfaces, full):
            ci = np.asarray(srf.collapse_index)
            if not len(ci) or ci[2] < cut:
                continue
            rc = int((ci >= cut).sum())
            m = np.arange(len(ci))
            col = np.asarray(srf.collapse)
            for i in range(rc, len(ci)):
                m[i] = m[col[i]]
            t0 = np.asarray(srf.triangles, np.int64)
            t = m[t0]
            bad = (t[:, 0] == t[:, 1]) | (t[:, 1] == t[:, 2]) | (t[:, 2] == t[:, 0])
            end = int(np.argmax(bad)) if bad.any() else len(t)
            moved = (t[:end] != t0[:end]).any(axis=1)     # untouched triangles are on the surface
            if moved.any():
                pts.append(_surface_samples(p, t[:end][moved], 2 * h))
        if not pts:
            continue
        q = np.concatenate(pts)
        if len(q) > 20000:
            q = q[:: int(math.ceil(len(q) / 20000))]
        d = fine.distance(q) - slack
        far = d >= fine.cell - slack
        if far.any():
            d[far] = np.maximum(coarse.distance(q[far]) - 7 * h, fine.cell - slack)
        meas[n] = max(0.0, float(d.max()))
    # each step takes the next measured step's error (an upper bound when error grows)
    nxt = np.searchsorted(steps, np.arange(1, K + 1), side="left")
    nxt = np.minimum(nxt, len(steps) - 1)
    meas_steps = np.maximum.accumulate(meas)[nxt]
    return np.maximum.accumulate(np.maximum(np.asarray(errors, np.float64), meas_steps))


def metric_scale() -> float:
    """Screen pixels per unit of (error / R) per unit of the engine's raw metric ``m``
    (``ProjectRadius``: m = R * (100 / fovX) / distance), at the reference view."""
    px_per_rad = (REF_WIDTH / 2) / math.tan(math.radians(REF_FOV) / 2)
    return px_per_rad / (100.0 / REF_FOV)


def cutoff_at(errors: np.ndarray, radius: float, m: float, tau: float = TAU_PX) -> float:
    """Highest cutoff (1 + steps made) whose error stays under ``tau`` pixels at raw metric ``m``."""
    allowed = tau * radius / (metric_scale() * max(m, 1e-9))
    return 1.0 + float(np.searchsorted(errors, allowed, side="right"))


def _fit_under(xs: np.ndarray, true: np.ndarray, idx: Sequence[int]) -> np.ndarray:
    """Values at the curve points ``xs[idx]`` (near to far) whose straight segments (in the
    engine's metric, as it interpolates) stay at or under ``true`` on every grid point: each
    point's value is lowered until the segment before it fits."""
    vals = [float(true[idx[0]])]
    for a, b in zip(idx, idx[1:]):
        xa, xb, va = xs[a], xs[b], vals[-1]
        vb = float(true[b])
        g = np.arange(a + 1, b)
        if len(g):
            t = (xa - xs[g]) / (xa - xb)
            vb = min(vb, float(np.min(va + (true[g] - va) / t)))
        vals.append(max(vb, va))
    return np.array(vals)


def lod_control(errors: np.ndarray, radius: float, tau: float = TAU_PX, vanish: float = 0.0,
                base_error: float = FREE_ERROR, free_errors: Optional[np.ndarray] = None) -> Optional[bytes]:
    """``.lod`` bytes (lodControl_t) for a model's collapse errors, or None when nothing
    collapses. The curve keeps error <= ``tau`` pixels at its points, starts at full detail
    (only the error-free collapses, < ``FREE_ERROR`` units) where the high preset's cap lands
    for near objects, and ends at ``MAX_DISTANCE``. With ``vanish`` (an eye distance, e.g. a
    CS:GO prop fade) its last point drops every surface from there on: the engine pivots
    ``r_lodscale`` on maxMetric (m' = (m - maxM) * lodscale + maxM), so maxMetric = R * (100 /
    fovX) / vanish holds at any detail preset (fovX ``VANISH_FOV``)."""
    K = len(errors)
    if K == 0 or radius <= 0:
        return None
    P, k, s = metric_scale(), 100.0 / REF_FOV, REF_LODSCALE
    # the free level (made at every distance) may differ from the curve's errors: up close
    # nothing may change that shows, texture and shading included (``free_errors``)
    free = 1.0 + float(np.searchsorted(errors if free_errors is None else free_errors, base_error, side="right"))
    m_far = radius * k / MAX_DISTANCE
    m_v = radius * (100.0 / VANISH_FOV) / vanish if vanish > 0 else 0.0
    if m_v <= m_far:
        m_v = 0.0                                     # vanishes beyond any view: ignore
    m_end = m_v * 1.02 if m_v else m_far
    nz = errors[errors > base_error]
    m_first = tau * radius / (P * nz[0]) if len(nz) else m_end * 4   # the first real collapse shows here
    m_first = max(m_first, m_end * 1.5)
    grid = np.exp(np.linspace(math.log(m_first), math.log(m_end), 32))
    true = np.maximum([cutoff_at(errors, radius, m, tau) for m in grid], free)
    maxm = m_v if m_v else m_end
    xs = (grid - maxm) * s + maxm                    # where the engine evaluates the curve
    best, best_idx, best_vals = -1.0, None, None
    inner = [(i,) for i in range(1, len(grid) - 1)] if m_v else \
            [(i, j) for i in range(1, len(grid) - 2) for j in range(i + 1, len(grid) - 1)]
    for mid in inner:
        idx = [0, *mid, len(grid) - 1]
        vals = _fit_under(xs, true, idx)
        area = np.interp(xs[::-1], xs[idx][::-1], vals[::-1]).sum()
        if area > best:
            best, best_idx, best_vals = area, idx, vals
    px = [float(xs[i]) for i in best_idx]
    pv = [float(v) for v in best_vals]
    if m_v:
        px.append(m_v)
        pv.append(float(K + 2))                      # above every collapseIndex: nothing drawn
    elif pv[-1] <= 1.0:
        return None
    minm = maxm + (px[0] - maxm) / REF_LODCAP         # the high preset's cap lands on the first point
    pos = [0.0] + [(minm - x) / (minm - maxm) for x in px]
    val = [free] + pv
    for i in range(1, 5):
        pos[i] = max(pos[i], pos[i - 1] + 1e-5)
        val[i] = max(val[i], val[i - 1])
    pos[4] = 1.0
    consts = []
    for i in range(4):
        common = (val[i + 1] - val[i]) / (pos[i + 1] - pos[i])
        base = val[i] + (minm / (minm - maxm) - pos[i]) * common
        scale = common / (maxm - minm)
        cutoff = minm + (maxm - minm) * pos[i]
        consts += [base, scale, cutoff]
    data = [minm, maxm] + [x for pv_ in zip(pos, val) for x in pv_] + consts
    return struct.pack("<24f", *data)


def read_lod(data: bytes) -> dict:
    f = struct.unpack("<12f", data[:48])
    return {"minMetric": f[0], "maxMetric": f[1], "curve": [(f[2 + 2 * i], f[3 + 2 * i]) for i in range(5)]}


EngineTable = tuple[float, float, list]     # (minMetric, maxMetric, 5 curve points (pos, val))


def engine_table(lod: Optional[bytes], lod_index: Sequence[int] = ()) -> EngineTable:
    """The LOD table ``GetLODFile`` (``tiki/tiki_skel.cpp``) builds for a model that can
    simplify: a ``.lod`` file's first 48 bytes (minMetric, maxMetric, 5 curve points: all a
    stock file holds; mohkit's files and some stock ones append the constants, which the
    engine recomputes anyway), else a default curve from the SKD's ``lodIndex``."""
    if lod:
        c = read_lod(lod)
        return c["minMetric"], c["maxMetric"], c["curve"]
    li = list(lod_index) + [0] * (11 - len(lod_index))
    # The engine walks down from lodIndex[10], one past the array: it reads the next field
    # (numBoxes, 0 for a static model), so the loop stops at once and the far value is 0.
    i = 10
    while li[i] > li[3] and i > 2:
        i -= 1
    v = float(li[1])
    return 1.0, 0.2, [(0.0, 0.0), (0.5, v), (0.8, v), (0.95, v), (1.0, float(li[i]))]


def engine_cutoff(lod, m: float, lodscale: float = REF_LODSCALE, lodcap: float = REF_LODCAP) -> float:
    """The cutoff ``GetLodCutoff`` returns for metric ``m``; ``lod`` is a ``.lod`` file's bytes
    or an ``engine_table``. Constants as ``TIKI_CalcLodConsts`` computes them at load."""
    minm, maxm, curve = engine_table(lod) if isinstance(lod, (bytes, bytearray)) else lod
    consts = []
    for i in range(4):
        common = (curve[i + 1][1] - curve[i][1]) / (curve[i + 1][0] - curve[i][0])
        consts.append((curve[i][1] + (minm / (minm - maxm) - curve[i][0]) * common, common / (maxm - minm),
                       minm + (maxm - minm) * curve[i][0]))
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


def can_lod(surfaces) -> bool:
    """``GetLODFile`` builds a table only when a surface's collapse index changes."""
    return any(getattr(s, "collapse_index", None) is not None and len(s.collapse_index)
               and s.collapse_index[0] != s.collapse_index[-1] for s in surfaces)


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


def lod_skd(name: str, data: bytes, tiki_scale: float = 1.0, cache: bool = True, vanish: float = 0.0,
            tau: float = TAU_PX, base_error: float = FREE_ERROR,
            colors: Optional[Sequence[np.ndarray]] = None) -> LodResult:
    """Simplify an SKD's surfaces: new SKD bytes (vertices reordered, collapse data filled),
    its ``.lod`` (with a ``vanish`` distance, see ``lod_control``) and the vertex permutation.
    Already-simplified SKDs come back unchanged. The simplification is cached (it doesn't
    depend on the curve); the curve is made each time."""
    info = _skd.read_skd(data)
    n = sum(len(s.positions) for s in info.surfaces)
    if any(len(ci) and ci[0] != ci[-1] for _, ci in info.collapse):
        return LodResult(data, None, np.arange(n))
    # colours: the instances' vertex colours over the SKD's vertices (file order), n x 3 each
    surf_cols = None
    if colors:
        cs = np.stack([np.nan_to_num(np.asarray(c, np.float64), nan=128.0) for c in colors])   # inst x n x 3
        if cs.shape[1] == n:
            q = np.clip(np.round(cs), 0, 255).astype(np.uint8)
            offs = np.cumsum([0] + [len(x.positions) for x in info.surfaces])
            surf_cols = [q[:, offs[i]:offs[i + 1]] for i in range(len(info.surfaces))]
    key = hashlib.md5(data + struct.pack("<if", VERSION, tiki_scale)
                      + (b"".join(c.tobytes() for c in surf_cols) if surf_cols else b"")).hexdigest()
    cf = _cache_dir() / f"{key}.npz" if cache else None
    if cf is not None and cf.is_file():
        z = np.load(cf)
        skd_bytes, perm, errors, radius, steps = (z["skd"].tobytes(), z["perm"], z["errors"], float(z["radius"]),
                                                  int(z["steps"]))
        geometric = z["geometric"]
    else:
        surfs = [_skd.SkdSurface(s.name, s.positions, s.normals, s.uvs, s.triangles) for s in info.surfaces]
        res = simplify(surfs, surf_cols)
        allp = np.concatenate([np.asarray(s.positions, np.float64) for s in surfs]) * tiki_scale
        radius = _skd.bounds_radius(allp.min(0), allp.max(0))
        geometric = measured_errors(res.surfaces, res.geometric) * tiki_scale
        errors, steps = np.maximum(res.errors * tiki_scale, geometric), res.steps
        skd_bytes = _skd.build_skd(info.name, res.surfaces) if steps else data
        perm = res.perm if steps else np.arange(n)
        if cf is not None:
            np.savez(cf, skd=np.frombuffer(skd_bytes, np.uint8), perm=perm, errors=errors, geometric=geometric,
                     radius=radius, steps=steps)
    # with distance, geometric error decides (shading and texture detail go with the pixels;
    # counting them there kept 3.5x the vertices on de_nuke); the free level keeps them
    curve = np.maximum(geometric, ATTR_FAR * errors) if ATTR_FAR else geometric
    lod = lod_control(curve, radius, tau=tau, vanish=vanish, base_error=base_error,
                      free_errors=errors) if steps else None
    if lod is None:
        return LodResult(data, None, np.arange(n), steps)
    return LodResult(skd_bytes, lod, perm, steps)


def vanish_by_tiki(instances) -> dict[str, float]:
    """Per model, the eye distance from which none of its instances needs drawing: the
    largest instance ``fade``, or 0 when any instance never fades."""
    out: dict[str, float] = {}
    for i in instances:
        f = float(getattr(i, "fade", 0.0) or 0.0)
        if i.model not in out:
            out[i.model] = f
        elif out[i.model] > 0:
            out[i.model] = 0.0 if f <= 0 else max(out[i.model], f)
    return out


def apply_to_assets(assets: dict, tikis: Sequence[str], read: Callable[[str], Optional[bytes]],
                    log: Optional[Callable] = None, vanish: Optional[dict] = None,
                    tau: float = TAU_PX, base_error: float = FREE_ERROR,
                    colors: Optional[dict] = None) -> dict[str, np.ndarray]:
    """Simplify every SKD the ``tikis`` load, in place in ``assets`` (``<skd>`` replaced,
    ``<skd minus 'skd'>lod`` added). Returns ``{tiki: permutation}`` over the TIKI's
    vertices in ``staticlight.tiki_mesh`` order, for TIKIs whose vertices moved; apply it
    to per-vertex data (instance colours) made before. ``colors``: ``{tiki: [instance
    colours over the TIKI's vertices (n x 3) or None, ...]}``; an SKD's collapses keep the
    shading of up to ``COLOR_INSTANCES`` of the instances that draw it (``simplify``)."""
    import re
    keys = re.compile(r"^\s*(scale|path|skelmodel)\s+(\S+)", re.M)
    done: dict[str, LodResult] = {}
    out: dict[str, np.ndarray] = {}
    vanish = vanish or {}
    skd_colors: dict[str, list] = {}
    nv_cache: dict[str, int] = {}
    for tik in sorted(set(tikis)) if colors else ():
        insts = [c for c in colors.get(tik) or () if c is not None]
        name = tik if tik.startswith("models/") else "models/" + tik
        text = read(name) if insts else None
        if text is None:
            continue
        t = text.decode("latin-1")
        path = (re.findall(r"^\s*path\s+(\S+)", t, re.M) or [str(Path(name).parent)])[0]
        base = 0
        for sk in re.findall(r"^\s*skelmodel\s+(\S+)", t, re.M):
            sp = sk if "/" in sk else f"{path.rstrip('/')}/{sk}"
            if sp not in nv_cache:
                blob = read(sp)
                nv_cache[sp] = sum(len(x.positions) for x in _skd.read_skd(blob).surfaces) if blob else 0
            nv = nv_cache[sp]
            skd_colors.setdefault(sp, []).extend(np.asarray(c)[base:base + nv] for c in insts if len(c) >= base + nv)
            base += nv
    for sp, lst in skd_colors.items():
        if len(lst) > COLOR_INSTANCES:
            skd_colors[sp] = [lst[i] for i in np.linspace(0, len(lst) - 1, COLOR_INSTANCES).round().astype(int)]
    # an SKD vanishes where every TIKI that loads it has (skins of one mesh share it)
    skd_vanish: dict[str, float] = {}
    for tik in sorted(set(tikis)):
        name = tik if tik.startswith("models/") else "models/" + tik
        text = read(name)
        if text is None:
            continue
        t = text.decode("latin-1")
        path = (re.findall(r"^\s*path\s+(\S+)", t, re.M) or [str(Path(name).parent)])[0]
        v = float(vanish.get(tik, 0.0) or 0.0)
        for sk in re.findall(r"^\s*skelmodel\s+(\S+)", t, re.M):
            sp = sk if "/" in sk else f"{path.rstrip('/')}/{sk}"
            prev = skd_vanish.get(sp)
            skd_vanish[sp] = v if prev is None else (0.0 if min(prev, v) <= 0 else max(prev, v))
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
                    r = lod_skd(path, blob, float(kv["scale"]), vanish=skd_vanish.get(path, 0.0), tau=tau,
                                base_error=base_error, colors=skd_colors.get(path))
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
