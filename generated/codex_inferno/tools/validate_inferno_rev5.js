const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_inferno.map");
const bspPath = path.join(root, "main", "maps", "dm", "codex_inferno.bsp");
const scriptPath = path.join(root, "main", "maps", "dm", "codex_inferno.scr");
const reportPath = path.join(root, "codex_inferno-conversion-report.json");
const boundsPath = path.join(root, "inferno-model-bounds.json");
const textureRoot = path.join(root, "main", "textures");

const map = fs.readFileSync(mapPath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const boundsManifest = JSON.parse(fs.readFileSync(boundsPath, "utf8"));
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
expect(
  !map.includes("\\n"),
  "Map contains a literal escaped newline sequence instead of a line break"
);

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
expect(report.revision === 5, "Expected Inferno revision 5");
expect(
  report.construction === "direct-source-brush-conversion-with-measured-prop-fill",
  "Direct brush plus measured prop-fill policy changed"
);
expect(
  report.referenceSha256 ===
    "c37a3d3cb4ea813b0cc1b36205234a9f9ccff258b7d69fba8ca5c448628505d5",
  "Private reference VMF fingerprint changed"
);
expect(report.stats.invalid === 0, "Conversion report contains invalid brushes");
expect(report.stats.rotatingDoors === 1, "Verified rotating door was not translated");
expect(
  report.propPolicy === "measured-original-substitutes-omit-remainder",
  "Measured prop substitution policy changed"
);
expect(
  report.compileBudgetMode === false,
  "Diagnostic compile-budget mode must not become the release map"
);
expect(
  report.modelBoundsRecords === 308,
  "Verified Source model-bounds manifest changed"
);
expect(
  boundsManifest.parsedHeaders === 308 && boundsManifest.models.length === 308,
  "Model-bounds manifest no longer contains all parsed headers"
);
expect(
  boundsManifest.source.vmf.sha256 ===
    "c37a3d3cb4ea813b0cc1b36205234a9f9ccff258b7d69fba8ca5c448628505d5" &&
    boundsManifest.source.bsp.sha256 ===
      "4c29b4b6ae35ce1dca3f56439876014e09baecdc25ad0146a865da6072fc60e6" &&
    boundsManifest.source.vpkDirectory.sha256 ===
      "a9ffaa07380d70e1b4362007cf50351c25844905e200c0e6c20c7d10cfe1364a",
  "Private reference fingerprint set changed"
);
expect(
  report.stats.sourcePropCandidates === 6200 &&
    report.stats.sourcePropsWithBounds === 6200,
  "Playable Source prop audit no longer resolves every candidate"
);
expect(
  report.stats.sourcePropsSubstituted >= 1100 &&
    report.stats.unverifiedPropsOmitted <= 5100,
  "Measured prop-fill coverage regressed"
);
expect(
  report.propSubstitutions.length === report.stats.sourcePropsSubstituted,
  "Per-instance prop substitution records are incomplete"
);
expect(
  report.propSubstitutions.reduce((sum, record) => sum + record.brushes, 0) ===
    report.stats.propSubstituteBrushes,
  "Per-instance prop brush counts do not match the aggregate"
);const manifestModels = new Set(
  boundsManifest.models.map((record) => record.model.toLowerCase())
);
const substitutionKeys = new Set();
let zeroBrushSubstitutions = 0;
for (const record of report.propSubstitutions) {
  expect(
    manifestModels.has(record.model),
    `Substitute model is absent from the bounds manifest: ${record.model}`
  );
  expect(
    record.origin.length === 3 &&
      record.angles.length === 3 &&
      [...record.origin, ...record.angles, record.scale].every(Number.isFinite),
    `Substitute transform is invalid: ${record.model}`
  );
  expect(
    record.origin[0] >= -2400 &&
      record.origin[0] <= 3200 &&
      record.origin[1] >= -1350 &&
      record.origin[1] <= 4200 &&
      record.origin[2] >= -320 &&
      record.origin[2] <= 960,
    `Substitute lies outside the audited playable bounds: ${record.model}`
  );
  expect(
    record.scale > 0 &&
      record.scale <= 4 &&
      Number.isInteger(record.brushes) &&
      record.brushes >= 0,
    `Substitute scale or brush count is invalid: ${record.model}`
  );
  const key = JSON.stringify([
    record.model,
    record.origin,
    record.angles,
    record.scale,
  ]);
  expect(!substitutionKeys.has(key), `Duplicate substitute transform: ${key}`);
  substitutionKeys.add(key);
  if (record.brushes === 0) zeroBrushSubstitutions++;
}
expect(
  zeroBrushSubstitutions === report.stats.collapsedLandmarkParts,
  "Zero-brush substitute records do not match collapsed landmark parts"
);
for (const [field, minimum] of Object.entries({
  facadeWindows: 200,
  facadeShutters: 80,
  facadeDoors: 90,
  facadeFrames: 60,
  measuredArchFrames: 40,
  roofSurfaceProps: 60,
  measuredPillars: 190,
  measuredChimneys: 60,
  measuredWoodSupports: 180,
  measuredBalconySupports: 40,
  measuredCoverProps: 80,
  landmarkAssemblies: 4,
})) {
  expect(report.stats[field] >= minimum, `Measured prop class regressed: ${field}`);
}
expect(
  report.worldBrushes >= 6800 && report.worldBrushes <= 7800,
  "Direct plus prop-fill brush count left the audited range"
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
  measuredPropCandidates: report.stats.sourcePropCandidates,
  measuredPropSubstitutes: report.stats.sourcePropsSubstituted,
  propSubstituteBrushes: report.stats.propSubstituteBrushes,
  omittedUnverifiedProps: report.stats.unverifiedPropsOmitted,
  measuredPropClasses: {
    windows: report.stats.facadeWindows,
    shutters: report.stats.facadeShutters,
    doors: report.stats.facadeDoors,
    frames: report.stats.facadeFrames,
    arches: report.stats.measuredArchFrames,
    roofSurfaces: report.stats.roofSurfaceProps,
    pillars: report.stats.measuredPillars,
    chimneys: report.stats.measuredChimneys,
    woodSupports: report.stats.measuredWoodSupports,
    balconySupports: report.stats.measuredBalconySupports,
    cover: report.stats.measuredCoverProps,
    landmarks: report.stats.landmarkAssemblies,
  },
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
