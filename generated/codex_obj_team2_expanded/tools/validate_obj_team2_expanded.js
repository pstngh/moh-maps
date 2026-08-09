#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function parseArgs(values) {
  const result = {};
  for (let index = 0; index < values.length; index += 2) result[values[index].replace(/^--/, "")] = values[index + 1];
  return result;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function markerRange(lines, begin, end) {
  const first = lines.indexOf(begin);
  const last = lines.indexOf(end);
  assert(first >= 0 && last > first, `Missing or reversed marker range: ${begin}`);
  assert(lines.indexOf(begin, first + 1) < 0 && lines.indexOf(end, last + 1) < 0, `Marker is not unique: ${begin}`);
  return { first, last };
}

function entityBlocks(lines) {
  const result = [];
  for (let index = 0; index < lines.length; index += 1) {
    const marker = lines[index].match(/^\/\/ entity (\d+)$/);
    if (!marker) continue;
    assert(lines[index + 1] === "{", `Malformed entity ${marker[1]}`);
    let depth = 0;
    let closeIndex = -1;
    const keys = {};
    for (let row = index + 1; row < lines.length; row += 1) {
      const trimmed = lines[row].trim();
      if (trimmed === "{") { depth += 1; continue; }
      if (trimmed === "}") {
        depth -= 1;
        if (depth === 0) { closeIndex = row; break; }
        continue;
      }
      if (depth === 1) {
        const match = lines[row].match(/^\s*"([^"]+)"\s+"([^"]*)"\s*$/);
        if (match) keys[match[1]] = match[2];
      }
    }
    assert(closeIndex > index, `Unclosed entity ${marker[1]}`);
    result.push({ number: Number(marker[1]), markerIndex: index, closeIndex, keys });
    index = closeIndex;
  }
  return result;
}

const args = parseArgs(process.argv.slice(2));
const outputRoot = path.resolve(args["output-root"] || path.join(__dirname, ".."));
const mapName = "codex_obj_team2_expanded";
const repositoryRoot = path.resolve(outputRoot, "..", "..");
const sourcePath = path.join(repositoryRoot, "aa", "obj_team2.map");
const mapPath = path.join(outputRoot, "main", "maps", "obj", `${mapName}.map`);
const scriptPath = path.join(outputRoot, "main", "maps", "obj", `${mapName}.scr`);
const precachePath = path.join(outputRoot, "main", "maps", "obj", `${mapName}_precache.scr`);
const reportPath = path.join(outputRoot, `${mapName}-mirror-report.json`);
for (const required of [sourcePath, mapPath, scriptPath, precachePath, reportPath]) assert(fs.existsSync(required), `Missing ${required}`);

const sourceBuffer = fs.readFileSync(sourcePath);
const sourceText = sourceBuffer.toString("utf8");
const mapText = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
assert(report.schemaVersion === 2 && report.revision === 2, "Expected revision 2 generation report");
assert(sha256(sourceBuffer) === report.sourceSha256, "Source hash no longer matches generation report");
assert(Buffer.byteLength(mapText) === report.output.bytes && sha256(mapText) === report.output.sha256, "Generated MAP bytes/hash mismatch");
assert(!mapText.includes("textures/codex"), "Expansion unexpectedly references custom texture bytes");

const worldBegin = "// CODEX OBJ_TEAM2 EXPANSION BRUSHES BEGIN";
const worldEnd = "// CODEX OBJ_TEAM2 EXPANSION BRUSHES END";
const entityBegin = "// CODEX OBJ_TEAM2 EXPANSION ENTITIES BEGIN";
const entityEnd = "// CODEX OBJ_TEAM2 EXPANSION ENTITIES END";
const sourceLines = sourceText.split("\r\n");
const mapLines = mapText.split("\r\n");
const worldRange = markerRange(mapLines, worldBegin, worldEnd);
const entityRange = markerRange(mapLines, entityBegin, entityEnd);
assert(worldRange.last < entityRange.first, "World/entity expansion marker order changed");

const strippedMapLines = mapLines.filter((_line, index) => !(index >= worldRange.first && index <= worldRange.last) && !(index >= entityRange.first && index <= entityRange.last));
const removedNumbers = new Set(report.preservation.removedEntityNumbers);
assert(removedNumbers.size === 14, "The preservation policy must remove nine foliage entities and five connector obstructions");
const connectorObstructionNumbers = new Set([666, 674, 675, 679, 680]);
const sourceEntities = entityBlocks(sourceLines);
const removedIndexes = new Set();
for (const entity of sourceEntities) {
  if (!removedNumbers.has(entity.number)) continue;
  const isFoliage = (entity.keys.classname || "").startsWith("static_natural_");
  const isConnectorObstruction = connectorObstructionNumbers.has(entity.number) && ["detail", "func_group"].includes(entity.keys.classname);
  assert(isFoliage || isConnectorObstruction, `Removed entity ${entity.number} is outside the documented derivative policy`);
  assert(!entity.keys.targetname, `Removed foliage entity ${entity.number} is targeted`);
  for (let index = entity.markerIndex; index <= entity.closeIndex; index += 1) removedIndexes.add(index);
}
assert([...removedNumbers].every((number) => sourceEntities.some((entity) => entity.number === number)), "A reported removed entity is absent from the source");
const retainedSourceLines = sourceLines.filter((_line, index) => !removedIndexes.has(index));
const retainedSourceText = retainedSourceLines.join("\r\n");
assert(sha256(retainedSourceText) === report.preservation.retainedSourceSha256, "Retained-source hash in report is stale");
assert(strippedMapLines.join("\r\n") === retainedSourceText, "Content outside the marked expansion differs from obj_team2 minus the nine documented foliage entities");

const originalDoorCount = sourceEntities.filter((entity) => entity.keys.classname === "func_rotatingdoor").length;
const originalTargetnameCount = sourceEntities.filter((entity) => entity.keys.targetname).length;
assert(originalDoorCount === 23 && report.preservation.originalDoorCount === originalDoorCount, "Original rotating-door inventory changed");
assert(report.preservation.originalTargetnameCount === originalTargetnameCount, "Original targetname inventory changed");

const customWorldLines = mapLines.slice(worldRange.first + 1, worldRange.last);
const customEntityLines = mapLines.slice(entityRange.first + 1, entityRange.last);
const brushMarkers = customWorldLines.filter((line) => /^\/\/ brush \d+$/.test(line));
assert(brushMarkers.length === report.transformed.addedBrushes && brushMarkers.length === report.expansion.brushes.length, "Added brush count mismatch");
const customEntities = entityBlocks(customEntityLines);
assert(customEntities.length === report.transformed.addedEntities, "Added entity count mismatch");
assert(customEntities.every((entity) => !entity.keys.targetname && !entity.keys.target), "Expansion must not alter the retail target graph");
assert(customEntities.filter((entity) => entity.keys.classname === "info_player_deathmatch").length === 8, "Expected eight expansion DM spawns");
assert(customEntities.every((entity) => entity.keys.classname !== "info_player_allied" && entity.keys.classname !== "info_player_axis"), "Expansion must not alter objective team spawn counts");
assert(customEntities.every((entity) => entity.keys.classname !== "func_door" && entity.keys.classname !== "func_rotatingdoor"), "Expansion intentionally adds no doors");

const forbiddenConstructionMaterials = ["common/caulk", "common/nodraw", "general_industrial/deckgrate_set1a", "general_industrial/deckgrate_set1b"];
assert(!customWorldLines.some((line) => forbiddenConstructionMaterials.some((texture) => line.includes(` ${texture} `))), "Revision 2 contains an invisible or alpha construction surface");
assert(report.expansion.fullySkinnedBrushes === report.expansion.brushes.length, "Not every expansion brush is fully skinned");
assert(report.expansion.transparentConstructionMaterials.length === 0, "Transparent construction material remains in revision 2");
for (const brush of report.expansion.brushes) {
  assert(brush.faceTextures && Object.keys(brush.faceTextures).length === 6, `${brush.role} lacks six recorded face materials`);
  assert(Object.values(brush.faceTextures).every((texture) => !forbiddenConstructionMaterials.includes(texture)), `${brush.role} contains a forbidden face material`);
}
assert(report.expansion.brushRoleCounts.south_shed_roof === 1 && report.expansion.brushRoleCounts.north_shed_roof === 1, "Both finished service sheds are required");
assert(report.expansion.brushRoleCounts.hall_bay_awning === 3 && report.expansion.brushRoleCounts.hall_ceiling_beam === 6, "Facade/ceiling completion inventory changed");

for (const brush of report.expansion.brushes) {
  assert(brush.min.length === 3 && brush.max.length === 3, `Malformed ${brush.role} bounds`);
  assert(brush.min.every((value, axis) => Number.isFinite(value) && value < brush.max[axis]), `Invalid ${brush.role} bounds`);
  assert(brush.min[0] >= 3296 && brush.max[0] <= 4800, `${brush.role} escaped the surveyed east-annex X footprint`);
  assert(brush.min[1] >= 640 && brush.max[1] <= 2496, `${brush.role} escaped the surveyed east-annex Y footprint`);
  assert(brush.min[2] >= -544 && brush.max[2] <= 336, `${brush.role} escaped the surveyed east-annex Z footprint`);
}

const connectors = report.expansion.brushes.filter((brush) => brush.role === "connector_steps");
assert(connectors.length === 18, "Expected two nine-step connectors");
for (const yMin of [896, 2016]) {
  const route = connectors.filter((brush) => brush.min[1] === yMin).sort((a, b) => a.min[0] - b.min[0]);
  assert(route.length === 9 && route.every((brush) => brush.max[1] - brush.min[1] === 288), `Connector at y=${yMin} lost its bot-safe width`);
  assert(route.every((brush, index) => index === 0 || brush.max[2] - route[index - 1].max[2] === 12), `Connector at y=${yMin} risers changed`);
}
assert(report.expansion.openHallBays === 3 && report.expansion.movingDoorsAdded === 0, "Hall access policy changed");
assert(report.expansion.objectivesChanged === false && report.expansion.originalTeamSpawnsChanged === false, "Retail objective policy changed");

const dmSpawns = report.expansion.entities.filter((entity) => entity.classname === "info_player_deathmatch");
for (const spawn of dmSpawns) {
  const origin = spawn.properties.origin.split(/\s+/).map(Number);
  const supports = report.expansion.brushes.filter((brush) => (
    origin[0] >= brush.min[0] && origin[0] <= brush.max[0]
    && origin[1] >= brush.min[1] && origin[1] <= brush.max[1]
    && brush.max[2] <= origin[2]
  ));
  const supportTop = Math.max(...supports.map((brush) => brush.max[2]));
  assert(Number.isFinite(supportTop) && origin[2] - supportTop === 48, `DM spawn ${spawn.properties.origin} lacks exact 48-unit support`);
  const blockers = report.expansion.brushes.filter((brush) => (
    origin[0] + 16 > brush.min[0] && origin[0] - 16 < brush.max[0]
    && origin[1] + 16 > brush.min[1] && origin[1] - 16 < brush.max[1]
    && origin[2] + 48 > brush.min[2] && origin[2] - 48 < brush.max[2]
  ));
  assert(blockers.every((brush) => brush.max[2] <= origin[2] - 48), `DM spawn ${spawn.properties.origin} intersects ${blockers.map((brush) => brush.role).join(", ")}`);
}

const expectedScript = "// Thin wrapper: retail obj_team2.scr remains authoritative.\nmain:\n\texec maps/obj/obj_team2.scr\nend\n";
const expectedPrecache = "// Thin wrapper: retail assets remain in Pak0-Pak6.\nexec maps/obj/obj_team2_precache.scr\ncache models/fx/bazookaexplosion_dm.tik\n";
assert(fs.readFileSync(scriptPath, "utf8") === expectedScript, "Runtime wrapper differs from the proven thin policy");
assert(fs.readFileSync(precachePath, "utf8") === expectedPrecache, "Precache wrapper differs from the proven thin policy");

process.stdout.write(`${JSON.stringify({
  schemaVersion: 2,
  revision: 2,
  valid: true,
  mapName,
  sourceSha256: report.sourceSha256,
  mapSha256: report.output.sha256,
  retainedSourceSha256: report.preservation.retainedSourceSha256,
  originalDoorsPreserved: originalDoorCount,
  originalTargetnamesPreserved: originalTargetnameCount,
  removedUntargetedFoliage: [...removedNumbers].filter((number) => !connectorObstructionNumbers.has(number)).length,
  removedUntargetedConnectorObstructions: connectorObstructionNumbers.size,
  addedBrushes: brushMarkers.length,
  addedEntities: customEntities.length,
  dmSpawns: dmSpawns.length,
  botSafeConnectors: 2,
  openHallBays: 3,
  customAssetBytes: 0,
}, null, 2)}\n`);
