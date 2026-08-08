"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const root = path.resolve(process.argv[2] || path.join(__dirname, ".."));
const mapName = process.argv[3] || "codex_reactor";
if (!/^[A-Za-z0-9_]+$/.test(mapName)) throw new Error("Invalid map name");

const mapRoot = path.join(root, "main", "maps", "dm");
const mapPath = path.join(mapRoot, `${mapName}.map`);
const scriptPath = path.join(mapRoot, `${mapName}.scr`);
const precachePath = path.join(mapRoot, `${mapName}_precache.scr`);
const reportPath = path.join(root, `${mapName}-design-report.json`);
for (const required of [mapPath, scriptPath, precachePath, reportPath]) {
  if (!fs.existsSync(required) || !fs.statSync(required).isFile()) {
    throw new Error(`Missing generated input: ${required}`);
  }
}

const mapText = fs.readFileSync(mapPath, "utf8");
const scriptText = fs.readFileSync(scriptPath, "utf8");
const precacheText = fs.readFileSync(precachePath, "utf8");
const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));

function count(haystack, expression) {
  return [...haystack.matchAll(expression)].length;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(report.schemaVersion === 1, "Unexpected design-report schema");
assert(report.mapName === mapName, "Design-report map name mismatch");
assert(report.originalDesign === true, "Map must be identified as an original design");
assert(!mapText.includes("\\n"), "MAP contains literal escaped newline characters");

let braceBalance = 0;
for (const character of mapText) {
  if (character === "{") braceBalance += 1;
  else if (character === "}") braceBalance -= 1;
  assert(braceBalance >= 0, "MAP closes a brace before it opens one");
}
assert(braceBalance === 0, `MAP brace imbalance: ${braceBalance}`);

const actualHash = crypto.createHash("sha256").update(mapText).digest("hex");
assert(actualHash === report.map.sha256, "MAP SHA-256 differs from design report");
assert(Buffer.byteLength(mapText) === report.map.bytes, "MAP size differs from design report");

const expectedEntities = {
  info_player_deathmatch: report.entities.neutralSpawns,
  info_player_allied: report.entities.alliedSpawns,
  info_player_axis: report.entities.axisSpawns,
  info_player_start: report.entities.spectatorStarts,
  light: report.entities.lights,
};
for (const [classname, expected] of Object.entries(expectedEntities)) {
  const actual = count(mapText, new RegExp(`"classname" "${classname}"`, "g"));
  assert(actual === expected, `${classname}: expected ${expected}, found ${actual}`);
}
assert(count(mapText, /"classname" "func_(?:rotating)?door"/g) === 0, "Bot-critical moving doors are forbidden");

const brushComments = [...mapText.matchAll(/^\/\/ brush (\d+) ([a-z0-9_]+)$/gm)];
assert(
  brushComments.length === report.geometry.worldBrushes,
  `Expected ${report.geometry.worldBrushes} brush comments, found ${brushComments.length}`,
);
brushComments.forEach((match, index) => {
  assert(Number(match[1]) === index, `Brush comment index discontinuity at ${index}`);
});
assert(report.geometry.worldBrushes >= 100, "Map is below the intended architectural/detail brush floor");
assert(report.geometry.worldBrushes < 500, "Map exceeds the original-layout brush budget");
assert(report.geometry.brushesByRole.moving_door === undefined, "Design report contains a moving-door role");

const graph = report.topology.routeGraph;
assert(Array.isArray(graph.zones) && graph.zones.length === 8, "Expected eight named combat zones");
assert(Array.isArray(graph.edges) && graph.edges.length >= 16, "Route graph has too few connections");
const adjacency = new Map(graph.zones.map((zone) => [zone, new Set()]));
for (const edge of graph.edges) {
  assert(Array.isArray(edge) && edge.length === 4, `Malformed route edge: ${JSON.stringify(edge)}`);
  const [from, to, width] = edge;
  assert(adjacency.has(from) && adjacency.has(to), `Route edge names unknown zone: ${from} -> ${to}`);
  assert(Number.isFinite(width) && width >= 192, `Route is too narrow: ${from} -> ${to} (${width})`);
  adjacency.get(from).add(to);
  adjacency.get(to).add(from);
}
const visited = new Set([graph.zones[0]]);
const queue = [graph.zones[0]];
while (queue.length) {
  const zone = queue.shift();
  for (const neighbor of adjacency.get(zone)) {
    if (!visited.has(neighbor)) {
      visited.add(neighbor);
      queue.push(neighbor);
    }
  }
}
assert(visited.size === graph.zones.length, `Disconnected route graph: ${[...adjacency.keys()].filter((zone) => !visited.has(zone)).join(", ")}`);
assert(report.topology.minimumPrimaryRouteWidth >= 192, "Reported route-width floor is too narrow");
assert(report.topology.movingDoors === 0, "Design report must record zero moving doors");
for (const stair of report.topology.stairSpecs) {
  assert(stair.width >= 224, "Stair width is below bot-safe target");
  assert(stair.rise <= 16, "Stair rise exceeds bot-safe target");
  assert(stair.tread >= 32, "Stair tread is below bot-safe target");
}

assert(report.spawnClearance.passed === true, "Generator spawn-clearance gate did not pass");
assert(report.spawnClearance.collisions.length === 0, "Generator reported a spawn collision");
assert(report.entities.neutralSpawns === 20, "Expected 20 neutral DM spawns");
assert(report.entities.alliedSpawns === 10, "Expected 10 Allied spawns");
assert(report.entities.axisSpawns === 10, "Expected 10 Axis spawns");
for (const origins of Object.values(report.spawnOrigins)) {
  for (const origin of origins) {
    const originText = `"origin" "${origin.join(" ")}"`;
    assert(mapText.includes(originText), `Spawn origin is missing from MAP: ${origin.join(" ")}`);
  }
}

assert(scriptText.includes("exec global/DMprecache.scr"), "Map script does not execute DMprecache");
assert(scriptText.includes(`level.script = maps/dm/${mapName}.scr`), "Map script path mismatch");
for (const line of [
  "exec global/DMprecache.scr",
  "cache models/items/dm_50_healthbox.tik",
  "cache models/fx/bazookaexplosion_dm.tik",
]) {
  const escaped = line.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert(count(precacheText, new RegExp(escaped, "g")) === 1, `Expected one precache line: ${line}`);
}

const generatedDirectory = path.dirname(root);
const sharedTextureRoot = path.join(generatedDirectory, "codex_nuke", "main", "textures", "codex_nuke");
const referencedCustom = new Set(
  [...mapText.matchAll(/\s(codex_nuke\/[a-z0-9_]+)\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+\d+\s+\d+\s+\d+/g)].map(
    (match) => match[1],
  ),
);
const expectedCustom = new Set(
  report.materials.bundledOriginalTextures.map((name) => `codex_nuke/${path.basename(name, ".tga")}`),
);
for (const material of referencedCustom) {
  assert(expectedCustom.has(material), `Referenced custom material is not package-listed: ${material}`);
}
for (const material of expectedCustom) {
  assert(referencedCustom.has(material), `Package-listed custom material is unused: ${material}`);
  const imagePath = path.join(sharedTextureRoot, `${material.split("/")[1]}.tga`);
  assert(fs.existsSync(imagePath), `Missing project-owned texture: ${imagePath}`);
  const bytes = fs.statSync(imagePath).size;
  assert(bytes === 786476 || bytes === 1048620, `Unexpected TGA size for ${imagePath}: ${bytes}`);
}

const result = {
  mapName,
  mapBytes: Buffer.byteLength(mapText),
  mapSha256: actualHash,
  worldBrushes: report.geometry.worldBrushes,
  entities: report.entities,
  routeZones: graph.zones.length,
  routeEdges: graph.edges.length,
  minimumRouteWidth: report.topology.minimumPrimaryRouteWidth,
  spawnClearance: report.spawnClearance,
  customMaterials: [...referencedCustom].sort(),
  bundledTextures: report.materials.bundledOriginalTextures.length,
};
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);