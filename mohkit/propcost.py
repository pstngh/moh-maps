"""What the renderer draws of a map's static models from a camera, without running the game.

Static models cost the back end per drawn vertex (``RB_StaticMesh`` copies each one into
``tess`` every frame, ``renderergl1/tr_model.cpp``): on de_nuke's stock-like build they were
2.0 of 3.7 ms per frame (``r_drawstaticmodelpoly 0`` vs on), the world 1.3 ms. ``estimate``
replays what ``R_AddStaticModelSurfaces`` (``tr_staticmodels.cpp``) and ``RB_StaticMesh`` do
for each model of a packaged map: the sphere test against the four frustum planes (the
model's SKC radius times its scale, at its origin), the LOD metric ``R * (100 / fovX) / d``
(``ProjectRadius``), the ``.lod`` curve's cutoff (``lod.engine_cutoff``: r_lodscale and
r_lodcap of the high preset) and the vertices and triangles left at that cutoff
(``lod.drawn``). It answers "which models make this view slow" and lets prop settings be
compared offline; the game's own ``r_speeds`` (``mohkit csgo --perf``) stays the judge.
"""

from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from . import lod as _lod
from .bsp import BSP
from .source import skd as _skd
from .staticlight import axes

_KEYS = re.compile(r"^\s*(scale|path|skelmodel)\s+(\S+)", re.M)


@dataclass
class _Mesh:
    radius: float                          # model radius (TIKI scale applied), as the SKC holds it
    surfaces: list                         # SkdSurface with collapse data
    lod: Optional[tuple]                   # the LOD table (``lod.engine_table``), None: always full detail
    full: int = 0                          # vertices at full detail


@dataclass
class ViewCost:
    verts: int = 0
    tris: int = 0
    surfaces: int = 0                      # draw surfaces added (vanished ones included)
    models: int = 0                        # models in the frustum
    by_model: dict = field(default_factory=dict)   # tiki -> vertices drawn (all its instances)


def _meshes(read: Callable[[str], Optional[bytes]], tiki: str, cache: dict) -> list[_Mesh]:
    """One ``_Mesh`` per SKD the TIKI loads (each has its own .lod)."""
    if tiki in cache:
        return cache[tiki]
    name = tiki if tiki.startswith("models/") else "models/" + tiki
    text = read(name)
    out = []
    if text is not None:
        kv = {"scale": "1", "path": str(Path(name).parent)}
        skds = []
        for k, v in _KEYS.findall(text.decode("latin-1")):
            if k == "skelmodel":
                skds.append(v)
            else:
                kv[k] = v
        scale = float(kv["scale"])
        for s in skds:
            path = s if "/" in s else f"{kv['path'].rstrip('/')}/{s}"
            blob = read(path)
            if blob is None:
                continue
            info = _skd.read_skd(blob)
            for srf, (col, cidx) in zip(info.surfaces, info.collapse):
                srf.collapse, srf.collapse_index = np.asarray(col), np.asarray(cidx)
            allp = np.concatenate([np.asarray(s_.positions, np.float64) for s_ in info.surfaces]) * scale \
                if info.surfaces else np.zeros((1, 3))
            lod = None
            if _lod.can_lod(info.surfaces):
                lod = _lod.engine_table(read(path[: path.find("skd")] + "lod") if "skd" in path else None, info.lod_index)
            out.append(_Mesh(_skd.bounds_radius(allp.min(0), allp.max(0)), info.surfaces, lod,
                             sum(len(s_.positions) for s_ in info.surfaces)))
    cache[tiki] = out
    return out


def pk3_reader(pk3: Path, under: Sequence[Path] = ()) -> tuple[Callable[[str], Optional[bytes]], bytes]:
    """``read(game_path)`` over a pk3, then over the ``under`` paks (later ones win, as the
    game loads them), and the pk3's (first) BSP's bytes."""
    zips = [zipfile.ZipFile(x) for x in [*under, pk3]]
    names = {}
    for z in zips:
        names.update({n.lower(): (z, n) for n in z.namelist()})

    def read(p: str) -> Optional[bytes]:
        hit = names.get(p.lower())
        return hit[0].read(hit[1]) if hit else None

    z = zips[-1]
    bsp = next(n for n in z.namelist() if n.lower().endswith(".bsp"))
    return read, z.read(bsp)


def _retail() -> list[Path]:
    from . import config
    try:
        return config.load().retail_paks()
    except RuntimeError:                    # no game dir: only the map's own models count
        return []


def frustum(origin, angles, fov_x: float, fov_y: float) -> list[tuple[np.ndarray, float]]:
    """The four side planes (inward normal, distance) of a view, as ``R_SetupFrustum``."""
    f, l, u = axes(angles)
    o = np.asarray(origin, np.float64)
    out = []
    for half, side in ((fov_x / 2, l), (fov_y / 2, u)):
        s, c = math.sin(math.radians(90 - half)), math.cos(math.radians(90 - half))
        for sign in (1, -1):
            n = f * c + side * s * sign
            n = n / np.linalg.norm(n)
            out.append((n, float(n @ o)))
    return out


def view_fov(fov: float = 80.0, width: int = 1280, height: int = 720) -> tuple[float, float]:
    """(fovX, fovY) for cg_fov ``fov`` (a 4:3 horizontal angle) on a wider screen."""
    ty = math.tan(math.radians(fov) / 2) * 3 / 4
    return 2 * math.degrees(math.atan(ty * width / height)), 2 * math.degrees(math.atan(ty))


def estimate(pk3: Path, shots: Sequence, width: int = 1280, height: int = 720, fov: float = 80.0,
             lodscale: float = _lod.REF_LODSCALE, lodcap: float = _lod.REF_LODCAP,
             retail: bool = True) -> dict[str, ViewCost]:
    """``{shot name: ViewCost}`` for ``game.Shot``s (origin, angles) over a packaged map.
    Stock models come from the retail paks (``retail``; before 2026-10-02 only the map's
    pk3 was read, so a map of stock props such as mk_summit cost 0)."""
    read, bsp_bytes = pk3_reader(Path(pk3), _retail() if retail else ())
    models = BSP(bsp_bytes).static_models()
    cache: dict = {}
    fx, fy = view_fov(fov, width, height)
    drawn_cache: dict = {}
    out = {}
    for shot in shots:
        planes = frustum(shot.origin, shot.angles, fx, fy)
        eye = np.asarray(shot.origin, np.float64)
        vc = ViewCost()
        for sm in models:
            meshes = _meshes(read, sm.model, cache)
            if not meshes:
                continue
            o = np.asarray(sm.origin, np.float64)
            r_cull = max(m.radius for m in meshes) * sm.scale
            if any(float(n @ o) - d < -r_cull for n, d in planes):
                continue
            vc.models += 1
            dist = max(float(np.linalg.norm(o - eye)), 1e-3)
            metric = max(m.radius for m in meshes) * (100.0 / fx) / dist
            got = 0
            for mi, m in enumerate(meshes):
                vc.surfaces += len(m.surfaces)
                cut = _lod.engine_cutoff(m.lod, metric, lodscale, lodcap) if m.lod else 0.0
                for si, srf in enumerate(m.surfaces):
                    if not m.lod:
                        v, t = len(srf.positions), len(srf.triangles)
                    else:
                        key = (sm.model, mi, si, round(cut, 2))
                        if key not in drawn_cache:
                            drawn_cache[key] = _lod.drawn(srf, cut)
                        v, t = drawn_cache[key]
                    got += v
                    vc.tris += t
            vc.verts += got
            if got:
                vc.by_model[sm.model] = vc.by_model.get(sm.model, 0) + got
        out[shot.name] = vc
    return out


def table(costs: dict[str, ViewCost], top: int = 3) -> str:
    """Cameras, most drawn prop vertices first, with the ``top`` models by vertices."""
    out = [f"{'camera':28s} {'models':>6s} {'verts':>7s} {'tris':>7s}  top models (vertices)"]
    for k, v in sorted(costs.items(), key=lambda kv: -kv[1].verts):
        best = sorted(v.by_model.items(), key=lambda kv: -kv[1])[:top]
        out.append(f"{k[:28]:28s} {v.models:6d} {v.verts:7d} {v.tris:7d}  "
                   + ", ".join(f"{Path(m).stem} {n}" for m, n in best))
    if costs:
        vs = [v.verts for v in costs.values()]
        out.append(f"== {len(vs)} cameras: mean {sum(vs) / len(vs):.0f} vertices, max {max(vs)}")
    return "\n".join(out)


def target(where: str, name: Optional[str] = None) -> tuple[Path, list]:
    """(pk3, shots) of a map project folder (``dist/<name>.pk3`` and its ``SHOTS``) or of a
    CS:GO conversion (``local/csgo/<name>/<name>.pk3`` and its named cameras)."""
    from . import config
    if (Path(where) / "build.py").is_file() or Path(where).is_dir():
        from .project import Project
        pr = Project.load(Path(where))
        return config.REPO / "dist" / f"{pr.name}.pk3", list(pr.shots)
    from .source.convert import _local_cameras
    name, out, cams = _local_cameras(where, name)
    return out / f"{name}.pk3", cams
