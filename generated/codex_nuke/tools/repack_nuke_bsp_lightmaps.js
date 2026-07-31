"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

if (process.argv.length < 4) {
  throw new Error(
    "Usage: node repack_nuke_bsp_lightmaps.js <input.bsp> <output.bsp>"
  );
}

const inputPath = path.resolve(process.argv[2]);
const outputPath = path.resolve(process.argv[3]);
const BSP_IDENT = 0x35313032;
const BSP_VERSION = 19;
const LUMP_SURFACES_HEADER = 12 + 3 * 8;
const LUMP_DRAWVERTS_HEADER = 12 + 4 * 8;
const DSURFACE_BYTES = 108;
const DRAWVERT_BYTES = 44;
const LIGHTMAP_SIZE = 128;
const GUTTER = 1;

const buffer = fs.readFileSync(inputPath);
if (buffer.readUInt32LE(0) !== BSP_IDENT || buffer.readInt32LE(4) !== BSP_VERSION) {
  throw new Error("Input is not a MOHAA BSP19 file");
}

function readLump(headerOffset, recordBytes, label) {
  const offset = buffer.readInt32LE(headerOffset);
  const length = buffer.readInt32LE(headerOffset + 4);
  if (
    offset < 0 ||
    length < 0 ||
    offset + length > buffer.length ||
    length % recordBytes !== 0
  ) {
    throw new Error(`Unexpected ${label} lump: offset ${offset}, length ${length}`);
  }
  return { offset, length, count: length / recordBytes };
}

const surfaces = readLump(LUMP_SURFACES_HEADER, DSURFACE_BYTES, "surface");
const drawVerts = readLump(LUMP_DRAWVERTS_HEADER, DRAWVERT_BYTES, "draw-vertex");
const rectangles = [];
const claimedDrawVerts = new Int32Array(drawVerts.count);
claimedDrawVerts.fill(-1);
let exactTexels = 0;
let originalPages = 0;

for (let index = 0; index < surfaces.count; index++) {
  const offset = surfaces.offset + index * DSURFACE_BYTES;
  const lightmapNum = buffer.readInt32LE(offset + 28);
  if (lightmapNum < 0) continue;
  const firstVert = buffer.readInt32LE(offset + 12);
  const numVerts = buffer.readInt32LE(offset + 16);
  const width = buffer.readInt32LE(offset + 40);
  const height = buffer.readInt32LE(offset + 44);
  if (
    firstVert < 0 ||
    numVerts < 0 ||
    firstVert + numVerts > drawVerts.count ||
    width < 1 ||
    height < 1 ||
    width + GUTTER * 2 > LIGHTMAP_SIZE ||
    height + GUTTER * 2 > LIGHTMAP_SIZE
  ) {
    throw new Error(`Invalid lightmapped surface ${index}`);
  }
  for (let vertex = firstVert; vertex < firstVert + numVerts; vertex++) {
    if (claimedDrawVerts[vertex] !== -1) {
      throw new Error(
        `Draw vertex ${vertex} is shared by surfaces ${claimedDrawVerts[vertex]} and ${index}`
      );
    }
    claimedDrawVerts[vertex] = index;
  }
  exactTexels += width * height;
  originalPages = Math.max(originalPages, lightmapNum + 1);
  rectangles.push({
    surfaceIndex: index,
    offset,
    firstVert,
    numVerts,
    oldPage: lightmapNum,
    oldX: buffer.readInt32LE(offset + 32),
    oldY: buffer.readInt32LE(offset + 36),
    width,
    height,
    packedWidth: width + GUTTER * 2,
    packedHeight: height + GUTTER * 2,
  });
}

function allocate(skyline, width, height) {
  let best = LIGHTMAP_SIZE;
  let bestX = -1;
  let bestY = -1;
  for (let x = 0; x <= LIGHTMAP_SIZE - width; x++) {
    let candidateY = 0;
    let column = 0;
    for (; column < width; column++) {
      if (skyline[x + column] >= best) break;
      candidateY = Math.max(candidateY, skyline[x + column]);
    }
    if (column === width) {
      bestX = x;
      bestY = best = candidateY;
    }
  }
  if (bestY < 0 || bestY + height > LIGHTMAP_SIZE) return null;
  for (let column = 0; column < width; column++) {
    skyline[bestX + column] = bestY + height;
  }
  return { x: bestX, y: bestY };
}

rectangles.sort(
  (left, right) =>
    Math.max(right.packedWidth, right.packedHeight) -
      Math.max(left.packedWidth, left.packedHeight) ||
    right.packedHeight - left.packedHeight ||
    right.packedWidth - left.packedWidth ||
    right.packedWidth * right.packedHeight -
      left.packedWidth * left.packedHeight ||
    left.surfaceIndex - right.surfaceIndex
);

const pages = [];
for (const rectangle of rectangles) {
  let placement = null;
  for (let page = 0; page < pages.length; page++) {
    const trial = pages[page].slice();
    const candidate = allocate(
      trial,
      rectangle.packedWidth,
      rectangle.packedHeight
    );
    if (!candidate) continue;
    pages[page] = trial;
    placement = { page, x: candidate.x + GUTTER, y: candidate.y + GUTTER };
    break;
  }
  if (!placement) {
    const skyline = new Array(LIGHTMAP_SIZE).fill(0);
    const candidate = allocate(
      skyline,
      rectangle.packedWidth,
      rectangle.packedHeight
    );
    if (!candidate) throw new Error(`Cannot pack surface ${rectangle.surfaceIndex}`);
    placement = {
      page: pages.push(skyline) - 1,
      x: candidate.x + GUTTER,
      y: candidate.y + GUTTER,
    };
  }

  buffer.writeInt32LE(placement.page, rectangle.offset + 28);
  buffer.writeInt32LE(placement.x, rectangle.offset + 32);
  buffer.writeInt32LE(placement.y, rectangle.offset + 36);
  const deltaS = (placement.x - rectangle.oldX) / LIGHTMAP_SIZE;
  const deltaT = (placement.y - rectangle.oldY) / LIGHTMAP_SIZE;
  for (
    let vertex = rectangle.firstVert;
    vertex < rectangle.firstVert + rectangle.numVerts;
    vertex++
  ) {
    const vertexOffset = drawVerts.offset + vertex * DRAWVERT_BYTES;
    const s = buffer.readFloatLE(vertexOffset + 20) + deltaS;
    const t = buffer.readFloatLE(vertexOffset + 24) + deltaT;
    if (s < -0.0001 || s > 1.0001 || t < -0.0001 || t > 1.0001) {
      throw new Error(`Repacked lightmap UV is outside [0,1] at draw vertex ${vertex}`);
    }
    buffer.writeFloatLE(s, vertexOffset + 20);
    buffer.writeFloatLE(t, vertexOffset + 24);
  }
}

if (pages.length > 180) {
  throw new Error(`Repacked atlas still exceeds the AA limit: ${pages.length} pages`);
}

fs.writeFileSync(outputPath, buffer);
const reservedTexels = rectangles.reduce(
  (sum, rectangle) => sum + rectangle.packedWidth * rectangle.packedHeight,
  0
);
const hash = crypto.createHash("sha256").update(buffer).digest("hex");
process.stdout.write(
  `${JSON.stringify(
    {
      input: inputPath,
      output: outputPath,
      surfaces: rectangles.length,
      drawVerts: drawVerts.count,
      gutterPixels: GUTTER,
      originalPages,
      repackedPages: pages.length,
      exactTexels,
      reservedTexels,
      exactUtilization: exactTexels / (pages.length * LIGHTMAP_SIZE ** 2),
      reservedUtilization: reservedTexels / (pages.length * LIGHTMAP_SIZE ** 2),
      bytes: buffer.length,
      sha256: hash,
    },
    null,
    2
  )}\n`
);