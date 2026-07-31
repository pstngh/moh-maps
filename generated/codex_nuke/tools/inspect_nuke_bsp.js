"use strict";

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const bspPath = path.resolve(
  process.argv.find((argument) => !argument.startsWith("--") && argument !== process.argv[0] && argument !== process.argv[1]) ||
    path.join(root, "main", "maps", "dm", "codex_nuke.bsp")
);
const requireRevision4 = process.argv.includes("--require-revision-4");
const allowUnlit = process.argv.includes("--allow-unlit");

const BSP_IDENT = 0x35313032;
const BSP_VERSION = 19;
const HEADER_BYTES = 12;
const LUMP_COUNT = 28;
const LUMP_SHADERS = 0;
const LUMP_LIGHTMAPS = 2;
const LUMP_SURFACES = 3;
const LUMP_VISIBILITY = 15;
const DSHADER_BYTES = 140;
const DSURFACE_BYTES = 108;
const LIGHTMAP_BYTES = 128 * 128 * 3;
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
if (shaderLump.length % DSHADER_BYTES !== 0) {
  fail(`Shader lump length ${shaderLump.length} is not divisible by ${DSHADER_BYTES}`);
}
if (lightmapLump.length % LIGHTMAP_BYTES !== 0) {
  fail(`Lightmap lump length ${lightmapLump.length} is not divisible by ${LIGHTMAP_BYTES}`);
}
if (surfaceLump.length % DSURFACE_BYTES !== 0) {
  fail(`Surface lump length ${surfaceLump.length} is not divisible by ${DSURFACE_BYTES}`);
}

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
  noLightmapShaders: noLightmapShaders.map((shader) => ({
    index: shader.index,
    name: shader.name,
    surfaceFlags: `0x${shader.surfaceFlags.toString(16)}`,
    referencedDrawSurfaces: surfaceCountsByShader.get(shader.index) || 0,
  })),
  unexpectedNoLightmap: unexpectedNoLightmap.map((shader) => shader.name),
};

if (!allowUnlit && lightmapPages === 0) fail("BSP has no compiled lightmaps");
if (allocatedLightmapPages > 180) {
  fail(`BSP allocation exceeds AA's 180-page lightmap limit: ${allocatedLightmapPages}`);
}
if (lightmapPages > 180) fail(`BSP exceeds AA's 180-page lightmap limit: ${lightmapPages}`);
if (unexpectedNoLightmap.length) {
  fail(`Unexpected non-lightmapped shaders: ${unexpectedNoLightmap.map((shader) => shader.name).join(", ")}`);
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