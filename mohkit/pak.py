"""Virtual filesystem over a MOHAA game directory (pk3 archives plus loose files).

Search order, as implemented by OpenMoHAA ``FS_AddGameDirectory`` (qcommon/files.cpp):

* Each mod directory (``main``, then ``mainta``/``maintt``) contributes its ``*.pk3``
  files sorted with ``FS_PathCmp`` (ASCII case-insensitive, ``\\`` and ``:`` read as
  ``/``). Every pk3 is pushed onto the front of the search path, so a later pk3
  overrides an earlier one (``pak7.pk3`` > ``Pak6EnUk.pk3`` > ... > ``Pak0.pk3``).
* The mod directory itself is pushed last, so loose files override every pk3 of
  that mod and of the mods before it. Later mods override earlier mods.
* Lookups are case-insensitive. Stored entry names keep their original case.
* ``FS_ListFiles`` walks the search path from the highest priority down, visiting
  pk3 members in central-directory order and keeping the first spelling of each
  name; :meth:`GameFS.engine_list` reproduces that order because shader-script
  precedence depends on it (see :mod:`mohkit.shaders`).

Retail archives are the ones named ``pak*.pk3`` (any case); community/test archives
such as ``zzz_*.pk3`` or ``1v1-maps.pk3`` are ignored by default. Zip directory
entries (names ending in ``/``) are skipped.

Images: the renderer (``R_FindShader``/``R_LoadImage``, renderergl1) gives a
shader-less name the default extension ``.tga``, and for ``.tga``/``.jpg`` names
tries ``.jpg`` first when ``r_loadjpg`` is 1 (the default), then ``.tga``. Q3map
prefixes map shader names with ``textures/``.

Stock paths quirks handled by :func:`normalize`: backslashes, doubled slashes
(``static//tree_oak.tik`` in many stock maps), leading ``./`` or ``/``.
"""

from __future__ import annotations

import io
import os
import re
import struct
import zipfile
from dataclasses import dataclass
from typing import BinaryIO, Callable, Iterable, Iterator, Optional, Union

IMAGE_EXTS = (".tga", ".jpg", ".jpeg", ".png", ".dds", ".bmp", ".pcx")
_RETAIL_RE = re.compile(r"^pak.*\.pk3$", re.IGNORECASE)
_SLASHES_RE = re.compile(r"/{2,}")

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def is_retail_pak(filename: str) -> bool:
    return bool(_RETAIL_RE.match(os.path.basename(filename)))


def normalize(path: str) -> str:
    """Canonical game path: forward slashes, no doubled or leading slashes."""
    p = _SLASHES_RE.sub("/", path.replace("\\", "/").strip())
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def path_key(path: str) -> str:
    return normalize(path).lower()


def _pathcmp_key(name: str) -> str:
    return name.lower().replace("\\", "/").replace(":", "/")


def split_image_ext(name: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(name)
    if ext.lower() in IMAGE_EXTS:
        return stem, ext.lower()
    return name, ""


@dataclass(frozen=True)
class Entry:
    """One file provider: a pk3 member or a loose file."""
    path: str                 # game path with original case
    mod: str
    container: str            # pk3 file, or the mod directory for loose files
    member: Optional[str]     # zip member name; None for loose files
    size: int
    priority: int             # search-path rank, higher wins
    index: int                # position inside the container (zip directory order)

    @property
    def loose(self) -> bool:
        return self.member is None

    @property
    def pak(self) -> Optional[str]:
        return None if self.member is None else os.path.basename(self.container)

    @property
    def origin(self) -> str:
        """``mod/Pak0.pk3`` or ``mod/`` (loose)."""
        return f"{self.mod}/{self.pak}" if self.pak else f"{self.mod}/"


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    format: str               # tga | jpg | png | dds
    bits: Optional[int] = None
    has_alpha: Optional[bool] = None


@dataclass(frozen=True)
class Container:
    path: str
    mod: str
    kind: str                 # "pk3" | "dir"
    priority: int


class GameFS:
    """Case-insensitive, override-aware view over one or more mod directories."""

    def __init__(self, game_dir: str, mods: Iterable[str] = ("main",), loose: bool = True,
                 pak_filter: Callable[[str], bool] = is_retail_pak):
        self.game_dir = os.path.abspath(game_dir)
        self.mods = tuple(mods)
        self.containers: list[Container] = []
        self._all: dict[str, list[Entry]] = {}
        self._zips: dict[str, zipfile.ZipFile] = {}
        prio = 0
        for mod in self.mods:
            mdir = os.path.join(self.game_dir, mod)
            if not os.path.isdir(mdir):
                raise FileNotFoundError(f"mod directory not found: {mdir}")
            pk3s = [f for f in os.listdir(mdir)
                    if f.lower().endswith(".pk3") and os.path.isfile(os.path.join(mdir, f)) and pak_filter(f)]
            for f in sorted(pk3s, key=_pathcmp_key):
                prio += 1
                self._index_pk3(Container(os.path.join(mdir, f), mod, "pk3", prio))
            if loose:
                prio += 1
                self._index_dir(Container(mdir, mod, "dir", prio))
        for lst in self._all.values():
            lst.sort(key=lambda e: -e.priority)

    # ------------------------------------------------------------ indexing
    def _add(self, e: Entry) -> None:
        self._all.setdefault(e.path.lower(), []).append(e)

    def _index_pk3(self, c: Container) -> None:
        self.containers.append(c)
        with zipfile.ZipFile(c.path) as zf:
            seen: set[str] = set()
            for i, info in enumerate(zf.infolist()):
                if info.is_dir():
                    continue
                p = normalize(info.filename)
                if not p or p.lower() in seen:
                    continue
                seen.add(p.lower())
                self._add(Entry(p, c.mod, c.path, info.filename, info.file_size, c.priority, i))

    def _index_dir(self, c: Container) -> None:
        self.containers.append(c)
        n = 0
        for root, dirs, files in os.walk(c.path):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            rel = os.path.relpath(root, c.path)
            for f in sorted(files):
                if f.startswith(".") or (rel == "." and f.lower().endswith(".pk3")):
                    continue
                p = f if rel == "." else normalize(os.path.join(rel, f))
                full = os.path.join(root, f)
                self._add(Entry(p, c.mod, c.path, None, os.path.getsize(full), c.priority, n))
                n += 1

    # ------------------------------------------------------------- queries
    def __len__(self) -> int:
        return len(self._all)

    def __contains__(self, path: str) -> bool:
        return self.exists(path)

    def __repr__(self) -> str:
        return f"GameFS({self.game_dir!r}, mods={self.mods}, {len(self.containers)} containers, {len(self)} files)"

    def entry(self, path: str) -> Optional[Entry]:
        lst = self._all.get(path_key(path))
        return lst[0] if lst else None

    def sources(self, path: str) -> list[Entry]:
        """Every provider of ``path``, winner first."""
        return list(self._all.get(path_key(path), ()))

    def exists(self, path: str) -> bool:
        return path_key(path) in self._all

    def real_path(self, path: str) -> Optional[str]:
        e = self.entry(path)
        return e.path if e else None

    def entries(self) -> Iterator[Entry]:
        for lst in self._all.values():
            yield lst[0]

    def list(self, prefix: str = "", ext: Union[str, Iterable[str], None] = None) -> list[str]:
        """Winning paths under ``prefix`` (recursive), sorted case-insensitively."""
        pre = path_key(prefix)
        exts = _norm_exts(ext)
        out = []
        for k, lst in self._all.items():
            if k.startswith(pre) and (exts is None or k.endswith(exts)):
                out.append(lst[0].path)
        return sorted(out, key=lambda s: (s.lower(), s))

    def engine_list(self, directory: str, ext: str) -> list[str]:
        """``FS_ListFiles(directory, ext)`` order: non-recursive, highest-priority container first,
        zip directory order inside a pk3, first spelling kept."""
        d = path_key(directory).rstrip("/")
        depth = d.count("/") + 1 if d else 0
        e = ext.lower()
        by_container: dict[str, list[Entry]] = {}
        for k, lst in self._all.items():
            if not k.endswith(e) or k.count("/") != depth or (d and not k.startswith(d + "/")):
                continue
            for ent in lst:
                by_container.setdefault(ent.container, []).append(ent)
        out, seen = [], set()
        for c in sorted(self.containers, key=lambda c: -c.priority):
            for ent in sorted(by_container.get(c.path, ()), key=lambda x: (x.index, x.path.lower())):
                if ent.path.lower() not in seen:
                    seen.add(ent.path.lower())
                    out.append(ent.path)
        return out

    # ------------------------------------------------------------- reading
    def _zip(self, path: str) -> zipfile.ZipFile:
        zf = self._zips.get(path)
        if zf is None:
            zf = self._zips[path] = zipfile.ZipFile(path)
        return zf

    def open(self, path: str) -> BinaryIO:
        e = self.entry(path)
        if e is None:
            raise FileNotFoundError(path)
        if e.member is None:
            return open(os.path.join(e.container, *e.path.split("/")), "rb")
        return self._zip(e.container).open(e.member)  # type: ignore[return-value]

    def read(self, path: str) -> bytes:
        with self.open(path) as fh:
            return fh.read()

    def read_text(self, path: str) -> str:
        return self.read(path).decode("latin-1")

    def close(self) -> None:
        for zf in self._zips.values():
            zf.close()
        self._zips.clear()

    def __enter__(self) -> "GameFS":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -------------------------------------------------------------- images
    def image_candidates(self, name: str) -> list[str]:
        """Paths tried, in engine order, for a texture/shader/image name."""
        n = normalize(name)
        stem, ext = split_image_ext(n)
        if ext in (".tga", ".jpg", ".jpeg", ""):
            exts = [".jpg", ".tga"]
        else:
            exts = [ext, ".jpg", ".tga"]
        bases = [stem] if stem.lower().startswith("textures/") else ["textures/" + stem, stem]
        return [b + x for b in bases for x in exts]

    def find_image(self, name: str) -> Optional[str]:
        """Resolve ``a/b``, ``textures/a/b`` or ``.../b.tga`` to the image file the engine loads."""
        for c in self.image_candidates(name):
            e = self.entry(c)
            if e is not None:
                return e.path
        return None

    def image_info(self, path: str) -> Optional[ImageInfo]:
        """Header-only image probe (TGA, JPEG, PNG, DDS). ``path`` may also be a texture name."""
        real = self.real_path(path) or self.find_image(path)
        if real is None:
            return None
        with self.open(real) as fh:
            return probe_image(fh, real)

    def image_size(self, path: str) -> Optional[tuple[int, int]]:
        info = self.image_info(path)
        return (info.width, info.height) if info else None


def _norm_exts(ext: Union[str, Iterable[str], None]) -> Optional[tuple[str, ...]]:
    if ext is None:
        return None
    items = [ext] if isinstance(ext, str) else list(ext)
    return tuple(("" if x.startswith(".") else ".") + x.lower() for x in items)


# ---------------------------------------------------------------------------
# Image headers


def probe_image(fh: BinaryIO, name: str = "") -> Optional[ImageInfo]:
    head = fh.read(32)
    if head[:2] == b"\xff\xd8":
        return _probe_jpeg(head, fh)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return ImageInfo(w, h, "png", head[24], head[25] in (4, 6))
    if head[:4] == b"DDS ":
        h, w = struct.unpack("<II", head[12:20])
        return ImageInfo(w, h, "dds")
    if name.lower().endswith(".tga") and len(head) >= 18:
        img_type = head[2]
        w, h = struct.unpack("<HH", head[12:16])
        bits, desc = head[16], head[17]
        if img_type in (1, 2, 3, 9, 10, 11) and w and h:
            return ImageInfo(w, h, "tga", bits, bits == 32 or (desc & 0x0F) > 0)
    return None


_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _probe_jpeg(head: bytes, fh: BinaryIO) -> Optional[ImageInfo]:
    buf = bytearray(head)
    pos = 2

    def need(n: int) -> bool:
        while len(buf) < n:
            chunk = fh.read(max(4096, n - len(buf)))
            if not chunk:
                return False
            buf.extend(chunk)
        return True

    while need(pos + 4):
        if buf[pos] != 0xFF:
            pos += 1
            continue
        marker = buf[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        seglen = (buf[pos + 2] << 8) | buf[pos + 3]
        if marker in _SOF:
            if not need(pos + 10):
                return None
            h = (buf[pos + 5] << 8) | buf[pos + 6]
            w = (buf[pos + 7] << 8) | buf[pos + 8]
            return ImageInfo(w, h, "jpg", buf[pos + 4] * buf[pos + 9], False)
        if marker == 0xD9:
            return None
        pos += 2 + seglen
    return None


# ---------------------------------------------------------------------------
# Writing


def write_pk3(out_path: str, files: dict[str, Union[bytes, str, "os.PathLike[str]"]],
              compresslevel: int = 9) -> list[str]:
    """Write a deterministic pk3: forward-slash names, sorted entries, fixed timestamps and
    attributes, no directory entries. Identical inputs give identical bytes. Returns the
    entry names written."""
    data: dict[str, bytes] = {}
    seen: set[str] = set()
    for name, src in files.items():
        n = normalize(name)
        if not n or n.endswith("/") or any(part in ("", ".", "..") for part in n.split("/")):
            raise ValueError(f"bad pk3 entry name: {name!r}")
        if n.lower() in seen:
            raise ValueError(f"duplicate pk3 entry (case-insensitive): {name!r}")
        seen.add(n.lower())
        data[n] = bytes(src) if isinstance(src, (bytes, bytearray, memoryview)) else _read_file(src)
    names = sorted(data, key=lambda s: (s.lower(), s))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=compresslevel) as zf:
        for n in names:
            info = zipfile.ZipInfo(n, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, data[n], compress_type=zipfile.ZIP_DEFLATED, compresslevel=compresslevel)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, out_path)
    return names


def _read_file(src: Union[str, "os.PathLike[str]"]) -> bytes:
    with open(src, "rb") as fh:
        return fh.read()


def image_clashes(main_dir: Union[str, "os.PathLike[str]"]) -> list[tuple[str, list[str]]]:
    """Images that exist as both ``x.jpg`` and ``x.tga`` among the pk3s of a game folder
    (in one pk3 or across several): the renderer tries the ``.jpg`` first for either name
    (``renderergl1/tr_image.c`` R_LoadImage), so a stale or foreign JPG hides a TGA with
    alpha. Returns ``[(stem, ["pk3:ext", ...])]``."""
    seen: dict[str, set] = {}
    for name in sorted(os.listdir(main_dir)):
        if not name.lower().endswith(".pk3"):
            continue
        try:
            with zipfile.ZipFile(os.path.join(main_dir, name)) as z:
                for n in z.namelist():
                    stem, ext = n[:-4].lower(), n[-4:].lower()
                    if ext in (".jpg", ".tga"):
                        seen.setdefault(stem, set()).add(f"{name}:{ext[1:]}")
        except zipfile.BadZipFile:
            continue
    return [(s, sorted(w)) for s, w in sorted(seen.items())
            if {x[-3:] for x in w} == {"jpg", "tga"} and not all(is_retail_pak(x.split(":")[0]) for x in w)]
