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
    } else if (next === undefined || next === "}") {
      throw new Error(`Missing value for ${key}`);
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
  return (
    entries.find((entry) => entry.key === key && entry.value !== undefined)
      ?.value ?? fallback
  );
}

function properties(entries) {
  return Object.fromEntries(
    entries
      .filter((entry) => entry.value !== undefined)
      .map((entry) => [entry.key, entry.value])
  );
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

function add(...vectors) {
  return vectors[0].map((_, axis) =>
    vectors.reduce((sum, vector) => sum + vector[axis], 0)
  );
}

function subtract(left, right) {
  return left.map((coordinate, axis) => coordinate - right[axis]);
}

function scale(vector, amount) {
  return vector.map((coordinate) => coordinate * amount);
}

function dot(left, right) {
  return left.reduce(
    (sum, coordinate, axis) => sum + coordinate * right[axis],
    0
  );
}

function cross(left, right) {
  return [
    left[1] * right[2] - left[2] * right[1],
    left[2] * right[0] - left[0] * right[2],
    left[0] * right[1] - left[1] * right[0],
  ];
}

function normalized(vector) {
  const length = Math.sqrt(dot(vector, vector));
  if (length < 0.00001) return null;
  return vector.map((coordinate) => coordinate / length);
}

function centroid(points) {
  const result = [0, 0, 0];
  for (const point of points) {
    for (let axis = 0; axis < 3; axis++) result[axis] += point[axis];
  }
  return result.map((sum) => sum / points.length);
}

function brushPlane(points, interiorPoint) {
  let normal = normalized(
    cross(subtract(points[1], points[0]), subtract(points[2], points[0]))
  );
  if (!normal) return null;
  let distance = dot(normal, points[0]);
  if (dot(normal, interiorPoint) > distance) {
    normal = scale(normal, -1);
    distance *= -1;
  }
  return { normal, distance };
}

function intersectPlanes(first, second, third) {
  const secondCrossThird = cross(second.normal, third.normal);
  const denominator = dot(first.normal, secondCrossThird);
  if (Math.abs(denominator) < 0.00001) return null;
  return scale(
    add(
      scale(secondCrossThird, first.distance),
      scale(cross(third.normal, first.normal), second.distance),
      scale(cross(first.normal, second.normal), third.distance)
    ),
    1 / denominator
  );
}

function reconstructSolid(solid) {
  const sides = children(solid.children, "side");
  const planePoints = sides
    .map((side) => parsePlane(value(side.children, "plane")))
    .filter(Boolean);
  if (!planePoints.length) return null;
  const interior = centroid(planePoints.flat());
  const planes = planePoints.map((points) => brushPlane(points, interior));
  if (planes.some((plane) => !plane)) return null;

  const vertices = [];
  for (let first = 0; first < planes.length; first++) {
    for (let second = first + 1; second < planes.length; second++) {
      for (let third = second + 1; third < planes.length; third++) {
        const point = intersectPlanes(
          planes[first],
          planes[second],
          planes[third]
        );
        if (!point) continue;
        if (
          !planes.every(
            (plane) => dot(plane.normal, point) <= plane.distance + 0.1
          )
        ) {
          continue;
        }
        if (
          vertices.some(
            (existing) =>
              dot(subtract(existing, point), subtract(existing, point)) < 0.01
          )
        ) {
          continue;
        }
        vertices.push(point);
      }
    }
  }
  if (vertices.length < 4) return null;

  const faces = [];
  for (let sideIndex = 0; sideIndex < sides.length; sideIndex++) {
    const plane = planes[sideIndex];
    const faceVertices = vertices.filter(
      (point) => Math.abs(dot(plane.normal, point) - plane.distance) < 0.1
    );
    if (faceVertices.length < 3) continue;
    const center = centroid(faceVertices);
    const firstAxis = normalized(subtract(faceVertices[0], center));
    if (!firstAxis) continue;
    const secondAxis = normalized(cross(plane.normal, firstAxis));
    if (!secondAxis) continue;
    faceVertices.sort((left, right) => {
      const leftDelta = subtract(left, center);
      const rightDelta = subtract(right, center);
      return (
        Math.atan2(dot(leftDelta, secondAxis), dot(leftDelta, firstAxis)) -
        Math.atan2(dot(rightDelta, secondAxis), dot(rightDelta, firstAxis))
      );
    });
    faces.push({
      material: value(sides[sideIndex].children, "material", "[missing]")
        .toLowerCase()
        .replace(/\\/g, "/"),
      vertices: faceVertices,
      center,
      normal: plane.normal,
      distance: plane.distance,
      displacement:
        children(sides[sideIndex].children, "dispinfo").length > 0,
    });
  }

  const minimum = [Infinity, Infinity, Infinity];
  const maximum = [-Infinity, -Infinity, -Infinity];
  for (const point of vertices) {
    for (let axis = 0; axis < 3; axis++) {
      minimum[axis] = Math.min(minimum[axis], point[axis]);
      maximum[axis] = Math.max(maximum[axis], point[axis]);
    }
  }
  return {
    id: value(solid.children, "id"),
    vertices,
    faces,
    planes,
    bounds: { minimum, maximum },
    center: centroid(vertices),
  };
}

function pointInPolygon2d(x, y, vertices) {
  let inside = false;
  for (
    let current = 0, previous = vertices.length - 1;
    current < vertices.length;
    previous = current++
  ) {
    const currentX = vertices[current][0];
    const currentY = vertices[current][1];
    const previousX = vertices[previous][0];
    const previousY = vertices[previous][1];
    const intersects =
      currentY > y !== previousY > y &&
      x <
        ((previousX - currentX) * (y - currentY)) /
          (previousY - currentY) +
          currentX;
    if (intersects) inside = !inside;
  }
  return inside;
}

function heightAt(face, x, y) {
  if (Math.abs(face.normal[2]) < 0.0001) return null;
  return (
    (face.distance - face.normal[0] * x - face.normal[1] * y) /
    face.normal[2]
  );
}

function escapeXml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function increment(counter, key) {
  counter.set(key, (counter.get(key) || 0) + 1);
}

function boundsForOrigins(origins) {
  const minimum = [Infinity, Infinity, Infinity];
  const maximum = [-Infinity, -Infinity, -Infinity];
  for (const origin of origins) {
    for (let axis = 0; axis < 3; axis++) {
      minimum[axis] = Math.min(minimum[axis], origin[axis]);
      maximum[axis] = Math.max(maximum[axis], origin[axis]);
    }
  }
  return { minimum, maximum };
}

const inputPath = process.argv[2];
const outputDirectory = process.argv[3] || path.resolve(__dirname, "..");
if (!inputPath) {
  throw new Error(
    "Usage: node audit_inferno_layout.js <de_inferno_d.vmf> [output-directory]"
  );
}

const source = fs.readFileSync(inputPath, "utf8");
const entries = parseEntries(tokenize(source), { index: 0 });
const world = children(entries, "world")[0];
if (!world) throw new Error("VMF has no world block");
const entities = children(entries, "entity");

const playableBounds = {
  minimum: [-2200, -1000, -160],
  maximum: [3000, 3900, 420],
};
const helperMaterial = /^tools\//;
const floorFaces = [];
const ceilingFaces = [];
const solidRecords = [];
const ownerEntries = [
  {
    classname: "worldspawn",
    ownerId: value(world.children, "id"),
    solids: children(world.children, "solid"),
  },
];

for (const entity of entities) {
  const props = properties(entity.children);
  const solids = children(entity.children, "solid");
  if (!solids.length) continue;
  ownerEntries.push({
    classname: props.classname || "[missing]",
    ownerId: props.id || "",
    solids,
  });
}

let failedSolids = 0;
for (const owner of ownerEntries) {
  for (const sourceSolid of owner.solids) {
    const solid = reconstructSolid(sourceSolid);
    if (!solid) {
      failedSolids++;
      continue;
    }
    solid.ownerClass = owner.classname;
    solid.ownerId = owner.ownerId;
    solidRecords.push(solid);
    for (const face of solid.faces) {
      const measuredFace = {
        ...face,
        solidId: solid.id,
        ownerClass: owner.classname,
        ownerId: owner.ownerId,
      };
      if (
        face.normal[2] < -0.65 &&
        face.center[0] >= playableBounds.minimum[0] &&
        face.center[0] <= playableBounds.maximum[0] &&
        face.center[1] >= playableBounds.minimum[1] &&
        face.center[1] <= playableBounds.maximum[1] &&
        face.center[2] >= playableBounds.minimum[2] &&
        face.center[2] <= 720
      ) {
        ceilingFaces.push(measuredFace);
      }
      if (helperMaterial.test(face.material)) continue;
      if (face.normal[2] < 0.65) continue;
      if (face.center[0] < playableBounds.minimum[0]) continue;
      if (face.center[0] > playableBounds.maximum[0]) continue;
      if (face.center[1] < playableBounds.minimum[1]) continue;
      if (face.center[1] > playableBounds.maximum[1]) continue;
      if (face.center[2] < playableBounds.minimum[2]) continue;
      if (face.center[2] > playableBounds.maximum[2]) continue;
      floorFaces.push(measuredFace);
    }
  }
}

const spawnClasses = new Set([
  "info_deathmatch_spawn",
  "info_player_terrorist",
  "info_player_counterterrorist",
]);
const spawns = [];
const bombTargets = [];
const selectedProps = [];
const modelCounts = new Map();
const selectedModelPattern =
  /(fountain|coffin|hay|cart|barrel|bell|church|arch|door|balcony|pit|well|column|shutter|window|roof)/i;

for (const entity of entities) {
  const props = properties(entity.children);
  const classname = props.classname || "[missing]";
  if (spawnClasses.has(classname) && props.origin) {
    spawns.push({
      id: props.id || "",
      classname,
      origin: parseVector(props.origin),
      angles: parseVector(props.angles || "0 0 0"),
    });
  }
  if (classname === "func_bomb_target") {
    const entitySolids = children(entity.children, "solid")
      .map(reconstructSolid)
      .filter(Boolean);
    if (entitySolids.length) {
      const points = entitySolids.flatMap((solid) => solid.vertices);
      bombTargets.push({
        id: props.id || "",
        bounds: boundsForOrigins(points),
      });
    }
  }
  if (props.model) {
    const model = props.model.toLowerCase().replace(/\\/g, "/");
    increment(modelCounts, model);
    if (props.origin && selectedModelPattern.test(model)) {
      selectedProps.push({
        id: props.id || "",
        classname,
        model,
        origin: parseVector(props.origin),
      });
    }
  }
}

const gridSize = 32;
const walkableOwners = new Set(["worldspawn", "func_detail", "func_brush"]);
const blockingOwners = new Set([
  "worldspawn",
  "func_detail",
  "func_brush",
  "func_breakable",
  "func_nav_blocker",
]);
const nonBlockingToolMaterial =
  /^tools\/(toolshint|toolsskip|toolstrigger|toolsareaportal|toolsblocklight|toolsinvisibleladder|toolsgrenadeclip)/;
const collisionBucketSize = 128;
const collisionBuckets = new Map();

function collisionBucketKey(x, y) {
  return `${Math.floor(x / collisionBucketSize)},${Math.floor(
    y / collisionBucketSize
  )}`;
}

function solidBlocksPlayer(solid) {
  if (!blockingOwners.has(solid.ownerClass)) return false;
  const materials = solid.faces.map((face) => face.material);
  if (!materials.length) return false;
  return !materials.every((material) => nonBlockingToolMaterial.test(material));
}

for (const solid of solidRecords.filter(solidBlocksPlayer)) {
  if (solid.bounds.maximum[0] < playableBounds.minimum[0]) continue;
  if (solid.bounds.minimum[0] > playableBounds.maximum[0]) continue;
  if (solid.bounds.maximum[1] < playableBounds.minimum[1]) continue;
  if (solid.bounds.minimum[1] > playableBounds.maximum[1]) continue;
  if (solid.bounds.maximum[2] < playableBounds.minimum[2]) continue;
  if (solid.bounds.minimum[2] > 720) continue;
  const minimumBucketX = Math.floor(
    solid.bounds.minimum[0] / collisionBucketSize
  );
  const maximumBucketX = Math.floor(
    solid.bounds.maximum[0] / collisionBucketSize
  );
  const minimumBucketY = Math.floor(
    solid.bounds.minimum[1] / collisionBucketSize
  );
  const maximumBucketY = Math.floor(
    solid.bounds.maximum[1] / collisionBucketSize
  );
  for (let bucketX = minimumBucketX; bucketX <= maximumBucketX; bucketX++) {
    for (let bucketY = minimumBucketY; bucketY <= maximumBucketY; bucketY++) {
      const key = `${bucketX},${bucketY}`;
      const bucket = collisionBuckets.get(key) || [];
      bucket.push(solid);
      collisionBuckets.set(key, bucket);
    }
  }
}

function pointInsideSolid(point, solid) {
  for (let axis = 0; axis < 3; axis++) {
    if (point[axis] < solid.bounds.minimum[axis] - 0.1) return false;
    if (point[axis] > solid.bounds.maximum[axis] + 0.1) return false;
  }
  return solid.planes.every(
    (plane) => dot(plane.normal, point) <= plane.distance + 0.1
  );
}

function pointBlocked(point) {
  return (collisionBuckets.get(collisionBucketKey(point[0], point[1])) || []).some(
    (solid) => pointInsideSolid(point, solid)
  );
}

function transitionBlocked(left, right) {
  for (const amount of [0.25, 0.5, 0.75]) {
    const x = left.x + (right.x - left.x) * amount;
    const y = left.y + (right.y - left.y) * amount;
    const feetZ = left.z + (right.z - left.z) * amount;
    if (pointBlocked([x, y, feetZ + 32])) return true;
    if (pointBlocked([x, y, feetZ + 68])) return true;
  }
  return false;
}

function cellKey(x, y) {
  return `${x},${y}`;
}

function nodeKey(x, y, z) {
  return `${x},${y},${z}`;
}

function rasterizeHorizontalFaces(faces, upward) {
  const result = new Map();
  for (const face of faces) {
    if (!walkableOwners.has(face.ownerClass)) continue;
    if (upward && helperMaterial.test(face.material)) continue;
    const xs = face.vertices.map((point) => point[0]);
    const ys = face.vertices.map((point) => point[1]);
    const minimumX = Math.max(playableBounds.minimum[0], Math.min(...xs));
    const maximumX = Math.min(playableBounds.maximum[0], Math.max(...xs));
    const minimumY = Math.max(playableBounds.minimum[1], Math.min(...ys));
    const maximumY = Math.min(playableBounds.maximum[1], Math.max(...ys));
    const startX = Math.ceil(minimumX / gridSize) * gridSize;
    const endX = Math.floor(maximumX / gridSize) * gridSize;
    const startY = Math.ceil(minimumY / gridSize) * gridSize;
    const endY = Math.floor(maximumY / gridSize) * gridSize;
    for (let x = startX; x <= endX; x += gridSize) {
      for (let y = startY; y <= endY; y += gridSize) {
        if (!pointInPolygon2d(x, y, face.vertices)) continue;
        const rawZ = heightAt(face, x, y);
        if (!Number.isFinite(rawZ)) continue;
        const z = Math.round(rawZ / 8) * 8;
        const key = cellKey(x, y);
        const candidates = result.get(key) || [];
        if (candidates.some((candidate) => Math.abs(candidate.z - z) < 4)) {
          continue;
        }
        candidates.push({
          x,
          y,
          z,
          material: face.material,
          ownerClass: face.ownerClass,
          solidId: face.solidId,
          displacement: face.displacement,
        });
        result.set(key, candidates);
      }
    }
  }
  for (const candidates of result.values()) {
    candidates.sort((left, right) => left.z - right.z);
  }
  return result;
}

const floorCandidates = rasterizeHorizontalFaces(floorFaces, true);
const ceilingCandidates = rasterizeHorizontalFaces(ceilingFaces, false);
let rejectedHeadroomNodes = 0;
for (const [key, candidates] of floorCandidates) {
  const retained = candidates.filter((candidate) => {
    const blocked =
      pointBlocked([candidate.x, candidate.y, candidate.z + 32]) ||
      pointBlocked([candidate.x, candidate.y, candidate.z + 68]);
    if (blocked) rejectedHeadroomNodes++;
    return !blocked;
  });
  if (retained.length) floorCandidates.set(key, retained);
  else floorCandidates.delete(key);
}
const allWalkNodes = new Map();
for (const candidates of floorCandidates.values()) {
  for (const candidate of candidates) {
    allWalkNodes.set(nodeKey(candidate.x, candidate.y, candidate.z), candidate);
  }
}

function nearestSpawnNode(spawn) {
  const centerX = Math.round(spawn.origin[0] / gridSize) * gridSize;
  const centerY = Math.round(spawn.origin[1] / gridSize) * gridSize;
  let best = null;
  for (let xOffset = -3; xOffset <= 3; xOffset++) {
    for (let yOffset = -3; yOffset <= 3; yOffset++) {
      const x = centerX + xOffset * gridSize;
      const y = centerY + yOffset * gridSize;
      for (const candidate of floorCandidates.get(cellKey(x, y)) || []) {
        const zDelta = Math.abs(candidate.z - spawn.origin[2]);
        if (zDelta > 112) continue;
        const xDelta = candidate.x - spawn.origin[0];
        const yDelta = candidate.y - spawn.origin[1];
        const score = xDelta * xDelta + yDelta * yDelta + zDelta * zDelta * 2;
        if (!best || score < best.score) best = { candidate, score };
      }
    }
  }
  return best?.candidate || null;
}

const seedNodeKeys = new Set();
const unmatchedSpawns = [];
for (const spawn of spawns) {
  const seed = nearestSpawnNode(spawn);
  if (seed) {
    seedNodeKeys.add(nodeKey(seed.x, seed.y, seed.z));
  } else {
    unmatchedSpawns.push(spawn);
  }
}

const visitedNodeKeys = new Set(seedNodeKeys);
const allowedWalkEdges = new Set();
const queue = [...seedNodeKeys];
const neighborOffsets = [
  [-gridSize, 0],
  [gridSize, 0],
  [0, -gridSize],
  [0, gridSize],
];
for (let queueIndex = 0; queueIndex < queue.length; queueIndex++) {
  const currentKey = queue[queueIndex];
  const current = allWalkNodes.get(currentKey);
  if (!current) continue;
  for (const [xOffset, yOffset] of neighborOffsets) {
    const candidates =
      floorCandidates.get(cellKey(current.x + xOffset, current.y + yOffset)) ||
      [];
    for (const candidate of candidates) {
      if (Math.abs(candidate.z - current.z) > 32) continue;
      if (transitionBlocked(current, candidate)) continue;
      const candidateKey = nodeKey(candidate.x, candidate.y, candidate.z);
      allowedWalkEdges.add([currentKey, candidateKey].sort().join("|"));
      if (visitedNodeKeys.has(candidateKey)) continue;
      visitedNodeKeys.add(candidateKey);
      queue.push(candidateKey);
    }
  }
}

const walkCells = [...visitedNodeKeys]
  .map((key) => allWalkNodes.get(key))
  .filter(Boolean)
  .map((cell) => {
    const ceilings = ceilingCandidates.get(cellKey(cell.x, cell.y)) || [];
    const overhead = ceilings
      .map((ceiling) => ceiling.z)
      .filter((z) => z >= cell.z + 64 && z <= cell.z + 384)
      .sort((left, right) => left - right)[0];
    return {
      ...cell,
      ceilingZ: Number.isFinite(overhead) ? overhead : null,
      interior: Number.isFinite(overhead) && overhead <= cell.z + 224,
    };
  })
  .sort((left, right) => left.z - right.z || left.y - right.y || left.x - right.x);

const walkHeightHistogram = new Map();
for (const cell of walkCells) increment(walkHeightHistogram, String(cell.z));
const width = 1280;
const height = 1180;
const margin = 55;
const worldWidth =
  playableBounds.maximum[0] - playableBounds.minimum[0];
const worldHeight =
  playableBounds.maximum[1] - playableBounds.minimum[1];
const scaleFactor = Math.min(
  (width - margin * 2) / worldWidth,
  (height - margin * 2) / worldHeight
);
const drawWidth = worldWidth * scaleFactor;
const drawHeight = worldHeight * scaleFactor;
const offsetX = (width - drawWidth) / 2;
const offsetY = (height - drawHeight) / 2;

function sx(x) {
  return offsetX + (x - playableBounds.minimum[0]) * scaleFactor;
}

function sy(y) {
  return (
    offsetY + (playableBounds.maximum[1] - y) * scaleFactor
  );
}

function colorForHeight(z) {
  if (z < 0) return "#5c6774";
  if (z < 64) return "#738496";
  if (z < 128) return "#879d9b";
  if (z < 192) return "#a7aa85";
  if (z < 256) return "#c7aa78";
  if (z < 320) return "#d68d6b";
  return "#a76e80";
}

const svg = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
  "<style>",
  "text { font-family: Segoe UI, Arial, sans-serif; }",
  ".label { fill: #f8f4e9; font-size: 15px; font-weight: 700; paint-order: stroke; stroke: #111827; stroke-width: 4px; }",
  ".small { fill: #111827; font-size: 11px; font-weight: 600; }",
  "</style>",
  `<rect width="${width}" height="${height}" fill="#17202b"/>`,
  `<rect x="${offsetX}" y="${offsetY}" width="${drawWidth}" height="${drawHeight}" fill="#263443" stroke="#9fb3c8" stroke-width="2"/>`,
];

for (let x = -2000; x <= 3000; x += 500) {
  svg.push(
    `<line x1="${sx(x)}" y1="${offsetY}" x2="${sx(x)}" y2="${
      offsetY + drawHeight
    }" stroke="#425365" stroke-width="1"/>`,
    `<text x="${sx(x) + 3}" y="${offsetY + drawHeight - 5}" class="small">${x}</text>`
  );
}
for (let y = -1000; y <= 3500; y += 500) {
  svg.push(
    `<line x1="${offsetX}" y1="${sy(y)}" x2="${
      offsetX + drawWidth
    }" y2="${sy(y)}" stroke="#425365" stroke-width="1"/>`,
    `<text x="${offsetX + 4}" y="${sy(y) - 4}" class="small">${y}</text>`
  );
}

const orderedFaces = [...floorFaces].sort(
  (left, right) => left.center[2] - right.center[2]
);
for (const face of orderedFaces) {
  const points = face.vertices
    .map((point) => `${sx(point[0]).toFixed(2)},${sy(point[1]).toFixed(2)}`)
    .join(" ");
  const opacity = face.displacement ? 0.82 : 0.66;
  svg.push(
    `<polygon points="${points}" fill="${colorForHeight(
      face.center[2]
    )}" fill-opacity="${opacity}" stroke="#111827" stroke-opacity="0.42" stroke-width="0.65"><title>${escapeXml(
      `${face.ownerClass} solid ${face.solidId}, z=${face.center[2].toFixed(
        1
      )}, ${face.material}`
    )}</title></polygon>`
  );
}

for (const target of bombTargets) {
  const x = sx(target.bounds.minimum[0]);
  const y = sy(target.bounds.maximum[1]);
  const targetWidth =
    (target.bounds.maximum[0] - target.bounds.minimum[0]) * scaleFactor;
  const targetHeight =
    (target.bounds.maximum[1] - target.bounds.minimum[1]) * scaleFactor;
  svg.push(
    `<rect x="${x}" y="${y}" width="${targetWidth}" height="${targetHeight}" fill="#ef4444" fill-opacity="0.28" stroke="#ef4444" stroke-width="3"/>`
  );
}

const spawnStyle = {
  info_player_terrorist: { fill: "#f97316", radius: 4.5 },
  info_player_counterterrorist: { fill: "#38bdf8", radius: 4.5 },
  info_deathmatch_spawn: { fill: "#f8fafc", radius: 2.2 },
};
for (const spawn of spawns) {
  const style = spawnStyle[spawn.classname];
  if (!style) continue;
  svg.push(
    `<circle cx="${sx(spawn.origin[0])}" cy="${sy(
      spawn.origin[1]
    )}" r="${style.radius}" fill="${style.fill}" stroke="#111827" stroke-width="0.8"><title>${escapeXml(
      `${spawn.classname} ${spawn.origin.join(" ")}`
    )}</title></circle>`
  );
}

for (const prop of selectedProps) {
  if (prop.origin[0] < playableBounds.minimum[0]) continue;
  if (prop.origin[0] > playableBounds.maximum[0]) continue;
  if (prop.origin[1] < playableBounds.minimum[1]) continue;
  if (prop.origin[1] > playableBounds.maximum[1]) continue;
  svg.push(
    `<circle cx="${sx(prop.origin[0])}" cy="${sy(
      prop.origin[1]
    )}" r="1.5" fill="#d946ef" fill-opacity="0.72"><title>${escapeXml(
      prop.model
    )}</title></circle>`
  );
}

const teamGroups = {
  T: spawns.filter((spawn) => spawn.classname === "info_player_terrorist"),
  CT: spawns.filter(
    (spawn) => spawn.classname === "info_player_counterterrorist"
  ),
};
for (const [label, group] of Object.entries(teamGroups)) {
  if (!group.length) continue;
  const center = centroid(group.map((spawn) => spawn.origin));
  svg.push(
    `<text x="${sx(center[0])}" y="${sy(center[1])}" text-anchor="middle" class="label">${label} SPAWN</text>`
  );
}

svg.push(
  `<text x="${width / 2}" y="28" text-anchor="middle" fill="#f8f4e9" font-size="22" font-weight="700">CS:GO Inferno measured playable-surface audit</text>`,
  `<text x="${width / 2}" y="${height - 16}" text-anchor="middle" fill="#b9c6d3" font-size="12">floor-like Source faces by elevation; orange T, blue CT, white DM, red bomb targets, magenta landmark-model origins</text>`,
  "</svg>"
);

const walkSvg = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
  "<style>",
  "text { font-family: Segoe UI, Arial, sans-serif; }",
  ".label { fill: #f8f4e9; font-size: 15px; font-weight: 700; paint-order: stroke; stroke: #111827; stroke-width: 4px; }",
  "</style>",
  `<rect width="${width}" height="${height}" fill="#17202b"/>`,
  `<rect x="${offsetX}" y="${offsetY}" width="${drawWidth}" height="${drawHeight}" fill="#263443" stroke="#9fb3c8" stroke-width="2"/>`,
];

const cellPixelSize = gridSize * scaleFactor;
for (const cell of walkCells) {
  const x = sx(cell.x - gridSize / 2);
  const y = sy(cell.y + gridSize / 2);
  walkSvg.push(
    `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${cellPixelSize.toFixed(
      2
    )}" height="${cellPixelSize.toFixed(2)}" fill="${colorForHeight(
      cell.z
    )}" fill-opacity="${cell.interior ? 0.95 : 0.76}" stroke="#111827" stroke-opacity="0.2" stroke-width="0.35"><title>${escapeXml(
      `${cell.x} ${cell.y} ${cell.z}; ${cell.interior ? "interior" : "outdoor"}; ${cell.material}`
    )}</title></rect>`
  );
}

for (const [targetIndex, target] of bombTargets.entries()) {
  const x = sx(target.bounds.minimum[0]);
  const y = sy(target.bounds.maximum[1]);
  const targetWidth =
    (target.bounds.maximum[0] - target.bounds.minimum[0]) * scaleFactor;
  const targetHeight =
    (target.bounds.maximum[1] - target.bounds.minimum[1]) * scaleFactor;
  const centerX = x + targetWidth / 2;
  const centerY = y + targetHeight / 2;
  const label =
    (target.bounds.minimum[1] + target.bounds.maximum[1]) / 2 < 1500
      ? "A SITE"
      : "B SITE";
  walkSvg.push(
    `<rect x="${x}" y="${y}" width="${targetWidth}" height="${targetHeight}" fill="#ef4444" fill-opacity="0.3" stroke="#ef4444" stroke-width="3"/>`,
    `<text x="${centerX}" y="${centerY}" text-anchor="middle" class="label">${label}</text>`
  );
}

for (const spawn of spawns) {
  const style = spawnStyle[spawn.classname];
  if (!style) continue;
  walkSvg.push(
    `<circle cx="${sx(spawn.origin[0])}" cy="${sy(
      spawn.origin[1]
    )}" r="${style.radius}" fill="${style.fill}" stroke="#111827" stroke-width="0.8"/>`
  );
}
for (const [label, group] of Object.entries(teamGroups)) {
  if (!group.length) continue;
  const center = centroid(group.map((spawn) => spawn.origin));
  walkSvg.push(
    `<text x="${sx(center[0])}" y="${sy(center[1])}" text-anchor="middle" class="label">${label} SPAWN</text>`
  );
}
walkSvg.push(
  `<text x="${width / 2}" y="28" text-anchor="middle" fill="#f8f4e9" font-size="22" font-weight="700">CS:GO Inferno spawn-seeded walkable grid</text>`,
  `<text x="${width / 2}" y="${height - 16}" text-anchor="middle" fill="#b9c6d3" font-size="12">32-unit measured cells; color is elevation, stronger opacity is detected interior</text>`,
  "</svg>"
);
const floorBounds = boundsForOrigins(
  floorFaces.flatMap((face) => face.vertices)
);
const topModels = [...modelCounts.entries()]
  .sort((left, right) => right[1] - left[1])
  .slice(0, 100)
  .map(([model, count]) => ({ model, count }));
const report = {
  input: path.basename(inputPath),
  inputBytes: Buffer.byteLength(source),
  playableBounds,
  source: {
    worldSolids: children(world.children, "solid").length,
    entities: entities.length,
    reconstructedSolids: solidRecords.length,
    failedSolids,
    floorLikeFaces: floorFaces.length,
    floorFaceBounds: floorBounds,
  },
  spawns: {
    deathmatch: spawns.filter(
      (spawn) => spawn.classname === "info_deathmatch_spawn"
    ),
    terrorist: spawns.filter(
      (spawn) => spawn.classname === "info_player_terrorist"
    ),
    counterTerrorist: spawns.filter(
      (spawn) => spawn.classname === "info_player_counterterrorist"
    ),
  },
  bombTargets,
  walkGrid: {
    cellSize: gridSize,
    candidateCells: floorCandidates.size,
    candidateNodes: allWalkNodes.size,
    rejectedHeadroomNodes,
    collisionBuckets: collisionBuckets.size,
    seededNodes: seedNodeKeys.size,
    connectedNodes: walkCells.length,
    connectedEdges: allowedWalkEdges.size,
    unmatchedSpawns,
    heightHistogram: Object.fromEntries(
      [...walkHeightHistogram].sort(
        (left, right) => Number(left[0]) - Number(right[0])
      )
    ),
    cells: walkCells,
    edges: [...allowedWalkEdges]
      .sort()
      .map((edgeKey) => edgeKey.split("|")),
  },
  selectedLandmarkProps: selectedProps,
  topModels,
};

fs.mkdirSync(outputDirectory, { recursive: true });
const reportPath = path.join(
  outputDirectory,
  "inferno-layout-reference-audit.json"
);
const svgPath = path.join(
  outputDirectory,
  "inferno-layout-reference-audit.svg"
);
const walkSvgPath = path.join(
  outputDirectory,
  "inferno-walk-grid-reference.svg"
);
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
fs.writeFileSync(svgPath, `${svg.join("\n")}\n`);
fs.writeFileSync(walkSvgPath, `${walkSvg.join("\n")}\n`);

console.log(
  JSON.stringify(
    {
      reportPath,
      svgPath,
      walkSvgPath,
      reconstructedSolids: solidRecords.length,
      failedSolids,
      floorLikeFaces: floorFaces.length,
      spawns: {
        deathmatch: report.spawns.deathmatch.length,
        terrorist: report.spawns.terrorist.length,
        counterTerrorist: report.spawns.counterTerrorist.length,
      },
      bombTargets: bombTargets.length,
      walkGrid: {
        candidateCells: floorCandidates.size,
        candidateNodes: allWalkNodes.size,
        rejectedHeadroomNodes,
        collisionBuckets: collisionBuckets.size,
        seededNodes: seedNodeKeys.size,
        connectedNodes: walkCells.length,
        connectedEdges: allowedWalkEdges.size,
        unmatchedSpawns: unmatchedSpawns.length,
      },
      selectedLandmarkProps: selectedProps.length,
    },
    null,
    2
  )
);
