#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const EXPECTED_SOURCE_SHA256 = "04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f";
const WORLD_BEGIN = "// CODEX OBJ_TEAM2 EXPANSION BRUSHES BEGIN";
const WORLD_END = "// CODEX OBJ_TEAM2 EXPANSION BRUSHES END";
const ENTITY_BEGIN = "// CODEX OBJ_TEAM2 EXPANSION ENTITIES BEGIN";
const ENTITY_END = "// CODEX OBJ_TEAM2 EXPANSION ENTITIES END";

function parseArgs(values) {
  const result = {};
  for (let index = 0; index < values.length; index += 2) {
    const key = values[index];
    if (!key || !key.startsWith("--") || values[index + 1] == null) throw new Error(`Malformed argument near ${key || "<end>"}`);
    result[key.slice(2)] = values[index + 1];
  }
  return result;
}

const args = parseArgs(process.argv.slice(2));
const sourcePath = path.resolve(args.source || path.join(__dirname, "..", "..", "..", "aa", "obj_team2.map"));
const outputRoot = path.resolve(args["output-root"] || path.join(__dirname, ".."));
const mapName = args["map-name"] || "codex_obj_team2_expanded";
const gameDirectory = args["game-directory"] || "obj";
const originalMap = args["original-map"] || "obj_team2";
const displayName = args["display-name"] || "V2 Facility: Expanded Complex";
if (!/^[A-Za-z0-9_]+$/.test(mapName)) throw new Error("Unsafe map name");
if (gameDirectory !== "obj") throw new Error("This derivative must remain in maps/obj");
if (originalMap !== "obj_team2") throw new Error("This derivative requires the retail obj_team2 scripts");

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

const sourceBuffer = fs.readFileSync(sourcePath);
const sourceSha256 = sha256(sourceBuffer);
if (sourceSha256 !== EXPECTED_SOURCE_SHA256) throw new Error(`Unexpected obj_team2 source hash: ${sourceSha256}`);
const sourceText = sourceBuffer.toString("utf8");
if (!sourceText.includes("\r\n") || sourceText.replace(/\r\n/g, "").includes("\n")) throw new Error("Expected the canonical CRLF obj_team2 source");
const sourceLines = sourceText.split("\r\n");

function blockAt(openIndex) {
  let depth = 0;
  for (let index = openIndex; index < sourceLines.length; index += 1) {
    for (const character of sourceLines[index]) {
      if (character === "{") depth += 1;
      else if (character === "}") depth -= 1;
    }
    if (depth === 0) return { openIndex, closeIndex: index };
  }
  throw new Error(`Unclosed block at source line ${openIndex + 1}`);
}

function entityKeys(openIndex, closeIndex) {
  const keys = {};
  let depth = 0;
  for (let index = openIndex; index <= closeIndex; index += 1) {
    const trimmed = sourceLines[index].trim();
    if (trimmed === "{") { depth += 1; continue; }
    if (trimmed === "}") { depth -= 1; continue; }
    if (depth !== 1) continue;
    const match = sourceLines[index].match(/^\s*"([^"]+)"\s+"([^"]*)"\s*$/);
    if (match) keys[match[1]] = match[2];
  }
  return keys;
}

function vector(value) {
  const values = value.trim().split(/\s+/).map(Number);
  return values.length === 3 && values.every(Number.isFinite) ? values : null;
}

const entityBlocks = [];
for (let index = 0; index < sourceLines.length; index += 1) {
  const marker = sourceLines[index].match(/^\/\/ entity (\d+)\s*$/);
  if (!marker) continue;
  if (sourceLines[index + 1] !== "{") throw new Error(`Unexpected entity opening at source line ${index + 2}`);
  const block = blockAt(index + 1);
  entityBlocks.push({ markerIndex: index, ...block, number: Number(marker[1]), keys: entityKeys(block.openIndex, block.closeIndex) });
  index = block.closeIndex;
}
if (entityBlocks.length !== 751) throw new Error(`Expected 751 point/brush entities, found ${entityBlocks.length}`);

const {
  firstEntityMarker,
  worldBrushBlocks,
  westFenceEntityNumbers,
  southEastFenceEntityNumbers,
  fenceEntityNumbers,
  fenceWorldBrushNumbers,
  removed,
  removedIndexes,
  retainedSourceLines,
} = require("./source_policy_obj_team2_expanded_v4")({ sourceLines, entityBlocks, blockAt, vector });

const T = Object.freeze({
  caulk: "common/caulk",
  bunker: "general_structure/bunker_wall",
  concrete: "general_structure/jh_conc512b",
  concreteA: "mohcommon/jeff-concrete-walla",
  concreteB: "mohcommon/jeff-concrete-wallb",
  floor: "algiers/whsflrset1_1b",
  step: "algiers/doccrtset_1stepsml",
  grate: "general_industrial/deckgrate_set1b",
  grateFence: "general_industrial/deckgrate_set1a",
  iron: "das_boot/ironwall1",
  rust: "german/rusty_iron",
  ibeam: "mohcommon/ibeam_1a",
  utilitySide: "general_industrial/utilitybox_side",
  utilityFront: "general_industrial/utilitybox_front",
  utilityTop: "general_industrial/utilboxtop",
  grass: "wilderness/m3l3grass_1rough",
  rock: "wilderness/wldrrckset1_1",
  sky: "sky/mohday1",
});

function fmt(value) {
  if (!Number.isFinite(value)) throw new Error(`Non-finite coordinate ${value}`);
  const rounded = Math.round(value * 1000) / 1000;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(3);
}

function material(texture, options = {}) {
  return {
    texture,
    shiftX: options.shiftX || 0,
    shiftY: options.shiftY || 0,
    rotation: options.rotation || 0,
    scaleX: options.scaleX == null ? 0.5 : options.scaleX,
    scaleY: options.scaleY == null ? 0.5 : options.scaleY,
    content: options.content || 0,
    surface: options.surface || 0,
    value: options.value || 0,
    extensions: options.extensions || "",
  };
}

const M = Object.freeze({
  caulk: material(T.caulk, { surface: 160 }),
  caulkDetail: material(T.caulk, { surface: 160, extensions: "+surfaceparm detail" }),
  bunker: material(T.bunker, { scaleX: 1, scaleY: 1, extensions: "surfaceDensity 64" }),
  bunkerDetail: material(T.bunker, { scaleX: 1, scaleY: 1, extensions: "+surfaceparm detail surfaceDensity 64" }),
  concrete: material(T.concrete),
  concreteDetail: material(T.concrete, { extensions: "+surfaceparm detail" }),
  concreteA: material(T.concreteA),
  concreteB: material(T.concreteB),
  floor: material(T.floor),
  floorDetail: material(T.floor, { extensions: "+surfaceparm detail" }),
  step: material(T.step, { extensions: "+surfaceparm detail" }),
  grate: material(T.grate, { surface: 32768, extensions: "+surfaceparm detail" }),
  grateFence: material(T.grateFence, { content: 8192, surface: 262176, extensions: "+surfaceparm detail" }),
  iron: material(T.iron, { surface: 32768, extensions: "+surfaceparm detail" }),
  rust: material(T.rust, { surface: 32768, extensions: "+surfaceparm detail" }),
  ibeam: material(T.ibeam, { surface: 32768, extensions: "+surfaceparm detail" }),
  utilitySide: material(T.utilitySide, { surface: 32768, extensions: "+surfaceparm detail" }),
  utilityFront: material(T.utilityFront, { surface: 32768, extensions: "+surfaceparm detail" }),
  utilityTop: material(T.utilityTop, { surface: 32768, extensions: "+surfaceparm detail" }),
  grass: material(T.grass, { scaleX: 1.5, scaleY: 1.5, extensions: "surfaceDensity 64" }),
  rock: material(T.rock, { scaleX: 1.5, scaleY: 1.5, extensions: "surfaceDensity 64" }),
  sky: material(T.sky, { shiftX: 22, shiftY: -36, rotation: -180, scaleX: 30.75, scaleY: -14.25, surface: 276 }),
});

const faceNames = ["xMin", "xMax", "yMin", "yMax", "zMin", "zMax"];

function face(points, spec) {
  const pointText = points.map((point) => `( ${point.map(fmt).join(" ")} )`).join(" ");
  return `${pointText} ${spec.texture} ${fmt(spec.shiftX)} ${fmt(spec.shiftY)} ${fmt(spec.rotation)} ${fmt(spec.scaleX)} ${fmt(spec.scaleY)} ${spec.content} ${spec.surface} ${spec.value}${spec.extensions ? ` ${spec.extensions}` : ""}`;
}

function faceSet(hidden, visible = {}) {
  return Object.fromEntries(faceNames.map((name) => [name, visible[name] || hidden]));
}

function boxBrush(min, max, specs) {
  if (min.some((value, axis) => !Number.isFinite(value) || value >= max[axis])) throw new Error(`Invalid box ${JSON.stringify({ min, max })}`);
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  const planes = [
    [[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]],
    [[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]],
    [[16, minY, -16], [0, minY, 0], [16, minY, 16]],
    [[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]],
    [[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]],
    [[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]],
  ];
  return ["{", ...planes.map((points, index) => face(points, specs[faceNames[index]])), "}"].join("\r\n");
}

const brushes = [];
const roleCounts = new Map();
const usedMaterials = new Set();

function addBox(role, min, max, visible, options = {}) {
  const visibleSpecs = Object.values(visible);
  if (!visibleSpecs.length) throw new Error(`Brush ${role} has no visible material`);
  // Revision 2 deliberately skins every face of every added brush. Stock-map
  // boundary brushes can be approached from directions the original author
  // never exposed; caulk/nodraw fallbacks therefore become visible holes.
  const specs = faceSet(options.fallback || visibleSpecs[0], visible);
  for (const spec of Object.values(specs)) usedMaterials.add(spec.texture);
  brushes.push({
    role,
    min: [...min],
    max: [...max],
    detail: Boolean(options.detail),
    faceTextures: Object.fromEntries(Object.entries(specs).map(([name, spec]) => [name, spec.texture])),
    text: boxBrush(min, max, specs),
  });
  roleCounts.set(role, (roleCounts.get(role) || 0) + 1);
}

function addUtility(role, min, max, frontFace) {
  const visible = { zMax: M.utilityTop };
  for (const side of ["xMin", "xMax", "yMin", "yMax"]) visible[side] = side === frontFace ? M.utilityFront : M.utilitySide;
  addBox(role, min, max, visible, { detail: true });
}

const { addedEntities } = require("./layout_obj_team2_forest_v4")({ addBox, addUtility, M });

const worldCloseIndex = firstEntityMarker - 1;
let highestWorldBrush = -1;
for (let index = 0; index < worldCloseIndex; index += 1) {
  const match = sourceLines[index].match(/^\/\/ brush (\d+)$/);
  if (match) highestWorldBrush = Math.max(highestWorldBrush, Number(match[1]));
}
if (highestWorldBrush < 5000) throw new Error(`Unexpected world brush high-water mark: ${highestWorldBrush}`);

const brushLines = [WORLD_BEGIN];
brushes.forEach((brush, index) => {
  brushLines.push(`// brush ${highestWorldBrush + 1 + index}`, ...brush.text.split("\r\n"));
});
brushLines.push(WORLD_END);

const outputLines = [];
for (let index = 0; index < sourceLines.length; index += 1) {
  if (removedIndexes.has(index)) continue;
  if (index === worldCloseIndex) outputLines.push(...brushLines);
  outputLines.push(sourceLines[index]);
}
if (outputLines[outputLines.length - 1] === "") outputLines.pop();
outputLines.push(ENTITY_BEGIN);
let nextEntityNumber = Math.max(...entityBlocks.map((entity) => entity.number)) + 1;
for (const entity of addedEntities) {
  outputLines.push(`// entity ${nextEntityNumber}`, ...entity.text.split("\r\n"));
  nextEntityNumber += 1;
}
outputLines.push(ENTITY_END, "");
const outputText = outputLines.join("\r\n");

const mapRoot = path.join(outputRoot, "main", "maps", gameDirectory);
fs.mkdirSync(mapRoot, { recursive: true });
const mapPath = path.join(mapRoot, `${mapName}.map`);
const scriptPath = path.join(mapRoot, `${mapName}.scr`);
const precachePath = path.join(mapRoot, `${mapName}_precache.scr`);
fs.writeFileSync(mapPath, outputText);
fs.writeFileSync(scriptPath, "// Thin wrapper: retail obj_team2.scr remains authoritative.\nmain:\n\texec maps/obj/obj_team2.scr\nend\n");
fs.writeFileSync(precachePath, "// Thin wrapper: retail assets remain in Pak0-Pak6.\nexec maps/obj/obj_team2_precache.scr\ncache models/fx/bazookaexplosion_dm.tik\n");

const { report, fixedViews } = require("./report_obj_team2_expanded_v4")({
  sourceLines, retainedSourceLines, sourceBuffer, sourceSha256, sourcePath, outputRoot, outputText,
  mapName, gameDirectory, originalMap, displayName, entityBlocks, vector, removed,
  worldBrushBlocks, westFenceEntityNumbers, southEastFenceEntityNumbers, fenceEntityNumbers,
  fenceWorldBrushNumbers, brushes, addedEntities, roleCounts, usedMaterials,
});
const reportPath = path.join(outputRoot, `${mapName}-mirror-report.json`);
const designPath = path.join(outputRoot, `${mapName}-design-report.json`);
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
fs.writeFileSync(designPath, `${JSON.stringify({ schemaVersion: 4, revision: 4, mapName, fixedViews, design: report.expansion, preservation: report.preservation }, null, 2)}\n`);
console.log(`Generated ${mapPath}`);
console.log(`Added ${brushes.length} brushes and ${addedEntities.length} entities; removed every stock fence component and completed the forest-side exterior loop`);
console.log(`SHA256 ${report.output.sha256}`);
