"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const mapName = process.argv[2] || "codex_reactor";
const outputRoot = path.resolve(process.argv[3] || path.join(__dirname, ".."));
if (!/^[A-Za-z0-9_]+$/.test(mapName)) {
  throw new Error("Map name may contain only letters, numbers, and underscores");
}

const mainRoot = path.join(outputRoot, "main");
const mapRoot = path.join(mainRoot, "maps", "dm");
fs.mkdirSync(mapRoot, { recursive: true });

const T = Object.freeze({
  caulk: "common/caulk",
  sky: "sky/mohday1",
  asphalt: "codex_nuke/asphalt",
  floor: "codex_nuke/concrete_floor",
  floorDark: "codex_nuke/concrete_dark",
  wall: "codex_nuke/painted_concrete",
  wallBlue: "codex_nuke/painted_concrete_blue",
  cladding: "codex_nuke/corrugated_gray",
  claddingBlue: "codex_nuke/corrugated_blue",
  trim: "codex_nuke/metal_trim",
  grate: "codex_nuke/metal_grating",
  ceiling: "codex_nuke/ceiling_tile",
  whiteMetal: "codex_nuke/clean_white_metal",
  yellow: "codex_nuke/safety_yellow",
  red: "codex_nuke/safety_red",
  equipmentBlue: "codex_nuke/equipment_blue",
  panel: "codex_nuke/control_panel",
  rubber: "codex_nuke/rubber",
});

const bundledTextures = Object.freeze([
  "asphalt.tga",
  "ceiling_tile.tga",
  "clean_white_metal.tga",
  "concrete_dark.tga",
  "concrete_floor.tga",
  "control_panel.tga",
  "corrugated_blue.tga",
  "corrugated_gray.tga",
  "equipment_blue.tga",
  "metal_grating.tga",
  "metal_trim.tga",
  "painted_concrete.tga",
  "painted_concrete_blue.tga",
  "rubber.tga",
  "safety_red.tga",
  "safety_yellow.tga",
]);

function fmt(value) {
  if (!Number.isFinite(value)) throw new Error(`Non-finite coordinate: ${value}`);
  const rounded = Math.round(value * 1000) / 1000;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(3);
}

function pointText(point) {
  return `( ${point.map(fmt).join(" ")} )`;
}

function face(points, texture, scale = 0.5) {
  return `${points.map(pointText).join(" ")} ${texture} 0 0 0 ${fmt(scale)} ${fmt(
    scale,
  )} 0 0 0`;
}

function assertBounds(min, max, label) {
  if (
    min.length !== 3 ||
    max.length !== 3 ||
    !min.every(Number.isFinite) ||
    !max.every(Number.isFinite) ||
    min.some((value, axis) => value >= max[axis])
  ) {
    throw new Error(`Invalid ${label} bounds: ${JSON.stringify({ min, max })}`);
  }
}

function boxBrush(min, max, texture, scale = 0.5) {
  assertBounds(min, max, "box");
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], texture, scale),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], texture, scale),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], texture, scale),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], texture, scale),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], texture, scale),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], texture, scale),
    "}",
  ].join("\n");
}

function cylinderBrush(center, minZ, maxZ, radius, texture, sides = 12, scale = 0.5) {
  if (
    center.length !== 2 ||
    !center.every(Number.isFinite) ||
    !Number.isFinite(minZ) ||
    !Number.isFinite(maxZ) ||
    minZ >= maxZ ||
    !Number.isFinite(radius) ||
    radius <= 0 ||
    !Number.isInteger(sides) ||
    sides < 6
  ) {
    throw new Error("Invalid cylinder parameters");
  }
  const [centerX, centerY] = center;
  const vertices = Array.from({ length: sides }, (_, index) => {
    const angle = (index / sides) * Math.PI * 2;
    return [centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius];
  });
  const lines = ["{"];
  for (let index = 0; index < sides; index += 1) {
    const current = vertices[index];
    const next = vertices[(index + 1) % sides];
    lines.push(
      face(
        [
          [next[0], next[1], minZ],
          [current[0], current[1], minZ],
          [current[0], current[1], maxZ],
        ],
        texture,
        scale,
      ),
    );
  }
  lines.push(
    face(
      [
        [centerX - 16, centerY + 16, minZ],
        [centerX, centerY, minZ],
        [centerX + 16, centerY + 16, minZ],
      ],
      texture,
      scale,
    ),
  );
  lines.push(
    face(
      [
        [centerX + 16, centerY + 16, maxZ],
        [centerX, centerY, maxZ],
        [centerX - 16, centerY + 16, maxZ],
      ],
      texture,
      scale,
    ),
  );
  lines.push("}");
  return lines.join("\n");
}

function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) {
    lines.push(`"${key}" "${value}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function yawToward(x, y, targetX, targetY) {
  let degrees = (Math.atan2(targetY - y, targetX - x) * 180) / Math.PI;
  if (degrees < 0) degrees += 360;
  return Math.round(degrees);
}

const brushes = [];
const collisionBoxes = [];
const collisionCylinders = [];
const brushesByRole = new Map();

function countRole(role) {
  brushesByRole.set(role, (brushesByRole.get(role) || 0) + 1);
}

function addBox(role, min, max, texture, options = {}) {
  const { scale = 0.5, collision = true } = options;
  brushes.push({ role, text: boxBrush(min, max, texture, scale) });
  if (collision) collisionBoxes.push({ role, min: [...min], max: [...max] });
  countRole(role);
}

function addCylinder(role, center, minZ, maxZ, radius, texture, sides = 12) {
  brushes.push({
    role,
    text: cylinderBrush(center, minZ, maxZ, radius, texture, sides),
  });
  collisionCylinders.push({ role, center: [...center], minZ, maxZ, radius });
  countRole(role);
}

// Structural shell: the south third is an open loading yard, while the north
// two thirds form a roofed reactor annex. The sky brush seals the whole level.
addBox("shell_floor", [-1536, -1280, -64], [1536, 1280, 0], T.floorDark, {
  scale: 1,
});
addBox("outer_wall", [-1536, -1280, 0], [-1472, 1280, 512], T.cladding);
addBox("outer_wall", [1472, -1280, 0], [1536, 1280, 512], T.cladding);
addBox("outer_wall", [-1472, -1280, 0], [1472, -1216, 512], T.cladding);
addBox("outer_wall", [-1472, 1216, 0], [1472, 1280, 512], T.cladding);
addBox("sky_ceiling", [-1472, -1216, 512], [1472, 1216, 576], T.sky, {
  scale: 1,
});

addBox("yard_floor", [-1472, -1216, 0], [1472, -288, 16], T.asphalt, {
  scale: 0.75,
});
addBox("interior_floor", [-1472, -256, 0], [1472, 1216, 16], T.floor, {
  scale: 0.75,
});

// Building front with three permanently open bot-safe entrances.
for (const [minX, maxX] of [
  [-1472, -1152],
  [-896, -160],
  [160, 896],
  [1152, 1472],
]) {
  addBox("front_wall", [minX, -288, 16], [maxX, -256, 384], T.wall);
}
for (const [minX, maxX, texture] of [
  [-1152, -896, T.wallBlue],
  [-160, 160, T.yellow],
  [896, 1152, T.wallBlue],
]) {
  addBox("entrance_lintel", [minX, -288, 256], [maxX, -256, 384], texture);
}

addBox("building_roof", [-1472, -256, 384], [1472, 1216, 416], T.cladding, {
  scale: 0.75,
});
addBox("interior_ceiling", [-1440, -224, 376], [1440, 1184, 384], T.ceiling, {
  scale: 0.75,
});

// The reactor hall has two large openings into each side room. The rear wall
// has two openings into the service crossover, avoiding a single choke point.
for (const wallX of [-624, 592]) {
  for (const [minY, maxY] of [
    [-256, -64],
    [192, 400],
    [656, 768],
  ]) {
    addBox("reactor_side_wall", [wallX, minY, 16], [wallX + 32, maxY, 384], T.wall);
  }
}
for (const [minX, maxX] of [
  [-624, -400],
  [-128, 128],
  [400, 624],
]) {
  addBox("reactor_rear_wall", [minX, 768, 16], [maxX, 800, 384], T.wall);
}

// Front facade articulation keeps the open yard visually tied to a modern
// industrial annex without creating additional collision chokepoints.
for (const x of [-1328, -1024, -528, 528, 1024, 1328]) {
  addBox("facade_pier", [x - 20, -304, 16], [x + 20, -288, 352], T.trim);
}
for (const [minX, maxX, texture] of [
  [-1440, -1184, T.claddingBlue],
  [-864, -192, T.cladding],
  [192, 864, T.cladding],
  [1184, 1440, T.claddingBlue],
]) {
  addBox("facade_panel", [minX, -300, 280], [maxX, -288, 352], texture, {
    collision: false,
  });
}

// Central reactor: stacked authored primitives block long sightlines and form
// a recognizable landmark without importing Source/Valve mesh data.
addCylinder("reactor_plinth", [0, 320], 16, 48, 160, T.rubber, 16);
addCylinder("reactor_body", [0, 320], 48, 248, 112, T.whiteMetal, 16);
addCylinder("reactor_band", [0, 320], 88, 116, 126, T.yellow, 16);
addCylinder("reactor_band", [0, 320], 176, 204, 126, T.red, 16);
addCylinder("reactor_cap", [0, 320], 248, 288, 96, T.equipmentBlue, 16);

for (const [min, max] of [
  [[-336, 272, 16], [-240, 368, 112]],
  [[240, 272, 16], [336, 368, 112]],
  [[-48, 24, 16], [48, 120, 112]],
  [[-48, 520, 16], [48, 616, 112]],
]) {
  addBox("reactor_cover", min, max, T.panel);
}
for (const [x, y] of [
  [-480, 32],
  [480, 32],
  [-480, 640],
  [480, 640],
]) {
  addBox("reactor_column", [x - 28, y - 28, 16], [x + 28, y + 28, 376], T.trim);
}

// Side-room machinery and consoles break up firing lanes while preserving at
// least 224 units around every primary route.
for (const [min, max, texture] of [
  [[-1384, -96, 16], [-1240, 96, 120], T.equipmentBlue],
  [[-984, -40, 16], [-792, 120, 104], T.panel],
  [[-920, 464, 16], [-736, 608, 112], T.claddingBlue],
  [[-1376, 872, 16], [-1168, 1088, 128], T.cladding],
  [[1240, -96, 16], [1384, 96, 120], T.equipmentBlue],
  [[792, -40, 16], [984, 120, 104], T.panel],
  [[736, 464, 16], [920, 608, 112], T.claddingBlue],
  [[1168, 872, 16], [1376, 1088, 128], T.cladding],
  [[-224, 880, 16], [224, 1168, 144], T.panel],
]) {
  addBox("equipment", min, max, texture);
}

for (const [min, max] of [
  [[-1360, 200, 16], [-1304, 672, 88]],
  [[1304, 200, 16], [1360, 672, 88]],
  [[-1040, 704, 16], [-752, 760, 88]],
  [[752, 704, 16], [1040, 760, 88]],
]) {
  addBox("control_console", min, max, T.panel);
}

// Broad two-sided stair access and an upper U-loop. Falls are survivable and
// no rail collision is used, avoiding one-way bot pockets.
const stairSpecs = [];
for (const centerX of [-1136, 1136]) {
  for (let step = 0; step < 10; step += 1) {
    const minY = -160 + step * 32;
    const maxY = minY + 32;
    const maxZ = 32 + step * 16;
    addBox(
      "mezzanine_stair",
      [centerX - 112, minY, 16],
      [centerX + 112, maxY, maxZ],
      T.grate,
    );
  }
  stairSpecs.push({ centerX, width: 224, tread: 32, rise: 16, steps: 10 });
}

addBox("west_mezzanine", [-1408, 160, 160], [-672, 736, 176], T.grate);
addBox("east_mezzanine", [672, 160, 160], [1408, 736, 176], T.grate);
addBox("west_balcony", [-576, 400, 160], [-400, 736, 176], T.grate);
addBox("east_balcony", [400, 400, 160], [576, 736, 176], T.grate);
addBox("west_balcony_link", [-672, 432, 160], [-400, 624, 176], T.grate);
addBox("east_balcony_link", [400, 432, 160], [672, 624, 176], T.grate);
addBox("west_rear_link", [-864, 736, 160], [-672, 992, 176], T.grate);
addBox("east_rear_link", [672, 736, 160], [864, 992, 176], T.grate);
addBox("rear_catwalk", [-864, 832, 160], [864, 1024, 176], T.grate);

for (const [x, y] of [
  [-1360, 256],
  [-720, 672],
  [1360, 256],
  [720, 672],
  [-720, 928],
  [720, 928],
]) {
  addBox("catwalk_support", [x - 20, y - 20, 16], [x + 20, y + 20, 160], T.trim);
}

// Yard cover is staggered, not mirrored into one uninterrupted firing lane.
for (const [min, max, texture] of [
  [[-1120, -1088, 16], [-768, -896, 160], T.claddingBlue],
  [[-984, -824, 16], [-664, -656, 144], T.cladding],
  [[720, -1080, 16], [1064, -888, 160], T.claddingBlue],
  [[536, -816, 16], [856, -648, 144], T.cladding],
  [[-1456, -720, 16], [-1248, -520, 112], T.equipmentBlue],
  [[1192, -696, 16], [1408, -488, 112], T.equipmentBlue],
]) {
  addBox("yard_container", min, max, texture);
}
for (const [min, max, texture] of [
  [[-448, -768, 16], [-192, -704, 80], T.yellow],
  [[192, -768, 16], [448, -704, 80], T.yellow],
  [[-256, -1056, 16], [-192, -896, 88], T.whiteMetal],
  [[192, -1040, 16], [256, -880, 88], T.whiteMetal],
  [[-1280, -384, 16], [-1168, -320, 96], T.red],
  [[1168, -384, 16], [1280, -320, 96], T.red],
]) {
  addBox("yard_barrier", min, max, texture);
}

// Brush light fixtures correspond one-to-one with restrained point lights.
const lightDefinitions = [];
function addFixture(x, y, z, intensity, color, zone) {
  addBox("light_fixture", [x - 48, y - 12, z - 6], [x + 48, y + 12, z + 6], T.whiteMetal);
  // Retail Q3Map flood classifies the high fixture-adjacent points as leaked; 200 is clear, visible, and compiler-proven.
  lightDefinitions.push({ origin: [x, y, 200], intensity, color, zone });
}

for (const [x, y] of [
  [-384, 48],
  [384, 48],
  [-384, 592],
  [384, 592],
]) {
  addFixture(x, y, 344, 190, "0.82 0.90 1.0", "reactor_hall");
}
for (const x of [-1184, -832, 832, 1184]) {
  for (const y of [64, 576]) addFixture(x, y, 336, 165, "0.88 0.93 1.0", "side_room");
}
for (const x of [-896, -320, 320, 896]) {
  addFixture(x, 1056, 336, 145, "0.80 0.88 1.0", "rear_service");
}

// Dedicated underslung fixtures keep the broad lower service loops readable;
// the main ceiling lights sit above the solid mezzanine decks.
for (const [x, y] of [
  [-1200, 320],
  [-800, 640],
  [1200, 320],
  [800, 640],
]) {
  addBox("under_mezzanine_fixture", [x - 36, y - 10, 146], [x + 36, y + 10, 154], T.whiteMetal);
  lightDefinitions.push({
    origin: [x, y, 112],
    intensity: 130,
    color: "0.78 0.88 1.0",
    zone: "under_mezzanine",
  });
}
// Exterior wall lamps have matching purposeful warm lights; the yard itself
// is primarily lit by sun and diffuse sky.
for (const x of [-1024, 0, 1024]) {
  addBox("entry_fixture", [x - 40, -312, 224], [x + 40, -296, 240], T.yellow);
  lightDefinitions.push({
    origin: [x, -352, 208],
    intensity: 100,
    color: "1.0 0.76 0.52",
    zone: "yard_entry",
  });
}

const routeGraph = Object.freeze({
  zones: [
    "loading_yard",
    "west_service",
    "reactor_hall",
    "east_control",
    "rear_service",
    "west_mezzanine",
    "east_mezzanine",
    "rear_catwalk",
  ],
  edges: [
    ["loading_yard", "west_service", 256, "west bay"],
    ["loading_yard", "reactor_hall", 320, "decon entrance"],
    ["loading_yard", "east_control", 256, "east bay"],
    ["west_service", "reactor_hall", 256, "south side opening"],
    ["west_service", "reactor_hall", 256, "north side opening"],
    ["reactor_hall", "east_control", 256, "south side opening"],
    ["reactor_hall", "east_control", 256, "north side opening"],
    ["west_service", "rear_service", 416, "west rear opening"],
    ["reactor_hall", "rear_service", 272, "west rear reactor opening"],
    ["reactor_hall", "rear_service", 272, "east rear reactor opening"],
    ["east_control", "rear_service", 416, "east rear opening"],
    ["west_service", "west_mezzanine", 224, "west stairs"],
    ["east_control", "east_mezzanine", 224, "east stairs"],
    ["west_mezzanine", "rear_catwalk", 192, "west upper connector"],
    ["east_mezzanine", "rear_catwalk", 192, "east upper connector"],
    ["west_mezzanine", "reactor_hall", 192, "west balcony opening"],
    ["east_mezzanine", "reactor_hall", 192, "east balcony opening"],
  ],
});

const neutralSpawns = [
  [-1320, -1080, 48, 0, -900, -760],
  [-560, -1080, 48, 0, -280, -720],
  [0, -1120, 48, 0, 0, -760],
  [560, -1080, 48, 0, 280, -720],
  [1320, -1060, 48, 0, 940, -760],
  [-1320, -416, 48, 0, -1040, -200],
  [1320, -416, 48, 0, 1040, -200],
  [-1280, 128, 48, 0, -920, 128],
  [-760, 336, 48, 0, -520, 336],
  [1280, 128, 48, 0, 920, 128],
  [760, 336, 48, 0, 520, 336],
  [-416, -144, 48, 0, -160, 64],
  [416, -144, 48, 0, 160, 64],
  [-416, 560, 48, 0, -160, 400],
  [416, 560, 48, 0, 160, 400],
  [-1032, 1088, 48, 0, -640, 960],
  [1032, 1088, 48, 0, 640, 960],
  [-1248, 320, 208, 0, -900, 480],
  [1248, 320, 208, 0, 900, 480],
  [0, 944, 208, 0, 0, 720],
];

const alliedSpawns = [
  [-1320, -1080, 48, 0, -900, -760],
  [-560, -1080, 48, 0, -280, -720],
  [0, -1120, 48, 0, 0, -760],
  [-1320, -416, 48, 0, -1040, -200],
  [-1280, 128, 48, 0, -920, 128],
  [-760, 336, 48, 0, -520, 336],
  [-416, -144, 48, 0, -160, 64],
  [-416, 560, 48, 0, -160, 400],
  [-1032, 1088, 48, 0, -640, 960],
  [-1248, 320, 208, 0, -900, 480],
];
const axisSpawns = [
  [1320, -1060, 48, 0, 940, -760],
  [560, -1080, 48, 0, 280, -720],
  [0, -880, 48, 0, 0, -560],
  [1320, -416, 48, 0, 1040, -200],
  [1280, 128, 48, 0, 920, 128],
  [760, 336, 48, 0, 520, 336],
  [416, -144, 48, 0, 160, 64],
  [416, 560, 48, 0, 160, 400],
  [1032, 1088, 48, 0, 640, 960],
  [1248, 320, 208, 0, 900, 480],
];

function spawnProperties(spawn) {
  const [x, y, z, _unused, targetX, targetY] = spawn;
  return {
    origin: `${x} ${y} ${z}`,
    angle: String(yawToward(x, y, targetX, targetY)),
  };
}

function spawnIntersectsCollision(spawn) {
  const [x, y, z] = spawn;
  const hull = {
    min: [x - 18, y - 18, z - 32],
    max: [x + 18, y + 18, z + 56],
  };
  const boxHits = collisionBoxes.filter(
    (box) =>
      hull.max[0] > box.min[0] &&
      hull.min[0] < box.max[0] &&
      hull.max[1] > box.min[1] &&
      hull.min[1] < box.max[1] &&
      hull.max[2] > box.min[2] &&
      hull.min[2] < box.max[2],
  );
  const cylinderHits = collisionCylinders.filter((cylinder) => {
    if (hull.max[2] <= cylinder.minZ || hull.min[2] >= cylinder.maxZ) return false;
    const closestX = Math.max(hull.min[0], Math.min(cylinder.center[0], hull.max[0]));
    const closestY = Math.max(hull.min[1], Math.min(cylinder.center[1], hull.max[1]));
    const dx = closestX - cylinder.center[0];
    const dy = closestY - cylinder.center[1];
    return dx * dx + dy * dy < cylinder.radius * cylinder.radius;
  });
  return [...boxHits, ...cylinderHits];
}

const allSpawns = [...neutralSpawns, ...alliedSpawns, ...axisSpawns];
const spawnCollisions = allSpawns.flatMap((spawn, index) =>
  spawnIntersectsCollision(spawn).map((hit) => ({ index, spawn: spawn.slice(0, 3), role: hit.role })),
);
if (spawnCollisions.length) {
  throw new Error(`Spawn clearance failed: ${JSON.stringify(spawnCollisions)}`);
}

const worldspawn = [
  "{",
  '"classname" "worldspawn"',
  '"message" "Codex Reactor"',
  '"ambientlight" "18 20 24"',
  '"suncolor" "130 112 84"',
  '"sundirection" "300 220 0"',
  '"sundiffusecolor" "62 72 92"',
  '"sundiffuse" "1.05"',
  '"_color" "1.0 0.94 0.84"',
  '"farplane" "5000"',
  '"farplane_color" "0.36 0.40 0.46"',
  ...brushes.map((brush, index) => `// brush ${index} ${brush.role}\n${brush.text}`),
  "}",
].join("\n");

const entities = [worldspawn];
entities.push(
  pointEntity("info_player_start", {
    origin: "0 -1100 64",
    angle: "90",
  }),
);
for (const spawn of neutralSpawns) {
  entities.push(pointEntity("info_player_deathmatch", spawnProperties(spawn)));
}
for (const spawn of alliedSpawns) {
  entities.push(pointEntity("info_player_allied", spawnProperties(spawn)));
}
for (const spawn of axisSpawns) {
  entities.push(pointEntity("info_player_axis", spawnProperties(spawn)));
}
for (const light of lightDefinitions) {
  entities.push(
    pointEntity("light", {
      origin: light.origin.join(" "),
      light: String(light.intensity),
      _color: light.color,
      overbright_range: "0.2",
    }),
  );
}

const mapText = `${entities
  .map((entity, index) => `// entity ${index}\n${entity}`)
  .join("\n")}\n`;
if (mapText.includes("\\n")) throw new Error("Generated MAP contains literal escaped newlines");
const mapPath = path.join(mapRoot, `${mapName}.map`);
fs.writeFileSync(mapPath, mapText, "utf8");

const scriptText = `main:

setcvar "g_obj_alliedtext1" "Codex Reactor"
setcvar "g_obj_alliedtext2" "Close-range industrial deathmatch"
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
const precacheText = `exec global/DMprecache.scr
cache models/items/dm_50_healthbox.tik
cache models/fx/bazookaexplosion_dm.tik
`;
fs.writeFileSync(path.join(mapRoot, `${mapName}.scr`), scriptText, "utf8");
fs.writeFileSync(path.join(mapRoot, `${mapName}_precache.scr`), precacheText, "utf8");

const report = {
  schemaVersion: 1,
  mapName,
  title: "Codex Reactor",
  originalDesign: true,
  designBrief: {
    target: "Allied Assault BSP 19 and OpenMoHAA",
    modes: ["DM", "TDM"],
    intendedPlayers: { minimum: 4, maximum: 16, botQa: 8 },
    fidelity: "original Nuke-inspired modern industrial reactor annex",
    assetPolicy: "project-owned original Nuke diffuse textures plus stock AA sky/scripts",
    combatTarget: "predominantly close range with 256+ unit primary lanes",
    lighting: "warm daylight yard, cool restrained industrial interior fixtures",
    omissions: ["moving doors", "Valve geometry", "Valve textures", "narrow vents", "dynamic obstacles"],
  },
  bounds: { min: [-1536, -1280, -64], max: [1536, 1280, 576] },
  topology: {
    lowerZones: 5,
    upperZones: 3,
    routeGraph,
    minimumPrimaryRouteWidth: Math.min(...routeGraph.edges.map((edge) => edge[2])),
    sightlineTarget: "approximately 256-1050 units; reactor/equipment/container masses block map-wide shots",
    movingDoors: 0,
    stairSpecs,
  },
  geometry: {
    worldBrushes: brushes.length,
    brushesByRole: Object.fromEntries([...brushesByRole.entries()].sort(([a], [b]) => a.localeCompare(b))),
    cylinders: collisionCylinders.length,
    collisionBoxes: collisionBoxes.length,
  },
  entities: {
    total: entities.length,
    neutralSpawns: neutralSpawns.length,
    alliedSpawns: alliedSpawns.length,
    axisSpawns: axisSpawns.length,
    spectatorStarts: 1,
    lights: lightDefinitions.length,
  },
  spawnOrigins: {
    neutral: neutralSpawns.map((spawn) => spawn.slice(0, 3)),
    allied: alliedSpawns.map((spawn) => spawn.slice(0, 3)),
    axis: axisSpawns.map((spawn) => spawn.slice(0, 3)),
  },
  spawnClearance: { testedHulls: allSpawns.length, collisions: spawnCollisions, passed: true },
  materials: {
    referenced: [...new Set(Object.values(T))].sort(),
    bundledOriginalTextures: bundledTextures,
    stockReferences: [T.caulk, T.sky],
    provenance: "generated/codex_nuke/ART-PROVENANCE.md",
  },
  map: {
    relativePath: `main/maps/dm/${mapName}.map`,
    bytes: Buffer.byteLength(mapText),
    sha256: crypto.createHash("sha256").update(mapText).digest("hex"),
  },
};
fs.writeFileSync(
  path.join(outputRoot, `${mapName}-design-report.json`),
  `${JSON.stringify(report, null, 2)}\n`,
  "utf8",
);

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
