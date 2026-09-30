"""Read MOHAA BSP files (ident ``2015``, version 19; 17-21 accepted).

Layout (little-endian): header ``ident[4] version checksum`` then 28 lumps of
``(fileofs, filelen)``. Versions <= 18 have an extra FOGS lump at slot 13, so
later lumps shift by one. Element sizes::

    0 SHADERS 140  1 PLANES 16  2 LIGHTMAPS 49152 (128x128 RGB)  3 SURFACES 108
    4 DRAWVERTS 44  5 DRAWINDEXES 4  6 LEAFBRUSHES 4  7 LEAFSURFACES 4  8 LEAFS 64
    9 NODES 36  10 SIDEEQUATIONS 32  11 BRUSHSIDES 12  12 BRUSHES 12  13 MODELS 40
    14 ENTITIES text  15 VISIBILITY  16-18 LIGHTGRID palette/offsets/data
    19 SPHERELIGHTS 56  20 SPHERELIGHTVIS  21 LIGHTDEFS 52  22 TERRAIN 388
    23 TERRAININDEXES 2  24 STATICMODELDATA 3/vertex  25 STATICMODELDEF 164
    26 STATICMODELINDEXES 2  27 unused

Submodels (brush entities) are stored in entity-local space around their origin.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Union

LUMPS = ["shaders", "planes", "lightmaps", "surfaces", "drawverts", "drawindexes", "leafbrushes", "leafsurfaces",
         "leafs", "nodes", "sideequations", "brushsides", "brushes", "models", "entities", "visibility",
         "lightgridpalette", "lightgridoffsets", "lightgriddata", "spherelights", "spherelightvis", "lightdefs",
         "terrain", "terrainindexes", "staticmodeldata", "staticmodeldef", "staticmodelindexes", "dummy"]
SIZES = {"shaders": 140, "planes": 16, "lightmaps": 49152, "surfaces": 108, "drawverts": 44, "drawindexes": 4,
         "leafbrushes": 4, "leafsurfaces": 4, "leafs": 64, "nodes": 36, "sideequations": 32, "brushsides": 12,
         "brushes": 12, "models": 40, "spherelights": 56, "lightdefs": 52, "terrain": 388, "terrainindexes": 2,
         "staticmodeldef": 164, "staticmodelindexes": 2}
LIMITS = {"shaders": 0x400, "planes": 0x20000, "surfaces": 0x20000, "drawverts": 0x80000, "drawindexes": 0x80000,
          "brushes": 0x8000, "brushsides": 0x20000, "leafs": 0x20000, "nodes": 0x20000, "models": 0x400,
          "spherelights": 1532}
SURF_TYPES = {1: "planar", 2: "patch", 3: "trisoup", 4: "flare", 5: "terrain"}

SURF = {0x1: "nodamage", 0x2: "slick", 0x4: "sky", 0x8: "ladder", 0x10: "noimpact", 0x20: "nomarks",
        0x40: "castshadow", 0x80: "nodraw", 0x100: "nolightmap", 0x200: "alphashadow", 0x400: "nosteps",
        0x800: "nonsolid", 0x1000: "overbright", 0x2000: "paper", 0x4000: "wood", 0x8000: "metal",
        0x10000: "rock", 0x20000: "dirt", 0x40000: "grill", 0x80000: "grass", 0x100000: "mud",
        0x200000: "puddle", 0x400000: "glass", 0x800000: "gravel", 0x1000000: "sand", 0x2000000: "foliage",
        0x4000000: "snow", 0x8000000: "carpet", 0x10000000: "backside", 0x20000000: "nodlight",
        0x40000000: "hint", 0x80000000: "patch"}
CONTENTS = {0x1: "solid", 0x2: "ladder", 0x8: "lava", 0x10: "slime", 0x20: "water", 0x40: "fog",
            0x2000: "fence", 0x8000: "areaportal", 0x10000: "playerclip", 0x20000: "monsterclip",
            0x40000: "weaponclip", 0x80000: "vehicleclip", 0x100000: "shootonly", 0x1000000: "origin",
            0x8000000: "detail", 0x10000000: "structural", 0x20000000: "translucent", 0x40000000: "trigger",
            0x80000000: "nodrop"}


def flag_names(value: int, table: dict[int, str]) -> list[str]:
    value &= 0xFFFFFFFF
    return [n for bit, n in table.items() if value & bit]


@dataclass
class Shader:
    name: str
    surface_flags: int
    content_flags: int
    subdivisions: int
    fence_mask: str


@dataclass
class Surface:
    shader: int
    type: int
    first_vert: int
    num_verts: int
    first_index: int
    num_indexes: int
    lightmap: int
    lm_x: int
    lm_y: int
    lm_w: int
    lm_h: int
    patch_w: int
    patch_h: int


@dataclass
class StaticModel:
    model: str
    origin: tuple[float, float, float]
    angles: tuple[float, float, float]
    scale: float
    first_vertex_data: int
    num_vertex_data: int


class BSP:
    def __init__(self, source: Union[str, Path, bytes]):
        self.data = source if isinstance(source, bytes) else Path(source).read_bytes()
        ident, self.version, self.checksum = struct.unpack_from("<4sii", self.data, 0)
        if ident != b"2015" or not 17 <= self.version <= 21:
            raise ValueError(f"not a MOHAA BSP (ident {ident!r}, version {self.version})")
        raw = [struct.unpack_from("<ii", self.data, 12 + 8 * i) for i in range(28)]
        self.lumps: dict[str, tuple[int, int]] = {}
        for i, name in enumerate(LUMPS):
            idx = i + 1 if (self.version <= 18 and i >= 13) else i
            if idx < 28:
                self.lumps[name] = raw[idx]

    def lump(self, name: str) -> bytes:
        ofs, ln = self.lumps[name]
        return self.data[ofs:ofs + ln]

    def count(self, name: str) -> int:
        size = SIZES.get(name)
        return self.lumps[name][1] // size if size else 0

    # ---------------------------------------------------------------- lumps
    def shaders(self) -> list[Shader]:
        d = self.lump("shaders")
        out = []
        for i in range(len(d) // 140):
            name, sf, cf, sub, fence = struct.unpack_from("<64siii64s", d, i * 140)
            out.append(Shader(name.split(b"\0")[0].decode("latin-1"), sf, cf, sub, fence.split(b"\0")[0].decode("latin-1")))
        return out

    def surfaces(self) -> list[Surface]:
        d = self.lump("surfaces")
        out = []
        for i in range(len(d) // 108):
            v = struct.unpack_from("<12i", d, i * 108)
            pw, ph = struct.unpack_from("<ii", d, i * 108 + 96)
            out.append(Surface(v[0], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10], v[11], pw, ph))
        return out

    def entities_text(self) -> str:
        return self.lump("entities").split(b"\0")[0].decode("latin-1")

    def entities(self) -> list[dict[str, str]]:
        out = []
        for block in re.findall(r"\{([^{}]*)\}", self.entities_text()):
            out.append(dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', block)))
        return out

    def static_models(self) -> list[StaticModel]:
        d = self.lump("staticmodeldef")
        out = []
        for i in range(len(d) // 164):
            name = d[i * 164:i * 164 + 128].split(b"\0")[0].decode("latin-1")
            vals = struct.unpack_from("<7fii", d, i * 164 + 128)
            out.append(StaticModel(name, vals[0:3], vals[3:6], vals[6], vals[7], vals[8]))
        return out

    def models(self) -> list[dict]:
        d = self.lump("models")
        out = []
        for i in range(len(d) // 40):
            v = struct.unpack_from("<6f4i", d, i * 40)
            out.append({"mins": v[0:3], "maxs": v[3:6], "first_surface": v[6], "num_surfaces": v[7],
                        "first_brush": v[8], "num_brushes": v[9]})
        return out

    def visibility(self) -> tuple[int, int]:
        d = self.lump("visibility")
        return struct.unpack_from("<ii", d, 0) if len(d) >= 8 else (0, 0)

    def lightmap_image(self, index: int):
        """Lightmap page as a Pillow RGB image (128x128)."""
        from PIL import Image
        ofs, _ = self.lumps["lightmaps"]
        start = ofs + index * 49152
        return Image.frombytes("RGB", (128, 128), self.data[start:start + 49152])

    def lightmap_atlas(self, cols: int = 8):
        from PIL import Image
        n = self.count("lightmaps")
        rows = (n + cols - 1) // cols or 1
        atlas = Image.new("RGB", (cols * 128, rows * 128))
        for i in range(n):
            atlas.paste(self.lightmap_image(i), ((i % cols) * 128, (i // cols) * 128))
        return atlas

    # -------------------------------------------------------------- summary
    def summary(self) -> dict:
        surfs = self.surfaces()
        types: dict[str, int] = {}
        for s in surfs:
            types[SURF_TYPES.get(s.type, str(s.type))] = types.get(SURF_TYPES.get(s.type, str(s.type)), 0) + 1
        shaders = self.shaders()
        ents = self.entities()
        classes: dict[str, int] = {}
        for e in ents:
            classes[e.get("classname", "?")] = classes.get(e.get("classname", "?"), 0) + 1
        clusters, cbytes = self.visibility()
        models = self.models()
        counts = {k: self.count(k) for k in SIZES}
        over = {k: f"{counts[k]}/{v}" for k, v in LIMITS.items() if counts.get(k, 0) > v}
        return {
            "version": self.version,
            "bytes": len(self.data),
            "world_bounds": [models[0]["mins"], models[0]["maxs"]] if models else None,
            "counts": counts,
            "surface_types": types,
            "vis_clusters": clusters,
            "vis_bytes": clusters * cbytes,
            "lightmap_pages": self.count("lightmaps"),
            "static_models": len(self.static_models()),
            "entity_classes": dict(sorted(classes.items(), key=lambda kv: -kv[1])),
            "shaders": sorted({s.name for s in shaders}),
            "over_limit": over,
        }
