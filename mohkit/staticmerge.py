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

The skeleton cache holds 1,024 SKDs (``TIKI_MAX_SKELCACHE``, ``tiki/tiki_shared.h:79``):
props past it never load ("No free spots open in skel cache"; de_nuke's 1,365 prop SKDs
lost hundreds of props). Players, weapons and effects share that cache.

``merge`` keeps a map within ``max_models`` static models and ``max_skd`` distinct SKDs.
It picks models to merge (``_choose``): rarely used ones first when SKDs are over budget
(merging a one-off model duplicates nothing), then the cheapest to duplicate (fewest
vertices) while instances are over budget. Their instances are merged per world grid cell
into rigid models whose surfaces are the instances' surfaces in world orientation, packed
into one bucket per shader within the SKD limits (999 vertices, 1,999 triangles per
surface, 24 surfaces per TIKI). Other models stay instanced. Maps within both budgets are
left alone.
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
DEFAULT_TARGET = 3500          # static models (instances)
DEFAULT_MAX_SKD = 600          # distinct prop SKDs, leaving ~400 of the cache for the game
CELL = 1024.0

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
    """A merged model being filled: one bucket per shader (more when one fills up), each
    accumulating vertices and triangles."""

    def __init__(self) -> None:
        self.buckets: list[dict] = []
        self.members: list[StaticInstance] = []

    def _open(self, shader: str, nv: int, nt: int) -> Optional[dict]:
        for b in self.buckets:
            if b["shader"] == shader and b["nv"] + nv <= _skd.MAX_SURFACE_VERTS and b["nt"] + nt <= _skd.MAX_SURFACE_TRIS:
                return b
        return None

    def fits(self, parts) -> bool:
        """Would one more instance fit in 24 surfaces? Simulates ``add``'s first-fit."""
        load: dict = {}
        pending: list[dict] = []
        for srf, shader in parts:
            nv, nt = len(srf.positions), len(srf.triangles)
            target = None
            for b in self.buckets + pending:
                av, at = load.get(id(b), (0, 0))
                if (b["shader"] == shader and b["nv"] + av + nv <= _skd.MAX_SURFACE_VERTS
                        and b["nt"] + at + nt <= _skd.MAX_SURFACE_TRIS):
                    target = b
                    break
            if target is None:
                target = {"shader": shader, "nv": 0, "nt": 0}
                pending.append(target)
            av, at = load.get(id(target), (0, 0))
            load[id(target)] = (av + nv, at + nt)
        return len(self.buckets) + len(pending) <= _skd.MAX_TIKI_SURFACES

    def add(self, inst: StaticInstance, parts) -> None:
        ax = axes(inst.angles)
        k = 0      # the instance's vertex colours run over its surfaces in file order
        for srf, shader in parts:
            nv, nt = len(srf.positions), len(srf.triangles)
            b = self._open(shader, nv, nt)
            if b is None:
                b = {"shader": shader, "nv": 0, "nt": 0, "pos": [], "nrm": [], "uv": [], "tri": [], "col": []}
                self.buckets.append(b)
            pos = srf.positions * float(inst.scale) @ ax + np.asarray(inst.origin, np.float64)
            nrm = srf.normals.astype(np.float64) @ ax
            b["tri"].append(np.asarray(srf.triangles) + b["nv"])
            b["pos"].append(pos)
            b["nrm"].append(nrm)
            b["uv"].append(srf.uvs)
            col = inst.colors[k:k + nv] if inst.colors is not None and len(inst.colors) >= k + nv else None
            b["col"].append(col if col is not None else np.full((nv, 3), np.nan))
            k += nv
            b["nv"] += nv
            b["nt"] += nt
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
    cols = np.concatenate([np.concatenate(b["col"]) for b in model.buckets])
    inst = StaticInstance(f"{path}/{h}.tik", tuple(float(v) for v in origin), (0.0, 0.0, 0.0), 1.0,
                          allp, np.concatenate([s.normals for s in surfaces]).astype(np.float64),
                          None if np.isnan(cols[:, 0]).all() else cols)
    return inst, files


def _skd_key(read, model: str) -> tuple:
    """The SKD files a TIKI loads (skins of one mesh share them)."""
    name = model if model.startswith("models/") else "models/" + model
    text = read(name)
    if text is None:
        return (name,)
    t = text.decode("latin-1")
    path = (re.findall(r"^\s*path\s+(\S+)", t, re.M) or [str(Path(name).parent)])[0]
    return tuple(s if "/" in s else f"{path}/{s}" for s in re.findall(r"^\s*skelmodel\s+(\S+)", t, re.M)) or (name,)


def _pack(instances: Sequence[StaticInstance], parts: Callable, cell: float) -> list[_Model]:
    """Merged models for ``instances`` (all mergeable): per grid cell, instances sorted by
    shader set, packed until a model would exceed 24 surfaces."""
    cells: dict = {}
    for inst in instances:
        cells.setdefault(tuple(int(np.floor(float(c) / cell)) for c in inst.origin), []).append(inst)
    out = []
    for key in sorted(cells):
        group = sorted(cells[key], key=lambda i: (tuple(sorted({sh for _, sh in parts(i.model)})), i.model,
                                                  tuple(i.origin)))
        cur = _Model()
        for inst in group:
            pr = parts(inst.model)
            if cur.members and not cur.fits(pr):
                out.append(cur)
                cur = _Model()
            cur.add(inst, pr)
        if cur.members:
            out.append(cur)
    return out


def _choose(instances, parts, skd_of, max_models: int, max_skd: int, cell: float) -> tuple[set, list]:
    """Models to merge and the packed result: a greedy pick, re-packed until both budgets hold."""
    count: dict = {}
    for i in instances:
        count[i.model] = count.get(i.model, 0) + 1
    mergeable = [m for m in count if parts(m)]
    verts = {m: sum(len(s.positions) for s, _ in parts(m)) for m in mergeable}
    # SKD budget: rarest first (merging a one-off model duplicates nothing), then smallest
    by_rarity = sorted(mergeable, key=lambda m: ((count[m] - 1) * verts[m], m))
    # instance budget: cheapest to duplicate first (fewest vertices per instance)
    by_cost = sorted(mergeable, key=lambda m: (verts[m], -count[m], m))
    chosen: set = set()
    packed: list = []
    for _ in range(64):
        kept = [i for i in instances if i.model not in chosen]
        packed = _pack([i for i in instances if i.model in chosen], parts, cell) if chosen else []
        n_models = len(kept) + len(packed)
        n_skd = len({skd_of(i.model) for i in kept}) + len(packed)
        if n_models <= max_models and n_skd <= max_skd:
            return chosen, packed
        add = []
        if n_skd > max_skd:
            add += [m for m in by_rarity if m not in chosen][: max(8, (n_skd - max_skd) // 2)]
        if n_models > max_models:
            need = n_models - max_models
            for m in by_cost:
                if m in chosen or m in add:
                    continue
                add.append(m)
                need -= count[m]
                if need <= 0:
                    break
        if not add:
            break
        chosen |= set(add)
    return chosen, packed


def merge(instances: Sequence[StaticInstance], read: Callable[[str], Optional[bytes]], prefix: str,
          target: int = DEFAULT_TARGET, max_skd: int = DEFAULT_MAX_SKD,
          cell: float = CELL) -> tuple[list[StaticInstance], dict[str, bytes], dict]:
    """Instances within ``target`` models and ``max_skd`` SKDs (unchanged when already
    within both), the merged models' files (``{game path: bytes}`` under ``prefix``, such as
    ``models/csgo/m_cs_inferno``) and a summary. Unreadable TIKIs are never merged."""
    instances = list(instances)
    skd_cache: dict = {}

    def skd_of(model: str) -> tuple:
        if model not in skd_cache:
            skd_cache[model] = _skd_key(read, model)
        return skd_cache[model]

    n_skd = len({skd_of(i.model) for i in instances})
    if len(instances) <= target and n_skd <= max_skd:
        return instances, {}, {"merged": False, "models": len(instances), "skd": n_skd}
    parts_cache: dict = {}

    def parts(model: str):
        if model not in parts_cache:
            try:
                parts_cache[model] = tiki_parts(read, model)
            except (FileNotFoundError, ValueError):
                parts_cache[model] = None
        return parts_cache[model]

    chosen, packed = _choose(instances, parts, skd_of, target, max_skd, cell)
    out = [i for i in instances if i.model not in chosen]
    files: dict[str, bytes] = {}
    for mdl in packed:
        k = mdl.members[0].model + ";" + ";".join(f"{m.model}@{tuple(m.origin)}" for m in mdl.members)
        inst, f = _write(mdl, prefix, k)
        out.append(inst)
        files.update(f)
    kept_skd = len({skd_of(i.model) for i in instances if i.model not in chosen})
    return out, files, {"merged": True, "models": len(out), "from": len(instances), "skd": kept_skd + len(packed),
                        "skd_from": n_skd, "merged_models": len(chosen), "merged_instances":
                        sum(len(m.members) for m in packed), "files": len(files)}


def prune(files: dict, models: set, used: set, read: Callable[[str], Optional[bytes]]) -> int:
    """Delete from ``files`` ({game path: data}) the TIKI, SKD and SKC of each model in
    ``models`` that no instance in ``used`` loads any more (merged away); SKDs and SKCs
    shared with a used TIKI (skins) stay. Returns the number of files removed."""
    def tik_path(m: str) -> str:
        return m if m.startswith("models/") else "models/" + m

    def deps(m: str) -> set:
        text = read(tik_path(m))
        if text is None:
            return set()
        t = text.decode("latin-1")
        path = (re.findall(r"^\s*path\s+(\S+)", t, re.M) or [str(Path(tik_path(m)).parent)])[0]
        names = re.findall(r"^\s*skelmodel\s+(\S+)", t, re.M) + re.findall(r"^\s*\w+\s+(\S+\.skc)\s*$", t, re.M)
        return {n if "/" in n else f"{path}/{n}" for n in names}

    keep = set()
    for m in used:
        keep |= deps(m) | {tik_path(m)}
    removed = 0
    for m in models - used:
        for f in deps(m) | {tik_path(m)}:
            if f not in keep and f in files:
                del files[f]
                removed += 1
    return removed
