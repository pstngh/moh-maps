#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function parseArgs(values) {
  const result = {};
  for (let index = 0; index < values.length; index += 2) {
    const key = values[index];
    if (!key || !key.startsWith("--") || values[index + 1] == null) throw new Error(`Malformed argument near ${key || "<end>"}`);
    result[key.slice(2)] = values[index + 1];
  }
  return result;
}

function nextIndex(lines, start, predicate, description) {
  for (let index = start; index < lines.length; index += 1) if (predicate(lines[index])) return index;
  throw new Error(`Could not find ${description} after line ${start}`);
}

function closeBrace(lines, openIndex) {
  let depth = 0;
  for (let index = openIndex; index < lines.length; index += 1) {
    const trimmed = lines[index].trim();
    if (trimmed === "{") depth += 1;
    else if (trimmed === "}") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  throw new Error(`Unclosed brace at line ${openIndex + 1}`);
}

if (process.argv.includes("--help")) {
  console.log("Usage: node inspect_map_terrain.js --input <map> [--output <json>]");
  process.exit(0);
}

const args = parseArgs(process.argv.slice(2));
const inputPath = path.resolve(args.input || "aa/obj_team2.map");
const outputPath = args.output ? path.resolve(args.output) : null;
const lines = fs.readFileSync(inputPath, "utf8").replace(/\r\n/g, "\n").split("\n");
const terrains = [];

for (let index = 0; index < lines.length; index += 1) {
  if (lines[index].trim() !== "terrainDef") continue;
  const dimensionsIndex = nextIndex(lines, index + 1, (line) => /^\s*\d+\s+\d+\s+[-+]?\d+\s*$/.test(line), "terrain dimensions");
  const [width, height, flags] = lines[dimensionsIndex].trim().split(/\s+/).map(Number);
  if (width < 2 || height < 2) throw new Error(`Invalid terrain dimensions at line ${dimensionsIndex + 1}`);
  const originIndex = nextIndex(lines, dimensionsIndex + 1, (line) => /^\s*[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s*$/.test(line), "terrain origin");
  const origin = lines[originIndex].trim().split(/\s+/).map(Number);
  const textureOpen = nextIndex(lines, originIndex + 1, (line) => line.trim() === "{", "texture grid");
  const textureClose = closeBrace(lines, textureOpen);
  const heightOpen = nextIndex(lines, textureClose + 1, (line) => line.trim() === "{", "height grid");
  const heightClose = closeBrace(lines, heightOpen);
  const payload = lines.slice(heightOpen + 1, heightClose).map((line) => line.trim()).filter(Boolean);
  if (payload.length !== width * height) throw new Error(`Terrain at line ${index + 1} has ${payload.length}/${width * height} height samples`);
  const samples = payload.map((line, sampleIndex) => {
    const match = line.match(/^([-+]?\d+(?:\.\d+)?)/);
    if (!match) throw new Error(`Malformed terrain height at line ${heightOpen + 2 + sampleIndex}`);
    const row = Math.floor(sampleIndex / width);
    const column = sampleIndex % width;
    const offset = Number(match[1]);
    return {
      column,
      row,
      x: origin[0] + column * 64,
      y: origin[1] + row * 64,
      z: origin[2] + offset,
      offset,
    };
  });
  const zValues = samples.map((sample) => sample.z);
  terrains.push({
    number: terrains.length,
    sourceLine: index + 1,
    width,
    height,
    flags,
    origin,
    bounds: {
      min: [origin[0], origin[1], Math.min(...zValues)],
      max: [origin[0] + (width - 1) * 64, origin[1] + (height - 1) * 64, Math.max(...zValues)],
    },
    samples,
  });
  index = heightClose;
}

const report = {
  schemaVersion: 1,
  source: path.relative(process.cwd(), inputPath).replace(/\\/g, "/"),
  terrainCount: terrains.length,
  sampleCount: terrains.reduce((sum, terrain) => sum + terrain.samples.length, 0),
  terrains,
};
const text = `${JSON.stringify(report, null, 2)}\n`;
if (outputPath) {
  fs.writeFileSync(outputPath, text);
  console.log(`Wrote ${outputPath}: ${report.terrainCount} terrains / ${report.sampleCount} samples`);
} else {
  process.stdout.write(text);
}
