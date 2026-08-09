"use strict";

const crypto = require("crypto");
const path = require("path");

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

module.exports = function buildRevision3Report(context) {
  const {
    sourceLines,
    retainedSourceLines,
    sourceBuffer,
    sourceSha256,
    sourcePath,
    outputRoot,
    outputText,
    mapName,
    gameDirectory,
    originalMap,
    displayName,
    entityBlocks,
    vector,
    removed,
    removedWorldBrushNumbers,
    eastFenceEntityNumbers,
    alliedGateEntityNumbers,
    eastFenceWorldBrushNumbers,
    alliedGateWorldBrushNumbers,
    brushes,
    addedEntities,
    roleCounts,
    usedMaterials,
  } = context;

  const entityRoleCounts = {};
  const entityClassCounts = {};
  for (const entity of addedEntities) {
    entityRoleCounts[entity.role] = (entityRoleCounts[entity.role] || 0) + 1;
    entityClassCounts[entity.classname] = (entityClassCounts[entity.classname] || 0) + 1;
  }
  const allMinimum = [0, 1, 2].map((axis) => Math.min(...brushes.map((brush) => brush.min[axis])));
  const allMaximum = [0, 1, 2].map((axis) => Math.max(...brushes.map((brush) => brush.max[axis])));
  const fixedViews = [
    { id: "reported_stock_side", origin: [2944, 1544, -300], viewangles: [-5, 0, 0] },
    { id: "full_open_frontage", origin: [3000, 1320, -260], viewangles: [-8, 0, 0] },
    { id: "frontage_south", origin: [2944, 560, -260], viewangles: [-7, 12, 0] },
    { id: "frontage_north", origin: [2944, 2080, -260], viewangles: [-7, 348, 0] },
    { id: "annex_courtyard", origin: [3440, 1800, -300], viewangles: [-5, 340, 0] },
    { id: "south_workshop", origin: [3840, 1040, -300], viewangles: [-5, 270, 0] },
    { id: "north_workshop", origin: [3840, 1960, -300], viewangles: [-5, 90, 0] },
    { id: "west_arcade", origin: [3424, 1560, -300], viewangles: [-5, 0, 0] },
    { id: "canopy_center", origin: [3904, 1384, -300], viewangles: [-8, 30, 0] },
    { id: "hall_south", origin: [4560, 800, -300], viewangles: [-5, 90, 0] },
    { id: "hall_middle", origin: [4752, 1800, -300], viewangles: [-5, 90, 0] },
    { id: "hall_north", origin: [4752, 2240, -300], viewangles: [-5, 270, 0] },
    { id: "hall_catwalk", origin: [4912, 1400, 0], viewangles: [5, 225, 0] },
    { id: "annex_overhead", origin: [3240, 240, 520], viewangles: [25, 35, 0] },
    { id: "allied_gate_inside", origin: [-1840, 512, -380], viewangles: [-5, 180, 0] },
    { id: "allied_gate_outside", origin: [-2240, 512, -380], viewangles: [-5, 0, 0] },
    { id: "allied_outer_lane", origin: [-2240, 864, -380], viewangles: [-5, 90, 0] },
    { id: "allied_rear_turn", origin: [-2240, 1184, -380], viewangles: [-5, 0, 0] },
  ];

  const report = {
    schemaVersion: 3,
    revision: 3,
    transform: "revision 3 byte-preserving obj_team2 expansion: remove the complete east fence/curb, replace it with a continuous grand frontage, more than double the annex footprint, and add an Allied-spawn exterior route into the rear bunker yard",
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
      removedWorldBrushNumbers: [...removedWorldBrushNumbers].sort((a, b) => a - b),
      originalDoorCount: entityBlocks.filter((entity) => entity.keys.classname === "func_rotatingdoor").length,
      originalTargetnameCount: entityBlocks.filter((entity) => entity.keys.targetname).length,
    },
    transformed: {
      addedBrushes: brushes.length,
      addedEntities: addedEntities.length,
      removedFoliageEntities: removed.filter((entity) => (entity.keys.classname || "").startsWith("static_natural_")).length,
      removedEastFenceEntities: removed.filter((entity) => eastFenceEntityNumbers.has(entity.number)).length,
      removedAlliedGateEntities: removed.filter((entity) => alliedGateEntityNumbers.has(entity.number)).length,
      removedWorldBrushes: removedWorldBrushNumbers.size,
      removedEastFenceWorldBrushes: eastFenceWorldBrushNumbers.size,
      removedAlliedGateWorldBrushes: alliedGateWorldBrushNumbers.size,
      dmSpawnsAdded: entityClassCounts.info_player_deathmatch || 0,
    },
    expansion: {
      bounds: { min: allMinimum, max: allMaximum },
      eastAnnexBounds: { min: [3040, 320, -560], max: [5152, 2496, 336] },
      alliedRouteBounds: { min: [-2432, 0, -560], max: [-1280, 1344, -160] },
      serviceDeckTopZ: -384,
      alliedRouteTopZ: -464,
      revision: 3,
      fullySkinnedBrushes: brushes.filter((brush) => Object.values(brush.faceTextures).every((texture) => !["common/caulk", "common/nodraw"].includes(texture))).length,
      transparentConstructionMaterials: [...usedMaterials].filter((texture) => texture.includes("deckgrate")),
      continuousFrontageCount: 1,
      continuousFrontageWidth: 1824,
      grandApronSteps: 6,
      grandApronRiser: 16,
      openHallBays: 4,
      alliedGateWidth: 326,
      alliedExteriorRouteConnected: true,
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
