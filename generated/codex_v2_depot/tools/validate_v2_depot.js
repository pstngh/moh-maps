#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const generatedRoot = path.resolve(process.argv[2] || path.join(__dirname, ".."));
const mapName = process.argv[3] || "codex_v2_depot";
const mapPath = path.join(generatedRoot, "main", "maps", "dm", `${mapName}.map`);
const reportPath = path.join(generatedRoot, `${mapName}-design-report.json`);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function count(text, expression) {
  return [...text.matchAll(expression)].length;
}

function insideStrict(value, min, max, epsilon = 0.001) {
  return value > min + epsilon && value < max - epsilon;
}

function hullIntersectsBox(origin, box) {
  const min = [origin[0] - 18, origin[1] - 18, origin[2] - 32];
  const max = [origin[0] + 18, origin[1] + 18, origin[2] + 64];
  return min[0] < box.max[0] - 0.001 && max[0] > box.min[0] + 0.001 &&
    min[1] < box.max[1] - 0.001 && max[1] > box.min[1] + 0.001 &&
    min[2] < box.max[2] - 0.001 && max[2] > box.min[2] + 0.001;
}

function hullIntersectsCylinder(origin, cylinder) {
  const hullMinZ = origin[2] - 32;
  const hullMaxZ = origin[2] + 64;
  if (hullMinZ >= cylinder.maxZ - 0.001 || hullMaxZ <= cylinder.minZ + 0.001) return false;
  const dx = Math.max(Math.abs(origin[0] - cylinder.center[0]) - 18, 0);
  const dy = Math.max(Math.abs(origin[1] - cylinder.center[1]) - 18, 0);
  return Math.hypot(dx, dy) < cylinder.radius - 0.001;
}

function supported(origin, boxes) {
  const footZ = origin[2] - 32;
  return boxes.some((box) => Math.abs(box.max[2] - footZ) < 0.001 &&
    origin[0] >= box.min[0] + 18 && origin[0] <= box.max[0] - 18 &&
    origin[1] >= box.min[1] + 18 && origin[1] <= box.max[1] - 18);
}

const mapText = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
assert(report.mapName === mapName, "Design report map name mismatch");
assert(report.materials.stockOnly === true, "Map must be stock-material only");
assert(report.materials.bundledOriginalTextures.length === 0, "No custom textures should be bundled");
assert(!mapText.includes("\\n"), "Literal escaped newlines found in MAP source");
assert(!/textures\/codex|codex_nuke\//i.test(mapText), "Old custom texture family leaked into V2 Depot");
assert(!/(valve|counter-strike|de_nuke|source2)/i.test(mapText), "Commercial/source-game asset identifier leaked into MAP");

const brushCount = count(mapText, /^\/\/ brush \d+\s*$/gm);
assert(brushCount === report.brushes.total, `Brush count mismatch: ${brushCount} vs ${report.brushes.total}`);
assert(report.brushes.total >= 180, "Map lost too much authored architectural/detail structure");
assert(report.brushes.cylinders === 2, "Inspection-engine cylinder count changed");

const faceLines = mapText.split(/\r?\n/).filter((line) => /^\s*\(/.test(line) && /\)\s+\S+\s+[-+\d.]+\s+[-+\d.]+/.test(line));
const caulkFaces = faceLines.filter((line) => /\scommon\/caulk\s/.test(line)).length;
const caulkRatio = caulkFaces / faceLines.length;
assert(faceLines.length >= 1100, `Unexpectedly low face count: ${faceLines.length}`);
assert(caulkRatio >= 0.3 && caulkRatio <= 0.55, `Hidden-face caulk ratio outside stock-like range: ${caulkRatio}`);

for (const requiredMaterial of [
  "common/caulk", "sky/mohday1", "general_structure/bunker_wall", "general_structure/jh_conc512b",
  "algiers/whsflrset1_1b", "algiers/doccrtset_1stepsml", "general_industrial/deckgrate_set1b",
  "normandy/bunk_ceiling", "normandy/bunk_ceiling_beam", "das_boot/ironwall1", "german/rusty_iron",
  "mohcommon/ibeam_1a", "general_industrial/utilitybox_side", "general_industrial/utilitybox_front",
  "general_industrial/utilboxtop", "german/crate_reinforced1_side", "german/crate_reinforced1_top",
]) {
  assert(report.materials.used.includes(requiredMaterial), `Required stock material missing: ${requiredMaterial}`);
  assert(mapText.includes(requiredMaterial), `Required stock material absent from MAP: ${requiredMaterial}`);
}

const expectedClasses = {
  info_player_deathmatch: 18,
  info_player_allied: 8,
  info_player_axis: 8,
  info_player_start: 1,
  light: 25,
  "static_lamp_lightbulb-caged": 20,
  script_model: 20,
  static_vehicle_german_opeltruck: 1,
};
for (const [classname, expected] of Object.entries(expectedClasses)) {
  const actual = count(mapText, new RegExp(`"classname" "${classname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`, "g"));
  assert(actual === expected, `${classname} count mismatch: ${actual} vs ${expected}`);
}
assert(!/"classname" "(?:func_rotatingdoor|func_door|script_door)"/.test(mapText), "Moving door entity introduced into primary bot routes");

const collisionBoxes = report.collision.boxes;
const collisionCylinders = report.collision.cylinders;
for (const spawn of report.spawns) {
  assert(supported(spawn.origin, collisionBoxes), `Unsupported spawn: ${spawn.classname} at ${spawn.origin.join(" ")}`);
  for (const box of collisionBoxes) {
    if (box.role.endsWith("floor") || box.role.includes("catwalk") || box.role.endsWith("landing")) continue;
    assert(!hullIntersectsBox(spawn.origin, box), `Spawn hull intersects ${box.role}: ${spawn.origin.join(" ")}`);
  }
  for (const cylinder of collisionCylinders) {
    assert(!hullIntersectsCylinder(spawn.origin, cylinder), `Spawn hull intersects ${cylinder.role}: ${spawn.origin.join(" ")}`);
  }
}

const truck = report.entities.models.find((model) => model.classname === "static_vehicle_german_opeltruck");
assert(truck && truck.origin[2] === 0, "Stock truck must use the obj_team2-proven ground-origin convention");
assert(supported([truck.origin[0], truck.origin[1], 32], collisionBoxes), "Stock truck is not supported by the yard floor");

const sealed = report.bounds.sealed;
for (const light of report.entities.lights) {
  assert(insideStrict(light.origin[0], sealed[0], sealed[2]) && insideStrict(light.origin[1], sealed[1], sealed[3]) && insideStrict(light.origin[2], sealed[4], sealed[5]), `Light outside sealed bounds: ${light.origin.join(" ")}`);
  assert(light.intensity >= 50 && light.intensity <= 90, `Local light outside measured obj_team2 range: ${light.intensity}`);
}

const graph = new Map(report.routes.zones.map((zone) => [zone.id, new Set()]));
for (const [left, right, width] of report.routes.connections) {
  assert(graph.has(left) && graph.has(right), `Route edge references unknown zone: ${left}/${right}`);
  assert(width >= report.constructionRules.primaryOpeningMinimum, `Route edge below minimum width: ${left}/${right} = ${width}`);
  graph.get(left).add(right);
  graph.get(right).add(left);
}
const visited = new Set();
const queue = [report.routes.zones[0].id];
while (queue.length) {
  const current = queue.shift();
  if (visited.has(current)) continue;
  visited.add(current);
  for (const next of graph.get(current)) if (!visited.has(next)) queue.push(next);
}
assert(visited.size === report.routes.zones.length, `Route graph disconnected: ${visited.size}/${report.routes.zones.length}`);
assert(report.fixedViews.length >= 8, "Visual QA matrix lost required coverage");

const requiredScript = path.join(generatedRoot, "main", "maps", "dm", `${mapName}.scr`);
const requiredPrecache = path.join(generatedRoot, "main", "maps", "dm", `${mapName}_precache.scr`);
const scriptText = fs.readFileSync(requiredScript, "utf8");
const precacheText = fs.readFileSync(requiredPrecache, "utf8");
assert(scriptText.includes("exec global/DMprecache.scr"), "DM script does not execute global/DMprecache.scr");
for (const cacheLine of ["models/items/dm_50_healthbox.tik", "models/fx/bazookaexplosion_dm.tik", "models/static/lightbulb_caged.tik", "models/static/corona_orange.tik", "models/static/vehicle_opeltruck.tik"]) {
  assert(precacheText.includes(cacheLine), `Precache missing ${cacheLine}`);
}

const result = {
  schemaVersion: 1,
  mapName,
  mapBytes: Buffer.byteLength(mapText),
  brushes: brushCount,
  faces: faceLines.length,
  caulkFaces,
  caulkRatio: Number(caulkRatio.toFixed(4)),
  stockMaterials: report.materials.used.length,
  movingDoors: 0,
  spawns: Object.fromEntries(Object.entries(expectedClasses).filter(([name]) => name.startsWith("info_player")).map(([name, value]) => [name, value])),
  lights: report.entities.lights.length,
  staticModels: report.entities.models.length,
  routeZones: report.routes.zones.length,
  routeConnections: report.routes.connections.length,
  minRouteWidth: Math.min(...report.routes.connections.map((edge) => edge[2])),
  fixedViews: report.fixedViews.length,
  checks: ["stock-only material policy", "face-specific hidden caulk", "source counts", "spawn support and clearance", "model grounding", "light bounds and budget", "route connectivity and width", "DM scripts and precache"],
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
