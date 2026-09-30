"""Read Valve VPK archives (versions 1 and 2) and chain file sources.

Only the reader lives here; nothing is ever copied into the repository.

Binary layout (all little endian)
---------------------------------
A VPK set is a *directory* file ``<name>_dir.vpk`` plus optional numbered
archives ``<name>_000.vpk``, ``<name>_001.vpk`` ...

Header, version 1 (12 bytes)::

    uint32 signature   0x55AA1234
    uint32 version     1
    uint32 tree_size   bytes of directory tree that follow the header

Header, version 2 (28 bytes) adds::

    uint32 file_data_section_size   data embedded in the _dir file after the tree
    uint32 archive_md5_section_size
    uint32 other_md5_section_size
    uint32 signature_section_size

The directory tree is three nested lists of NUL-terminated strings, each list
terminated by an empty string::

    for extension in strings:          # "vtf", "vmt", ... (" " = no extension)
        for directory in strings:      # "materials/brick" (" " = root)
            for filename in strings:   # "brickwall001a"
                uint32 crc32           # of the complete file
                uint16 preload_bytes   # bytes stored inline right after this record
                uint16 archive_index   # 0x7FFF = data lives in the _dir file itself
                uint32 entry_offset    # offset inside the archive
                uint32 entry_length    # bytes in the archive (excluding preload)
                uint16 terminator      # 0xFFFF
                byte   preload[preload_bytes]

A file's content is ``preload + archive[entry_offset : entry_offset + entry_length]``.
For ``archive_index == 0x7FFF`` the offset is relative to the end of the tree
(``header_size + tree_size``) inside the ``_dir`` file.

Paths are matched case-insensitively with ``/`` separators.
"""

from __future__ import annotations

import fnmatch
import io
import os
import struct
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Optional, Protocol, Union, runtime_checkable

VPK_SIGNATURE = 0x55AA1234
DIR_ARCHIVE_INDEX = 0x7FFF
_ENTRY = struct.Struct("<IHHIIH")  # crc, preload, archive, offset, length, terminator


def normalize_path(path: str) -> str:
    """Canonical lookup key: lower case, forward slashes, no leading ``./`` or ``/``.

    Whitespace is kept: CS:GO ships files such as
    ``materials/de_mirage/base/de_mirage_base_trim_ver1_diffuse .vmt`` and BSP
    texdata names with the same trailing space.
    """
    p = path.replace("\\", "/").lower()
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    while "//" in p:
        p = p.replace("//", "/")
    return p


@dataclass(frozen=True)
class VPKEntry:
    path: str             # normalized (lower-case) path, e.g. "materials/tools/toolsclip.vmt"
    crc: int
    preload_offset: int   # absolute offset of the preload bytes in the _dir file
    preload_length: int
    archive_index: int    # 0x7FFF = stored in the _dir file after the tree
    offset: int
    length: int

    @property
    def size(self) -> int:
        return self.preload_length + self.length


class VPK:
    """A VPK directory (``*_dir.vpk``) and its numbered archives.

    >>> vpk = VPK(".../csgo/pak01_dir.vpk")        # doctest: +SKIP
    >>> data = vpk.read("materials/tools/toolsclip.vmt")
    """

    def __init__(self, dir_path: Union[str, os.PathLike]):
        self.dir_path = Path(dir_path)
        name = self.dir_path.name
        if not name.lower().endswith("_dir.vpk"):
            raise ValueError(f"{dir_path}: expected a *_dir.vpk file")
        self._prefix = str(self.dir_path)[: -len("_dir.vpk")]
        self._handles: dict[int, BinaryIO] = {}
        with open(self.dir_path, "rb") as fh:
            head = fh.read(28)
            sig, version, tree_size = struct.unpack_from("<III", head)
            if sig != VPK_SIGNATURE:
                raise ValueError(f"{dir_path}: not a VPK (signature {sig:#x})")
            if version == 1:
                self.header_size = 12
                self.file_data_size = 0
            elif version == 2:
                self.header_size = 28
                self.file_data_size = struct.unpack_from("<I", head, 12)[0]
            else:
                raise ValueError(f"{dir_path}: unsupported VPK version {version}")
            self.version = version
            self.tree_size = tree_size
            fh.seek(self.header_size)
            tree = fh.read(tree_size)
        self.data_offset = self.header_size + tree_size  # base for archive_index 0x7FFF
        self.entries: dict[str, VPKEntry] = {}
        self._parse_tree(tree)

    # ------------------------------------------------------------------ parsing
    def _parse_tree(self, tree: bytes) -> None:
        pos = 0
        find = tree.find
        unpack = _ENTRY.unpack_from
        entries = self.entries
        base = self.header_size

        def string() -> str:
            nonlocal pos
            end = find(b"\0", pos)
            if end < 0:
                raise ValueError(f"{self.dir_path}: truncated directory tree")
            s = tree[pos:end].decode("utf-8", "replace")
            pos = end + 1
            return s

        while True:
            ext = string()
            if not ext:
                break
            while True:
                directory = string()
                if not directory:
                    break
                while True:
                    fname = string()
                    if not fname:
                        break
                    crc, preload, archive, offset, length, term = unpack(tree, pos)
                    if term != 0xFFFF:
                        raise ValueError(f"{self.dir_path}: bad entry terminator at tree offset {pos}")
                    pos += _ENTRY.size
                    parts = []
                    if directory != " ":  # a single space marks the root directory
                        parts.append(directory + "/")
                    parts.append(fname)
                    if ext != " ":  # ... and "no extension"
                        parts.append("." + ext)
                    path = normalize_path("".join(parts))
                    entries[path] = VPKEntry(path, crc, base + pos, preload, archive, offset, length)
                    pos += preload

    # ------------------------------------------------------------------ queries
    def __contains__(self, path: str) -> bool:
        return normalize_path(path) in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[str]:
        return iter(self.entries)

    def entry(self, path: str) -> Optional[VPKEntry]:
        return self.entries.get(normalize_path(path))

    def glob(self, pattern: str) -> list[str]:
        """Paths matching a shell pattern (case-insensitive), e.g. ``materials/tools/*.vmt``."""
        pat = normalize_path(pattern)
        return sorted(p for p in self.entries if fnmatch.fnmatchcase(p, pat))

    def listdir(self, directory: str) -> list[str]:
        """Direct children (files only) of ``directory``."""
        d = normalize_path(directory).rstrip("/") + "/"
        return sorted(p for p in self.entries if p.startswith(d) and "/" not in p[len(d):])

    # ------------------------------------------------------------------ reading
    def archive_path(self, index: int) -> str:
        if index == DIR_ARCHIVE_INDEX:
            return str(self.dir_path)
        return f"{self._prefix}_{index:03d}.vpk"

    def _handle(self, index: int) -> BinaryIO:
        fh = self._handles.get(index)
        if fh is None:
            fh = open(self.archive_path(index), "rb")
            self._handles[index] = fh
        return fh

    def read_entry(self, e: VPKEntry, verify: bool = False) -> bytes:
        parts = []
        if e.preload_length:
            fh = self._handle(DIR_ARCHIVE_INDEX)
            fh.seek(e.preload_offset)
            parts.append(fh.read(e.preload_length))
        if e.length:
            fh = self._handle(e.archive_index)
            base = self.data_offset if e.archive_index == DIR_ARCHIVE_INDEX else 0
            fh.seek(base + e.offset)
            chunk = fh.read(e.length)
            if len(chunk) != e.length:
                raise IOError(f"{self.archive_path(e.archive_index)}: short read for {e.path}")
            parts.append(chunk)
        data = b"".join(parts)
        if verify and (zlib.crc32(data) & 0xFFFFFFFF) != e.crc:
            raise IOError(f"CRC mismatch for {e.path}")
        return data

    def read(self, path: str, verify: bool = False) -> bytes:
        """File contents; raises ``KeyError`` if the path is not in the VPK."""
        e = self.entry(path)
        if e is None:
            raise KeyError(path)
        return self.read_entry(e, verify)

    def try_read(self, path: str) -> Optional[bytes]:
        e = self.entry(path)
        return None if e is None else self.read_entry(e)

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()
        self._handles.clear()

    def __enter__(self) -> "VPK":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"VPK({str(self.dir_path)!r}, v{self.version}, {len(self.entries)} files)"


# ---------------------------------------------------------------------------
# Chained file sources (pakfile zip > loose files > VPK), like the engine's
# search paths.


@runtime_checkable
class FileSource(Protocol):
    def try_read(self, path: str) -> Optional[bytes]: ...


class DirectorySource:
    """Loose files under a game directory, matched case-insensitively."""

    def __init__(self, root: Union[str, os.PathLike]):
        self.root = Path(root)

    def try_read(self, path: str) -> Optional[bytes]:
        rel = normalize_path(path)
        p = self.root / rel
        if p.is_file():
            return p.read_bytes()
        # Slow path: case-insensitive walk (macOS is usually case-insensitive anyway).
        cur = self.root
        for part in rel.split("/"):
            if not cur.is_dir():
                return None
            match = next((c for c in cur.iterdir() if c.name.lower() == part), None)
            if match is None:
                return None
            cur = match
        return cur.read_bytes() if cur.is_file() else None

    def __repr__(self) -> str:
        return f"DirectorySource({str(self.root)!r})"


class ZipSource:
    """A zip archive (e.g. a BSP pakfile lump), matched case-insensitively."""

    def __init__(self, zf: Union[zipfile.ZipFile, bytes, str, os.PathLike]):
        if isinstance(zf, (bytes, bytearray)):
            zf = zipfile.ZipFile(io.BytesIO(zf))
        elif not isinstance(zf, zipfile.ZipFile):
            zf = zipfile.ZipFile(zf)
        self.zip = zf
        self.names = {normalize_path(n): n for n in zf.namelist() if not n.endswith("/")}

    def try_read(self, path: str) -> Optional[bytes]:
        n = self.names.get(normalize_path(path))
        return None if n is None else self.zip.read(n)

    def __contains__(self, path: str) -> bool:
        return normalize_path(path) in self.names

    def __repr__(self) -> str:
        return f"ZipSource({len(self.names)} files)"


class SearchPath:
    """Ordered list of file sources; the first one that has a file wins.

    Sources may be :class:`VPK`, :class:`ZipSource`, :class:`DirectorySource` or
    anything with ``try_read(path) -> bytes | None``. Plain directory paths and
    ``zipfile.ZipFile`` objects are wrapped automatically.
    """

    def __init__(self, *sources):
        self.sources: list[FileSource] = []
        for s in sources:
            self.add(s)

    def add(self, source, first: bool = False) -> None:
        if isinstance(source, (str, os.PathLike)):
            p = Path(source)
            source = VPK(p) if p.is_file() and p.name.lower().endswith("_dir.vpk") else DirectorySource(p)
        elif isinstance(source, zipfile.ZipFile):
            source = ZipSource(source)
        if not hasattr(source, "try_read"):
            raise TypeError(f"not a file source: {source!r}")
        if first:
            self.sources.insert(0, source)
        else:
            self.sources.append(source)

    def try_read(self, path: str) -> Optional[bytes]:
        for s in self.sources:
            data = s.try_read(path)
            if data is not None:
                return data
        return None

    def read(self, path: str) -> bytes:
        data = self.try_read(path)
        if data is None:
            raise KeyError(path)
        return data

    def __contains__(self, path: str) -> bool:
        for s in self.sources:
            if isinstance(s, (VPK, ZipSource)):
                if path in s:
                    return True
            elif s.try_read(path) is not None:
                return True
        return False

    @classmethod
    def for_game(cls, game_dir: Union[str, os.PathLike], vpk_names: tuple[str, ...] = ("pak01",)) -> "SearchPath":
        """Loose files in ``game_dir`` first, then ``<name>_dir.vpk`` for each name."""
        game = Path(game_dir)
        sp = cls(DirectorySource(game))
        for n in vpk_names:
            p = game / f"{n}_dir.vpk"
            if p.is_file():
                sp.add(VPK(p))
        return sp

    def __repr__(self) -> str:
        return f"SearchPath({self.sources!r})"
