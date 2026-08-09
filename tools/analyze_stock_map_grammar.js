#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function usage() {
  throw new Error("Usage: node analyze_stock_map_grammar.js <input.map> [output.json]");
}

const inputPath = process.argv[2] ? path.resolve(process.argv[2]) : usage();
const outputPath = process.argv[3] ? path.resolve(process.argv[3]) : null;
const text = fs.readFileSync(inputPath, "utf8").replace(/\r\n/g, "\n");
const lines = text.split("\n");

const facePattern = /^\s*\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)\s*\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)\s*\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)\s+(\S+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(.*)$/;
const keyPattern = /^\s*"([^"]+)"\s+"([^"]*)"\s*$/;

function addCount(map, key, amount = 1) {
  map.set(key, (map.get(key) || 0) + amount);
}

function sortedCounts(map, limit = null) {
  const rows = [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  return limit == null ? rows : rows.slice(0, limit);
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function subtract(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function parseFace(line) {
  const match = line.match(facePattern);
  if (!match) return null;
  const numbers = match.slice(1, 10).map(Number);
  const p1 = numbers.slice(0, 3);
  const p2 = numbers.slice(3, 6);
  const p3 = numbers.slice(6, 9);
  const normal = cross(subtract(p2, p1), subtract(p3, p1));
  const abs = normal.map(Math.abs);
  const magnitude = Math.hypot(...normal);
  let axis = "angled";
  if (magnitude > 0) {
    const normalized = abs.map((value) => value / magnitude);
    const max = Math.max(...normalized);
    if (max > 0.999999) axis = ["x", "y", "z"][normalized.indexOf(max)];
  }
  return {
    points: [p1, p2, p3],
    texture: match[10],
    shift: [Number(match[11]), Number(match[12])],
    rotation: Number(match[13]),
    scale: [Number(match[14]), Number(match[15])],
    content: Number(match[16]),
    surface: Number(match[17]),
    value: Number(match[18]),
    extensions: match[19].trim(),
    axis,
  };
}

function extractBalancedBlock(startIndex) {
  let openIndex = startIndex;
  while (openIndex < lines.length && lines[openIndex].trim() !== "{") openIndex += 1;
  if (openIndex >= lines.length) return null;
  let depth = 0;
  for (let index = openIndex; index < lines.length; index += 1) {
    for (const character of lines[index]) {
      if (character === "{") depth += 1;
      else if (character === "}") depth -= 1;
    }
    if (depth === 0) return { openIndex, closeIndex: index, block: lines.slice(openIndex, index + 1) };
  }
  throw new Error(`Unclosed block after line ${startIndex + 1}`);
}

const primitiveBlocks = [];
for (let index = 0; index < lines.length; index += 1) {
  if (!/^\s*\/\/\s*brush\s+\d+\s*$/.test(lines[index])) continue;
  const parsed = extractBalancedBlock(index + 1);
  if (!parsed) continue;
  primitiveBlocks.push(parsed);
  index = parsed.closeIndex;
}

const materials = new Map();
const axisMaterials = new Map();
const materialFlags = new Map();
const scales = new Map();
const surfaceFlags = new Map();
const extensionTokens = new Map();
const boxDimensions = { x: new Map(), y: new Map(), z: new Map() };
const boxShortest = new Map();
const substantialBoxShortest = new Map();
const brushFaceCounts = new Map();
const patchMaterials = new Map();
const patchDimensions = new Map();
let ordinaryBrushes = 0;
let axisAlignedBoxes = 0;
let angledBrushes = 0;
let patches = 0;
let terrains = 0;
let faceCount = 0;

for (const primitive of primitiveBlocks) {
  const blockText = primitive.block.join("\n");
  if (/\bpatchDef2\b/.test(blockText)) {
    patches += 1;
    const patchIndex = primitive.block.findIndex((line) => /\bpatchDef2\b/.test(line));
    let material = null;
    let dimensions = null;
    for (let i = patchIndex + 1; i < primitive.block.length; i += 1) {
      const trimmed = primitive.block[i].trim();
      if (!trimmed || trimmed === "{" || trimmed === "}") continue;
      if (!material && !trimmed.startsWith("(")) {
        material = trimmed.split(/\s+/)[0];
        continue;
      }
      const dimMatch = trimmed.match(/^\(\s*(\d+)\s+(\d+)\s+/);
      if (dimMatch) {
        dimensions = `${dimMatch[1]}x${dimMatch[2]}`;
        break;
      }
    }
    if (material) addCount(patchMaterials, material);
    if (dimensions) addCount(patchDimensions, dimensions);
    continue;
  }
  if (/\bterrainDef\b/.test(blockText)) {
    terrains += 1;
    continue;
  }

  const faces = primitive.block.map(parseFace).filter(Boolean);
  if (!faces.length) continue;
  ordinaryBrushes += 1;
  faceCount += faces.length;
  addCount(brushFaceCounts, String(faces.length));
  let hasAngledFace = false;
  for (const face of faces) {
    addCount(materials, face.texture);
    addCount(axisMaterials, `${face.axis}:${face.texture}`);
    addCount(materialFlags, `${face.texture}|${face.content},${face.surface},${face.value}|${face.extensions || "none"}`);
    addCount(scales, `${face.scale[0]},${face.scale[1]}`);
    addCount(surfaceFlags, `${face.content},${face.surface},${face.value}`);
    if (face.extensions) {
      for (const token of face.extensions.split(/\s+/)) addCount(extensionTokens, token);
    }
    if (face.axis === "angled") hasAngledFace = true;
  }
  if (hasAngledFace) angledBrushes += 1;

  if (faces.length === 6 && !hasAngledFace && faces.filter((face) => face.axis === "x").length === 2 && faces.filter((face) => face.axis === "y").length === 2 && faces.filter((face) => face.axis === "z").length === 2) {
    const coordinates = { x: [], y: [], z: [] };
    for (const face of faces) {
      const axisIndex = { x: 0, y: 1, z: 2 }[face.axis];
      coordinates[face.axis].push(face.points[0][axisIndex]);
    }
    const dimensions = {};
    for (const axis of ["x", "y", "z"]) {
      dimensions[axis] = Math.abs(Math.max(...coordinates[axis]) - Math.min(...coordinates[axis]));
      addCount(boxDimensions[axis], String(dimensions[axis]));
    }
    const shortest = Math.min(dimensions.x, dimensions.y, dimensions.z);
    addCount(boxShortest, String(shortest));
    if (shortest >= 16) addCount(substantialBoxShortest, String(shortest));
    axisAlignedBoxes += 1;
  }
}

const entityClasses = new Map();
const models = new Map();
const lightIntensities = new Map();
const spawnOrigins = [];
for (let index = 0; index < lines.length; index += 1) {
  if (!/^\s*\/\/\s*entity\s+\d+\s*$/.test(lines[index])) continue;
  const parsed = extractBalancedBlock(index + 1);
  if (!parsed) continue;
  const keys = {};
  let depth = 0;
  for (const line of parsed.block) {
    const trimmed = line.trim();
    if (trimmed === "{") { depth += 1; continue; }
    if (trimmed === "}") { depth -= 1; continue; }
    if (depth !== 1) continue;
    const match = line.match(keyPattern);
    if (match) keys[match[1]] = match[2];
  }
  if (keys.classname) addCount(entityClasses, keys.classname);
  if (keys.model) addCount(models, keys.model);
  if (keys.classname === "light" && keys.light) addCount(lightIntensities, keys.light);
  if (["info_player_deathmatch", "info_player_allied", "info_player_axis", "info_player_start"].includes(keys.classname) && keys.origin) {
    spawnOrigins.push({ classname: keys.classname, origin: keys.origin.split(/\s+/).map(Number), angle: keys.angle || null });
  }
  index = parsed.closeIndex;
}

const report = {
  source: path.relative(process.cwd(), inputPath).replace(/\\/g, "/"),
  sourceBytes: Buffer.byteLength(text, "utf8"),
  primitiveCounts: { ordinaryBrushes, axisAlignedBoxes, angledBrushes, faces: faceCount, patches, terrains },
  brushFaceCounts: sortedCounts(brushFaceCounts),
  dominantMaterials: sortedCounts(materials, 80),
  materialsByAxis: sortedCounts(axisMaterials, 120),
  materialFlags: sortedCounts(materialFlags, 160),
  faceScales: sortedCounts(scales, 30),
  faceFlags: sortedCounts(surfaceFlags, 30),
  extensionTokens: sortedCounts(extensionTokens, 50),
  boxDimensions: {
    x: sortedCounts(boxDimensions.x, 40),
    y: sortedCounts(boxDimensions.y, 40),
    z: sortedCounts(boxDimensions.z, 40),
    shortest: sortedCounts(boxShortest, 40),
    substantialShortest: sortedCounts(substantialBoxShortest, 40),
  },
  patchMaterials: sortedCounts(patchMaterials, 40),
  patchDimensions: sortedCounts(patchDimensions, 30),
  entityClasses: sortedCounts(entityClasses),
  models: sortedCounts(models, 80),
  lightIntensities: sortedCounts(lightIntensities),
  spawnOrigins,
};

const json = `${JSON.stringify(report, null, 2)}\n`;
if (outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, json, "utf8");
}
process.stdout.write(json);
