"""Catalog of the stock map-source corpus, resolved against the retail paks.

``python -m mohkit.catalog --out data/`` regenerates ``data/*.json`` and
``docs/reference/{materials,entities}.md``.

Corpus (relative to the repository root):

* ``reference/aa/*.map``: Allied Assault SP + MP;
* ``reference/sh/*.map``: Spearhead; ``reference/bt/*.map``: Breakthrough (any file
  byte-identical to another corpus map is dropped and kept as an alias);
* ``reference/community/*.map``: community objective maps.

Resolution: "aa" means a shader script or implicit image exists in retail
``main/pak*.pk3``; otherwise "sh"/"bt"/"sh+bt" when found with ``mainta``/``maintt``
added on top of ``main``; otherwise "missing". Loose files are ignored so results do
not depend on local extras.

Terms used in the outputs:

* orientation is from :attr:`mapfile.Face.plane` (outward normal): floor ``z > 0.7``,
  ceiling ``z < -0.7``, wall otherwise; patches and terrain are counted separately;
* "uses" = brush faces + patches + terrain material cells;
* tool shaders are ``common/*`` and the terrain placeholder ``notexture``; they are
  recorded but left out of palettes and style statistics;
* static-model bounds are the union of the ``idle`` animation frame bounds from the
  ``.skc`` (SKAN v13: 48-byte header, 48-byte frames starting with ``bounds[2][3]``)
  times the TIKI ``setup`` scale, exactly like ``TIKI_CalculateBounds`` at entity
  scale 1; ``editor_bounds`` is the ``/*QUAKED name (r g b) (mins) (maxs)`` comment.
  Expansion ``.skc`` files are SKAN v14 (a Huffman-coded ``msg_t`` stream) and are not
  decoded, so those models only get editor/collision bounds;
* static collision masks: Q3map looks for ``models/<same path>.map`` next to a static
  model's ``.tik`` (311 such files, all in Pak0) and bakes its clip brushes into the
  world; models without one get no collision. The brushes are in model-local game
  units at entity scale 1 (their AABB matches the ``.skc`` bounds x TIKI scale, e.g.
  ``hedgehog``), so ``collision.bounds`` is a reliable placement footprint. Trees only
  carry a trunk clip.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib
import json
import os
import re
import statistics
import struct
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from . import geom
from .mapfile import Brush, MapFile, Patch, Terrain
from .pak import GameFS, normalize, path_key
from .shaders import ShaderDef, ShaderIndex

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GAME_DIR = os.environ.get("MOHKIT_GAME_DIR", os.path.expanduser("~/Documents/Games/moh"))

CORPUS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("aa", ("reference/aa/*.map",)),
    ("sh", ("reference/sh/*.map",)),
    ("bt", ("reference/bt/*.map",)),
    ("aa_custom", ("reference/community/*.map",)),
)
MP_RE = re.compile(r"^(mohdm|obj_|mp_)|_(obj|dm|tow|lib)$", re.IGNORECASE)
FLAG_PARMS = ("nonsolid", "trans", "playerclip", "monsterclip", "weaponclip", "vehicleclip", "sky", "nolightmap",
              "alphashadow", "fence", "nodraw", "nomarks", "noimpact", "water", "ladder", "castshadow", "detail",
              "structural", "areaportal", "hint", "origin", "shootonly", "nodamage", "slick", "fog", "lava", "slime",
              "nodlight", "nosteps", "obscuring")
EXAMPLE_LEN = 100
MAX_EXAMPLES = 5
MAP_LIST = 8


def is_tool(shader: str) -> bool:
    return shader.startswith("common/") or shader == "notexture"


def shader_key(name: str) -> str:
    return path_key(name)


def _r(x: float, nd: int = 4) -> float:
    v = round(float(x), nd)
    return int(v) if v.is_integer() else v


# ---------------------------------------------------------------------------
# Corpus


@dataclass
class CorpusMap:
    id: str
    group: str
    path: str
    sha1: str
    size: int
    mp: bool
    aliases: list[str] = field(default_factory=list)


def discover_corpus(root: str = REPO) -> list[CorpusMap]:
    out: list[CorpusMap] = []
    by_hash: dict[str, CorpusMap] = {}
    for group, patterns in CORPUS_GROUPS:
        files: list[str] = []
        for pat in patterns:
            files += glob.glob(os.path.join(root, pat))
        for f in sorted(set(files), key=lambda p: os.path.basename(p).lower()):
            with open(f, "rb") as fh:
                data = fh.read()
            h = hashlib.sha1(data).hexdigest()
            stem = os.path.splitext(os.path.basename(f))[0]
            rel = os.path.relpath(f, root)
            if h in by_hash:
                by_hash[h].aliases.append(rel)
                continue
            m = CorpusMap(f"{group}/{stem}", group, rel, h, len(data), bool(MP_RE.search(stem)) or group == "aa_custom")
            by_hash[h] = m
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Per-map scan (runs in worker processes)


@dataclass
class ShaderUse:
    faces: int = 0
    patches: int = 0
    terrain: int = 0
    floor: int = 0
    wall: int = 0
    ceiling: int = 0
    degenerate: int = 0
    detail: int = 0
    floor_area: float = 0.0
    wall_area: float = 0.0
    ceiling_area: float = 0.0
    scales: Counter = field(default_factory=Counter)
    rotations: Counter = field(default_factory=Counter)
    face_parms: Counter = field(default_factory=Counter)

    @property
    def uses(self) -> int:
        return self.faces + self.patches + self.terrain

    def merge(self, o: "ShaderUse") -> None:
        for k in ("faces", "patches", "terrain", "floor", "wall", "ceiling", "degenerate", "detail",
                  "floor_area", "wall_area", "ceiling_area"):
            setattr(self, k, getattr(self, k) + getattr(o, k))
        self.scales.update(o.scales)
        self.rotations.update(o.rotations)
        self.face_parms.update(o.face_parms)


@dataclass
class KeyStats:
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, value: str) -> None:
        self.count += 1
        self.example(value)

    def example(self, value: str) -> None:
        v = value if len(value) <= EXAMPLE_LEN else value[:EXAMPLE_LEN - 3] + "..."
        if len(self.examples) < MAX_EXAMPLES and v not in self.examples:
            self.examples.append(v)


@dataclass
class ClassStats:
    count: int = 0
    brush: int = 0
    keys: dict[str, KeyStats] = field(default_factory=dict)
    models: Counter = field(default_factory=Counter)


@dataclass
class ModelUse:
    count: int = 0
    classnames: Counter = field(default_factory=Counter)
    spellings: Counter = field(default_factory=Counter)
    scale: Counter = field(default_factory=Counter)
    angle: Counter = field(default_factory=Counter)
    angles: KeyStats = field(default_factory=KeyStats)
    scale_set: int = 0
    angle_set: int = 0


@dataclass
class MapScan:
    map: CorpusMap
    entities: int = 0
    brushes: int = 0
    faces: int = 0
    patches: int = 0
    terrains: int = 0
    shaders: dict[str, ShaderUse] = field(default_factory=dict)
    classes: dict[str, ClassStats] = field(default_factory=dict)
    models: dict[str, ModelUse] = field(default_factory=dict)
    worldspawn: dict[str, str] = field(default_factory=dict)
    lights: dict[str, Any] = field(default_factory=dict)
    spawns: Counter = field(default_factory=Counter)
    anomalies: Counter = field(default_factory=Counter)
    seconds: float = 0.0


def model_key(value: str) -> str:
    k = path_key(value)
    return k if k.startswith("models/") else "models/" + k


def _use(scan: MapScan, name: str) -> ShaderUse:
    k = shader_key(name)
    if not k or k.startswith("("):
        scan.anomalies["face without shader name"] += 1
        k = "<malformed>"
    u = scan.shaders.get(k)
    if u is None:
        u = scan.shaders[k] = ShaderUse()
    return u


def scan_map(cm: CorpusMap, root: str = REPO) -> MapScan:
    t0 = time.time()
    mf = MapFile.load(os.path.join(root, cm.path))
    s = MapScan(cm, entities=len(mf.entities), worldspawn=dict(mf.worldspawn.props))
    light_vals: list[float] = []
    lights = Counter({k: 0 for k in ("count", "missing_light_key", "color", "spot", "angles", "radius")})
    for ent in mf.entities:
        cls = ent.classname or "<none>"
        cs = s.classes.get(cls)
        if cs is None:
            cs = s.classes[cls] = ClassStats()
        cs.count += 1
        if ent.prims:
            cs.brush += 1
        for k, v in ent.props.items():
            ks = cs.keys.get(k)
            if ks is None:
                ks = cs.keys[k] = KeyStats()
            ks.add(v)
        model = ent.get("model")
        if model:
            cs.models[model_key(model)] += 1
        if model and path_key(model).endswith(".tik"):
            mk = model_key(model)
            mu = s.models.get(mk)
            if mu is None:
                mu = s.models[mk] = ModelUse()
            mu.count += 1
            mu.classnames[cls] += 1
            mu.spellings[model] += 1
            if "scale" in ent:
                mu.scale_set += 1
                mu.scale[_num_or_str(ent["scale"])] += 1
            if "angle" in ent:
                mu.angle_set += 1
                mu.angle[_num_or_str(ent["angle"])] += 1
            if "angles" in ent:
                mu.angles.add(ent["angles"])
        if cls.startswith("info_player"):
            s.spawns[cls] += 1
        if cls == "light":
            lights["count"] += 1
            raw = ent.get("light")
            try:
                light_vals.append(float(raw.split()[0]))
            except (ValueError, IndexError):
                lights["missing_light_key"] += 1
            if "_color" in ent:
                lights["color"] += 1
            if "target" in ent or any(k.startswith("spot") for k in ent.props):
                lights["spot"] += 1
            if "angles" in ent:
                lights["angles"] += 1
            if "radius" in ent:
                lights["radius"] += 1
        for p in ent.prims:
            if isinstance(p, Brush):
                s.brushes += 1
                planes = p.planes()
                windings = geom.brush_windings(planes)
                for f, pl, w in zip(p.faces, planes, windings):
                    s.faces += 1
                    u = _use(s, f.shader)
                    u.faces += 1
                    n = pl.normal
                    area = geom.winding_area(w) if w else 0.0
                    if n == (0.0, 0.0, 0.0):
                        u.degenerate += 1
                    elif n[2] > 0.7:
                        u.floor += 1
                        u.floor_area += area
                    elif n[2] < -0.7:
                        u.ceiling += 1
                        u.ceiling_area += area
                    else:
                        u.wall += 1
                        u.wall_area += area
                    u.scales[(_r(f.scale[0]), _r(f.scale[1]))] += 1
                    u.rotations[_r(f.rotate, 2)] += 1
                    if f.ext:
                        for sign, parm in f.surfaceparms():
                            if parm == "detail" and sign == "+":
                                u.detail += 1
                            else:
                                u.face_parms[sign + parm] += 1
            elif isinstance(p, Patch):
                s.patches += 1
                _use(s, p.shader).patches += 1
            elif isinstance(p, Terrain):
                s.terrains += 1
                for c in p.controls:
                    _use(s, c.shader).terrain += 1
    s.shaders.pop("<malformed>", None)
    s.lights = dict(lights)
    if light_vals:
        s.lights["light"] = {"median": _r(statistics.median(light_vals), 2), "mean": _r(statistics.fmean(light_vals), 2),
                             "min": _r(min(light_vals), 2), "max": _r(max(light_vals), 2)}
    s.seconds = time.time() - t0
    return s


def _num_or_str(v: str) -> Any:
    try:
        return _r(float(v), 4)
    except ValueError:
        return v.strip()


# ---------------------------------------------------------------------------
# Pak resolution


@dataclass
class Retail:
    """Shader/image/model lookups for AA alone and with each expansion."""
    aa_fs: GameFS
    aa: ShaderIndex
    exp: list[tuple[str, GameFS, ShaderIndex]]

    @classmethod
    def load(cls, game_dir: str) -> "Retail":
        aa_fs = GameFS(game_dir, ("main",), loose=False)
        exp = []
        for tag, mod in (("sh", "mainta"), ("bt", "maintt")):
            if os.path.isdir(os.path.join(game_dir, mod)):
                fs = GameFS(game_dir, ("main", mod), loose=False)
                exp.append((tag, fs, ShaderIndex.from_fs(fs)))
        return cls(aa_fs, ShaderIndex.from_fs(aa_fs), exp)

    def shader_home(self, name: str) -> tuple[str, Optional[GameFS], Optional[ShaderIndex]]:
        if self.aa.exists(name):
            return "aa", self.aa_fs, self.aa
        tags = [(t, fs, idx) for t, fs, idx in self.exp if idx.exists(name)]
        if not tags:
            return "missing", None, None
        return "+".join(t for t, _, _ in tags), tags[0][1], tags[0][2]

    def file_home(self, path: str) -> tuple[str, Optional[GameFS]]:
        if self.aa_fs.exists(path):
            return "aa", self.aa_fs
        tags = [(t, fs) for t, fs, _ in self.exp if fs.exists(path)]
        if not tags:
            return "missing", None
        return "+".join(t for t, _ in tags), tags[0][1]


# ---------------------------------------------------------------------------
# TIKI


_TIKI_TOKEN_RE = re.compile(r'\n|[ \t\r\f\v]+|//[^\n]*|/\*.*?\*/|"[^"\n]*"|[{}]|[^\s{}"]+', re.S)
_QUAKED_RE = re.compile(r"/\*QUAKED\s+(\S+)\s+\(([^)]*)\)\s+(\?|\(([^)]*)\)\s+\(([^)]*)\))")
_MACRO_RE = re.compile(r"\$([^$\s]*)\$")


@dataclass
class TikiInfo:
    path: str
    scale: float = 1.0
    skelmodels: list[str] = field(default_factory=list)
    anims: dict[str, str] = field(default_factory=dict)   # lower alias -> file (first wins)
    quaked: Optional[str] = None
    editor_bounds: Optional[tuple[list[float], list[float]]] = None
    setsize: Optional[tuple[list[float], list[float]]] = None
    includes: list[str] = field(default_factory=list)
    missing_includes: list[str] = field(default_factory=list)


def _tiki_lines(text: str) -> list[list[str]]:
    lines: list[list[str]] = [[]]
    for m in _TIKI_TOKEN_RE.finditer(text):
        s = m.group(0)
        if s == "\n":
            lines.append([])
        elif s.startswith("/*"):
            lines.extend([] for _ in range(s.count("\n")))
        elif not (s[0] in " \t\r\f\v" or s.startswith("//")):
            lines[-1].append(s.strip('"'))
    return [ln for ln in lines if ln]


class TikiReader:
    """TIKI text reader. ``$include`` splices the included tokens into the including stream
    (parse state is shared), ``$define`` macros (``$name$``) propagate to every script, and
    the ``path`` prefix for ``skelmodel``/animation files belongs to the script being read
    (``TikiScript::path``). ``includes <map> { ... }`` blocks are map-conditional and ignored;
    a ``path`` change inside a nested block is undone when the block closes. Included files
    are tokenized once and cached; includes inside ``animations`` stop being followed once
    ``idle`` is known (only setup, ``idle`` and ``setsize`` are extracted)."""

    def __init__(self, fs: GameFS):
        self.fs = fs
        self._lines: dict[str, list[list[str]]] = {}

    def lines(self, path: str) -> list[list[str]]:
        k = path_key(path)
        if k not in self._lines:
            self._lines[k] = _tiki_lines(self.fs.read_text(path))
        return self._lines[k]

    def read(self, path: str) -> TikiInfo:
        info = TikiInfo(self.fs.real_path(path) or path)
        q = _QUAKED_RE.search(self.fs.read_text(path))
        if q:
            info.quaked = q.group(1)
            if q.group(4) is not None:
                try:
                    info.editor_bounds = ([_r(float(x), 3) for x in q.group(4).split()],
                                          [_r(float(x), 3) for x in q.group(5).split()])
                except ValueError:
                    pass
        st = _TikiState(info)
        self._walk(path, st, 0)
        return info

    def _walk(self, path: str, st: "_TikiState", level: int) -> None:
        holder = [""]
        for toks in self.lines(path):
            if toks[0].startswith("$"):
                cmd = toks[0][1:].lower()
                arg = st.expand(toks[1]) if len(toks) > 1 else ""
                if cmd == "define" and len(toks) > 2:
                    st.macros.setdefault(toks[1].lower(), toks[2])
                elif cmd == "include" and arg and level < 8 and not st.skipping and not st.done_with_includes():
                    inc = normalize(arg)
                    if self.fs.exists(inc):
                        st.info.includes.append(inc)
                        self._walk(inc, st, level + 1)
                    else:
                        st.info.missing_includes.append(inc)
                elif cmd == "path" and arg and not st.skipping:
                    holder[0] = arg.rstrip("/\\") + "/"
                continue
            st.feed(toks, holder)


@dataclass
class _TikiState:
    info: TikiInfo
    macros: dict[str, str] = field(default_factory=dict)
    section: str = ""
    depth: int = 0
    skip_depth: int = 0
    saved: list[tuple[list[str], str]] = field(default_factory=list)

    @property
    def skipping(self) -> bool:
        return self.skip_depth > 0

    def done_with_includes(self) -> bool:
        return "idle" in self.info.anims and self.section in ("animations", "")

    def expand(self, tok: str) -> str:
        if "$" not in tok:
            return tok
        return _MACRO_RE.sub(lambda m: self.macros.get(m.group(1).lower(), m.group(0)) if m.group(1) else "$", tok)

    def feed(self, toks: list[str], holder: list[str]) -> None:
        info = self.info
        if self.section == "animations" and "idle" in info.anims:
            for tok in toks:
                if tok == "{":
                    self.depth += 1
                    if self.depth >= 2:
                        self.saved.append((holder, holder[0]))
                elif tok == "}":
                    if self.depth >= 2 and self.saved:
                        h, v = self.saved.pop()
                        h[0] = v
                    self.depth = max(0, self.depth - 1)
                    if self.depth == 0:
                        self.section = ""
            return
        first = True
        for i, tok in enumerate(toks):
            if tok == "{":
                self.depth += 1
                if self.depth >= 2:
                    self.saved.append((holder, holder[0]))
                continue
            if tok == "}":
                if self.depth >= 2 and self.saved:
                    h, v = self.saved.pop()
                    h[0] = v
                if self.skip_depth and self.depth <= self.skip_depth:
                    self.skip_depth = 0
                self.depth = max(0, self.depth - 1)
                if self.depth == 0:
                    self.section = ""
                continue
            if not first or self.skipping:
                continue
            first = False
            low = tok.lower()
            if low == "includes":
                self.skip_depth = self.depth + 1
                continue
            args = [self.expand(t) for t in toks[i + 1:i + 3] if t not in "{}"] if self.depth else []
            if self.depth == 0:
                self.section = low
            elif self.depth == 1 and self.section == "setup":
                if low == "scale" and args:
                    try:
                        info.scale = float(args[0])
                    except ValueError:
                        pass
                elif low == "path" and args:
                    holder[0] = args[0].rstrip("/\\") + "/"
                elif low == "skelmodel" and args:
                    info.skelmodels.append(normalize(holder[0] + args[0]))
            elif self.depth == 1 and self.section == "animations" and args:
                info.anims.setdefault(low, normalize(holder[0] + args[0]))
            elif self.section == "init" and low == "setsize" and info.setsize is None:
                try:
                    v = [float(x) for t in args[:2] for x in t.split()]
                    if len(v) == 6:
                        info.setsize = ([_r(x, 2) for x in v[:3]], [_r(x, 2) for x in v[3:]])
                except ValueError:
                    pass


def read_tiki(fs: GameFS, path: str) -> TikiInfo:
    return TikiReader(fs).read(path)


def skc_bounds(data: bytes) -> Optional[tuple[list[float], list[float]]]:
    if len(data) < 96 or data[:4] != b"SKAN":
        return None
    version = struct.unpack_from("<i", data, 4)[0]
    if version != 13:
        return None
    nframes = struct.unpack_from("<i", data, 44)[0]
    if nframes <= 0 or 48 + 48 * nframes > len(data):
        return None
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for i in range(nframes):
        b = struct.unpack_from("<6f", data, 48 + 48 * i)
        for a in range(3):
            mins[a] = min(mins[a], b[a])
            maxs[a] = max(maxs[a], b[3 + a])
    return mins, maxs


def model_bounds(fs: GameFS, info: TikiInfo) -> tuple[Optional[tuple[list[float], list[float]]], str]:
    anim = info.anims.get("idle")
    if not anim:
        return None, "no idle animation"
    if not fs.exists(anim):
        return None, f"idle animation missing: {anim}"
    b = skc_bounds(fs.read(anim))
    if b is None:
        return None, "idle animation is not SKAN v13"
    s = info.scale
    return ([_r(x * s, 2) for x in b[0]], [_r(x * s, 2) for x in b[1]]), ""


@dataclass
class Collision:
    path: str
    brushes: int
    bounds: Optional[tuple[list[float], list[float]]]
    clip: list[list[Any]]


def collision_map_path(tiki_path: str) -> str:
    return re.sub(r"\.tik$", ".map", normalize(tiki_path), flags=re.IGNORECASE)


def read_collision(fs: GameFS, path: str) -> Collision:
    mf = MapFile.parse(fs.read_text(path), path)
    brushes = [b for e in mf.entities for b in e.brushes()]
    pts = [p for b in brushes for w in b.windings() for p in w]
    bounds = None
    if pts:
        lo, hi = geom.bounds_of(pts)
        bounds = ([_r(x, 2) for x in lo], [_r(x, 2) for x in hi])
    clip = Counter(shader_key(f.shader) for b in brushes for f in b.faces)
    return Collision(fs.real_path(path) or path, len(brushes), bounds, _top(clip, 3))


# ---------------------------------------------------------------------------
# Aggregation


@dataclass
class Merged:
    maps: list[CorpusMap]
    scans: list[MapScan]
    shaders: dict[str, ShaderUse] = field(default_factory=dict)
    shader_maps: dict[str, Counter] = field(default_factory=dict)
    classes: dict[str, ClassStats] = field(default_factory=dict)
    class_maps: dict[str, set] = field(default_factory=dict)
    class_mp: Counter = field(default_factory=Counter)
    class_mp_maps: dict[str, set] = field(default_factory=dict)
    models: dict[str, ModelUse] = field(default_factory=dict)
    model_maps: dict[str, Counter] = field(default_factory=dict)


def merge(scans: list[MapScan]) -> Merged:
    mg = Merged([s.map for s in scans], scans)
    for s in scans:
        mid = s.map.id
        for k, u in s.shaders.items():
            if k not in mg.shaders:
                mg.shaders[k] = ShaderUse()
                mg.shader_maps[k] = Counter()
            mg.shaders[k].merge(u)
            mg.shader_maps[k][mid] += u.uses
        for cls, cs in s.classes.items():
            m = mg.classes.get(cls)
            if m is None:
                m = mg.classes[cls] = ClassStats()
                mg.class_maps[cls] = set()
                mg.class_mp_maps[cls] = set()
            m.count += cs.count
            m.brush += cs.brush
            m.models.update(cs.models)
            mg.class_maps[cls].add(mid)
            if s.map.mp:
                mg.class_mp[cls] += cs.count
                mg.class_mp_maps[cls].add(mid)
            for k, ks in cs.keys.items():
                mk = m.keys.get(k)
                if mk is None:
                    mk = m.keys[k] = KeyStats()
                mk.count += ks.count
                for v in ks.examples:
                    mk.example(v)
        for mk_, mu in s.models.items():
            m2 = mg.models.get(mk_)
            if m2 is None:
                m2 = mg.models[mk_] = ModelUse()
                mg.model_maps[mk_] = Counter()
            m2.count += mu.count
            m2.classnames.update(mu.classnames)
            m2.spellings.update(mu.spellings)
            m2.scale.update(mu.scale)
            m2.angle.update(mu.angle)
            m2.scale_set += mu.scale_set
            m2.angle_set += mu.angle_set
            m2.angles.count += mu.angles.count
            for v in mu.angles.examples:
                m2.angles.example(v)
            mg.model_maps[mk_][mid] += mu.count
    return mg


def _top_maps(c: Counter, order: dict[str, int], n: int = MAP_LIST) -> list[str]:
    return [m for m, _ in sorted(c.items(), key=lambda kv: (-kv[1], order[kv[0]]))[:n]]


def _top(c: Counter, n: int) -> list[list[Any]]:
    return [[k, v] for k, v in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))[:n]]


def _meta(mg: Merged, what: str, **extra: Any) -> dict[str, Any]:
    groups = Counter(m.group for m in mg.maps)
    return {"what": what, "generator": "python -m mohkit.catalog", "maps": len(mg.maps),
            "groups": dict(groups), "mp_maps": sum(m.mp for m in mg.maps), **extra}


# ---------------------------------------------------------------------------
# Output builders


def build_materials(mg: Merged, retail: Retail) -> dict[str, Any]:
    order = {m.id: i for i, m in enumerate(mg.maps)}
    out: dict[str, Any] = {}
    for k in sorted(mg.shaders, key=lambda k: (-mg.shaders[k].uses, k)):
        u = mg.shaders[k]
        avail, fs, idx = retail.shader_home(k)
        sd: Optional[ShaderDef] = idx.get(k) if idx else None
        e: dict[str, Any] = {"uses": u.uses, "faces": u.faces}
        if u.patches:
            e["patches"] = u.patches
        if u.terrain:
            e["terrain"] = u.terrain
        e["maps"] = len(mg.shader_maps[k])
        e["map_list"] = _top_maps(mg.shader_maps[k], order)
        if u.faces:
            e["orient"] = {"floor": u.floor, "wall": u.wall, "ceiling": u.ceiling}
            if u.degenerate:
                e["orient"]["degenerate"] = u.degenerate
            area = u.floor_area + u.wall_area + u.ceiling_area
            e["area"] = round(area)
            if area > 0:
                e["orient_area"] = {"floor": _r(u.floor_area / area, 3), "wall": _r(u.wall_area / area, 3),
                                    "ceiling": _r(u.ceiling_area / area, 3)}
            (sc, n_sc), = u.scales.most_common(1)
            e["scale"] = list(sc)
            e["scale_share"] = _r(n_sc / u.faces, 3)
            if len(u.scales) > 1:
                e["scales"] = [[a, b, n] for (a, b), n in u.scales.most_common(3)]
            (rot, n_rot), = u.rotations.most_common(1)
            e["rotation"] = rot
            e["rotation_share"] = _r(n_rot / u.faces, 3)
            e["detail"] = _r(u.detail / u.faces, 3)
            if u.face_parms:
                e["face_parms"] = dict(u.face_parms.most_common(4))
        e["avail"] = avail
        e["tool"] = is_tool(k)
        e["script"] = sd.source if sd else None
        if fs is not None and idx is not None:
            img = idx.resolve_image(k)
            info = fs.image_info(img) if img else None
            e["image"] = img
            e["size"] = [info.width, info.height] if info else None
            if info and info.has_alpha:
                e["alpha"] = True
        else:
            e["image"], e["size"] = None, None
        parms = list(dict.fromkeys(sd.surfaceparms)) if sd else []
        e["parms"] = parms
        e["material"] = sd.material if sd else None
        if sd and sd.unknown_parms:
            e["unknown_parms"] = sd.unknown_parms
        e["transparent"] = bool(sd and sd.transparent)
        if sd and sd.is_sky:
            e["sky"] = sd.skyparms[0] if sd.skyparms else True
        if sd and sd.qer_keywords:
            e["keywords"] = list(dict.fromkeys(sd.qer_keywords))
        out[k] = e
    return out


def style_stats(mg: Merged) -> dict[str, Any]:
    """Corpus-wide face statistics over non-tool shaders."""
    scales: Counter = Counter()
    rots: Counter = Counter()
    faces = detail = 0
    for k, u in mg.shaders.items():
        if is_tool(k):
            continue
        scales.update(u.scales)
        rots.update(u.rotations)
        faces += u.faces
        detail += u.detail
    return {"faces": faces, "detail": _r(detail / faces, 3) if faces else 0,
            "scales": [[a, b, n] for (a, b), n in scales.most_common(10)],
            "rotations": [[r, n] for r, n in rots.most_common(6)]}


def build_entities(mg: Merged) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cls in sorted(mg.classes, key=lambda c: (-mg.classes[c].count, c)):
        cs = mg.classes[cls]
        e: dict[str, Any] = {"count": cs.count, "maps": len(mg.class_maps[cls]),
                             "mp_count": mg.class_mp[cls], "mp_maps": len(mg.class_mp_maps[cls])}
        if cs.brush:
            e["brush"] = cs.brush
        e["keys"] = {k: {"count": ks.count, "examples": ks.examples}
                     for k, ks in sorted(cs.keys.items(), key=lambda kv: (-kv[1].count, kv[0]))}
        if cs.models:
            e["models"] = _top(cs.models, 10)
        out[cls] = e
    return out


def build_models(mg: Merged, retail: Retail) -> tuple[dict[str, Any], Counter]:
    order = {m.id: i for i, m in enumerate(mg.maps)}
    out: dict[str, Any] = {}
    notes: Counter = Counter()
    readers: dict[int, TikiReader] = {}
    for k in sorted(mg.models, key=lambda k: (-mg.models[k].count, k)):
        mu = mg.models[k]
        avail, fs = retail.file_home(k)
        e: dict[str, Any] = {"count": mu.count, "maps": len(mg.model_maps[k]),
                             "map_list": _top_maps(mg.model_maps[k], order),
                             "classnames": _top(mu.classnames, 3), "spellings": _top(mu.spellings, 3),
                             "avail": avail}
        e["scale"] = {"set": mu.scale_set, "top": _top(mu.scale, 4)} if mu.scale_set else None
        e["angle"] = {"set": mu.angle_set, "top": _top(mu.angle, 4)} if mu.angle_set else None
        e["angles"] = {"set": mu.angles.count, "examples": mu.angles.examples[:3]} if mu.angles.count else None
        if fs is not None:
            reader = readers.get(id(fs))
            if reader is None:
                reader = readers[id(fs)] = TikiReader(fs)
            info = reader.read(k)
            e["path"] = info.path
            e["tiki_scale"] = _r(info.scale, 4)
            e["skelmodel"] = info.skelmodels[0] if info.skelmodels else None
            e["idle"] = info.anims.get("idle")
            b, why = model_bounds(fs, info)
            e["bounds"] = [b[0], b[1]] if b else None
            if why:
                e["bounds_note"] = why
                notes[why.split(":")[0]] += 1
            e["editor_bounds"] = list(info.editor_bounds) if info.editor_bounds else None
            if info.setsize:
                e["setsize"] = list(info.setsize)
            if info.quaked:
                e["quaked"] = info.quaked
            cpath = collision_map_path(k)
            e["collision_map"] = fs.exists(cpath)
            if e["collision_map"]:
                c = read_collision(fs, cpath)
                e["collision"] = {"path": c.path, "brushes": c.brushes,
                                  "bounds": [c.bounds[0], c.bounds[1]] if c.bounds else None, "clip": c.clip}
                notes["collision map"] += 1
            if info.missing_includes:
                e["missing_includes"] = info.missing_includes
        else:
            e["collision_map"] = None
            notes["model missing"] += 1
        out[k] = e
    return out, notes


def build_worldspawn(mg: Merged) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for s in mg.scans:
        m = s.map
        out[m.id] = {
            "file": m.path, "group": m.group, "mp": m.mp, "bytes": m.size, "sha1": m.sha1,
            **({"aliases": m.aliases} if m.aliases else {}),
            "worldspawn": s.worldspawn,
            "counts": {"entities": s.entities, "brushes": s.brushes, "faces": s.faces, "patches": s.patches,
                       "terrain": s.terrains},
            "lights": s.lights,
            "spawns": dict(sorted(s.spawns.items())),
            **({"anomalies": dict(s.anomalies)} if s.anomalies else {}),
        }
    return out


def build_palettes(mg: Merged, materials: dict[str, Any], n: int = 25) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for s in mg.scans:
        if not s.map.mp:
            continue
        rows = sorted(((k, u.uses) for k, u in s.shaders.items() if not is_tool(k)), key=lambda kv: (-kv[1], kv[0]))
        out[s.map.id] = {"group": s.map.group,
                         "shaders": [[k, c, materials[k]["avail"]] for k, c in rows[:n]]}
    return out


# ---------------------------------------------------------------------------
# JSON writing


def _compact(v: Any) -> str:
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def dumps_lines(obj: dict[str, Any], expand: Iterable[str]) -> str:
    """Valid JSON with one line per item of the ``expand`` top-level mappings (diff friendly)."""
    exp = set(expand)
    lines = ["{"]
    items = list(obj.items())
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if k in exp and isinstance(v, dict):
            lines.append(f"{json.dumps(k)}: {{")
            sub = list(v.items())
            for j, (k2, v2) in enumerate(sub):
                lines.append(f"  {json.dumps(k2, ensure_ascii=False)}: {_compact(v2)}{',' if j < len(sub) - 1 else ''}")
            lines.append("}" + comma)
        else:
            lines.append(f"{json.dumps(k)}: {_compact(v)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _write(path: str, text: str) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return len(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Markdown


def _pct(a: int, total: int) -> str:
    return f"{round(100 * a / total)}" if total else "0"


def _usage(e: dict[str, Any]) -> str:
    o = e.get("orient_area")
    parts = []
    if o:
        parts.append(f"F{round(100 * o['floor'])}/W{round(100 * o['wall'])}/C{round(100 * o['ceiling'])}")
    if e.get("patches"):
        parts.append(f"{e['patches']} patch")
    if e.get("terrain"):
        parts.append(f"{e['terrain']} terrain")
    return " ".join(parts)


def _scale(e: dict[str, Any]) -> str:
    if "scale" not in e:
        return ""
    a, b = e["scale"]
    s = f"{a:g}" if a == b else f"{a:g}×{b:g}"
    return f"{s} ({round(100 * e['scale_share'])}%)"


def _flags(e: dict[str, Any]) -> str:
    f = [p for p in e["parms"] if p in FLAG_PARMS]
    if e.get("transparent"):
        f.append("blend/alpha")
    return ", ".join(f)


def _esc(s: str) -> str:
    return s.replace("|", "\\|")


def materials_md(materials: dict[str, Any], retail: Retail, corpus: list[CorpusMap],
                 models: Optional[dict[str, Any]] = None, style: Optional[dict[str, Any]] = None,
                 per_theme: int = 25) -> str:
    themes: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for k, e in materials.items():
        if not e["tool"]:
            themes[k.split("/")[0] if "/" in k else "(root)"].append((k, e))
    theme_uses = {t: sum(e["uses"] for _, e in rows) for t, rows in themes.items()}
    aa_themes = [t for t in themes if any(e["avail"] == "aa" for _, e in themes[t])]
    exp_themes = [t for t in themes if t not in aa_themes and any(e["avail"] != "missing" for _, e in themes[t])]
    missing_themes = [t for t in themes if t not in aa_themes and t not in exp_themes]
    sizes = Counter(tuple(e["size"]) for e in materials.values() if e["size"] and not e["tool"] and e["avail"] == "aa")
    sizes_w: Counter = Counter()
    for e in materials.values():
        if e["size"] and not e["tool"] and e["avail"] == "aa":
            sizes_w[tuple(e["size"])] += e["faces"]
    face_total = sum(e["faces"] for e in materials.values() if not e["tool"])
    style = style or {"scales": [], "rotations": [], "detail": 0}
    groups = Counter(m.group for m in corpus)
    L = ["# Stock material reference",
         "",
         "Generated by `python -m mohkit.catalog` from the stock map sources "
         f"({', '.join(f'{n} {g}' for g, n in groups.items())}; byte-identical `bt/` copies of Spearhead MP maps "
         "counted once) resolved against the retail paks. Do not edit by hand; data lives in "
         "[`data/materials.json`](../../data/materials.json).",
         "",
         "Columns: **px** image size the compiler scales texture coordinates by (editor image, else "
         "implicit `textures/<name>` image); **scale** most common face scale and its share; **F/W/C** "
         "share of brush-face *area* that faces up (normal z > 0.7), sideways, down (z < -0.7), plus patch "
         "and terrain-cell counts (face-count shares are in the JSON); **material** "
         "the footstep/impact surfaceparm (`stone`/`plaster` are *not* recognised by MOHAA Q3map, see "
         "below); **flags** other notable surfaceparms; **maps** number of maps and the top users. "
         "**avail**: `aa` = retail AA paks, `sh`/`bt` = only with Spearhead/Breakthrough data.",
         "",
         "## Overview",
         "",
         f"- {sum(1 for e in materials.values() if not e['tool'])} non-tool shaders on {face_total} brush faces; "
         f"availability: {dict(Counter(e['avail'] for e in materials.values()))}.",
         "- Face scale (all non-tool faces): "
         + ", ".join(f"{a:g}×{b:g} {100 * n / face_total:.1f}%" for a, b, n in style["scales"][:6])
         + ". Stock sources store `1 1` for almost everything (one texel per unit: a 256 px texture "
         "tiles every 256 units); 0.5 is the next most common. Rotation: "
         + ", ".join(f"{r:g}° {100 * n / face_total:.1f}%" for r, n in style["rotations"][:3])
         + f". {round(100 * style['detail'])}% of non-tool faces carry `+surfaceparm detail`.",
         "- AA texture sizes (distinct materials used): "
         + ", ".join(f"{w}×{h}: {n}" for (w, h), n in sizes.most_common(8))
         + "; by faces: " + ", ".join(f"{w}×{h} {_pct(n, face_total)}%" for (w, h), n in sizes_w.most_common(5)) + ".",
         "- `surfaceparm stone` (552 AA shaders) and `plaster` are unknown to the shipped MOHAA Q3map and "
         "the OpenMoHAA surfaceparm table, which use `rock`; the Spearhead/Breakthrough copies of the same "
         "scripts replaced `stone` with `rock`. A custom AA shader should use `rock`.",
         "",
         "## Themes available in Allied Assault",
         ""]
    for t in sorted(aa_themes, key=lambda t: -theme_uses[t]):
        L += _theme_table(t, themes[t], theme_uses[t], per_theme)
    if exp_themes:
        L += ["## Expansion-only themes (need Spearhead/Breakthrough data)", ""]
        for t in sorted(exp_themes, key=lambda t: -theme_uses[t]):
            L += _theme_table(t, themes[t], theme_uses[t], min(per_theme, 12))
    if missing_themes:
        L += ["## Not in any retail pak", "",
              "Community textures shipped with their own maps, and typos in stock sources:", ""]
        for t in sorted(missing_themes, key=lambda t: -theme_uses[t]):
            rows = sorted(themes[t], key=lambda kv: -kv[1]["uses"])
            maps = sorted({m for _, e in rows for m in e["map_list"]})
            L.append(f"- `{t}/`: {len(rows)} materials, {theme_uses[t]} uses in {', '.join(maps[:4])}")
        L.append("")
    L += _common_section(materials, retail)
    if models:
        L += _props_section(models)
    return "\n".join(L).rstrip() + "\n"


def _dims(b: Optional[list[list[float]]]) -> str:
    if not b:
        return ""
    return "×".join(f"{hi - lo:g}" for lo, hi in zip(b[0], b[1]))


def _box(b: Optional[list[list[float]]]) -> str:
    if not b:
        return ""
    return f"({' '.join(f'{x:g}' for x in b[0])})–({' '.join(f'{x:g}' for x in b[1])})"


def _props_section(models: dict[str, Any], n_with: int = 45, n_without: int = 25) -> list[str]:
    static = {k: e for k, e in models.items() if e["avail"] == "aa" and e.get("classnames")
              and e["classnames"][0][0].startswith("static_")}
    with_c = sorted((k for k, e in static.items() if e.get("collision_map")),
                    key=lambda k: (-static[k]["maps"], -static[k]["count"], k))
    without = sorted((k for k, e in static.items() if not e.get("collision_map")),
                     key=lambda k: (-static[k]["maps"], -static[k]["count"], k))
    total_c = sum(1 for e in models.values() if e.get("collision_map"))
    L = ["## Props (static models) and collision", "",
         "Q3map bakes `static_*` model entities into the BSP. A model gets collision only if a companion "
         "`models/<same path>.map` exists (\"static collision mask\": clip brushes in model-local game units at "
         "entity scale 1, all 311 of them in Pak0); otherwise it has none and needs hand-placed clip brushes. "
         f"{total_c} of {len(models)} referenced models have one. Sizes are w×d×h in game units at scale 1; "
         "**collision** is the clip-brush AABB (a reliable footprint), **render** the idle-animation bounds × "
         "TIKI scale. Trees and pines only clip the trunk. Data: "
         "[`data/static_models.json`](../../data/static_models.json).", "",
         f"### Most used AA props with collision (top {n_with} by maps)", "",
         "| model | uses | maps | collision w×d×h | collision mins–maxs | clip | render w×d×h | typical scale |",
         "|---|---|---|---|---|---|---|---|"]
    for k in with_c[:n_with]:
        e = static[k]
        c = e["collision"]
        clip = ", ".join(x[0].split("/")[-1] for x in c["clip"][:2])
        sc = e["scale"]["top"][0][0] if e.get("scale") else 1
        L.append(f"| `{k[len('models/'):]}` | {e['count']} | {e['maps']} | {_dims(c['bounds'])} | {_box(c['bounds'])} "
                 f"| {clip} | {_dims(e.get('bounds'))} | {sc} |")
    L += ["", f"### Most used AA props without collision (top {n_without} by maps)", "",
          "These need clip brushes (e.g. `common/woodclip`, `common/metalclip`) where players can touch them.", "",
          "| model | uses | maps | render w×d×h | render mins–maxs | editor (QUAKED) box |", "|---|---|---|---|---|---|"]
    for k in without[:n_without]:
        e = static[k]
        L.append(f"| `{k[len('models/'):]}` | {e['count']} | {e['maps']} | {_dims(e.get('bounds'))} | "
                 f"{_box(e.get('bounds'))} | {_box(e.get('editor_bounds'))} |")
    L.append("")
    return L


def _theme_table(theme: str, rows: list[tuple[str, dict]], uses: int, n: int) -> list[str]:
    rows = sorted(rows, key=lambda kv: (-kv[1]["uses"], kv[0]))
    L = [f"### {theme}", "", f"{len(rows)} materials, {uses} uses."
         + (f" Showing top {n}." if len(rows) > n else ""), "",
         "| material | px | scale | F/W/C | material | flags | maps | avail |",
         "|---|---|---|---|---|---|---|---|"]
    for k, e in rows[:n]:
        size = f"{e['size'][0]}×{e['size'][1]}" if e["size"] else "?"
        maps = f"{e['maps']}: " + ", ".join(m.split("/")[1] for m in e["map_list"][:3])
        L.append(f"| `{_esc(k)}` | {size} | {_scale(e)} | {_usage(e)} | {e['material'] or ''} | {_flags(e)} "
                 f"| {_esc(maps)} | {e['avail']} |")
    L.append("")
    return L


_COMMON_PURPOSE = {
    "caulk": "Hidden faces: no draw, no lightmap, still solid and structural. Use on every face players never see.",
    "nodraw": "Invisible and non-solid (`nonsolid`, `trans`); not a replacement for caulk.",
    "caulkshadow": "Invisible, casts shadows (`castshadow`).",
    "sunblock": "Invisible `alphashadow` blocker for sunlight.",
    "clip": "Invisible player+monster clip (no bullets).",
    "playerclip": "Invisible player-only clip.",
    "monster": "Invisible AI (monster) clip.",
    "weapon": "Invisible weapon clip (bullets only). There is no `common/weaponclip`.",
    "clipall": "Invisible player+monster+vehicle+weapon clip.",
    "vehicleclip": "Invisible vehicle clip.",
    "tankclip": "Metal-sounding player/monster/vehicle/weapon clip for tanks.",
    "hint": "BSP hint portal (`hint`, `structural`).",
    "skip": "Non-drawn, non-solid side of hint brushes.",
    "areaportal": "Area portal separating areas (doors).",
    "origin": "Rotation origin brush for movers.",
    "trigger": "Trigger brushes (nodraw only; solidity comes from the entity).",
    "ladder": "Ladder surface.",
    "sky": "",
    "caulksky": "Sky that draws nothing (fogged maps); `skyParms env/idontexist`.",
    "skyportal": "Portal sky surface.",
    "vis": "Hint variant (`hint`, `structural`, `nonsolid`).",
    "snowclip": "Solid invisible collision with snow impacts/footsteps.",
    "rain": "Marks rain volumes for the weather system (nodraw only).",
    "black": "Plain black surface (no lightmap).",
    "blank_lightmap": "White lightmapped surface (lighting tests, blockout).",
    "static_visible": "Semi-transparent nonsolid white, used in static-model collision `.map` files.",
    "modelshader": "Invisible, used on model tags/helpers.",
    "light": "Fullbright white light panel.",
    "patharea": "Editor helper for AI path areas.",
    "white_volumetric": "Additive volumetric light beam.",
    "adjustable_volumetric": "Volumetric beam tinted by the entity color.",
    "adjustable_volumetric2": "Volumetric beam tinted by the entity color.",
    "adjustable_color": "Surface tinted by the entity color (filter blend).",
    "switchflat": "Wall switch plate.",
    "switchflat_pulse": "Pulsing wall switch plate.",
    "blastmark3": "Decal-style blast mark (alpha-tested).",
    "rope": "Rope sprite texture.",
    "waterskip": "Water volume side without drawing.",
    "portal": "Mirror/portal surface.",
}


def _common_section(materials: dict[str, Any], retail: Retail) -> list[str]:
    L = ["## Tool shaders (`common/*`)", "",
         "From `scripts/common.shader` in Pak0 (winning definitions). Collision-material clips "
         "(`woodclip`, `metalclip`, `stoneclip`, `dirtclip`, `grassclip`, ...) are `nodraw`, `trans`, "
         "`nomarks` plus a material parm: they stay solid and set the bullet-impact/footstep sound. "
         "`clip`/`playerclip`/`weapon`/`clipall`/`vehicleclip` are `nonsolid` plus clip contents. "
         "`foliageclip` is `shootonly` (bullets only). `grillclip`/`bplaneclip`/`hedgehogclip` add "
         "`fence` and all clip contents. **uses** is the corpus usage count.", "",
         "| shader | surfaceparms | purpose (script comment) | uses |", "|---|---|---|---|"]
    common = sorted((sd for sd in retail.aa if sd.key.startswith("textures/common/")), key=lambda sd: sd.key)
    for sd in common:
        short = sd.key[len("textures/"):]
        purpose = _COMMON_PURPOSE.get(short.split("/", 1)[1], "") or sd.comment.replace("\n", " ")
        if sd.comment and purpose != sd.comment.replace("\n", " "):
            purpose = f"{purpose} ({sd.comment.splitlines()[0]})" if purpose else sd.comment.splitlines()[0]
        parms = ", ".join(sd.surfaceparms)
        if sd.skyparms is not None:
            parms += f"; skyParms {' '.join(sd.skyparms)}"
        uses = materials.get(short, {}).get("uses", 0)
        L.append(f"| `{short}` | {parms} | {_esc(purpose)} | {uses} |")
    used_missing = [k for k, e in materials.items() if e["tool"] and e["avail"] != "aa"]
    L.append("")
    if used_missing:
        L.append("Tool names used in the corpus but not defined for AA: "
                 + ", ".join(f"`{k}` ({materials[k]['uses']}, {materials[k]['avail']})" for k in used_missing) + ".")
        L.append("")
    return L


_ENTITY_GROUPS: tuple[tuple[str, str], ...] = (
    ("World", r"^worldspawn$"),
    ("Player spawns and intermission", r"^info_player"),
    ("Lights and light helpers", r"^(light|lightstyle)"),
    ("Structure groups", r"^(func_group|detail|func_static|func_areaportal|func_explodingwall|func_window)$"),
    ("Doors, movers, ladders", r"^func_"),
    ("Triggers", r"^trigger_"),
    ("Script entities", r"^script_"),
    ("Paths and AI nodes", r"^(info_|ai_|actor|path|node)"),
    ("Animated models", r"^animate_"),
    ("Static models (Q3map bakes these into the BSP)", r"^static_"),
    ("Effects and emitters", r"^(fx_|emitter|misc_|func_emitter)"),
    ("Sounds", r"^sound"),
    ("Items, weapons, ammo", r"^(item_|weapon_|ammo_|health)"),
    ("Vehicles and turrets", r"^(vehicle|turret|statweapons|mg42|tank)"),
)


def _entity_group(cls: str) -> str:
    for title, pat in _ENTITY_GROUPS:
        if re.search(pat, cls):
            return title
    return "Other"


def entities_md(entities: dict[str, Any], corpus: list[CorpusMap], mg: Merged) -> str:
    aa_mp = [m.id for m in corpus if m.group == "aa" and m.mp]
    sub = build_entities(merge([s for s in mg.scans if s.map.id in set(aa_mp)]))
    groups: dict[str, list[str]] = defaultdict(list)
    for cls in entities:
        groups[_entity_group(cls)].append(cls)
    L = ["# Stock entity reference", "",
         "Generated by `python -m mohkit.catalog` from the stock map sources; data in "
         "[`data/entities.json`](../../data/entities.json). **count** entities, **maps** maps using the class, "
         "**MP** count in multiplayer maps (`mohdm*`, `obj_team*`, `mp_*`, `*_obj/_dm/_tow/_lib`, community "
         "objective maps). Keys are listed by frequency with an example value.", "",
         "Keys starting with `#` or `$` are handled by `SpawnArgs::Spawn` (OpenMoHAA fgame/g_spawn.cpp): "
         "`#name` is numeric and `$name` a string; each calls the setter event of that name when the class has "
         "one (so `$targetname` sets the targetname) and otherwise becomes a script variable on the entity "
         "(`#set 500` → `self.set`).", "",
         "## What the stock AA multiplayer maps use", "",
         f"Counts and keys below are from {', '.join(m.split('/')[1] for m in aa_mp)} only. "
         "Static models are summarised after the table.", "",
         "| class | count | maps | keys (count: example) |", "|---|---|---|---|"]
    statics = []
    for cls, e in sub.items():
        if cls.startswith("static_"):
            statics.append((cls, e))
            continue
        L.append(f"| `{cls}` | {e['count']} | {e['maps']} | {_keys_summary(e, 7)} |")
    L += ["", f"Static models in AA MP: {sum(e['count'] for _, e in statics)} entities of {len(statics)} classes; "
          "most used: " + ", ".join(f"`{c}` {e['count']}" for c, e in statics[:15]) + ". Their keys are "
          "`model`, `origin`, `scale`, `angle`/`angles` and the editor-only `testanim`.", ""]
    for title, _ in list(_ENTITY_GROUPS) + [("Other", "")]:
        classes = groups.get(title)
        if not classes:
            continue
        classes.sort(key=lambda c: (-entities[c]["count"], c))
        L += [f"## {title}", ""]
        limit = 60 if title.startswith("Static models") else 200
        L += ["| class | count | maps | MP | keys (count: example) |", "|---|---|---|---|---|"]
        for cls in classes[:limit]:
            e = entities[cls]
            keys = _keys_summary(e, 8 if not cls.startswith("static_") else 4)
            if e.get("models") and not cls.startswith("static_"):
                keys += "; models: " + ", ".join(f"`{m}` ({n})" for m, n in e["models"][:3])
            L.append(f"| `{cls}` | {e['count']} | {e['maps']} | {e['mp_count']} | {keys} |")
        if len(classes) > limit:
            L.append(f"| … {len(classes) - limit} more | | | | |")
        L.append("")
        if title.startswith("Static models"):
            L += ["Only models with a companion collision `.map` are solid; see "
                  "[materials.md → Props](materials.md#props-static-models-and-collision).", ""]
    return "\n".join(L).rstrip() + "\n"


_SKIP_KEYS = {"classname"}


def _keys_summary(e: dict[str, Any], n: int) -> str:
    parts = []
    for k, ks in e["keys"].items():
        if k in _SKIP_KEYS:
            continue
        ex = ks["examples"][0] if ks["examples"] else ""
        ex = ex if len(ex) <= 28 else ex[:25] + "..."
        parts.append(f"`{_esc(k)}` {ks['count']}: {_esc(ex)}")
        if len(parts) >= n:
            break
    more = len([k for k in e["keys"] if k not in _SKIP_KEYS]) - len(parts)
    return "; ".join(parts) + (f"; +{more} more" if more > 0 else "")


# ---------------------------------------------------------------------------
# Driver


def run(out_dir: str, game_dir: str = DEFAULT_GAME_DIR, docs_dir: Optional[str] = None, jobs: int = 0,
        root: str = REPO, verbose: bool = True) -> dict[str, int]:
    log = (lambda *a: print(*a, file=sys.stderr, flush=True)) if verbose else (lambda *a: None)
    t0 = time.time()
    corpus = discover_corpus(root)
    log(f"corpus: {len(corpus)} maps ({sum(len(m.aliases) for m in corpus)} duplicate copies dropped)")
    jobs = jobs or max(1, min(8, (os.cpu_count() or 2) - 1))
    worker = importlib.import_module("mohkit.catalog").scan_map
    if jobs == 1:
        scans = [worker(m, root) for m in corpus]
    else:
        with ProcessPoolExecutor(jobs) as ex:
            scans = list(ex.map(worker, corpus, [root] * len(corpus)))
    log(f"parsed in {time.time() - t0:.1f}s (cpu {sum(s.seconds for s in scans):.1f}s)")
    mg = merge(scans)
    retail = Retail.load(game_dir)
    log(f"retail: AA {len(retail.aa)} shaders" + "".join(f", {t} {len(i)}" for t, _, i in retail.exp))

    materials = build_materials(mg, retail)
    style = style_stats(mg)
    entities = build_entities(mg)
    models, model_notes = build_models(mg, retail)
    worldspawn = build_worldspawn(mg)
    palettes = build_palettes(mg, materials)
    corpus_meta = [{"id": m.id, "file": m.path, "mp": m.mp, **({"aliases": m.aliases} if m.aliases else {})}
                   for m in corpus]
    avail = Counter(e["avail"] for e in materials.values())
    anomalies: dict[str, dict[str, int]] = defaultdict(dict)
    for sc in scans:
        for kind, n in sc.anomalies.items():
            anomalies[kind][sc.map.id] = n
    stock_missing = sorted(k for k, e in materials.items()
                           if e["avail"] == "missing" and any(not m.startswith("aa_custom/") for m in e["map_list"]))
    sizes: dict[str, int] = {}
    sizes["materials.json"] = _write(os.path.join(out_dir, "materials.json"), dumps_lines({
        "meta": _meta(mg, "shaders used on brush faces, patches and terrain in the stock corpus",
                      shaders=len(materials), avail=dict(avail), style=style, anomalies=dict(anomalies),
                      missing_in_stock_maps=stock_missing,
                      fields={"uses": "faces + patches + terrain cells", "orient": "brush faces by outward normal z: "
                              "floor > 0.7, ceiling < -0.7, else wall", "orient_area": "same, as area fractions",
                              "area": "total brush-face area (units^2)", "scale": "most common (scaleS, scaleT)",
                              "scales": "top 3 [s, t, faces]", "detail": "fraction of faces with +surfaceparm detail",
                              "face_parms": "other per-face surfaceparm overrides", "avail": "aa | sh | bt | sh+bt | missing",
                              "image": "editor image, else implicit, else first non-env stage image",
                              "size": "image pixels", "alpha": "image has an alpha channel",
                              "parms": "surfaceparms of the winning shader definition",
                              "material": "first material surfaceparm", "transparent": "alphaFunc or blended first stage",
                              "tool": "common/* or notexture; excluded from palettes/style stats"},
                      corpus=corpus_meta),
        "materials": materials}, ["materials"]))
    sizes["entities.json"] = _write(os.path.join(out_dir, "entities.json"), dumps_lines({
        "meta": _meta(mg, "entity classnames and keys in the stock corpus", classes=len(entities),
                      fields={"count": "entities", "maps": "maps using the class", "mp_count": "entities in MP maps",
                              "brush": "entities with brushes/patches/terrain",
                              "keys": "key -> count and up to 5 distinct example values (truncated to 100 chars)",
                              "models": "top model keys (normalized to models/...)"}),
        "classes": entities}, ["classes"]))
    sizes["static_models.json"] = _write(os.path.join(out_dir, "static_models.json"), dumps_lines({
        "meta": _meta(mg, ".tik models referenced by entity model keys", models=len(models),
                      avail=dict(Counter(e["avail"] for e in models.values())), bounds_notes=dict(model_notes),
                      fields={"bounds": "union of idle .skc frame bounds x TIKI setup scale (entity scale 1)",
                              "editor_bounds": "/*QUAKED comment mins/maxs in the .tik",
                              "spellings": "model key as written in maps", "scale/angle/angles": "entity key usage"}),
        "models": models}, ["models"]))
    sizes["worldspawn.json"] = _write(os.path.join(out_dir, "worldspawn.json"), dumps_lines({
        "meta": _meta(mg, "per-map worldspawn keys, light entity statistics and spawn counts",
                      fields={"lights.spot": "light entities with target or spot_* keys",
                              "lights.light": "stats of the numeric light key (default 300 when absent)"}),
        "maps": worldspawn}, ["maps"]))
    sizes["palettes.json"] = _write(os.path.join(out_dir, "palettes.json"), dumps_lines({
        "meta": _meta(mg, "25 most used non-tool shaders per multiplayer map", fields={
            "shaders": "[name, uses, avail]"}),
        "maps": palettes}, ["maps"]))
    docs = docs_dir or os.path.join(root, "docs", "reference")
    sizes["materials.md"] = _write(os.path.join(docs, "materials.md"), materials_md(materials, retail, corpus, models, style))
    sizes["entities.md"] = _write(os.path.join(docs, "entities.md"), entities_md(entities, corpus, mg))
    log("wrote " + ", ".join(f"{k} {v / 1024:.0f} KiB" for k, v in sizes.items()) + f" in {time.time() - t0:.1f}s")
    return sizes


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mohkit.catalog", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join(REPO, "data"), help="output directory for JSON (default: data/)")
    ap.add_argument("--docs", default=None, help="output directory for Markdown (default: docs/reference/)")
    ap.add_argument("--game", default=DEFAULT_GAME_DIR, help="game directory holding main/, mainta/, maintt/")
    ap.add_argument("--jobs", type=int, default=0, help="worker processes (default: cpu count - 1, max 8)")
    ap.add_argument("--root", default=REPO, help="repository root holding the corpus")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)
    run(a.out, a.game, a.docs, a.jobs, a.root, not a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
