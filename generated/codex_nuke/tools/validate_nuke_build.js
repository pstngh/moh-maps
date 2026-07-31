const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_nuke.map");
const reportPath = path.join(root, "codex_nuke-conversion-report.json");
const manifestPath = path.join(root, "fidelity-manifest.json");
const textureRoot = path.join(root, "main", "textures");
const shaderPath = path.join(root, "main", "scripts", "codex_nuke.shader");

const map = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
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
  [...map.matchAll(/\s(codex_nuke\/[a-z0-9_]+)\s/g)].map(
    (match) => match[1]
  )
);
for (const material of customMaterials) {
  const imagePath = path.join(textureRoot, `${material}.tga`);
  expect(fs.existsSync(imagePath), `Missing custom image: ${imagePath}`);
}

for (const shaderName of [
  "textures/codex_nuke/chainlink",
  "textures/codex_nuke/glass",
  "textures/codex_nuke/window_backing",
  "textures/codex_nuke/foliage",
]) {
  expect(shader.includes(shaderName), `Missing shader definition: ${shaderName}`);
}
expect(
  !/q3map_lightmapSampleSize/i.test(shader),
  "Unsupported q3map_lightmapSampleSize directive was reintroduced"
);
for (const [shaderName, tint] of [
  ["chainlink", "0.62 0.62 0.62"],
  ["foliage", "0.68 0.68 0.68"],
]) {
  const pattern = new RegExp(
    `textures/codex_nuke/${shaderName}\\s*\\{[\\s\\S]*?rgbGen\\s+const\\s+\\(\\s*${tint.replaceAll(" ", "\\s+")}\\s*\\)`
  );
  expect(pattern.test(shader), `Missing bounded alpha-detail tint: ${shaderName}`);
}
expect(
  !/surfaceparm\s+nolightmap/i.test(
    shader
      .replace(/[\s\S]*?textures\/codex_nuke\/window_backing\s*\{([\s\S]*?)\n\}/, "")
  ),
  "Unexpected shader-level nolightmap outside the proven window backing"
);

expect(count(/"classname" "worldspawn"/g) === 1, "Expected one worldspawn");
expect(
  count(/"classname" "func_rotatingdoor"/g) === 4,
  "Expected four generated rotating doors"
);
expect(
  count(/"classname" "info_player_axis"/g) === 16,
  "Expected 16 Axis spawns"
);
expect(
  count(/"classname" "info_player_allied"/g) === 16,
  "Expected 16 Allied spawns"
);
expect(
  count(/"classname" "info_player_deathmatch"/g) === 32,
  "Expected 32 neutral DM spawns"
);
expect(
  !/materials\/|models\/props\/de_nuke/i.test(map),
  "Generated map contains a raw Source asset path"
);
expect(report.stats.invalid === 0, "Conversion report contains invalid brushes");
expect(
  report.stats.rotatingDoors === 4,
  "Conversion report did not retain all four doors"
);
expect(
  report.stats.embeddedAutocombinesReconstructed === 0,
  "Unsafe embedded-autocombine inference was re-enabled"
);
expect(
  report.stats.embeddedAutocombinesOmitted === 710,
  "Embedded-autocombine debt changed; re-audit before accepting"
);
expect(
  report.stats.autocombineFillBrushes === 0,
  "Unsafe autocombine fill brushes were generated"
);
expect(
  report.stats.maximumPlanarUnderlayExpansion >= 100,
  "Terrain underlay no longer covers the measured displacement excursion"
);
expect(
  report.stats.sourceLights < report.stats.sourceLightCandidates,
  "Source fixture clustering is no longer reducing overlapping lights"
);
expect(
  manifest.counts.instances === 4687 && manifest.counts.measuredInstances === 4687,
  "Playable Source prop manifest changed; re-audit the Nuke fidelity layer"
);
expect(
  report.stats.fidelityInstances >= 1900,
  "Fidelity reconstruction no longer handles the expected prop inventory"
);
expect(
  report.stats.fidelityBrushes >= 2800,
  "Fidelity reconstruction brush count regressed"
);
expect(
  report.stats.unsupportedPropsSkipped <= 1600,
  "Too many understood Nuke props were dropped"
);
for (const [family, minimum] of Object.entries({
  vehicle: 17,
  truck: 6,
  forklift: 8,
  cargo_crane: 8,
  chainlink: 230,
  structural_column: 130,
  control_room_display: 55,
  furniture: 130,
  a_site_silo: 1,
  reactor_head: 1,
  upper_crane: 1,
  core_crane: 1,
})) {
  expect(
    (report.stats.fidelityFamilies[family] || 0) >= minimum,
    `Fidelity family ${family} fell below ${minimum}`
  );
}
const noLightmapFaceLines = map
  .split(/\r?\n/)
  .filter((line) => line.includes("+surfaceparm nolightmap"));
expect(
  noLightmapFaceLines.length === 4320,
  `Expected 4,320 targeted alpha-detail nolightmap faces, got ${noLightmapFaceLines.length}`
);
for (const line of noLightmapFaceLines) {
  expect(
    /\s(?:codex_nuke\/chainlink|codex_nuke\/foliage)\s/.test(line),
    `Non-alpha material received nolightmap: ${line}`
  );
}
expect(
  report.stats.alphaDetailNoLightmapFaces === noLightmapFaceLines.length,
  "Report alpha-detail lightmap count does not match the generated MAP"
);

const result = {
  mapBytes: Buffer.byteLength(map),
  worldBrushes: report.worldBrushes,
  entities: report.entities,
  customMaterials: [...customMaterials].sort(),
  reconstructedAutocombines: report.stats.embeddedAutocombinesReconstructed,
  omittedAutocombines: report.stats.embeddedAutocombinesOmitted,
  autocombineFillBrushes: report.stats.autocombineFillBrushes,
  sourceLights: report.stats.sourceLights,
  sourceLightCandidates: report.stats.sourceLightCandidates,
  fidelityInstances: report.stats.fidelityInstances,
  fidelityBrushes: report.stats.fidelityBrushes,
  fidelityFamilies: report.stats.fidelityFamilies,
  unsupportedPropsSkipped: report.stats.unsupportedPropsSkipped,
  noLightmapSides: noLightmapFaceLines.length,
  rotatingDoors: report.stats.rotatingDoors,
  spawnCounts: {
    axis: 16,
    allied: 16,
    neutral: 32,
  },
  failures,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (failures.length) process.exitCode = 1;
