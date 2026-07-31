"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

if (process.argv.length < 4) {
  throw new Error(
    "Usage: node relight_nuke_unlit_surfaces.js <input.bsp> <output.bsp>"
  );
}

const inputPath = path.resolve(process.argv[2]);
const outputPath = path.resolve(process.argv[3]);
const BSP_IDENT = 0x35313032;
const BSP_VERSION = 19;
const HEADER_BYTES = 12;
const LUMP_COUNT = 28;
const LUMP_SHADERS = 0;
const LUMP_LIGHTMAPS = 2;
const LUMP_SURFACES = 3;
const LUMP_DRAWVERTS = 4;
const DSHADER_BYTES = 140;
const DSURFACE_BYTES = 108;
const DRAWVERT_BYTES = 44;
const LIGHTMAP_SIZE = 128;
const LIGHTMAP_BYTES = LIGHTMAP_SIZE * LIGHTMAP_SIZE * 3;
const MST_PLANAR = 1;
const PAGE_RECT = { x: 1, y: 1, width: 126, height: 126 };
const PAGE_UV = (PAGE_RECT.x + PAGE_RECT.width / 2) / LIGHTMAP_SIZE;

const buffer = fs.readFileSync(inputPath);
if (buffer.readUInt32LE(0) !== BSP_IDENT || buffer.readInt32LE(4) !== BSP_VERSION) {
  throw new Error("Input is not a MOHAA BSP19 file");
}

function readLump(index) {
  const headerOffset = HEADER_BYTES + index * 8;
  const offset = buffer.readInt32LE(headerOffset);
  const length = buffer.readInt32LE(headerOffset + 4);
  if (offset < 0 || length < 0 || offset + length > buffer.length) {
    throw new Error(`Lump ${index} is outside the BSP: ${offset}+${length}`);
  }
  return { index, offset, length };
}

const shaderLump = readLump(LUMP_SHADERS);
const lightmapLump = readLump(LUMP_LIGHTMAPS);
const surfaceLump = readLump(LUMP_SURFACES);
const drawVertLump = readLump(LUMP_DRAWVERTS);
if (lightmapLump.length % LIGHTMAP_BYTES !== 0) {
  throw new Error(`Lightmap lump length ${lightmapLump.length} is not page-aligned`);
}
if (surfaceLump.length % DSURFACE_BYTES !== 0) {
  throw new Error(`Surface lump length ${surfaceLump.length} is not record-aligned`);
}

const shaderNames = [];
for (let index = 0; index < shaderLump.length / DSHADER_BYTES; index++) {
  const offset = shaderLump.offset + index * DSHADER_BYTES;
  const terminator = buffer.indexOf(0, offset);
  shaderNames.push(
    buffer.toString(
      "ascii",
      offset,
      terminator < 0 || terminator > offset + 64 ? offset + 64 : terminator
    )
  );
}

const existingPages = lightmapLump.length / LIGHTMAP_BYTES;
const constantPage = existingPages;
if (constantPage + 1 > 180) {
  throw new Error(`Appending a page would exceed AA's 180-page limit: ${constantPage + 1}`);
}

const drawVertCount = drawVertLump.length / DRAWVERT_BYTES;
const vertOwner = new Int8Array(drawVertCount); // 0 unclaimed, 1 lit, 2 unlit
const patchedByShader = new Map();
const patchedSurfaces = [];
let skySurfaces = 0;

for (let index = 0; index < surfaceLump.length / DSURFACE_BYTES; index++) {
  const offset = surfaceLump.offset + index * DSURFACE_BYTES;
  const lightmapNum = buffer.readInt32LE(offset + 28);
  const firstVert = buffer.readInt32LE(offset + 12);
  const numVerts = buffer.readInt32LE(offset + 16);
  if (firstVert < 0 || numVerts < 0 || firstVert + numVerts > drawVertCount) {
    throw new Error(`Surface ${index} references invalid draw vertices`);
  }
  const shaderName = shaderNames[buffer.readInt32LE(offset)];
  const isSky = shaderName.startsWith("textures/sky/");
  if (lightmapNum >= 0 || isSky) {
    if (isSky && lightmapNum < 0) skySurfaces++;
    for (let vertex = firstVert; vertex < firstVert + numVerts; vertex++) {
      if (vertOwner[vertex] === 2) {
        throw new Error(`Draw vertex ${vertex} is shared by lit and unlit surfaces`);
      }
      vertOwner[vertex] = 1;
    }
    continue;
  }
  const surfaceType = buffer.readInt32LE(offset + 8);
  if (surfaceType !== MST_PLANAR) {
    throw new Error(`Unlit surface ${index} has unsupported type ${surfaceType}`);
  }
  for (let vertex = firstVert; vertex < firstVert + numVerts; vertex++) {
    if (vertOwner[vertex] === 1) {
      throw new Error(`Draw vertex ${vertex} is shared by lit and unlit surfaces`);
    }
    vertOwner[vertex] = 2;
  }
  patchedSurfaces.push({ offset, firstVert, numVerts });
  patchedByShader.set(shaderName, (patchedByShader.get(shaderName) || 0) + 1);
}

if (!patchedSurfaces.length) {
  throw new Error("No unlit non-sky surfaces found; nothing to relight");
}

for (const surface of patchedSurfaces) {
  buffer.writeInt32LE(constantPage, surface.offset + 28);
  buffer.writeInt32LE(PAGE_RECT.x, surface.offset + 32);
  buffer.writeInt32LE(PAGE_RECT.y, surface.offset + 36);
  buffer.writeInt32LE(PAGE_RECT.width, surface.offset + 40);
  buffer.writeInt32LE(PAGE_RECT.height, surface.offset + 44);
  for (
    let vertex = surface.firstVert;
    vertex < surface.firstVert + surface.numVerts;
    vertex++
  ) {
    const vertexOffset = drawVertLump.offset + vertex * DRAWVERT_BYTES;
    buffer.writeFloatLE(PAGE_UV, vertexOffset + 20);
    buffer.writeFloatLE(PAGE_UV, vertexOffset + 24);
  }
}

const insertAt = lightmapLump.offset + lightmapLump.length;
const whitePage = Buffer.alloc(LIGHTMAP_BYTES, 0xff);
const output = Buffer.concat([
  buffer.slice(0, insertAt),
  whitePage,
  buffer.slice(insertAt),
]);
output.writeInt32LE(lightmapLump.length + LIGHTMAP_BYTES, HEADER_BYTES + LUMP_LIGHTMAPS * 8 + 4);
for (let index = 0; index < LUMP_COUNT; index++) {
  const headerOffset = HEADER_BYTES + index * 8;
  const offset = output.readInt32LE(headerOffset);
  if (index !== LUMP_LIGHTMAPS && offset >= insertAt) {
    output.writeInt32LE(offset + LIGHTMAP_BYTES, headerOffset);
  }
}

fs.writeFileSync(outputPath, output);
const hash = crypto.createHash("sha256").update(output).digest("hex");
process.stdout.write(
  `${JSON.stringify(
    {
      input: inputPath,
      output: outputPath,
      relitSurfaces: patchedSurfaces.length,
      relitByShader: Object.fromEntries(
        [...patchedByShader.entries()].sort((left, right) =>
          left[0].localeCompare(right[0])
        )
      ),
      skySurfacesLeftUnlit: skySurfaces,
      constantPage,
      constantPageColor: [255, 255, 255],
      pages: constantPage + 1,
      bytes: output.length,
      sha256: hash,
    },
    null,
    2
  )}\n`
);
