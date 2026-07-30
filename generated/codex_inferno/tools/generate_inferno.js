const fs = require("fs");
const path = require("path");

const mapName = process.argv[2] || "codex_inferno";
const outputRoot = path.resolve(
  process.argv[3] || path.join(__dirname, "..")
);
const mainDir = path.join(outputRoot, "main");
const mapDir = path.join(mainDir, "maps", "dm");

if (!/^[A-Za-z0-9_]+$/.test(mapName)) {
  throw new Error("Map name may contain only letters, numbers, and underscores");
}

fs.mkdirSync(mapDir, { recursive: true });

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
  if (texture === T.roof || texture === T.brick || texture === T.cobble) {
    return [0.5, 0.5];
  }
  if (texture === T.window || texture === T.shutter) {
    return [0.25, 0.25];
  }
  return [0.5, 0.5];
}

function face(points, texture, shiftX = 0, shiftY = 0, rotation = 0) {
  const [scaleX, scaleY] = textureScale(texture);
  const pointText = points
    .map((point) => `( ${point.map(fmt).join(" ")} )`)
    .join(" ");
  return `${pointText} ${texture} ${shiftX} ${shiftY} ${rotation} ${scaleX} ${scaleY} 0 0 0`;
}

function boxBrush(min, max, texture) {
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  if (!(minX < maxX && minY < maxY && minZ < maxZ)) {
    throw new Error(`Invalid box ${JSON.stringify({ min, max, texture })}`);
  }
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], texture),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], texture),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], texture),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], texture),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], texture),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], texture),
    "}",
  ].join("\n");
}

function subtract(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function convexBrush(facePolygons, centroid, texture) {
  const lines = ["{"];
  for (const polygon of facePolygons) {
    if (polygon.length < 3) throw new Error("Convex face has fewer than 3 points");
    let [a, b, c] = polygon;
    const normal = cross(subtract(b, a), subtract(c, a));
    if (Math.abs(normal[0]) + Math.abs(normal[1]) + Math.abs(normal[2]) < 0.001) {
      throw new Error(`Degenerate convex face ${JSON.stringify(polygon)}`);
    }
    if (dot(normal, subtract(centroid, a)) < 0) {
      [b, c] = [c, b];
    }
    lines.push(face([a, b, c], texture));
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
  const faces = [bottom, [...top].reverse()];
  for (let index = 0; index < points.length; index++) {
    const next = (index + 1) % points.length;
    faces.push([bottom[index], top[index], top[next], bottom[next]]);
  }
  return convexBrush(faces, centroid, texture);
}

function orientedBox(cx, cy, length, width, minZ, maxZ, yaw, texture) {
  const radians = (yaw * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const points = [
    [-length / 2, -width / 2],
    [length / 2, -width / 2],
    [length / 2, width / 2],
    [-length / 2, width / 2],
  ].map(([x, y]) => [
    cx + x * cos - y * sin,
    cy + x * sin + y * cos,
  ]);
  return prismBrush(points, minZ, maxZ, texture);
}

function gableRoof(rect, baseZ, rise, texture) {
  const { x0, y0, x1, y1 } = rect;
  const width = x1 - x0;
  const depth = y1 - y0;
  let vertices;
  let faces;
  let centroid;
  if (width >= depth) {
    const midY = (y0 + y1) / 2;
    const a = [x0, y0, baseZ];
    const b = [x0, y1, baseZ];
    const c = [x0, midY, baseZ + rise];
    const d = [x1, y0, baseZ];
    const e = [x1, y1, baseZ];
    const f = [x1, midY, baseZ + rise];
    vertices = [a, b, c, d, e, f];
    faces = [
      [a, c, b],
      [d, e, f],
      [a, b, e, d],
      [a, d, f, c],
      [b, c, f, e],
    ];
  } else {
    const midX = (x0 + x1) / 2;
    const a = [x0, y0, baseZ];
    const b = [x1, y0, baseZ];
    const c = [midX, y0, baseZ + rise];
    const d = [x0, y1, baseZ];
    const e = [x1, y1, baseZ];
    const f = [midX, y1, baseZ + rise];
    vertices = [a, b, c, d, e, f];
    faces = [
      [a, b, c],
      [d, f, e],
      [a, d, e, b],
      [a, c, f, d],
      [b, e, f, c],
    ];
  }
  centroid = [
    vertices.reduce((sum, point) => sum + point[0], 0) / vertices.length,
    vertices.reduce((sum, point) => sum + point[1], 0) / vertices.length,
    baseZ + rise / 3,
  ];
  return convexBrush(faces, centroid, texture);
}

function pointEntity(classname, properties = {}) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) {
    lines.push(`"${key}" "${value}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function brushEntity(classname, brushes, properties = {}) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) {
    lines.push(`"${key}" "${value}"`);
  }
  for (let index = 0; index < brushes.length; index++) {
    lines.push(`// ${classname} brush ${index}`, brushes[index]);
  }
  lines.push("}");
  return lines.join("\n");
}

function yawToward(from, to) {
  let degrees =
    (Math.atan2(to[1] - from[1], to[0] - from[0]) * 180) / Math.PI;
  if (degrees < 0) degrees += 360;
  return Math.round(degrees);
}

const bounds = {
  minX: -1792,
  maxX: 1792,
  minY: -2048,
  maxY: 2048,
  floorZ: 0,
  skyZ: 704,
};
const cellSize = 128;

const routeRects = [
  { name: "T Spawn", x0: -512, y0: -1792, x1: 512, y1: -1408 },
  { name: "Lower Mid", x0: -256, y0: -1536, x1: 256, y1: -512 },
  { name: "Mid", x0: -256, y0: -640, x1: 256, y1: 640 },
  { name: "Top Mid", x0: -384, y0: 512, x1: 384, y1: 768 },
  { name: "Short", x0: -1024, y0: 512, x1: -256, y1: 896 },
  { name: "A Site", x0: -1536, y0: 768, x1: -768, y1: 1536 },
  { name: "A Porch", x0: -1152, y0: 640, x1: -384, y1: 1024 },
  { name: "A Pit", x0: -1536, y0: 512, x1: -1152, y1: 1024 },
  { name: "Library", x0: -768, y0: 1024, x1: 640, y1: 1280 },
  { name: "Arch", x0: 256, y0: 512, x1: 768, y1: 1024 },
  { name: "CT Spawn", x0: 512, y0: 768, x1: 1024, y1: 1280 },
  { name: "Ruins", x0: 896, y0: 1024, x1: 1408, y1: 1408 },
  { name: "B Site", x0: 1024, y0: 1280, x1: 1664, y1: 1792 },
  { name: "Banana Start", x0: 384, y0: -1664, x1: 1024, y1: -1408 },
  { name: "Banana Bend", x0: 768, y0: -1536, x1: 1280, y1: -1024 },
  { name: "Banana", x0: 896, y0: -1152, x1: 1280, y1: 1408 },
  { name: "Alt Mid Start", x0: -1024, y0: -1664, x1: -384, y1: -1280 },
  { name: "Alt Mid", x0: -1152, y0: -1408, x1: -768, y1: 256 },
  { name: "Second Mid", x0: -896, y0: -896, x1: -256, y1: -640 },
  { name: "Apartments", x0: -1152, y0: -384, x1: -768, y1: 896 },
];

function isOpenPoint(x, y) {
  return routeRects.some(
    (rect) => x >= rect.x0 && x < rect.x1 && y >= rect.y0 && y < rect.y1
  );
}

const columns = (bounds.maxX - bounds.minX) / cellSize;
const rows = (bounds.maxY - bounds.minY) / cellSize;
const openGrid = Array.from({ length: rows }, (_, row) =>
  Array.from({ length: columns }, (_, column) => {
    const x = bounds.minX + column * cellSize + cellSize / 2;
    const y = bounds.minY + row * cellSize + cellSize / 2;
    return isOpenPoint(x, y);
  })
);

function gridCellForPoint(x, y) {
  return [
    Math.floor((x - bounds.minX) / cellSize),
    Math.floor((y - bounds.minY) / cellSize),
  ];
}

function validateOpenConnectivity() {
  const [startX, startY] = gridCellForPoint(0, -1600);
  const queue = [[startX, startY]];
  const visited = new Set();
  while (queue.length) {
    const [x, y] = queue.shift();
    const key = `${x},${y}`;
    if (
      visited.has(key) ||
      x < 0 ||
      x >= columns ||
      y < 0 ||
      y >= rows ||
      !openGrid[y][x]
    ) {
      continue;
    }
    visited.add(key);
    queue.push([x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]);
  }
  const openCells = openGrid.flat().filter(Boolean).length;
  if (visited.size !== openCells) {
    throw new Error(
      `Authored route grid is disconnected: reached ${visited.size}/${openCells} cells`
    );
  }
  for (const route of routeRects) {
    const [x, y] = gridCellForPoint(
      (route.x0 + route.x1) / 2,
      (route.y0 + route.y1) / 2
    );
    if (!visited.has(`${x},${y}`)) {
      throw new Error(`Route ${route.name} is not connected to T Spawn`);
    }
  }
  return openCells;
}

const openCellCount = validateOpenConnectivity();

function mergeBlockedCells() {
  const used = Array.from({ length: rows }, () => Array(columns).fill(false));
  const rectangles = [];
  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      if (openGrid[row][column] || used[row][column]) continue;
      let width = 0;
      while (
        column + width < columns &&
        !openGrid[row][column + width] &&
        !used[row][column + width]
      ) {
        width++;
      }
      let height = 1;
      while (row + height < rows) {
        let canExtend = true;
        for (let x = column; x < column + width; x++) {
          if (openGrid[row + height][x] || used[row + height][x]) {
            canExtend = false;
            break;
          }
        }
        if (!canExtend) break;
        height++;
      }
      for (let y = row; y < row + height; y++) {
        for (let x = column; x < column + width; x++) {
          used[y][x] = true;
        }
      }
      rectangles.push({
        gridX: column,
        gridY: row,
        x0: bounds.minX + column * cellSize,
        y0: bounds.minY + row * cellSize,
        x1: bounds.minX + (column + width) * cellSize,
        y1: bounds.minY + (row + height) * cellSize,
      });
    }
  }
  return rectangles;
}

const buildingRects = mergeBlockedCells();
const worldBrushes = [];
const detailBrushes = [];
const addWorldBox = (min, max, texture) =>
  worldBrushes.push(boxBrush(min, max, texture));
const addDetailBox = (min, max, texture) =>
  detailBrushes.push(boxBrush(min, max, texture));

// Sealed AA sky shell and continuous base floor.
addWorldBox(
  [bounds.minX, bounds.minY, -64],
  [bounds.maxX, bounds.maxY, 0],
  T.cobble
);
addWorldBox(
  [bounds.minX, bounds.minY, bounds.skyZ],
  [bounds.maxX, bounds.maxY, bounds.skyZ + 64],
  T.sky
);
addWorldBox(
  [bounds.minX - 64, bounds.minY - 64, -64],
  [bounds.minX, bounds.maxY + 64, bounds.skyZ + 64],
  T.sky
);
addWorldBox(
  [bounds.maxX, bounds.minY - 64, -64],
  [bounds.maxX + 64, bounds.maxY + 64, bounds.skyZ + 64],
  T.sky
);
addWorldBox(
  [bounds.minX, bounds.minY - 64, -64],
  [bounds.maxX, bounds.minY, bounds.skyZ + 64],
  T.sky
);
addWorldBox(
  [bounds.minX, bounds.maxY, -64],
  [bounds.maxX, bounds.maxY + 64, bounds.skyZ + 64],
  T.sky
);

const facadePalette = [
  T.plasterCream,
  T.plasterOchre,
  T.plasterRose,
  T.plasterWhite,
];
let facadeWindowCount = 0;
let gableRoofCount = 0;
let flatRoofCount = 0;

function stableHash(x, y) {
  let value = ((x + 31) * 73856093) ^ ((y + 17) * 19349663);
  value ^= value >>> 13;
  return Math.abs(value);
}

function exposedAlongX(xOutside, y0, y1) {
  for (let y = y0 + 64; y < y1; y += 128) {
    if (isOpenPoint(xOutside, y)) return true;
  }
  return false;
}

function exposedAlongY(yOutside, x0, x1) {
  for (let x = x0 + 64; x < x1; x += 128) {
    if (isOpenPoint(x, yOutside)) return true;
  }
  return false;
}

function addWindowX(x, centerY, outward, height) {
  if (height < 240) return;
  const x0 = outward < 0 ? x - 5 : x;
  const x1 = outward < 0 ? x : x + 5;
  addDetailBox([x0, centerY - 34, 104], [x1, centerY + 34, 186], T.window);
  const shutterX0 = outward < 0 ? x - 7 : x;
  const shutterX1 = outward < 0 ? x : x + 7;
  addDetailBox(
    [shutterX0, centerY - 58, 104],
    [shutterX1, centerY - 38, 186],
    T.shutter
  );
  addDetailBox(
    [shutterX0, centerY + 38, 104],
    [shutterX1, centerY + 58, 186],
    T.shutter
  );
  addDetailBox(
    [x0 - (outward < 0 ? 2 : 0), centerY - 42, 96],
    [x1 + (outward > 0 ? 2 : 0), centerY + 42, 104],
    T.stoneTrim
  );
  facadeWindowCount++;
}

function addWindowY(centerX, y, outward, height) {
  if (height < 240) return;
  const y0 = outward < 0 ? y - 5 : y;
  const y1 = outward < 0 ? y : y + 5;
  addDetailBox([centerX - 34, y0, 104], [centerX + 34, y1, 186], T.window);
  const shutterY0 = outward < 0 ? y - 7 : y;
  const shutterY1 = outward < 0 ? y : y + 7;
  addDetailBox(
    [centerX - 58, shutterY0, 104],
    [centerX - 38, shutterY1, 186],
    T.shutter
  );
  addDetailBox(
    [centerX + 38, shutterY0, 104],
    [centerX + 58, shutterY1, 186],
    T.shutter
  );
  addDetailBox(
    [centerX - 42, y0 - (outward < 0 ? 2 : 0), 96],
    [centerX + 42, y1 + (outward > 0 ? 2 : 0), 104],
    T.stoneTrim
  );
  facadeWindowCount++;
}

for (const rect of buildingRects) {
  const hash = stableHash(rect.gridX, rect.gridY);
  const height = 288 + (hash % 3) * 64;
  const facade = facadePalette[hash % facadePalette.length];
  rect.height = height;
  rect.facade = facade;
  addWorldBox([rect.x0, rect.y0, 0], [rect.x1, rect.y1, height], facade);

  const width = rect.x1 - rect.x0;
  const depth = rect.y1 - rect.y0;
  if (
    width >= 256 &&
    depth >= 256 &&
    width <= 768 &&
    depth <= 768 &&
    hash % 3 !== 0
  ) {
    detailBrushes.push(gableRoof(rect, height, 72, T.roof));
    gableRoofCount++;
  } else {
    addDetailBox(
      [rect.x0 - 8, rect.y0 - 8, height],
      [rect.x1 + 8, rect.y1 + 8, height + 24],
      T.roof
    );
    flatRoofCount++;
  }

  const westOpen = exposedAlongX(rect.x0 - 4, rect.y0, rect.y1);
  const eastOpen = exposedAlongX(rect.x1 + 4, rect.y0, rect.y1);
  const southOpen = exposedAlongY(rect.y0 - 4, rect.x0, rect.x1);
  const northOpen = exposedAlongY(rect.y1 + 4, rect.x0, rect.x1);

  if (westOpen) {
    addDetailBox(
      [rect.x0 - 6, rect.y0, 0],
      [rect.x0, rect.y1, 40],
      T.stoneTrim
    );
    for (let y = rect.y0 + 128; y < rect.y1 - 64; y += 320) {
      if (isOpenPoint(rect.x0 - 8, y)) addWindowX(rect.x0, y, -1, height);
    }
  }
  if (eastOpen) {
    addDetailBox(
      [rect.x1, rect.y0, 0],
      [rect.x1 + 6, rect.y1, 40],
      T.stoneTrim
    );
    for (let y = rect.y0 + 128; y < rect.y1 - 64; y += 320) {
      if (isOpenPoint(rect.x1 + 8, y)) addWindowX(rect.x1, y, 1, height);
    }
  }
  if (southOpen) {
    addDetailBox(
      [rect.x0, rect.y0 - 6, 0],
      [rect.x1, rect.y0, 40],
      T.stoneTrim
    );
    for (let x = rect.x0 + 128; x < rect.x1 - 64; x += 320) {
      if (isOpenPoint(x, rect.y0 - 8)) addWindowY(x, rect.y0, -1, height);
    }
  }
  if (northOpen) {
    addDetailBox(
      [rect.x0, rect.y1, 0],
      [rect.x1, rect.y1 + 6, 40],
      T.stoneTrim
    );
    for (let x = rect.x0 + 128; x < rect.x1 - 64; x += 320) {
      if (isOpenPoint(x, rect.y1 + 8)) addWindowY(x, rect.y1, 1, height);
    }
  }
}

function addSiteFloor(x0, y0, x1, y1) {
  addDetailBox([x0, y0, 0], [x1, y1, 8], T.stoneFloor);
}

function addCrate(cx, cy, size = 96, height = size) {
  addDetailBox(
    [cx - size / 2, cy - size / 2, 8],
    [cx + size / 2, cy + size / 2, 8 + height],
    T.wood
  );
  addDetailBox(
    [cx - size / 2 - 3, cy - size / 2 - 3, 8 + height - 12],
    [cx + size / 2 + 3, cy + size / 2 + 3, 8 + height],
    T.woodDark
  );
}

function addArchAcrossX(centerX, centerY, openingWidth, height = 216) {
  const thickness = 32;
  const pillar = 40;
  addDetailBox(
    [centerX - thickness, centerY - openingWidth / 2 - pillar, 0],
    [centerX + thickness, centerY - openingWidth / 2, height],
    T.brick
  );
  addDetailBox(
    [centerX - thickness, centerY + openingWidth / 2, 0],
    [centerX + thickness, centerY + openingWidth / 2 + pillar, height],
    T.brick
  );
  addDetailBox(
    [centerX - thickness, centerY - openingWidth / 2 - pillar, height],
    [centerX + thickness, centerY + openingWidth / 2 + pillar, height + 48],
    T.stoneTrim
  );
}

function addArchAcrossY(centerX, centerY, openingWidth, height = 216) {
  const thickness = 32;
  const pillar = 40;
  addDetailBox(
    [centerX - openingWidth / 2 - pillar, centerY - thickness, 0],
    [centerX - openingWidth / 2, centerY + thickness, height],
    T.brick
  );
  addDetailBox(
    [centerX + openingWidth / 2, centerY - thickness, 0],
    [centerX + openingWidth / 2 + pillar, centerY + thickness, height],
    T.brick
  );
  addDetailBox(
    [centerX - openingWidth / 2 - pillar, centerY - thickness, height],
    [centerX + openingWidth / 2 + pillar, centerY + thickness, height + 48],
    T.stoneTrim
  );
}

function addStairsNorth(x0, x1, y0, count, depth, rise, descending = false) {
  for (let index = 0; index < count; index++) {
    const stepHeight = descending
      ? (count - index) * rise
      : (index + 1) * rise;
    addDetailBox(
      [x0, y0 + index * depth, 0],
      [x1, y0 + (index + 1) * depth, stepHeight],
      T.stoneFloor
    );
  }
}

// Site and courtyard material breaks.
addSiteFloor(-1504, 800, -800, 1504);
addSiteFloor(1040, 1312, 1632, 1760);
addSiteFloor(544, 800, 992, 1248);
addSiteFloor(-480, -1760, 480, -1424);

// Apartments: authored upper route, complete floor/ceiling, and two stair runs.
addStairsNorth(-1088, -832, -384, 8, 40, 12, false);
addDetailBox([-1152, -64, 0], [-768, 640, 96], T.plasterCream);
addDetailBox([-1120, -64, 96], [-800, 640, 104], T.wood);
addDetailBox([-1152, -384, 248], [-768, 640, 272], T.ceiling);
addStairsNorth(-1088, -832, 640, 8, 32, 12, true);
for (const y of [-160, 160, 480]) {
  addDetailBox([-1152, y - 8, 216], [-768, y + 8, 232], T.woodDark);
}

// Library and ruins receive real ceilings instead of Source-model gaps.
addDetailBox([-736, 1056, 224], [608, 1248, 248], T.ceiling);
addDetailBox([928, 1056, 224], [1376, 1376, 248], T.ceiling);
for (const x of [-576, -256, 64, 384]) {
  addDetailBox([x - 8, 1056, 192], [x + 8, 1248, 208], T.woodDark);
}

// Landmark arches define route transitions.
addArchAcrossX(448, 704, 248);
addArchAcrossY(-896, 448, 248);
addArchAcrossY(1088, 1152, 264);
addArchAcrossX(768, 1120, 248);

// A-site cover and porch/pit cues.
addCrate(-1248, 1216, 104, 104);
addCrate(-1128, 1280, 88, 88);
addCrate(-1392, 992, 80, 128);
addDetailBox([-1536, 704, 0], [-1184, 736, 88], T.stoneTrim);
addDetailBox([-1520, 736, 88], [-1184, 748, 108], T.metal);
addStairsNorth(-1456, -1216, 512, 6, 32, 12, false);

// B-site fountain and traditional "coffins" cover.
const fountainPoints = [];
for (let index = 0; index < 8; index++) {
  const angle = (index * Math.PI * 2) / 8;
  fountainPoints.push([
    1344 + Math.cos(angle) * 112,
    1568 + Math.sin(angle) * 112,
  ]);
}
detailBrushes.push(prismBrush(fountainPoints, 8, 34, T.stoneTrim));
const fountainCenter = [];
for (let index = 0; index < 10; index++) {
  const angle = (index * Math.PI * 2) / 10;
  fountainCenter.push([
    1344 + Math.cos(angle) * 34,
    1568 + Math.sin(angle) * 34,
  ]);
}
detailBrushes.push(prismBrush(fountainCenter, 34, 112, T.stoneTrim));
addDetailBox([1512, 1376, 8], [1616, 1456, 112], T.stoneTrim);
addDetailBox([1512, 1472, 8], [1616, 1552, 112], T.stoneTrim);

// Banana cover breaks the long sightline without blocking navigation.
detailBrushes.push(orientedBox(1088, -640, 160, 48, 0, 96, 12, T.stoneTrim));
detailBrushes.push(orientedBox(1088, 64, 144, 48, 0, 88, -10, T.brick));
addCrate(1000, 656, 80, 80);
addCrate(1184, 960, 72, 104);

// Mid and T-spawn cover.
addDetailBox([-160, -128, 0], [160, -88, 80], T.stoneTrim);
addCrate(-352, -1568, 88, 88);
addCrate(352, -1512, 96, 96);
addDetailBox([-640, -1520, 0], [-608, -1328, 72], T.stoneTrim);

// Bell tower above the solid village block near B/CT.
addDetailBox([1472, 1056, 320], [1664, 1280, 544], T.plasterWhite);
addDetailBox([1456, 1040, 304], [1680, 1296, 328], T.stoneTrim);
addDetailBox([1512, 1050, 408], [1568, 1056, 488], T.window);
addDetailBox([1568, 1278, 408], [1624, 1284, 488], T.window);
detailBrushes.push(
  gableRoof({ x0: 1456, y0: 1040, x1: 1680, y1: 1296 }, 544, 96, T.roof)
);

// A few planted beds establish color without Source foliage/model guesses.
addDetailBox([-1456, 1408, 8], [-1328, 1488, 22], T.grass);
addDetailBox([1072, 1648, 8], [1184, 1736, 22], T.grass);
addDetailBox([-1088, -1328, 0], [-1048, -1120, 28], T.grass);

const entities = [];
const worldspawn = [
  "{",
  `"classname" "worldspawn"`,
  `"message" "Codex Inferno"`,
  `"ambientlight" "8 9 11"`,
  `"suncolor" "142 125 100"`,
  `"sundirection" "330 215 0"`,
  `"sundiffusecolor" "60 70 88"`,
  `"sundiffuse" "1.1"`,
  `"_color" "1.0 0.95 0.88"`,
  `"farplane" "6200"`,
  `"farplane_color" "0.44 0.50 0.56"`,
  ...worldBrushes.map((brush, index) => `// world brush ${index}\n${brush}`),
  ...detailBrushes.map(
    (brush, index) => `// authored detail brush ${index}\n${brush}`
  ),
  "}",
].join("\n");
entities.push(worldspawn);

const axisSpawns = [
  [-384, -1696], [-192, -1696], [0, -1696], [192, -1696],
  [384, -1696], [-448, -1568], [-192, -1568], [0, -1568],
  [192, -1568], [384, -1568], [512, -1504], [640, -1504],
  [-512, -1504], [-704, -1504], [128, -1440], [-128, -1440],
];
const alliedSpawns = [
  [592, 864], [720, 864], [848, 864], [944, 928],
  [592, 992], [720, 992], [848, 992], [944, 1056],
  [592, 1120], [720, 1120], [848, 1120], [944, 1184],
  [1040, 1184], [1120, 1248], [480, 1184], [448, 1088],
];
const neutralSpawns = [
  [0, -1600, 40], [704, -1472, 40], [-704, -1472, 40],
  [0, -1088, 40], [-960, -1152, 40], [1056, -1088, 40],
  [-64, -704, 40], [-576, -768, 40], [1088, -512, 40],
  [64, -256, 40], [-960, -320, 40], [1088, 128, 40],
  [64, 384, 40], [-960, 160, 136], [1088, 640, 40],
  [-512, 672, 40], [512, 672, 40], [-960, 496, 136],
  [-1344, 672, 112], [-1248, 1120, 48], [-944, 1408, 48],
  [-256, 1152, 40], [768, 1088, 48], [1184, 1472, 48],
];

function addSpawn(classname, point, target) {
  entities.push(
    pointEntity(classname, {
      origin: `${point[0]} ${point[1]} ${point[2] ?? 40}`,
      angle: String(yawToward(point, target)),
    })
  );
}

for (const point of axisSpawns) addSpawn("info_player_axis", point, [0, -800]);
for (const point of alliedSpawns) addSpawn("info_player_allied", point, [256, 512]);
for (const point of neutralSpawns) {
  addSpawn("info_player_deathmatch", point, [128, 256]);
}
addSpawn("info_player_start", [0, -1600, 40], [0, -800]);
entities.push(
  pointEntity("info_player_intermission", {
    origin: "0 256 560",
    angle: "90",
  })
);

const interiorLights = [
  [-960, -160, 208], [-960, 160, 208], [-960, 480, 208],
  [-576, 1152, 184], [-256, 1152, 184], [64, 1152, 184],
  [384, 1152, 184], [1088, 1168, 184],
];
for (const [x, y, z] of interiorLights) {
  entities.push(
    pointEntity("light", {
      origin: `${x} ${y} ${z}`,
      light: "115",
      _color: "1.0 0.72 0.48",
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
setcvar "g_obj_alliedtext2" "Authored Mediterranean village DM"
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

const report = {
  map: mapName,
  revision: 1,
  construction: "authored-from-scratch",
  referencePolicy: "route-and-scale-inspiration-only",
  bounds,
  grid: {
    cellSize,
    columns,
    rows,
    openCells: openCellCount,
    blockedCells: rows * columns - openCellCount,
  },
  routeNames: routeRects.map((route) => route.name),
  worldBrushes: worldBrushes.length,
  authoredDetailBrushes: detailBrushes.length,
  compiledWorldBrushes: worldBrushes.length + detailBrushes.length,
  buildingMasses: buildingRects.length,
  facadeWindows: facadeWindowCount,
  gableRoofs: gableRoofCount + 1,
  flatRoofs: flatRoofCount,
  spawns: {
    axis: axisSpawns.length,
    allied: alliedSpawns.length,
    neutral: neutralSpawns.length,
  },
  pointLights: interiorLights.length,
  sourceSolidsImported: 0,
  sourcePropsImported: 0,
  sourceDisplacementsImported: 0,
};
fs.writeFileSync(
  path.join(outputRoot, `${mapName}-generation-report.json`),
  `${JSON.stringify(report, null, 2)}\n`
);

function svgY(y) {
  return bounds.maxY - y;
}

const svgScale = 0.2;
const svgWidth = (bounds.maxX - bounds.minX) * svgScale;
const svgHeight = (bounds.maxY - bounds.minY) * svgScale;
const svg = [
  `<svg xmlns="http://www.w3.org/2000/svg" width="${svgWidth}" height="${svgHeight}" viewBox="${bounds.minX} ${-bounds.maxY} ${bounds.maxX - bounds.minX} ${bounds.maxY - bounds.minY}">`,
  `<rect x="${bounds.minX}" y="${-bounds.maxY}" width="${bounds.maxX - bounds.minX}" height="${bounds.maxY - bounds.minY}" fill="#342f2a"/>`,
  ...buildingRects.map(
    (rect) =>
      `<rect x="${rect.x0}" y="${-rect.y1}" width="${rect.x1 - rect.x0}" height="${rect.y1 - rect.y0}" fill="#a97956" stroke="#5f4434" stroke-width="8"/>`
  ),
  ...routeRects.map(
    (rect) =>
      `<text x="${(rect.x0 + rect.x1) / 2}" y="${-((rect.y0 + rect.y1) / 2)}" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="48" fill="#f5ead8">${rect.name}</text>`
  ),
  `<circle cx="0" cy="${-(-1600)}" r="42" fill="#d07b4a"/>`,
  `<circle cx="768" cy="${-1024}" r="42" fill="#6b8fb3"/>`,
  "</svg>",
].join("\n");
fs.writeFileSync(path.join(outputRoot, "layout-plan.svg"), `${svg}\n`);

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
