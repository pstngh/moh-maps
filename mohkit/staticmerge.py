"""Merge static model instances so a map stays under the engine's static model limit.

The renderer indexes per-frame triangle counts by static model number in
``staticModelNumIndexes[4095]`` (``renderergl1/tr_model.cpp:33``, written for every drawn
static model at ``:1560``) and packs that number into 12 sort-key bits
(``R_DecomposeSort``: ``(sort >> QSORT_ENTITYNUM_SHIFT) & 4095``, ``tr_main.c:1241``). A map
with more than 4095 static models writes past the array every frame and draws the extra
models with another model's transform: de_inferno's 6,326 injected props crashed the game
with 8 bots (``R_PrintInfoWorldtris`` from corrupted state). Static models are only
frustum-culled (the vis test is commented out, ``tr_staticmodels.cpp``), and at most 8,192
of their surfaces are drawn per frame (``MAX_STATIC_MODELS_SURFS``), so fewer, larger models
also help there.

``merge`` groups instances of one model by a world grid cell and writes each group of two
or more as one rigid model (TIKI + SKD + SKC) whose surfaces are the instances' surfaces in
world orientation, packed into buckets within the SKD limits (999 vertices, 1,999 triangles
per surface, 24 surfaces per TIKI). It uses the smallest cell that brings the count under
``target``; maps already under it are left alone.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from .source import skd as _skd
from .staticlight import StaticInstance, axes

MAX_STATIC_MODELS = 4095
DEFAULT_TARGET = 3500
CELLS = (512.0, 1024.0, 2048.0, 4096.0)

_SETUP = re.compile(r"^\s*(scale|path|skelmodel)\s+(\S+)", re.M)
_SURFACE = re.compile(r"^\s*surface\s+(\S+)\s+shader\s+(\S+)", re.M)


def tiki_parts(read: Callable[[str], Optional[bytes]], tik: str) -> list[tuple[_skd.SkdSurface, str]]:
    """A TIKI's SKD surfaces (positions times the TIKI ``scale``) with their shaders, in the
    file order ``staticlight.tiki_mesh`` uses. Surfaces without a ``surface ... shader``
    binding are left out (the engine would draw them with no shader)."""
    name = tik if tik.startswith("models/") else "models/" + tik
    text = read(name)
    if text is None:
        raise FileNotFoundError(name)
    t = text.decode("latin-1")
    keys = {"scale": "1", "path": str(Path(name).parent)}
    skds = []
    for k, v in _SETUP.findall(t):
        if k == "skelmodel":
            skds.append(v)
        else:
            keys[k] = v
    shaders = {s.lower(): sh for s, sh in _SURFACE.findall(t)}
    scale = float(keys["scale"])
    out = []
    for s in skds:
        path = s if "/" in s else f"{keys['path'].rstrip('/')}/{s}"
        blob = read(path)
        if blob is None:
            raise FileNotFoundError(path)
        for srf in _skd.read_skd(blob).surfaces:
            sh = shaders.get(srf.name.lower()) or shaders.get("all")
            if sh is None:
                continue
            srf.positions = srf.positions.astype(np.float64) * scale
            out.append((srf, sh))
    return out


class _Model:
    """Buckets of one merged model being filled: per bucket the source part index, shader
    and the accumulated vertices/triangles."""

    def __init__(self) -> None:
        self.buckets: list[dict] = []
        self.members: list[StaticInstance] = []

    def fits(self, parts) -> bool:
        need = 0
        for pi, (srf, _) in enumerate(parts):
            b = self._open(pi, len(srf.positions), len(srf.triangles))
            need += b is None
        return len(self.buckets) + need <= _skd.MAX_TIKI_SURFACES

    def _open(self, pi: int, nv: int, nt: int) -> Optional[dict]:
        for b in self.buckets:
            if b["part"] == pi and b["nv"] + nv <= _skd.MAX_SURFACE_VERTS and b["nt"] + nt <= _skd.MAX_SURFACE_TRIS:
                return b
        return None

    def add(self, inst: StaticInstance, parts) -> None:
        ax = axes(inst.angles)
        for pi, (srf, shader) in enumerate(parts):
            b = self._open(pi, len(srf.positions), len(srf.triangles))
            if b is None:
                b = {"part": pi, "shader": shader, "nv": 0, "nt": 0, "pos": [], "nrm": [], "uv": [], "tri": []}
                self.buckets.append(b)
            pos = srf.positions * float(inst.scale) @ ax + np.asarray(inst.origin, np.float64)
            nrm = srf.normals.astype(np.float64) @ ax
            b["tri"].append(np.asarray(srf.triangles) + b["nv"])
            b["pos"].append(pos)
            b["nrm"].append(nrm)
            b["uv"].append(srf.uvs)
            b["nv"] += len(srf.positions)
            b["nt"] += len(srf.triangles)
        self.members.append(inst)


def _write(model: _Model, prefix: str, key: str) -> tuple[StaticInstance, dict[str, bytes]]:
    origin = np.round(np.mean([np.asarray(m.origin, np.float64) for m in model.members], axis=0), 1)
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    surfaces = []
    for i, b in enumerate(model.buckets):
        pos = np.concatenate(b["pos"]) - origin
        nrm = np.concatenate(b["nrm"])
        ln = np.linalg.norm(nrm, axis=1, keepdims=True)
        nrm = np.where(ln > 1e-6, nrm / np.maximum(ln, 1e-6), np.array([0.0, 0.0, 1.0]))
        surfaces.append(_skd.SkdSurface(f"s{i}", pos.astype(np.float32), nrm.astype(np.float32),
                                        np.concatenate(b["uv"]).astype(np.float32), np.concatenate(b["tri"])))
    allp = np.concatenate([s.positions for s in surfaces]).astype(np.float64)
    mins, maxs = allp.min(0), allp.max(0)
    path = prefix.rstrip("/")
    files = {
        f"{path}/{h}.skd": _skd.build_skd(f"{h}.skd", surfaces),
        f"{path}/{h}.skc": _skd.build_skc(tuple(mins), tuple(maxs)),
        f"{path}/{h}.tik": _skd.build_tiki(path, f"{h}.skd", f"{h}.skc",
                                           [(s.name, b["shader"]) for s, b in zip(surfaces, model.buckets)],
                                           comment=f"{len(model.members)} x {model.members[0].model}, "
                                                   "merged by mohkit.staticmerge").encode("latin-1"),
    }
    inst = StaticInstance(f"{path}/{h}.tik", tuple(float(v) for v in origin), (0.0, 0.0, 0.0), 1.0,
                          allp, np.concatenate([s.normals for s in surfaces]).astype(np.float64))
    return inst, files


def _group(instances: Sequence[StaticInstance], cell: float) -> dict:
    groups: dict = {}
    for i, inst in enumerate(instances):
        key = (inst.model,) + tuple(int(np.floor(float(c) / cell)) for c in inst.origin)
        groups.setdefault(key, []).append(i)
    return groups


def merge(instances: Sequence[StaticInstance], read: Callable[[str], Optional[bytes]], prefix: str,
          target: int = DEFAULT_TARGET, cells: Sequence[float] = CELLS) -> tuple[list[StaticInstance], dict[str, bytes], dict]:
    """Instances under ``target`` models (unchanged when already under it), the merged models'
    files (``{game path: bytes}``, under ``prefix`` such as ``models/csgo/m_cs_inferno``)
    and a summary. Instances whose TIKI cannot be read stay as they are."""
    instances = list(instances)
    if len(instances) <= target:
        return instances, {}, {"merged": False, "models": len(instances)}
    parts_cache: dict = {}

    def parts(model: str):
        if model not in parts_cache:
            try:
                parts_cache[model] = tiki_parts(read, model)
            except (FileNotFoundError, ValueError):
                parts_cache[model] = None
        return parts_cache[model]

    cell = cells[-1]
    for c in cells:  # the smallest cell whose group count is under the target (rough: buckets may split)
        if len(_group(instances, c)) <= target * 0.9:
            cell = c
            break
    out: list[StaticInstance] = []
    files: dict[str, bytes] = {}
    merged_from = 0
    for key, idx in sorted(_group(instances, cell).items(), key=lambda kv: (kv[0][0], kv[0][1:])):
        group = [instances[i] for i in idx]
        pr = parts(group[0].model) if len(group) > 1 else None
        if not pr:
            out += group
            continue
        models: list[_Model] = [_Model()]
        for inst in group:
            if not models[-1].fits(pr):
                models.append(_Model())
            models[-1].add(inst, pr)
        for n, mdl in enumerate(models):
            if len(mdl.members) == 1:
                out.append(mdl.members[0])
                continue
            k = f"{key}/{n}/" + ";".join(f"{m.origin}" for m in mdl.members)
            inst, f = _write(mdl, prefix, k)
            out.append(inst)
            files.update(f)
            merged_from += len(mdl.members)
    return out, files, {"merged": True, "cell": cell, "models": len(out), "from": len(instances),
                        "merged_instances": merged_from, "files": len(files)}
