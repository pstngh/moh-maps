const fs = require("fs");
const path = require("path");

function tokenize(text) {
  const tokens = [];
  let index = 0;

  while (index < text.length) {
    const char = text[index];

    if (/\s/.test(char)) {
      index++;
      continue;
    }

    if (char === "/" && text[index + 1] === "/") {
      index += 2;
      while (index < text.length && text[index] !== "\n") index++;
      continue;
    }

    if (char === "{" || char === "}") {
      tokens.push(char);
      index++;
      continue;
    }

    if (char === '"') {
      index++;
      let value = "";
      while (index < text.length) {
        const current = text[index++];
        if (current === "\\") {
          if (index < text.length) value += text[index++];
        } else if (current === '"') {
          break;
        } else {
          value += current;
        }
      }
      tokens.push(value);
      continue;
    }

    const start = index;
    while (
      index < text.length &&
      !/\s/.test(text[index]) &&
      text[index] !== "{" &&
      text[index] !== "}"
    ) {
      index++;
    }
    tokens.push(text.slice(start, index));
  }

  return tokens;
}

function parseEntries(tokens, state, stopAtBrace = false) {
  const entries = [];

  while (state.index < tokens.length) {
    const key = tokens[state.index++];
    if (key === "}") {
      if (!stopAtBrace) throw new Error("Unexpected closing brace");
      return entries;
    }
    if (key === "{") throw new Error("Unexpected opening brace");

    const next = tokens[state.index++];
    if (next === "{") {
      entries.push({ key, children: parseEntries(tokens, state, true) });
    } else if (next === "}") {
      throw new Error(`Missing value for ${key}`);
    } else if (next === undefined) {
      throw new Error(`Unexpected EOF after ${key}`);
    } else {
      entries.push({ key, value: next });
    }
  }

  if (stopAtBrace) throw new Error("Unexpected EOF inside block");
  return entries;
}

function children(entries, key) {
  return entries.filter((entry) => entry.key === key && entry.children);
}

function value(entries, key, fallback = "") {
  return entries.find((entry) => entry.key === key && entry.value !== undefined)?.value ?? fallback;
}

function parseVector(text) {
  return text
    .trim()
    .replace(/^[\[(]/, "")
    .replace(/[\])]$/, "")
    .trim()
    .split(/\s+/)
    .map(Number);
}

function parsePlane(text) {
  const matches = [...text.matchAll(/\(([^)]+)\)/g)];
  if (matches.length !== 3) return null;
  return matches.map((match) => parseVector(match[1]));
}

function increment(map, key) {
  map.set(key, (map.get(key) || 0) + 1);
}

const inputPath = path.resolve(process.argv[2]);
const text = fs.readFileSync(inputPath, "utf8");
const entries = parseEntries(tokenize(text), { index: 0 });
const world = children(entries, "world")[0];
const entities = children(entries, "entity");
const classCounts = new Map();
const materials = new Map();
const propModels = new Map();
const propPlacements = [];
const displacementSolids = [];
const originsByClass = {};
const allPoints = [];
let solidCount = 0;
let sideCount = 0;
let displacementSides = 0;

function inspectSolid(solid, owner) {
  solidCount++;
  const solidPoints = [];
  const displacementFaces = [];
  for (const side of children(solid.children, "side")) {
    sideCount++;
    increment(materials, value(side.children, "material", "[missing]").toLowerCase());
    if (children(side.children, "dispinfo").length) {
      displacementSides++;
      displacementFaces.push({
        sideId: value(side.children, "id"),
        material: value(side.children, "material", "[missing]").toLowerCase(),
      });
    }
    const plane = parsePlane(value(side.children, "plane"));
    if (plane) {
      allPoints.push(...plane);
      solidPoints.push(...plane);
    }
    const vertices = children(side.children, "vertices_plus")[0];
    if (vertices) {
      for (const vertex of vertices.children.filter((entry) => entry.key === "v")) {
        const point = parseVector(vertex.value);
        allPoints.push(point);
        solidPoints.push(point);
      }
    }
  }
  if (displacementFaces.length) {
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (const point of solidPoints) {
      for (let axis = 0; axis < 3; axis++) {
        min[axis] = Math.min(min[axis], point[axis]);
        max[axis] = Math.max(max[axis], point[axis]);
      }
    }
    displacementSolids.push({
      id: value(solid.children, "id"),
      owner,
      min,
      max,
      displacementFaces,
    });
  }
}

for (const solid of children(world.children, "solid")) inspectSolid(solid, "worldspawn");

for (const entity of entities) {
  const classname = value(entity.children, "classname", "[missing]");
  increment(classCounts, classname);
  const originText = value(entity.children, "origin");
  if (originText) {
    if (!originsByClass[classname]) originsByClass[classname] = [];
    originsByClass[classname].push(parseVector(originText));
  }
  for (const solid of children(entity.children, "solid")) inspectSolid(solid, classname);
  if (classname.startsWith("prop_")) {
    const model = value(entity.children, "model", "[missing]").toLowerCase();
    increment(propModels, model);
    propPlacements.push({
      id: value(entity.children, "id"),
      classname,
      model,
      origin: parseVector(value(entity.children, "origin", "0 0 0")),
      angles: parseVector(value(entity.children, "angles", "0 0 0")),
    });
  }
}

const bounds = {
  min: [Infinity, Infinity, Infinity],
  max: [-Infinity, -Infinity, -Infinity],
};
for (const point of allPoints) {
  for (let axis = 0; axis < 3; axis++) {
    bounds.min[axis] = Math.min(bounds.min[axis], point[axis]);
    bounds.max[axis] = Math.max(bounds.max[axis], point[axis]);
  }
}

const result = {
  input: inputPath,
  bytes: Buffer.byteLength(text),
  topLevelBlocks: entries.filter((entry) => entry.children).length,
  worldSolids: children(world.children, "solid").length,
  entities: entities.length,
  solidCount,
  sideCount,
  displacementSides,
  bounds,
  worldspawn: Object.fromEntries(
    world.children
      .filter((entry) => entry.value !== undefined)
      .map((entry) => [entry.key, entry.value])
  ),
  classes: Object.fromEntries([...classCounts].sort((a, b) => b[1] - a[1])),
  originsByClass,
  materials: Object.fromEntries([...materials].sort((a, b) => b[1] - a[1])),
  propModels: Object.fromEntries([...propModels].sort((a, b) => b[1] - a[1])),
  propPlacements,
  displacementSolids,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
