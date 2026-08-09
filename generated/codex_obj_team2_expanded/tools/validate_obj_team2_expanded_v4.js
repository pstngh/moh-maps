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
function blockAt(lines, openIndex) {
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
function entityBlocks(lines) {
  const result = [];
  for (let index = 0; index < lines.length; index += 1) {
    const marker = lines[index].match(/^\/\/ entity (\d+)$/);
    if (!marker) continue;
    assert(lines[index + 1] === "{", `Malformed entity ${marker[1]}`);
    const block = blockAt(lines, index + 1);
    const keys = {};
    let depth = 0;
    for (let row = block.openIndex; row <= block.closeIndex; row += 1) {
      const trimmed = lines[row].trim();
      if (trimmed === "{") { depth += 1; continue; }
      if (trimmed === "}") { depth -= 1; continue; }
      if (depth !== 1) continue;
      const match = lines[row].match(/^\s*"([^"]+)"\s+"([^"]*)"\s*$/);
      if (match) keys[match[1]] = match[2];
    }
    result.push({ number: Number(marker[1]), markerIndex: index, closeIndex: block.closeIndex, keys });
    index = block.closeIndex;
  }
  return result;
}
function worldBrushBlocks(lines) {
  const firstEntity = lines.findIndex((line) => /^\/\/ entity \d+$/.test(line));
  const result = [];
  for (let index = 0; index < firstEntity; index += 1) {
    const marker = lines[index].match(/^\/\/ brush (\d+)$/);
    if (!marker) continue;
    assert(lines[index + 1].trim() === "{", `Malformed world brush ${marker[1]}`);
    const block = blockAt(lines, index + 1);
    result.push({ number: Number(marker[1]), markerIndex: index, closeIndex: block.closeIndex });
    index = block.closeIndex;
  }
  return result;
}
function markerRange(lines, begin, end) {
  const first = lines.indexOf(begin);
  const last = lines.indexOf(end);
  assert(first >= 0 && last > first, `Missing or reversed marker range: ${begin}`);
  assert(lines.indexOf(begin, first + 1) < 0 && lines.indexOf(end, last + 1) < 0, `Marker is not unique: ${begin}`);
  return { first, last };
}
const range = (first, last) => Array.from({ length: last - first + 1 }, (_value, index) => first + index);

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
assert(report.schemaVersion === 4 && report.revision === 4, "Expected revision 4 generation report");
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

const sourceEntities = entityBlocks(sourceLines);
const sourceWorldBrushes = worldBrushBlocks(sourceLines);
const expectedFoliage = new Set([398, 453, 471, 472, 489, 490, 491, 492, 493, 496, 498, 526, 528, 558, 687, 688, 689, 690, 692, 693, 696, 699, 702, 704]);
const expectedWestFenceEntities = new Set(range(425, 446));
const expectedSouthEastFenceEntities = new Set(range(648, 684));
const expectedFenceEntities = new Set([...expectedWestFenceEntities, ...expectedSouthEastFenceEntities]);
const expectedRemovedEntities = new Set([...expectedFoliage, ...expectedFenceEntities]);
const expectedFenceWorldBrushes = new Set([811, 812, 819, 820, ...range(1109, 1124), ...range(3217, 3229)]);
assert(expectedRemovedEntities.size === 83 && expectedFenceWorldBrushes.size === 33, "Revision-4 policy constants are malformed");
assert(JSON.stringify([...report.preservation.removedEntityNumbers].sort((a, b) => a - b)) === JSON.stringify([...expectedRemovedEntities].sort((a, b) => a - b)), "Removed entity inventory differs from revision-4 policy");
assert(JSON.stringify([...report.preservation.removedWorldBrushNumbers].sort((a, b) => a - b)) === JSON.stringify([...expectedFenceWorldBrushes].sort((a, b) => a - b)), "Removed world-brush inventory differs from revision-4 policy");

const removedIndexes = new Set();
for (const entity of sourceEntities.filter(({ number }) => expectedRemovedEntities.has(number))) {
  const foliage = expectedFoliage.has(entity.number) && (entity.keys.classname || "").startsWith("static_natural_");
  const fenceOwner = expectedFenceEntities.has(entity.number) && ["detail", "func_group"].includes(entity.keys.classname);
  assert((foliage || fenceOwner) && !entity.keys.targetname, `Entity ${entity.number} violates the documented removal policy`);
  for (let index = entity.markerIndex; index <= entity.closeIndex; index += 1) removedIndexes.add(index);
}
for (const brush of sourceWorldBrushes.filter(({ number }) => expectedFenceWorldBrushes.has(number))) {
  for (let index = brush.markerIndex; index <= brush.closeIndex; index += 1) removedIndexes.add(index);
}
assert([...expectedFenceWorldBrushes].every((number) => sourceWorldBrushes.some((brush) => brush.number === number)), "A removed stock fence world brush is absent");
const retainedSourceLines = sourceLines.filter((_line, index) => !removedIndexes.has(index));
const strippedMapLines = mapLines.filter((_line, index) => !(index >= worldRange.first && index <= worldRange.last) && !(index >= entityRange.first && index <= entityRange.last));
assert(sha256(retainedSourceLines.join("\r\n")) === report.preservation.retainedSourceSha256, "Retained-source hash is stale");
assert(strippedMapLines.join("\r\n") === retainedSourceLines.join("\r\n"), "Content outside marked expansion differs from the exact documented stock subtraction");

const originalDoorCount = sourceEntities.filter((entity) => entity.keys.classname === "func_rotatingdoor").length;
const originalTargetnameCount = sourceEntities.filter((entity) => entity.keys.targetname).length;
const originalAlliedStarts = sourceEntities.filter((entity) => entity.keys.classname === "info_player_allied").length;
const originalAxisStarts = sourceEntities.filter((entity) => entity.keys.classname === "info_player_axis").length;
assert(originalDoorCount === 23 && report.preservation.originalDoorCount === 23, "Original rotating-door inventory changed");
assert(originalTargetnameCount === 88 && report.preservation.originalTargetnameCount === 88, "Original targetname inventory changed");
assert(originalAlliedStarts === 16 && originalAxisStarts === 16, "Unexpected stock team-spawn inventory");

const customWorldLines = mapLines.slice(worldRange.first + 1, worldRange.last);
const customEntityLines = mapLines.slice(entityRange.first + 1, entityRange.last);
const brushMarkers = customWorldLines.filter((line) => /^\/\/ brush \d+$/.test(line));
const customEntities = entityBlocks(customEntityLines);
assert(brushMarkers.length === report.transformed.addedBrushes && brushMarkers.length === report.expansion.brushes.length, "Added brush count mismatch");
assert(customEntities.length === report.transformed.addedEntities, "Added entity count mismatch");
assert(customEntities.every((entity) => !entity.keys.targetname && !entity.keys.target && !entity.keys.team), "Expansion must not alter the retail target/team graph");
assert(customEntities.filter((entity) => entity.keys.classname === "info_player_deathmatch").length === 21, "Expected twenty-one revision-4 DM spawns");
assert(customEntities.every((entity) => !["info_player_allied", "info_player_axis", "func_door", "func_rotatingdoor"].includes(entity.keys.classname)), "Expansion altered team starts or moving doors");

const forbiddenMaterials = ["common/caulk", "common/nodraw", "general_industrial/deckgrate_set1a", "general_industrial/deckgrate_set1b", "mohcommon/secfence", "mohcommon/barbwire"];
assert(!customWorldLines.some((line) => forbiddenMaterials.some((texture) => line.includes(` ${texture} `))), "Revision 4 contains an invisible, alpha or fence construction face");
assert(!mapText.includes("mohcommon/secfence") && !mapText.includes("mohcommon/barbwire"), "A stock fence or overhead wire survived the complete removal");
assert(report.expansion.fullySkinnedBrushes === report.expansion.brushes.length, "Not every expansion brush is fully skinned");
assert(report.expansion.transparentConstructionMaterials.length === 0, "Transparent/fence construction material remains in revision 4");
for (const brush of report.expansion.brushes) {
  assert(brush.faceTextures && Object.keys(brush.faceTextures).length === 6, `${brush.role} lacks six recorded face materials`);
  assert(Object.values(brush.faceTextures).every((texture) => !forbiddenMaterials.includes(texture)), `${brush.role} contains a forbidden face material`);
  assert(brush.min.every((value, axis) => Number.isFinite(value) && value < brush.max[axis]), `Invalid ${brush.role} bounds`);
  assert(brush.min[0] >= -2432 && brush.max[0] <= 5152 && brush.min[1] >= -1824 && brush.max[1] <= 2496 && brush.min[2] >= -960 && brush.max[2] <= 992, `${brush.role} escaped the surveyed revision-4 bounds`);
}

const roles = report.expansion.brushRoleCounts;
assert(roles.service_deck === 2 && roles.grand_apron_steps === 6, "Leak-safe east deck or frontage inventory changed");
assert(roles.south_workshop_roof === 1 && roles.north_workshop_roof === 1 && roles.hall_bay_awning === 4, "East annex completion inventory changed");
assert(!roles.allied_fence_base_south && !roles.allied_fence_base_north && !roles.allied_fence_lower_rail && !roles.allied_fence_upper_rail, "Revision-3 fence reconstruction survived");
assert(!roles.allied_outer_guard && !roles.allied_south_guard && !roles.allied_north_guard, "Revision-3 perimeter blockers survived");
assert(roles.forest_allied_court === 1 && roles.forest_west_transition_steps === 3 && roles.forest_west_lower_lane === 1, "Allied forest entrance is incomplete");
assert(roles.forest_west_climb_steps === 11 && roles.forest_west_ridge === 1, "West forest climb is incomplete");
assert(roles.forest_bridge_west_steps === 4 && roles.forest_central_bridge === 1 && roles.forest_bridge_east_steps === 4, "Central forest bridge is incomplete");
assert(roles.forest_east_ridge === 1 && roles.forest_east_descent_steps === 14 && roles.forest_east_lower_lane === 1 && roles.forest_east_entry === 1, "East forest return is incomplete");
assert(roles.forest_central_foundation === 1 && !roles.forest_foundation_buttress, "Central terrain seam has not been solidly sealed");
assert(roles.forest_south_sky_hull === 1 && report.expansion.stockSkyHullExtended, "Central south sky hull was not completed");
assert(roles.forest_north_sky_hull === 1 && roles.forest_central_sky_ceiling === 1 && report.expansion.stockSkyHullExtensionBrushes === 3, "Central north/ceiling sky hull was not completed");
assert(roles.forest_central_facade_backwall === 1 && roles.forest_central_facade_pier === 4 && roles.forest_central_facade_lintel === 3, "Central terrain gap has not been architecturally completed");
assert(roles.forest_south_retaining_wall === 1 && roles.forest_south_retaining_pier === 6 && roles.forest_south_tree_planter === 5, "Central forest boundary is unfinished");
assert(roles.forest_central_facade_pilaster === 4 && roles.forest_central_service_door === 3 && roles.forest_central_service_door_lintel === 3 && roles.forest_central_facade_band === 1, "Central facade detail is incomplete");
assert(roles.forest_route_light_pole === 8 && roles.forest_route_light_arm === 8, "Forest loop light coverage changed");
assert(report.transformed.removedFenceEntities === 59 && report.transformed.removedFenceWorldBrushes === 33, "Complete fence-system counts changed");
assert(report.transformed.removedInvisibleFencePlayerclips === 4 && report.expansion.invisibleFenceCollisionRemoved, "Invisible fence collision was not documented as removed");
assert(report.expansion.completeStockFenceSystemRemoved && report.expansion.forestRouteConnected && report.expansion.centralTerrainGapFinished, "Revision-4 completion metadata changed");
assert(report.expansion.forestRouteMinimumCombatWidth >= 320 && report.expansion.centralBridgeLaneDepth === 320, "Forest route is too narrow for the bot-combat brief");

const dmSpawns = report.expansion.entities.filter((entity) => entity.classname === "info_player_deathmatch");
for (const spawn of dmSpawns) {
  const origin = spawn.properties.origin.split(/\s+/).map(Number);
  const supports = report.expansion.brushes.filter((brush) => origin[0] >= brush.min[0] && origin[0] <= brush.max[0] && origin[1] >= brush.min[1] && origin[1] <= brush.max[1] && brush.max[2] <= origin[2]);
  const supportTop = Math.max(...supports.map((brush) => brush.max[2]));
  assert(Number.isFinite(supportTop) && origin[2] - supportTop === 48, `DM spawn ${spawn.properties.origin} lacks exact 48-unit support`);
  const blockers = report.expansion.brushes.filter((brush) => origin[0] + 16 > brush.min[0] && origin[0] - 16 < brush.max[0] && origin[1] + 16 > brush.min[1] && origin[1] - 16 < brush.max[1] && origin[2] + 48 > brush.min[2] && origin[2] - 48 < brush.max[2]);
  assert(blockers.every((brush) => brush.max[2] <= origin[2] - 48), `DM spawn ${spawn.properties.origin} intersects ${blockers.map((brush) => brush.role).join(", ")}`);
}

const expectedScript = "// Thin wrapper: retail obj_team2.scr remains authoritative.\nmain:\n\texec maps/obj/obj_team2.scr\nend\n";
const expectedPrecache = "// Thin wrapper: retail assets remain in Pak0-Pak6.\nexec maps/obj/obj_team2_precache.scr\ncache models/fx/bazookaexplosion_dm.tik\n";
assert(fs.readFileSync(scriptPath, "utf8") === expectedScript, "Runtime wrapper differs from the proven thin policy");
assert(fs.readFileSync(precachePath, "utf8") === expectedPrecache, "Precache wrapper differs from the proven thin policy");

process.stdout.write(`${JSON.stringify({
  schemaVersion: 4,
  revision: 4,
  valid: true,
  mapName,
  sourceSha256: report.sourceSha256,
  mapSha256: report.output.sha256,
  retainedSourceSha256: report.preservation.retainedSourceSha256,
  originalDoorsPreserved: originalDoorCount,
  originalTargetnamesPreserved: originalTargetnameCount,
  originalTeamStartsPreserved: { allied: originalAlliedStarts, axis: originalAxisStarts },
  removedUntargetedFoliage: expectedFoliage.size,
  removedFenceEntities: expectedFenceEntities.size,
  removedFenceWorldBrushes: expectedFenceWorldBrushes.size,
  removedInvisibleFencePlayerclips: report.transformed.removedInvisibleFencePlayerclips,
  addedBrushes: brushMarkers.length,
  addedEntities: customEntities.length,
  dmSpawns: dmSpawns.length,
  forestRouteConnected: report.expansion.forestRouteConnected,
  forestRouteMinimumCombatWidth: report.expansion.forestRouteMinimumCombatWidth,
  centralBridgeWidth: report.expansion.centralBridgeWidth,
  customAssetBytes: 0,
}, null, 2)}\n`);
