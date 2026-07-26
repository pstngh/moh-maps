const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const mapPath = path.join(root, "main", "maps", "dm", "codex_nuke.map");
const reportPath = path.join(root, "codex_nuke-conversion-report.json");
const textureRoot = path.join(root, "main", "textures");
const shaderPath = path.join(root, "main", "scripts", "codex_nuke.shader");

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
  [...map.matchAll(/\s(codex_nuke\/[a-z0-9_]+)\s/g)].map(
    (match) => match[1]
  )
);
for (const material of customMaterials) {
  const imagePath = path.join(textureRoot, `${material}.tga`);
  expect(fs.existsSync(imagePath), `Missing custom image: ${imagePath}`);
}

for (const shaderName of ["textures/codex_nuke/chainlink", "textures/codex_nuke/glass"]) {
  expect(shader.includes(shaderName), `Missing shader definition: ${shaderName}`);
}

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
  report.stats.embeddedAutocombinesOmitted === 710,
  "Embedded-autocombine debt changed; re-audit before accepting"
);

const result = {
  mapBytes: Buffer.byteLength(map),
  worldBrushes: report.worldBrushes,
  entities: report.entities,
  customMaterials: [...customMaterials].sort(),
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

