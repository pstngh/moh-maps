#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const bspPath = path.resolve(process.argv[2] || "");
const outputPath = path.resolve(process.argv[3] || path.join(__dirname, "..", "codex_obj_team2_expanded-forest-bsp-zones.json"));
if (!fs.existsSync(bspPath)) throw new Error("Pass an existing AA BSP19 path");
const buffer = fs.readFileSync(bspPath);
const zones = [
  { id: "allied_open_perimeter", min: [-2432, -352, -1000], max: [-900, 448, 600] },
  { id: "west_forest_route", min: [-2112, -1600, -1000], max: [-900, -256, 1000] },
  { id: "central_causeway", min: [-1024, -1856, -1000], max: [1696, -960, 1000] },
  { id: "east_forest_return", min: [1472, -1600, -700], max: [3136, 512, 700] },
  { id: "east_annex", min: [2960, 256, -700], max: [5200, 2944, 900] },
];
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
if (buffer.readUInt32LE(0) !== 0x35313032 || buffer.readInt32LE(4) !== 19) throw new Error("Expected AA BSP19");
const shaderLump = lump(0);
const surfaceLump = lump(3);
const vertexLump = lump(4);
if (shaderLump.length % DSHADER_BYTES || surfaceLump.length % DSURFACE_BYTES || vertexLump.length % DRAWVERT_BYTES) throw new Error("Unexpected BSP lump stride");

const shaders = [];
for (let offset = 0; offset < shaderLump.length; offset += DSHADER_BYTES) {
  const start = shaderLump.offset + offset;
  const zero = buffer.indexOf(0, start);
  shaders.push(buffer.toString("utf8", start, zero < 0 || zero > start + 64 ? start + 64 : zero));
}
function overlaps(bounds, zone) {
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
  surfaces.push({ surface, shader: shaders[shaderNum] || null, surfaceType, bounds });
}

const zoneReports = zones.map((zone) => {
  const matched = surfaces.filter((surface) => overlaps(surface.bounds, zone));
  const counts = new Map();
  for (const surface of matched) counts.set(surface.shader, (counts.get(surface.shader) || 0) + 1);
  if (!matched.length) throw new Error(`Compiled zone ${zone.id} contains no draw surfaces`);
  return {
    ...zone,
    matchedSurfaces: matched.length,
    shaderCounts: [...counts.entries()].map(([shader, count]) => ({ shader, count })).sort((a, b) => b.count - a.count || a.shader.localeCompare(b.shader)),
    surfaceNumbers: matched.map((surface) => surface.surface),
  };
});
const report = {
  schemaVersion: 1,
  revision: 4,
  bsp: bspPath.replace(/\\/g, "/"),
  bspBytes: buffer.length,
  zones: zoneReports,
};
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(`Wrote ${outputPath}`);
for (const zone of zoneReports) console.log(`${zone.id}: ${zone.matchedSurfaces} surfaces; ${zone.shaderCounts.length} shaders`);
