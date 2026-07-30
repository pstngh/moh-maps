const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_inferno.map");
const bspPath = path.join(root, "main", "maps", "dm", "codex_inferno.bsp");
const scriptPath = path.join(root, "main", "maps", "dm", "codex_inferno.scr");
const reportPath = path.join(root, "codex_inferno-generation-report.json");
const blueprintPath = path.join(root, "inferno-layout-reference-audit.json");
const layoutPath = path.join(root, "layout-plan.svg");
const textureRoot = path.join(root, "main", "textures");

const map = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const blueprintBytes = fs.readFileSync(blueprintPath);
const blueprint = JSON.parse(blueprintBytes.toString("utf8"));
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

const blueprintHash = crypto
  .createHash("sha256")
  .update(blueprintBytes)
  .digest("hex");

expect(braceDepth === 0, `Map brace depth ends at ${braceDepth}`);
expect(count(/"classname" "worldspawn"/g) === 1, "Expected one worldspawn");
expect(
  count(/"classname" "func_detail"/g) === 0,
  "AA Q3map strips func_detail brush entities"
);
expect(count(/"classname" "info_player_axis"/g) === 20, "Expected 20 Axis spawns");
expect(
  count(/"classname" "info_player_allied"/g) === 20,
  "Expected 20 Allied spawns"
);
expect(
  count(/"classname" "info_player_deathmatch"/g) === 67,
  "Expected all 67 measured neutral DM spawns"
);
expect(
  count(/"classname" "info_player_start"/g) === 1,
  "Expected one player start"
);
expect(
  count(/"classname" "light"/g) === report.pointLights,
  "Point-light count differs from generation report"
);
expect(customMaterials.size >= 14, "Expected at least fourteen authored texture roles");
expect(report.revision === 2, "Expected Inferno revision 2");
expect(
  report.construction === "manually-reauthored-clone-from-measured-topology",
  "Construction policy changed"
);
expect(
  report.blueprint.sha256 === blueprintHash,
  "Generation report does not match the committed measured blueprint"
);
expect(
  blueprint.source.reconstructedSolids === 7921 &&
    blueprint.source.failedSolids === 0,
  "Source reference reconstruction evidence changed"
);
expect(
  blueprint.walkGrid.connectedNodes === 6997 &&
    blueprint.walkGrid.connectedEdges === 13420 &&
    blueprint.walkGrid.unmatchedSpawns.length === 0,
  "Measured Inferno route graph changed or lost a spawn"
);
expect(
  report.geometry.floorRectangles >= 400 &&
    report.geometry.floorRectangles < 700,
  "Floor reconstruction left its measured merge range"
);
expect(
  report.geometry.wallRuns >= 900 && report.geometry.wallRuns < 1800,
  "Wall reconstruction left its measured merge range"
);
expect(
  report.geometry.totalWorldspawnBrushes >= 2400 &&
    report.geometry.totalWorldspawnBrushes < 3500,
  "Authored brush count left the compile safety range"
);
expect(
  report.geometry.measuredArches === 10,
  "Measured landmark-arch count changed"
);
expect(
  report.sourceSolidsImported === 0 &&
    report.sourcePropsImported === 0 &&
    report.sourceDisplacementsImported === 0 &&
    report.sourceTexturesIncluded === 0 &&
    report.sourceModelsIncluded === 0,
  "Source geometry or assets were imported"
);
expect(
  !/materials\/|models\/props\/|de_inferno|hr_[a-z]\//i.test(map),
  "Generated map contains a Source asset/reference path"
);
expect(
  count(/\+surfaceparm nolightmap/g) === 0,
  "Broad nolightmap policy was added"
);
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
expect(fs.existsSync(scriptPath), "Map script is missing");
expect(fs.existsSync(layoutPath), "Authored layout plan is missing");
expect(fs.existsSync(bspPath), "Compiled BSP is missing");


const result = {
  revision: report.revision,
  mapBytes: Buffer.byteLength(map),
  bspBytes: fs.existsSync(bspPath) ? fs.statSync(bspPath).size : 0,
  blueprint: {
    reconstructedSolids: blueprint.source.reconstructedSolids,
    failedSolids: blueprint.source.failedSolids,
    connectedWalkCells: blueprint.walkGrid.connectedNodes,
    connectedRouteEdges: blueprint.walkGrid.connectedEdges,
    unmatchedSpawns: blueprint.walkGrid.unmatchedSpawns.length,
    sha256: blueprintHash,
  },
  geometry: report.geometry,
  customMaterials: [...customMaterials].sort(),
  spawnCounts: report.spawns,
  pointLights: report.pointLights,
  failures,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (failures.length) process.exitCode = 1;
