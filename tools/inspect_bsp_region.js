#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function parseVector(value) {
  const result = value.split(/[ ,]+/).map(Number);
  if (result.length !== 3 || result.some((number) => !Number.isFinite(number))) throw new Error(`Expected three coordinates, got ${value}`);
  return result;
}

if (process.argv.includes("--help")) {
  console.log("Usage: node inspect_bsp_region.js <input.bsp> <output.json> <min-x,y,z> <max-x,y,z>");
  process.exit(0);
}

const bspPath = process.argv[2] ? path.resolve(process.argv[2]) : null;
const outputPath = process.argv[3] ? path.resolve(process.argv[3]) : null;
const zone = {
  min: parseVector(process.argv[4] || "-999999,-999999,-999999"),
  max: parseVector(process.argv[5] || "999999,999999,999999"),
};
if (!bspPath || !outputPath || !fs.existsSync(bspPath)) throw new Error("Usage: node inspect_bsp_region.js <input.bsp> <output.json> <min-x,y,z> <max-x,y,z>");

const buffer = fs.readFileSync(bspPath);
const HEADER_BYTES = 12;
const DSHADER_BYTES = 140;
const DSURFACE_BYTES = 108;
const DRAWVERT_BYTES = 44;
function lump(index) {
  const header = HEADER_BYTES + index * 8;
  const offset = buffer.readInt32LE(header);
  const length = buffer.readInt32LE(header + 4);
  if (offset < 0 || length < 0 || offset + length > buffer.length) throw new Error(`Bad lump ${index}`);
  return { offset, length };
}
if (buffer.readUInt32LE(0) !== 0x35313032 || buffer.readInt32LE(4) !== 19) throw new Error("Expected Allied Assault BSP19");
const shaderLump = lump(0);
const surfaceLump = lump(3);
const vertexLump = lump(4);
if (shaderLump.length % DSHADER_BYTES || surfaceLump.length % DSURFACE_BYTES || vertexLump.length % DRAWVERT_BYTES) throw new Error("Unexpected BSP lump stride");

const shaders = [];
for (let offset = 0; offset < shaderLump.length; offset += DSHADER_BYTES) {
  const start = shaderLump.offset + offset;
  const end = buffer.indexOf(0, start);
  shaders.push(buffer.toString("utf8", start, end < 0 || end > start + 64 ? start + 64 : end));
}
function overlaps(bounds) {
  return bounds.min.every((value, axis) => value <= zone.max[axis] && bounds.max[axis] >= zone.min[axis]);
}
const surfaces = [];
for (let surface = 0; surface < surfaceLump.length / DSURFACE_BYTES; surface += 1) {
  const base = surfaceLump.offset + surface * DSURFACE_BYTES;
  const shaderNum = buffer.readInt32LE(base);
  const surfaceType = buffer.readInt32LE(base + 8);
  const firstVert = buffer.readInt32LE(base + 12);
  const numVerts = buffer.readInt32LE(base + 16);
  if (firstVert < 0 || numVerts <= 0 || (firstVert + numVerts) * DRAWVERT_BYTES > vertexLump.length) continue;
  const bounds = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  for (let index = firstVert; index < firstVert + numVerts; index += 1) {
    const vertex = vertexLump.offset + index * DRAWVERT_BYTES;
    for (let axis = 0; axis < 3; axis += 1) {
      const value = buffer.readFloatLE(vertex + axis * 4);
      bounds.min[axis] = Math.min(bounds.min[axis], value);
      bounds.max[axis] = Math.max(bounds.max[axis], value);
    }
  }
  if (overlaps(bounds)) surfaces.push({ surface, shaderNum, shader: shaders[shaderNum] || null, surfaceType, firstVert, numVerts, bounds });
}
const shaderCounts = {};
for (const surface of surfaces) shaderCounts[surface.shader] = (shaderCounts[surface.shader] || 0) + 1;
const report = {
  schemaVersion: 1,
  bsp: path.relative(process.cwd(), bspPath).replace(/\\/g, "/"),
  zone,
  matchedSurfaces: surfaces.length,
  shaderCounts: Object.entries(shaderCounts).map(([shader, count]) => ({ shader, count })).sort((a, b) => b.count - a.count || a.shader.localeCompare(b.shader)),
  surfaces,
};
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(`Wrote ${outputPath}: ${surfaces.length} surfaces`);
console.log(JSON.stringify(report.shaderCounts, null, 2));
