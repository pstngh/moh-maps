"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const bspPath = path.resolve(process.argv[2] || path.join(__dirname, "..", "main", "maps", "dm", "codex_reactor.bsp"));
const buffer = fs.readFileSync(bspPath);
const BSP_IDENT = 0x35313032;
const BSP_VERSION = 19;
const HEADER_BYTES = 12;
const LUMP_COUNT = 28;
const LUMP_SHADERS = 0;
const LUMP_LIGHTMAPS = 2;
const LUMP_SURFACES = 3;
const LUMP_ENTITIES = 14;
const LUMP_VISIBILITY = 15;
const DSHADER_BYTES = 140;
const DSURFACE_BYTES = 108;
const LIGHTMAP_BYTES = 128 * 128 * 3;

function fail(message) {
  throw new Error(message);
}

function lump(index) {
  const headerOffset = HEADER_BYTES + index * 8;
  const offset = buffer.readInt32LE(headerOffset);
  const length = buffer.readInt32LE(headerOffset + 4);
  if (offset < 0 || length < 0 || offset + length > buffer.length) fail(`Lump ${index} is outside BSP`);
  return { offset, length };
}

if (buffer.length < HEADER_BYTES + LUMP_COUNT * 8) fail("Truncated BSP header");
const ident = buffer.readUInt32LE(0);
const version = buffer.readInt32LE(4);
const checksum = buffer.readUInt32LE(8);
if (ident !== BSP_IDENT) fail(`Unexpected BSP ident: 0x${ident.toString(16)}`);
if (version !== BSP_VERSION) fail(`Expected BSP 19, got ${version}`);

const shaderLump = lump(LUMP_SHADERS);
const lightmapLump = lump(LUMP_LIGHTMAPS);
const surfaceLump = lump(LUMP_SURFACES);
const entityLump = lump(LUMP_ENTITIES);
const visibilityLump = lump(LUMP_VISIBILITY);
if (shaderLump.length % DSHADER_BYTES !== 0) fail("Invalid shader lump length");
if (lightmapLump.length % LIGHTMAP_BYTES !== 0) fail("Invalid lightmap lump length");
if (surfaceLump.length % DSURFACE_BYTES !== 0) fail("Invalid surface lump length");

let allocatedLightmapPages = 0;
for (let offset = 0; offset < surfaceLump.length; offset += DSURFACE_BYTES) {
  const lightmapNumber = buffer.readInt32LE(surfaceLump.offset + offset + 28);
  allocatedLightmapPages = Math.max(allocatedLightmapPages, lightmapNumber + 1);
}

const entityText = buffer.toString("utf8", entityLump.offset, entityLump.offset + entityLump.length);
function entityCount(classname) {
  return [...entityText.matchAll(new RegExp(`"classname" "${classname}"`, "g"))].length;
}

const result = {
  bsp: bspPath,
  bytes: buffer.length,
  sha256: crypto.createHash("sha256").update(buffer).digest("hex"),
  ident: `0x${ident.toString(16)}`,
  version,
  checksum: `0x${checksum.toString(16)}`,
  shaders: shaderLump.length / DSHADER_BYTES,
  surfaces: surfaceLump.length / DSURFACE_BYTES,
  lightmapPages: lightmapLump.length / LIGHTMAP_BYTES,
  allocatedLightmapPages,
  visibilityBytes: visibilityLump.length,
  entities: {
    info_player_deathmatch: entityCount("info_player_deathmatch"),
    info_player_allied: entityCount("info_player_allied"),
    info_player_axis: entityCount("info_player_axis"),
    info_player_start: entityCount("info_player_start"),
    light: entityCount("light"),
  },
};
if (result.lightmapPages <= 0 || result.lightmapPages > 180) fail(`Invalid final lightmap page count: ${result.lightmapPages}`);
if (result.allocatedLightmapPages !== result.lightmapPages) fail("Allocated/written lightmap page mismatch");
if (
  result.entities.info_player_deathmatch !== 20 ||
  result.entities.info_player_allied !== 10 ||
  result.entities.info_player_axis !== 10 ||
  result.entities.info_player_start !== 1
) {
  fail(`Compiled spawn counts are wrong: ${JSON.stringify(result.entities)}`);
}
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);