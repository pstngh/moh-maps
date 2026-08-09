#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function parseArgs(values) {
  const result = {};
  for (let index = 0; index < values.length; index += 2) {
    const key = values[index];
    if (!key || !key.startsWith("--") || values[index + 1] == null) {
      throw new Error(`Malformed argument near ${key || "<end>"}`);
    }
    result[key.slice(2)] = values[index + 1];
  }
  return result;
}

function parseVector(value, fallback) {
  if (value == null) return fallback;
  const parsed = value.trim().split(/[ ,]+/).map(Number);
  if (parsed.length !== 3 || parsed.some((number) => !Number.isFinite(number))) {
    throw new Error(`Expected three finite coordinates, got ${value}`);
  }
  return parsed;
}

function parseRange(value, fallback) {
  if (value == null) return fallback;
  const parsed = value.split(/[,-]+/).map(Number);
  if (parsed.length !== 2 || parsed.some((number) => !Number.isInteger(number))) {
    throw new Error(`Expected integer range, got ${value}`);
  }
  return parsed;
}

if (process.argv.includes("--help")) {
  console.log("Usage: node inspect_map_entities.js --input <map> [--output <json>] [--min x,y,z] [--max x,y,z] [--entities first-last] [--world-brushes first-last]");
  process.exit(0);
}

const args = parseArgs(process.argv.slice(2));
const inputPath = path.resolve(args.input || "aa/obj_team2.map");
const outputPath = args.output ? path.resolve(args.output) : null;
const zone = {
  min: parseVector(args.min, [-Infinity, -Infinity, -Infinity]),
  max: parseVector(args.max, [Infinity, Infinity, Infinity]),
};
const entityRange = parseRange(args.entities, [0, Number.MAX_SAFE_INTEGER]);
const worldBrushRange = parseRange(args["world-brushes"], [0, Number.MAX_SAFE_INTEGER]);
const lines = fs.readFileSync(inputPath, "utf8").replace(/\r\n/g, "\n").split("\n");

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

function include(bounds, point) {
  for (let axis = 0; axis < 3; axis += 1) {
    bounds.min[axis] = Math.min(bounds.min[axis], point[axis]);
    bounds.max[axis] = Math.max(bounds.max[axis], point[axis]);
  }
}

function overlaps(bounds) {
  return bounds.min.every((value, axis) => value <= zone.max[axis] && bounds.max[axis] >= zone.min[axis]);
}

const numberPattern = "[-+]?\\d+(?:\\.\\d*)?(?:[eE][-+]?\\d+)?";
const facePattern = new RegExp(`^\\s*\\(\\s*(${numberPattern})\\s+(${numberPattern})\\s+(${numberPattern})\\s*\\)\\s*\\(\\s*(${numberPattern})\\s+(${numberPattern})\\s+(${numberPattern})\\s*\\)\\s*\\(\\s*(${numberPattern})\\s+(${numberPattern})\\s+(${numberPattern})\\s*\\)\\s+(\\S+)`);

function geometry(openIndex, closeIndex) {
  const bounds = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  const materialCounts = new Map();
  let faceCount = 0;
  for (let index = openIndex; index <= closeIndex; index += 1) {
    const match = lines[index].match(facePattern);
    if (!match) continue;
    faceCount += 1;
    const coordinates = match.slice(1, 10).map(Number);
    for (let point = 0; point < 3; point += 1) include(bounds, coordinates.slice(point * 3, point * 3 + 3));
    materialCounts.set(match[10], (materialCounts.get(match[10]) || 0) + 1);
  }
  return {
    bounds: faceCount ? bounds : null,
    faceCount,
    materials: [...materialCounts.entries()]
      .map(([material, count]) => ({ material, count }))
      .sort((a, b) => b.count - a.count || a.material.localeCompare(b.material)),
  };
}

function keysAt(openIndex, closeIndex) {
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
  const number = Number(marker[1]);
  const openIndex = index + 1;
  const block = blockAt(openIndex);
  if (number >= entityRange[0] && number <= entityRange[1]) {
    const keys = keysAt(openIndex, block.closeIndex);
    const spatial = geometry(openIndex, block.closeIndex);
    const origin = keys.origin ? parseVector(keys.origin) : null;
    const relevant = spatial.bounds ? overlaps(spatial.bounds) : origin && origin.every((value, axis) => value >= zone.min[axis] && value <= zone.max[axis]);
    if (relevant) {
      entities.push({ number, line: index + 1, classname: keys.classname || null, origin, targetname: keys.targetname || null, model: keys.model || null, ...spatial });
    }
  }
  index = block.closeIndex;
}

const worldBrushes = [];
const firstEntityLine = lines.findIndex((line) => /^\/\/ entity \d+\s*$/.test(line));
for (let index = 0; index < (firstEntityLine < 0 ? lines.length : firstEntityLine); index += 1) {
  const marker = lines[index].match(/^\/\/ brush (\d+)\s*$/);
  if (!marker) continue;
  const number = Number(marker[1]);
  const openIndex = index + 1;
  const block = blockAt(openIndex);
  if (number >= worldBrushRange[0] && number <= worldBrushRange[1]) {
    const spatial = geometry(openIndex, block.closeIndex);
    if (spatial.bounds && overlaps(spatial.bounds)) worldBrushes.push({ number, line: index + 1, ...spatial });
  }
  index = block.closeIndex;
}

const report = {
  schemaVersion: 1,
  source: path.relative(process.cwd(), inputPath).replace(/\\/g, "/"),
  filters: { zone, entityRange, worldBrushRange },
  entities,
  worldBrushes,
};
const json = `${JSON.stringify(report, null, 2)}\n`;
if (outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, json);
  console.log(`Wrote ${outputPath}`);
}
process.stdout.write(json);
