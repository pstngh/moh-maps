#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const inputPath = path.resolve(process.argv[2] || path.join(__dirname, "..", "..", "..", "aa", "obj_team2.map"));
const outputPath = path.resolve(process.argv[3] || path.join(__dirname, "..", "obj_team2-expansion-zone.json"));
const zone = { min: [3200, 384, -800], max: [5184, 2944, 960] };
const text = fs.readFileSync(inputPath, "utf8").replace(/\r\n/g, "\n");
const lines = text.split("\n");

function nextLine(from, predicate, label) {
  for (let index = from; index < lines.length; index += 1) {
    if (predicate(lines[index])) return index;
  }
  throw new Error(`Could not find ${label} after line ${from + 1}`);
}

function blockAt(openIndex) {
  let depth = 0;
  for (let index = openIndex; index < lines.length; index += 1) {
    for (const character of lines[index]) {
      if (character === "{") depth += 1;
      else if (character === "}") depth -= 1;
    }
    if (depth === 0) return { openIndex, closeIndex: index };
  }
  throw new Error(`Unclosed block at line ${openIndex + 1}`);
}

function overlaps(a, b) {
  return a.min.every((value, axis) => value <= b.max[axis] && a.max[axis] >= b.min[axis]);
}

function parseOrigin(value) {
  const result = value.trim().split(/\s+/).map(Number);
  return result.length === 3 && result.every(Number.isFinite) ? result : null;
}

function entityKeys(openIndex, closeIndex) {
  const keys = {};
  let depth = 0;
  for (let index = openIndex; index <= closeIndex; index += 1) {
    const trimmed = lines[index].trim();
    if (trimmed === "{") { depth += 1; continue; }
    if (trimmed === "}") { depth -= 1; continue; }
    if (depth !== 1) continue;
    const match = lines[index].match(/^\s*"([^"]+)"\s+"([^"]*)"\s*$/);
    if (match) keys[match[1]] = match[2];
  }
  return keys;
}

const entities = [];
for (let index = 0; index < lines.length; index += 1) {
  const marker = lines[index].match(/^\/\/ entity (\d+)\s*$/);
  if (!marker) continue;
  const openIndex = nextLine(index + 1, (line) => line.trim() === "{", "entity opening");
  const block = blockAt(openIndex);
  const keys = entityKeys(openIndex, block.closeIndex);
  const origin = keys.origin ? parseOrigin(keys.origin) : null;
  if (origin && origin.every((value, axis) => value >= zone.min[axis] && value <= zone.max[axis])) {
    entities.push({
      number: Number(marker[1]),
      line: index + 1,
      origin,
      classname: keys.classname || null,
      model: keys.model || null,
      angle: keys.angle || null,
      scale: keys.scale || null,
      targetname: keys.targetname || null,
    });
  }
  index = block.closeIndex;
}

const NUMBER = "[-+]?\\d+(?:\\.\\d*)?(?:[eE][-+]?\\d+)?";
const facePattern = new RegExp(`^\\s*\\(\\s*(${NUMBER})\\s+(${NUMBER})\\s+(${NUMBER})\\s*\\)\\s*\\(\\s*(${NUMBER})\\s+(${NUMBER})\\s+(${NUMBER})\\s*\\)\\s*\\(\\s*(${NUMBER})\\s+(${NUMBER})\\s+(${NUMBER})\\s*\\)`);

function cross(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function axisOfFace(line) {
  const match = line.match(facePattern);
  if (!match) return null;
  const n = match.slice(1, 10).map(Number);
  const p1 = n.slice(0, 3);
  const p2 = n.slice(3, 6);
  const p3 = n.slice(6, 9);
  const a = p2.map((value, axis) => value - p1[axis]);
  const b = p3.map((value, axis) => value - p1[axis]);
  const normal = cross(a, b).map(Math.abs);
  const magnitude = Math.hypot(...normal);
  if (!magnitude) return null;
  const normalized = normal.map((value) => value / magnitude);
  const maximum = Math.max(...normalized);
  if (maximum < 0.999999) return { axis: "angled", point: p1 };
  return { axis: ["x", "y", "z"][normalized.indexOf(maximum)], point: p1 };
}

const boxes = [];
for (let index = 0; index < lines.length; index += 1) {
  const marker = lines[index].match(/^\/\/ brush (\d+)\s*$/);
  if (!marker) continue;
  const openIndex = nextLine(index + 1, (line) => line.trim() === "{", "brush opening");
  const block = blockAt(openIndex);
  const faces = lines.slice(openIndex, block.closeIndex + 1).map(axisOfFace).filter(Boolean);
  if (
    faces.length === 6
    && !faces.some((face) => face.axis === "angled")
    && ["x", "y", "z"].every((axis) => faces.filter((face) => face.axis === axis).length === 2)
  ) {
    const bounds = { min: [], max: [] };
    for (const axis of ["x", "y", "z"]) {
      const axisIndex = { x: 0, y: 1, z: 2 }[axis];
      const values = faces.filter((face) => face.axis === axis).map((face) => face.point[axisIndex]);
      bounds.min.push(Math.min(...values));
      bounds.max.push(Math.max(...values));
    }
    if (overlaps(bounds, zone)) {
      boxes.push({
        number: Number(marker[1]),
        line: index + 1,
        ...bounds,
        size: bounds.max.map((value, axis) => value - bounds.min[axis]),
      });
    }
  }
  index = block.closeIndex;
}

function blockPayload(openIndex, closeIndex) {
  const output = [];
  for (let index = openIndex + 1; index < closeIndex; index += 1) {
    if (lines[index].trim()) output.push(index);
  }
  return output;
}

const terrains = [];
for (let index = 0; index < lines.length; index += 1) {
  if (lines[index].trim() !== "terrainDef") continue;
  const dimensionsIndex = nextLine(index + 1, (line) => /^\s*\d+\s+\d+\s+[-+]?\d+\s*$/.test(line), "terrain dimensions");
  const [width, height] = lines[dimensionsIndex].trim().split(/\s+/).map(Number);
  const originIndex = nextLine(dimensionsIndex + 1, (line) => /^\s*[-+\d.eE]+\s+[-+\d.eE]+\s+[-+\d.eE]+\s*$/.test(line), "terrain origin");
  const origin = lines[originIndex].trim().split(/\s+/).map(Number);
  const terrainBounds = {
    min: origin,
    max: [origin[0] + (width - 1) * 64, origin[1] + (height - 1) * 64, origin[2]],
  };
  const textureOpen = nextLine(originIndex + 1, (line) => line.trim() === "{", "texture opening");
  const textureClose = blockAt(textureOpen).closeIndex;
  const heightOpen = nextLine(textureClose + 1, (line) => line.trim() === "{", "height opening");
  const heightClose = blockAt(heightOpen).closeIndex;
  const heightRows = blockPayload(heightOpen, heightClose);
  if (heightRows.length !== width * height) {
    throw new Error(`Terrain at line ${index + 1} expected ${width * height} samples, got ${heightRows.length}`);
  }
  const samples = heightRows.map((row) => Number(lines[row].trim().split(/\s+/)[0]));
  const samplePoints = samples.map((sample, offset) => {
    const xIndex = offset % width;
    const yIndex = Math.floor(offset / width);
    return [origin[0] + xIndex * 64, origin[1] + yIndex * 64, origin[2] + sample];
  });
  const pointsInZone = samplePoints.filter((point) => (
    point[0] >= zone.min[0] && point[0] <= zone.max[0]
    && point[1] >= zone.min[1] && point[1] <= zone.max[1]
  ));
  if (
    pointsInZone.length
    || overlaps({ min: terrainBounds.min, max: [terrainBounds.max[0], terrainBounds.max[1], 960] }, zone)
  ) {
    terrains.push({
      line: index + 1,
      dimensions: [width, height],
      origin,
      xyBounds: [terrainBounds.min.slice(0, 2), terrainBounds.max.slice(0, 2)],
      zoneSampleCount: pointsInZone.length,
      zoneHeightRange: pointsInZone.length
        ? [Math.min(...pointsInZone.map((point) => point[2])), Math.max(...pointsInZone.map((point) => point[2]))]
        : null,
      zoneSamples: pointsInZone,
    });
  }
  index = heightClose;
}

const classCounts = {};
for (const entity of entities) {
  const classname = entity.classname || "<unknown>";
  classCounts[classname] = (classCounts[classname] || 0) + 1;
}

const report = {
  source: path.relative(process.cwd(), inputPath).replace(/\\/g, "/"),
  zone,
  entities,
  entityClassCounts: Object.entries(classCounts)
    .map(([classname, count]) => ({ classname, count }))
    .sort((a, b) => b.count - a.count || a.classname.localeCompare(b.classname)),
  axisAlignedBoxes: boxes,
  terrains,
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(`Wrote ${outputPath}`);
console.log(`Zone entities: ${entities.length}; axis boxes: ${boxes.length}; terrain tiles: ${terrains.length}`);
console.log(JSON.stringify(report.entityClassCounts, null, 2));
