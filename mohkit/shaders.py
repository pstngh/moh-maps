"""Parse MOHAA (Quake 3 derived) shader scripts: ``scripts/*.shader``.

Format::

    textures/common/caulk          // shader name at depth 0
    {
        qer_editorimage textures/common/caulk.tga
        surfaceparm nodraw         // shader keywords: one per line, args end at newline
        {                          // stage
            map textures/foo.tga
            blendFunc GL_ONE GL_ZERO
            nextbundle             // MOH: second texture bundle of the same stage
            map $lightmap
        }
    }

Facts established from OpenMoHAA (renderergl1/tr_shader.c) and the retail tools:

* The engine loads every ``scripts/*.shader`` returned by ``FS_ListFiles``;
  ``scripts/shaderlist.txt`` is not used (MOHAA Q3map also scans ``scripts/*.shader``).
* Precedence for a name defined more than once: the text is concatenated in reverse
  listing order and every definition is pushed onto the front of its hash chain, so
  the definition in the *first listed* file wins, and inside one file the *last*
  definition wins. The listing starts with the highest-priority pk3 (``pak7`` before
  ``Pak0``) in zip-directory order; :meth:`ShaderIndex.from_fs` reproduces this.
* ``//`` starts a comment only at the start of a token (``COM_ParseExt``); ``/* */``
  block comments occur in stock scripts. Stock scripts use CRLF, tabs or spaces.
* Surfaceparm names known to MOHAA Q3map (string table of the shipped ``Q3map.exe``)
  and the OpenMoHAA renderer (``infoParms``) are :data:`KNOWN_SURFACEPARMS`. The
  footstep/impact material is ``rock``, not ``stone``: ``surfaceparm stone`` (552 AA
  shaders, including ``common/stoneclip``) and ``plaster`` are in neither table, so
  they set no flag. The Spearhead/Breakthrough copies of the same scripts use ``rock``.
* Engine-unknown keywords that nevertheless occur in stock scripts (``fullbright``,
  ``nodraw`` as a keyword, ``clampmapy``, stage-level ``surfaceparm``, the typo
  ``alpahfunc``) are recorded in :attr:`ShaderDef.unknown`.
* Like Quake 3's q3map, MOHAA Q3map sizes texture coordinates by the editor image
  (``qer_editorimage``, then the implicit ``textures/<name>`` image; its string table
  holds ``qer_editorimage``, ``.tga`` and ``%s.jpg``/``%s.tga``), which is why
  :meth:`ShaderIndex.resolve_image` prefers the editor image.

The parser tolerates missing braces: a line holding one unknown path-like token
followed by ``{`` inside a shader body or stage closes the open blocks (the engine
itself would instead swallow the following shader). Such cases are recorded in
:attr:`ShaderIndex.problems`.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

from .pak import GameFS, path_key, split_image_ext

KNOWN_SURFACEPARMS = frozenset("""
water slime lava playerclip monsterclip fence weaponclip vehicleclip shootonly nodrop nonsolid
obscuring origin trans detail structural areaportal fog sky alphashadow slick noimpact nomarks
ladder nodamage nosteps paper wood metal rock dirt grill grass mud puddle glass gravel sand
foliage snow carpet nodraw castshadow nolightmap nodlight hint overbright
""".split())

MATERIAL_PARMS = ("wood", "metal", "rock", "stone", "dirt", "grill", "grass", "mud", "puddle", "glass",
                  "gravel", "sand", "foliage", "snow", "carpet", "paper")

SHADER_KEYWORDS = frozenset("""
surfaceparm qer_editorimage qer_keyword qer_trans qer_nocarve qer_path skyparms cull sort
deformvertexes tesssize clamptime surfacelight surfacecolor surfaceangle surfacedensity subdivisions
nomipmaps nopicmip force32bit polygonoffset entitymergable nomerge portal portalsky light spritegen
spritescale #if #if_not #else #endif
""".split())

STAGE_KEYWORDS = frozenset("""
map clampmap animmap animmaponce animmapphase normalmap nomipmaps nopicmip nofog alphafunc depthfunc
blendfunc rgbgen alphagen texgen tcgen tcmod depthwrite depthmask nodepthwrite nodepthmask
nocolorwrite nocolormask nodepthtest nextbundle ifcvar ifcvarnot
""".split())

_IMAGE_STAGE_KW = ("map", "clampmap", "clampmapx", "clampmapy", "animmap", "animmaponce", "animmapphase",
                   "normalmap")
_OPAQUE_BLENDS = {"gl_one gl_zero"}
_NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)$")
_TOKEN_RE = re.compile(r'\n|[ \t\r\f\v]+|//[^\n]*|/\*.*?\*/|/\*.*\Z|"[^"\n]*"?|[{}]|[^\s{}"]+', re.S)


@dataclass
class Stage:
    images: list[str] = field(default_factory=list)       # bundle 0 images in order
    bundle_images: list[str] = field(default_factory=list)  # images after ``nextbundle``
    blend: Optional[str] = None                           # lowercased ``blendFunc`` args
    alpha_func: Optional[str] = None
    uses_lightmap: bool = False
    env: bool = False                                     # ``tcGen environment`` (reflection layer)


@dataclass
class ShaderDef:
    name: str
    source: str = ""                # script path, e.g. scripts/common.shader
    pak: Optional[str] = None       # pk3 basename (None for loose scripts)
    mod: str = ""
    line: int = 0
    comment: str = ""               # comment lines directly above the definition
    surfaceparms: list[str] = field(default_factory=list)
    editor_image: Optional[str] = None
    stages: list[Stage] = field(default_factory=list)
    skyparms: Optional[list[str]] = None
    cull: Optional[str] = None
    sort: Optional[str] = None
    qer_keywords: list[str] = field(default_factory=list)
    q3map: dict[str, list[str]] = field(default_factory=dict)
    keywords: Counter = field(default_factory=Counter)  # every keyword seen, lowercased
    unknown: list[str] = field(default_factory=list)   # keywords the engine does not parse
    warnings: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.name.lower()

    @property
    def stage_image(self) -> Optional[str]:
        """First image of the first non-environment-mapped stage (``$lightmap`` etc. skipped)."""
        for st in self.stages:
            if st.images and not st.env:
                return st.images[0]
        return None

    @property
    def images(self) -> list[str]:
        return [im for st in self.stages for im in st.images + st.bundle_images]

    @property
    def blend_funcs(self) -> list[str]:
        return [st.blend for st in self.stages if st.blend]

    @property
    def alpha_funcs(self) -> list[str]:
        return [st.alpha_func for st in self.stages if st.alpha_func]

    @property
    def alpha_tested(self) -> bool:
        return any(st.alpha_func for st in self.stages)

    @property
    def blended(self) -> bool:
        return bool(self.stages) and self.stages[0].blend is not None and self.stages[0].blend not in _OPAQUE_BLENDS

    @property
    def transparent(self) -> bool:
        """Alpha-tested anywhere, or the first stage blends with what is behind it."""
        return self.alpha_tested or self.blended

    @property
    def is_sky(self) -> bool:
        return "sky" in self.surfaceparms or self.skyparms is not None

    @property
    def material(self) -> Optional[str]:
        for p in self.surfaceparms:
            if p in MATERIAL_PARMS:
                return p
        return None

    def has_parm(self, parm: str) -> bool:
        return parm.lower() in self.surfaceparms

    @property
    def unknown_parms(self) -> list[str]:
        return [p for p in self.surfaceparms if p not in KNOWN_SURFACEPARMS]


# ---------------------------------------------------------------------------
# Tokenizer and parser


@dataclass
class _Tok:
    kind: str   # word | { | } | comment
    text: str
    line: int


def _tokenize(text: str) -> list[_Tok]:
    out: list[_Tok] = []
    line = 1
    for m in _TOKEN_RE.finditer(text):
        s = m.group(0)
        c = s[0]
        if c == "\n":
            line += 1
            continue
        if c in " \t\r\f\v":
            continue
        if s.startswith("//"):
            out.append(_Tok("comment", s[2:].strip(), line))
        elif s.startswith("/*"):
            out.append(_Tok("comment", s[2:-2].strip() if s.endswith("*/") else s[2:].strip(), line))
            line += s.count("\n")
        elif c == "{" or c == "}":
            out.append(_Tok(c, c, line))
        elif c == '"':
            out.append(_Tok("word", s.strip('"'), line))
        else:
            out.append(_Tok("word", s, line))
    return out


def _is_image(tok: str) -> bool:
    return bool(tok) and tok[0] not in "$*" and not _NUM_RE.match(tok)


class _ShaderParser:
    def __init__(self, text: str, source: str, pak: Optional[str], mod: str):
        self.toks = _tokenize(text)
        self.n = len(self.toks)
        self.source, self.pak, self.mod = source, pak, mod
        self.defs: list[ShaderDef] = []
        self.problems: list[str] = []

    def problem(self, line: int, msg: str, sd: Optional[ShaderDef] = None) -> None:
        self.problems.append(f"{self.source}:{line}: {msg}")
        if sd is not None:
            sd.warnings.append(msg)

    def _next_sig(self, i: int) -> int:
        while i < self.n and self.toks[i].kind == "comment":
            i += 1
        return i

    def _line_args(self, i: int, line: int) -> tuple[list[str], int]:
        args = []
        while i < self.n and self.toks[i].line == line and self.toks[i].kind in ("word", "comment"):
            if self.toks[i].kind == "word":
                args.append(self.toks[i].text)
            i += 1
        return args, i

    def _new_shader_ahead(self, tok: _Tok, args: list[str], i: int) -> bool:
        if args or "/" not in tok.text:
            return False
        kw = tok.text.lower()
        if kw in SHADER_KEYWORDS or kw in STAGE_KEYWORDS or kw.startswith(("qer", "q3map")):
            return False
        j = self._next_sig(i)
        return j < self.n and self.toks[j].kind == "{"

    def parse(self) -> list[ShaderDef]:
        i, comments, last_line = 0, [], 0
        while i < self.n:
            t = self.toks[i]
            if t.kind == "comment":
                if comments and t.line > last_line + 1:
                    comments = []
                comments.append(t.text)
                last_line = t.line
                i += 1
                continue
            if t.kind == "}":
                self.problem(t.line, "stray '}'")
                i += 1
                continue
            if t.kind == "{":
                self.problem(t.line, "'{' without a shader name; block skipped")
                i = self._skip_block(i)
                continue
            j = self._next_sig(i + 1)
            if j >= self.n or self.toks[j].kind != "{":
                self.problem(t.line, f"token {t.text!r} outside a shader")
                i += 1
                continue
            keep = comments if comments and last_line >= t.line - 1 else []
            sd = ShaderDef(t.text, self.source, self.pak, self.mod, t.line, "\n".join(keep))
            comments = []
            self.defs.append(sd)
            i = self._body(j + 1, sd)
        return self.defs

    def _skip_block(self, i: int) -> int:
        depth = 0
        while i < self.n:
            k = self.toks[i].kind
            depth += (k == "{") - (k == "}")
            i += 1
            if depth <= 0:
                break
        return i

    def _body(self, i: int, sd: ShaderDef) -> int:
        while i < self.n:
            t = self.toks[i]
            if t.kind == "comment":
                i += 1
                continue
            if t.kind == "}":
                return i + 1
            if t.kind == "{":
                i, end_shader = self._stage(i + 1, sd)
                if end_shader:
                    return i
                continue
            args, j = self._line_args(i + 1, t.line)
            if self._new_shader_ahead(t, args, j):
                self.problem(t.line, f"missing '}}' before {t.text!r}", sd)
                return i
            self._shader_kw(sd, t.text.lower(), args)
            i = j
        self.problem(sd.line, "unterminated shader at end of file", sd)
        return i

    def _stage(self, i: int, sd: ShaderDef) -> tuple[int, bool]:
        st, bundle = Stage(), 0
        sd.stages.append(st)
        while i < self.n:
            t = self.toks[i]
            if t.kind == "comment":
                i += 1
                continue
            if t.kind == "}":
                return i + 1, False
            if t.kind == "{":
                self.problem(t.line, "'{' inside a stage (missing '}')", sd)
                return i, False
            args, j = self._line_args(i + 1, t.line)
            if self._new_shader_ahead(t, args, j):
                self.problem(t.line, f"missing '}}}}' before {t.text!r}", sd)
                return i, True
            kw = t.text.lower()
            sd.keywords[kw] += 1
            if kw not in STAGE_KEYWORDS:
                sd.unknown.append(kw)
            if kw == "nextbundle":
                bundle += 1
            elif kw in _IMAGE_STAGE_KW or kw.startswith(("clampmap", "animmap")):
                for a in args:
                    if a.lower() == "$lightmap":
                        st.uses_lightmap = True
                ims = [a for a in args if _is_image(a)]
                (st.images if bundle == 0 else st.bundle_images).extend(ims)
            elif kw == "blendfunc" and bundle == 0:
                st.blend = " ".join(a.lower() for a in args) or None
            elif kw == "alphafunc":
                st.alpha_func = args[0] if args else ""
            elif kw in ("tcgen", "texgen") and args and args[0].lower().startswith("environment"):
                st.env = True
            i = j
        self.problem(sd.line, "unterminated stage at end of file", sd)
        return i, True

    def _shader_kw(self, sd: ShaderDef, kw: str, args: list[str]) -> None:
        sd.keywords[kw] += 1
        if kw.startswith("q3map"):
            sd.q3map[kw] = args
        elif kw.startswith("qer"):
            if kw == "qer_editorimage" and args:
                sd.editor_image = args[0]
            elif kw == "qer_keyword" and args:
                sd.qer_keywords.append(args[0].lower())
            elif kw not in SHADER_KEYWORDS:
                sd.unknown.append(kw)
        elif kw == "surfaceparm":
            if args:
                sd.surfaceparms.append(args[0].lower())
        elif kw == "skyparms":
            sd.skyparms = args
        elif kw == "cull":
            sd.cull = args[0].lower() if args else ""
        elif kw == "sort":
            sd.sort = args[0].lower() if args else ""
        elif kw not in SHADER_KEYWORDS:
            sd.unknown.append(kw)


def parse_shader_text(text: str, source: str = "<shader>", pak: Optional[str] = None,
                      mod: str = "") -> tuple[list[ShaderDef], list[str]]:
    """Parse one script. Returns definitions in file order and a list of problems."""
    p = _ShaderParser(text, source, pak, mod)
    return p.parse(), p.problems


# ---------------------------------------------------------------------------
# Index


def lookup_keys(name: str) -> list[str]:
    """Lowercase shader names to try for a map/model shader reference, in order."""
    n = path_key(name)
    stem, ext = split_image_ext(n)
    out: list[str] = []
    for c in ([n, stem] if ext else [n]):
        if not c.startswith("textures/"):
            out.append("textures/" + c)
        out.append(c)
    return list(dict.fromkeys(out))


class ShaderIndex:
    def __init__(self, fs: Optional[GameFS] = None):
        self.fs = fs
        self.defs: dict[str, ShaderDef] = {}           # lower name -> winning definition
        self.all_defs: dict[str, list[ShaderDef]] = {}  # lower name -> every definition, winner first
        self.files: list[str] = []                      # scripts in precedence order
        self.problems: list[str] = []

    @classmethod
    def from_fs(cls, fs: GameFS) -> "ShaderIndex":
        idx = cls(fs)
        for path in fs.engine_list("scripts", ".shader"):
            e = fs.entry(path)
            defs, probs = parse_shader_text(fs.read_text(path), e.path if e else path,
                                            e.pak if e else None, e.mod if e else "")
            idx.add(defs, probs, path)
        return idx

    @classmethod
    def from_texts(cls, texts: Iterable[tuple[str, str]], fs: Optional[GameFS] = None) -> "ShaderIndex":
        """Build from ``(source, text)`` pairs given in precedence order."""
        idx = cls(fs)
        for source, text in texts:
            defs, probs = parse_shader_text(text, source)
            idx.add(defs, probs, source)
        return idx

    def add(self, defs: list[ShaderDef], problems: Iterable[str] = (), source: str = "") -> None:
        """Add one script's definitions; scripts must be added highest precedence first."""
        if source:
            self.files.append(source)
        self.problems.extend(problems)
        for sd in reversed(defs):
            self.all_defs.setdefault(sd.key, []).append(sd)
            self.defs.setdefault(sd.key, sd)

    def __len__(self) -> int:
        return len(self.defs)

    def __iter__(self) -> Iterator[ShaderDef]:
        return iter(self.defs.values())

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def get(self, name: str) -> Optional[ShaderDef]:
        for k in lookup_keys(name):
            sd = self.defs.get(k)
            if sd is not None:
                return sd
        return None

    def duplicates(self) -> dict[str, list[ShaderDef]]:
        return {k: v for k, v in self.all_defs.items() if len(v) > 1}

    def image_candidates(self, name: str) -> list[str]:
        """Editor image, implicit image (shader name), first non-environment stage image, then
        any other stage image. The implicit image precedes stage images because Q3map sizes
        texture coordinates from it, and stock windows/snow shaders start with an environment
        or sparkle layer (``mohcommon/environ_puddle``, ``snowfx3``)."""
        sd = self.get(name)
        cands: list[str] = []
        if sd is not None:
            if sd.editor_image:
                cands.append(sd.editor_image)
            cands.append(sd.name)
            if sd.stage_image:
                cands.append(sd.stage_image)
            cands += sd.images
        cands.append(name)
        return list(dict.fromkeys(cands))

    def resolve_image(self, name: str) -> Optional[str]:
        """Image the editor/compiler sizes the shader by, see :meth:`image_candidates`."""
        if self.fs is None:
            raise ValueError("ShaderIndex has no GameFS")
        for c in self.image_candidates(name):
            p = self.fs.find_image(c)
            if p is not None:
                return p
        return None

    def exists(self, name: str) -> bool:
        """True if a shader script defines ``name`` or an implicit image exists for it."""
        if self.get(name) is not None:
            return True
        return self.fs is not None and self.fs.find_image(name) is not None

    def surfaceparms(self, name: str) -> list[str]:
        sd = self.get(name)
        return list(sd.surfaceparms) if sd else []

    def material(self, name: str) -> Optional[str]:
        sd = self.get(name)
        return sd.material if sd else None
