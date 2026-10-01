"""Read and write MOHAA ``.map`` source files.

The MOHAA dialect is the Quake 3 "old brush" format plus:

* per-face extensions after the eight numeric fields, e.g.
  ``+surfaceparm detail``, ``-surfaceparm solid``, ``surfaceDensity 16``,
  ``subdivisions 4``, ``surfaceColor r g b``;
* the same extensions inside a ``patchDef2`` header;
* ``terrainDef`` blocks (LOD terrain, 64-unit height samples).

Face line::

    ( x y z ) ( x y z ) ( x y z ) shader shiftS shiftT rotate scaleS scaleT contents flags value [ext...]

``patchDef2`` header is ``( rows cols contents flags value [ext...] )`` followed by
``rows`` lines of ``cols`` control points ``( x y z s t )``. MOH Q3map reads the first
number as the number of row records, the second as points per row.

The parser is line oriented (all stock EA maps, MOHRadiant and NetRadiant output
are), which keeps it fast enough for the 15 MB stock sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Optional, Union

from . import geom
from .geom import Plane, Vec3

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_PT = rf"\(\s*({NUM})\s+({NUM})\s+({NUM})\s*\)"
FACE_RE = re.compile(rf"^\s*{_PT}\s*{_PT}\s*{_PT}\s*(\S+)\s+(.*)$")
KV_RE = re.compile(r'^\s*"([^"]*)"\s+"([^"]*)"\s*$')  # Q3 strings have no escapes
CTRL_RE = re.compile(rf"\(\s*({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s*\)")


def fmt(x: float) -> str:
    """Compact number formatting: integers without decimals, otherwise <= 6 decimals."""
    if isinstance(x, int):
        return str(x)
    r = round(x)
    if abs(x - r) < 1e-6:
        return str(int(r)) if r != 0 else "0"
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _num(s: str) -> float:
    v = float(s)
    return int(v) if v.is_integer() and "e" not in s.lower() and abs(v) < 2**53 else v


class MapParseError(ValueError):
    pass


@dataclass
class Face:
    points: tuple[Vec3, Vec3, Vec3]
    shader: str
    shift: tuple[float, float] = (0, 0)
    rotate: float = 0
    scale: tuple[float, float] = (0.5, 0.5)
    contents: int = 0
    flags: int = 0
    value: int = 0
    ext: list[str] = field(default_factory=list)

    @property
    def plane(self) -> Plane:
        return Plane.from_points(*self.points)

    # --- extension helpers -------------------------------------------------
    def surfaceparms(self) -> list[tuple[str, str]]:
        out, t = [], self.ext
        for i, tok in enumerate(t):
            if tok in ("+surfaceparm", "-surfaceparm") and i + 1 < len(t):
                out.append((tok[0], t[i + 1]))
        return out

    def has_parm(self, name: str) -> bool:
        return ("+", name) in self.surfaceparms()

    def add_parm(self, name: str) -> None:
        if not self.has_parm(name):
            self.ext += ["+surfaceparm", name]

    def remove_parm(self, name: str) -> None:
        t, out, i = self.ext, [], 0
        while i < len(t):
            if t[i] == "+surfaceparm" and i + 1 < len(t) and t[i + 1] == name:
                i += 2
                continue
            out.append(t[i])
            i += 1
        self.ext = out

    def to_line(self) -> str:
        p = " ".join("( " + " ".join(fmt(c) for c in pt) + " )" for pt in self.points)
        nums = [fmt(self.shift[0]), fmt(self.shift[1]), fmt(self.rotate), fmt(self.scale[0]), fmt(self.scale[1]),
                str(int(self.contents)), str(int(self.flags)), str(int(self.value))]
        line = f"{p} {self.shader} {' '.join(nums)}"
        if self.ext:
            line += " " + " ".join(self.ext)
        return line


@dataclass
class Brush:
    faces: list[Face]

    def planes(self) -> list[Plane]:
        return [f.plane for f in self.faces]

    def windings(self) -> list[geom.Winding]:
        return geom.brush_windings(self.planes())

    def bounds(self) -> tuple[Vec3, Vec3]:
        return geom.bounds_of(p for w in self.windings() for p in w)

    def is_detail(self) -> bool:
        return any(f.has_parm("detail") for f in self.faces)

    def shaders(self) -> set[str]:
        return {f.shader for f in self.faces}


@dataclass
class Patch:
    shader: str
    ctrl: list[list[tuple[float, float, float, float, float]]]  # rows x cols of (x y z s t)
    contents: int = 0
    flags: int = 0
    value: int = 0
    ext: list[str] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return len(self.ctrl)

    @property
    def cols(self) -> int:
        return len(self.ctrl[0]) if self.ctrl else 0

    def bounds(self) -> tuple[Vec3, Vec3]:
        return geom.bounds_of((c[0], c[1], c[2]) for row in self.ctrl for c in row)


@dataclass
class TerrainControl:
    """One material control (one per 8x8 cell plus a trailing sentinel row/column)."""
    a: int
    b: int
    shader: str
    rest: list[str]  # numeric fields after the shader, kept verbatim

    def to_line(self) -> str:
        return f"{self.a} {self.b} ( {self.shader} {' '.join(self.rest)} )"


@dataclass
class TerrainSample:
    height: float
    flags1: list[str]
    flags2: list[str]

    def to_line(self) -> str:
        f1 = (" " + " ".join(self.flags1) + " ") if self.flags1 else " "
        f2 = (" " + " ".join(self.flags2) + " ") if self.flags2 else " "
        return f"{self.height:.6f} ({f1}) ({f2})"


@dataclass
class Terrain:
    """MOHAA ``terrainDef``: ``width x height`` samples spaced 64 units, starting at ``origin``.

    Samples are stored row-major (row = Y index, column = X index).
    """
    width: int
    height: int
    flags: int
    origin: Vec3
    controls: list[TerrainControl]
    samples: list[TerrainSample]

    def bounds(self) -> tuple[Vec3, Vec3]:
        hs = [s.height for s in self.samples] or [0.0]
        ox, oy, oz = self.origin
        return ((ox, oy, oz + min(hs)), (ox + (self.width - 1) * 64, oy + (self.height - 1) * 64, oz + max(hs)))


Primitive = Union[Brush, Patch, Terrain]


class Entity:
    def __init__(self, props: Optional[dict[str, str]] = None, prims: Optional[list[Primitive]] = None):
        self.props: dict[str, str] = dict(props or {})
        self.prims: list[Primitive] = list(prims or [])

    @property
    def classname(self) -> str:
        return self.props.get("classname", "")

    def get(self, key: str, default: str = "") -> str:
        return self.props.get(key, default)

    def __getitem__(self, key: str) -> str:
        return self.props[key]

    def __setitem__(self, key: str, value) -> None:
        self.props[key] = value if isinstance(value, str) else _fmt_value(value)

    def __contains__(self, key: str) -> bool:
        return key in self.props

    def origin(self) -> Optional[Vec3]:
        if "origin" not in self.props:
            return None
        v = [float(x) for x in self.props["origin"].split()]
        return (v[0], v[1], v[2])

    def brushes(self) -> list[Brush]:
        return [p for p in self.prims if isinstance(p, Brush)]

    def patches(self) -> list[Patch]:
        return [p for p in self.prims if isinstance(p, Patch)]

    def terrains(self) -> list[Terrain]:
        return [p for p in self.prims if isinstance(p, Terrain)]

    def __repr__(self) -> str:
        return f"Entity({self.classname!r}, {len(self.props)} keys, {len(self.prims)} prims)"


def _fmt_value(v) -> str:
    if isinstance(v, (tuple, list)):
        return " ".join(fmt(x) for x in v)
    if isinstance(v, float):
        return fmt(v)
    return str(v)


class MapFile:
    def __init__(self, entities: Optional[list[Entity]] = None):
        self.entities: list[Entity] = entities or [Entity({"classname": "worldspawn"})]

    @property
    def worldspawn(self) -> Entity:
        return self.entities[0]

    def find(self, classname: str) -> list[Entity]:
        return [e for e in self.entities if e.classname == classname]

    def iter_prims(self) -> Iterator[tuple[Entity, Primitive]]:
        for e in self.entities:
            for p in e.prims:
                yield e, p

    # ------------------------------------------------------------------ I/O
    @classmethod
    def load(cls, path: str) -> "MapFile":
        with open(path, "r", encoding="latin-1") as fh:
            return cls.parse(fh.read(), source=path)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="latin-1", newline="\n") as fh:
            fh.write(self.dumps())

    @classmethod
    def parse(cls, text: str, source: str = "<map>") -> "MapFile":
        return _Parser(text, source).parse()

    def dumps(self) -> str:
        out: list[str] = []
        w = out.append
        for ei, e in enumerate(self.entities):
            w(f"// entity {ei}\n{{\n")
            for k, v in e.props.items():
                w(f'"{k}" "{v}"\n')
            for bi, p in enumerate(e.prims):
                w(f"// brush {bi}\n")
                if isinstance(p, Brush):
                    w("{\n")
                    for f in p.faces:
                        w(f.to_line() + "\n")
                    w("}\n")
                elif isinstance(p, Patch):
                    ext = (" " + " ".join(p.ext)) if p.ext else ""
                    w(f"{{\npatchDef2\n{{\n{p.shader}\n( {p.rows} {p.cols} {int(p.contents)} {int(p.flags)} {int(p.value)}{ext} )\n(\n")
                    for row in p.ctrl:
                        w("( " + " ".join("( " + " ".join(fmt(c) for c in pt) + " )" for pt in row) + " )\n")
                    w(")\n}\n}\n")
                elif isinstance(p, Terrain):
                    o = p.origin
                    w(f"{{\nterrainDef\n{{\n{p.width} {p.height} {p.flags}\n{o[0]:.6f} {o[1]:.6f} {o[2]:.6f}\n{{\n")
                    for c in p.controls:
                        w(c.to_line() + "\n")
                    w("}\n{\n")
                    for s in p.samples:
                        w(s.to_line() + "\n")
                    w("}\n}\n}\n")
            w("}\n")
        return "".join(out)


_NUM_RE = re.compile(NUM)


def _loose_diff(x: str, y: str, tol: float) -> bool:
    """True if two texts differ by more than ``tol`` in any number, or at all elsewhere."""
    if x == y:
        return False
    return _NUM_RE.sub("#", x) != _NUM_RE.sub("#", y) or any(
        abs(float(p) - float(q)) > tol for p, q in zip(_NUM_RE.findall(x), _NUM_RE.findall(y)))


def compiled_difference(old: MapFile, new: MapFile, runtime: tuple[str, ...] = ("script_model",),
                        tol: float = 0.01) -> Optional[str]:
    """The first difference between two maps that needs a full compile, or None.

    Entities whose classname is in ``runtime`` are ignored: the game spawns them from the
    entity lump, which ``Q3map -onlyents`` rewrites without touching geometry, lighting or
    static models (``compile.update_entities``). Brush faces are compared by plane (the
    three points may be any three on it) and numbers may differ by ``tol``: re-placed props
    round their clip brushes differently in the last digit.
    """
    ea = [e for e in old.entities if e.classname not in runtime]
    eb = [e for e in new.entities if e.classname not in runtime]
    if len(ea) != len(eb):
        return f"{len(ea)} vs {len(eb)} entities outside {', '.join(runtime)}"
    for i, (x, y) in enumerate(zip(ea, eb)):
        where = f"entity {i} ({x.classname})"
        kx, ky = ("\n".join(f'"{k}" "{v}"' for k, v in e.props.items()) for e in (x, y))
        if _loose_diff(kx, ky, tol):
            return f"{where}: keys changed"
        if len(x.prims) != len(y.prims):
            return f"{where}: {len(x.prims)} vs {len(y.prims)} primitives"
        for j, (p, q) in enumerate(zip(x.prims, y.prims)):
            if type(p) is not type(q):
                return f"{where} primitive {j}: {type(p).__name__} vs {type(q).__name__}"
            if isinstance(p, Brush) and isinstance(q, Brush):
                if len(p.faces) != len(q.faces):
                    return f"{where} brush {j}: {len(p.faces)} vs {len(q.faces)} faces"
                for k, (f, g) in enumerate(zip(p.faces, q.faces)):
                    pf = f.plane
                    if geom.dot(pf.normal, g.plane.normal) < 0.9999 or max(abs(pf.distance(pt)) for pt in g.points) > tol:
                        return f"{where} brush {j} face {k}: plane moved"
                    lf, lg = f.to_line(), g.to_line()
                    if _loose_diff(lf[lf.rindex(")") + 1:], lg[lg.rindex(")") + 1:], tol):
                        return f"{where} brush {j} face {k}: surface changed"
            elif _loose_diff(MapFile([Entity(prims=[p])]).dumps(), MapFile([Entity(prims=[q])]).dumps(), tol):
                return f"{where} primitive {j} changed"
    return None


class _Parser:
    def __init__(self, text: str, source: str):
        self.lines = text.splitlines()
        self.i = 0
        self.source = source

    def err(self, msg: str) -> MapParseError:
        return MapParseError(f"{self.source}:{self.i + 1}: {msg}")

    def next(self) -> Optional[str]:
        """Next non-empty, non-comment line (stripped)."""
        while self.i < len(self.lines):
            s = self.lines[self.i].strip()
            self.i += 1
            if not s or s.startswith("//"):
                continue
            return s
        return None

    def expect(self, tok: str) -> None:
        s = self.next()
        if s != tok:
            raise self.err(f"expected {tok!r}, got {s!r}")

    def parse(self) -> MapFile:
        ents: list[Entity] = []
        while True:
            s = self.next()
            if s is None:
                break
            if s != "{":
                raise self.err(f"expected entity '{{', got {s[:40]!r}")
            ents.append(self.entity())
        if not ents:
            raise self.err("no entities")
        return MapFile(ents)

    def entity(self) -> Entity:
        e = Entity()
        while True:
            s = self.next()
            if s is None:
                raise self.err("EOF inside entity")
            if s == "}":
                return e
            if s == "{":
                e.prims.append(self.primitive())
                continue
            m = KV_RE.match(s)
            if not m:
                raise self.err(f"bad key/value line {s[:60]!r}")
            e.props[m.group(1)] = m.group(2)

    def primitive(self) -> Primitive:
        s = self.next()
        if s == "patchDef2":
            return self.patch()
        if s == "terrainDef":
            return self.terrain()
        faces: list[Face] = []
        while True:
            if s is None:
                raise self.err("EOF inside brush")
            if s == "}":
                if len(faces) < 4:
                    raise self.err(f"brush with {len(faces)} faces")
                return Brush(faces)
            faces.append(self.face(s))
            s = self.next()

    def face(self, s: str) -> Face:
        m = FACE_RE.match(s)
        if not m:
            raise self.err(f"bad face line {s[:80]!r}")
        g = m.groups()
        pts = tuple((_num(g[i]), _num(g[i + 1]), _num(g[i + 2])) for i in (0, 3, 6))
        rest = g[10].split()
        if len(rest) < 5:
            raise self.err("face has too few texture fields")
        nums = rest[:8]
        while len(nums) < 8:
            nums.append("0")
        return Face(pts, g[9], (_num(nums[0]), _num(nums[1])), _num(nums[2]), (_num(nums[3]), _num(nums[4])),
                    int(float(nums[5])), int(float(nums[6])), int(float(nums[7])), rest[8:])

    def patch(self) -> Patch:
        self.expect("{")
        shader = self.next()
        hdr = self.next()
        if not hdr or not hdr.startswith("("):
            raise self.err("bad patch header")
        toks = hdr.strip("()").split()
        rows, cols = int(toks[0]), int(toks[1])
        contents, flags, value = (int(float(t)) for t in toks[2:5])
        ext = toks[5:]
        self.expect("(")
        ctrl = []
        for _ in range(rows):
            line = self.next() or ""
            pts = [tuple(_num(x) for x in m.groups()) for m in CTRL_RE.finditer(line)]
            if len(pts) != cols:
                raise self.err(f"patch row has {len(pts)} points, expected {cols}")
            ctrl.append(pts)
        self.expect(")")
        self.expect("}")
        self.expect("}")
        return Patch(shader, ctrl, contents, flags, value, ext)  # type: ignore[arg-type]

    def terrain(self) -> Terrain:
        self.expect("{")
        w, h, fl = (int(x) for x in (self.next() or "").split())
        origin = tuple(float(x) for x in (self.next() or "").split())
        self.expect("{")
        controls = []
        while True:
            s = self.next()
            if s == "}":
                break
            m = re.match(r"^(-?\d+)\s+(-?\d+)\s+\(\s*(\S+)\s+(.*?)\s*\)$", s or "")
            if not m:
                raise self.err(f"bad terrain control {s!r}")
            controls.append(TerrainControl(int(m.group(1)), int(m.group(2)), m.group(3), m.group(4).split()))
        self.expect("{")
        samples = []
        while True:
            s = self.next()
            if s == "}":
                break
            m = re.match(r"^(\S+)\s*\(([^)]*)\)\s*\(([^)]*)\)$", s or "")
            if not m:
                raise self.err(f"bad terrain sample {s!r}")
            samples.append(TerrainSample(float(m.group(1)), m.group(2).split(), m.group(3).split()))
        self.expect("}")
        self.expect("}")
        if len(samples) != w * h:
            raise self.err(f"terrain has {len(samples)} samples, expected {w}x{h}")
        return Terrain(w, h, fl, origin, controls, samples)  # type: ignore[arg-type]
