#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const mapName = process.argv[2] || "codex_v2_depot";
const outputRoot = path.resolve(process.argv[3] || path.join(__dirname, ".."));
if (!/^[A-Za-z0-9_]+$/.test(mapName)) {
  throw new Error("Map name may contain only letters, numbers, and underscores");
}

const mapRoot = path.join(outputRoot, "main", "maps", "dm");
fs.mkdirSync(mapRoot, { recursive: true });

const T = Object.freeze({
  caulk: "common/caulk",
  sky: "sky/mohday1",
  bunker: "general_structure/bunker_wall",
  bunkerAlt: "normandy/bunker_conc3",
  concrete: "general_structure/jh_conc512b",
  concreteA: "mohcommon/jeff-concrete-walla",
  concreteB: "mohcommon/jeff-concrete-wallb",
  floor: "algiers/whsflrset1_1b",
  step: "algiers/doccrtset_1stepsml",
  grate: "general_industrial/deckgrate_set1b",
  grateFence: "general_industrial/deckgrate_set1a",
  ceiling: "normandy/bunk_ceiling",
  ceilingBeam: "normandy/bunk_ceiling_beam",
  iron: "das_boot/ironwall1",
  rust: "german/rusty_iron",
  ibeam: "mohcommon/ibeam_1a",
  brace: "general_industrial/verticalbrace",
  utilitySide: "general_industrial/utilitybox_side",
  utilityFront: "general_industrial/utilitybox_front",
  utilityTop: "general_industrial/utilboxtop",
  crateSide: "german/crate_reinforced1_side",
  crateTop: "german/crate_reinforced1_top",
});

function fmt(value) {
  if (!Number.isFinite(value)) throw new Error(`Non-finite number: ${value}`);
  const rounded = Math.round(value * 1000) / 1000;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(3);
}

function sha256(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

function material(texture, options = {}) {
  const {
    scaleX = 0.5,
    scaleY = 0.5,
    rotation = 0,
    shiftX = 0,
    shiftY = 0,
    content = 0,
    surface = 0,
    value = 0,
    extensions = "",
  } = options;
  return { texture, scaleX, scaleY, rotation, shiftX, shiftY, content, surface, value, extensions };
}

const M = Object.freeze({
  caulk: material(T.caulk, { surface: 160 }),
  caulkDetail: material(T.caulk, { surface: 160, extensions: "+surfaceparm detail" }),
  sky: material(T.sky, { scaleX: 1, scaleY: 1 }),
  bunker: material(T.bunker, { scaleX: 1, scaleY: 1, extensions: "surfaceDensity 64" }),
  bunkerDetail: material(T.bunker, { scaleX: 1, scaleY: 1, extensions: "+surfaceparm detail surfaceDensity 64" }),
  bunkerAlt: material(T.bunkerAlt),
  concrete: material(T.concrete),
  concreteDetail: material(T.concrete, { extensions: "+surfaceparm detail" }),
  concreteA: material(T.concreteA),
  concreteB: material(T.concreteB),
  floor: material(T.floor),
  floorDetail: material(T.floor, { extensions: "+surfaceparm detail" }),
  step: material(T.step, { extensions: "+surfaceparm detail" }),
  grate: material(T.grate, { surface: 32768, extensions: "+surfaceparm detail" }),
  grateStructural: material(T.grate, { surface: 32768 }),
  grateFence: material(T.grateFence, { content: 8192, surface: 262176, extensions: "+surfaceparm detail" }),
  ceiling: material(T.ceiling),
  ceilingDetail: material(T.ceiling, { extensions: "+surfaceparm detail" }),
  ceilingBeam: material(T.ceilingBeam, { surface: 32768, extensions: "+surfaceparm detail" }),
  iron: material(T.iron, { surface: 32768, extensions: "+surfaceparm detail" }),
  ironStructural: material(T.iron, { surface: 32768 }),
  rust: material(T.rust, { surface: 32768, extensions: "+surfaceparm detail" }),
  ibeam: material(T.ibeam, { surface: 32768, extensions: "+surfaceparm detail" }),
  brace: material(T.brace, { content: 204800, surface: 35328, extensions: "+surfaceparm detail" }),
  utilitySide: material(T.utilitySide, { surface: 32768, extensions: "+surfaceparm detail" }),
  utilityFront: material(T.utilityFront, { surface: 32768, extensions: "+surfaceparm detail" }),
  utilityTop: material(T.utilityTop, { surface: 32768, extensions: "+surfaceparm detail" }),
  crateSide: material(T.crateSide, { surface: 16384, extensions: "+surfaceparm detail" }),
  crateTop: material(T.crateTop, { surface: 16384, extensions: "+surfaceparm detail" }),
});

function face(points, spec) {
  const pointText = points.map((point) => `( ${point.map(fmt).join(" ")} )`).join(" ");
  return `${pointText} ${spec.texture} ${fmt(spec.shiftX)} ${fmt(spec.shiftY)} ${fmt(spec.rotation)} ${fmt(spec.scaleX)} ${fmt(spec.scaleY)} ${spec.content} ${spec.surface} ${spec.value}${spec.extensions ? ` ${spec.extensions}` : ""}`;
}

const faceNames = ["xMin", "xMax", "yMin", "yMax", "zMin", "zMax"];

function assertBounds(min, max, label) {
  if (min.length !== 3 || max.length !== 3 || min.some((value, axis) => !Number.isFinite(value) || value >= max[axis]) || max.some((value) => !Number.isFinite(value))) {
    throw new Error(`Invalid ${label} bounds: ${JSON.stringify({ min, max })}`);
  }
}

function boxBrush(min, max, faceSpecs) {
  assertBounds(min, max, "box");
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  const planes = [
    [[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]],
    [[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]],
    [[16, minY, -16], [0, minY, 0], [16, minY, 16]],
    [[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]],
    [[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]],
    [[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]],
  ];
  return ["{", ...planes.map((points, index) => face(points, faceSpecs[faceNames[index]])), "}"].join("\n");
}

function cylinderBrush(center, minZ, maxZ, radius, sides, sideSpec, bottomSpec, topSpec) {
  const [centerX, centerY] = center;
  const vertices = Array.from({ length: sides }, (_, index) => {
    const angle = (index / sides) * Math.PI * 2;
    return [centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius];
  });
  const lines = ["{"];
  for (let index = 0; index < sides; index += 1) {
    const current = vertices[index];
    const next = vertices[(index + 1) % sides];
    lines.push(face([[next[0], next[1], minZ], [current[0], current[1], minZ], [current[0], current[1], maxZ]], sideSpec));
  }
  lines.push(face([[centerX - 16, centerY + 16, minZ], [centerX, centerY, minZ], [centerX + 16, centerY + 16, minZ]], bottomSpec));
  lines.push(face([[centerX + 16, centerY + 16, maxZ], [centerX, centerY, maxZ], [centerX - 16, centerY + 16, maxZ]], topSpec));
  lines.push("}");
  return lines.join("\n");
}

function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) lines.push(`"${key}" "${value}"`);
  lines.push("}");
  return lines.join("\n");
}

function yawToward(x, y, targetX, targetY) {
  let degrees = (Math.atan2(targetY - y, targetX - x) * 180) / Math.PI;
  if (degrees < 0) degrees += 360;
  return Math.round(degrees);
}

function faceSet(hidden, visible = {}) {
  return Object.fromEntries(faceNames.map((name) => [name, visible[name] || hidden]));
}

const brushes = [];
const collisionBoxes = [];
const collisionCylinders = [];
const roleCounts = new Map();
const usedMaterials = new Set();

function countRole(role) {
  roleCounts.set(role, (roleCounts.get(role) || 0) + 1);
}

function recordFaceMaterials(faces) {
  for (const spec of Object.values(faces)) usedMaterials.add(spec.texture);
}

function addBox(role, min, max, faces, options = {}) {
  const { collision = true, expectedGrid = 16 } = options;
  recordFaceMaterials(faces);
  brushes.push({ role, type: "box", min: [...min], max: [...max], expectedGrid, collision, text: boxBrush(min, max, faces) });
  if (collision) collisionBoxes.push({ role, min: [...min], max: [...max] });
  countRole(role);
}

function addCylinder(role, center, minZ, maxZ, radius, sideSpec, topSpec = M.iron, sides = 12, options = {}) {
  const { collision = true } = options;
  usedMaterials.add(sideSpec.texture);
  usedMaterials.add(topSpec.texture);
  usedMaterials.add(M.caulkDetail.texture);
  brushes.push({ role, type: "cylinder", center: [...center], minZ, maxZ, radius, sides, collision, text: cylinderBrush(center, minZ, maxZ, radius, sides, sideSpec, M.caulkDetail, topSpec) });
  if (collision) collisionCylinders.push({ role, center: [...center], minZ, maxZ, radius });
  countRole(role);
}

function structuralFloor(role, min, max, top) {
  addBox(role, min, max, faceSet(M.caulk, { zMax: top }));
}

function structuralWall(role, min, max, exposed) {
  addBox(role, min, max, faceSet(M.caulk, exposed));
}

function detailBox(role, min, max, exposed, options = {}) {
  addBox(role, min, max, faceSet(M.caulkDetail, exposed), options);
}

function addCrate(role, min, max) {
  detailBox(role, min, max, {
    xMin: M.crateSide,
    xMax: M.crateSide,
    yMin: M.crateSide,
    yMax: M.crateSide,
    zMax: M.crateTop,
  });
}

function addUtilityBox(role, min, max, frontFace) {
  const exposed = { zMax: M.utilityTop };
  exposed[frontFace] = M.utilityFront;
  for (const side of ["xMin", "xMax", "yMin", "yMax"]) {
    if (side !== frontFace) exposed[side] = M.utilitySide;
  }
  detailBox(role, min, max, exposed, { expectedGrid: 4 });
}

// Sealed outdoor sky shell. The visible retaining walls and bunker shell sit
// just inside these sky faces, so no black void can appear above them.
structuralFloor("yard_floor", [-1504, -1248, -64], [1504, -320, 0], M.concreteA);
structuralFloor("bunker_floor", [-1504, -320, -64], [1504, 1248, 0], M.floor);
structuralWall("sky_west", [-1536, -1280, -64], [-1504, 1280, 608], { xMax: M.sky });
structuralWall("sky_east", [1504, -1280, -64], [1536, 1280, 608], { xMin: M.sky });
structuralWall("sky_south", [-1504, -1280, -64], [1504, -1248, 608], { yMax: M.sky });
structuralWall("sky_north", [-1504, 1248, -64], [1504, 1280, 608], { yMin: M.sky });
structuralWall("sky_ceiling", [-1536, -1280, 576], [1536, 1280, 608], { zMin: M.sky });

// Yard retaining walls obscure the lower sky shell and use the stock V2
// bunker material on the faces that players actually see.
structuralWall("yard_retaining", [-1504, -1248, 0], [-1472, -320, 192], { xMax: M.bunker });
structuralWall("yard_retaining", [1472, -1248, 0], [1504, -320, 192], { xMin: M.bunker });
structuralWall("yard_retaining", [-1472, -1248, 0], [1472, -1216, 160], { yMax: M.bunker });

// Main bunker shell with three permanently open, bot-safe front passages.
const frontSegments = [
  [-1472, -1152],
  [-864, -192],
  [192, 864],
  [1152, 1472],
];
for (const [minX, maxX] of frontSegments) {
  structuralWall("front_wall", [minX, -320, 0], [maxX, -288, 384], { yMin: M.bunker, yMax: M.concreteB });
}
for (const [minX, maxX] of [[-1152, -864], [-192, 192], [864, 1152]]) {
  structuralWall("front_lintel", [minX, -320, 224], [maxX, -288, 384], { yMin: M.bunker, yMax: M.concreteB, zMin: M.bunkerAlt });
  detailBox("door_frame", [minX, -336, 0], [minX + 16, -288, 240], { xMax: M.iron, yMin: M.iron, yMax: M.iron });
  detailBox("door_frame", [maxX - 16, -336, 0], [maxX, -288, 240], { xMin: M.iron, yMin: M.iron, yMax: M.iron });
  detailBox("door_frame", [minX, -336, 224], [maxX, -288, 240], { yMin: M.iron, yMax: M.iron, zMin: M.iron });
}

structuralWall("bunker_side", [-1504, -320, 0], [-1472, 1248, 384], { xMax: M.bunker });
structuralWall("bunker_side", [1472, -320, 0], [1504, 1248, 384], { xMin: M.bunker });
structuralWall("bunker_rear", [-1472, 1216, 0], [1472, 1248, 384], { yMin: M.bunker });
structuralWall("bunker_roof", [-1504, -320, 384], [1504, 1248, 416], {
  xMin: M.bunker,
  xMax: M.bunker,
  yMin: M.bunker,
  yMax: M.bunker,
  zMax: M.ironStructural,
});
detailBox("interior_ceiling", [-1472, -288, 376], [1472, 1216, 384], { zMin: M.ceiling }, { collision: false });

// Two long internal walls define a central assembly bay and two side-service
// loops. Openings are authored as absent wall spans, not door entities.
for (const [minX, maxX, hallFace, serviceFace] of [
  [-640, -608, "xMax", "xMin"],
  [608, 640, "xMin", "xMax"],
]) {
  for (const [minY, maxY] of [[-288, -64], [192, 448], [640, 832]]) {
    const exposed = {};
    exposed[hallFace] = M.concrete;
    exposed[serviceFace] = M.bunker;
    structuralWall("hall_divider", [minX, minY, 0], [maxX, maxY, 376], exposed);
  }
  for (const [minY, maxY] of [[-64, 192], [448, 640]]) {
    const exposed = {};
    exposed[hallFace] = M.concrete;
    exposed[serviceFace] = M.bunker;
    structuralWall("hall_divider_lintel", [minX, minY, 224], [maxX, maxY, 376], exposed);
    detailBox("interior_frame", [minX - 8, minY, 0], [maxX + 8, minY + 16, 240], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron });
    detailBox("interior_frame", [minX - 8, maxY - 16, 0], [maxX + 8, maxY, 240], { xMin: M.iron, xMax: M.iron, yMin: M.iron, yMax: M.iron });
    detailBox("interior_frame", [minX - 8, minY, 224], [maxX + 8, maxY, 240], { xMin: M.iron, xMax: M.iron, zMin: M.iron });
  }
}

// Rear wall has two 256-unit passages into the full-width crossover.
for (const [minX, maxX] of [[-608, -448], [-192, 192], [448, 608]]) {
  structuralWall("rear_hall_wall", [minX, 832, 0], [maxX, 864, 376], { yMin: M.concrete, yMax: M.bunker });
}
for (const [minX, maxX] of [[-448, -192], [192, 448]]) {
  structuralWall("rear_hall_lintel", [minX, 832, 224], [maxX, 864, 376], { yMin: M.concrete, yMax: M.bunker, zMin: M.bunkerAlt });
  detailBox("rear_frame", [minX, 824, 0], [minX + 16, 872, 240], { xMax: M.iron, yMin: M.iron, yMax: M.iron });
  detailBox("rear_frame", [maxX - 16, 824, 0], [maxX, 872, 240], { xMin: M.iron, yMin: M.iron, yMax: M.iron });
  detailBox("rear_frame", [minX, 824, 224], [maxX, 872, 240], { yMin: M.iron, yMax: M.iron, zMin: M.iron });
}

// Native-looking ceiling beams and I-beam columns break the hall into human-
// scale bays while leaving every primary path broad.
for (const y of [-32, 224, 480, 736, 992]) {
  detailBox("ceiling_beam", [-1472, y - 8, 344], [1472, y + 8, 360], { xMin: M.ceilingBeam, xMax: M.ceilingBeam, yMin: M.ceilingBeam, yMax: M.ceilingBeam, zMin: M.ceilingBeam });
}
for (const x of [-592, 592]) {
  for (const y of [-32, 224, 480, 736]) {
    detailBox("hall_column", [x - 12, y - 12, 0], [x + 12, y + 12, 344], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam });
  }
}

// Central inspection cradle: compact, layered industrial cover rather than a
// giant room-filling prop. It leaves 256+ units of circulation on both sides.
detailBox("assembly_plinth", [-176, 32, 0], [176, 544, 32], { xMin: M.concreteDetail, xMax: M.concreteDetail, yMin: M.concreteDetail, yMax: M.concreteDetail, zMax: M.concreteDetail });
for (const x of [-144, 112]) {
  detailBox("assembly_rail", [x, 56, 32], [x + 32, 520, 48], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });
}
for (let y = 80; y <= 496; y += 64) {
  detailBox("assembly_tie", [-128, y, 48], [128, y + 16, 56], { xMin: M.rust, xMax: M.rust, yMin: M.rust, yMax: M.rust, zMax: M.rust });
}
addCylinder("test_engine", [0, 288], 56, 168, 72, M.iron, M.rust, 12);
addCylinder("test_engine_band", [0, 288], 96, 120, 84, M.rust, M.rust, 12);
detailBox("engine_console", [-304, 208, 0], [-208, 368, 104], { xMin: M.utilitySide, xMax: M.utilityFront, yMin: M.utilitySide, yMax: M.utilitySide, zMax: M.utilityTop });
detailBox("engine_console", [208, 208, 0], [304, 368, 104], { xMin: M.utilityFront, xMax: M.utilitySide, yMin: M.utilitySide, yMax: M.utilitySide, zMax: M.utilityTop });

// Broad 16:32 stairs and a 192-unit-wide U-shaped upper route mirror the
// usable proportions measured from obj_team2 without copying its topology.
const stairSpecs = [];
for (const centerX of [-1088, 1088]) {
  for (let step = 0; step < 12; step += 1) {
    const minY = -224 + step * 32;
    const maxY = minY + 32;
    const maxZ = 16 + (step + 1) * 16;
    detailBox("catwalk_stair", [centerX - 112, minY, 0], [centerX + 112, maxY, maxZ], {
      xMin: M.step,
      xMax: M.step,
      yMin: M.step,
      yMax: M.step,
      zMax: M.step,
    });
  }
  stairSpecs.push({ centerX, width: 224, tread: 32, rise: 16, steps: 12 });
}

detailBox("west_landing", [-1200, 160, 192], [-384, 384, 208], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });
detailBox("east_landing", [384, 160, 192], [1200, 384, 208], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });
detailBox("west_catwalk", [-576, -32, 192], [-384, 800, 208], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });
detailBox("east_catwalk", [384, -32, 192], [576, 800, 208], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });
detailBox("rear_catwalk", [-576, 640, 192], [576, 800, 208], { xMin: M.grate, xMax: M.grate, yMin: M.grate, yMax: M.grate, zMax: M.grate });

for (const x of [-384, 384]) {
  for (const y of [0, 160, 320, 480, 640, 784]) {
    detailBox("catwalk_post", [x - 6, y - 6, 208], [x + 6, y + 6, 272], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam }, { expectedGrid: 2 });
  }
  detailBox("catwalk_handrail", [x - 5, -8, 264], [x + 5, 792, 274], { xMin: M.rust, xMax: M.rust, yMin: M.rust, yMax: M.rust }, { expectedGrid: 2 });
}
for (const y of [648, 792]) {
  for (const x of [-576, -384, 384, 576]) {
    detailBox("rear_rail_post", [x - 6, y - 6, 208], [x + 6, y + 6, 272], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam }, { expectedGrid: 2 });
  }
  detailBox("rear_handrail", [-576, y - 5, 264], [576, y + 5, 274], { xMin: M.rust, xMax: M.rust, yMin: M.rust, yMax: M.rust }, { expectedGrid: 2 });
}

// Purposeful lower-route cover. Everything is grounded at z=0 and kept away
// from door openings, stairs, and the minimum 192-unit circulation envelope.
for (const [min, max] of [
  [[-1376, 32, 0], [-1248, 192, 112]],
  [[-944, 480, 0], [-784, 608, 96]],
  [[-1360, 896, 0], [-1168, 1088, 112]],
  [[1248, 32, 0], [1376, 192, 112]],
  [[784, 480, 0], [944, 608, 96]],
  [[1168, 896, 0], [1360, 1088, 112]],
  [[-512, 928, 0], [-320, 976, 96]],
  [[320, 928, 0], [512, 976, 96]],
]) {
  detailBox("service_cover", min, max, { xMin: M.bunkerDetail, xMax: M.bunkerDetail, yMin: M.bunkerDetail, yMax: M.bunkerDetail, zMax: M.concreteDetail });
}

// Wall-mounted utility boxes use the same face-specific texture family as
// obj_team2 instead of wrapping a generic image around every side.
for (const [y, z] of [[80, 72], [520, 64]]) {
  addUtilityBox("utility_box", [-608, y, z], [-584, y + 96, z + 72], "xMax");
  addUtilityBox("utility_box", [584, y, z], [608, y + 96, z + 72], "xMin");
}
for (const x of [-1280, -960, 960, 1280]) {
  addUtilityBox("facade_utility", [x - 48, -344, 64], [x + 48, -320, 136], "yMin");
}

// Facade bays, braces, and trim reproduce the layered stock construction:
// structural wall, thin concrete panel, I-beam edge, then nonblocking brace.
for (const [minX, maxX] of frontSegments) {
  detailBox("facade_band", [minX + 16, -332, 272], [maxX - 16, -320, 288], { yMin: M.iron, zMin: M.iron, zMax: M.iron });
}
for (const x of [-1360, -1008, -528, 528, 1008, 1360]) {
  detailBox("facade_pier", [x - 8, -336, 16], [x + 8, -320, 352], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam });
}
for (const [minX, maxX] of [[-832, -608], [608, 832]]) {
  detailBox("facade_inset", [minX, -336, 96], [maxX, -320, 256], { yMin: M.concreteA });
  detailBox("facade_brace", [minX + 32, -344, 112], [maxX - 32, -336, 240], { yMin: M.brace }, { collision: false, expectedGrid: 8 });
}

// Outdoor cover and loading detail. Brush crates have face-correct wood art;
// the truck is the one stock vehicle family proven by obj_team2 source use.
for (const [min, max] of [
  [[-1312, -1136, 0], [-1216, -1040, 96]],
  [[-1200, -1136, 0], [-1104, -1040, 96]],
  [[-1256, -1040, 0], [-1160, -944, 96]],
  [[-864, -688, 0], [-768, -592, 96]],
  [[768, -688, 0], [864, -592, 96]],
  [[-96, -1072, 0], [0, -976, 96]],
  [[16, -1072, 0], [112, -976, 96]],
]) addCrate("yard_crate", min, max);

for (const [min, max] of [
  [[-1088, -816, 0], [-736, -784, 128]],
  [[736, -816, 0], [1088, -784, 128]],
  [[-416, -576, 0], [-160, -544, 112]],
  [[160, -576, 0], [416, -544, 112]],
]) {
  detailBox("yard_blast_wall", min, max, { xMin: M.bunkerDetail, xMax: M.bunkerDetail, yMin: M.bunkerDetail, yMax: M.bunkerDetail, zMax: M.concreteDetail });
}

for (const [x, y] of [[-896, -784], [896, -784], [-288, -544], [288, -544]]) {
  detailBox("yard_wall_cap", [x - 12, y - 16, 128], [x + 12, y + 48, 192], { xMin: M.ibeam, xMax: M.ibeam, yMin: M.ibeam, yMax: M.ibeam });
}

// Under-catwalk fixtures are separate from ceiling fixtures so the lower
// service loops remain readable beneath the solid deck.
const entities = [];
const modelPlacements = [];
const lightPlacements = [];

function addModel(classname, model, origin, properties = {}) {
  entities.push(pointEntity(classname, { model, origin: origin.map(fmt).join(" "), testanim: "idle", ...properties }));
  modelPlacements.push({ classname, model, origin: [...origin], ...properties });
}

function addLight(origin, intensity, color = "1.0 0.9 0.8", properties = {}) {
  entities.push(pointEntity("light", { origin: origin.map(fmt).join(" "), light: String(intensity), _color: color, overbright_range: "0.15", ...properties }));
  lightPlacements.push({ origin: [...origin], intensity, color, ...properties });
}

const ceilingFixtures = [
  [-320, 64, 320, 90], [320, 64, 320, 90],
  [-320, 384, 320, 90], [320, 384, 320, 90],
  [-320, 704, 320, 90], [320, 704, 320, 90],
  [-1120, 32, 320, 75], [-1120, 480, 320, 75], [-1120, 992, 320, 75],
  [1120, 32, 320, 75], [1120, 480, 320, 75], [1120, 992, 320, 75],
  [-256, 1040, 320, 75], [256, 1040, 320, 75],
];
for (const [x, y, z, intensity] of ceilingFixtures) {
  addModel("static_lamp_lightbulb-caged", "static//lightbulb_caged.tik", [x, y, z + 12], { scale: "1.20", angle: "-2" });
  addModel("script_model", "static//corona_orange.tik", [x, y, z + 4], { scale: "0.70", spawnflags: "1" });
  addLight([x, y, z - 24], intensity, "1.0 0.9 0.8", { radius: "60", spawnflags: "2", angles: "90 0 0" });
}
for (const [x, y] of [[-1040, 272], [-1040, 560], [1040, 272], [1040, 560], [-480, 688], [480, 688]]) {
  addModel("static_lamp_lightbulb-caged", "static//lightbulb_caged.tik", [x, y, 168], { scale: "1.0", angle: "-2" });
  addModel("script_model", "static//corona_orange.tik", [x, y, 160], { scale: "0.55", spawnflags: "1" });
  addLight([x, y, 144], 65, "1.0 0.82 0.62");
}
for (const [x, y] of [[-240, 160], [240, 160], [-240, 448], [240, 448]]) {
  addLight([x, y, 112], 60, "0.82 0.88 1.0");
}
addLight([0, 1040, 144], 65, "0.90 0.88 0.82");

addModel("static_vehicle_german_opeltruck", "static//vehicle_opeltruck.tik", [1120, -1016, 0], { scale: "1.0", angle: "0" });

const neutralSpawns = [
  [-1328, -944, 32, 0, 0], [-640, -1040, 32, 0, -480], [416, -1056, 32, 0, -480], [1328, -656, 32, 0, -480],
  [-1248, -128, 32, -896, 256], [-864, 736, 32, -320, 736], [1248, -128, 32, 896, 256], [864, 736, 32, 320, 736],
  [-448, -128, 32, 0, 288], [448, -128, 32, 0, 288], [-432, 512, 32, 0, 288], [432, 512, 32, 0, 288],
  [-896, 1056, 32, 0, 960], [896, 1056, 32, 0, 960],
  [-480, 96, 240, 0, 448], [480, 544, 240, 0, 448], [-256, 720, 240, 0, 448], [256, 720, 240, 0, 448],
];

const alliedSpawns = [
  [-1408, -720, 32, -960, -480], [-960, -1056, 32, -640, -480], [-592, -960, 32, -256, -480], [-256, -944, 32, 0, -480],
  [256, -944, 32, 0, -480], [592, -960, 32, 256, -480], [960, -1056, 32, 640, -480], [1328, -880, 32, 960, -480],
];
const axisSpawns = [
  [-1408, 800, 32, -960, 640], [-960, 1088, 32, -640, 640], [-560, 1056, 32, -256, 704], [-240, 1056, 32, 0, 704],
  [240, 1056, 32, 0, 704], [560, 1056, 32, 256, 704], [960, 1088, 32, 640, 640], [1408, 800, 32, 960, 640],
];

const spawnRecords = [];
function addSpawn(classname, [x, y, z, targetX, targetY]) {
  const angle = yawToward(x, y, targetX, targetY);
  entities.push(pointEntity(classname, { origin: `${x} ${y} ${z}`, angle: String(angle) }));
  spawnRecords.push({ classname, origin: [x, y, z], angle });
}
for (const spawn of neutralSpawns) addSpawn("info_player_deathmatch", spawn);
for (const spawn of alliedSpawns) addSpawn("info_player_allied", spawn);
for (const spawn of axisSpawns) addSpawn("info_player_axis", spawn);
entities.push(pointEntity("info_player_start", { origin: "0 -1152 32", angle: "90" }));
spawnRecords.push({ classname: "info_player_start", origin: [0, -1152, 32], angle: 90 });

const worldspawn = [
  "{",
  '"classname" "worldspawn"',
  '"message" "V2 Depot"',
  '"ambient" "32"',
  '"ambientlight" "7.5 8 10"',
  '"suncolor" "95 86 74"',
  '"sundirection" "315 90 0"',
  '"sundiffusecolor" "44 52 66"',
  '"sundiffuse" "0.75"',
  '"_color" "1.0 0.9 0.8"',
  '"farplane" "6000"',
  '"farplane_color" "0.25 0.27 0.30"',
  ...brushes.map((brush, index) => `// brush ${index}\n${brush.text}`),
  "}",
].join("\n");

const mapText = `${[worldspawn, ...entities].map((entity, index) => `// entity ${index}\n${entity}`).join("\n")}\n`;
const mapPath = path.join(mapRoot, `${mapName}.map`);
fs.writeFileSync(mapPath, mapText, "utf8");

const scriptText = `main:\n\nsetcvar "g_obj_alliedtext1" "V2 Depot"\nsetcvar "g_obj_alliedtext2" "Original stock-AA industrial deathmatch"\nsetcvar "g_obj_alliedtext3" "Open passages; three lower routes; upper loop"\nsetcvar "g_obj_axistext1" ""\nsetcvar "g_obj_axistext2" ""\nsetcvar "g_obj_axistext3" ""\n\nlevel waittill prespawn\nexec global/DMprecache.scr\nlevel.script = maps/dm/${mapName}.scr\nlevel waittill spawn\n\nend\n`;
fs.writeFileSync(path.join(mapRoot, `${mapName}.scr`), scriptText, "utf8");

const precacheText = `exec global/DMprecache.scr\ncache models/items/dm_50_healthbox.tik\ncache models/fx/bazookaexplosion_dm.tik\ncache models/static/lightbulb_caged.tik\ncache models/static/corona_orange.tik\ncache models/static/vehicle_opeltruck.tik\n`;
fs.writeFileSync(path.join(mapRoot, `${mapName}_precache.scr`), precacheText, "utf8");

const routeZones = [
  { id: "yard_west", bounds: [-1472, -1216, -192, -320, 0, 192] },
  { id: "yard_center", bounds: [-192, -1216, 192, -320, 0, 192] },
  { id: "yard_east", bounds: [192, -1216, 1472, -320, 0, 192] },
  { id: "west_service", bounds: [-1472, -288, -640, 1216, 0, 192] },
  { id: "assembly_hall", bounds: [-608, -288, 608, 832, 0, 192] },
  { id: "east_service", bounds: [640, -288, 1472, 1216, 0, 192] },
  { id: "rear_crossover", bounds: [-640, 864, 640, 1216, 0, 192] },
  { id: "west_upper", bounds: [-1200, -32, -384, 800, 208, 360] },
  { id: "rear_upper", bounds: [-576, 640, 576, 800, 208, 360] },
  { id: "east_upper", bounds: [384, -32, 1200, 800, 208, 360] },
];
const routeConnections = [
  ["yard_west", "west_service", 288], ["yard_center", "assembly_hall", 384], ["yard_east", "east_service", 288],
  ["west_service", "assembly_hall", 256], ["west_service", "assembly_hall", 192],
  ["east_service", "assembly_hall", 256], ["east_service", "assembly_hall", 192],
  ["assembly_hall", "rear_crossover", 256], ["assembly_hall", "rear_crossover", 256],
  ["west_service", "rear_crossover", 416], ["east_service", "rear_crossover", 416],
  ["west_service", "west_upper", 224], ["east_service", "east_upper", 224],
  ["west_upper", "rear_upper", 192], ["rear_upper", "east_upper", 192],
];

const designReport = {
  schemaVersion: 2,
  mapName,
  title: "V2 Depot",
  target: "Medal of Honor: Allied Assault BSP 19 / OpenMoHAA DM and TDM",
  designIntent: "Original compact V2-industrial depot using measured obj_team2 construction grammar, stock AA materials, face-specific texturing, broad bot routes, and no moving doors.",
  sourceReference: {
    path: "aa/obj_team2.map",
    policy: "construction grammar, material families, proportions, entity conventions, and lighting ratios only; no copied layout",
    measuredGrammar: "obj_team2-construction-grammar.json",
  },
  bounds: { playable: [-1472, -1216, 1472, 1216, 0, 376], sealed: [-1536, -1280, 1536, 1280, -64, 608] },
  brushes: {
    total: brushes.length,
    boxes: brushes.filter((brush) => brush.type === "box").length,
    cylinders: brushes.filter((brush) => brush.type === "cylinder").length,
    roles: Object.fromEntries([...roleCounts.entries()].sort(([a], [b]) => a.localeCompare(b))),
    hiddenFacePolicy: "All box faces default to common/caulk; only deliberately exposed faces receive stock visible materials.",
  },
  materials: { stockOnly: true, bundledOriginalTextures: [], used: [...usedMaterials].sort() },
  constructionRules: {
    structuralGrid: 16,
    detailGrid: 2,
    wallThicknesses: [32],
    primaryOpeningMinimum: 192,
    primaryCrossfireOpeningMinimum: 256,
    stair: { rise: 16, tread: 32, width: 224, countPerFlight: 12 },
    catwalkWidth: 192,
    lowerCatwalkHeadroom: 192,
    movingDoors: 0,
  },
  collision: { boxes: collisionBoxes, cylinders: collisionCylinders },
  spawns: spawnRecords,
  entities: { lights: lightPlacements, models: modelPlacements },
  routes: { zones: routeZones, connections: routeConnections },
  fixedViews: [
    { id: "yard_wide", origin: [0, -1120, 72], viewangles: [-8, 90, 0], covers: ["yard", "three entrances", "facade", "truck"] },
    { id: "west_entry", origin: [-1008, -656, 72], viewangles: [-5, 72, 0], covers: ["threshold", "frames", "service stair"] },
    { id: "hall_low", origin: [0, -192, 72], viewangles: [-4, 90, 0], covers: ["assembly bay", "central cover", "ceiling beams"] },
    { id: "west_service", origin: [-1328, 512, 72], viewangles: [-5, 0, 0], covers: ["deep interior", "under-catwalk lighting", "utility detail"] },
    { id: "rear_cross", origin: [-320, 1104, 72], viewangles: [-5, 270, 0], covers: ["rear crossover", "twin openings"] },
    { id: "upper_loop", origin: [-480, 320, 248], viewangles: [-5, 0, 0], covers: ["catwalk", "handrail", "upper lighting"] },
    { id: "hall_overview", origin: [0, 544, 256], viewangles: [35, 270, 0], covers: ["high overview", "roof closure", "grounded cover"] },
    { id: "map_edge", origin: [-1408, -1120, 72], viewangles: [-5, 45, 0], covers: ["retaining wall", "sky shell", "perimeter"] },
  ],
  generated: { mapBytes: Buffer.byteLength(mapText), mapSha256: sha256(mapText) },
  knownIntentionalOmissions: ["moving doors", "breakable machinery", "custom textures", "retail objective scripting", "dense cosmetic signage"],
};
fs.writeFileSync(path.join(outputRoot, `${mapName}-design-report.json`), `${JSON.stringify(designReport, null, 2)}\n`, "utf8");

process.stdout.write(`${mapPath}\nbrushes=${brushes.length} entities=${entities.length + 1} mapSha256=${designReport.generated.mapSha256}\n`);
