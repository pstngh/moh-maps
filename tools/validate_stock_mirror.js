"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { mirrorMapText } = require("./mirror_stock_map.js");

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    assert(argv[index]?.startsWith("--") && argv[index + 1] !== undefined, `Invalid arguments near ${argv[index] || "end"}`);
    values[argv[index].slice(2)] = argv[index + 1];
  }
  return values;
}

function count(text, expression) {
  return [...text.matchAll(expression)].length;
}

function classCounts(text) {
  const result = {};
  for (const match of text.matchAll(/^"classname" "([^"]+)"\s*$/gm)) {
    result[match[1]] = (result[match[1]] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b)));
}

function entityKeyCounts(text) {
  const result = {};
  for (const match of text.matchAll(/^"([^"]+)" "([^"]*)"\s*$/gm)) {
    result[match[1]] = (result[match[1]] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b)));
}

function preservedEntityKeyValueCounts(text) {
  const transformedKeys = new Set(["origin", "angle", "angles", "sundirection", "message"]);
  const result = {};
  for (const match of text.matchAll(/^"([^"]+)" "([^"]*)"\s*$/gm)) {
    if (transformedKeys.has(match[1])) continue;
    const identity = `${match[1]}\u0000${match[2]}`;
    result[identity] = (result[identity] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b)));
}
function vectorKeys(text, key) {
  const expression = new RegExp(`^"${key}" "([-+0-9.eE]+) ([-+0-9.eE]+) ([-+0-9.eE]+)"\\s*$`, "gm");
  return [...text.matchAll(expression)].map((match) => match.slice(1, 4).map(Number));
}

function scalarKeys(text, key) {
  const expression = new RegExp(`^"${key}" "([-+0-9.eE]+)"\\s*$`, "gm");
  return [...text.matchAll(expression)].map((match) => Number(match[1]));
}

function nearlyEqual(a, b) {
  return Math.abs(a - b) <= 0.00002;
}

function main() {
  const args = parseArguments(process.argv.slice(2));
  assert(args["output-root"], "Missing --output-root");
  const outputRoot = path.resolve(args["output-root"]);
  const configPath = path.join(outputRoot, "mirror-config.json");
  assert(fs.existsSync(configPath), `Missing config: ${configPath}`);
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const repositoryRoot = path.resolve(__dirname, "..");
  const sourcePath = path.join(repositoryRoot, config.sourceMap);
  const gameDirectory = config.gameDirectory;
  const mapRoot = path.join(outputRoot, "main", "maps", gameDirectory);
  const mapPath = path.join(mapRoot, `${config.mapName}.map`);
  const scriptPath = path.join(mapRoot, `${config.mapName}.scr`);
  const precachePath = path.join(mapRoot, `${config.mapName}_precache.scr`);
  const reportPath = path.join(outputRoot, `${config.mapName}-mirror-report.json`);
  for (const required of [sourcePath, mapPath, scriptPath, precachePath, reportPath]) {
    assert(fs.existsSync(required) && fs.statSync(required).isFile(), `Missing mirror input: ${required}`);
  }

  const source = fs.readFileSync(sourcePath, "utf8");
  const mirrored = fs.readFileSync(mapPath, "utf8");
  const script = fs.readFileSync(scriptPath, "utf8");
  const precache = fs.readFileSync(precachePath, "utf8");
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  assert(report.schemaVersion === 1, "Unexpected mirror-report schema");
  assert(report.mapName === config.mapName, "Mirror-report map name mismatch");
  assert(report.sourceSha256 === sha256(source), "Source MAP hash mismatch");
  assert(report.output.sha256 === sha256(mirrored), "Mirrored MAP hash mismatch");
  assert(report.output.bytes === Buffer.byteLength(mirrored), "Mirrored MAP byte count mismatch");

  let balance = 0;
  for (const character of mirrored) {
    if (character === "{") balance += 1;
    else if (character === "}") balance -= 1;
    assert(balance >= 0, "Mirrored MAP closes a brace before it opens one");
  }
  assert(balance === 0, `Mirrored MAP brace imbalance: ${balance}`);
  assert(JSON.stringify(classCounts(source)) === JSON.stringify(classCounts(mirrored)), "Entity classname counts changed");
  assert(JSON.stringify(entityKeyCounts(source)) === JSON.stringify(entityKeyCounts(mirrored)), "Entity key counts changed");
  assert(JSON.stringify(preservedEntityKeyValueCounts(source)) === JSON.stringify(preservedEntityKeyValueCounts(mirrored)), "A preserved entity key/value changed");
  assert(count(source, /\bpatchDef2\b/g) === count(mirrored, /\bpatchDef2\b/g), "Patch count changed");
  assert(count(source, /\bterrainDef\b/g) === count(mirrored, /\bterrainDef\b/g), "Terrain count changed");
  assert(count(source, /^\/\/ brush \d+\s*$/gm) === count(mirrored, /^\/\/ brush \d+\s*$/gm), "Primitive comment count changed");
  assert(count(source, /^\/\/ entity \d+\s*$/gm) === count(mirrored, /^\/\/ entity \d+\s*$/gm), "Entity comment count changed");

  const sourceOrigins = vectorKeys(source, "origin");
  const mirrorOrigins = vectorKeys(mirrored, "origin");
  assert(sourceOrigins.length === mirrorOrigins.length, "Origin count changed");
  sourceOrigins.forEach((origin, index) => {
    const actual = mirrorOrigins[index];
    assert(nearlyEqual(actual[0], -origin[0]) && nearlyEqual(actual[1], origin[1]) && nearlyEqual(actual[2], origin[2]), `Origin ${index} was not reflected exactly`);
  });

  const sourceAngles = scalarKeys(source, "angle");
  const mirrorAngles = scalarKeys(mirrored, "angle");
  assert(sourceAngles.length === mirrorAngles.length, "Angle count changed");
  sourceAngles.forEach((angle, index) => {
    const expected = angle === -1 || angle === -2 ? angle : 180 - angle;
    assert(nearlyEqual(mirrorAngles[index], expected), `Yaw angle ${index} was not reflected exactly`);
  });

  const sourceVectors = vectorKeys(source, "angles");
  const mirrorVectors = vectorKeys(mirrored, "angles");
  assert(sourceVectors.length === mirrorVectors.length, "Angles-vector count changed");
  sourceVectors.forEach((angles, index) => {
    const actual = mirrorVectors[index];
    assert(nearlyEqual(actual[0], angles[0]) && nearlyEqual(actual[1], 180 - angles[1]) && nearlyEqual(actual[2], -angles[2]), `Angles vector ${index} was not reflected exactly`);
  });
  const sourceSunDirections = vectorKeys(source, "sundirection");
  const mirrorSunDirections = vectorKeys(mirrored, "sundirection");
  assert(sourceSunDirections.length === mirrorSunDirections.length, "Sun-direction count changed");
  sourceSunDirections.forEach((direction, index) => {
    const actual = mirrorSunDirections[index];
    assert(nearlyEqual(actual[0], 180 - direction[0]) && nearlyEqual(actual[1], direction[1]) && nearlyEqual(actual[2], -direction[2]), `Sun direction ${index} was not reflected exactly`);
  });

  const first = mirrorMapText(source, null).text;
  const second = mirrorMapText(first, null).text;
  const third = mirrorMapText(second, null).text;
  assert(first === third, "Mirror transform is not a stable involution after canonicalization");
  assert(classCounts(second).worldspawn === 1, "Double-reflected MAP lost worldspawn");

  const originalDirectory = gameDirectory === "dm" ? "DM" : "obj";
  assert(script.includes(`exec maps/${originalDirectory}/${config.originalMap}.scr`), "Script does not delegate to the retail map script");
  assert(precache.includes(`exec maps/${originalDirectory}/${config.originalMap}_precache.scr`), "Precache does not delegate to the retail map precache");
  assert(!script.includes("level waittill"), "Wrapper unexpectedly contains copied retail gameplay script content");

  const result = {
    schemaVersion: 1,
    mapName: config.mapName,
    sourceSha256: report.sourceSha256,
    mapBytes: Buffer.byteLength(mirrored),
    mapSha256: report.output.sha256,
    classCounts: classCounts(mirrored),
    transformed: report.transformed,
    preservedEntityKeyValueMultiset: true,
    reflectedSunDirections: true,
    stableInvolution: true,
    retailScriptWrapper: true,
  };
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main();
