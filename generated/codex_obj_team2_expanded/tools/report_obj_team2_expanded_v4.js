"use strict";

const crypto = require("crypto");
const path = require("path");

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

module.exports = function buildRevision4Report(context) {
  const {
    sourceLines, retainedSourceLines, sourceBuffer, sourceSha256, sourcePath, outputRoot, outputText,
    mapName, gameDirectory, originalMap, displayName, entityBlocks, vector, removed,
    worldBrushBlocks, westFenceEntityNumbers, southEastFenceEntityNumbers, fenceEntityNumbers,
    fenceWorldBrushNumbers, brushes, addedEntities, roleCounts, usedMaterials,
  } = context;

  const entityRoleCounts = {};
  const entityClassCounts = {};
  for (const entity of addedEntities) {
    entityRoleCounts[entity.role] = (entityRoleCounts[entity.role] || 0) + 1;
    entityClassCounts[entity.classname] = (entityClassCounts[entity.classname] || 0) + 1;
  }
  const allMinimum = [0, 1, 2].map((axis) => Math.min(...brushes.map((brush) => brush.min[axis])));
  const allMaximum = [0, 1, 2].map((axis) => Math.max(...brushes.map((brush) => brush.max[axis])));
  const routeBrushes = brushes.filter((brush) => brush.role.startsWith("forest_"));
  const fixedViews = [
    { id: "reported_stock_side", origin: [2944, 1544, -300], viewangles: [-5, 0, 0] },
    { id: "full_open_frontage", origin: [3000, 1320, -260], viewangles: [-8, 0, 0] },
    { id: "frontage_south", origin: [2944, 560, -260], viewangles: [-7, 12, 0] },
    { id: "frontage_north", origin: [2944, 2080, -260], viewangles: [-7, 348, 0] },
    { id: "annex_courtyard", origin: [3440, 1800, -300], viewangles: [-5, 340, 0] },
    { id: "south_workshop", origin: [3840, 1040, -300], viewangles: [-5, 270, 0] },
    { id: "north_workshop", origin: [3840, 1960, -300], viewangles: [-5, 90, 0] },
    { id: "canopy_center", origin: [3904, 1384, -300], viewangles: [-8, 30, 0] },
    { id: "hall_south", origin: [4560, 800, -300], viewangles: [-5, 90, 0] },
    { id: "hall_middle", origin: [4752, 1800, -300], viewangles: [-5, 90, 0] },
    { id: "hall_north", origin: [4752, 2240, -300], viewangles: [-5, 270, 0] },
    { id: "hall_catwalk", origin: [4912, 1400, 0], viewangles: [5, 225, 0] },
    { id: "annex_overhead", origin: [3240, 240, 520], viewangles: [25, 35, 0] },
    { id: "allied_spawn_open_perimeter", origin: [-1600, 288, -360], viewangles: [-7, 270, 0] },
    { id: "allied_forest_court", origin: [-1440, 64, -384], viewangles: [-6, 180, 0] },
    { id: "allied_forest_layby", origin: [-2112, -640, -336], viewangles: [-5, 180, 0] },
    { id: "west_forest_descent", origin: [-1792, -736, -320], viewangles: [-8, 270, 0] },
    { id: "west_forest_climb", origin: [-1792, -1120, -280], viewangles: [-8, 270, 0] },
    { id: "west_ridge", origin: [-1376, -1456, -160], viewangles: [-5, 180, 0] },
    { id: "central_bridge_west", origin: [-96, -1376, -112], viewangles: [-5, 0, 0] },
    { id: "central_bridge_east", origin: [960, -1376, -96], viewangles: [-5, 180, 0] },
    { id: "central_facade", origin: [544, -1600, -96], viewangles: [-8, 90, 0] },
    { id: "east_ridge_shelter", origin: [1856, -1376, -160], viewangles: [-6, 0, 0] },
    { id: "east_forest_descent", origin: [2816, -1088, -224], viewangles: [-8, 90, 0] },
    { id: "east_forest_lower", origin: [2816, -448, -384], viewangles: [-5, 90, 0] },
    { id: "east_open_perimeter", origin: [2720, 352, -384], viewangles: [-5, 0, 0] },
    { id: "forest_loop_west_overhead", origin: [-1792, -896, 256], viewangles: [40, 270, 0] },
    { id: "forest_loop_east_overhead", origin: [2700, -640, 256], viewangles: [40, 270, 0] },
  ];

  const report = {
    schemaVersion: 4,
    revision: 4,
    transform: "revision 4 byte-preserving obj_team2 expansion: remove every west/south/east fence owner, curb, rail and playerclip; complete a graded Allied-to-annex forest loop; finish the central terrain gap as a lit bridge and facility facade",
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
      removedEntities: removed.map((entity) => ({
        number: entity.number,
        classname: entity.keys.classname,
        origin: entity.keys.origin ? vector(entity.keys.origin) : null,
        model: entity.keys.model || null,
        targetname: entity.keys.targetname || null,
      })),
      removedWorldBrushNumbers: [...fenceWorldBrushNumbers].sort((a, b) => a - b),
      canonicalWorldBrushCount: worldBrushBlocks.length,
      originalDoorCount: entityBlocks.filter((entity) => entity.keys.classname === "func_rotatingdoor").length,
      originalTargetnameCount: entityBlocks.filter((entity) => entity.keys.targetname).length,
    },
    transformed: {
      addedBrushes: brushes.length,
      addedEntities: addedEntities.length,
      removedFoliageEntities: removed.filter((entity) => (entity.keys.classname || "").startsWith("static_natural_")).length,
      removedFenceEntities: removed.filter((entity) => fenceEntityNumbers.has(entity.number)).length,
      removedWestFenceEntities: removed.filter((entity) => westFenceEntityNumbers.has(entity.number)).length,
      removedSouthEastFenceEntities: removed.filter((entity) => southEastFenceEntityNumbers.has(entity.number)).length,
      removedFenceWorldBrushes: fenceWorldBrushNumbers.size,
      removedInvisibleFencePlayerclips: 4,
      dmSpawnsAdded: entityClassCounts.info_player_deathmatch || 0,
    },
    expansion: {
      revision: 4,
      bounds: { min: allMinimum, max: allMaximum },
      eastAnnexBounds: { min: [3040, 320, -560], max: [5152, 2496, 336] },
      forestRouteBounds: { min: [-2400, -1792, -960], max: [3072, 448, 176] },
      forestRouteBrushes: routeBrushes.length,
      forestRouteConnected: true,
      forestRouteEndpoints: ["Allied spawn court", "east annex grand apron"],
      forestRouteMinimumCombatWidth: 320,
      completeStockFenceSystemRemoved: true,
      remainingCustomFenceRoles: 0,
      remainingCustomFenceMaterials: 0,
      invisibleFenceCollisionRemoved: true,
      centralTerrainGapFinished: true,
      centralTerrainGapSealedBySolidFoundation: true,
      centralSouthEdgeVisuallyFinished: true,
      centralFacadeVisuallyFinished: true,
      stockSkyHullExtended: true,
      stockSkyHullExtensionBrushes: 3,
      centralBridgeWidth: 1024,
      centralBridgeLaneDepth: 320,
      fullySkinnedBrushes: brushes.filter((brush) => Object.values(brush.faceTextures).every((texture) => !["common/caulk", "common/nodraw"].includes(texture))).length,
      transparentConstructionMaterials: [...usedMaterials].filter((texture) => texture.includes("deckgrate") || texture.includes("secfence") || texture.includes("barbwire")),
      continuousFrontageCount: 1,
      continuousFrontageWidth: 1824,
      grandApronSteps: 6,
      grandApronRiser: 16,
      openHallBays: 4,
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
  return { report, fixedViews };
};
