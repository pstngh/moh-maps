"""Read Valve Texture Format (VTF) files, versions 7.1 - 7.5.

Header (little endian, packed)::

    off size
      0   4  char  signature "VTF\\0"
      4   8  uint32 version[2]           major 7, minor 1..5
     12   4  uint32 header_size          offset of the image data (7.1/7.2) /
                                         size of header + resource dictionary (7.3+)
     16   2  uint16 width
     18   2  uint16 height
     20   4  uint32 flags                (0x4000 = ENVMAP / cube map, 0x2000 = ONEBITALPHA, ...)
     24   2  uint16 frames
     26   2  uint16 first_frame          (0xFFFF on 7.5+ cube maps without sphere map)
     28   4  padding
     32  12  float  reflectivity[3]
     44   4  padding
     48   4  float  bumpmap_scale
     52   4  int32  high_res_format      (IMAGE_FORMAT_*, see ``Fmt``)
     56   1  uint8  mipmap_count
     57   4  int32  low_res_format       (thumbnail, normally DXT1; -1 = none)
     61   1  uint8  low_res_width
     62   1  uint8  low_res_height
     63   2  uint16 depth                (7.2+, 1 for 2D textures)
     65   3  padding                     (7.3+)
     68   4  uint32 num_resources        (7.3+)
     72   8  padding
     80   8*n resource entries: uint8 tag[3], uint8 flags, uint32 offset
                                         tag b"\\x01\\0\\0" = low-res image,
                                         tag b"\\x30\\0\\0" = high-res image data.
                                         flags & 2: no data, ``offset`` holds the value.

Data layout: 7.1/7.2 store the low-res thumbnail at ``header_size`` and the
high-res data right after it; 7.3+ take both offsets from the resource entries.
High-res data is ordered::

    for mip in smallest .. largest:          # mip (mipmap_count-1) first, mip 0 last
        for frame in frames:
            for face in faces:               # 1, or 6/7 for cube maps
                for slice in depth(mip):
                    image bytes

``faces`` = 1 unless flags & ENVMAP; then 7 (with sphere map) when version < 7.5
and first_frame != 0xFFFF, else 6. Mip sizes are ``max(1, dim >> mip)`` (depth
too); block compressed formats round up to 4x4 blocks. This layout reproduces
the exact file size of 12380 of the 12414 VTFs in CS:GO's pak01. The other 34
(DXT depth-4 glove customization textures) pad mip 1 to four slices, so mip 0 is
located from the *end* of the high-res block when the sizes disagree
(``VTF.layout_mismatch``); map textures are never affected.

``decode()`` returns the largest mip of frame 0 / face 0 / slice 0 as an
``(h, w, 4)`` uint8 RGBA array. DXT decoding is numpy-vectorised: palettes are
built for all blocks at once and indices are gathered with fancy indexing.
"""

from __future__ import annotations

import enum
import os
import struct
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np


class Fmt(enum.IntEnum):
    NONE = -1
    RGBA8888 = 0
    ABGR8888 = 1
    RGB888 = 2
    BGR888 = 3
    RGB565 = 4
    I8 = 5
    IA88 = 6
    P8 = 7
    A8 = 8
    RGB888_BLUESCREEN = 9
    BGR888_BLUESCREEN = 10
    ARGB8888 = 11
    BGRA8888 = 12
    DXT1 = 13
    DXT3 = 14
    DXT5 = 15
    BGRX8888 = 16
    BGR565 = 17
    BGRX5551 = 18
    BGRA4444 = 19
    DXT1_ONEBITALPHA = 20
    BGRA5551 = 21
    UV88 = 22
    UVWQ8888 = 23
    RGBA16161616F = 24
    RGBA16161616 = 25
    UVLX8888 = 26
    R32F = 27
    RGB323232F = 28
    RGBA32323232F = 29
    NV_DST16 = 30
    NV_DST24 = 31
    NV_INTZ = 32
    NV_RAWZ = 33
    ATI_DST16 = 34
    ATI_DST24 = 35
    NV_NULL = 36
    ATI2N = 37  # BC5 (two-channel normal maps)
    ATI1N = 38  # BC4


# Bytes per pixel for uncompressed formats.
_BPP = {
    Fmt.RGBA8888: 4, Fmt.ABGR8888: 4, Fmt.RGB888: 3, Fmt.BGR888: 3, Fmt.RGB565: 2, Fmt.I8: 1,
    Fmt.IA88: 2, Fmt.P8: 1, Fmt.A8: 1, Fmt.RGB888_BLUESCREEN: 3, Fmt.BGR888_BLUESCREEN: 3,
    Fmt.ARGB8888: 4, Fmt.BGRA8888: 4, Fmt.BGRX8888: 4, Fmt.BGR565: 2, Fmt.BGRX5551: 2,
    Fmt.BGRA4444: 2, Fmt.BGRA5551: 2, Fmt.UV88: 2, Fmt.UVWQ8888: 4, Fmt.RGBA16161616F: 8,
    Fmt.RGBA16161616: 8, Fmt.UVLX8888: 4, Fmt.R32F: 4, Fmt.RGB323232F: 12, Fmt.RGBA32323232F: 16,
    Fmt.NV_DST16: 2, Fmt.NV_DST24: 4, Fmt.NV_INTZ: 4, Fmt.NV_RAWZ: 4, Fmt.ATI_DST16: 2,
    Fmt.ATI_DST24: 4, Fmt.NV_NULL: 4,
}
# Bytes per 4x4 block for block-compressed formats.
_BLOCK = {Fmt.DXT1: 8, Fmt.DXT1_ONEBITALPHA: 8, Fmt.DXT3: 16, Fmt.DXT5: 16, Fmt.ATI1N: 8, Fmt.ATI2N: 16}


class Flag(enum.IntFlag):
    POINTSAMPLE = 0x1
    TRILINEAR = 0x2
    CLAMPS = 0x4
    CLAMPT = 0x8
    ANISOTROPIC = 0x10
    HINT_DXT5 = 0x20
    SRGB = 0x40  # PWL_CORRECTED in older SDKs
    NORMAL = 0x80
    NOMIP = 0x100
    NOLOD = 0x200
    ALL_MIPS = 0x400
    PROCEDURAL = 0x800
    ONEBITALPHA = 0x1000
    EIGHTBITALPHA = 0x2000
    ENVMAP = 0x4000
    RENDERTARGET = 0x8000
    DEPTHRENDERTARGET = 0x10000
    NODEBUGOVERRIDE = 0x20000
    SINGLECOPY = 0x40000
    SSBUMP = 0x8000000
    BORDER = 0x20000000


RES_LOWRES = b"\x01\x00\x00"
RES_HIGHRES = b"\x30\x00\x00"


def image_size(fmt: int, width: int, height: int, depth: int = 1) -> int:
    """Byte size of one image (one mip of one frame/face) including all depth slices."""
    f = Fmt(fmt)
    if f in _BLOCK:
        return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * _BLOCK[f] * depth
    if f in _BPP:
        return width * height * _BPP[f] * depth
    raise ValueError(f"unknown VTF image format {fmt}")


@dataclass
class VTFHeader:
    version: tuple[int, int]
    header_size: int
    width: int
    height: int
    flags: int
    frames: int
    first_frame: int
    reflectivity: tuple[float, float, float]
    bumpmap_scale: float
    format: int
    mipmap_count: int
    lowres_format: int
    lowres_width: int
    lowres_height: int
    depth: int
    resources: dict[bytes, tuple[int, int]]  # tag -> (flags, offset/value)

    @property
    def format_name(self) -> str:
        try:
            return Fmt(self.format).name
        except ValueError:
            return f"UNKNOWN_{self.format}"

    @property
    def faces(self) -> int:
        if not self.flags & Flag.ENVMAP:
            return 1
        if self.version[1] < 5 and self.first_frame != 0xFFFF:
            return 7
        return 6


class VTFError(ValueError):
    pass


class VTF:
    """A parsed VTF file held in memory."""

    def __init__(self, data: bytes, name: str = "<vtf>"):
        self.data = data
        self.name = name
        self.header = _parse_header(data, name)
        h = self.header
        if h.format not in _BPP and h.format not in _BLOCK:
            raise VTFError(f"{name}: unsupported image format {h.format}")
        self.highres_offset = self._highres_offset()
        self.highres_end = self._highres_end()
        self.chain_size = sum(self._mip_block_size(m) for m in range(h.mipmap_count))
        # Some CS:GO DXT volume textures (glove customization, depth 4) pad the
        # smaller mips, so the computed chain is shorter than the stored data. The
        # largest mip is always stored last, so anchor mip 0 to the end instead.
        self.layout_mismatch = self.highres_offset + self.chain_size != self.highres_end

    @classmethod
    def open(cls, path: Union[str, os.PathLike]) -> "VTF":
        with open(path, "rb") as fh:
            return cls(fh.read(), str(path))

    # -------------------------------------------------------------- layout
    def _highres_offset(self) -> int:
        h = self.header
        if h.version[1] >= 3:
            res = h.resources.get(RES_HIGHRES)
            if res is None:
                raise VTFError(f"{self.name}: no high-res image resource")
            return res[1]
        off = h.header_size
        if h.lowres_format not in (-1, 0xFFFFFFFF) and h.lowres_width and h.lowres_height:
            off += image_size(h.lowres_format, h.lowres_width, h.lowres_height)
        return off

    def _highres_end(self) -> int:
        """End of the high-res block: the next data-bearing resource, else end of file."""
        end = len(self.data)
        for tag, (flags, off) in self.header.resources.items():
            if not flags & 2 and self.highres_offset < off < end:
                end = off
        return end

    def mip_dims(self, mip: int) -> tuple[int, int, int]:
        h = self.header
        return max(1, h.width >> mip), max(1, h.height >> mip), max(1, h.depth >> mip)

    def _mip_block_size(self, mip: int) -> int:
        """Bytes of one mip level across all frames, faces and slices."""
        h = self.header
        w, ht, d = self.mip_dims(mip)
        return image_size(h.format, w, ht, d) * h.frames * h.faces

    def image_offset(self, mip: int = 0, frame: int = 0, face: int = 0, slice_: int = 0) -> int:
        """Absolute byte offset of one 2D image in the file."""
        h = self.header
        faces = h.faces
        w, ht, d = self.mip_dims(mip)
        one = image_size(h.format, w, ht)
        if mip == 0 and self.layout_mismatch and self.highres_end - self._mip_block_size(0) >= self.highres_offset:
            off = self.highres_end - self._mip_block_size(0)
        else:
            off = self.highres_offset
            for m in range(h.mipmap_count - 1, mip, -1):  # skip smaller mips (stored first)
                off += self._mip_block_size(m)
        return off + ((frame * faces + face) * d + slice_) * one

    def raw_image(self, mip: int = 0, frame: int = 0, face: int = 0, slice_: int = 0) -> bytes:
        w, ht, _ = self.mip_dims(mip)
        off = self.image_offset(mip, frame, face, slice_)
        size = image_size(self.header.format, w, ht)
        if off + size > len(self.data):
            raise VTFError(f"{self.name}: image data truncated (need {off + size}, have {len(self.data)})")
        return self.data[off : off + size]

    # -------------------------------------------------------------- decoding
    def decode(self, mip: int = 0, frame: int = 0, face: int = 0) -> np.ndarray:
        """RGBA uint8 array of shape (height, width, 4)."""
        w, h, _ = self.mip_dims(mip)
        return decode_image(self.raw_image(mip, frame, face), self.header.format, w, h)

    def to_pil(self, mip: int = 0):
        return to_pil(self.decode(mip))

    @property
    def width(self) -> int:
        return self.header.width

    @property
    def height(self) -> int:
        return self.header.height

    def __repr__(self) -> str:
        h = self.header
        return (f"VTF({self.name!r}, {h.version[0]}.{h.version[1]}, {h.width}x{h.height}, {h.format_name}, "
                f"mips={h.mipmap_count}, frames={h.frames}, faces={h.faces}, depth={h.depth})")


def _parse_header(data: bytes, name: str) -> VTFHeader:
    if len(data) < 64 or data[:4] != b"VTF\0":
        raise VTFError(f"{name}: not a VTF file")
    major, minor, header_size = struct.unpack_from("<3I", data, 4)
    if major != 7 or not 0 <= minor <= 5:
        raise VTFError(f"{name}: unsupported VTF version {major}.{minor}")
    width, height, flags, frames, first_frame = struct.unpack_from("<HHIHH", data, 16)
    refl = struct.unpack_from("<3f", data, 32)
    bump_scale, fmt, mips, lowfmt, loww, lowh = struct.unpack_from("<fiBiBB", data, 48)
    depth = struct.unpack_from("<H", data, 63)[0] if minor >= 2 else 1
    resources: dict[bytes, tuple[int, int]] = {}
    if minor >= 3:
        nres = struct.unpack_from("<I", data, 68)[0]
        for i in range(nres):
            tag, rflags, off = struct.unpack_from("<3sBI", data, 80 + 8 * i)
            resources[tag] = (rflags, off)
    return VTFHeader((major, minor), header_size, width, height, flags, max(1, frames), first_frame,
                     refl, bump_scale, fmt, max(1, mips), lowfmt, loww, lowh, max(1, depth), resources)


def read_header(data: bytes, name: str = "<vtf>") -> VTFHeader:
    """Parse only the header (cheap; no format validation)."""
    return _parse_header(data, name)


# ---------------------------------------------------------------------------
# Pixel decoders

def _expand565(c: np.ndarray) -> np.ndarray:
    """uint16 R5G6B5 (R in the high bits) -> (..., 3) uint8."""
    c = c.astype(np.uint32)
    r = (c >> 11) & 31
    g = (c >> 5) & 63
    b = c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1).astype(np.uint8)


def _blocks_to_image(texels: np.ndarray, bw: int, bh: int, w: int, h: int) -> np.ndarray:
    """(bh*bw, 16, C) per-block texels (row-major inside the block) -> (h, w, C)."""
    c = texels.shape[-1]
    img = texels.reshape(bh, bw, 4, 4, c).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, c)
    return np.ascontiguousarray(img[:h, :w])


_SHIFT2 = (np.arange(16, dtype=np.uint32) * 2)
_SHIFT3 = (np.arange(16, dtype=np.uint64) * 3)
_SHIFT4 = (np.arange(16, dtype=np.uint64) * 4)


def _dxt_color(block8: np.ndarray, four_color_only: bool) -> np.ndarray:
    """Decode the 8-byte colour half of DXT blocks. block8: (N, 8) uint8 -> (N, 16, 4) uint8."""
    n = block8.shape[0]
    c0 = block8[:, 0].astype(np.uint16) | (block8[:, 1].astype(np.uint16) << 8)
    c1 = block8[:, 2].astype(np.uint16) | (block8[:, 3].astype(np.uint16) << 8)
    idx = np.ascontiguousarray(block8[:, 4:8]).view("<u4").reshape(n)
    p0 = _expand565(c0).astype(np.uint16)
    p1 = _expand565(c1).astype(np.uint16)
    pal = np.empty((n, 4, 4), np.uint8)
    pal[:, 0, :3] = p0
    pal[:, 1, :3] = p1
    pal[:, :, 3] = 255
    four = (c0 > c1) if not four_color_only else np.ones(n, bool)
    pal[:, 2, :3] = np.where(four[:, None], (2 * p0 + p1 + 1) // 3, (p0 + p1) // 2)
    pal[:, 3, :3] = np.where(four[:, None], (p0 + 2 * p1 + 1) // 3, 0)
    pal[:, 3, 3] = np.where(four, 255, 0)
    sel = (idx[:, None] >> _SHIFT2[None, :]) & 3  # (N, 16)
    return pal[np.arange(n)[:, None], sel]


def _dxt5_alpha(block8: np.ndarray) -> np.ndarray:
    """Decode interpolated (DXT5/BC4) alpha halves. (N, 8) uint8 -> (N, 16) uint8."""
    n = block8.shape[0]
    a0 = block8[:, 0].astype(np.int32)
    a1 = block8[:, 1].astype(np.int32)
    bits = np.zeros(n, np.uint64)
    for i in range(6):
        bits |= block8[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    sel = ((bits[:, None] >> _SHIFT3[None, :]) & np.uint64(7)).astype(np.intp)
    pal = np.empty((n, 8), np.int32)
    pal[:, 0] = a0
    pal[:, 1] = a1
    eight = (a0 > a1)[:, None]
    k = np.arange(1, 7, dtype=np.int32)[None, :]
    interp8 = ((7 - k) * a0[:, None] + k * a1[:, None] + 3) // 7          # codes 2..7
    k5 = np.arange(1, 5, dtype=np.int32)[None, :]
    interp6 = ((5 - k5) * a0[:, None] + k5 * a1[:, None] + 2) // 5         # codes 2..5
    six = np.concatenate([interp6, np.zeros((n, 1), np.int32), np.full((n, 1), 255, np.int32)], axis=1)
    pal[:, 2:] = np.where(eight, interp8, six)
    return pal[np.arange(n)[:, None], sel].astype(np.uint8)


def decode_dxt(data: bytes, fmt: int, width: int, height: int) -> np.ndarray:
    f = Fmt(fmt)
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    bs = _BLOCK[f]
    blocks = np.frombuffer(data, np.uint8, bw * bh * bs).reshape(bw * bh, bs)
    if f in (Fmt.DXT1, Fmt.DXT1_ONEBITALPHA):
        tex = _dxt_color(blocks, four_color_only=False)
    elif f == Fmt.DXT3:
        tex = _dxt_color(blocks[:, 8:], four_color_only=True)
        abits = np.ascontiguousarray(blocks[:, :8]).view("<u8").reshape(-1)
        a = ((abits[:, None] >> _SHIFT4[None, :]) & np.uint64(15)).astype(np.uint8)
        tex[:, :, 3] = a * 17
    elif f == Fmt.DXT5:
        tex = _dxt_color(blocks[:, 8:], four_color_only=True)
        tex[:, :, 3] = _dxt5_alpha(blocks[:, :8])
    elif f == Fmt.ATI1N:
        r = _dxt5_alpha(blocks)
        tex = np.stack([r, r, r, np.full_like(r, 255)], axis=-1)
    elif f == Fmt.ATI2N:
        # Source stores the second channel first for ATI2N (Y then X).
        g = _dxt5_alpha(blocks[:, :8])
        r = _dxt5_alpha(blocks[:, 8:])
        x = r.astype(np.float32) / 127.5 - 1.0
        y = g.astype(np.float32) / 127.5 - 1.0
        z = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0))
        b = np.clip((z + 1.0) * 127.5 + 0.5, 0, 255).astype(np.uint8)
        tex = np.stack([r, g, b, np.full_like(r, 255)], axis=-1)
    else:
        raise VTFError(f"not a block format: {f.name}")
    return _blocks_to_image(tex, bw, bh, width, height)


def _tonemap(rgb: np.ndarray) -> np.ndarray:
    """Linear HDR float -> display uint8: clamp to [0, 1], then gamma 2.2."""
    rgb = np.nan_to_num(rgb, nan=0.0, posinf=1.0, neginf=0.0)
    return (np.power(np.clip(rgb, 0.0, 1.0), 1.0 / 2.2) * 255.0 + 0.5).astype(np.uint8)


def decode_image(data: bytes, fmt: int, width: int, height: int) -> np.ndarray:
    """Decode one image of any supported format to (height, width, 4) uint8 RGBA."""
    f = Fmt(fmt)
    if f in _BLOCK:
        return decode_dxt(data, f, width, height)
    n = width * height
    bpp = _BPP[f]
    raw = np.frombuffer(data, np.uint8, n * bpp)
    out = np.empty((n, 4), np.uint8)
    out[:, 3] = 255
    if bpp in (3, 4) and f not in (Fmt.R32F,):
        px = raw.reshape(n, bpp)
    if f in (Fmt.RGBA8888, Fmt.UVWQ8888, Fmt.UVLX8888):
        out[:] = px
    elif f == Fmt.ABGR8888:
        out[:] = px[:, ::-1]
    elif f == Fmt.ARGB8888:
        out[:] = px[:, [1, 2, 3, 0]]
    elif f == Fmt.BGRA8888:
        out[:] = px[:, [2, 1, 0, 3]]
    elif f == Fmt.BGRX8888:
        out[:, :3] = px[:, [2, 1, 0]]
    elif f in (Fmt.RGB888, Fmt.RGB888_BLUESCREEN):
        out[:, :3] = px
        if f == Fmt.RGB888_BLUESCREEN:
            out[:, 3] = np.where((px[:, 0] == 0) & (px[:, 1] == 0) & (px[:, 2] == 255), 0, 255)
    elif f in (Fmt.BGR888, Fmt.BGR888_BLUESCREEN):
        out[:, :3] = px[:, ::-1]
        if f == Fmt.BGR888_BLUESCREEN:
            out[:, 3] = np.where((px[:, 2] == 0) & (px[:, 1] == 0) & (px[:, 0] == 255), 0, 255)
    elif f in (Fmt.I8, Fmt.P8):
        out[:, 0] = out[:, 1] = out[:, 2] = raw
    elif f == Fmt.A8:
        out[:, :3] = 0
        out[:, 3] = raw
    elif f == Fmt.IA88:
        px2 = raw.reshape(n, 2)
        out[:, 0] = out[:, 1] = out[:, 2] = px2[:, 0]
        out[:, 3] = px2[:, 1]
    elif f == Fmt.UV88:
        px2 = raw.reshape(n, 2)
        out[:, 0] = px2[:, 0]
        out[:, 1] = px2[:, 1]
        out[:, 2] = 0
    elif f in (Fmt.BGR565, Fmt.RGB565):
        v = np.frombuffer(data, "<u2", n)
        rgb = _expand565(v)  # R from the high bits (BGR565 in VTF naming)
        out[:, :3] = rgb if f == Fmt.BGR565 else rgb[:, ::-1]
    elif f in (Fmt.BGRA4444,):
        v = np.frombuffer(data, "<u2", n).astype(np.uint16)
        out[:, 2] = (v & 15) * 17
        out[:, 1] = ((v >> 4) & 15) * 17
        out[:, 0] = ((v >> 8) & 15) * 17
        out[:, 3] = ((v >> 12) & 15) * 17
    elif f in (Fmt.BGRX5551, Fmt.BGRA5551):
        v = np.frombuffer(data, "<u2", n).astype(np.uint16)
        for ch, shift in ((2, 0), (1, 5), (0, 10)):
            c = (v >> shift) & 31
            out[:, ch] = (c << 3) | (c >> 2)
        if f == Fmt.BGRA5551:
            out[:, 3] = np.where(v & 0x8000, 255, 0)
    elif f == Fmt.RGBA16161616F:
        with np.errstate(invalid="ignore", over="ignore"):
            v = np.frombuffer(data, "<f2", n * 4).reshape(n, 4).astype(np.float32)
        out[:, :3] = _tonemap(v[:, :3])
        # HDR sky/cubemap textures leave alpha at 0; treat an all-zero alpha as opaque.
        if v[:, 3].max(initial=0.0) > 0.0:
            out[:, 3] = (np.clip(v[:, 3], 0, 1) * 255 + 0.5).astype(np.uint8)
    elif f == Fmt.RGBA16161616:
        v = np.frombuffer(data, "<u2", n * 4).reshape(n, 4)
        out[:] = (v >> 8).astype(np.uint8)
    elif f == Fmt.R32F:
        v = np.frombuffer(data, "<f4", n)
        out[:, 0] = out[:, 1] = out[:, 2] = _tonemap(v)
    elif f == Fmt.RGB323232F:
        v = np.frombuffer(data, "<f4", n * 3).reshape(n, 3)
        out[:, :3] = _tonemap(v)
    elif f == Fmt.RGBA32323232F:
        v = np.frombuffer(data, "<f4", n * 4).reshape(n, 4)
        out[:, :3] = _tonemap(v[:, :3])
        out[:, 3] = (np.clip(v[:, 3], 0, 1) * 255 + 0.5).astype(np.uint8)
    else:
        raise VTFError(f"decoding {f.name} is not supported")
    return out.reshape(height, width, 4)


# ---------------------------------------------------------------------------
# Output helpers

def to_pil(rgba: np.ndarray):
    """PIL RGBA image from an (h, w, 4) uint8 array."""
    from PIL import Image
    return Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), "RGBA")


def save_tga(rgba: np.ndarray, path: Union[str, os.PathLike], alpha: Optional[bool] = None) -> None:
    """Write an uncompressed TGA (type 2), bottom-up rows as id Tech 3 expects.

    ``alpha=None`` writes 32-bit only if any pixel is not fully opaque, else 24-bit.
    """
    img = np.ascontiguousarray(rgba, dtype=np.uint8)
    h, w = img.shape[:2]
    if alpha is None:
        alpha = bool((img[..., 3] != 255).any())
    bgr = img[::-1, :, [2, 1, 0, 3] if alpha else [2, 1, 0]]  # flip rows: origin bottom-left
    bits = 32 if alpha else 24
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, bits, 8 if alpha else 0)
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(np.ascontiguousarray(bgr).tobytes())


def load_vtf(source, name: str) -> VTF:
    """Load ``materials/<name>.vtf`` from a VPK/SearchPath (``name`` as in ``$basetexture``)."""
    from .vmt import texture_path
    path = texture_path(name)
    data = source.try_read(path)
    if data is None:
        raise KeyError(path)
    return VTF(data, path)
