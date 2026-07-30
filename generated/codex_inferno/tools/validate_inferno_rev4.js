const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_inferno.map");
const bspPath = path.join(root, "main", "maps", "dm", "codex_inferno.bsp");
const scriptPath = path.join(root, "main", "maps", "dm", "codex_inferno.scr");
const reportPath = path.join(root, "codex_inferno-conversion-report.json");
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
expect(braceDepth === 0, `Map brace depth ends at ${braceDepth}`);

const customMaterials = new Set(
  [...map.matchAll(/\s(codex_inferno\/[a-z0-9_]+)\s/g)].map(
    (match) => match[1]
  )
);
for (const material of customMaterials) {
  const imagePath = path.join(textureRoot, `${material}.tga`);
  expect(fs.existsSync(imagePath), `Missing custom image: ${imagePath}`);
}

expect(count(/"classname" "worldspawn"/g) === 1, "Expected one worldspawn");
expect(
  count(/"classname" "func_rotatingdoor"/g) === 1,
  "Expected the one verified Source rotating door"
);
expect(count(/"classname" "info_player_axis"/g) === 20, "Expected 20 Axis spawns");
expect(
  count(/"classname" "info_player_allied"/g) === 20,
  "Expected 20 Allied spawns"
);
expect(
  count(/"classname" "info_player_deathmatch"/g) === 67,
  "Expected all 67 dedicated deathmatch spawns"
);
expect(count(/"classname" "info_player_start"/g) === 1, "Expected one player start");
expect(customMaterials.size >= 12, "Expected at least twelve authored material roles");
expect(
  !/materials\/|models\/(props|hr_|weapons)\//i.test(map),
  "Generated map contains a raw Source asset path"
);
expect(report.revision === 4, "Expected Inferno revision 4");
expect(
  report.construction === "direct-source-brush-conversion",
  "Direct Source brush conversion policy changed"
);
expect(
  report.referenceSha256 ===
    "c37a3d3cb4ea813b0cc1b36205234a9f9ccff258b7d69fba8ca5c448628505d5",
  "Private reference VMF fingerprint changed"
);
expect(report.stats.invalid === 0, "Conversion report contains invalid brushes");
expect(report.stats.rotatingDoors === 1, "Verified rotating door was not translated");
expect(
  report.propPolicy === "omit-unverified-source-models",
  "Unverified Source prop omission policy changed"
);
expect(
  report.compileBudgetMode === false,
  "Diagnostic compile-budget mode must not become the release map"
);
expect(
  report.stats.unverifiedPropsOmitted >= 6000,
  "Too few playable Source props were audited as omitted"
);
expect(
  report.worldBrushes >= 5200 && report.worldBrushes <= 7000,
  "Direct playable brush count left the audited range"
);
expect(
  report.stats.converted >= 5200,
  "Too few measured Source brush solids were preserved"
);
expect(
  report.stats.skyboxSkipped >= 500,
  "Distant Source skybox cluster is no longer excluded"
);
expect(
  report.stats.displacementPlanarized >= 1900,
  "Planar displacement debt is no longer fully audited"
);
expect(
  report.stats.sourceLights < report.stats.sourceLightCandidates,
  "Source fixture clustering is no longer reducing overlapping lights"
);
expect(count(/\+surfaceparm nolightmap/g) === 0, "Broad nolightmap policy was enabled");
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
expect(fs.existsSync(bspPath), "Compiled BSP is missing");

const result = {
  revision: report.revision,
  construction: report.construction,
  mapBytes: Buffer.byteLength(map),
  bspBytes: fs.existsSync(bspPath) ? fs.statSync(bspPath).size : 0,
  worldBrushes: report.worldBrushes,
  convertedSourceSolids: report.stats.converted,
  invalidSourceSolids: report.stats.invalid,
  customMaterials: [...customMaterials].sort(),
  omittedUnverifiedProps: report.stats.unverifiedPropsOmitted,
  excludedSkyboxBrushes: report.stats.skyboxSkipped,
  planarizedDisplacementSides: report.stats.displacementPlanarized,
  sourceLights: report.stats.sourceLights,
  sourceLightCandidates: report.stats.sourceLightCandidates,
  rotatingDoors: report.stats.rotatingDoors,
  spawnCounts: {
    axis: 20,
    allied: 20,
    neutral: 67,
  },
  failures,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (failures.length) process.exitCode = 1;
