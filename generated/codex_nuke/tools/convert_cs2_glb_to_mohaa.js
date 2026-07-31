#!/usr/bin/env node
"use strict";

/*
 * Convert a ValveResourceFormat GLB export into the retail-compatible
 * MOHAA static-model trio:
 *
 *   model.skd  - SKD version 5, one POSROT root bone
 *   model.skc  - SKC version 13, one identity frame
 *   model.tik  - surface-to-shader bindings and idle animation
 *
 * The converter intentionally depends only on Node's standard library.
 * It does not extract Source 2 resources and it never writes into the
 * repository unless the caller explicitly chooses a repository path.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SKD_IDENT = 0x444d4b53; // "SKMD"
const SKD_VERSION = 5;
const SKD_SURFACE_IDENT = 0x204c4b53; // "SKL "
const SKC_IDENT = 0x4e414b53; // "SKAN"
const SKC_VERSION = 13;
const MAX_SURFACE_VERTICES = 999;
const MAX_SURFACE_TRIANGLES = 1999;
const MAX_TIKI_SURFACES = 24;
const VRF_METERS_PER_SOURCE_UNIT = 0.025399996;

function fail(message) {
  throw new Error(message);
}

function parseArguments(argv) {
  const options = {
    inputs: [],
    coordinateSystem: "vrf-source2",
    scale: 1,
    flipV: false,
    fallbackShader: "textures/codex_nuke/control_panel",
    shaderPrefix: "",
    modelPath: "",
    recenterBounds: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    const take = () => {
      if (i + 1 >= argv.length) fail(`Missing value after ${token}`);
      i += 1;
      return argv[i];
    };

    switch (token) {
      case "--input":
      case "-i":
        options.inputs.push(take());
        break;
      case "--output":
      case "-o":
        options.output = take();
        break;
      case "--name":
        options.name = take();
        break;
      case "--model-path":
        options.modelPath = take();
        break;
      case "--shader-prefix":
        options.shaderPrefix = take();
        break;
      case "--fallback-shader":
        options.fallbackShader = take();
        break;
      case "--coordinate-system":
        options.coordinateSystem = take();
        break;
      case "--scale":
        options.scale = Number(take());
        break;
      case "--flip-v":
        options.flipV = true;
        break;
      case "--recenter-bounds":
        options.recenterBounds = true;
        break;
      case "--help":
      case "-h":
        options.help = true;
        break;
      default:
        fail(`Unknown option: ${token}`);
    }
  }

  if (options.help) return options;
  if (!options.inputs.length) fail("At least one --input is required");
  if (!options.output) fail("--output is required");
  if (!Number.isFinite(options.scale) || options.scale <= 0) {
    fail("--scale must be a positive finite number");
  }
  if (!["vrf-source2", "gltf"].includes(options.coordinateSystem)) {
    fail("--coordinate-system must be vrf-source2 or gltf");
  }
  return options;
}

function usage() {
  return `Usage:
  node convert_cs2_glb_to_mohaa.js --input model.glb [--input model2.glb ...] --output output-dir [options]

Options:
  --input FILE                Repeat to merge related GLBs into one MOHAA model
  --name NAME                 Output/model name derived from the first GLB by default
  --model-path QPATH          TIKI data path; defaults to models/codex_nuke/source2/NAME
  --shader-prefix QPATH       Use one direct texture shader per GLB material
  --fallback-shader QPATH     Shader used when --shader-prefix is absent
  --coordinate-system MODE   vrf-source2 (default) or gltf
  --scale NUMBER              Additional MOHAA scale after coordinate conversion
  --flip-v                    Replace each texture V coordinate with 1-V
  --recenter-bounds           Center model vertices and report placement origin

The vrf-source2 mode reverses VRF's Source-units/Z-up to glTF-meters/Y-up
scene transform after applying the complete glTF node hierarchy. This keeps
map-embedded aggregate vertices in Source/MOHAA world units.`;
}

function sanitizeName(value, fallback = "model") {
  const cleaned = String(value || "")
    .toLowerCase()
    .replace(/\.[^.]+$/, "")
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_");
  return (cleaned || fallback).slice(0, 48);
}

function qpath(value) {
  return String(value).replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
}

function writeFixedAscii(buffer, offset, length, value) {
  const encoded = Buffer.from(String(value), "ascii");
  encoded.copy(buffer, offset, 0, Math.min(encoded.length, length - 1));
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function align4(value) {
  return (value + 3) & ~3;
}

function parseGlb(filename) {
  const file = fs.readFileSync(filename);
  if (file.length < 20 || file.toString("ascii", 0, 4) !== "glTF") {
    fail(`${filename} is not a GLB file`);
  }
  if (file.readUInt32LE(4) !== 2) fail("Only GLB version 2 is supported");
  if (file.readUInt32LE(8) !== file.length) {
    fail("GLB header length does not match file length");
  }

  let json = null;
  let binary = null;
  let cursor = 12;
  while (cursor + 8 <= file.length) {
    const chunkLength = file.readUInt32LE(cursor);
    const chunkType = file.readUInt32LE(cursor + 4);
    const start = cursor + 8;
    const end = start + chunkLength;
    if (end > file.length) fail("GLB chunk extends past end of file");
    if (chunkType === 0x4e4f534a) {
      json = JSON.parse(file.subarray(start, end).toString("utf8"));
    } else if (chunkType === 0x004e4942) {
      binary = file.subarray(start, end);
    }
    cursor = end;
  }

  if (!json) fail("GLB has no JSON chunk");
  if (!binary) fail("GLB has no BIN chunk");
  if ((json.buffers || []).length !== 1) {
    fail("Only a single embedded GLB buffer is supported");
  }
  return { file, json, binary };
}

const COMPONENTS_PER_TYPE = {
  SCALAR: 1,
  VEC2: 2,
  VEC3: 3,
  VEC4: 4,
  MAT2: 4,
  MAT3: 9,
  MAT4: 16,
};

const COMPONENT_INFO = {
  5120: { bytes: 1, read: "readInt8", signed: true, max: 127 },
  5121: { bytes: 1, read: "readUInt8", signed: false, max: 255 },
  5122: { bytes: 2, read: "readInt16LE", signed: true, max: 32767 },
  5123: { bytes: 2, read: "readUInt16LE", signed: false, max: 65535 },
  5125: { bytes: 4, read: "readUInt32LE", signed: false, max: 4294967295 },
  5126: { bytes: 4, read: "readFloatLE", float: true },
};

function accessorReader(gltf, binary, accessorIndex) {
  const accessor = gltf.accessors?.[accessorIndex];
  if (!accessor) fail(`Missing accessor ${accessorIndex}`);
  if (accessor.sparse) fail(`Sparse accessor ${accessorIndex} is not supported`);
  const view = gltf.bufferViews?.[accessor.bufferView];
  if (!view) fail(`Accessor ${accessorIndex} has no buffer view`);
  if ((view.buffer || 0) !== 0) fail("Only GLB buffer 0 is supported");
  const info = COMPONENT_INFO[accessor.componentType];
  const components = COMPONENTS_PER_TYPE[accessor.type];
  if (!info || !components) {
    fail(`Unsupported accessor ${accessorIndex} component/type combination`);
  }
  const packedStride = info.bytes * components;
  const stride = view.byteStride || packedStride;
  if (stride < packedStride) fail(`Accessor ${accessorIndex} has an invalid stride`);
  const base = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const required =
    accessor.count === 0 ? base : base + stride * (accessor.count - 1) + packedStride;
  if (required > binary.length) fail(`Accessor ${accessorIndex} exceeds the BIN chunk`);

  const read = (index) => {
    if (index < 0 || index >= accessor.count) fail("Accessor index out of range");
    const values = [];
    const elementOffset = base + index * stride;
    for (let component = 0; component < components; component += 1) {
      let value = binary[info.read](elementOffset + component * info.bytes);
      if (accessor.normalized && !info.float) {
        value = info.signed ? Math.max(value / info.max, -1) : value / info.max;
      }
      values.push(value);
    }
    return values;
  };

  return { accessor, read };
}

function identity4() {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

function multiply4(a, b) {
  const out = new Array(16).fill(0);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      for (let k = 0; k < 4; k += 1) {
        out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
      }
    }
  }
  return out;
}

function matrixFromNode(node) {
  if (node.matrix) {
    if (node.matrix.length !== 16) fail("glTF node matrix must have 16 values");
    return node.matrix.map(Number);
  }
  const translation = node.translation || [0, 0, 0];
  const rotation = node.rotation || [0, 0, 0, 1];
  const scale = node.scale || [1, 1, 1];
  const [x, y, z, w] = rotation;
  const xx = x * x;
  const yy = y * y;
  const zz = z * z;
  const xy = x * y;
  const xz = x * z;
  const yz = y * z;
  const wx = w * x;
  const wy = w * y;
  const wz = w * z;

  return [
    (1 - 2 * (yy + zz)) * scale[0],
    (2 * (xy + wz)) * scale[0],
    (2 * (xz - wy)) * scale[0],
    0,
    (2 * (xy - wz)) * scale[1],
    (1 - 2 * (xx + zz)) * scale[1],
    (2 * (yz + wx)) * scale[1],
    0,
    (2 * (xz + wy)) * scale[2],
    (2 * (yz - wx)) * scale[2],
    (1 - 2 * (xx + yy)) * scale[2],
    0,
    translation[0],
    translation[1],
    translation[2],
    1,
  ];
}

function transformPoint(matrix, point) {
  const [x, y, z] = point;
  const w =
    matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
  const divisor = w && w !== 1 ? w : 1;
  return [
    (matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]) / divisor,
    (matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]) / divisor,
    (matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]) / divisor,
  ];
}

function inverseTranspose3(matrix) {
  const a00 = matrix[0];
  const a01 = matrix[4];
  const a02 = matrix[8];
  const a10 = matrix[1];
  const a11 = matrix[5];
  const a12 = matrix[9];
  const a20 = matrix[2];
  const a21 = matrix[6];
  const a22 = matrix[10];
  const b01 = a22 * a11 - a12 * a21;
  const b11 = -a22 * a10 + a12 * a20;
  const b21 = a21 * a10 - a11 * a20;
  const determinant = a00 * b01 + a01 * b11 + a02 * b21;
  if (Math.abs(determinant) < 1e-20) fail("glTF node transform is singular");
  const inverseDeterminant = 1 / determinant;
  const inverse = [
    b01 * inverseDeterminant,
    (-a22 * a01 + a02 * a21) * inverseDeterminant,
    (a12 * a01 - a02 * a11) * inverseDeterminant,
    b11 * inverseDeterminant,
    (a22 * a00 - a02 * a20) * inverseDeterminant,
    (-a12 * a00 + a02 * a10) * inverseDeterminant,
    b21 * inverseDeterminant,
    (-a21 * a00 + a01 * a20) * inverseDeterminant,
    (a11 * a00 - a01 * a10) * inverseDeterminant,
  ];
  // Return inverse-transpose in column-major order.
  return [
    inverse[0],
    inverse[3],
    inverse[6],
    inverse[1],
    inverse[4],
    inverse[7],
    inverse[2],
    inverse[5],
    inverse[8],
  ];
}

function transformDirection(matrix3, direction) {
  const [x, y, z] = direction;
  return [
    matrix3[0] * x + matrix3[3] * y + matrix3[6] * z,
    matrix3[1] * x + matrix3[4] * y + matrix3[7] * z,
    matrix3[2] * x + matrix3[5] * y + matrix3[8] * z,
  ];
}

function normalize(vector) {
  const length = Math.hypot(...vector);
  return length > 1e-20 ? vector.map((value) => value / length) : [0, 0, 1];
}

function convertCoordinate(vector, mode, scale) {
  if (mode === "vrf-source2") {
    return [
      (vector[2] / VRF_METERS_PER_SOURCE_UNIT) * scale,
      (vector[0] / VRF_METERS_PER_SOURCE_UNIT) * scale,
      (vector[1] / VRF_METERS_PER_SOURCE_UNIT) * scale,
    ];
  }
  return vector.map((value) => value * scale);
}

function convertNormalCoordinate(vector, mode) {
  return mode === "vrf-source2"
    ? normalize([vector[2], vector[0], vector[1]])
    : normalize(vector);
}

function materialRecord(gltf, materialIndex, sourceIndex) {
  const material = gltf.materials?.[materialIndex] || {};
  const baseTextureIndex =
    material.pbrMetallicRoughness?.baseColorTexture?.index;
  const texture =
    baseTextureIndex === undefined ? null : gltf.textures?.[baseTextureIndex];
  const image = texture ? gltf.images?.[texture.source] : null;
  const vmat = material.extras?.vmat;
  return {
    index: materialIndex ?? null,
    name: material.name || `material_${materialIndex ?? "none"}`,
    vmat: vmat?.Name || null,
    shaderName: vmat?.ShaderName || null,
    baseColorImage: image?.uri || null,
    alphaMode: material.alphaMode || "OPAQUE",
    doubleSided: Boolean(material.doubleSided),
    sourceIndex,
  };
}

function collectTriangles(glb, options, sourceIndex) {
  const { json: gltf, binary } = glb;
  const primitives = [];
  const sceneIndex = gltf.scene ?? 0;
  const scene = gltf.scenes?.[sceneIndex];
  if (!scene) fail(`Missing glTF scene ${sceneIndex}`);

  const visit = (nodeIndex, parentMatrix) => {
    const node = gltf.nodes?.[nodeIndex];
    if (!node) fail(`Missing glTF node ${nodeIndex}`);
    const world = multiply4(parentMatrix, matrixFromNode(node));
    if (node.mesh !== undefined) {
      const mesh = gltf.meshes?.[node.mesh];
      if (!mesh) fail(`Missing glTF mesh ${node.mesh}`);
      const normalMatrix = inverseTranspose3(world);

      for (let primitiveIndex = 0; primitiveIndex < mesh.primitives.length; primitiveIndex += 1) {
        const primitive = mesh.primitives[primitiveIndex];
        const mode = primitive.mode ?? 4;
        if (mode !== 4) fail(`Primitive mode ${mode} is not TRIANGLES`);
        if (primitive.indices === undefined) {
          fail("Non-indexed glTF primitives are not supported");
        }
        const positionAccessor = accessorReader(
          gltf,
          binary,
          primitive.attributes?.POSITION,
        );
        const normalAccessor =
          primitive.attributes?.NORMAL === undefined
            ? null
            : accessorReader(gltf, binary, primitive.attributes.NORMAL);
        const uvAccessor =
          primitive.attributes?.TEXCOORD_0 === undefined
            ? null
            : accessorReader(gltf, binary, primitive.attributes.TEXCOORD_0);
        const indexAccessor = accessorReader(gltf, binary, primitive.indices);
        if (indexAccessor.accessor.type !== "SCALAR") {
          fail("Index accessor must be SCALAR");
        }
        if (indexAccessor.accessor.count % 3 !== 0) {
          fail("Triangle index count must be divisible by three");
        }

        const vertices = new Array(positionAccessor.accessor.count);
        for (let index = 0; index < vertices.length; index += 1) {
          const gltfPosition = transformPoint(world, positionAccessor.read(index));
          const position = convertCoordinate(
            gltfPosition,
            options.coordinateSystem,
            options.scale,
          );
          const gltfNormal = normalAccessor
            ? transformDirection(normalMatrix, normalAccessor.read(index))
            : [0, 0, 0];
          const normal = normalAccessor
            ? convertNormalCoordinate(gltfNormal, options.coordinateSystem)
            : [0, 0, 0];
          const sourceUv = uvAccessor ? uvAccessor.read(index) : [0, 0];
          vertices[index] = {
            position,
            normal,
            uv: [sourceUv[0], options.flipV ? 1 - sourceUv[1] : sourceUv[1]],
          };
        }

        const indices = [];
        for (let index = 0; index < indexAccessor.accessor.count; index += 1) {
          const vertexIndex = indexAccessor.read(index)[0];
          if (vertexIndex >= vertices.length) {
            fail(`Primitive index ${vertexIndex} exceeds vertex count`);
          }
          indices.push(vertexIndex);
        }

        if (!normalAccessor) generateNormals(vertices, indices);
        primitives.push({
          nodeIndex,
          nodeName: node.name || `node_${nodeIndex}`,
          meshIndex: node.mesh,
          meshName: mesh.name || `mesh_${node.mesh}`,
          primitiveIndex,
          material: materialRecord(gltf, primitive.material, sourceIndex),
          vertices,
          indices,
        });
      }
    }
    for (const child of node.children || []) visit(child, world);
  };

  for (const rootNode of scene.nodes || []) visit(rootNode, identity4());
  if (!primitives.length) fail("The selected scene contains no triangle primitives");
  return primitives;
}

function generateNormals(vertices, indices) {
  const accumulated = vertices.map(() => [0, 0, 0]);
  for (let index = 0; index < indices.length; index += 3) {
    const a = vertices[indices[index]].position;
    const b = vertices[indices[index + 1]].position;
    const c = vertices[indices[index + 2]].position;
    const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const ac = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const face = [
      ab[1] * ac[2] - ab[2] * ac[1],
      ab[2] * ac[0] - ab[0] * ac[2],
      ab[0] * ac[1] - ab[1] * ac[0],
    ];
    for (let corner = 0; corner < 3; corner += 1) {
      const target = accumulated[indices[index + corner]];
      target[0] += face[0];
      target[1] += face[1];
      target[2] += face[2];
    }
  }
  for (let index = 0; index < vertices.length; index += 1) {
    vertices[index].normal = normalize(accumulated[index]);
  }
}

function vertexKey(vertex) {
  return [...vertex.position, ...vertex.normal, ...vertex.uv]
    .map((value) => (Object.is(value, -0) ? "0" : Number(value).toString()))
    .join("|");
}

function splitPrimitives(primitives) {
  const surfaces = [];
  for (const primitive of primitives) {
    let localVertices = [];
    let localIndices = [];
    let remap = new Map();
    let sequence = 0;

    const flush = () => {
      if (!localIndices.length) return;
      surfaces.push({
        material: primitive.material,
        source: {
          nodeIndex: primitive.nodeIndex,
          nodeName: primitive.nodeName,
          meshIndex: primitive.meshIndex,
          meshName: primitive.meshName,
          primitiveIndex: primitive.primitiveIndex,
        },
        sequence,
        vertices: localVertices,
        indices: localIndices,
      });
      sequence += 1;
      localVertices = [];
      localIndices = [];
      remap = new Map();
    };

    for (let index = 0; index < primitive.indices.length; index += 3) {
      const triangle = primitive.indices.slice(index, index + 3);
      const triangleVertices = triangle.map(
        (vertexIndex) => primitive.vertices[vertexIndex],
      );
      const triangleKeys = triangleVertices.map(vertexKey);
      const newVertexCount = new Set(
        triangleKeys.filter((key) => !remap.has(key)),
      ).size;
      const triangleCount = localIndices.length / 3;
      if (
        localIndices.length &&
        (localVertices.length + newVertexCount > MAX_SURFACE_VERTICES ||
          triangleCount + 1 > MAX_SURFACE_TRIANGLES)
      ) {
        flush();
      }

      for (let corner = 0; corner < triangle.length; corner += 1) {
        const key = triangleKeys[corner];
        if (!remap.has(key)) {
          remap.set(key, localVertices.length);
          localVertices.push(triangleVertices[corner]);
        }
        localIndices.push(remap.get(key));
      }
    }
    flush();
  }

  for (let index = 0; index < surfaces.length; index += 1) {
    const surface = surfaces[index];
    // The retail TIKI setup parser corrupts 32-character surface identifiers
    // even though the SKD field itself is 64 bytes. Keep the shared identifier
    // at 28 characters or fewer.
    const materialSlug = sanitizeName(surface.material.name, "material").slice(
      0,
      24,
    );
    surface.name = `${materialSlug}_${String(index).padStart(3, "0")}`;
  }
  return surfaces;
}

function calculateBounds(surfaces) {
  const minimum = [Infinity, Infinity, Infinity];
  const maximum = [-Infinity, -Infinity, -Infinity];
  let radius = 0;
  for (const surface of surfaces) {
    for (const vertex of surface.vertices) {
      for (let axis = 0; axis < 3; axis += 1) {
        minimum[axis] = Math.min(minimum[axis], vertex.position[axis]);
        maximum[axis] = Math.max(maximum[axis], vertex.position[axis]);
      }
      radius = Math.max(radius, Math.hypot(...vertex.position));
    }
  }
  return { minimum, maximum, radius };
}

function calculatePrimitiveBounds(primitives) {
  return calculateBounds(
    primitives.map((primitive) => ({ vertices: primitive.vertices })),
  );
}

function buildBone() {
  const rotationChannel = Buffer.from("ORIGIN rot\0", "ascii");
  const positionChannel = Buffer.from("ORIGIN pos\0", "ascii");
  const headerSize = 84;
  const valuesSize = 12;
  const bone = Buffer.alloc(
    headerSize + valuesSize + rotationChannel.length + positionChannel.length,
  );
  writeFixedAscii(bone, 0, 32, "ORIGIN");
  writeFixedAscii(bone, 32, 32, "worldbone");
  bone.writeInt32LE(1, 64); // SKELBONE_POSROT / JT_POSROT_SKC
  bone.writeInt32LE(headerSize, 68);
  bone.writeInt32LE(headerSize + valuesSize, 72);
  bone.writeInt32LE(bone.length, 76);
  bone.writeInt32LE(bone.length, 80);
  bone.writeFloatLE(1, 84);
  bone.writeFloatLE(1, 88);
  bone.writeFloatLE(1, 92);
  rotationChannel.copy(bone, 96);
  positionChannel.copy(bone, 96 + rotationChannel.length);
  return bone;
}

function buildSurface(surface) {
  const headerSize = 100;
  const triangleBytes = surface.indices.length * 4;
  const vertexBytes = surface.vertices.length * (28 + 20);
  // Retail-authored SKDs carry two int32 arrays after the variable-length
  // vertex records. Their entries may all be zero when no progressive LOD
  // collapse data is authored, but original Q3map still dereferences the
  // offsets while processing a static model.
  const collapseBytes = surface.vertices.length * 4;
  const result = Buffer.alloc(
    headerSize + triangleBytes + vertexBytes + collapseBytes * 2,
  );
  result.writeUInt32LE(SKD_SURFACE_IDENT, 0);
  writeFixedAscii(result, 4, 64, surface.name);
  result.writeInt32LE(surface.indices.length / 3, 68);
  result.writeInt32LE(surface.vertices.length, 72);
  result.writeInt32LE(0, 76);
  result.writeInt32LE(headerSize, 80);
  result.writeInt32LE(headerSize + triangleBytes, 84);
  result.writeInt32LE(headerSize + triangleBytes + vertexBytes, 88);
  result.writeInt32LE(result.length, 92);
  result.writeInt32LE(
    headerSize + triangleBytes + vertexBytes + collapseBytes,
    96,
  );

  let cursor = headerSize;
  for (const index of surface.indices) {
    result.writeUInt32LE(index, cursor);
    cursor += 4;
  }
  for (const vertex of surface.vertices) {
    for (const value of vertex.normal) {
      result.writeFloatLE(value, cursor);
      cursor += 4;
    }
    result.writeFloatLE(vertex.uv[0], cursor);
    result.writeFloatLE(vertex.uv[1], cursor + 4);
    cursor += 8;
    result.writeInt32LE(1, cursor);
    result.writeInt32LE(0, cursor + 4);
    cursor += 8;
    result.writeInt32LE(0, cursor); // root bone
    result.writeFloatLE(1, cursor + 4);
    result.writeFloatLE(vertex.position[0], cursor + 8);
    result.writeFloatLE(vertex.position[1], cursor + 12);
    result.writeFloatLE(vertex.position[2], cursor + 16);
    cursor += 20;
  }
  // The allocated buffer is zero-filled, which is the no-collapse retail
  // representation seen in known-working static props.
  cursor += collapseBytes * 2;
  if (cursor !== result.length) fail("Internal SKD surface size mismatch");
  return result;
}

function buildSkd(modelName, surfaces) {
  const headerSize = 148;
  const bone = buildBone();
  const surfaceBuffers = surfaces.map(buildSurface);
  const totalSize =
    headerSize +
    bone.length +
    surfaceBuffers.reduce((sum, buffer) => sum + buffer.length, 0);
  const result = Buffer.alloc(totalSize);
  result.writeUInt32LE(SKD_IDENT, 0);
  result.writeInt32LE(SKD_VERSION, 4);
  writeFixedAscii(result, 8, 64, `${modelName}.skd`);
  result.writeInt32LE(surfaces.length, 72);
  result.writeInt32LE(1, 76);
  result.writeInt32LE(headerSize, 80);
  result.writeInt32LE(headerSize + bone.length, 84);
  result.writeInt32LE(totalSize, 88);
  result.writeInt32LE(0, 132);
  result.writeInt32LE(totalSize, 136);
  result.writeInt32LE(0, 140);
  result.writeInt32LE(totalSize, 144);

  let cursor = headerSize;
  bone.copy(result, cursor);
  cursor += bone.length;
  for (const surface of surfaceBuffers) {
    surface.copy(result, cursor);
    cursor += surface.length;
  }
  if (cursor !== result.length) fail("Internal SKD size mismatch");
  return result;
}

function buildSkc(bounds) {
  const headerSize = 48;
  const frameSize = 48;
  const channelDataSize = 32;
  const channelNameSize = 32;
  const result = Buffer.alloc(
    headerSize + frameSize + channelDataSize + channelNameSize * 2,
  );
  result.writeUInt32LE(SKC_IDENT, 0);
  result.writeInt32LE(SKC_VERSION, 4);
  result.writeInt32LE(0, 8);
  result.writeInt32LE(result.length, 12);
  result.writeFloatLE(1 / 30, 16);
  result.writeInt32LE(2, 36);
  result.writeInt32LE(headerSize + frameSize + channelDataSize, 40);
  result.writeInt32LE(1, 44);

  let cursor = headerSize;
  for (const value of bounds.minimum) {
    result.writeFloatLE(value, cursor);
    cursor += 4;
  }
  for (const value of bounds.maximum) {
    result.writeFloatLE(value, cursor);
    cursor += 4;
  }
  result.writeFloatLE(bounds.radius, cursor);
  cursor += 4;
  cursor += 12; // zero delta
  cursor += 4; // zero angle delta
  result.writeInt32LE(headerSize + frameSize, cursor);
  cursor += 4;

  // Bone channel order and data must match: rotation first, then position.
  result.writeFloatLE(0, cursor);
  result.writeFloatLE(0, cursor + 4);
  result.writeFloatLE(0, cursor + 8);
  result.writeFloatLE(1, cursor + 12);
  cursor += 16;
  cursor += 16; // zero position vec4

  writeFixedAscii(result, cursor, channelNameSize, "ORIGIN rot");
  cursor += channelNameSize;
  writeFixedAscii(result, cursor, channelNameSize, "ORIGIN pos");
  return result;
}

function shaderForMaterial(material, options) {
  if (!options.shaderPrefix) return qpath(options.fallbackShader);
  return `${qpath(options.shaderPrefix)}/${sanitizeName(material.name, "material")}`;
}

function buildTiki(modelName, modelPath, surfaces, options) {
  const lines = [
    "TIKI",
    "setup",
    "{",
    "\tscale 1",
    `\tpath ${qpath(modelPath)}`,
    `\tskelmodel ${modelName}.skd`,
  ];
  for (const surface of surfaces) {
    lines.push(
      `\tsurface ${surface.name} shader ${shaderForMaterial(surface.material, options)}`,
    );
  }
  lines.push(
    "}",
    "",
    "init",
    "{",
    "\tserver",
    "\t{",
    "\t\tclassname object",
    "\t}",
    "}",
    "",
    "animations",
    "{",
    `\tidle ${modelName}.skc`,
    "}",
    "",
    `/*QUAKED static_codex_nuke_${modelName} (0 0 1) (-16 -16 -16) (16 16 16)`,
    "Local-only topology converted from a user-owned CS2 resource.",
    "*/",
    "",
  );
  return lines.join("\n");
}

function makeManifest(
  glbs,
  inputPaths,
  modelName,
  modelPath,
  surfaces,
  bounds,
  sourceBounds,
  placementOrigin,
  outputs,
  options,
) {
  const materialMap = new Map();
  for (const surface of surfaces) {
    const key =
      `${surface.material.sourceIndex}:` +
      `${surface.material.index}:${surface.material.name}`;
    if (!materialMap.has(key)) {
      materialMap.set(key, {
        ...surface.material,
        shader: shaderForMaterial(surface.material, options),
        surfaceNames: [],
      });
    }
    materialMap.get(key).surfaceNames.push(surface.name);
  }

  const triangleCount = surfaces.reduce(
    (sum, surface) => sum + surface.indices.length / 3,
    0,
  );
  const vertexCount = surfaces.reduce(
    (sum, surface) => sum + surface.vertices.length,
    0,
  );

  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: {
      path: path.resolve(inputPaths[0]),
      sha256: sha256(glbs[0].file),
      bytes: glbs[0].file.length,
      gltfGenerator: glbs[0].json.asset?.generator || null,
    },
    sources: glbs.map((glb, index) => ({
      path: path.resolve(inputPaths[index]),
      sha256: sha256(glb.file),
      bytes: glb.file.length,
      gltfGenerator: glb.json.asset?.generator || null,
    })),
    conversion: {
      modelName,
      tikiDataPath: qpath(modelPath),
      coordinateSystem: options.coordinateSystem,
      scale: options.scale,
      flipV: options.flipV,
      recenterBounds: options.recenterBounds,
      placementOrigin,
      surfaceVertexLimit: MAX_SURFACE_VERTICES,
      surfaceTriangleLimit: MAX_SURFACE_TRIANGLES,
      tikiSurfaceLimit: MAX_TIKI_SURFACES,
    },
    geometry: {
      surfaces: surfaces.length,
      verticesAfterSplitting: vertexCount,
      triangles: triangleCount,
      bounds,
      sourceBounds,
      allSurfacesWithinRetailLimits: surfaces.every(
        (surface) =>
          surface.vertices.length <= MAX_SURFACE_VERTICES &&
          surface.indices.length / 3 <= MAX_SURFACE_TRIANGLES,
      ),
    },
    materials: [...materialMap.values()],
    outputs: Object.fromEntries(
      Object.entries(outputs).map(([name, buffer]) => [
        name,
        { bytes: buffer.length, sha256: sha256(buffer) },
      ]),
    ),
    legalBoundary:
      "The converted model and texture outputs are derived from user-owned Valve data and must remain local/untracked. Only this converter and non-payload metadata belong in the public repository.",
  };
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(`${usage()}\n`);
    return;
  }

  const inputPaths = options.inputs.map((input) => path.resolve(input));
  const outputPath = path.resolve(options.output);
  const modelName = sanitizeName(
    options.name || path.basename(inputPaths[0], path.extname(inputPaths[0])),
    "source2_model",
  );
  const modelPath =
    options.modelPath || `models/codex_nuke/source2/${modelName}`;
  const glbs = inputPaths.map(parseGlb);
  const primitives = glbs.flatMap((glb, sourceIndex) =>
    collectTriangles(glb, options, sourceIndex),
  );
  const sourceBounds = calculatePrimitiveBounds(primitives);
  const placementOrigin = options.recenterBounds
    ? sourceBounds.minimum.map(
        (minimum, axis) => (minimum + sourceBounds.maximum[axis]) / 2,
      )
    : [0, 0, 0];
  if (options.recenterBounds) {
    for (const primitive of primitives) {
      for (const vertex of primitive.vertices) {
        vertex.position = vertex.position.map(
          (value, axis) => value - placementOrigin[axis],
        );
      }
    }
  }
  const surfaces = splitPrimitives(primitives);
  if (surfaces.length > MAX_TIKI_SURFACES) {
    fail(
      `${modelName} requires ${surfaces.length} retail-safe surfaces, exceeding ` +
        `the original TIKI setup limit of ${MAX_TIKI_SURFACES}; partition the resource into multiple models`,
    );
  }
  const bounds = calculateBounds(surfaces);
  const outputs = {
    [`${modelName}.skd`]: buildSkd(modelName, surfaces),
    [`${modelName}.skc`]: buildSkc(bounds),
  };
  outputs[`${modelName}.tik`] = Buffer.from(
    buildTiki(modelName, modelPath, surfaces, options),
    "utf8",
  );

  fs.mkdirSync(outputPath, { recursive: true });
  for (const [filename, contents] of Object.entries(outputs)) {
    fs.writeFileSync(path.join(outputPath, filename), contents);
  }
  const manifest = makeManifest(
    glbs,
    inputPaths,
    modelName,
    modelPath,
    surfaces,
    bounds,
    sourceBounds,
    placementOrigin,
    outputs,
    options,
  );
  const manifestBuffer = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`);
  fs.writeFileSync(
    path.join(outputPath, `${modelName}.conversion.json`),
    manifestBuffer,
  );

  process.stdout.write(
    `${modelName}: ${manifest.geometry.triangles} triangles, ` +
      `${manifest.geometry.verticesAfterSplitting} split vertices, ` +
      `${manifest.geometry.surfaces} retail-safe surfaces\n`,
  );
  process.stdout.write(
    `bounds ${bounds.minimum.map((value) => value.toFixed(3)).join(" ")} -> ` +
      `${bounds.maximum.map((value) => value.toFixed(3)).join(" ")}\n`,
  );
  for (const [filename, contents] of Object.entries(outputs)) {
    process.stdout.write(
      `${filename}: ${contents.length} bytes sha256 ${sha256(contents)}\n`,
    );
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`ERROR: ${error.message}\n`);
  process.exitCode = 1;
}
