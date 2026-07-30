const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const mapName = process.argv[2] || "codex_inferno";
const outputRoot = path.resolve(process.argv[3] || path.join(__dirname, ".."));
const blueprintPath = path.join(
  outputRoot,
  "inferno-layout-reference-audit.json"
);
const mainDir = path.join(outputRoot, "main");
const mapDir = path.join(mainDir, "maps", "dm");

if (!/^[A-Za-z0-9_]+$/.test(mapName)) {
  throw new Error("Map name may contain only letters, numbers, and underscores");
}
if (!fs.existsSync(blueprintPath)) {
  throw new Error(
    `Missing measured Inferno blueprint: ${blueprintPath}. Run audit_inferno_layout.js first.`
  );
}

fs.mkdirSync(mapDir, { recursive: true });

const blueprintBytes = fs.readFileSync(blueprintPath);
const blueprint = JSON.parse(blueprintBytes.toString("utf8"));
const gridSize = blueprint.walkGrid.cellSize;
const halfGrid = gridSize / 2;
const measuredCells = blueprint.walkGrid.cells;
const measuredEdges = new Set(
  blueprint.walkGrid.edges.map(([left, right]) =>
    [left, right].sort().join("|")
  )
);

if (gridSize !== 32) {
  throw new Error(`Expected a 32-unit Inferno audit grid, received ${gridSize}`);
}
if (measuredCells.length < 6000 || measuredEdges.size < 10000) {
  throw new Error("Measured Inferno blueprint is incomplete");
}

const T = {
  sky: "sky/mohday1",
  caulk: "common/caulk",
  clip: "common/playerclip",
  cobble: "codex_inferno/cobblestone",
  stoneFloor: "codex_inferno/stone_floor",
  stoneTrim: "codex_inferno/stone_trim",
  plasterCream: "codex_inferno/plaster_cream",
  plasterOchre: "codex_inferno/plaster_ochre",
  plasterRose: "codex_inferno/plaster_rose",
  plasterWhite: "codex_inferno/plaster_white",
  brick: "codex_inferno/brick",
  roof: "codex_inferno/roof_tile",
  grass: "codex_inferno/grass",
  wood: "codex_inferno/wood",
  woodDark: "codex_inferno/wood_dark",
  metal: "codex_inferno/painted_metal",
  shutter: "codex_inferno/shutter_green",
  window: "codex_inferno/window_dark",
  ceiling: "codex_inferno/ceiling",
};

function fmt(value) {
  const rounded = Math.abs(value) < 0.0005 ? 0 : value;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(3);
}

function textureScale(texture) {
  if (texture === T.window || texture === T.shutter) return [0.25, 0.25];
  return [0.5, 0.5];
}

function face(
  points,
  texture,
  shiftX = 0,
  shiftY = 0,
  rotation = 0,
  surfaceFlags = ""
) {
  const [scaleX, scaleY] = textureScale(texture);
  const pointText = points
    .map((point) => `( ${point.map(fmt).join(" ")} )`)
    .join(" ");
  return `${pointText} ${texture} ${shiftX} ${shiftY} ${rotation} ${scaleX} ${scaleY} 0 0 0${surfaceFlags}`;
}

function boxBrush(minimum, maximum, texture, isDetail = true) {
  const [minX, minY, minZ] = minimum;
  const [maxX, maxY, maxZ] = maximum;
  if (!(minX < maxX && minY < maxY && minZ < maxZ)) {
    throw new Error(
      `Invalid box ${JSON.stringify({ minimum, maximum, texture })}`
    );
  }
  const surfaceFlags = isDetail ? " +surfaceparm detail" : "";
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], texture, 0, 0, 0, surfaceFlags),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], texture, 0, 0, 0, surfaceFlags),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], texture, 0, 0, 0, surfaceFlags),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], texture, 0, 0, 0, surfaceFlags),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], texture, 0, 0, 0, surfaceFlags),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], texture, 0, 0, 0, surfaceFlags),
    "}",
  ].join("\n");
}

function subtract(left, right) {
  return [left[0] - right[0], left[1] - right[1], left[2] - right[2]];
}

function cross(left, right) {
  return [
    left[1] * right[2] - left[2] * right[1],
    left[2] * right[0] - left[0] * right[2],
    left[0] * right[1] - left[1] * right[0],
  ];
}

function dot(left, right) {
  return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

function convexBrush(facePolygons, centroid, texture, isDetail = true) {
  const lines = ["{"];
  const surfaceFlags = isDetail ? " +surfaceparm detail" : "";
  for (const polygon of facePolygons) {
    let [a, b, c] = polygon;
    const normal = cross(subtract(b, a), subtract(c, a));
    if (Math.abs(normal[0]) + Math.abs(normal[1]) + Math.abs(normal[2]) < 0.001) {
      throw new Error(`Degenerate convex face: ${JSON.stringify(polygon)}`);
    }
    if (dot(normal, subtract(centroid, a)) < 0) [b, c] = [c, b];
    lines.push(face([a, b, c], texture, 0, 0, 0, surfaceFlags));
  }
  lines.push("}");
  return lines.join("\n");
}

function prismBrush(points, minZ, maxZ, texture) {
  const centroid = [
    points.reduce((sum, point) => sum + point[0], 0) / points.length,
    points.reduce((sum, point) => sum + point[1], 0) / points.length,
    (minZ + maxZ) / 2,
  ];
  const bottom = points.map(([x, y]) => [x, y, minZ]);
  const top = points.map(([x, y]) => [x, y, maxZ]);
  const polygons = [bottom, [...top].reverse()];
  for (let index = 0; index < points.length; index++) {
    const next = (index + 1) % points.length;
    polygons.push([bottom[index], top[index], top[next], bottom[next]]);
  }
  return convexBrush(polygons, centroid, texture);
}

function orientedBox(
  centerX,
  centerY,
  length,
  width,
  minZ,
  maxZ,
  yaw,
  texture
) {
  const radians = (yaw * Math.PI) / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const points = [
    [-length / 2, -width / 2],
    [length / 2, -width / 2],
    [length / 2, width / 2],
    [-length / 2, width / 2],
  ].map(([x, y]) => [
    centerX + x * cosine - y * sine,
    centerY + x * sine + y * cosine,
  ]);
  return prismBrush(points, minZ, maxZ, texture);
}

function gableRoof(rectangle, baseZ, rise, texture) {
  const { x0, y0, x1, y1 } = rectangle;
  const width = x1 - x0;
  const depth = y1 - y0;
  let vertices;
  let polygons;
  if (width >= depth) {
    const middleY = (y0 + y1) / 2;
    const a = [x0, y0, baseZ];
    const b = [x0, y1, baseZ];
    const c = [x0, middleY, baseZ + rise];
    const d = [x1, y0, baseZ];
    const e = [x1, y1, baseZ];
    const f = [x1, middleY, baseZ + rise];
    vertices = [a, b, c, d, e, f];
    polygons = [
      [a, c, b],
      [d, e, f],
      [a, b, e, d],
      [a, d, f, c],
      [b, c, f, e],
    ];
  } else {
    const middleX = (x0 + x1) / 2;
    const a = [x0, y0, baseZ];
    const b = [x1, y0, baseZ];
    const c = [middleX, y0, baseZ + rise];
    const d = [x0, y1, baseZ];
    const e = [x1, y1, baseZ];
    const f = [middleX, y1, baseZ + rise];
    vertices = [a, b, c, d, e, f];
    polygons = [
      [a, b, c],
      [d, f, e],
      [a, d, e, b],
      [a, c, f, d],
      [b, e, f, c],
    ];
  }
  const centroid = [
    vertices.reduce((sum, point) => sum + point[0], 0) / vertices.length,
    vertices.reduce((sum, point) => sum + point[1], 0) / vertices.length,
    baseZ + rise / 3,
  ];
  return convexBrush(polygons, centroid, texture);
}

function pointEntity(classname, properties = {}) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) {
    lines.push(`"${key}" "${value}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function nodeKey(cell) {
  return `${cell.x},${cell.y},${cell.z}`;
}

function xyKey(x, y) {
  return `${x},${y}`;
}

function edgeKey(left, right) {
  return [nodeKey(left), nodeKey(right)].sort().join("|");
}

function stableHash(x, y) {
  let value = ((x + 37) * 73856093) ^ ((y + 19) * 19349663);
  value ^= value >>> 13;
  return Math.abs(value);
}

function sourceMaterialRole(material) {
  const lower = material.toLowerCase();
  if (lower.includes("wood")) return "wood";
  if (lower.includes("tile") || lower.includes("herringbone")) return "tile";
  if (lower.includes("dirt") || lower.includes("grass")) return "earth";
  if (
    lower.includes("flagstone") ||
    lower.includes("concrete") ||
    lower.includes("metal")
  ) {
    return "stone";
  }
  if (lower.includes("liquid")) return "water";
  return "cobble";
}

function floorTexture(cell) {
  const role = sourceMaterialRole(cell.material);
  if (role === "wood") return T.wood;
  if (role === "tile" || role === "stone" || role === "water") {
    return T.stoneFloor;
  }
  if (role === "earth") return T.grass;
  return T.cobble;
}

function facadeTexture(cell) {
  if (cell.y > 2450) return cell.x > 720 ? T.brick : T.plasterCream;
  if (cell.x > 1500 && cell.y < 900) return T.plasterWhite;
  if (cell.x < -750) return T.plasterOchre;
  if (cell.x < 500 && cell.y > 1100) return T.plasterRose;
  return T.plasterCream;
}

function isIndoorCell(cell) {
  return sourceMaterialRole(cell.material) === "wood";
}

function wallTop(cell) {
  if (isIndoorCell(cell)) {
    const measuredClearance =
      Number.isFinite(cell.ceilingZ) && cell.ceilingZ - cell.z >= 112
        ? Math.min(224, cell.ceilingZ - cell.z)
        : 192;
    return cell.z + Math.round(measuredClearance / 16) * 16;
  }
  return cell.z + 288;
}

const cellsByXY = new Map();
const cellsByNode = new Map();
for (const cell of measuredCells) {
  const key = xyKey(cell.x, cell.y);
  if (!cellsByXY.has(key)) cellsByXY.set(key, []);
  cellsByXY.get(key).push(cell);
  cellsByNode.set(nodeKey(cell), cell);
}

function hasAllowedTransition(cell, targetX, targetY) {
  return (cellsByXY.get(xyKey(targetX, targetY)) || []).some((candidate) =>
    measuredEdges.has(edgeKey(cell, candidate))
  );
}

function greedyMerge(items, groupForItem) {
  const groups = new Map();
  for (const item of items) {
    const groupKey = groupForItem(item);
    if (!groups.has(groupKey)) groups.set(groupKey, new Map());
    groups.get(groupKey).set(xyKey(item.x, item.y), item);
  }

  const rectangles = [];
  for (const [groupKey, pointMap] of groups) {
    const used = new Set();
    const points = [...pointMap.values()].sort(
      (left, right) => left.y - right.y || left.x - right.x
    );
    for (const point of points) {
      const startKey = xyKey(point.x, point.y);
      if (used.has(startKey)) continue;

      let width = 1;
      while (
        pointMap.has(xyKey(point.x + width * gridSize, point.y)) &&
        !used.has(xyKey(point.x + width * gridSize, point.y))
      ) {
        width++;
      }

      let height = 1;
      extendHeight: while (true) {
        for (let xIndex = 0; xIndex < width; xIndex++) {
          const candidateKey = xyKey(
            point.x + xIndex * gridSize,
            point.y + height * gridSize
          );
          if (!pointMap.has(candidateKey) || used.has(candidateKey)) {
            break extendHeight;
          }
        }
        height++;
      }

      for (let yIndex = 0; yIndex < height; yIndex++) {
        for (let xIndex = 0; xIndex < width; xIndex++) {
          used.add(
            xyKey(
              point.x + xIndex * gridSize,
              point.y + yIndex * gridSize
            )
          );
        }
      }

      rectangles.push({
        groupKey,
        sample: point,
        x0: point.x - halfGrid,
        y0: point.y - halfGrid,
        x1: point.x - halfGrid + width * gridSize,
        y1: point.y - halfGrid + height * gridSize,
      });
    }
  }
  return rectangles;
}

const floorRectangles = greedyMerge(
  measuredCells,
  (cell) => `${cell.z}|${floorTexture(cell)}`
);

const ceilingCells = measuredCells
  .filter(isIndoorCell)
  .map((cell) => {
    const top = wallTop(cell);
    return { ...cell, authoredCeilingZ: top };
  });
const ceilingRectangles = greedyMerge(
  ceilingCells,
  (cell) => `${cell.authoredCeilingZ}|${T.ceiling}`
);

const rawWallSegments = new Map();
const directions = [
  { name: "west", dx: -gridSize, dy: 0, orientation: "vertical" },
  { name: "east", dx: gridSize, dy: 0, orientation: "vertical" },
  { name: "south", dx: 0, dy: -gridSize, orientation: "horizontal" },
  { name: "north", dx: 0, dy: gridSize, orientation: "horizontal" },
];

for (const cell of measuredCells) {
  for (const direction of directions) {
    if (hasAllowedTransition(cell, cell.x + direction.dx, cell.y + direction.dy)) {
      continue;
    }

    const isVertical = direction.orientation === "vertical";
    const fixed = isVertical
      ? cell.x + direction.dx / 2
      : cell.y + direction.dy / 2;
    const start = isVertical ? cell.y - halfGrid : cell.x - halfGrid;
    const end = start + gridSize;
    const segmentKey = [
      direction.orientation,
      fixed,
      start,
      end,
      cell.z,
    ].join("|");
    const outdoor = !isIndoorCell(cell);
    const candidate = {
      orientation: direction.orientation,
      fixed,
      start,
      end,
      z0: cell.z - 32,
      z1: wallTop(cell),
      texture: facadeTexture(cell),
      side: direction.name,
      outdoor,
      massDepth: outdoor ? 112 : 16,
    };

    const existing = rawWallSegments.get(segmentKey);
    if (!existing) {
      rawWallSegments.set(segmentKey, candidate);
    } else {
      existing.z1 = Math.max(existing.z1, candidate.z1);
      if (existing.side !== candidate.side) {
        existing.massDepth = 16;
        existing.outdoor = false;
      } else if (candidate.massDepth > existing.massDepth) {
        existing.massDepth = candidate.massDepth;
        existing.outdoor = candidate.outdoor;
        existing.texture = candidate.texture;
      }
    }
  }
}

function mergeWallSegments(segments) {
  const groups = new Map();
  for (const segment of segments) {
    const key = [
      segment.orientation,
      segment.fixed,
      segment.z0,
      segment.z1,
      segment.texture,
      segment.side,
      segment.massDepth,
      segment.outdoor ? 1 : 0,
    ].join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(segment);
  }

  const merged = [];
  for (const group of groups.values()) {
    group.sort((left, right) => left.start - right.start);
    let current = { ...group[0] };
    for (const next of group.slice(1)) {
      if (Math.abs(current.end - next.start) < 0.01) {
        current.end = next.end;
      } else {
        merged.push(current);
        current = { ...next };
      }
    }
    merged.push(current);
  }
  return merged;
}

const wallRuns = mergeWallSegments([...rawWallSegments.values()]);
const worldBrushes = [];
const authoredBrushes = [];
const addWorldBox = (minimum, maximum, texture) =>
  worldBrushes.push(boxBrush(minimum, maximum, texture));
const addAuthoredBox = (minimum, maximum, texture) =>
  authoredBrushes.push(boxBrush(minimum, maximum, texture));
const addStructuralBox = (minimum, maximum, texture) =>
  worldBrushes.push(boxBrush(minimum, maximum, texture, false));

for (const rectangle of floorRectangles) {
  const [zText, texture] = rectangle.groupKey.split("|");
  const z = Number(zText);
  addWorldBox(
    [rectangle.x0, rectangle.y0, z - 32],
    [rectangle.x1, rectangle.y1, z],
    texture
  );
}

let facadeWindowCount = 0;
let roofMassCount = 0;

// Revision 2 extruded every blocked route edge into shallow visible strips.
// Revision 3 grows a continuous village mass around measured routes, fills
// enclosed pockets, and merges the result into complete building blocks.
const routeColumns = new Set(measuredCells.map((cell) => xyKey(cell.x, cell.y)));
const routeXs = measuredCells.map((cell) => cell.x);
const routeYs = measuredCells.map((cell) => cell.y);
const massMarginCells = 10;
const minGridX = Math.min(...routeXs) - massMarginCells * gridSize;
const maxGridX = Math.max(...routeXs) + massMarginCells * gridSize;
const minGridY = Math.min(...routeYs) - massMarginCells * gridSize;
const maxGridY = Math.max(...routeYs) + massMarginCells * gridSize;
const massColumns = new Set();
const dilationVisited = new Set(routeColumns);
const dilationFrontier = [...routeColumns].map((key) => {
  const [x, y] = key.split(",").map(Number);
  return { x, y, distance: 0 };
});
for (let cursor = 0; cursor < dilationFrontier.length; cursor++) {
  const current = dilationFrontier[cursor];
  if (current.distance >= massMarginCells) continue;
  for (const direction of directions) {
    const x = current.x + direction.dx;
    const y = current.y + direction.dy;
    if (x < minGridX || x > maxGridX || y < minGridY || y > maxGridY) continue;
    const key = xyKey(x, y);
    if (dilationVisited.has(key)) continue;
    dilationVisited.add(key);
    dilationFrontier.push({ x, y, distance: current.distance + 1 });
    if (!routeColumns.has(key)) massColumns.add(key);
  }
}

// Flood from the outside of the authored village. Any blocked pocket that is
// no longer reachable is part of a complete building/courtyard mass, not sky.
const exteriorColumns = new Set();
const exteriorQueue = [];
function seedExteriorColumn(x, y) {
  const key = xyKey(x, y);
  if (
    routeColumns.has(key) ||
    massColumns.has(key) ||
    exteriorColumns.has(key)
  ) return;
  exteriorColumns.add(key);
  exteriorQueue.push({ x, y });
}
for (let x = minGridX; x <= maxGridX; x += gridSize) {
  seedExteriorColumn(x, minGridY);
  seedExteriorColumn(x, maxGridY);
}
for (let y = minGridY; y <= maxGridY; y += gridSize) {
  seedExteriorColumn(minGridX, y);
  seedExteriorColumn(maxGridX, y);
}
for (let cursor = 0; cursor < exteriorQueue.length; cursor++) {
  const current = exteriorQueue[cursor];
  for (const direction of directions) {
    const x = current.x + direction.dx;
    const y = current.y + direction.dy;
    if (x < minGridX || x > maxGridX || y < minGridY || y > maxGridY) continue;
    seedExteriorColumn(x, y);
  }
}
for (let y = minGridY; y <= maxGridY; y += gridSize) {
  for (let x = minGridX; x <= maxGridX; x += gridSize) {
    const key = xyKey(x, y);
    if (!routeColumns.has(key) && !exteriorColumns.has(key)) massColumns.add(key);
  }
}

// Deliberate callout-scale massing. A whole callout shares a material and roof
// datum; sampled floor-height noise no longer fragments its architecture.
function massingZone(x, y) {
  if (y >= 2380 && x <= 900) return { name: "b_site", top: 432, texture: T.plasterWhite };
  if (y >= 950 && x <= 650) return { name: "banana", top: 368, texture: T.plasterOchre };
  if (y >= 1350 && x >= 650) return { name: "ct_library", top: 416, texture: T.plasterCream };
  if (x >= 1450 && y <= 950) return { name: "a_site", top: 400, texture: T.plasterRose };
  if (x >= 650 && y <= 650) return { name: "apartments", top: 464, texture: T.plasterCream };
  if (x <= -900 && y <= 950) return { name: "t_spawn", top: 352, texture: T.plasterOchre };
  if (y <= 250) return { name: "alt_mid", top: 384, texture: T.plasterRose };
  return { name: "mid", top: 400, texture: T.plasterWhite };
}
const massCells = [...massColumns].map((key) => {
  const [x, y] = key.split(",").map(Number);
  return { x, y, zone: massingZone(x, y) };
});
const buildingMassRectangles = greedyMerge(
  massCells,
  (cell) => `${cell.zone.name}|${cell.zone.top}|${cell.zone.texture}`
);
const massBaseZ = Math.min(...measuredCells.map((cell) => cell.z)) - 96;
let gableRoofCount = 0;
for (const rectangle of buildingMassRectangles) {
  const [, topText, texture] = rectangle.groupKey.split("|");
  const top = Number(topText);
  addWorldBox(
    [rectangle.x0, rectangle.y0, massBaseZ],
    [rectangle.x1, rectangle.y1, top],
    texture
  );
  const width = rectangle.x1 - rectangle.x0;
  const depth = rectangle.y1 - rectangle.y0;
  if (
    gableRoofCount < 72 &&
    Math.min(width, depth) >= 128 &&
    width * depth >= 65536
  ) {
    authoredBrushes.push(gableRoof(rectangle, top, 72, T.roof));
    gableRoofCount++;
  } else {
    addAuthoredBox(
      [rectangle.x0 - 4, rectangle.y0 - 4, top],
      [rectangle.x1 + 4, rectangle.y1 + 4, top + 16],
      T.roof
    );
  }
  roofMassCount++;
}
function addWindowOnRun(run, position) {
  const bottom = run.z0 + 32;
  if (run.z1 - bottom < 224) return;
  const lowZ = bottom + 104;
  const highZ = bottom + 184;
  if (highZ + 16 >= run.z1) return;

  if (run.orientation === "vertical") {
    const accessibleX =
      run.side === "east" ? run.fixed - 10 : run.fixed + 8;
    addAuthoredBox(
      [accessibleX, position - 34, lowZ],
      [accessibleX + 2, position + 34, highZ],
      T.window
    );
    addAuthoredBox(
      [accessibleX - 1, position - 58, lowZ],
      [accessibleX + 3, position - 39, highZ],
      T.shutter
    );
    addAuthoredBox(
      [accessibleX - 1, position + 39, lowZ],
      [accessibleX + 3, position + 58, highZ],
      T.shutter
    );
  } else {
    const accessibleY =
      run.side === "north" ? run.fixed - 10 : run.fixed + 8;
    addAuthoredBox(
      [position - 34, accessibleY, lowZ],
      [position + 34, accessibleY + 2, highZ],
      T.window
    );
    addAuthoredBox(
      [position - 58, accessibleY - 1, lowZ],
      [position - 39, accessibleY + 3, highZ],
      T.shutter
    );
    addAuthoredBox(
      [position + 39, accessibleY - 1, lowZ],
      [position + 58, accessibleY + 3, highZ],
      T.shutter
    );
  }
  facadeWindowCount++;
}

for (const run of wallRuns.filter((candidate) => !candidate.outdoor)) {
  const thickness = 16;
  let minimum;
  let maximum;
  if (run.orientation === "vertical") {
    if (run.massDepth > thickness && run.side === "east") {
      minimum = [run.fixed - thickness / 2, run.start, run.z0];
      maximum = [run.fixed + run.massDepth, run.end, run.z1];
    } else if (run.massDepth > thickness && run.side === "west") {
      minimum = [run.fixed - run.massDepth, run.start, run.z0];
      maximum = [run.fixed + thickness / 2, run.end, run.z1];
    } else {
      minimum = [run.fixed - thickness / 2, run.start, run.z0];
      maximum = [run.fixed + thickness / 2, run.end, run.z1];
    }
  } else if (run.massDepth > thickness && run.side === "north") {
    minimum = [run.start, run.fixed - thickness / 2, run.z0];
    maximum = [run.end, run.fixed + run.massDepth, run.z1];
  } else if (run.massDepth > thickness && run.side === "south") {
    minimum = [run.start, run.fixed - run.massDepth, run.z0];
    maximum = [run.end, run.fixed + thickness / 2, run.z1];
  } else {
    minimum = [run.start, run.fixed - thickness / 2, run.z0];
    maximum = [run.end, run.fixed + thickness / 2, run.z1];
  }
  addWorldBox(minimum, maximum, run.texture);

  const runLength = run.end - run.start;
  if (run.outdoor) {
    if (runLength >= 96) {
      const trimMinimum = [...minimum];
      const trimMaximum = [...maximum];
      trimMaximum[2] = Math.min(run.z0 + 64, run.z1);
      addAuthoredBox(trimMinimum, trimMaximum, T.stoneTrim);
    }

    if (run.massDepth > thickness && runLength >= 96) {
      const roofMinimum = [
        minimum[0] - 6,
        minimum[1] - 6,
        run.z1,
      ];
      const roofMaximum = [
        maximum[0] + 6,
        maximum[1] + 6,
        run.z1 + 18,
      ];
      addAuthoredBox(roofMinimum, roofMaximum, T.roof);
      roofMassCount++;
    }

    if (runLength >= 176) {
      for (
        let position = run.start + 96;
        position <= run.end - 80;
        position += 224
      ) {
        addWindowOnRun(run, position);
      }
    }
  }
}

for (const rectangle of ceilingRectangles) {
  const [zText] = rectangle.groupKey.split("|");
  const z = Number(zText);
  addWorldBox(
    [rectangle.x0, rectangle.y0, z],
    [rectangle.x1, rectangle.y1, z + 16],
    T.ceiling
  );
}

const coordinateBounds = {
  minX: Math.min(...measuredCells.map((cell) => cell.x)) - 352,
  maxX: Math.max(...measuredCells.map((cell) => cell.x)) + 352,
  minY: Math.min(...measuredCells.map((cell) => cell.y)) - 352,
  maxY: Math.max(...measuredCells.map((cell) => cell.y)) + 352,
  minZ: Math.min(...measuredCells.map((cell) => cell.z)) - 160,
  skyZ: 768,
};

// The shell seals the newly authored map but does not define its topology.
addStructuralBox(
  [coordinateBounds.minX, coordinateBounds.minY, coordinateBounds.minZ - 64],
  [coordinateBounds.maxX, coordinateBounds.maxY, coordinateBounds.minZ],
  T.sky
);
addStructuralBox(
  [coordinateBounds.minX, coordinateBounds.minY, coordinateBounds.skyZ],
  [coordinateBounds.maxX, coordinateBounds.maxY, coordinateBounds.skyZ + 64],
  T.sky
);
addStructuralBox(
  [coordinateBounds.minX - 64, coordinateBounds.minY - 64, coordinateBounds.minZ - 64],
  [coordinateBounds.minX, coordinateBounds.maxY + 64, coordinateBounds.skyZ + 64],
  T.sky
);
addStructuralBox(
  [coordinateBounds.maxX, coordinateBounds.minY - 64, coordinateBounds.minZ - 64],
  [coordinateBounds.maxX + 64, coordinateBounds.maxY + 64, coordinateBounds.skyZ + 64],
  T.sky
);
addStructuralBox(
  [coordinateBounds.minX, coordinateBounds.minY - 64, coordinateBounds.minZ - 64],
  [coordinateBounds.maxX, coordinateBounds.minY, coordinateBounds.skyZ + 64],
  T.sky
);
addStructuralBox(
  [coordinateBounds.minX, coordinateBounds.maxY, coordinateBounds.minZ - 64],
  [coordinateBounds.maxX, coordinateBounds.maxY + 64, coordinateBounds.skyZ + 64],
  T.sky
);

function nearestWalkCell(x, y, preferredZ = null) {
  let best = null;
  for (const cell of measuredCells) {
    const dx = cell.x - x;
    const dy = cell.y - y;
    const dz = preferredZ === null ? 0 : cell.z - preferredZ;
    const score = dx * dx + dy * dy + dz * dz * 2;
    if (!best || score < best.score) best = { cell, score };
  }
  return best.cell;
}

function addCrate(x, y, size = 80, height = 80, texture = T.wood) {
  const floor = nearestWalkCell(x, y).z;
  addAuthoredBox(
    [x - size / 2, y - size / 2, floor],
    [x + size / 2, y + size / 2, floor + height],
    texture
  );
  addAuthoredBox(
    [x - size / 2 - 3, y - size / 2 - 3, floor + height - 12],
    [x + size / 2 + 3, y + size / 2 + 3, floor + height],
    T.woodDark
  );
}

function addBarrel(x, y, baseZ, height = 52, radius = 22, texture = T.wood) {
  const points = [];
  for (let index = 0; index < 8; index++) {
    const angle = (index * Math.PI * 2) / 8;
    points.push([
      x + Math.cos(angle) * radius,
      y + Math.sin(angle) * radius,
    ]);
  }
  authoredBrushes.push(prismBrush(points, baseZ, baseZ + height, texture));
}

function addMeasuredArch(x, y) {
  const floor = nearestWalkCell(x, y).z;
  const nearby = measuredCells.filter(
    (cell) => Math.abs(cell.x - x) <= 176 && Math.abs(cell.y - y) <= 176
  );
  const horizontal = nearby.filter((cell) => Math.abs(cell.y - y) <= 40).length;
  const vertical = nearby.filter((cell) => Math.abs(cell.x - x) <= 40).length;
  const opening = 128;
  const pillar = 22;
  const archHeight = floor + 176;
  const lintelTop = archHeight + 40;

  if (horizontal >= vertical) {
    addAuthoredBox(
      [x - 20, y - opening / 2 - pillar, floor],
      [x + 20, y - opening / 2, archHeight],
      T.brick
    );
    addAuthoredBox(
      [x - 20, y + opening / 2, floor],
      [x + 20, y + opening / 2 + pillar, archHeight],
      T.brick
    );
    addAuthoredBox(
      [x - 20, y - opening / 2 - pillar, archHeight],
      [x + 20, y + opening / 2 + pillar, lintelTop],
      T.stoneTrim
    );
  } else {
    addAuthoredBox(
      [x - opening / 2 - pillar, y - 20, floor],
      [x - opening / 2, y + 20, archHeight],
      T.brick
    );
    addAuthoredBox(
      [x + opening / 2, y - 20, floor],
      [x + opening / 2 + pillar, y + 20, archHeight],
      T.brick
    );
    addAuthoredBox(
      [x - opening / 2 - pillar, y - 20, archHeight],
      [x + opening / 2 + pillar, y + 20, lintelTop],
      T.stoneTrim
    );
  }
}

function addSiteSurface(target, texture) {
  const [minX, minY] = target.bounds.minimum;
  const [maxX, maxY] = target.bounds.maximum;
  const cells = measuredCells.filter(
    (cell) =>
      cell.x >= minX &&
      cell.x <= maxX &&
      cell.y >= minY &&
      cell.y <= maxY
  );
  const rectangles = greedyMerge(cells, (cell) => `${cell.z}|${texture}`);
  for (const rectangle of rectangles) {
    const [zText] = rectangle.groupKey.split("|");
    const z = Number(zText);
    addAuthoredBox(
      [rectangle.x0, rectangle.y0, z],
      [rectangle.x1, rectangle.y1, z + 4],
      texture
    );
  }
  return rectangles.length;
}

const aTarget = blueprint.bombTargets
  .slice()
  .sort(
    (left, right) =>
      right.bounds.minimum[0] - left.bounds.minimum[0]
  )[0];
const bTarget = blueprint.bombTargets
  .slice()
  .sort(
    (left, right) =>
      left.bounds.minimum[0] - right.bounds.minimum[0]
  )[0];
const siteSurfaceCount =
  addSiteSurface(aTarget, T.stoneFloor) +
  addSiteSurface(bTarget, T.stoneFloor);

// B fountain at the measured Source landmark origin.
const fountainX = 352;
const fountainY = 2768;
const fountainFloor = nearestWalkCell(fountainX, fountainY, 175).z;
const fountainOuter = [];
const fountainInner = [];
for (let index = 0; index < 12; index++) {
  const angle = (index * Math.PI * 2) / 12;
  fountainOuter.push([
    fountainX + Math.cos(angle) * 156,
    fountainY + Math.sin(angle) * 156,
  ]);
  fountainInner.push([
    fountainX + Math.cos(angle) * 43,
    fountainY + Math.sin(angle) * 43,
  ]);
}
authoredBrushes.push(
  prismBrush(
    fountainOuter,
    fountainFloor,
    fountainFloor + 28,
    T.stoneTrim
  )
);
authoredBrushes.push(
  prismBrush(
    fountainInner,
    fountainFloor + 28,
    fountainFloor + 136,
    T.stoneTrim
  )
);

// CT well at the measured Source landmark origin. This is a real blocking
// landmark, so its simple AA-native silhouette intentionally retains collision.
const wellX = 1952;
const wellY = 2562;
const wellFloor = nearestWalkCell(wellX, wellY, 125).z;
const wellBase = [];
for (let index = 0; index < 12; index++) {
  const angle = (index * Math.PI * 2) / 12;
  wellBase.push([
    wellX + Math.cos(angle) * 62,
    wellY + Math.sin(angle) * 62,
  ]);
}
authoredBrushes.push(
  prismBrush(wellBase, wellFloor, wellFloor + 34, T.stoneTrim)
);
addAuthoredBox(
  [wellX - 58, wellY - 50, wellFloor + 34],
  [wellX - 46, wellY + 50, wellFloor + 142],
  T.woodDark
);
addAuthoredBox(
  [wellX + 46, wellY - 50, wellFloor + 34],
  [wellX + 58, wellY + 50, wellFloor + 142],
  T.woodDark
);
addAuthoredBox(
  [wellX - 70, wellY - 58, wellFloor + 130],
  [wellX + 70, wellY + 58, wellFloor + 146],
  T.wood
);
authoredBrushes.push(
  gableRoof(
    { x0: wellX - 78, y0: wellY - 66, x1: wellX + 78, y1: wellY + 66 },
    wellFloor + 146,
    38,
    T.roof
  )
);
// Coffins and barrel stacks use the supplied landmark coordinates.
addCrate(520, 3064, 92, 64, T.stoneTrim);
addCrate(596, 2960, 80, 60, T.stoneTrim);
addCrate(536, 3124, 72, 54, T.stoneTrim);
const bBarrelFloor = nearestWalkCell(210, 3050, 160).z;
for (const [x, y, level] of [
  [184, 3052, 0],
  [222, 3052, 0],
  [260, 3052, 0],
  [202, 3087, 0],
  [240, 3087, 0],
  [203, 3053, 1],
  [241, 3053, 1],
]) {
  addBarrel(x, y, bBarrelFloor + level * 52, 52, 19, T.woodDark);
}

// A-site boxes and the hay/cart silhouette near pit.
addCrate(1850, 350, 88, 88);
addCrate(2090, 520, 96, 112);
addCrate(2180, 640, 72, 72);
const hayFloor = nearestWalkCell(1980, -80, 200).z;
authoredBrushes.push(
  orientedBox(1980, -80, 184, 72, hayFloor, hayFloor + 36, -8, T.wood)
);
for (const [x, y, zOffset, length] of [
  [1935, -86, 38, 78],
  [1992, -82, 38, 82],
  [2038, -76, 38, 72],
  [1985, -80, 72, 80],
]) {
  authoredBrushes.push(
    orientedBox(
      x,
      y,
      length,
      34,
      hayFloor + zOffset,
      hayFloor + zOffset + 28,
      -8,
      T.plasterOchre
    )
  );
}

// Measured major passage arches; these remain open gameplay portals.
const measuredArchOrigins = [
  [885, 144],
  [596, 449],
  [-1026, -128],
  [-1026, -376],
  [-904, 128],
  [-888, 520],
  [108, 988],
  [1028, 1884],
  [101, 2551],
  [40, 3179],
];
for (const [x, y] of measuredArchOrigins) addMeasuredArch(x, y);

// A few measured balconies preserve Inferno's vertical facade rhythm.
for (const balcony of [
  { x: 1130, y: 417, z: 304, alongX: true },
  { x: 1296, y: 796, z: 344, alongX: false },
  { x: 968, y: 304, z: 268, alongX: false },
  { x: 1344, y: 2310, z: 490, alongX: true },
]) {
  if (balcony.alongX) {
    addAuthoredBox(
      [balcony.x - 82, balcony.y - 36, balcony.z - 12],
      [balcony.x + 82, balcony.y + 12, balcony.z],
      T.wood
    );
    addAuthoredBox(
      [balcony.x - 82, balcony.y - 42, balcony.z],
      [balcony.x + 82, balcony.y - 36, balcony.z + 42],
      T.metal
    );
  } else {
    addAuthoredBox(
      [balcony.x - 36, balcony.y - 82, balcony.z - 12],
      [balcony.x + 12, balcony.y + 82, balcony.z],
      T.wood
    );
    addAuthoredBox(
      [balcony.x - 42, balcony.y - 82, balcony.z],
      [balcony.x - 36, balcony.y + 82, balcony.z + 42],
      T.metal
    );
  }
}

// The visible bell tower occupies the measured non-walkable village block.
const towerBase = 128;
addAuthoredBox([964, 984, towerBase], [1124, 1160, 496], T.plasterWhite);
addAuthoredBox([948, 968, 480], [1140, 1176, 512], T.stoneTrim);
addAuthoredBox([974, 976, 336], [1024, 984, 424], T.window);
addAuthoredBox([1064, 1160, 336], [1114, 1168, 424], T.window);
authoredBrushes.push(
  gableRoof({ x0: 940, y0: 960, x1: 1148, y1: 1184 }, 512, 104, T.roof)
);

const entities = [];
const worldspawn = [
  "{",
  `"classname" "worldspawn"`,
  `"message" "Codex Inferno - recognition-first revision 3"`,
  `"ambientlight" "8 9 12"`,
  `"suncolor" "148 128 102"`,
  `"sundirection" "325 212 0"`,
  `"sundiffusecolor" "62 72 92"`,
  `"sundiffuse" "1.15"`,
  `"_color" "1.0 0.95 0.88"`,
  `"farplane" "7600"`,
  `"farplane_color" "0.48 0.54 0.60"`,
  ...worldBrushes.map((brush, index) => `// world brush ${index}\n${brush}`),
  ...authoredBrushes.map(
    (brush, index) => `// authored brush ${index}\n${brush}`
  ),
  "}",
].join("\n");
entities.push(worldspawn);

function normalizeSpawn(sourceSpawn) {
  const preferredFloorZ = sourceSpawn.origin[2] - 40;
  const floor = nearestWalkCell(
    sourceSpawn.origin[0],
    sourceSpawn.origin[1],
    preferredFloorZ
  );
  return {
    origin: [floor.x, floor.y, floor.z + 48],
    angle: Math.round(sourceSpawn.angles?.[1] || 0),
  };
}

function addSpawn(classname, sourceSpawn) {
  const spawn = normalizeSpawn(sourceSpawn);
  entities.push(
    pointEntity(classname, {
      origin: spawn.origin.map(fmt).join(" "),
      angle: String(spawn.angle),
    })
  );
  return spawn;
}

const axisSpawns = blueprint.spawns.terrorist.map((spawn) =>
  addSpawn("info_player_axis", spawn)
);
const alliedSpawns = blueprint.spawns.counterTerrorist.map((spawn) =>
  addSpawn("info_player_allied", spawn)
);
const neutralSpawns = blueprint.spawns.deathmatch.map((spawn) =>
  addSpawn("info_player_deathmatch", spawn)
);
entities.push(
  pointEntity("info_player_start", {
    origin: axisSpawns[0].origin.map(fmt).join(" "),
    angle: String(axisSpawns[0].angle),
  })
);
entities.push(
  pointEntity("info_player_intermission", {
    origin: "420 1500 700",
    angle: "90",
  })
);

const interiorLightCandidates = ceilingCells
  .filter((cell) => wallTop(cell) - cell.z >= 144)
  .sort((left, right) => left.y - right.y || left.x - right.x);
const lightBuckets = new Set();
const interiorLights = [];
for (const cell of interiorLightCandidates) {
  const bucket = `${Math.floor(cell.x / 320)},${Math.floor(cell.y / 320)}`;
  if (lightBuckets.has(bucket)) continue;
  lightBuckets.add(bucket);
  interiorLights.push([cell.x, cell.y, cell.z + 112]);
  if (interiorLights.length >= 24) break;
}
for (const [x, y, z] of interiorLights) {
  entities.push(
    pointEntity("light", {
      origin: `${x} ${y} ${z}`,
      light: "105",
      _color: "1.0 0.73 0.50",
      overbright_range: "0.2",
    })
  );
}

const mapText = `${entities
  .map((entity, index) => `// entity ${index}\n${entity}`)
  .join("\n")}\n`;
fs.writeFileSync(path.join(mapDir, `${mapName}.map`), mapText);

const scriptText = `main:

setcvar "g_obj_alliedtext1" "Codex Inferno"
setcvar "g_obj_alliedtext2" "Recognition-first reconstruction - revision 3"
setcvar "g_obj_alliedtext3" ""
setcvar "g_obj_axistext1" ""
setcvar "g_obj_axistext2" ""
setcvar "g_obj_axistext3" ""

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/${mapName}.scr
level waittill spawn

end
`;
fs.writeFileSync(path.join(mapDir, `${mapName}.scr`), scriptText);
fs.writeFileSync(
  path.join(mapDir, `${mapName}_precache.scr`),
  [
    "exec global/DMprecache.scr",
    "cache models/items/dm_50_healthbox.tik",
    "cache models/fx/bazookaexplosion_dm.tik",
    "",
  ].join("\n")
);

const calloutAnchors = [
  { name: "T Spawn", x: -1580, y: 410 },
  { name: "Alt Mid", x: -700, y: 300 },
  { name: "Second Mid", x: 120, y: 350 },
  { name: "Apartments", x: 1080, y: -240 },
  { name: "Mid", x: 560, y: 760 },
  { name: "A Site", x: 1976, y: 434 },
  { name: "Arch / Library", x: 1050, y: 1740 },
  { name: "CT Spawn", x: 2350, y: 2100 },
  { name: "Banana", x: 130, y: 1840 },
  { name: "B Site", x: 352, y: 2768 },
];

const report = {
  map: mapName,
  revision: 3,
  construction: "callout-zoned-complete-village-massing-over-measured-routes",
  referencePolicy:
    "source VMF used as measurement/reference drawing; no Source brushes or assets imported",
  blueprint: {
    file: path.basename(blueprintPath),
    sha256: crypto.createHash("sha256").update(blueprintBytes).digest("hex"),
    reconstructedSourceSolids: blueprint.source.reconstructedSolids,
    failedSourceSolids: blueprint.source.failedSolids,
    measuredWalkCells: measuredCells.length,
    measuredRouteEdges: measuredEdges.size,
    unmatchedSourceSpawns: blueprint.walkGrid.unmatchedSpawns.length,
  },
  bounds: coordinateBounds,
  privateReferenceEvidence: {
    officialOverview: {
      posX: -2087,
      posY: 3870,
      scale: 4.9,
      purpose: "macro-layout comparison only; radar pixels are not distributed",
    },
    verifiedLandmarkDimensions: {
      bFountain: {
        origin: [352, 2768],
        basinRadius: 156,
        basinHeight: 29,
        centerRadius: 43,
        sourceCenterHeight: 133,
        authoredCenterHeight: 136,
      },
      ctWell: {
        origin: [1952, 2562],
        baseRadius: 59,
        baseHeight: 40,
        woodEnvelope: [104, 147, 141],
      },
      largeArchEnvelope: [24, 160, 81],
      coffinEnvelope: [19, 43, 100],
    },
    verifiedDynamicDoors: 1,
  },
  geometry: {
    floorRectangles: floorRectangles.length,
    massColumns: massColumns.size,
    buildingMassRectangles: buildingMassRectangles.length,
    gableRoofs: gableRoofCount,
    renderedOutdoorWallRuns: 0,
    renderedIndoorWallRuns: wallRuns.filter((candidate) => !candidate.outdoor).length,
    wallSegmentsBeforeMerge: rawWallSegments.size,
    wallRuns: wallRuns.length,
    ceilingRectangles: ceilingRectangles.length,
    siteSurfaceBrushes: siteSurfaceCount,
    worldBrushes: worldBrushes.length,
    authoredBrushes: authoredBrushes.length,
    totalWorldspawnBrushes: worldBrushes.length + authoredBrushes.length,
    facadeWindows: facadeWindowCount,
    roofMasses: roofMassCount,
    measuredArches: measuredArchOrigins.length,
  },
  spawns: {
    axis: axisSpawns.length,
    allied: alliedSpawns.length,
    neutral: neutralSpawns.length,
  },
  pointLights: interiorLights.length,
  calloutAnchors,
  sourceSolidsImported: 0,
  sourcePropsImported: 0,
  sourceDisplacementsImported: 0,
  sourceTexturesIncluded: 0,
  sourceModelsIncluded: 0,
};
fs.writeFileSync(
  path.join(outputRoot, `${mapName}-generation-report.json`),
  `${JSON.stringify(report, null, 2)}\n`
);

const svg = [
  `<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="1120" viewBox="${coordinateBounds.minX} ${-coordinateBounds.maxY} ${coordinateBounds.maxX - coordinateBounds.minX} ${coordinateBounds.maxY - coordinateBounds.minY}">`,
  `<rect x="${coordinateBounds.minX}" y="${-coordinateBounds.maxY}" width="${coordinateBounds.maxX - coordinateBounds.minX}" height="${coordinateBounds.maxY - coordinateBounds.minY}" fill="#17191b"/>`,
  ...buildingMassRectangles.map((rectangle) => {
    const [zoneName, topText, texture] = rectangle.groupKey.split("|");
    const colors = {
      [T.plasterWhite]: "#d9d1bd",
      [T.plasterCream]: "#cdbb97",
      [T.plasterOchre]: "#b88655",
      [T.plasterRose]: "#a9695b",
    };
    return `<rect x="${rectangle.x0}" y="${-rectangle.y1}" width="${rectangle.x1 - rectangle.x0}" height="${rectangle.y1 - rectangle.y0}" fill="${colors[texture] || "#9c8267"}" stroke="#4b3b31" stroke-width="5"><title>${zoneName} roof ${topText}</title></rect>`;
  }),
  ...floorRectangles.map((rectangle) => {
    const [zText, texture] = rectangle.groupKey.split("|");
    const colors = {
      [T.cobble]: "#c49a6c",
      [T.stoneFloor]: "#d7c2a5",
      [T.wood]: "#9a6745",
      [T.grass]: "#71865a",
    };
    return `<rect x="${rectangle.x0}" y="${-rectangle.y1}" width="${rectangle.x1 - rectangle.x0}" height="${rectangle.y1 - rectangle.y0}" fill="${colors[texture] || "#b99a75"}" stroke="#5d5145" stroke-width="2"><title>floor z ${zText}</title></rect>`;
  }),
  `<circle cx="${fountainX}" cy="${-fountainY}" r="156" fill="#6e9aa3" stroke="#e5d8c3" stroke-width="18"/>`,
  ...calloutAnchors.map(
    (anchor) =>
      `<g><circle cx="${anchor.x}" cy="${-anchor.y}" r="30" fill="#b84335"/><text x="${anchor.x}" y="${-anchor.y - 45}" text-anchor="middle" font-family="sans-serif" font-size="54" font-weight="700" fill="#ffffff" stroke="#1a1a1a" stroke-width="3" paint-order="stroke">${anchor.name}</text></g>`
  ),
  `<text x="${coordinateBounds.minX + 80}" y="${-coordinateBounds.maxY + 110}" font-family="sans-serif" font-size="64" font-weight="700" fill="#ffffff">Codex Inferno revision 3 - complete village massing</text>`,
  "</svg>",
];
fs.writeFileSync(path.join(outputRoot, "layout-plan.svg"), `${svg.join("\n")}\n`);

console.log(JSON.stringify(report, null, 2));
