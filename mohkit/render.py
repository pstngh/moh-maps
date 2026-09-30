"""Top-down plan images of a MapFile (needs Pillow).

Upward-facing brush faces are painted lowest-first, shaded by height, so the
image reads like a height map of walkable surfaces. Spawns are drawn as arrows
(blue allied, red axis, white DM, green spectator start), lights as yellow dots.
Caulk/tool-only faces are skipped; sky ceilings are ignored because only faces
with an upward normal are drawn.
"""

from __future__ import annotations

import math
from typing import Optional

from . import geom
from .mapfile import Brush, MapFile, Patch, Terrain

SPAWN_COLORS = {
    "info_player_deathmatch": (240, 240, 240),
    "info_player_allied": (80, 140, 255),
    "info_player_axis": (255, 80, 70),
    "info_player_start": (80, 230, 110),
}


def plan(m: MapFile, out: str, size: int = 1600, zmin: Optional[float] = None, zmax: Optional[float] = None,
         margin: int = 24, title: str = "") -> str:
    from PIL import Image, ImageDraw

    polys: list[tuple[float, list[tuple[float, float]], bool]] = []
    for _, p in m.iter_prims():
        if isinstance(p, Brush):
            for f, w in zip(p.faces, p.windings()):
                if len(w) < 3 or f.plane.normal[2] <= 0.3 or f.shader.lower().startswith(("common/", "sky/")):
                    continue
                z = max(pt[2] for pt in w)
                polys.append((z, [(pt[0], pt[1]) for pt in w], False))
        elif isinstance(p, Patch):
            for row in range(p.rows - 1):
                for col in range(p.cols - 1):
                    q = [p.ctrl[row][col], p.ctrl[row][col + 1], p.ctrl[row + 1][col + 1], p.ctrl[row + 1][col]]
                    polys.append((max(c[2] for c in q), [(c[0], c[1]) for c in q], False))
        elif isinstance(p, Terrain):
            ox, oy, oz = p.origin
            for r in range(p.height - 1):
                for c in range(p.width - 1):
                    h = oz + p.samples[r * p.width + c].height
                    polys.append((h, [(ox + c * 64, oy + r * 64), (ox + c * 64 + 64, oy + r * 64),
                                      (ox + c * 64 + 64, oy + r * 64 + 64), (ox + c * 64, oy + r * 64 + 64)], False))
    if zmin is not None:
        polys = [q for q in polys if q[0] >= zmin]
    if zmax is not None:
        polys = [q for q in polys if q[0] <= zmax]
    if not polys:
        raise ValueError("nothing to draw")
    xs = [x for _, pts, _ in polys for x, _ in pts]
    ys = [y for _, pts, _ in polys for _, y in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    s = (size - 2 * margin) / max(x1 - x0, y1 - y0, 1)
    w, h = int((x1 - x0) * s) + 2 * margin, int((y1 - y0) * s) + 2 * margin + 20
    img = Image.new("RGB", (w, h), (18, 18, 22))
    d = ImageDraw.Draw(img)

    def tx(x, y):
        return (margin + (x - x0) * s, h - margin - (y - y0) * s)

    zs = [q[0] for q in polys]
    lo, hi = min(zs), max(zs)
    for z, pts, tool in sorted(polys, key=lambda q: q[0]):
        t = 0.0 if hi == lo else (z - lo) / (hi - lo)
        base = (int(60 + 160 * t), int(70 + 150 * t), int(90 + 120 * t))
        if tool:
            base = (70, 40, 70)
        d.polygon([tx(x, y) for x, y in pts], fill=base, outline=(30, 30, 36))
    for e in m.entities:
        o = e.origin()
        if o is None:
            continue
        cn = e.classname
        px, py = tx(o[0], o[1])
        if cn in SPAWN_COLORS:
            yaw = math.radians(float(e.get("angle", "0") or 0))
            col = SPAWN_COLORS[cn]
            r = 7
            d.ellipse((px - r, py - r, px + r, py + r), outline=col, width=2)
            d.line((px, py, px + math.cos(yaw) * 14, py - math.sin(yaw) * 14), fill=col, width=2)
        elif cn == "light":
            d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(255, 220, 90))
        elif cn.startswith("static_"):
            d.rectangle((px - 2, py - 2, px + 2, py + 2), outline=(170, 120, 60))
    label = title or m.worldspawn.get("message", "")
    d.text((8, 4), f"{label}  x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}] z[{lo:.0f},{hi:.0f}]  {1/s:.1f} u/px",
           fill=(220, 220, 220))
    img.save(out)
    return out
