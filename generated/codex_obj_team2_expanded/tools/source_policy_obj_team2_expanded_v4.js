"use strict";

module.exports = function applyRevision4SourcePolicy({ sourceLines, entityBlocks, blockAt, vector }) {
  const firstEntityMarker = sourceLines.indexOf("// entity 1");
  if (firstEntityMarker < 0 || sourceLines[firstEntityMarker - 1] !== "}") throw new Error("Could not locate the worldspawn close before entity 1");

  const worldBrushBlocks = [];
  for (let index = 0; index < firstEntityMarker; index += 1) {
    const marker = sourceLines[index].match(/^\/\/ brush (\d+)$/);
    if (!marker) continue;
    if (sourceLines[index + 1].trim() !== "{") throw new Error(`Unexpected world-brush opening at source line ${index + 2}`);
    const block = blockAt(index + 1);
    worldBrushBlocks.push({ markerIndex: index, ...block, number: Number(marker[1]) });
    index = block.closeIndex;
  }

  const range = (first, last) => Array.from({ length: last - first + 1 }, (_value, index) => first + index);
  const westFenceEntityNumbers = new Set(range(425, 446));
  const southEastFenceEntityNumbers = new Set(range(648, 684));
  const fenceEntityNumbers = new Set([...westFenceEntityNumbers, ...southEastFenceEntityNumbers]);
  const fenceWorldBrushNumbers = new Set([811, 812, 819, 820, ...range(1109, 1124), ...range(3217, 3229)]);

  function inBox(origin, minX, maxX, minY, maxY, minZ = -1000, maxZ = 1000) {
    return origin[0] >= minX && origin[0] <= maxX
      && origin[1] >= minY && origin[1] <= maxY
      && origin[2] >= minZ && origin[2] <= maxZ;
  }

  function inExpansionFoliageFootprint(origin) {
    return inBox(origin, 3200, 5200, 256, 2944, -700, -300)
      || inBox(origin, -2450, -1900, 250, 1450, -700, -300)
      || inBox(origin, -2432, -960, -320, 384)
      || inBox(origin, -2112, -1472, -1088, -256)
      || inBox(origin, -2112, -128, -1600, -1024)
      || inBox(origin, -192, 3008, -1600, -1152)
      || inBox(origin, 2496, 3136, -1216, 320)
      || inBox(origin, 1472, 3072, 256, 512);
  }

  const removed = entityBlocks.filter(({ number, keys }) => {
    const origin = keys.origin ? vector(keys.origin) : null;
    const footprintFoliage = Boolean(
      origin
      && (keys.classname || "").startsWith("static_natural_")
      && !keys.targetname
      && inExpansionFoliageFootprint(origin)
    );
    const fenceOwner = fenceEntityNumbers.has(number)
      && !keys.targetname
      && ["detail", "func_group"].includes(keys.classname);
    return footprintFoliage || fenceOwner;
  });
  const removedFoliage = removed.filter(({ keys }) => (keys.classname || "").startsWith("static_natural_"));
  if (removedFoliage.length !== 24) throw new Error(`Expected 24 footprint foliage entities, found ${removedFoliage.length}`);
  if ([...fenceEntityNumbers].some((number) => !removed.some((entity) => entity.number === number))) throw new Error("A complete fence-system entity owner is missing from the removal policy");
  if (removed.length !== 83) throw new Error(`Expected 83 removed entities, found ${removed.length}`);

  if ([...fenceWorldBrushNumbers].some((number) => !worldBrushBlocks.some((brush) => brush.number === number))) throw new Error("A complete fence-system world brush is missing from the canonical source");

  const removedIndexes = new Set();
  for (const entity of removed) {
    for (let index = entity.markerIndex; index <= entity.closeIndex; index += 1) removedIndexes.add(index);
  }
  for (const brush of worldBrushBlocks.filter(({ number }) => fenceWorldBrushNumbers.has(number))) {
    for (let index = brush.markerIndex; index <= brush.closeIndex; index += 1) removedIndexes.add(index);
  }

  return {
    firstEntityMarker,
    worldBrushBlocks,
    westFenceEntityNumbers,
    southEastFenceEntityNumbers,
    fenceEntityNumbers,
    fenceWorldBrushNumbers,
    removed,
    removedIndexes,
    retainedSourceLines: sourceLines.filter((_line, index) => !removedIndexes.has(index)),
  };
};
