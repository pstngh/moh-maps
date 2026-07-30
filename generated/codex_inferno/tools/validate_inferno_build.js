const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_inferno.map");
const bspPath = path.join(root, "main", "maps", "dm", "codex_inferno.bsp");
const reportPath = path.join(root, "codex_inferno-generation-report.json");
const textureRoot = path.join(root, "main", "textures");

const map = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const failures = [];

function expect(condition, message) {
  if (!condition) failures.push(message);
}

function count(pattern) {
  return [...map.matchAll(pattern)].length;
}

let braceDepth = 0;
for (const character of map) {
  if (character === "{") braceDepth++;
  if (character === "}") braceDepth--;
  if (braceDepth < 0) {
    failures.push("Map closes a brace before its matching opening brace");
    break;
  }
}

const customMaterials = new Set(
  [...map.matchAll(/\s(codex_inferno\/[a-z0-9_]+)\s/g)].map(
    (match) => match[1]
  )
);
for (const material of customMaterials) {
  const imagePath = path.join(textureRoot, `${material}.tga`);
  expect(fs.existsSync(imagePath), `Missing custom texture: ${imagePath}`);
}

expect(braceDepth === 0, `Map brace depth ends at ${braceDepth}`);
expect(count(/"classname" "worldspawn"/g) === 1, "Expected one worldspawn");
expect(count(/"classname" "func_detail"/g) === 0, "AA Q3map strips func_detail brush entities");
expect(count(/"classname" "info_player_axis"/g) === 16, "Expected 16 Axis spawns");
expect(count(/"classname" "info_player_allied"/g) === 16, "Expected 16 Allied spawns");
expect(
  count(/"classname" "info_player_deathmatch"/g) === 24,
  "Expected 24 neutral DM spawns"
);
expect(count(/"classname" "info_player_start"/g) === 1, "Expected one player start");
expect(count(/"classname" "light"/g) === 8, "Expected eight authored interior lights");
expect(customMaterials.size === 16, "Expected all sixteen original texture roles");
expect(report.construction === "authored-from-scratch", "Construction policy changed");
expect(
  report.referencePolicy === "route-and-scale-inspiration-only",
  "Reference-use policy changed"
);
expect(report.compiledWorldBrushes >= 400 && report.compiledWorldBrushes < 1200,
  "Authored brush count left the intended safety range"
);
expect(report.routeNames.length === 20, "Expected twenty named authored spaces");
expect(report.grid.openCells === 362, "Authored route-grid topology changed");
expect(
  report.sourceSolidsImported === 0 &&
    report.sourcePropsImported === 0 &&
    report.sourceDisplacementsImported === 0,
  "Source geometry or props were imported"
);
expect(
  !/materials\/|models\/props\/|de_inferno|hr_[a-z]\//i.test(map),
  "Generated map contains a Source asset/reference path"
);
expect(count(/\+surfaceparm nolightmap/g) === 0, "Broad nolightmap policy was added");
for (const key of [
  "ambientlight",
  "suncolor",
  "sundirection",
  "sundiffusecolor",
  "sundiffuse",
  "farplane",
  "farplane_color",
]) {
  expect(map.includes(`"${key}"`), `Missing lighting/world key: ${key}`);
}
expect(fs.existsSync(bspPath), "Compiled BSP is missing");

const result = {
  mapBytes: Buffer.byteLength(map),
  bspBytes: fs.existsSync(bspPath) ? fs.statSync(bspPath).size : 0,
  compiledWorldBrushes: report.compiledWorldBrushes,
  buildingMasses: report.buildingMasses,
  facadeWindows: report.facadeWindows,
  customMaterials: [...customMaterials].sort(),
  routeNames: report.routeNames,
  spawnCounts: report.spawns,
  pointLights: report.pointLights,
  failures,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (failures.length) process.exitCode = 1;
