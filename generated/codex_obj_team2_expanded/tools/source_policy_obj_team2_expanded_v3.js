"use strict";

module.exports = function applyRevision3SourcePolicy({ sourceLines, entityBlocks, blockAt, vector }) {
  const firstEntityMarker = sourceLines.indexOf("// entity 1");
  if (firstEntityMarker < 0 || sourceLines[firstEntityMarker - 1] !== "}") {
    throw new Error("Could not locate the worldspawn close before entity 1");
  }

  const worldBrushBlocks = [];
  for (let index = 0; index < firstEntityMarker; index += 1) {
    const marker = sourceLines[index].match(/^\/\/ brush (\d+)$/);
    if (!marker) continue;
    if (sourceLines[index + 1].trim() !== "{") throw new Error(`Unexpected world-brush opening at source line ${index + 2}`);
    const block = blockAt(index + 1);
    worldBrushBlocks.push({ markerIndex: index, ...block, number: Number(marker[1]) });
    index = block.closeIndex;
  }

  const eastFenceEntityNumbers = new Set(Array.from({ length: 19 }, (_value, index) => 666 + index));
  const alliedGateEntityNumbers = new Set([442, 444]);
  const removedStructureEntityNumbers = new Set([...eastFenceEntityNumbers, ...alliedGateEntityNumbers]);
  const removed = entityBlocks.filter(({ number, keys }) => {
    const origin = keys.origin ? vector(keys.origin) : null;
    const eastFootprintFoliage = Boolean(
      origin
      && (keys.classname || "").startsWith("static_natural_")
      && !keys.targetname
      && origin[0] >= 3200 && origin[0] <= 5200
      && origin[1] >= 256 && origin[1] <= 2944
      && origin[2] >= -600 && origin[2] <= -350
    );
    const alliedRouteFoliage = Boolean(
      origin
      && (keys.classname || "").startsWith("static_natural_")
      && !keys.targetname
      && origin[0] >= -2450 && origin[0] <= -1900
      && origin[1] >= 250 && origin[1] <= 1450
      && origin[2] >= -600 && origin[2] <= -350
    );
    const removedStructure = removedStructureEntityNumbers.has(number)
      && !keys.targetname
      && ["detail", "func_group"].includes(keys.classname);
    return eastFootprintFoliage || alliedRouteFoliage || removedStructure;
  });
  if (removed.length !== 31 || [...removedStructureEntityNumbers].some((number) => !removed.some((entity) => entity.number === number))) {
    throw new Error(`Expected ten footprint foliage entities and 21 boundary entities, found ${removed.length}`);
  }

  const eastFenceWorldBrushNumbers = new Set([1109, 1110, 1111, 1112, 1113, 1114, 1115, 1124]);
  const alliedGateWorldBrushNumbers = new Set([819, 3224, 3228, 3229]);
  const removedWorldBrushNumbers = new Set([...eastFenceWorldBrushNumbers, ...alliedGateWorldBrushNumbers]);
  if ([...removedWorldBrushNumbers].some((number) => !worldBrushBlocks.some((brush) => brush.number === number))) {
    throw new Error("A documented boundary world brush is missing from the canonical source");
  }

  const removedIndexes = new Set();
  for (const entity of removed) {
    for (let index = entity.markerIndex; index <= entity.closeIndex; index += 1) removedIndexes.add(index);
  }
  for (const brush of worldBrushBlocks.filter(({ number }) => removedWorldBrushNumbers.has(number))) {
    for (let index = brush.markerIndex; index <= brush.closeIndex; index += 1) removedIndexes.add(index);
  }

  return {
    firstEntityMarker,
    worldBrushBlocks,
    eastFenceEntityNumbers,
    alliedGateEntityNumbers,
    removedStructureEntityNumbers,
    eastFenceWorldBrushNumbers,
    alliedGateWorldBrushNumbers,
    removedWorldBrushNumbers,
    removed,
    removedIndexes,
    retainedSourceLines: sourceLines.filter((_line, index) => !removedIndexes.has(index)),
  };
};
