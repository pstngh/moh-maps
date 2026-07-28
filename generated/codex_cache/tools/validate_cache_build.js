const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_cache.map");
const reportPath = path.join(root, "codex_cache-conversion-report.json");
const textureRoot = path.join(root, "main", "textures");
const shaderPath = path.join(root, "main", "scripts", "codex_cache.shader");

const map = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const shader = fs.readFileSync(shaderPath, "utf8");
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
    failures.push("Map has a closing brace before its matching opening brace");
    break;
  }
}
expect(braceDepth === 0, `Map brace depth ends at ${braceDepth}, expected 0`);

const customMaterials = new Set(
  [...map.matchAll(/\s(codex_cache\/[a-z0-9_]+)\s/g)].map(
    (match) => match[1]
  )
);
for (const material of customMaterials) {
  const imagePath = path.join(textureRoot, `${material}.tga`);
  expect(fs.existsSync(imagePath), `Missing custom image: ${imagePath}`);
}

for (const shaderName of [
  "textures/codex_cache/chainlink",
  "textures/codex_cache/glass",
  "textures/codex_cache/window_backing",
]) {
  expect(shader.includes(shaderName), `Missing shader definition: ${shaderName}`);
}

expect(count(/"classname" "worldspawn"/g) === 1, "Expected one worldspawn");
expect(
  count(/"classname" "func_rotatingdoor"/g) === 1,
  "Expected one measured rotating door"
);
expect(
  count(/"classname" "info_player_axis"/g) === 20,
  "Expected 20 Axis spawns"
);
expect(
  count(/"classname" "info_player_allied"/g) === 20,
  "Expected 20 Allied spawns"
);
expect(
  count(/"classname" "info_player_deathmatch"/g) === 24,
  "Expected 24 neutral DM spawns"
);
expect(
  !/materials\/|models\/(props|newcache)\//i.test(map),
  "Generated map contains a raw Source asset path"
);
expect(report.stats.invalid === 0, "Conversion report contains invalid brushes");
expect(
  report.stats.rotatingDoors === 1,
  "Conversion report did not retain the measured door"
);
expect(
  report.propPolicy === "omit-unverified",
  "Unverified Source prop omission policy changed"
);
expect(
  report.compileBudgetMode === false,
  "Diagnostic compile-budget mode must not be used for the release map"
);
expect(
  report.stats.unverifiedPropsOmitted >= 2500,
  "Too few playable Source props were audited as omitted"
);
expect(
  report.worldBrushes >= 2000 && report.worldBrushes <= 12000,
  "Playable-cluster brush count is outside the audited safety range"
);
expect(
  report.stats.skyboxSkipped >= 1000,
  "Distant Source clusters are no longer being excluded"
);
expect(
  report.stats.sourceLights < report.stats.sourceLightCandidates,
  "Source fixture clustering is no longer reducing overlapping lights"
);
expect(
  count(/\+surfaceparm nolightmap/g) === 0,
  "Broad nolightmap policy was re-enabled"
);

const result = {
  mapBytes: Buffer.byteLength(map),
  worldBrushes: report.worldBrushes,
  entities: report.entities,
  customMaterials: [...customMaterials].sort(),
  omittedUnverifiedProps: report.stats.unverifiedPropsOmitted,
  excludedDistantBrushes: report.stats.skyboxSkipped,
  sourceLights: report.stats.sourceLights,
  sourceLightCandidates: report.stats.sourceLightCandidates,
  noLightmapSides: count(/\+surfaceparm nolightmap/g),
  rotatingDoors: report.stats.rotatingDoors,
  spawnCounts: {
    axis: 20,
    allied: 20,
    neutral: 24,
  },
  failures,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (failures.length) process.exitCode = 1;
