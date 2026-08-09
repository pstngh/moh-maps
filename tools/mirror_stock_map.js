"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const NUMBER_SOURCE = "[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?";
const FACE_RE = new RegExp(
  `^(\\s*)\\(\\s*(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s*\\)\\s*` +
    `\\(\\s*(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s*\\)\\s*` +
    `\\(\\s*(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s*\\)(.*)$`,
);
const CONTROL_RE = new RegExp(
  `\\(\\s*(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s+(${NUMBER_SOURCE})\\s*\\)`,
  "g",
);
const VECTOR_KEY_RE = new RegExp(`^(\\s*)"([^"]+)" "(${NUMBER_SOURCE}) (${NUMBER_SOURCE}) (${NUMBER_SOURCE})"(\\s*)$`);
const SCALAR_KEY_RE = new RegExp(`^(\\s*)"([^"]+)" "(${NUMBER_SOURCE})"(\\s*)$`);

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function cleanZero(value) {
  return Object.is(value, -0) || Math.abs(value) < 1e-9 ? 0 : value;
}

function decimalsOf(token) {
  const mantissa = token.replace(/^[+-]/, "").split(/[eE]/)[0];
  const dot = mantissa.indexOf(".");
  return dot < 0 ? 0 : mantissa.length - dot - 1;
}

function formatLike(token, value) {
  value = cleanZero(value);
  if (/[eE]/.test(token)) return value.toExponential(decimalsOf(token)).replace("e+", "e");
  const decimals = decimalsOf(token);
  return decimals ? value.toFixed(decimals) : String(Math.round(value));
}

function negateToken(token) {
  return formatLike(token, -Number(token));
}

function reflectYawToken(token) {
  return formatLike(token, 180 - Number(token));
}

function pointText(x, y, z) {
  return `( ${negateToken(x)} ${y} ${z} )`;
}

function mirrorFace(line) {
  const match = line.match(FACE_RE);
  if (!match) return null;
  const p0 = pointText(match[2], match[3], match[4]);
  const p1 = pointText(match[5], match[6], match[7]);
  const p2 = pointText(match[8], match[9], match[10]);
  // A reflection changes handedness. Swapping points 0 and 2 preserves the
  // original plane/brush inside direction, matching NetRadiant's brush code.
  return `${match[1]}${p2} ${p1} ${p0}${match[11]}`;
}

function mirrorPatchControlLine(line) {
  return line.replace(CONTROL_RE, (_whole, x, y, z, s, t) => `( ${negateToken(x)} ${y} ${z} ${s} ${t} )`);
}

function findNext(lines, from, predicate, label) {
  for (let index = from; index < lines.length; index += 1) {
    if (predicate(lines[index], index)) return index;
  }
  fail(`Could not find ${label} after line ${from + 1}`);
}

function payloadIndexes(lines, openIndex, closeIndex) {
  const result = [];
  for (let index = openIndex + 1; index < closeIndex; index += 1) {
    if (lines[index].trim()) result.push(index);
  }
  return result;
}

function reverseRows(values, width) {
  assert(Number.isInteger(width) && width > 0, `Invalid row width ${width}`);
  assert(values.length % width === 0, `Payload length ${values.length} is not divisible by ${width}`);
  const output = [];
  for (let offset = 0; offset < values.length; offset += width) {
    output.push(...values.slice(offset, offset + width).reverse());
  }
  return output;
}

function swapTerrainTriangleFlags(line) {
  const match = line.match(new RegExp(`^(\\s*)(${NUMBER_SOURCE})(\\s+\\(\\s*)([^)]*)(\\s*\\)\\s+\\(\\s*)([^)]*)(\\s*\\)\\s*)$`));
  assert(match, `Malformed terrain sample: ${line}`);
  return `${match[1]}${match[2]}${match[3]}${match[6]}${match[5]}${match[4]}${match[7]}`;
}

function mirrorMapText(sourceText, displayName) {
  const hadTerminalNewline = /\r?\n$/.test(sourceText);
  const lines = sourceText.replace(/\r\n/g, "\n").split("\n");
  if (lines[lines.length - 1] === "") lines.pop();

  const patchRows = new Map();
  const terrainRows = new Map();
  let patchCount = 0;
  let terrainCount = 0;
  let terrainSamples = 0;
  let terrainTextureControls = 0;

  for (let index = 0; index < lines.length; index += 1) {
    const primitive = lines[index].trim();
    if (primitive === "patchDef2") {
      const headerIndex = findNext(
        lines,
        index + 1,
        (line) => /^\s*\(\s*\d+\s+\d+\s+/.test(line),
        "patch dimensions",
      );
      const dimensionMatch = lines[headerIndex].match(/^\s*\(\s*(\d+)\s+(\d+)\s+/);
      assert(dimensionMatch, `Malformed patch dimensions at line ${headerIndex + 1}`);
      // Legacy MOH patchDef2 serializes row-count first and controls-per-row
      // second (the inverse of the in-memory width/height naming).
      const height = Number(dimensionMatch[1]);
      const width = Number(dimensionMatch[2]);
      const gridOpen = findNext(lines, headerIndex + 1, (line) => line.trim() === "(", "patch grid opening");
      const rowIndexes = [];
      for (let row = gridOpen + 1; row < lines.length && rowIndexes.length < height; row += 1) {
        if (lines[row].trim()) rowIndexes.push(row);
      }
      assert(rowIndexes.length === height, `Patch at line ${index + 1} has ${rowIndexes.length}/${height} rows`);
      const transformed = rowIndexes.map((row) => {
        const matches = [...lines[row].matchAll(CONTROL_RE)];
        assert(matches.length === width, `Patch row ${row + 1} has ${matches.length}/${width} controls`);
        return mirrorPatchControlLine(lines[row]);
      });
      // NetRadiant reverses the control-grid height on a left-handed transform.
      transformed.reverse();
      rowIndexes.forEach((row, rowOffset) => patchRows.set(row, transformed[rowOffset]));
      patchCount += 1;
    } else if (primitive === "terrainDef") {
      const dimensionsIndex = findNext(
        lines,
        index + 1,
        (line) => /^\s*\d+\s+\d+\s+[-+]?\d+\s*$/.test(line),
        "terrain dimensions",
      );
      const dimensions = lines[dimensionsIndex].trim().split(/\s+/).map(Number);
      const [width, height] = dimensions;
      assert(width >= 2 && height >= 2, `Invalid terrain dimensions at line ${dimensionsIndex + 1}`);
      const originIndex = findNext(
        lines,
        dimensionsIndex + 1,
        (line) => new RegExp(`^\\s*${NUMBER_SOURCE}\\s+${NUMBER_SOURCE}\\s+${NUMBER_SOURCE}\\s*$`).test(line),
        "terrain origin",
      );
      const originMatch = lines[originIndex].match(new RegExp(`^(\\s*)(${NUMBER_SOURCE})(\\s+)(${NUMBER_SOURCE})(\\s+)(${NUMBER_SOURCE})(\\s*)$`));
      assert(originMatch, `Malformed terrain origin at line ${originIndex + 1}`);
      const spanX = (width - 1) * 64;
      terrainRows.set(
        originIndex,
        `${originMatch[1]}${formatLike(originMatch[2], -(Number(originMatch[2]) + spanX))}${originMatch[3]}${originMatch[4]}${originMatch[5]}${originMatch[6]}${originMatch[7]}`,
      );

      const textureOpen = findNext(lines, originIndex + 1, (line) => line.trim() === "{", "terrain texture-grid opening");
      const textureClose = findNext(lines, textureOpen + 1, (line) => line.trim() === "}", "terrain texture-grid close");
      const textureIndexes = payloadIndexes(lines, textureOpen, textureClose);
      const textureWidth = (width - 1) / 8 + 1;
      const textureHeight = (height - 1) / 8 + 1;
      assert(Number.isInteger(textureWidth) && Number.isInteger(textureHeight), `Terrain ${width}x${height} is not on the 8-cell grid`);
      assert(textureIndexes.length === textureWidth * textureHeight, `Terrain texture grid has ${textureIndexes.length}/${textureWidth * textureHeight} controls`);
      const mirroredTextureLines = reverseRows(textureIndexes.map((row) => lines[row]), textureWidth);
      textureIndexes.forEach((row, rowOffset) => terrainRows.set(row, mirroredTextureLines[rowOffset]));

      const heightOpen = findNext(lines, textureClose + 1, (line) => line.trim() === "{", "terrain height-grid opening");
      const heightClose = findNext(lines, heightOpen + 1, (line) => line.trim() === "}", "terrain height-grid close");
      const heightIndexes = payloadIndexes(lines, heightOpen, heightClose);
      assert(heightIndexes.length === width * height, `Terrain height grid has ${heightIndexes.length}/${width * height} samples`);
      const mirroredHeightLines = reverseRows(heightIndexes.map((row) => swapTerrainTriangleFlags(lines[row])), width);
      heightIndexes.forEach((row, rowOffset) => terrainRows.set(row, mirroredHeightLines[rowOffset]));
      terrainTextureControls += textureIndexes.length;
      terrainSamples += heightIndexes.length;
      terrainCount += 1;
    }
  }

  let faceCount = 0;
  let originCount = 0;
  let angleCount = 0;
  let anglesCount = 0;
  let sunDirectionCount = 0;
  let messageChanged = false;
  const output = lines.map((line, index) => {
    if (patchRows.has(index)) return patchRows.get(index);
    if (terrainRows.has(index)) return terrainRows.get(index);

    const face = mirrorFace(line);
    if (face !== null) {
      faceCount += 1;
      return face;
    }

    const vector = line.match(VECTOR_KEY_RE);
    if (vector) {
      const [, indent, key, a, b, c, suffix] = vector;
      if (key === "origin") {
        originCount += 1;
        return `${indent}"${key}" "${negateToken(a)} ${b} ${c}"${suffix}`;
      }
      if (key === "angles") {
        anglesCount += 1;
        return `${indent}"${key}" "${a} ${reflectYawToken(b)} ${negateToken(c)}"${suffix}`;
      }
      if (key === "sundirection") {
        sunDirectionCount += 1;
        return `${indent}"${key}" "${reflectYawToken(a)} ${b} ${negateToken(c)}"${suffix}`;
      }
    }

    const scalar = line.match(SCALAR_KEY_RE);
    if (scalar && scalar[2] === "angle") {
      angleCount += 1;
      const value = Number(scalar[3]);
      const mirrored = value === -1 || value === -2 ? scalar[3] : reflectYawToken(scalar[3]);
      return `${scalar[1]}"angle" "${mirrored}"${scalar[4]}`;
    }

    if (!messageChanged && displayName && /^\s*"message"\s+"[^"]*"\s*$/.test(line)) {
      messageChanged = true;
      return `"message" "${displayName.replace(/"/g, "")}"`;
    }
    return line;
  });

  const text = `${output.join("\n")}${hadTerminalNewline ? "\n" : ""}`;
  return {
    text,
    counts: {
      brushFaces: faceCount,
      patches: patchCount,
      terrains: terrainCount,
      terrainSamples,
      terrainTextureControls,
      origins: originCount,
      angles: angleCount,
      angleVectors: anglesCount,
      sunDirections: sunDirectionCount,
    },
  };
}

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    assert(key && key.startsWith("--") && value !== undefined, `Invalid argument sequence near ${key || "end"}`);
    values[key.slice(2)] = value;
  }
  return values;
}

function main() {
  const args = parseArguments(process.argv.slice(2));
  for (const required of ["source", "output-root", "map-name", "game-directory", "original-map", "display-name"]) {
    assert(args[required], `Missing --${required}`);
  }
  assert(/^[A-Za-z0-9_]+$/.test(args["map-name"]), "Map name contains unsafe characters");
  assert(/^(dm|obj)$/.test(args["game-directory"]), "Game directory must be dm or obj");
  assert(/^[A-Za-z0-9_]+$/.test(args["original-map"]), "Original map name contains unsafe characters");

  const sourcePath = path.resolve(args.source);
  const outputRoot = path.resolve(args["output-root"]);
  assert(fs.existsSync(sourcePath) && fs.statSync(sourcePath).isFile(), `Missing source MAP: ${sourcePath}`);
  const sourceText = fs.readFileSync(sourcePath, "utf8");
  const mirrored = mirrorMapText(sourceText, args["display-name"]);
  const gameDirectory = args["game-directory"];
  const mapName = args["map-name"];
  const originalMap = args["original-map"];
  const extraPrecache = args["extra-precache"] ? args["extra-precache"].split(";").filter(Boolean) : [];
  for (const asset of extraPrecache) assert(/^models\/[A-Za-z0-9_./-]+\.tik$/.test(asset), `Unsafe extra precache asset: ${asset}`);
  const originalDirectory = gameDirectory === "dm" ? "DM" : "obj";
  const mapDirectory = path.join(outputRoot, "main", "maps", gameDirectory);
  fs.mkdirSync(mapDirectory, { recursive: true });
  const mapPath = path.join(mapDirectory, `${mapName}.map`);
  const scriptPath = path.join(mapDirectory, `${mapName}.scr`);
  const precachePath = path.join(mapDirectory, `${mapName}_precache.scr`);
  const script = `// Thin wrapper: retail ${originalMap}.scr remains authoritative.\nmain:\n\texec maps/${originalDirectory}/${originalMap}.scr\nend\n`;
  const precache = `// Thin wrapper: retail assets remain in Pak0-Pak6.\nexec maps/${originalDirectory}/${originalMap}_precache.scr\n${extraPrecache.map((asset) => `cache ${asset}\n`).join("")}`;
  fs.writeFileSync(mapPath, mirrored.text, "utf8");
  fs.writeFileSync(scriptPath, script, "utf8");
  fs.writeFileSync(precachePath, precache, "utf8");

  const report = {
    schemaVersion: 1,
    transform: "reflect X about world x=0",
    sourceMap: path.relative(path.dirname(outputRoot), sourcePath).replace(/\\/g, "/"),
    sourceBytes: Buffer.byteLength(sourceText),
    sourceSha256: sha256(sourceText),
    mapName,
    gameDirectory,
    originalMap,
    displayName: args["display-name"],
    output: {
      bytes: Buffer.byteLength(mirrored.text),
      sha256: sha256(mirrored.text),
    },
    transformed: mirrored.counts,
    scriptPolicy: "thin wrappers execute retail scripts; no retail script contents redistributed",
    extraPrecache,
  };
  fs.writeFileSync(path.join(outputRoot, `${mapName}-mirror-report.json`), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

if (require.main === module) main();

module.exports = { mirrorMapText };
