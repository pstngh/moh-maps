"""Source studio model geometry: ``.mdl`` + ``.vvd`` + ``.vtx`` meshes and ``.phy`` collision.

Only what a static prop needs is read: LOD 0 triangles of one submodel per body
part, per-material, plus the convex collision pieces. All structures are little
endian; offsets marked *rel* are relative to the start of the structure that
holds them.

MDL (``studiohdr_t``, see :mod:`.mdl` for the header)::

    232 int32 numbodyparts   236 int32 bodypartindex -> mstudiobodyparts_t[]

    mstudiobodyparts_t (16 B)  sznameindex, nummodels, base, modelindex (rel)
    mstudiomodel_t    (148 B)  name[64], type, boundingradius, nummeshes,
                               meshindex (rel), numvertices, vertexindex (bytes
                               into the VVD vertex array, /48 = first vertex),
                               tangentsindex, numattachments, attachmentindex,
                               numeyeballs, eyeballindex, vertexdata[2], unused[8]
    mstudiomesh_t     (116 B)  material (skin reference), modelindex, numvertices,
                               vertexoffset (relative to the model's first vertex),
                               numflexes, flexindex, materialtype, materialparam,
                               meshid, center[3], vertexdata{ptr, numLODVertexes[8]},
                               unused[8]

VVD (``vertexFileHeader_t``, 64 B)::

      0 "IDSV"   4 version (4)   8 checksum   12 numLODs   16 numLODVertexes[8]
     48 numFixups   52 fixupTableStart   56 vertexDataStart   60 tangentDataStart

    vertexFileFixup_t (12 B): lod, sourceVertexID, numVertexes
    mstudiovertex_t   (48 B): weight[3] f32, bone[3] u8, numbones u8, pos[3], normal[3], uv[2]

    With fixups, the LOD-0 vertex array is the concatenation of every fixup range
    whose ``lod >= 0`` (i.e. all of them); without fixups it is the raw array.

VTX (``*.dx90.vtx``, version 7, ``#pragma pack(1)``)::

    FileHeader_t (36 B): version, vertCacheSize, maxBonesPerStrip u16, maxBonesPerTri u16,
                         maxBonesPerVert, checkSum, numLODs, materialReplacementListOffset,
                         numBodyParts, bodyPartOffset
    BodyPartHeader_t  (8 B): numModels, modelOffset (rel)
    ModelHeader_t     (8 B): numLODs, lodOffset (rel)
    ModelLODHeader_t (12 B): numMeshes, meshOffset (rel), switchPoint f32
    MeshHeader_t      (9 B): numStripGroups, stripGroupHeaderOffset (rel), flags u8
    StripGroupHeader_t (25 B, 33 B for MDL v49+): numVerts, vertOffset (rel),
                         numIndices, indexOffset (rel), numStrips, stripOffset (rel),
                         flags u8 [, numTopologyIndices, topologyOffset]
    Vertex_t          (9 B): boneWeightIndex[3] u8, numBones u8, origMeshVertID u16, boneID[3] i8
    indices           u16, a triangle list over the strip group's Vertex_t array

    Every strip in a modern VTX is a triangle list, so the whole index array of a
    strip group is used and the strip headers (whose size also varies by version)
    are not needed. VTX meshes correspond 1:1 to MDL meshes; the vertex of a
    triangle corner is ``model_first_vertex + mesh.vertexoffset + origMeshVertID``.

PHY::

    phyheader_t (16 B): size (16), id, solidCount, checkSum
    per solid: int32 byte size, then either
      "VPHY" header (28 B): id, version u16, modelType u16, surfaceSize, dragAxisAreas[3], axisMapSize
      followed by an IVP_Compact_Surface, or (old files) the compact surface directly.
    then a KeyValues text block (``solid { "index" .. "mass" .. }``).

    IVP_Compact_Surface (48 B): mass_center[3], rotation_inertia[3], upper_limit_radius,
        max_deviation:8|byte_size:24, offset_ledgetree_root (rel), dummy[3]
    IVP_Compact_Ledgetree_Node (28 B): offset_right_node (rel, 0 = leaf),
        offset_compact_ledge (rel), center[3], radius, box_sizes[3], free
        (the left child immediately follows its parent)
    IVP_Compact_Ledge (16 B): c_point_offset (rel), client_data,
        flags:2|is_compact:2|dummy:4|size_div_16:24, n_triangles i16, for_future_use i16
    IVP_Compact_Triangle (16 B): indices u32, then 3 edges u32 whose low 16 bits
        are the start point index into the ledge's point array
    IVP_Compact_Poly_Point (16 B): x, y, z, pad (metres, IVP axes)

    IVP to Source units: ``(x, z, -y) / 0.0254`` (vphysics ``ConvertPositionToHL``).
    Each leaf ledge is one convex piece.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .mdl import MDLInfo, read_mdl

METERS_PER_INCH = 0.0254

VVD_VERTEX = np.dtype([("weight", "<f4", 3), ("bone", "u1", 3), ("numbones", "u1"),
                       ("pos", "<f4", 3), ("normal", "<f4", 3), ("uv", "<f4", 2)])
VTX_VERTEX = np.dtype([("bwi", "u1", 3), ("numbones", "u1"), ("orig", "<u2"), ("bone", "i1", 3)])
assert VVD_VERTEX.itemsize == 48 and VTX_VERTEX.itemsize == 9


class StudioError(ValueError):
    pass


@dataclass
class StudioMesh:
    """One MDL mesh at LOD 0: triangles over its own vertex arrays."""
    bodypart: int
    model: int
    mesh: int
    skinref: int               # mstudiomesh_t.material (index into the skin family)
    positions: np.ndarray      # (n, 3) float32, model space
    normals: np.ndarray        # (n, 3) float32
    uvs: np.ndarray            # (n, 2) float32, Source/DirectX convention (v = 0 at the image top)
    triangles: np.ndarray      # (m, 3) int32, counter-clockwise seen from the front (Source winding)


@dataclass
class StudioModel:
    info: MDLInfo
    meshes: list[StudioMesh]
    bodyparts: list[tuple[str, list[str]]] = field(default_factory=list)  # (name, [submodel names])

    def material_for(self, skinref: int, skin: int = 0) -> int:
        """Texture index (into ``info.materials``) for a mesh's skin reference."""
        fams = self.info.skins
        if fams:
            fam = fams[skin] if 0 <= skin < len(fams) else fams[0]
            if 0 <= skinref < len(fam):
                return fam[skinref]
        return skinref


def _cstr(data: bytes, ofs: int) -> str:
    if ofs <= 0 or ofs >= len(data):
        return ""
    end = data.find(b"\0", ofs)
    return data[ofs:end if end >= 0 else len(data)].decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# VVD


def read_vvd(data: bytes) -> np.ndarray:
    """LOD-0 vertex array (structured ``VVD_VERTEX``) with fixups applied."""
    if data[:4] != b"IDSV":
        raise StudioError("not a VVD (IDSV) file")
    num_lods = struct.unpack_from("<i", data, 12)[0]
    lod_verts = struct.unpack_from("<8i", data, 16)
    num_fixups, fixup_start, vert_start = struct.unpack_from("<3i", data, 48)
    total = lod_verts[0]
    raw = np.frombuffer(data, VVD_VERTEX, count=total, offset=vert_start)
    if num_fixups <= 0:
        return raw
    parts = []
    for i in range(num_fixups):
        lod, src, count = struct.unpack_from("<3i", data, fixup_start + 12 * i)
        if lod >= 0:  # root LOD 0 keeps every fixup whose lod >= 0
            parts.append(raw[src : src + count] if src + count <= total else
                         np.frombuffer(data, VVD_VERTEX, count=count, offset=vert_start + 48 * src))
    del num_lods
    return np.concatenate(parts) if parts else raw


# ---------------------------------------------------------------------------
# VTX


def _vtx_mesh_triangles(vtx: bytes, mesh_ofs: int, sg_size: int, mesh_nverts: int) -> Optional[list[np.ndarray]]:
    """Triangles of one VTX mesh as mesh-local vertex ids, or ``None`` if the layout is implausible."""
    n_groups, groups_ofs = struct.unpack_from("<ii", vtx, mesh_ofs)
    out = []
    for g in range(n_groups):
        sg = mesh_ofs + groups_ofs + g * sg_size
        if sg < 0 or sg + 25 > len(vtx):
            return None
        nverts, vofs, nidx, iofs, nstrips, sofs = struct.unpack_from("<6i", vtx, sg)
        flags = vtx[sg + 24]
        if nverts < 0 or nidx < 0 or nidx % 3 or flags > 0x0F:
            return None
        if sg + vofs + nverts * 9 > len(vtx) or sg + iofs + nidx * 2 > len(vtx) or vofs < 0 or iofs < 0:
            return None
        if nidx == 0:
            continue
        verts = np.frombuffer(vtx, VTX_VERTEX, count=nverts, offset=sg + vofs)
        idx = np.frombuffer(vtx, "<u2", count=nidx, offset=sg + iofs).astype(np.int64)
        if idx.max() >= nverts:
            return None
        orig = verts["orig"].astype(np.int64)
        if nverts and orig.max() >= max(1, mesh_nverts):
            return None
        out.append(orig[idx].reshape(-1, 3))
    return out


def read_studio_model(mdl: bytes, vvd: bytes, vtx: bytes, lod: int = 0,
                      body: Optional[list[int]] = None) -> StudioModel:
    """Meshes of submodel ``body[i]`` (default 0) of every body part at ``lod``."""
    info = read_mdl(mdl, vvd)
    verts = read_vvd(vvd)
    nbody, bodyidx = struct.unpack_from("<ii", mdl, 232)
    if vtx[:4] != struct.pack("<i", 7):
        raise StudioError(f"unsupported VTX version {struct.unpack_from('<i', vtx, 0)[0]}")
    vtx_nbody, vtx_bodyofs = struct.unpack_from("<ii", vtx, 28)
    if vtx_nbody != nbody:
        raise StudioError(f"VTX has {vtx_nbody} body parts, MDL {nbody}")
    sg_sizes = (33, 25) if info.version >= 49 else (25, 33)

    meshes: list[StudioMesh] = []
    bodyparts = []
    for bp in range(nbody):
        bpo = bodyidx + 16 * bp
        bp_name_ofs, nmodels, _base, modelidx = struct.unpack_from("<4i", mdl, bpo)
        models_names = []
        for mi in range(nmodels):
            mo = bpo + modelidx + 148 * mi
            models_names.append(mdl[mo : mo + 64].split(b"\0", 1)[0].decode("utf-8", "replace"))
        bodyparts.append((_cstr(mdl, bpo + bp_name_ofs), models_names))
        pick = (body[bp] if body and bp < len(body) else 0)
        if not 0 <= pick < nmodels:
            continue
        mo = bpo + modelidx + 148 * pick
        (nmeshes, meshidx, nmverts, vertexindex) = struct.unpack_from("<4i", mdl, mo + 72)
        first = vertexindex // 48
        # VTX side
        vbp = vtx_bodyofs + 8 * bp
        vnm, vmofs = struct.unpack_from("<ii", vtx, vbp)
        if pick >= vnm:
            continue
        vmo = vbp + vmofs + 8 * pick
        vnlods, vlodofs = struct.unpack_from("<ii", vtx, vmo)
        use_lod = min(lod, vnlods - 1)
        if use_lod < 0:
            continue
        vlo = vmo + vlodofs + 12 * use_lod
        vnmesh, vmeshofs = struct.unpack_from("<ii", vtx, vlo)
        for me in range(min(nmeshes, vnmesh)):
            meo = mo + meshidx + 116 * me
            skinref, _modelindex, mesh_nverts, vertexoffset = struct.unpack_from("<4i", mdl, meo)
            vmesh = vlo + vmeshofs + 9 * me
            tris = None
            for sgs in sg_sizes:
                tris = _vtx_mesh_triangles(vtx, vmesh, sgs, mesh_nverts)
                if tris is not None:
                    break
            if not tris:
                continue
            local = np.concatenate(tris)
            used, inv = np.unique(local.reshape(-1), return_inverse=True)
            src = first + vertexoffset + used
            if src.max() >= len(verts):
                raise StudioError(f"mesh {bp}/{pick}/{me} references vertex {src.max()} of {len(verts)}")
            v = verts[src]
            # Source front faces are clockwise in DirectX terms; flip to CCW for OpenGL-style consumers.
            t = inv.reshape(-1, 3).astype(np.int32)[:, [0, 2, 1]]
            meshes.append(StudioMesh(bp, pick, me, skinref, v["pos"].astype(np.float32),
                                     v["normal"].astype(np.float32), v["uv"].astype(np.float32), t))
    return StudioModel(info, meshes, bodyparts)


VTX_SUFFIXES = (".dx90.vtx", ".vtx", ".dx80.vtx", ".sw.vtx")


def load_studio_model(fs, mdl_path: str, lod: int = 0, body: Optional[list[int]] = None) -> StudioModel:
    """Read ``models/....mdl`` and its ``.vvd``/``.vtx`` from a file source (``try_read``)."""
    mdl = fs.try_read(mdl_path)
    if mdl is None:
        raise KeyError(mdl_path)
    base = os.path.splitext(mdl_path)[0]
    vvd = fs.try_read(base + ".vvd")
    if vvd is None:
        raise KeyError(base + ".vvd")
    vtx = None
    for suf in VTX_SUFFIXES:
        vtx = fs.try_read(base + suf)
        if vtx is not None:
            break
    if vtx is None:
        raise KeyError(base + ".dx90.vtx")
    return read_studio_model(mdl, vvd, vtx, lod, body)


# ---------------------------------------------------------------------------
# PHY


@dataclass
class PhySolid:
    index: int
    pieces: list[np.ndarray]           # convex pieces: (n, 3) float64 points in Source units
    triangles: list[np.ndarray]        # per piece (m, 3) indices into its points (hull faces)


@dataclass
class PhyModel:
    solids: list[PhySolid]
    keyvalues: str = ""

    @property
    def pieces(self) -> list[np.ndarray]:
        return [p for s in self.solids for p in s.pieces]

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        pts = np.concatenate(self.pieces) if self.pieces else np.zeros((1, 3))
        return pts.min(0), pts.max(0)


def _ivp_to_source(p: np.ndarray) -> np.ndarray:
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], axis=1) / METERS_PER_INCH


def _read_ledge(data: bytes, lo: int) -> Optional[tuple[np.ndarray, np.ndarray]]:
    if lo < 0 or lo + 16 > len(data):
        return None
    point_ofs, _client, bits, ntri = struct.unpack_from("<iiIh", data, lo)
    if ntri <= 0 or ntri > 65535:
        return None
    tris = np.frombuffer(data, "<u4", count=4 * ntri, offset=lo + 16).reshape(ntri, 4)
    idx = (tris[:, 1:4] & 0xFFFF).astype(np.int64)
    npts = int(idx.max()) + 1
    po = lo + point_ofs
    if po < 0 or po + 16 * npts > len(data):
        return None
    pts = np.frombuffer(data, "<f4", count=4 * npts, offset=po).reshape(npts, 4)[:, :3].astype(np.float64)
    used, inv = np.unique(idx.reshape(-1), return_inverse=True)
    return _ivp_to_source(pts[used]), inv.reshape(-1, 3)


def _walk_ledgetree(data: bytes, node: int, out: list, depth: int = 0) -> None:
    if depth > 64 or node < 0 or node + 28 > len(data):
        return
    right, ledge = struct.unpack_from("<ii", data, node)
    if right == 0:
        r = _read_ledge(data, node + ledge)
        if r is not None:
            out.append(r)
        return
    _walk_ledgetree(data, node + 28, out, depth + 1)
    _walk_ledgetree(data, node + right, out, depth + 1)


def read_phy(data: bytes) -> PhyModel:
    hsize, _id, nsolids, _crc = struct.unpack_from("<4i", data, 0)
    pos = hsize
    solids = []
    for s in range(nsolids):
        size = struct.unpack_from("<i", data, pos)[0]
        start = pos + 4
        surf = start
        if data[start : start + 4] == b"VPHY":
            _vid, _ver, model_type = struct.unpack_from("<4sHH", data, start)
            surf = start + 28
            if model_type != 0:  # 0 = compact surface; 1 = MOPP (unsupported, not used by props)
                solids.append(PhySolid(s, [], []))
                pos = start + size
                continue
        root_ofs = struct.unpack_from("<i", data, surf + 32)[0]
        found: list[tuple[np.ndarray, np.ndarray]] = []
        if root_ofs > 0:
            _walk_ledgetree(data[surf : start + size], root_ofs, found)
        solids.append(PhySolid(s, [p for p, _ in found], [t for _, t in found]))
        pos = start + size
    kv = data[pos:].split(b"\0", 1)[0].decode("latin-1", "replace")
    return PhyModel(solids, kv)


def load_phy(fs, mdl_path: str) -> Optional[PhyModel]:
    data = fs.try_read(os.path.splitext(mdl_path)[0] + ".phy")
    return None if data is None else read_phy(data)
