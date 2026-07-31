"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
let bspArgument = null;
let requireRevision4 = false;
let allowUnlit = false;
let requireSource2StaticCount = null;
let compareNonEntityWith = null;
const requiredRuntimeModelOrigins = [];
const argumentsList = process.argv.slice(2);
for (let index = 0; index < argumentsList.length; index += 1) {
  const argument = argumentsList[index];
  if (argument === "--require-revision-4") requireRevision4 = true;
  else if (argument === "--allow-unlit") allowUnlit = true;
  else if (argument === "--require-source2-static-count") {
    index += 1;
    const countArgument = argumentsList[index];
    if (!/^[1-9]\d*$/.test(countArgument || "")) {
      throw new Error("--require-source2-static-count requires a positive integer");
    }
    requireSource2StaticCount = Number(countArgument);
  } else if (argument === "--compare-nonentity-with") {
    index += 1;
    compareNonEntityWith = argumentsList[index];
    if (!compareNonEntityWith) {
      throw new Error("--compare-nonentity-with requires a BSP path");
    }
  } else if (argument === "--require-runtime-model-origin") {
    if (index + 4 >= argumentsList.length) {
      throw new Error("--require-runtime-model-origin requires MODEL X Y Z");
    }
    const model = argumentsList[++index];
    const origin = [
      Number(argumentsList[++index]),
      Number(argumentsList[++index]),
      Number(argumentsList[++index]),
    ];
    if (!model || !origin.every(Number.isFinite)) {
      throw new Error("--require-runtime-model-origin requires MODEL X Y Z");
    }
    requiredRuntimeModelOrigins.push({ model, origin });
  } else if (argument.startsWith("--")) {
    throw new Error(`Unknown option: ${argument}`);
  } else if (bspArgument) {
    throw new Error(`Unexpected positional argument: ${argument}`);
  } else {
    bspArgument = argument;
  }
}
const bspPath = path.resolve(
  bspArgument || path.join(root, "main", "maps", "dm", "codex_nuke.bsp"),
);

const BSP_IDENT = 0x35313032;
const BSP_VERSION = 19;
const HEADER_BYTES = 12;
const LUMP_COUNT = 28;
const LUMP_SHADERS = 0;
const LUMP_LIGHTMAPS = 2;
const LUMP_SURFACES = 3;
const LUMP_VISIBILITY = 15;
const LUMP_ENTITIES = 14;
const LUMP_STATIC_MODEL_DEFS = 25;
const LUMP_STATIC_MODEL_INDEXES = 26;
const DSHADER_BYTES = 140;
const DSURFACE_BYTES = 108;
const LIGHTMAP_BYTES = 128 * 128 * 3;
const STATIC_MODEL_BYTES = 164;
const SURF_NOLIGHTMAP = 0x100;

function fail(message) {
  throw new Error(message);
}

function readLump(buffer, index) {
  if (index < 0 || index >= LUMP_COUNT) fail(`Invalid lump index ${index}`);
  const headerOffset = HEADER_BYTES + index * 8;
  const offset = buffer.readInt32LE(headerOffset);
  const length = buffer.readInt32LE(headerOffset + 4);
  if (offset < 0 || length < 0 || offset + length > buffer.length) {
    fail(`Lump ${index} is outside the BSP: offset ${offset}, length ${length}`);
  }
  return { index, offset, length };
}

function cString(buffer, offset, length) {
  const end = buffer.indexOf(0, offset);
  const boundedEnd = end < 0 || end > offset + length ? offset + length : end;
  return buffer.toString("ascii", offset, boundedEnd);
}

const buffer = fs.readFileSync(bspPath);
if (buffer.length < HEADER_BYTES + LUMP_COUNT * 8) fail("BSP header is truncated");
const ident = buffer.readUInt32LE(0);
const version = buffer.readInt32LE(4);
const checksum = buffer.readUInt32LE(8);
if (ident !== BSP_IDENT) fail(`Unexpected BSP ident 0x${ident.toString(16)}`);
if (version !== BSP_VERSION) fail(`Expected BSP version 19, got ${version}`);

const shaderLump = readLump(buffer, LUMP_SHADERS);
const lightmapLump = readLump(buffer, LUMP_LIGHTMAPS);
const surfaceLump = readLump(buffer, LUMP_SURFACES);
const visibilityLump = readLump(buffer, LUMP_VISIBILITY);
const entityLump = readLump(buffer, LUMP_ENTITIES);
const staticModelLump = readLump(buffer, LUMP_STATIC_MODEL_DEFS);
const staticModelIndexLump = readLump(buffer, LUMP_STATIC_MODEL_INDEXES);
if (shaderLump.length % DSHADER_BYTES !== 0) {
  fail(`Shader lump length ${shaderLump.length} is not divisible by ${DSHADER_BYTES}`);
}
if (lightmapLump.length % LIGHTMAP_BYTES !== 0) {
  fail(`Lightmap lump length ${lightmapLump.length} is not divisible by ${LIGHTMAP_BYTES}`);
}
if (surfaceLump.length % DSURFACE_BYTES !== 0) {
  fail(`Surface lump length ${surfaceLump.length} is not divisible by ${DSURFACE_BYTES}`);
}
if (staticModelLump.length % STATIC_MODEL_BYTES !== 0) {
  fail(`Static-model lump length ${staticModelLump.length} is invalid`);
}
if (staticModelIndexLump.length % 2 !== 0) {
  fail(`Static-model index lump length ${staticModelIndexLump.length} is invalid`);
}

const staticModels = [];
for (let index = 0; index < staticModelLump.length / STATIC_MODEL_BYTES; index += 1) {
  const offset = staticModelLump.offset + index * STATIC_MODEL_BYTES;
  staticModels.push({
    index,
    model: cString(buffer, offset, 128),
    origin: [0, 1, 2].map((axis) => buffer.readFloatLE(offset + 128 + axis * 4)),
    angles: [0, 1, 2].map((axis) => buffer.readFloatLE(offset + 140 + axis * 4)),
    scale: buffer.readFloatLE(offset + 152),
    firstVertexData: buffer.readInt32LE(offset + 156),
    numVertexData: buffer.readInt32LE(offset + 160),
  });
}
for (let offset = 0; offset < staticModelIndexLump.length; offset += 2) {
  const modelIndex = buffer.readUInt16LE(staticModelIndexLump.offset + offset);
  if (modelIndex >= staticModels.length) {
    fail(`Static-model index ${modelIndex} exceeds ${staticModels.length} definitions`);
  }
}
const source2ModelPattern = /^codex_nuke\/source2\/([a-z0-9_]+)\/\1\.tik$/;
const source2StaticModels = staticModels.filter((model) =>
  source2ModelPattern.test(model.model),
);

const entityText = buffer.toString(
  "utf8",
  entityLump.offset,
  entityLump.offset + entityLump.length,
);
const entities = [...entityText.matchAll(/\{([\s\S]*?)\}/g)].map((match) => {
  const properties = {};
  for (const property of match[1].matchAll(/"([^"]*)"\s+"([^"]*)"/g)) {
    properties[property[1]] = property[2];
  }
  return properties;
});

const shaders = [];
for (let index = 0; index < shaderLump.length / DSHADER_BYTES; index++) {
  const offset = shaderLump.offset + index * DSHADER_BYTES;
  shaders.push({
    index,
    name: cString(buffer, offset, 64),
    surfaceFlags: buffer.readUInt32LE(offset + 64),
    contentFlags: buffer.readUInt32LE(offset + 68),
    subdivisions: buffer.readInt32LE(offset + 72),
    fenceMaskImage: cString(buffer, offset + 76, 64),
  });
}

const surfaceCountsByShader = new Map();
let allocatedLightmapPages = 0;
for (let index = 0; index < surfaceLump.length / DSURFACE_BYTES; index++) {
  const offset = surfaceLump.offset + index * DSURFACE_BYTES;
  const shaderIndex = buffer.readInt32LE(offset);
  const lightmapNum = buffer.readInt32LE(offset + 28);
  allocatedLightmapPages = Math.max(allocatedLightmapPages, lightmapNum + 1);
  surfaceCountsByShader.set(
    shaderIndex,
    (surfaceCountsByShader.get(shaderIndex) || 0) + 1
  );
}

const lightmapPages = lightmapLump.length / LIGHTMAP_BYTES;
const codexShaders = shaders.filter((shader) => shader.name.includes("codex_nuke/"));
const noLightmapShaders = codexShaders.filter(
  (shader) => (shader.surfaceFlags & SURF_NOLIGHTMAP) !== 0
);
const allowedNoLightmap = new Set([
  "textures/codex_nuke/chainlink",
  "textures/codex_nuke/foliage",
  "textures/codex_nuke/window_backing",
]);
const unexpectedNoLightmap = noLightmapShaders.filter(
  (shader) =>
    (surfaceCountsByShader.get(shader.index) || 0) > 0 &&
    !allowedNoLightmap.has(shader.name)
);

const result = {
  bsp: bspPath,
  bytes: buffer.length,
  ident: `0x${ident.toString(16)}`,
  version,
  checksum: `0x${checksum.toString(16)}`,
  shaderCount: shaders.length,
  surfaceCount: surfaceLump.length / DSURFACE_BYTES,
  codexShaderCount: codexShaders.length,
  lightmapBytes: lightmapLump.length,
  lightmapPages,
  allocatedLightmapPages,
  visibilityBytes: visibilityLump.length,
  staticModelCount: staticModels.length,
  staticModelIndexCount: staticModelIndexLump.length / 2,
  source2StaticModels: source2StaticModels.map((model) => model.model),
  requiredRuntimeModels: [],
  nonEntityComparison: null,
  noLightmapShaders: noLightmapShaders.map((shader) => ({
    index: shader.index,
    name: shader.name,
    surfaceFlags: `0x${shader.surfaceFlags.toString(16)}`,
    referencedDrawSurfaces: surfaceCountsByShader.get(shader.index) || 0,
  })),
  unexpectedNoLightmap: unexpectedNoLightmap.map((shader) => shader.name),
};

for (const requireRuntimeModelOrigin of requiredRuntimeModelOrigins) {
  const matching = entities.filter(
    (entity) =>
      entity.classname === "script_model" &&
      entity.model === requireRuntimeModelOrigin.model,
  );
  if (matching.length !== 1) {
    fail(
      `Expected one runtime model ${requireRuntimeModelOrigin.model}, found ${matching.length}`,
    );
  }
  const actualOrigin = (matching[0].origin || "")
    .trim()
    .split(/\s+/)
    .map(Number);
  if (
    actualOrigin.length !== 3 ||
    !actualOrigin.every(Number.isFinite) ||
    actualOrigin.some(
      (value, axis) =>
        Math.abs(value - requireRuntimeModelOrigin.origin[axis]) > 1e-6,
    )
  ) {
    fail(
      `Runtime model origin mismatch for ${requireRuntimeModelOrigin.model}: ${matching[0].origin}`,
    );
  }
  result.requiredRuntimeModels.push({
    model: requireRuntimeModelOrigin.model,
    origin: actualOrigin,
  });
}

if (compareNonEntityWith) {
  const comparisonPath = path.resolve(compareNonEntityWith);
  const comparisonBuffer = fs.readFileSync(comparisonPath);
  if (
    comparisonBuffer.length < HEADER_BYTES + LUMP_COUNT * 8 ||
    comparisonBuffer.readUInt32LE(0) !== BSP_IDENT ||
    comparisonBuffer.readInt32LE(4) !== BSP_VERSION
  ) {
    fail(`Comparison BSP is not version ${BSP_VERSION}: ${comparisonPath}`);
  }
  const changedNonEntityLumps = [];
  for (let index = 0; index < LUMP_COUNT; index += 1) {
    if (index === LUMP_ENTITIES) continue;
    const current = readLump(buffer, index);
    const comparison = readLump(comparisonBuffer, index);
    const currentHash = crypto
      .createHash("sha256")
      .update(buffer.subarray(current.offset, current.offset + current.length))
      .digest("hex");
    const comparisonHash = crypto
      .createHash("sha256")
      .update(
        comparisonBuffer.subarray(
          comparison.offset,
          comparison.offset + comparison.length,
        ),
      )
      .digest("hex");
    if (current.length !== comparison.length || currentHash !== comparisonHash) {
      changedNonEntityLumps.push(index);
    }
  }
  if (changedNonEntityLumps.length) {
    fail(
      `Entity-only update changed non-entity BSP lumps: ${changedNonEntityLumps.join(", ")}`,
    );
  }
  result.nonEntityComparison = {
    bsp: comparisonPath,
    unchangedLumps: LUMP_COUNT - 1,
    excludedEntityLump: LUMP_ENTITIES,
  };
}

if (!allowUnlit && lightmapPages === 0) fail("BSP has no compiled lightmaps");
if (allocatedLightmapPages > 180) {
  fail(`BSP allocation exceeds AA's 180-page lightmap limit: ${allocatedLightmapPages}`);
}
if (lightmapPages > 180) fail(`BSP exceeds AA's 180-page lightmap limit: ${lightmapPages}`);
if (unexpectedNoLightmap.length) {
  fail(`Unexpected non-lightmapped shaders: ${unexpectedNoLightmap.map((shader) => shader.name).join(", ")}`);
}
if (requireSource2StaticCount !== null) {
  if (source2StaticModels.length !== requireSource2StaticCount) {
    fail(
      `Expected ${requireSource2StaticCount} Source 2 static models, found ${source2StaticModels.length}`,
    );
  }
  if (new Set(source2StaticModels.map((model) => model.model)).size !== source2StaticModels.length) {
    fail("Source 2 static-model BSP definitions are not unique");
  }
  for (const model of source2StaticModels) {
    const transform = [...model.origin, ...model.angles, model.scale];
    if (
      !transform.every(Number.isFinite) ||
      model.origin.some((value) => Math.abs(value) > 1e-5) ||
      model.angles.some((value) => Math.abs(value) > 1e-5) ||
      Math.abs(model.scale - 1) > 1e-5
    ) {
      fail(`Source 2 world aggregate has an unexpected BSP transform: ${model.model}`);
    }
  }
}
if (requireRevision4) {
  for (const name of [
    "textures/codex_nuke/chainlink",
    "textures/codex_nuke/foliage",
    ]) {
    if (
      !noLightmapShaders.some(
        (shader) =>
          shader.name === name && (surfaceCountsByShader.get(shader.index) || 0) > 0
      )
    ) {
      fail(`Revision-4 targeted no-lightmap draw surfaces are missing: ${name}`);
    }
  }
}

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);