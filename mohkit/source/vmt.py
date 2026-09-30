"""Valve KeyValues / VMT (material) parsing and material resolution.

KeyValues text format
---------------------
::

    // comment to end of line
    "ShaderName"                 <- key; quotes optional
    {                            <- a key followed by '{' opens a block
        "$basetexture" "brick/brickwall001a"
        $surfaceprop   brick     <- unquoted tokens end at whitespace, quote or brace
        "$envmap" "env_cubemap" [$X360]      <- conditional: pair kept only if true
        "Proxies" { ... }        <- nested block
        "GPU>=2?$detail" "..."   <- CS:GO conditional *key prefix* (kept verbatim)
        ">=dx90" { ... }         <- shader fallback block (kept as a nested dict)
    }

Tokens: ``{`` ``}``, ``"quoted"`` (no escape sequences - material paths use
backslashes), ``[conditional]``, and bare words. Keys are case-insensitive.
Duplicate keys: the last scalar wins; duplicate blocks are merged (this matches
how the material system applies parameters in order).

Conditionals ``[expr]`` use ``$SYMBOL``, ``!``, ``&&`` and ``||`` (``||`` binds
weakest). Symbols in ``defines`` are true (default: ``WIN32``, ``WINDOWS``).

Patch materials
---------------
vbsp writes *patch* materials into a map's pakfile (cubemap-specific
``$envmap``, water depth, WorldVertexTransition fixes)::

    "patch" {
        "include" "materials/concrete/concretefloor001a.vmt"
        "insert"  { "$envmap" "maps/de_x/c-120_45_64" }   <- added (or overwritten)
        "replace" { "$envmaptint" "[.5 .5 .5]" }          <- only if the key exists
    }

:func:`material_info` follows ``include`` chains (up to 8 deep) and applies the
patches, then resolves CS:GO conditional key prefixes (``GPU>=N?``, ``GPU<N?``,
``srgb?``, ``>=dx90?`` ...) and fallback blocks for a high-end PC
(``gpu_level=3``, ``srgb=False``).

Tool materials. vbsp reads ``%compile*`` keys from ``materials/tools/*.vmt``
and turns them into contents/surface flags. Keys actually present in the CS:GO
pak01 install (scan with :func:`tool_material_flags`)::

    %compilenodraw      toolsnodraw, toolsinvisible, toolsinvisibleladder, toolsplayerclip,
                        toolsblock_los, toolsblockbullets, toolsblockbomb, toolsblocklight, climb
    %compileclip        toolsclip, toolsclip_<surface> (concrete, dirt, glass, grass, gravel,
                        metal, metalgrate, plastic, rubber, sand, tile, wood)
    %playerclip         toolsplayerclip  (note: not "%compileplayerclip")
    %compilenpcclip     toolsnpcclip
    %compilegrenadeclip toolsgrenadeclip (brushes get CONTENTS_CURRENT_90)
    %compilesky         toolsskybox       %compile2dsky   toolsskybox2d
    %compilehint        toolshint         %compileskip    toolsskip
    %compiletrigger     toolstrigger      %compileorigin  toolsorigin
    %compilefog         toolsfog          %compileblocklos toolsblock_los
    %compileladder      toolsinvisibleladder, climb*      %compileteam  climb* (value 2)
    %compilepassbullets toolsinvisible, toolsinvisibleladder, toolsplayerclip, climb*
    %compilenonsolid    toolsblocklight   %compiledetail  toolsblocklight, toolsblock_los
    %compilenolight     toolsareaportal, toolsoccluder

``toolsareaportal``/``toolsoccluder`` carry no contents key: areaportals and
occluders come from their entities (``func_areaportal``, ``func_occluder``).
Older Source games also used ``%compileareaportal``, ``%compilewater``,
``%compileslime``, ``%compileinvisible``, ``%compilenochop``; they are parsed the
same way. :attr:`MaterialInfo.tool_flags` holds the key names without the
``%compile`` prefix (``{"nodraw", "clip"}``; ``%playerclip`` -> ``"playerclip"``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Union

from .vpk import normalize_path

KVValue = Union[str, "KVList"]
KVList = list  # list[tuple[str, KVValue]]

DEFAULT_DEFINES = frozenset({"WIN32", "WINDOWS"})


# ---------------------------------------------------------------------------
# Tokenizer

_T_STR, _T_OPEN, _T_CLOSE, _T_COND = range(4)


def _tokenize(text: str) -> list[tuple[int, str, bool]]:
    """(kind, text, was_quoted) tuples."""
    out: list[tuple[int, str, bool]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n\f\v﻿":
            i += 1
            continue
        if c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "{":
            out.append((_T_OPEN, "{", False))
            i += 1
        elif c == "}":
            out.append((_T_CLOSE, "}", False))
            i += 1
        elif c == '"':
            j = text.find('"', i + 1)
            if j < 0:
                j = n
            out.append((_T_STR, text[i + 1 : j], True))
            i = j + 1
        elif c == "[":
            j = text.find("]", i + 1)
            if j < 0:
                j = n
            out.append((_T_COND, text[i + 1 : j].strip(), False))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n\f\v"{}':
                j += 1
            out.append((_T_STR, text[i:j], False))
            i = j
    return out


def eval_conditional(expr: str, defines: Iterable[str] = DEFAULT_DEFINES) -> bool:
    """Evaluate ``$X360 || !$WIN32 && $OSX`` style expressions."""
    d = {s.upper().lstrip("$") for s in defines}
    for alt in expr.split("||"):
        ok = True
        for term in alt.split("&&"):
            t = term.strip()
            neg = False
            while t.startswith("!"):
                neg = not neg
                t = t[1:].strip()
            val = t.lstrip("$").upper() in d
            if val == neg:
                ok = False
                break
        if ok:
            return True
    return False


class KVParseError(ValueError):
    pass


def parse_kv_pairs(text: Union[str, bytes], defines: Iterable[str] = DEFAULT_DEFINES) -> KVList:
    """Parse KeyValues text to an ordered list of ``(key, value)`` pairs.

    ``value`` is a string or a nested pair list. Original key case is kept and
    duplicates are preserved. Pairs whose ``[conditional]`` is false are dropped.
    Unbalanced input is tolerated (missing ``}`` at EOF, stray ``}``).
    """
    if isinstance(text, (bytes, bytearray)):
        text = _decode(text)
    toks = _tokenize(text)
    defs = frozenset(defines)
    pos = 0

    def cond_ok() -> bool:
        nonlocal pos
        if pos < len(toks) and toks[pos][0] == _T_COND:
            ok = eval_conditional(toks[pos][1], defs)
            pos += 1
            return ok
        return True

    def block(depth: int) -> KVList:
        nonlocal pos
        pairs: KVList = []
        while pos < len(toks):
            kind, tok, _ = toks[pos]
            if kind == _T_CLOSE:
                pos += 1
                if depth > 0:
                    return pairs
                continue  # stray '}' at top level
            if kind == _T_COND:  # conditional without a pair; ignore
                pos += 1
                continue
            if kind == _T_OPEN:  # anonymous block: parse and attach under ""
                pos += 1
                sub = block(depth + 1)
                if cond_ok():
                    pairs.append(("", sub))
                continue
            key = tok
            pos += 1
            # A conditional may sit between key and '{' as well.
            pre_ok = True
            if pos < len(toks) and toks[pos][0] == _T_COND and pos + 1 < len(toks) and toks[pos + 1][0] == _T_OPEN:
                pre_ok = eval_conditional(toks[pos][1], defs)
                pos += 1
            if pos >= len(toks):
                pairs.append((key, ""))
                break
            kind, tok, _ = toks[pos]
            if kind == _T_OPEN:
                pos += 1
                sub = block(depth + 1)
                if cond_ok() and pre_ok:
                    pairs.append((key, sub))
            elif kind == _T_STR:
                pos += 1
                if cond_ok():
                    pairs.append((key, tok))
            elif kind == _T_CLOSE:
                pairs.append((key, ""))  # key without value right before '}'
            else:
                pos += 1
        return pairs

    return block(0)


def pairs_to_dict(pairs: KVList, lower: bool = True) -> dict[str, Any]:
    """Collapse a pair list to nested dicts (last scalar wins, blocks merge)."""
    out: dict[str, Any] = {}
    for k, v in pairs:
        key = k.lower() if lower else k
        if isinstance(v, list):
            sub = pairs_to_dict(v, lower)
            prev = out.get(key)
            if isinstance(prev, dict):
                prev.update(sub)
            else:
                out[key] = sub
        else:
            out[key] = v
    return out


def parse_keyvalues(text: Union[str, bytes], defines: Iterable[str] = DEFAULT_DEFINES) -> dict[str, Any]:
    """Parse KeyValues text to nested dicts with lower-cased keys."""
    return pairs_to_dict(parse_kv_pairs(text, defines))


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# ---------------------------------------------------------------------------
# VMT documents


@dataclass
class VMT:
    """A parsed material file: ``shader { params }``."""
    shader: str                   # as written (e.g. "LightmappedGeneric", "patch")
    params: dict[str, Any]        # lower-cased keys, nested dicts for blocks
    pairs: KVList = field(default_factory=list)  # raw ordered pairs of the body

    @property
    def is_patch(self) -> bool:
        return self.shader.lower() == "patch"


def parse_vmt(text: Union[str, bytes], defines: Iterable[str] = DEFAULT_DEFINES) -> VMT:
    pairs = parse_kv_pairs(text, defines)
    for k, v in pairs:
        if isinstance(v, list) and not k.startswith("#"):
            return VMT(k, pairs_to_dict(v), v)
    # Malformed: shader name followed by loose params instead of a block.
    if pairs:
        rest = pairs[1:]
        return VMT(pairs[0][0], pairs_to_dict(rest), rest)
    raise KVParseError("empty material")


# ---------------------------------------------------------------------------
# Condition resolution for CS:GO key prefixes and fallback blocks

_GPU_RE = re.compile(r"^gpu\s*(>=|<=|>|<|==|=)\s*(\d+)$")
_FALLBACK_RE = re.compile(r"^(\w+?)_(hdr_)?dx(\d+)(?:_\w+)?$")
_CONSOLE_CONDITIONS = frozenset({"360", "x360", "gameconsole", "ps3", "sonyps3", "console"})
_DX_RE = re.compile(r"^(>=|<=|>|<)?\s*dx(\d+)(?:_\w+)?$")


def _eval_material_condition(cond: str, gpu_level: int, srgb: bool, dx_level: int = 90) -> Optional[bool]:
    """True/False for a known condition, ``None`` if unknown."""
    c = cond.strip().lower()
    neg = c.startswith("!")
    if neg:
        c = c[1:].strip()
    res: Optional[bool]
    m = _GPU_RE.match(c)
    if m:
        op, n = m.group(1), int(m.group(2))
        res = {">=": gpu_level >= n, "<=": gpu_level <= n, ">": gpu_level > n, "<": gpu_level < n,
               "==": gpu_level == n, "=": gpu_level == n}[op]
    elif c == "srgb":
        res = srgb
    elif c in _CONSOLE_CONDITIONS or c in ("lowfill", "lowquality", "lowqualitycsm"):
        res = False
    else:
        m = _DX_RE.match(c)
        if m:
            op, n = m.group(1) or "==", int(m.group(2))
            if n < 20:
                n *= 10  # "dx9" == "dx90"
            res = {">=": dx_level >= n, "<=": dx_level <= n, ">": dx_level > n, "<": dx_level < n,
                   "==": dx_level == n}[op]
        else:
            res = None
    return (not res) if (res is not None and neg) else res


def resolve_conditions(params: dict[str, Any], shader: str = "", gpu_level: int = 3, srgb: bool = False) -> dict[str, Any]:
    """Flatten ``cond?$key`` prefixes and matching fallback blocks.

    Order: plain keys, then true fallback blocks (``>=dx90``, ``GPU>=1``,
    ``<shader>_dx9``, ``<shader>_hdr_dx9``), then true ``cond?`` keys.
    Unknown conditions are dropped; other nested blocks (``proxies``) are kept.
    """
    out: dict[str, Any] = {}
    blocks: list[dict[str, Any]] = []
    prefixed: list[tuple[str, Any]] = []
    sh = shader.lower()
    for k, v in params.items():
        if "?" in k:
            cond, _, key = k.rpartition("?")
            if all(_eval_material_condition(c, gpu_level, srgb) for c in cond.split("?")):
                prefixed.append((key, v))
            continue
        if isinstance(v, dict) and not k.startswith("$") and not k.startswith("%"):
            ok = _eval_material_condition(k, gpu_level, srgb)
            fb = _FALLBACK_RE.match(k) if ok is None else None
            if fb:  # "<shader>_dx9" / "<shader>_hdr_dx9": applies to this shader at DX9+
                n = int(fb.group(3))
                ok = fb.group(1) == sh and (n * 10 if n < 20 else n) >= 90
            if ok is not None:
                if ok:
                    blocks.append(v)
                continue
        out[k] = v
    for b in blocks:
        out.update(resolve_conditions(b, shader, gpu_level, srgb))
    for k, v in prefixed:
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# Material resolution

TEXTURE_PARAMS = (
    "$basetexture", "$basetexture2", "$basetexture3", "$basetexture4", "$bumpmap", "$bumpmap2",
    "$normalmap", "$detail", "$envmapmask", "$blendmodulatetexture", "$selfillummask",
    "$phongexponenttexture", "$texture2", "$dudvmap", "$refracttexture", "$bottommaterial",
)


def normalize_material_name(name: str) -> str:
    """``Materials\\Brick\\Wall.vmt`` -> ``brick/wall``."""
    n = normalize_path(name)
    if n.startswith("materials/"):
        n = n[len("materials/"):]
    if n.endswith(".vmt"):
        n = n[:-4]
    return n


def normalize_texture_name(name: str) -> str:
    """``Tools\\toolsclip.vtf`` -> ``tools/toolsclip``."""
    n = normalize_path(name)
    if n.startswith("materials/"):
        n = n[len("materials/"):]
    if n.endswith(".vtf"):
        n = n[:-4]
    return n


def texture_path(name: str) -> str:
    """VPK path of a texture referenced by a material parameter."""
    return f"materials/{normalize_texture_name(name)}.vtf"


def _truthy(v: Any) -> bool:
    if isinstance(v, dict):
        return True
    s = str(v).strip().strip('"').lower()
    if not s:
        return False
    try:
        return float(s) != 0.0
    except ValueError:
        return s not in ("false", "no", "off")


@dataclass
class MaterialInfo:
    name: str                          # normalized request name (no materials/, no .vmt)
    found: bool = False
    path: Optional[str] = None         # VMT path that was read first
    shader: str = ""                   # lower-case shader of the final (non-patch) material
    params: dict[str, Any] = field(default_factory=dict)  # resolved, lower-case keys
    includes: list[str] = field(default_factory=list)     # patch include chain
    basetexture: Optional[str] = None
    basetexture2: Optional[str] = None
    textures: dict[str, str] = field(default_factory=dict)  # every texture-valued param found
    surfaceprop: Optional[str] = None
    surfaceprop2: Optional[str] = None
    translucent: bool = False
    alphatest: bool = False
    additive: bool = False
    nocull: bool = False
    compile_keys: dict[str, str] = field(default_factory=dict)  # all %keys (lower-case)
    tool_flags: frozenset[str] = frozenset()  # e.g. {"nodraw", "clip"} from %compile<flag>

    @property
    def is_tool(self) -> bool:
        return self.name.startswith("tools/")

    @property
    def nodraw(self) -> bool:
        return bool(self.tool_flags & {"nodraw", "clip", "playerclip", "npcclip", "grenadeclip", "droneclip",
                                       "trigger", "hint", "skip", "areaportal", "origin", "fog", "invisible",
                                       "blocklos"})

    @property
    def is_sky(self) -> bool:
        return bool(self.tool_flags & {"sky", "2dsky"})

    @property
    def is_water(self) -> bool:
        return self.shader == "water" or "water" in self.tool_flags


def material_info(source, name: str, gpu_level: int = 3, srgb: bool = False,
                  defines: Iterable[str] = DEFAULT_DEFINES) -> MaterialInfo:
    """Resolve a material by name from ``source`` (VPK / SearchPath / anything with ``try_read``).

    ``name`` may be ``"brick/wall"``, ``"materials/brick/wall.vmt"`` or the upper-case
    texdata name from a BSP. Missing materials return ``found=False``.
    """
    info = MaterialInfo(normalize_material_name(name))
    path = f"materials/{info.name}.vmt"
    data = source.try_read(path)
    if data is None:
        return info
    info.found = True
    info.path = path
    vmt = parse_vmt(data, defines)

    # Follow patch includes, collecting patches outermost-first.
    patches: list[dict[str, Any]] = []
    depth = 0
    while vmt.is_patch and depth < 8:
        patches.append(vmt.params)
        inc = vmt.params.get("include")
        if not isinstance(inc, str):
            break
        inc_path = normalize_path(inc)
        if not inc_path.startswith("materials/"):
            inc_path = "materials/" + inc_path
        if not inc_path.endswith(".vmt"):
            inc_path += ".vmt"
        info.includes.append(inc_path)
        data = source.try_read(inc_path)
        if data is None:
            vmt = VMT("patch", {})
            break
        vmt = parse_vmt(data, defines)
        depth += 1

    params = dict(vmt.params)
    for patch in reversed(patches):  # innermost patch applies first
        ins = patch.get("insert")
        if isinstance(ins, dict):
            params.update(ins)
        rep = patch.get("replace")
        if isinstance(rep, dict):
            for k, v in rep.items():
                if k in params:
                    params[k] = v
    info.shader = "" if vmt.is_patch else vmt.shader.lower()
    params = resolve_conditions(params, info.shader, gpu_level, srgb)
    info.params = params

    for k in TEXTURE_PARAMS:
        v = params.get(k)
        if isinstance(v, str) and v.strip() and k != "$bottommaterial":
            info.textures[k] = normalize_texture_name(v)
    info.basetexture = info.textures.get("$basetexture")
    info.basetexture2 = info.textures.get("$basetexture2")
    sp = params.get("$surfaceprop")
    info.surfaceprop = sp if isinstance(sp, str) else None
    sp2 = params.get("$surfaceprop2")
    info.surfaceprop2 = sp2 if isinstance(sp2, str) else None
    info.translucent = _truthy(params.get("$translucent", "0"))
    info.alphatest = _truthy(params.get("$alphatest", "0"))
    info.additive = _truthy(params.get("$additive", "0"))
    info.nocull = _truthy(params.get("$nocull", "0"))
    info.compile_keys = {k: str(v) for k, v in params.items() if k.startswith("%") and isinstance(v, str)}
    flags = set()
    for k, v in info.compile_keys.items():
        if k.startswith("%compile") and _truthy(v):
            flags.add(k[len("%compile"):])
        elif k in ("%playerclip", "%noportal") and _truthy(v):
            flags.add(k[1:])
    info.tool_flags = frozenset(flags)
    return info


def tool_material_flags(source) -> dict[str, dict[str, str]]:
    """``{material: {%key: value}}`` for every ``materials/tools/*.vmt`` in a VPK."""
    out: dict[str, dict[str, str]] = {}
    paths = source.glob("materials/tools/*.vmt") if hasattr(source, "glob") else []
    for p in paths:
        mi = material_info(source, p)
        keys = {k: v for k, v in mi.compile_keys.items() if k != "%keywords"}
        out[mi.name] = keys
    return out
