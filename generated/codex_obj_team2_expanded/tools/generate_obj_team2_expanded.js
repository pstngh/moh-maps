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
const displayName = args["display-name"] || "V2 Facility: East Annex";
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

const connectorObstructionNumbers = new Set([666, 674, 675, 679, 680]);
const removed = entityBlocks.filter(({ number, keys }) => {
  const origin = keys.origin ? vector(keys.origin) : null;
  const footprintFoliage = Boolean(
    origin
    && (keys.classname || "").startsWith("static_natural_")
    && !keys.targetname
    && origin[0] >= 3400 && origin[0] <= 5050
    && origin[1] >= 480 && origin[1] <= 2700
    && origin[2] >= -600 && origin[2] <= -350
  );
  const connectorObstruction = connectorObstructionNumbers.has(number)
    && !keys.targetname
    && ["detail", "func_group"].includes(keys.classname);
  return footprintFoliage || connectorObstruction;
});
if (removed.length !== 14 || [...connectorObstructionNumbers].some((number) => !removed.some((entity) => entity.number === number))) {
  throw new Error(`Expected nine footprint foliage entities and five connector obstructions, found ${removed.length}`);
}
const removedIndexes = new Set();
for (const entity of removed) {
  for (let index = entity.markerIndex; index <= entity.closeIndex; index += 1) removedIndexes.add(index);
}
const retainedSourceLines = sourceLines.filter((_line, index) => !removedIndexes.has(index));

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

// Raised motor-pool/service deck. Revision 2 treats every added surface as
// potentially visible from the newly opened stock boundary.
addBox("service_deck", [3584, 640, -544], [4800, 2496, -384], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete });

// Two independent, 288-unit-wide bot-safe approaches from the original Axis
// exterior. Nine 12-unit risers stay below the measured stock step grammar.
for (const yRange of [[896, 1184], [2016, 2304]]) {
  for (let index = 0; index < 9; index += 1) {
    const minX = 3296 + index * 32;
    const maxX = minX + 32;
    const top = -480 + index * 12;
    addBox("connector_steps", [minX, yRange[0], -544], [maxX, yRange[1], top], { xMin: M.step, xMax: M.step, yMin: M.concreteB, yMax: M.concreteB, zMax: M.step }, { detail: true });
  }
}

// Finished retaining walls hide the raised slab from all approach directions
// while leaving both connections permanently open.
for (const [minY, maxY] of [[640, 896], [1184, 2016], [2304, 2496]]) {
  addBox("west_retaining", [3584, minY, -384], [3616, maxY, -224], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB, zMax: M.concrete });
}
addBox("south_retaining", [3616, 640, -384], [4304, 672, -224], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete });
addBox("north_retaining", [3616, 2464, -384], [4304, 2496, -224], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete });

// Complete concrete maintenance hall. Both interior and exterior faces are
// visible and solid; the west facade keeps three broad, permanently open bays.
addBox("hall_east_wall", [4768, 768, -384], [4800, 2368, 208], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB });
addBox("hall_south_wall", [4304, 768, -384], [4768, 800, 208], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker });
addBox("hall_north_wall", [4304, 2336, -384], [4768, 2368, 208], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker });
for (const [minY, maxY] of [[768, 896], [1184, 1376], [1664, 1856], [2144, 2368]]) {
  addBox("hall_west_pillar", [4304, minY, -384], [4336, maxY, 208], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB });
}
for (const [minY, maxY] of [[896, 1184], [1376, 1664], [1856, 2144]]) {
  addBox("hall_bay_lintel", [4304, minY, -80], [4336, maxY, 208], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB, zMin: M.concrete, zMax: M.concrete });
  addBox("hall_bay_frame", [4288, minY, -384], [4304, minY + 16, -64], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
  addBox("hall_bay_frame", [4288, maxY - 16, -384], [4304, maxY, -64], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
  addBox("hall_bay_frame", [4288, minY, -80], [4304, maxY, -64], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
  addBox("hall_bay_awning", [4256, minY + 24, -64], [4304, maxY - 24, -32], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
}
addBox("hall_roof", [4304, 768, 208], [4800, 2368, 240], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.concreteB, yMax: M.concreteB, zMin: M.concrete, zMax: M.concrete });
addBox("roof_parapet", [4304, 768, 240], [4320, 2368, 288], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
addBox("roof_parapet", [4784, 768, 240], [4800, 2368, 288], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
addBox("roof_parapet", [4320, 768, 240], [4784, 784, 288], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
addBox("roof_parapet", [4320, 2352, 240], [4784, 2368, 288], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });

// Ceiling ribs, facade overhangs, and rooftop equipment make the hall read as
// a finished facility instead of an empty box.
for (const y of [912, 1200, 1488, 1776, 2064, 2304]) {
  addBox("hall_ceiling_beam", [4336, y, 160], [4768, y + 16, 192], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
}
for (const vent of [
  [[4400, 928, 240], [4496, 1120, 320]],
  [[4584, 1376, 240], [4680, 1568, 304]],
  [[4400, 1888, 240], [4496, 2080, 320]],
]) {
  addBox("roof_vent", vent[0], vent[1], { xMin: M.rust, xMax: M.rust, yMin: M.rust, yMax: M.rust, zMin: M.iron, zMax: M.iron }, { detail: true });
  addBox("roof_vent_cap", [vent[0][0] - 8, vent[0][1] - 8, vent[1][2]], [vent[1][0] + 8, vent[1][1] + 8, vent[1][2] + 16], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
}

// Internal mezzanine and a 128-unit-wide, 16-unit-rise stair. Revision 2 uses
// a solid floor instead of an alpha grate so it cannot disappear edge-on.
for (let index = 0; index < 20; index += 1) {
  const minY = 864 + index * 40;
  addBox("mezzanine_steps", [4384, minY, -384], [4512, minY + 40, -368 + index * 16], { xMin: M.step, xMax: M.step, yMin: M.step, yMax: M.step, zMin: M.step, zMax: M.step }, { detail: true });
}
addBox("mezzanine_floor", [4384, 1664, -80], [4768, 2320, -64], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.floorDetail }, { detail: true });
for (const y of [1696, 1824, 1952, 2080, 2208, 2304]) {
  addBox("mezzanine_rail_post", [4368, y, -64], [4384, y + 16, 48], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
}
for (const [minZ, maxZ] of [[-8, 0], [48, 56]]) {
  addBox("mezzanine_rail", [4368, 1696, minZ], [4384, 2320, maxZ], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
}
for (const y of [1728, 2048, 2288]) {
  addBox("mezzanine_support", [4368, y, -384], [4400, y + 32, -80], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
}

// Solid loading canopy and a central waist-high dispatch island divide the yard
// into close-range loops without introducing alpha or one-sided surfaces.
for (const x of [3744, 4160]) {
  for (const y of [1296, 1760]) {
    addBox("canopy_column", [x, y, -384], [x + 32, y + 32, 48], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
  }
}
addBox("canopy_roof", [3728, 1280, 48], [4208, 1808, 80], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
addBox("canopy_beam", [3728, 1280, 16], [4208, 1296, 48], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
addBox("canopy_beam", [3728, 1792, 16], [4208, 1808, 48], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
addBox("dispatch_island", [3920, 1440, -384], [4016, 1648, -272], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.concreteB, yMax: M.concreteB, zMin: M.concrete, zMax: M.concrete }, { detail: true });

// South and north service sheds fill the previously empty ends of the deck.
// Each has two open inward-facing bays, a divider, roof, and finished parapet.
function addServiceShed(prefix, yMin, yMax, openingSide) {
  const facadeMin = openingSide === "north" ? yMax - 32 : yMin;
  const facadeMax = openingSide === "north" ? yMax : yMin + 32;
  const backMin = openingSide === "north" ? yMin : yMax - 32;
  const backMax = openingSide === "north" ? yMin + 32 : yMax;
  const dividerMin = openingSide === "north" ? backMax : facadeMax;
  const dividerMax = openingSide === "north" ? facadeMin : backMin;
  addBox(`${prefix}_west_wall`, [3616, yMin, -384], [3648, yMax, 64], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB });
  addBox(`${prefix}_east_wall`, [4176, yMin, -384], [4208, yMax, 64], { xMin: M.bunker, xMax: M.bunker, yMin: M.concreteB, yMax: M.concreteB });
  addBox(`${prefix}_back_wall`, [3648, backMin, -384], [4176, backMax, 64], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker });
  for (const [xMin, xMax] of [[3648, 3712], [3904, 3976], [4144, 4176]]) {
    addBox(`${prefix}_facade_pillar`, [xMin, facadeMin, -384], [xMax, facadeMax, 64], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker });
  }
  for (const [xMin, xMax] of [[3712, 3904], [3976, 4144]]) {
    addBox(`${prefix}_facade_lintel`, [xMin, facadeMin, -80], [xMax, facadeMax, 64], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMin: M.concrete, zMax: M.concrete });
  }
  addBox(`${prefix}_divider`, [3920, dividerMin, -384], [3952, dividerMax, -64], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.bunker, yMax: M.bunker, zMin: M.concrete, zMax: M.concrete });
  addBox(`${prefix}_roof`, [3616, yMin, 64], [4208, yMax, 96], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.concrete });
  addBox(`${prefix}_parapet`, [3616, yMin, 96], [3632, yMax, 128], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
  addBox(`${prefix}_parapet`, [4192, yMin, 96], [4208, yMax, 128], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
  addBox(`${prefix}_parapet`, [3632, yMin, 96], [4192, yMin + 16, 128], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
  addBox(`${prefix}_parapet`, [3632, yMax - 16, 96], [4192, yMax, 128], { xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMax: M.concrete }, { detail: true });
}
addServiceShed("south_shed", 672, 864, "north");
addServiceShed("north_shed", 2304, 2464, "south");

for (const box of [
  [[3696, 1040, -384], [3824, 1088, -272]],
  [[4056, 1040, -384], [4184, 1088, -272]],
  [[3696, 2112, -384], [3824, 2160, -272]],
  [[4056, 2112, -384], [4184, 2160, -272]],
  [[3664, 1504, -384], [3712, 1632, -288]],
  [[4224, 1504, -384], [4272, 1632, -288]],
]) {
  addBox("yard_cover", box[0], box[1], { xMin: M.concreteB, xMax: M.concreteB, yMin: M.concreteB, yMax: M.concreteB, zMin: M.concrete, zMax: M.concrete }, { detail: true });
}

for (const [x, y] of [
  [3664, 1200], [3664, 1936], [3792, 1200], [3792, 1936],
  [4112, 1200], [4112, 1936], [4240, 1200], [4240, 1936],
]) {
  addBox("yard_bollard", [x, y, -384], [x + 16, y + 16, -256], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron, zMin: M.iron, zMax: M.iron }, { detail: true });
}

addUtility("utility_bank", [3736, 720, -384], [3848, 816, -240], "yMax");
addUtility("utility_bank", [4000, 720, -384], [4112, 816, -272], "yMax");
addUtility("utility_bank", [3736, 2336, -384], [3848, 2432, -240], "yMin");
addUtility("utility_bank", [4000, 2336, -384], [4112, 2432, -272], "yMin");
addUtility("utility_bank", [4424, 1224, -384], [4520, 1320, -240], "xMin");
addUtility("utility_bank", [4624, 1224, -384], [4720, 1320, -272], "xMin");
addUtility("utility_bank", [4560, 2176, -64], [4704, 2272, 64], "yMin");

// Solid service ducts echo the rectangular pipe/vent construction already used
// throughout obj_team2 without relying on custom or alpha-textured assets.
addBox("service_duct", [4688, 816, 48], [4752, 1632, 112], { xMin: M.rust, xMax: M.rust, yMin: M.rust, yMax: M.rust, zMin: M.iron, zMax: M.iron }, { detail: true });
for (const y of [944, 1200, 1456]) {
  addBox("duct_bracket", [4664, y, 32], [4760, y + 16, 128], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam, zMin: M.ibeam, zMax: M.ibeam }, { detail: true });
}
function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) lines.push(`"${key}" "${value}"`);
  lines.push("}");
  return lines.join("\r\n");
}

const addedEntities = [];
function addEntity(role, classname, properties) {
  addedEntities.push({ role, classname, properties, text: pointEntity(classname, properties) });
}

for (const spawn of [
  [3744, 840, -336, 30],
  [4056, 840, -336, 150],
  [3744, 2320, -336, 330],
  [4056, 2320, -336, 210],
  [4208, 1120, -336, 180],
  [4592, 1040, -336, 180],
  [4624, 1512, -336, 180],
  [4576, 2072, -16, 200],
]) {
  addEntity("dm_spawn", "info_player_deathmatch", { origin: `${spawn[0]} ${spawn[1]} ${spawn[2]}`, angle: String(spawn[3]) });
}

addEntity("vehicle", "static_vehicle_german_opeltruck", { model: "static//vehicle_opeltruck.tik", origin: "3944 2104 -384", angle: "90", scale: "1.10", testanim: "idle" });
for (const [x, y, z, angle] of [
  [4672, 864, -384, 280],
  [4632, 904, -384, 10],
  [4672, 864, -350, 260],
  [4432, 2240, -64, 90],
  [3824, 752, -384, 20],
  [4080, 752, -384, 340],
  [3824, 2384, -384, 160],
  [4080, 2384, -384, 200],
]) {
  addEntity("crate", "static_item_nazicrate", { model: "static//nazi_crate.tik", origin: `${x} ${y} ${z}`, angle: String(angle), scale: "1.0", testanim: "idle" });
}

function addLamp(role, fixtureOrigin, coronaOrigin, lightOrigin, angle, intensity) {
  addEntity(role, "static_lamp_lightbulb-caged", { model: "static//lightbulb_caged.tik", origin: fixtureOrigin.join(" "), angle: String(angle), scale: "1.40", testanim: "idle" });
  addEntity(role, "static_corona_orange", { model: "static//corona_orange.tik", origin: coronaOrigin.join(" "), scale: "1.0", testanim: "idle" });
  addEntity(role, "light", { origin: lightOrigin.join(" "), light: String(intensity), _color: "1.0 0.9 0.8", overbright_range: "0.15" });
}

for (const y of [1040, 1520, 2048]) addLamp("bay_light", [4294, y, -112], [4288, y, -115], [4232, y, -112], 0, 80);
for (const y of [1040, 1520, 2048]) addLamp("hall_light", [4544, y, 196], [4544, y, 190], [4544, y, 128], -2, 80);
for (const x of [3872, 4064]) addLamp("canopy_light", [x, 1544, 36], [x, 1544, 30], [x, 1544, -32], -2, 60);
for (const x of [3792, 4056]) addLamp("south_shed_light", [x, 768, 52], [x, 768, 46], [x, 768, -16], -2, 60);
for (const x of [3792, 4056]) addLamp("north_shed_light", [x, 2400, 52], [x, 2400, 46], [x, 2400, -16], -2, 60);
const firstEntityMarker = sourceLines.indexOf("// entity 1");
if (firstEntityMarker < 0 || sourceLines[firstEntityMarker - 1] !== "}") throw new Error("Could not locate the worldspawn close before entity 1");
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

const entityRoleCounts = {};
const entityClassCounts = {};
for (const entity of addedEntities) {
  entityRoleCounts[entity.role] = (entityRoleCounts[entity.role] || 0) + 1;
  entityClassCounts[entity.classname] = (entityClassCounts[entity.classname] || 0) + 1;
}
const allMinimum = [Math.min(...brushes.map((brush) => brush.min[0])), Math.min(...brushes.map((brush) => brush.min[1])), Math.min(...brushes.map((brush) => brush.min[2]))];
const allMaximum = [Math.max(...brushes.map((brush) => brush.max[0])), Math.max(...brushes.map((brush) => brush.max[1])), Math.max(...brushes.map((brush) => brush.max[2]))];
const fixedViews = [
  { id: "reported_stock_side", origin: [3000, 1544, -300], viewangles: [-5, 0, 0] },
  { id: "stock_side_overview", origin: [3000, 1544, 80], viewangles: [10, 0, 0] },
  { id: "south_connection", origin: [3120, 1040, -360], viewangles: [-5, 0, 0] },
  { id: "north_connection", origin: [3400, 2160, -300], viewangles: [-5, 0, 0] },
  { id: "annex_facade", origin: [3712, 1544, -280], viewangles: [-5, 0, 0] },
  { id: "south_shed", origin: [3840, 1120, -300], viewangles: [-5, 270, 0] },
  { id: "north_shed", origin: [3840, 2112, -300], viewangles: [-5, 90, 0] },
  { id: "yard_south_lane", origin: [3680, 1120, -300], viewangles: [-5, 35, 0] },
  { id: "yard_north_lane", origin: [3680, 2080, -300], viewangles: [-5, 325, 0] },
  { id: "hall_center", origin: [4560, 1200, -300], viewangles: [-5, 90, 0] },
  { id: "hall_stair", origin: [4624, 960, -300], viewangles: [-10, 160, 0] },
  { id: "mezzanine", origin: [4580, 2100, 0], viewangles: [5, 225, 0] },
  { id: "east_return", origin: [4680, 2000, -300], viewangles: [-5, 180, 0] },
  { id: "overhead", origin: [3300, 400, 350], viewangles: [25, 35, 0] },
];
const report = {
  schemaVersion: 2,
  revision: 2,
  transform: "revision 2 byte-preserving obj_team2 expansion: preserve retail gameplay, fully skin every added brush, remove transparent construction materials, and add two complete service sheds to the east annex",
  sourceMap: path.relative(outputRoot, sourcePath).replace(/\\/g, "/"),
  sourceBytes: sourceBuffer.length,
  sourceSha256,
  mapName,
  gameDirectory,
  originalMap,
  displayName,
  output: { bytes: Buffer.byteLength(outputText), sha256: sha256(outputText) },
  preservation: {
    sourceLineCount: sourceLines.length,
    retainedSourceLineCount: retainedSourceLines.length,
    retainedSourceSha256: sha256(retainedSourceLines.join("\r\n")),
    removedEntityNumbers: removed.map((entity) => entity.number),
    removedEntities: removed.map((entity) => ({ number: entity.number, classname: entity.keys.classname, origin: entity.keys.origin ? vector(entity.keys.origin) : null, model: entity.keys.model || null, targetname: entity.keys.targetname || null })),
    originalDoorCount: entityBlocks.filter((entity) => entity.keys.classname === "func_rotatingdoor").length,
    originalTargetnameCount: entityBlocks.filter((entity) => entity.keys.targetname).length,
  },
  transformed: {
    addedBrushes: brushes.length,
    addedEntities: addedEntities.length,
    removedFoliageEntities: removed.filter((entity) => (entity.keys.classname || "").startsWith("static_natural_")).length,
    removedConnectorObstructions: removed.filter((entity) => connectorObstructionNumbers.has(entity.number)).length,
    dmSpawnsAdded: entityClassCounts.info_player_deathmatch || 0,
  },
  expansion: {
    bounds: { min: allMinimum, max: allMaximum },
    serviceDeckTopZ: -384,
    revision: 2,
    fullySkinnedBrushes: brushes.filter((brush) => Object.values(brush.faceTextures).every((texture) => !["common/caulk", "common/nodraw"].includes(texture))).length,
    transparentConstructionMaterials: [...usedMaterials].filter((texture) => texture.includes("deckgrate")),
    connectorCount: 2,
    connectorWidth: 288,
    connectorRiser: 12,
    openHallBays: 3,
    movingDoorsAdded: 0,
    objectivesChanged: false,
    originalTeamSpawnsChanged: false,
    brushRoleCounts: Object.fromEntries([...roleCounts.entries()].sort((a, b) => a[0].localeCompare(b[0]))),
    addedEntityRoleCounts: entityRoleCounts,
    addedEntityClassCounts: entityClassCounts,
    usedMaterials: [...usedMaterials].sort(),
    brushes: brushes.map(({ role, min, max, detail, faceTextures }) => ({ role, min, max, detail, faceTextures })),
    entities: addedEntities.map(({ role, classname, properties }) => ({ role, classname, properties })),
  },
  scriptPolicy: "thin wrappers execute retail obj_team2 scripts; no retail script or texture/model bytes redistributed",
  extraPrecache: ["models/fx/bazookaexplosion_dm.tik"],
};
const reportPath = path.join(outputRoot, `${mapName}-mirror-report.json`);
const designPath = path.join(outputRoot, `${mapName}-design-report.json`);
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
fs.writeFileSync(designPath, `${JSON.stringify({ schemaVersion: 2, revision: 2, mapName, fixedViews, design: report.expansion, preservation: report.preservation }, null, 2)}\n`);
console.log(`Generated ${mapPath}`);
console.log(`Added ${brushes.length} brushes and ${addedEntities.length} entities; removed nine untargeted foliage entities and five untargeted connector obstructions`);
console.log(`SHA256 ${report.output.sha256}`);
