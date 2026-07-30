const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const referencePath = path.resolve(
  process.argv[2] || path.join("references", "de_inferno_d.vmf")
);
const outputRoot = path.resolve(
  process.argv[3] || path.join("generated", "codex_inferno")
);
const mapName = process.argv[4] || "codex_inferno";
const displacementMode = process.argv.includes("--full-displacements")
  ? "full"
  : "planar";
const compileBudgetMode = process.argv.includes("--compile-budget");
const mainDir = path.join(outputRoot, "main");
const mapDir = path.join(mainDir, "maps", "dm");
fs.mkdirSync(mapDir, { recursive: true });

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

function fmt(number) {
  if (Math.abs(number) < 0.0005) return "0";
  if (Number.isInteger(number)) return String(number);
  return Number(number.toFixed(4)).toString();
}

function formatPoint(point) {
  return `( ${point.map(fmt).join(" ")} )`;
}

const targetMaterials = {
  concreteLight: {
    texture: "codex_inferno/plaster_cream",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  paintedConcrete: {
    texture: "codex_inferno/plaster_white",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  paintedConcreteBlue: {
    texture: "codex_inferno/plaster_rose",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  plasterOchre: {
    texture: "codex_inferno/plaster_ochre",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  concreteFloor: {
    texture: "codex_inferno/stone_floor",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  concreteDark: {
    texture: "codex_inferno/stone_trim",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  asphalt: {
    texture: "codex_inferno/cobblestone",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  grass: {
    texture: "codex_inferno/grass",
    contentFlags: 0,
    surfaceFlags: 524288,
  },
  gravel: {
    texture: "codex_inferno/stone_floor",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  corrugatedBlue: {
    texture: "codex_inferno/roof_tile",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  corrugatedGray: {
    texture: "codex_inferno/roof_tile",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  metalTrim: {
    texture: "codex_inferno/stone_trim",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  ceilingTile: {
    texture: "codex_inferno/ceiling",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  metalGrating: {
    texture: "codex_inferno/painted_metal",
    contentFlags: 8192,
    surfaceFlags: 262176,
  },
  chainlink: {
    texture: "codex_inferno/painted_metal",
    contentFlags: 8192,
    surfaceFlags: 262176,
  },
  glass: {
    texture: "codex_inferno/window_dark",
    contentFlags: 0,
    surfaceFlags: 4194304,
  },
  windowBacking: {
    texture: "codex_inferno/window_dark",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  brick: {
    texture: "codex_inferno/brick",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  wood: {
    texture: "codex_inferno/wood",
    contentFlags: 0,
    surfaceFlags: 16384,
  },
  paintedMetal: {
    texture: "codex_inferno/painted_metal",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  sky: {
    texture: "sky/m5l2",
    contentFlags: 0,
    surfaceFlags: 276,
  },
  caulk: {
    texture: "common/caulk",
    contentFlags: 0,
    surfaceFlags: 160,
  },
  playerClip: {
    texture: "common/playerclip",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  clip: {
    texture: "common/clip",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  origin: {
    texture: "common/origin",
    contentFlags: 0,
    surfaceFlags: 0,
  },
};

const targetByTexture = new Map(
  Object.values(targetMaterials).map((material) => [material.texture, material])
);

function materialFor(sourceMaterial) {
  const material = sourceMaterial.toLowerCase();
  if (material.includes("skybox")) return targetMaterials.sky;

  // Hidden Source faces remain hidden. This is safe only when compiling
  // against retail AA shader definitions so common/caulk receives its real
  // flags in the BSP.
  if (/tools\/toolsnodraw/i.test(material)) return targetMaterials.caulk;
  if (
    /tools\/(toolsclip|toolsgrenadeclip|grenadeclip|toolshint|toolsskip|toolstrigger|toolsareaportal|toolsplayerclip|toolsblockbullets|toolsinvisibleladder|toolsinvisible|wrongway)/i.test(
      material
    )
  ) {
    return targetMaterials.caulk;
  }

  if (/tools\/toolsblack/i.test(material)) return targetMaterials.windowBacking;
  if (/(cobweb)/.test(material)) return targetMaterials.caulk;
  if (/liquids\//.test(material)) return targetMaterials.caulk;
  if (/(stained_glass|stain_glass|glass)/.test(material)) return targetMaterials.glass;
  if (/(lights\/|toolsblack|window|oldwindow)/.test(material)) {
    return targetMaterials.windowBacking;
  }
  if (/(grass|foliage|blendgrass)/.test(material)) return targetMaterials.grass;
  if (/(cobblestone)/.test(material)) return targetMaterials.asphalt;
  if (/(flagstone|sidewalk|herringbone)/.test(material)) return targetMaterials.concreteFloor;
  if (/(dirt|gravel|rock)/.test(material)) return targetMaterials.gravel;
  if (/(asphalt|road|path)/.test(material)) return targetMaterials.asphalt;
  if (/plaster/.test(material)) {
    if (/plaster_(b|e)/.test(material)) return targetMaterials.concreteLight;
    if (/plaster_(g|c)/.test(material)) return targetMaterials.plasterOchre;
    if (/plaster_i/.test(material)) return targetMaterials.paintedConcreteBlue;
    return targetMaterials.paintedConcrete;
  }
  if (/(crate|wood|plank|board|plywood)/.test(material)) return targetMaterials.wood;
  if (/(brick)/.test(material)) return targetMaterials.brick;
  if (/(grate|mesh)/.test(material)) return targetMaterials.metalGrating;
  if (/(fence|chainlink)/.test(material)) return targetMaterials.chainlink;
  if (/(blueroom|blue_room)/.test(material)) {
    return /(beam|metal|panel|door)/.test(material)
      ? targetMaterials.paintedMetal
      : targetMaterials.paintedConcreteBlue;
  }
  if (/(roof|roofing_tile|corrugated|inferno_tiles_red)/.test(material)) {
    return /blue/.test(material)
      ? targetMaterials.corrugatedBlue
      : targetMaterials.corrugatedGray;
  }
  if (/(beam|ibeam|metal|iron|rust|steel|panel|rollup|pipe|vent|duct)/.test(material)) {
    return targetMaterials.paintedMetal;
  }
  if (/(trim|underbeam)/.test(material)) return targetMaterials.metalTrim;
  if (/(ceiling|acoustic)/.test(material)) return targetMaterials.ceilingTile;
  if (/(floor|tile)/.test(material)) return targetMaterials.concreteFloor;
  if (/(concrete|block|interior|wallpaper|white|apartment|plaster|wall)/.test(material)) {
    return targetMaterials.paintedConcrete;
  }
  return targetMaterials.concreteLight;
}

const helperMaterial = /tools\/(toolsclip|toolsgrenadeclip|grenadeclip|toolshint|toolsskip|toolstrigger|toolsareaportal|toolsplayerclip|toolsblockbullets|toolsinvisibleladder|toolsinvisible|wrongway)/i;
const nodrawMaterial = /tools\/toolsnodraw/i;

function pointsForSolid(solid) {
  const points = [];
  for (const side of children(solid.children, "side")) {
    const vertices = children(side.children, "vertices_plus")[0];
    if (vertices) {
      for (const vertex of vertices.children.filter((entry) => entry.key === "v")) {
        points.push(parseVector(vertex.value));
      }
    }
    if (!vertices) {
      const plane = parsePlane(value(side.children, "plane"));
      if (plane) points.push(...plane);
    }
  }
  return points;
}

function centroid(points) {
  const result = [0, 0, 0];
  for (const point of points) {
    for (let axis = 0; axis < 3; axis++) result[axis] += point[axis];
  }
  return result.map((sum) => sum / points.length);
}

function solidExtents(solid) {
  const points = pointsForSolid(solid);
  if (!points.length) return null;
  const min = [...points[0]];
  const max = [...points[0]];
  for (const point of points.slice(1)) {
    for (let axis = 0; axis < 3; axis++) {
      min[axis] = Math.min(min[axis], point[axis]);
      max[axis] = Math.max(max[axis], point[axis]);
    }
  }
  return max.map((coordinate, axis) => coordinate - min[axis]);
}

function subtract(a, b) {
  return a.map((component, axis) => component - b[axis]);
}

function add(...vectors) {
  return vectors[0].map((_, axis) =>
    vectors.reduce((sum, vector) => sum + vector[axis], 0)
  );
}

function scale(vector, amount) {
  return vector.map((component) => component * amount);
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot(a, b) {
  return a.reduce((sum, component, axis) => sum + component * b[axis], 0);
}

function normalized(vector) {
  const length = Math.sqrt(dot(vector, vector));
  if (length < 0.0001) return null;
  return vector.map((component) => component / length);
}

function orientedPlane(points, interiorPoint) {
  const result = points.map((point) => [...point]);
  const normal = cross(subtract(result[1], result[0]), subtract(result[2], result[0]));
  if (dot(normal, subtract(interiorPoint, result[0])) < 0) {
    [result[1], result[2]] = [result[2], result[1]];
  }
  return result;
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

function reconstructedFaceVertices(sides, targetSide, interiorPoint) {
  const planes = sides.map((side) => {
    const points = parsePlane(value(side.children, "plane"));
    return points ? brushPlane(points, interiorPoint) : null;
  });
  const targetIndex = sides.indexOf(targetSide);
  const targetPlane = planes[targetIndex];
  if (!targetPlane || targetIndex < 0) return null;

  const vertices = [];
  for (let first = 0; first < planes.length; first++) {
    if (first === targetIndex || !planes[first]) continue;
    for (let second = first + 1; second < planes.length; second++) {
      if (second === targetIndex || !planes[second]) continue;
      const point = intersectPlanes(targetPlane, planes[first], planes[second]);
      if (!point) continue;
      const inside = planes.every(
        (plane) => !plane || dot(plane.normal, point) <= plane.distance + 0.05
      );
      if (!inside) continue;
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
  if (vertices.length !== 4) return null;

  const center = centroid(vertices);
  const firstAxis = normalized(subtract(vertices[0], center));
  if (!firstAxis) return null;
  const secondAxis = normalized(cross(targetPlane.normal, firstAxis));
  if (!secondAxis) return null;
  return vertices.sort((left, right) => {
    const leftDelta = subtract(left, center);
    const rightDelta = subtract(right, center);
    return (
      Math.atan2(dot(leftDelta, secondAxis), dot(leftDelta, firstAxis)) -
      Math.atan2(dot(rightDelta, secondAxis), dot(rightDelta, firstAxis))
    );
  });
}

function parseDisplacementRows(dispInfo, blockName, gridSize, tupleSize) {
  const block = children(dispInfo.children, blockName)[0];
  if (!block) return null;
  const rows = [];
  for (let rowIndex = 0; rowIndex < gridSize; rowIndex++) {
    const numbers = value(block.children, `row${rowIndex}`)
      .trim()
      .split(/\s+/)
      .map(Number);
    if (
      numbers.length < gridSize * tupleSize ||
      numbers.some((number) => !Number.isFinite(number))
    ) {
      return null;
    }
    if (tupleSize === 1) {
      rows.push(numbers.slice(0, gridSize));
    } else {
      rows.push(
        Array.from({ length: gridSize }, (_, columnIndex) =>
          numbers.slice(columnIndex * tupleSize, (columnIndex + 1) * tupleSize)
        )
      );
    }
  }
  return rows;
}

function bilinearPoint(p00, p10, p01, p11, u, v) {
  return add(
    scale(p00, (1 - u) * (1 - v)),
    scale(p10, u * (1 - v)),
    scale(p01, (1 - u) * v),
    scale(p11, u * v)
  );
}

function linearPoint(start, end, amount) {
  return add(scale(start, 1 - amount), scale(end, amount));
}

function displacementPatch(
  grid,
  startRow,
  endRow,
  startColumn,
  endColumn,
  visibleMaterial,
  reverseColumns
) {
  const controlHeight = 2 * (endRow - startRow) + 1;
  const controlWidth = 2 * (endColumn - startColumn) + 1;
  const lines = [
    "{",
    "patchDef2",
    "{",
    visibleMaterial.texture,
    `( ${controlWidth} ${controlHeight} 0 0 0 )`,
    "(",
  ];
  for (let rowOffset = 0; rowOffset < controlHeight; rowOffset++) {
    const controlPoints = [];
    for (let columnOffset = 0; columnOffset < controlWidth; columnOffset++) {
      const row = startRow + rowOffset / 2;
      const orientedColumn = startColumn + columnOffset / 2;
      const column = reverseColumns
        ? grid.length - 1 - orientedColumn
        : orientedColumn;
      const row0 = Math.floor(row);
      const row1 = Math.ceil(row);
      const column0 = Math.floor(column);
      const column1 = Math.ceil(column);
      const point = bilinearPoint(
        grid[row0][column0].point,
        grid[row0][column1].point,
        grid[row1][column0].point,
        grid[row1][column1].point,
        column - column0,
        row - row0
      );
      controlPoints.push(
        `( ${point.map(fmt).join(" ")} ${fmt(column / 2)} ${fmt(row / 2)} )`
      );
    }
    lines.push(`( ${controlPoints.join(" ")} )`);
  }
  lines.push(")", "}", "}");
  return lines.join("\n");
}

function displacementSkirtPatch(
  displacedEdge,
  baseEdge,
  visibleMaterial,
  solidCenter
) {
  const maxGapSquared = displacedEdge.reduce((maximum, point, index) => {
    const delta = subtract(point, baseEdge[index]);
    return Math.max(maximum, dot(delta, delta));
  }, 0);
  if (maxGapSquared < 0.25) return null;

  let patchNormal = null;
  for (let index = 0; index < displacedEdge.length - 1; index++) {
    const along = subtract(displacedEdge[index + 1], displacedEdge[index]);
    const across = subtract(baseEdge[index], displacedEdge[index]);
    patchNormal = normalized(cross(along, across));
    if (patchNormal) break;
  }
  if (!patchNormal) return null;

  const outward = subtract(
    centroid([...displacedEdge, ...baseEdge]),
    solidCenter
  );
  // As with the main terrain patch, AA draws the side opposite the
  // mathematical cross-product normal.
  const reverseColumns = dot(patchNormal, outward) > 0;
  const controlWidth = 2 * (displacedEdge.length - 1) + 1;
  const lines = [
    "{",
    "patchDef2",
    "{",
    visibleMaterial.texture,
    // MOHAA's legacy parser treats the first dimension as the number of
    // row records and the second as the points in each row.
    `( 3 ${controlWidth} 0 0 0 )`,
    "(",
  ];

  function sampleEdge(edge, samplePosition) {
    const first = Math.floor(samplePosition);
    const second = Math.ceil(samplePosition);
    return linearPoint(
      edge[first],
      edge[second],
      samplePosition - first
    );
  }

  for (let rowOffset = 0; rowOffset < 3; rowOffset++) {
    const acrossAmount = rowOffset / 2;
    const controlPoints = [];
    for (let columnOffset = 0; columnOffset < controlWidth; columnOffset++) {
      const orientedPosition = columnOffset / 2;
      const samplePosition = reverseColumns
        ? displacedEdge.length - 1 - orientedPosition
        : orientedPosition;
      const displaced = sampleEdge(displacedEdge, samplePosition);
      const base = sampleEdge(baseEdge, samplePosition);
      const point = linearPoint(displaced, base, acrossAmount);
      controlPoints.push(
        `( ${point.map(fmt).join(" ")} ${fmt(samplePosition / 2)} ${fmt(
          acrossAmount
        )} )`
      );
    }
    lines.push(`( ${controlPoints.join(" ")} )`);
  }
  lines.push(")", "}", "}");
  return lines.join("\n");
}

function displacementNeedsSkirts(sourceMaterial) {
  // Seams matter on traversable terrain, where a Source displacement can lift
  // away from its backing brush. Roof shingles, timber beams, wall trims, and
  // other architectural displacements already sit against surrounding
  // geometry; giving every one four curved skirts multiplies Q3map's patch
  // workload without improving the playable silhouette.
  return /(grass|dirt|ground|cobble|flagstone|stone_floor|floor_0|road|path|rock|rubble)/i.test(
    sourceMaterial
  );
}

function planarSeamUnderlayPatch(surface) {
  const expansion = 24;
  const depth = 12;
  const center = centroid(surface.vertices);
  const expanded = surface.vertices.map((point) => {
    const deltaX = point[0] - center[0];
    const deltaY = point[1] - center[1];
    const length = Math.hypot(deltaX, deltaY) || 1;
    return [
      point[0] + (deltaX / length) * expansion - surface.normal[0] * depth,
      point[1] + (deltaY / length) * expansion - surface.normal[1] * depth,
      point[2] - surface.normal[2] * depth,
    ];
  });

  let p00 = expanded[0];
  let p10 = expanded[1];
  let p01 = expanded[3];
  let p11 = expanded[2];
  const mathematicalNormal = normalized(
    cross(subtract(p10, p00), subtract(p01, p00))
  );
  if (!mathematicalNormal) return null;
  // AA draws the side opposite the patch's mathematical normal.
  if (dot(mathematicalNormal, surface.normal) > 0) {
    [p00, p10] = [p10, p00];
    [p01, p11] = [p11, p01];
  }

  const material = materialFor(surface.sourceMaterial);
  const lines = [
    "{",
    "patchDef2",
    "{",
    material.texture,
    "( 3 3 0 0 0 )",
    "(",
  ];
  for (let row = 0; row < 3; row++) {
    const v = row / 2;
    const controls = [];
    for (let column = 0; column < 3; column++) {
      const u = column / 2;
      const point = bilinearPoint(p00, p10, p01, p11, u, v);
      controls.push(
        `( ${point.map(fmt).join(" ")} ${fmt(u)} ${fmt(v)} )`
      );
    }
    lines.push(`( ${controls.join(" ")} )`);
  }
  lines.push(")", "}", "}");
  return lines.join("\n");
}

function displacementBrushes(side, solidCenter, solidSides, stats) {
  const verticesBlock = children(side.children, "vertices_plus")[0];
  const dispInfo = children(side.children, "dispinfo")[0];
  if (!dispInfo) {
    stats.displacementFailureNoInfo++;
    return null;
  }
  const outer = verticesBlock
    ? verticesBlock.children
        .filter((entry) => entry.key === "v")
        .map((entry) => parseVector(entry.value))
    : reconstructedFaceVertices(solidSides, side, solidCenter);
  if (!outer || outer.length !== 4) {
    stats.displacementFailureNoQuad++;
    return null;
  }

  const power = Number(value(dispInfo.children, "power"));
  const gridSize = 2 ** power + 1;
  if (![5, 9, 17].includes(gridSize)) {
    stats.displacementFailurePower++;
    return null;
  }

  const startPosition = parseVector(value(dispInfo.children, "startposition"));
  if (startPosition.length !== 3 || startPosition.some((number) => !Number.isFinite(number))) {
    stats.displacementFailureStart++;
    return null;
  }
  const startIndex = outer.reduce(
    (best, point, index) => {
      const distanceSquared = point.reduce(
        (sum, component, axis) =>
          sum + (component - startPosition[axis]) ** 2,
        0
      );
      return distanceSquared < best.distanceSquared
        ? { index, distanceSquared }
        : best;
    },
    { index: -1, distanceSquared: Number.POSITIVE_INFINITY }
  );
  if (startIndex.index < 0 || startIndex.distanceSquared > 1) {
    stats.displacementFailureStart++;
    return null;
  }

  // VMF rows begin at startposition. With the side's cyclic vertex order,
  // columns advance toward the previous corner and rows toward the next one.
  const p00 = outer[startIndex.index];
  const p10 = outer[(startIndex.index + 3) % 4];
  const p01 = outer[(startIndex.index + 1) % 4];
  const p11 = outer[(startIndex.index + 2) % 4];
  const normals = parseDisplacementRows(dispInfo, "normals", gridSize, 3);
  const distances = parseDisplacementRows(dispInfo, "distances", gridSize, 1);
  const offsets = children(dispInfo.children, "offsets").length
    ? parseDisplacementRows(dispInfo, "offsets", gridSize, 3)
    : Array.from({ length: gridSize }, () =>
        Array.from({ length: gridSize }, () => [0, 0, 0])
      );
  if (!normals || !distances || !offsets) {
    stats.displacementFailureRows++;
    return null;
  }

  const grid = Array.from({ length: gridSize }, (_, rowIndex) =>
    Array.from({ length: gridSize }, (_, columnIndex) => {
      const u = columnIndex / (gridSize - 1);
      const v = rowIndex / (gridSize - 1);
      const base = bilinearPoint(p00, p10, p01, p11, u, v);
      return {
        row: rowIndex,
        column: columnIndex,
        base,
        point: add(
          base,
          offsets[rowIndex][columnIndex],
          scale(normals[rowIndex][columnIndex], distances[rowIndex][columnIndex])
        ),
      };
    })
  );

  const sourceMaterial = value(side.children, "material");
  const visibleMaterial = materialFor(sourceMaterial);
  const patchNormal = normalized(
    cross(
      subtract(grid[0][1].point, grid[0][0].point),
      subtract(grid[1][0].point, grid[0][0].point)
    )
  );
  if (!patchNormal) {
    stats.displacementFailureNormal++;
    return null;
  }
  const outward = subtract(centroid(outer), solidCenter);
  // MOHAA/Q3 patch draw winding is opposite the mathematical normal formed
  // by cross(columnAdvance, rowAdvance). Reverse columns when that normal
  // points out of the source solid so the rendered side faces playable air.
  const reverseColumns = dot(patchNormal, outward) > 0;
  const patches = [];
  const maxSourceSpan = 8;
  for (let rowIndex = 0; rowIndex < gridSize - 1; rowIndex += maxSourceSpan) {
    const endRow = Math.min(rowIndex + maxSourceSpan, gridSize - 1);
    for (
      let columnIndex = 0;
      columnIndex < gridSize - 1;
      columnIndex += maxSourceSpan
    ) {
      const endColumn = Math.min(
        columnIndex + maxSourceSpan,
        gridSize - 1
      );
      patches.push(
        displacementPatch(
          grid,
          rowIndex,
          endRow,
          columnIndex,
          endColumn,
          visibleMaterial,
          reverseColumns
        )
      );
    }
  }
  const surfacePatchCount = patches.length;
  let skirtPatchCount = 0;
  let skirtTriangleCount = 0;
  if (displacementNeedsSkirts(sourceMaterial)) {
    const skirtEdges = [
      grid[0],
      grid[gridSize - 1],
      grid.map((row) => row[0]),
      grid.map((row) => row[gridSize - 1]),
    ];
    for (const edge of skirtEdges) {
      for (
        let startIndex = 0;
        startIndex < edge.length - 1;
        startIndex += maxSourceSpan
      ) {
        const endIndex = Math.min(
          startIndex + maxSourceSpan,
          edge.length - 1
        );
        const segment = edge.slice(startIndex, endIndex + 1);
        const skirt = displacementSkirtPatch(
          segment.map((sample) => sample.point),
          segment.map((sample) => sample.base),
          visibleMaterial,
          solidCenter
        );
        if (!skirt) continue;
        patches.push(skirt);
        skirtPatchCount++;
        skirtTriangleCount += 2 * (segment.length - 1);
      }
    }
  }

  patches.surfacePatchCount = surfacePatchCount;
  patches.skirtPatchCount = skirtPatchCount;
  patches.triangleCount = 2 * (gridSize - 1) ** 2;
  patches.skirtTriangleCount = skirtTriangleCount;
  patches.reversed = reverseColumns;
  return patches;
}

function convertSolid(solid, isDetail, stats) {
  const sides = children(solid.children, "side");
  if (sides.length < 4) {
    stats.invalid++;
    return null;
  }

  const sourceMaterials = sides.map((side) => value(side.children, "material"));
  if (
    isDetail &&
    sourceMaterials.some((material) => /skybox/i.test(material))
  ) {
    stats.sourceSkySkipped++;
    return null;
  }
  const allHelper = sourceMaterials.every((material) =>
    helperMaterial.test(material)
  );
  const sourcePlayerClip =
    allHelper &&
    sourceMaterials.some((material) =>
      /tools\/toolsplayerclip/i.test(material)
    );
  const sourceClipMaterial =
    allHelper &&
    sourceMaterials.some((material) =>
      /tools\/toolsclip(?:_|$)/i.test(material)
    );
  let sourceLargeClip = false;
  let sourceLargeClipBounds = null;
  if (sourceClipMaterial) {
    const helperPoints = pointsForSolid(solid);
    if (helperPoints.length) {
      const helperMin = [0, 1, 2].map((axis) =>
        Math.min(...helperPoints.map((point) => point[axis]))
      );
      const helperMax = [0, 1, 2].map((axis) =>
        Math.max(...helperPoints.map((point) => point[axis]))
      );
      const helperExtents = helperMax.map(
        (component, axis) => component - helperMin[axis]
      );
      sourceLargeClip = Math.max(...helperExtents) >= 512;
      if (sourceLargeClip) {
        sourceLargeClipBounds = { min: helperMin, max: helperMax };
      }
    }
  }
  if (allHelper && !sourcePlayerClip && !sourceLargeClip) {
    for (const material of new Set(sourceMaterials.map((item) => item.toLowerCase()))) {
      stats.helperBrushesByMaterial[material] =
        (stats.helperBrushesByMaterial[material] || 0) + 1;
    }
    stats.helperSkipped++;
    return null;
  }

  const solidPoints = pointsForSolid(solid);
  if (!solidPoints.length) {
    stats.invalid++;
    return null;
  }
  const center = centroid(solidPoints);
  if (!inPlayableArea(center)) {
    stats.skyboxSkipped++;
    return null;
  }
  if (sourcePlayerClip) {
    stats.sourcePlayerClipBrushes++;
    stats.sourcePlayerClipBounds.push({
      min: [0, 1, 2].map((axis) =>
        Math.min(...solidPoints.map((point) => point[axis]))
      ),
      max: [0, 1, 2].map((axis) =>
        Math.max(...solidPoints.map((point) => point[axis]))
      ),
    });
  }
  if (sourceLargeClip) {
    stats.sourceLargeClipBrushes++;
    stats.sourceLargeClipBounds.push(sourceLargeClipBounds);
  }

  // Source commonly exposes only one or two faces of a convex construction
  // brush and marks the remaining faces nodraw. When the covering Source
  // displacement/model is unavailable, leaving those faces as AA caulk makes
  // literal sky holes. Reuse the brush's own visible material on nodraw faces;
  // buried/shared faces are still removed by Q3map, while genuinely exposed
  // support faces remain closed.
  const fallbackSourceMaterial = sourceMaterials.find(
    (material) =>
      !nodrawMaterial.test(material) &&
      !helperMaterial.test(material) &&
      !/skybox/i.test(material)
  );
  const nodrawFallback = fallbackSourceMaterial
    ? materialFor(fallbackSourceMaterial)
    : null;

  const displacementSides = sides.filter(
    (side) => children(side.children, "dispinfo").length > 0
  );
  if (displacementSides.length && displacementMode === "full") {
    const rebuilt = [];
    let rebuiltSides = 0;
    let rebuiltTriangles = 0;
    let rebuiltSurfacePatches = 0;
    let rebuiltSkirtPatches = 0;
    let rebuiltSkirtTriangles = 0;
    let rebuiltFlipped = 0;
    for (const side of displacementSides) {
      const brushes = displacementBrushes(side, center, sides, stats);
      if (!brushes?.length) {
        stats.displacementSkipped++;
        continue;
      }
      rebuilt.push(...brushes);
      rebuiltSides++;
      rebuiltTriangles += brushes.triangleCount;
      rebuiltSurfacePatches += brushes.surfacePatchCount;
      rebuiltSkirtPatches += brushes.skirtPatchCount;
      rebuiltSkirtTriangles += brushes.skirtTriangleCount;
      if (brushes.reversed) rebuiltFlipped++;
    }
    if (!rebuilt.length) {
      stats.invalid++;
      return null;
    }
    stats.displacementRebuilt += rebuiltSides;
    stats.displacementPatches += rebuilt.length;
    stats.displacementSurfacePatches += rebuiltSurfacePatches;
    stats.displacementSkirtPatches += rebuiltSkirtPatches;
    stats.displacementTriangles += rebuiltTriangles;
    stats.displacementSkirtTriangles += rebuiltSkirtTriangles;
    stats.displacementWindingFlipped += rebuiltFlipped;

    // A Source displacement belongs to a backing brush. Emitting only its
    // curved face leaves the underside and perimeter open in the AA BSP,
    // exposing sky or the one-sided back of the patch. Preserve the source
    // brush as a support hull: caulk the displaced base plane and texture
    // helper-only perimeter faces with the displacement material so exposed
    // edges remain visually closed.
    const displacementSideSet = new Set(displacementSides);
    const supportMaterial = materialFor(
      value(displacementSides[0].children, "material")
    );
    const supportLines = ["{"];
    for (const side of sides) {
      const plane = parsePlane(value(side.children, "plane"));
      if (!plane) {
        stats.invalid++;
        return null;
      }
      const sourceMaterial = value(side.children, "material");
      const material = displacementSideSet.has(side)
        ? targetMaterials.caulk
        : helperMaterial.test(sourceMaterial)
          ? supportMaterial
          : materialFor(sourceMaterial);
      const detailSuffix =
        isDetail && material !== targetMaterials.sky
          ? " +surfaceparm detail"
          : "";
      supportLines.push(
        `${plane.map(formatPoint).join(" ")} ${material.texture} 0 0 0 0.5 0.5 ${
          material.contentFlags
        } ${material.surfaceFlags} 0${detailSuffix}`
      );
    }
    supportLines.push("}");
    stats.converted++;
    stats.displacementSupports++;
    if (isDetail) stats.detail++;
    return `${supportLines.join("\n")}\n${rebuilt.join("\n")}`;
  }
  if (displacementSides.length) {
    // The baseline build keeps the original backing brush and its visible
    // material. This preserves sealing and collision while avoiding thousands
    // of curved patches that make MOHAA's 2002-era Q3map impractical. A later
    // fidelity pass can opt into exact curved reconstruction with
    // --full-displacements.
    stats.displacementPlanarized += displacementSides.length;
  }

  const lines = ["{"];
  for (const side of sides) {
    const plane = parsePlane(value(side.children, "plane"));
    if (!plane) {
      stats.invalid++;
      return null;
    }
    const sourceMaterial = value(side.children, "material");
    const useNodrawFallback =
      nodrawFallback && nodrawMaterial.test(sourceMaterial);
    const material = sourcePlayerClip
      ? targetMaterials.playerClip
      : sourceLargeClip
        ? targetMaterials.clip
        : useNodrawFallback
          ? nodrawFallback
          : materialFor(sourceMaterial);
    if (useNodrawFallback) stats.nodrawFallbackFaces++;
    const detailSuffix = isDetail && material !== targetMaterials.sky ? " +surfaceparm detail" : "";
    lines.push(
      `${plane.map(formatPoint).join(" ")} ${material.texture} 0 0 0 0.5 0.5 ${
        material.contentFlags
      } ${material.surfaceFlags} 0${detailSuffix}`
    );
  }
  lines.push("}");
  stats.converted++;
  if (isDetail) stats.detail++;
  return lines.join("\n");
}

function face(
  points,
  materialOrTexture,
  isDetail = true,
  surfaceParms = ""
) {
  const material =
    typeof materialOrTexture === "string"
      ? targetByTexture.get(materialOrTexture) || targetMaterials.concreteLight
      : materialOrTexture;
  const suffix = [
    isDetail ? "+surfaceparm detail" : "",
    surfaceParms,
  ]
    .filter(Boolean)
    .join(" ");
  return `${points.map(formatPoint).join(" ")} ${material.texture} 0 0 0 0.5 0.5 ${
    material.contentFlags
  } ${material.surfaceFlags} 0${suffix ? ` ${suffix}` : ""}`;
}

function boxBrush(min, max, material, surfaceParms = "", isDetail = true) {
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  return [
    "{",
    face(
      [[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]],
      material,
      isDetail,
      surfaceParms
    ),
    face(
      [[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]],
      material,
      isDetail,
      surfaceParms
    ),
    face(
      [[16, minY, -16], [0, minY, 0], [16, minY, 16]],
      material,
      isDetail,
      surfaceParms
    ),
    face(
      [[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]],
      material,
      isDetail,
      surfaceParms
    ),
    face(
      [[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]],
      material,
      isDetail,
      surfaceParms
    ),
    face(
      [[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]],
      material,
      isDetail,
      surfaceParms
    ),
    "}",
  ].join("\n");
}

function verticalPanelBrush(
  origin,
  yaw,
  width,
  height,
  material,
  thickness = 4,
  surfaceParms = ""
) {
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  const halfThickness = thickness / 2;
  const quarterTurns = ((Math.round(yaw / 90) % 4) + 4) % 4;
  if (quarterTurns % 2 === 0) {
    return boxBrush(
      [
        origin[0] - halfThickness,
        origin[1] - halfWidth,
        origin[2] - halfHeight,
      ],
      [
        origin[0] + halfThickness,
        origin[1] + halfWidth,
        origin[2] + halfHeight,
      ],
      material,
      surfaceParms
    );
  }
  return boxBrush(
    [
      origin[0] - halfWidth,
      origin[1] - halfThickness,
      origin[2] - halfHeight,
    ],
    [
      origin[0] + halfWidth,
      origin[1] + halfThickness,
      origin[2] + halfHeight,
    ],
    material,
    surfaceParms
  );
}

function archFrameBrushes(
  origin,
  yaw,
  width,
  height,
  material,
  frameWidth = 20,
  depth = 8
) {
  const centerZ = origin[2] + height / 2;
  const sideHeight = height - frameWidth;
  const horizontal = ((Math.round(yaw / 90) % 2) + 2) % 2 === 1;
  const left = [...origin];
  const right = [...origin];
  if (horizontal) {
    left[0] -= width / 2 - frameWidth / 2;
    right[0] += width / 2 - frameWidth / 2;
  } else {
    left[1] -= width / 2 - frameWidth / 2;
    right[1] += width / 2 - frameWidth / 2;
  }
  left[2] = origin[2] + sideHeight / 2;
  right[2] = left[2];
  const top = [origin[0], origin[1], origin[2] + height - frameWidth / 2];
  return [
    verticalPanelBrush(
      left,
      yaw,
      frameWidth,
      sideHeight,
      material,
      depth,
      "-surfaceparm solid"
    ),
    verticalPanelBrush(
      right,
      yaw,
      frameWidth,
      sideHeight,
      material,
      depth,
      "-surfaceparm solid"
    ),
    verticalPanelBrush(
      top,
      yaw,
      width,
      frameWidth,
      material,
      depth,
      "-surfaceparm solid"
    ),
  ];
}

function cylinderBrush(origin, minZ, maxZ, radius, material, sides = 8) {
  const [centerX, centerY] = origin;
  const vertices = Array.from({ length: sides }, (_, index) => {
    const angle = (index / sides) * Math.PI * 2;
    return [centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius];
  });
  const lines = ["{"];
  for (let index = 0; index < sides; index++) {
    const current = vertices[index];
    const next = vertices[(index + 1) % sides];
    lines.push(
      face(
        [
          [next[0], next[1], minZ],
          [current[0], current[1], minZ],
          [current[0], current[1], maxZ],
        ],
        material
      )
    );
  }
  lines.push(
    face(
      [
        [centerX - 16, centerY + 16, minZ],
        [centerX, centerY, minZ],
        [centerX + 16, centerY + 16, minZ],
      ],
      material
    )
  );
  lines.push(
    face(
      [
        [centerX + 16, centerY + 16, maxZ],
        [centerX, centerY, maxZ],
        [centerX - 16, centerY + 16, maxZ],
      ],
      material
    )
  );
  lines.push("}");
  return lines.join("\n");
}

function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, propertyValue] of Object.entries(properties)) {
    lines.push(`"${key}" "${propertyValue}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function brushEntity(classname, properties, brushes) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, propertyValue] of Object.entries(properties)) {
    lines.push(`"${key}" "${propertyValue}"`);
  }
  for (const brush of brushes) lines.push(brush);
  lines.push("}");
  return lines.join("\n");
}

function rotatedLocalBounds(origin, yaw, localMin, localMax) {
  const radians = (yaw * Math.PI) / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const corners = [];
  for (const x of [localMin[0], localMax[0]]) {
    for (const y of [localMin[1], localMax[1]]) {
      for (const z of [localMin[2], localMax[2]]) {
        corners.push([
          origin[0] + x * cosine - y * sine,
          origin[1] + x * sine + y * cosine,
          origin[2] + z,
        ]);
      }
    }
  }
  return {
    min: [0, 1, 2].map((axis) =>
      Math.min(...corners.map((corner) => corner[axis]))
    ),
    max: [0, 1, 2].map((axis) =>
      Math.max(...corners.map((corner) => corner[axis]))
    ),
  };
}

function inPlayableArea(origin) {
  return (
    origin[0] > -2400 &&
    origin[0] < 3200 &&
    origin[1] > -1350 &&
    origin[1] < 4200 &&
    origin[2] > -320 &&
    origin[2] < 960
  );
}

function pointInConvexPolygonXY(point, vertices) {
  let hasPositive = false;
  let hasNegative = false;
  for (let index = 0; index < vertices.length; index++) {
    const start = vertices[index];
    const end = vertices[(index + 1) % vertices.length];
    const crossZ =
      (end[0] - start[0]) * (point[1] - start[1]) -
      (end[1] - start[1]) * (point[0] - start[0]);
    if (crossZ > 0.05) hasPositive = true;
    if (crossZ < -0.05) hasNegative = true;
    if (hasPositive && hasNegative) return false;
  }
  return true;
}

function collectPlanarDisplacementSupports(solid, surfaces) {
  const sides = children(solid.children, "side");
  const points = pointsForSolid(solid);
  if (sides.length < 4 || !points.length) return;
  const center = centroid(points);
  if (!inPlayableArea(center)) return;
  for (const side of sides) {
    if (!children(side.children, "dispinfo").length) continue;
    const vertices = reconstructedFaceVertices(sides, side, center);
    const planePoints = parsePlane(value(side.children, "plane"));
    const plane = planePoints ? brushPlane(planePoints, center) : null;
    if (!vertices || !plane || plane.normal[2] < 0.2) continue;
    surfaces.push({
      vertices,
      normal: plane.normal,
      distance: plane.distance,
      sourceMaterial: value(side.children, "material"),
      minX: Math.min(...vertices.map((point) => point[0])),
      maxX: Math.max(...vertices.map((point) => point[0])),
      minY: Math.min(...vertices.map((point) => point[1])),
      maxY: Math.max(...vertices.map((point) => point[1])),
    });
  }
}

function snapOriginToPlanarSupport(origin, surfaces, stats) {
  let best = null;
  let closest = null;
  for (const surface of surfaces) {
    if (
      origin[0] < surface.minX - 0.1 ||
      origin[0] > surface.maxX + 0.1 ||
      origin[1] < surface.minY - 0.1 ||
      origin[1] > surface.maxY + 0.1 ||
      !pointInConvexPolygonXY(origin, surface.vertices)
    ) {
      continue;
    }
    const z =
      (surface.distance -
        surface.normal[0] * origin[0] -
        surface.normal[1] * origin[1]) /
      surface.normal[2];
    const drop = origin[2] - z;
    if (!closest || Math.abs(drop) < Math.abs(closest.drop)) {
      closest = { z, drop };
    }
    if (drop < -8 || drop > 64) continue;
    if (!best || Math.abs(drop) < Math.abs(best.drop)) best = { z, drop };
  }
  if (!best) {
    return {
      origin: [...origin],
      excessiveCorrection: Boolean(closest),
    };
  }
  if (Math.abs(best.drop) < 0.5) {
    return { origin: [...origin], excessiveCorrection: false };
  }
  stats.propsGroundSnapped++;
  stats.maximumPropGroundAdjustment = Math.max(
    stats.maximumPropGroundAdjustment,
    Math.abs(best.drop)
  );
  return {
    origin: [origin[0], origin[1], best.z],
    excessiveCorrection: false,
  };
}

function isUnsafeArchitecturalPlaceholder(model) {
  return (
    /models\/props\/de_cbble\/arch_[^/]+\//.test(model) ||
    /models\/props\/de_cbble\/port_(a|b|c|sect_a)\//.test(model) ||
    /models\/props\/de_cbble\/window_[^/]+\//.test(model) ||
    model.includes("/door_a/") ||
    model.includes("metal_grate")
  );
}

function receivesGroundedSubstitute(model) {
  return (
    model.includes("barrel_a") ||
    model.includes("oildrum") ||
    model.includes("hay_bail") ||
    model.includes("/coffin/") ||
    model.includes("/pine_a/") ||
    model.includes("urban_bush") ||
    model.includes("mall_fern") ||
    model.includes("balcony_planter") ||
    model.includes("crate")
  );
}

const vmfText = fs.readFileSync(referencePath, "utf8");
const rootEntries = parseEntries(tokenize(vmfText), { index: 0 });
const world = children(rootEntries, "world")[0];
const sourceEntities = children(rootEntries, "entity");
const stats = {
  converted: 0,
  detail: 0,
  helperSkipped: 0,
  detailSolidsSkipped: 0,
  compileBudgetDetailSkipped: 0,
  skyboxSkipped: 0,
  invalid: 0,
  displacementRebuilt: 0,
  displacementPatches: 0,
  displacementSurfacePatches: 0,
  displacementSkirtPatches: 0,
  displacementTriangles: 0,
  displacementSkirtTriangles: 0,
  displacementWindingFlipped: 0,
  displacementSupports: 0,
  displacementPlanarized: 0,
  displacementSkipped: 0,
  displacementFailureNoInfo: 0,
  displacementFailureNoQuad: 0,
  displacementFailurePower: 0,
  displacementFailureStart: 0,
  displacementFailureRows: 0,
  displacementFailureNormal: 0,
  nodrawFallbackFaces: 0,
  unsupportedPropsSkipped: 0,
  helperBrushesByMaterial: {},
  sourcePlayerClipBrushes: 0,
  sourcePlayerClipBounds: [],
  sourceLargeClipBrushes: 0,
  sourceLargeClipBounds: [],
  planarSeamUnderlays: 0,
  vegetationOmittedForGrounding: 0,
  unsafeArchitecturalPropsSkipped: 0,
  displacementSupportSurfaces: 0,
  propsGroundSnapped: 0,
  maximumPropGroundAdjustment: 0,
  coverBrushes: 0,
  archFrames: 0,
  facadePanels: 0,
  barrels: 0,
  hayBales: 0,
  trees: 0,
  bushes: 0,
  stockProps: 0,
  sourceLights: 0,
  sourceLightCandidates: 0,
  sourceLightsDeduplicated: 0,
  fillLights: 0,
  rotatingDoors: 0,
  unverifiedPropsOmitted: 0,
  sourceSkySkipped: 0,
  structuralSkyBrushes: 0,
  detailSizeBuckets: {
    under8: 0,
    under16: 0,
    under24: 0,
    under32: 0,
    under64: 0,
    atLeast64: 0,
  },
  detailVolumeBuckets: {
    under4k: 0,
    under16k: 0,
    under64k: 0,
    under256k: 0,
    under1m: 0,
    atLeast1m: 0,
  },
  detailSecondExtentBuckets: {
    under16: 0,
    under32: 0,
    under48: 0,
    under64: 0,
    under96: 0,
    under128: 0,
    atLeast128: 0,
  },
};

const planarDisplacementSupports = [];
for (const solid of children(world.children, "solid")) {
  collectPlanarDisplacementSupports(solid, planarDisplacementSupports);
}
for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["func_detail", "func_brush", "func_breakable"].includes(classname)) continue;
  for (const solid of children(entity.children, "solid")) {
    collectPlanarDisplacementSupports(solid, planarDisplacementSupports);
  }
}
stats.displacementSupportSurfaces = planarDisplacementSupports.length;

const worldBrushes = [];
const stockPropEntities = [];
for (const solid of children(world.children, "solid")) {
  // Imported Source world brushes are internal geometry inside the explicit
  // structural sky shell below. Treating them as detail preserves collision
  // but prevents every castle trim plane from exploding the Q3 visibility
  // tree beyond MOHAA's fixed 2 MiB portal limit.
  const converted = convertSolid(solid, true, stats);
  if (converted) worldBrushes.push(converted);
}

const skyBounds = {
  min: [-2464, -1408, -384],
  max: [3264, 4256, 1152],
  thickness: 64,
};
const [skyMinX, skyMinY, skyMinZ] = skyBounds.min;
const [skyMaxX, skyMaxY, skyMaxZ] = skyBounds.max;
const skyShell = [
  boxBrush(
    [skyMinX, skyMinY, skyMinZ],
    [skyMinX + skyBounds.thickness, skyMaxY, skyMaxZ],
    targetMaterials.sky,
    "",
    false
  ),
  boxBrush(
    [skyMaxX - skyBounds.thickness, skyMinY, skyMinZ],
    [skyMaxX, skyMaxY, skyMaxZ],
    targetMaterials.sky,
    "",
    false
  ),
  boxBrush(
    [skyMinX + skyBounds.thickness, skyMinY, skyMinZ],
    [skyMaxX - skyBounds.thickness, skyMinY + skyBounds.thickness, skyMaxZ],
    targetMaterials.sky,
    "",
    false
  ),
  boxBrush(
    [skyMinX + skyBounds.thickness, skyMaxY - skyBounds.thickness, skyMinZ],
    [skyMaxX - skyBounds.thickness, skyMaxY, skyMaxZ],
    targetMaterials.sky,
    "",
    false
  ),
  boxBrush(
    [
      skyMinX + skyBounds.thickness,
      skyMinY + skyBounds.thickness,
      skyMinZ,
    ],
    [
      skyMaxX - skyBounds.thickness,
      skyMaxY - skyBounds.thickness,
      skyMinZ + skyBounds.thickness,
    ],
    targetMaterials.sky,
    "",
    false
  ),
  boxBrush(
    [
      skyMinX + skyBounds.thickness,
      skyMinY + skyBounds.thickness,
      skyMaxZ - skyBounds.thickness,
    ],
    [
      skyMaxX - skyBounds.thickness,
      skyMaxY - skyBounds.thickness,
      skyMaxZ,
    ],
    targetMaterials.sky,
    "",
    false
  ),
];
worldBrushes.push(...skyShell);
stats.structuralSkyBrushes = skyShell.length;

if (displacementMode === "planar") {
  for (const surface of planarDisplacementSupports) {
    if (!displacementNeedsSkirts(surface.sourceMaterial)) continue;
    const underlay = planarSeamUnderlayPatch(surface);
    if (!underlay) continue;
    worldBrushes.push(underlay);
    stats.planarSeamUnderlays++;
  }
}

for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["func_detail", "func_brush", "func_breakable"].includes(classname)) continue;
  for (const solid of children(entity.children, "solid")) {
    if (classname === "func_detail") {
      const extents = solidExtents(solid);
      const maximumExtent = extents ? Math.max(...extents) : 0;
      if (maximumExtent < 8) stats.detailSizeBuckets.under8++;
      else if (maximumExtent < 16) stats.detailSizeBuckets.under16++;
      else if (maximumExtent < 24) stats.detailSizeBuckets.under24++;
      else if (maximumExtent < 32) stats.detailSizeBuckets.under32++;
      else if (maximumExtent < 64) stats.detailSizeBuckets.under64++;
      else stats.detailSizeBuckets.atLeast64++;
      const volume = extents ? extents.reduce((product, extent) => product * extent, 1) : 0;
      if (volume < 4096) stats.detailVolumeBuckets.under4k++;
      else if (volume < 16384) stats.detailVolumeBuckets.under16k++;
      else if (volume < 65536) stats.detailVolumeBuckets.under64k++;
      else if (volume < 262144) stats.detailVolumeBuckets.under256k++;
      else if (volume < 1048576) stats.detailVolumeBuckets.under1m++;
      else stats.detailVolumeBuckets.atLeast1m++;
      const orderedExtents = extents ? [...extents].sort((a, b) => a - b) : [0, 0, 0];
      const secondExtent = orderedExtents[1];
      if (secondExtent < 16) stats.detailSecondExtentBuckets.under16++;
      else if (secondExtent < 32) stats.detailSecondExtentBuckets.under32++;
      else if (secondExtent < 48) stats.detailSecondExtentBuckets.under48++;
      else if (secondExtent < 64) stats.detailSecondExtentBuckets.under64++;
      else if (secondExtent < 96) stats.detailSecondExtentBuckets.under96++;
      else if (secondExtent < 128) stats.detailSecondExtentBuckets.under128++;
      else stats.detailSecondExtentBuckets.atLeast128++;
      // Diagnostic compile-budget mode keeps broad surfaces and hero-scale
      // detail but omits compact/narrow trim. It is never enabled silently:
      // the full measured baseline remains the default, and this mode must
      // pass visual review before it can become a release source.
      const compileCritical =
        secondExtent >= 128 ||
        volume >= 1048576 ||
        (maximumExtent >= 512 && secondExtent >= 64);
      if (compileBudgetMode && !compileCritical) {
        stats.detailSolidsSkipped++;
        stats.compileBudgetDetailSkipped++;
        continue;
      }
      // Keep every architectural detail solid in repair builds. The earlier
      // volume threshold removed thin wall skins, floors, and ceilings along
      // with cosmetic trim, leaving open sky holes and unsupported facade
      // props. The structural sky shell keeps these brushes from splitting
      // the visibility tree, so the tradeoff is compile time rather than BSP
      // portal overflow.
    }
    const converted = convertSolid(solid, true, stats);
    if (converted) worldBrushes.push(converted);
  }
}

// Reconstruct a deliberately small set of gameplay-significant castle props.
// Source-only trim, rubble, lamps, and cosmetic roof pieces remain omitted.
if (false) {
let pineSeen = 0;
let bushSeen = 0;
for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["prop_static", "prop_physics_multiplayer"].includes(classname)) continue;
  const model = value(entity.children, "model").toLowerCase();
  const origin = parseVector(value(entity.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;

  const angles = parseVector(value(entity.children, "angles", "0 0 0"));
  const yaw = Number.isFinite(angles[1]) ? angles[1] : 0;
  const pitch = Number.isFinite(angles[0]) ? angles[0] : 0;
  const roll = Number.isFinite(angles[2]) ? angles[2] : 0;
  if (
    architecturalPlaceholderMode === "omit" &&
    isUnsafeArchitecturalPlaceholder(model)
  ) {
    stats.unsafeArchitecturalPropsSkipped++;
    continue;
  }
  const grounding = receivesGroundedSubstitute(model)
    ? snapOriginToPlanarSupport(origin, planarDisplacementSupports, stats)
    : { origin: [...origin], excessiveCorrection: false };
  const groundedOrigin = grounding.origin;
  if (
    grounding.excessiveCorrection &&
    (model.includes("/pine_a/") ||
      model.includes("urban_bush") ||
      model.includes("mall_fern") ||
      model.includes("balcony_planter"))
  ) {
    stats.vegetationOmittedForGrounding++;
    continue;
  }
  let size = null;
  let height = null;
  let material = targetMaterials.crate;

  if (model.includes("/arch_") && !model.includes("pillar")) {
    worldBrushes.push(
      ...archFrameBrushes(origin, yaw, 128, 160, targetMaterials.stone, 36, 32)
    );
    stats.archFrames++;
    continue;
  } else if (
    model.includes("/port_a/") ||
    model.includes("/port_b/") ||
    model.includes("/port_c/")
  ) {
    worldBrushes.push(
      ...archFrameBrushes(origin, yaw, 256, 160, targetMaterials.darkStone, 56, 48)
    );
    stats.archFrames++;
    continue;
  } else if (model.includes("/port_sect_a/")) {
    worldBrushes.push(
      ...archFrameBrushes(origin, yaw, 128, 144, targetMaterials.darkStone, 40, 48)
    );
    stats.archFrames++;
    continue;
  } else if (model.includes("arch_g_pillar")) {
    worldBrushes.push(
      boxBrush(
        [origin[0] - 20, origin[1] - 20, origin[2]],
        [origin[0] + 20, origin[1] + 20, origin[2] + 160],
        targetMaterials.stone
      )
    );
    stats.coverBrushes++;
    continue;
  } else if (model.includes("/window_")) {
    const panelOrigin = [origin[0], origin[1], origin[2] + 40];
    worldBrushes.push(
      verticalPanelBrush(
        panelOrigin,
        yaw,
        64,
        model.includes("_half") ? 48 : 80,
        targetMaterials.shutter,
        4,
        "-surfaceparm solid"
      )
    );
    stats.facadePanels++;
    continue;
  } else if (model.includes("/door_a/")) {
    const panelOrigin = [origin[0], origin[1], origin[2] + 56];
    worldBrushes.push(
      verticalPanelBrush(
        panelOrigin,
        yaw,
        64,
        112,
        targetMaterials.door,
        4,
        "-surfaceparm solid"
      )
    );
    stats.facadePanels++;
    continue;
  } else if (model.includes("metal_grate")) {
    const panelOrigin = [origin[0], origin[1], origin[2] + 48];
    worldBrushes.push(
      verticalPanelBrush(
        panelOrigin,
        yaw,
        64,
        96,
        targetMaterials.grate,
        4,
        "-surfaceparm solid"
      )
    );
    stats.facadePanels++;
    continue;
  } else if (model.includes("barrel_a") || model.includes("oildrum")) {
    const normalizedPitch = ((pitch + 180) % 360 + 360) % 360 - 180;
    const normalizedRoll = ((roll + 180) % 360 + 360) % 360 - 180;
    if (Math.abs(normalizedPitch) > 25 || Math.abs(normalizedRoll) > 25) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    worldBrushes.push(
      cylinderBrush(
        groundedOrigin,
        groundedOrigin[2],
        groundedOrigin[2] + 48,
        22,
        targetMaterials.rustyMetal
      )
    );
    stats.coverBrushes++;
    stats.barrels++;
    continue;
  } else if (model.includes("hay_bail_stack")) {
    size = 80;
    height = 64;
    material = targetMaterials.grass;
    stats.hayBales++;
  } else if (model.includes("hay_bails")) {
    size = 48;
    height = 32;
    material = targetMaterials.grass;
    stats.hayBales++;
  } else if (model.includes("/coffin/")) {
    size = 72;
    height = 28;
    material = targetMaterials.wood;
  } else if (model.includes("/pine_a/")) {
    pineSeen++;
    if (pineSeen % 2 === 0) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    stockPropEntities.push(
      pointEntity("static_natural_tree_commontree", {
        origin: groundedOrigin.map(fmt).join(" "),
        angle: fmt(yaw),
        model: "static//tree_commontree.tik",
        scale: "0.7",
        testanim: "idle",
      })
    );
    stats.stockProps++;
    stats.trees++;
    continue;
  } else if (
    model.includes("urban_bush") ||
    model.includes("mall_fern") ||
    model.includes("balcony_planter")
  ) {
    bushSeen++;
    if (bushSeen % 4 !== 1) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    stockPropEntities.push(
      pointEntity("static_natural_bush_regularbush", {
        origin: groundedOrigin.map(fmt).join(" "),
        angle: fmt(yaw),
        model: "static//bush_regularbush.tik",
        scale: "0.8",
        testanim: "idle",
      })
    );
    stats.stockProps++;
    stats.bushes++;
    continue;
  } else if (model.includes("crate")) {
    size = 48;
    height = 48;
    material = targetMaterials.crate;
  } else {
    stats.unsupportedPropsSkipped++;
  }

  if (size && height) {
    const half = size / 2;
    worldBrushes.push(
      boxBrush(
        [
          groundedOrigin[0] - half,
          groundedOrigin[1] - half,
          groundedOrigin[2],
        ],
        [
          groundedOrigin[0] + half,
          groundedOrigin[1] + half,
          groundedOrigin[2] + height,
        ],
        material
      )
    );
    stats.coverBrushes++;
  }
}
}

// Inferno contains thousands of Source-only models. Their names do not encode
// trustworthy dimensions, so guessing brush substitutes would create floating
// cover, blocked routes, and fake walls. Preserve only topology represented by
// measured VMF brushes; count every omitted playable prop for the audit.
for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["prop_static", "prop_dynamic", "prop_physics_multiplayer"].includes(classname)) {
    continue;
  }
  const origin = parseVector(value(entity.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  stats.unsupportedPropsSkipped++;
  stats.unverifiedPropsOmitted++;
}

const generatedBrushEntities = [];
// Inferno has one genuine rotating interior door. These collision bounds were read
// directly from its embedded Source MDL header (IDST v49), not guessed.
for (const entity of sourceEntities) {
  if (value(entity.children, "classname") !== "prop_door_rotating") continue;
  const origin = parseVector(value(entity.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(value(entity.children, "angles", "0 0 0"));
  const yaw = Number.isFinite(angles[1]) ? angles[1] : 0;
  const bounds = rotatedLocalBounds(
    origin,
    yaw,
    [-4.2947, 0, -0.01],
    [4.2947, 55.5151, 111.621]
  );
  const doorBrush = boxBrush(
    bounds.min,
    bounds.max,
    targetMaterials.wood,
    "",
    false
  );
  const originBrush = boxBrush(
    [origin[0] - 4, origin[1] - 4, origin[2] - 4],
    [origin[0] + 4, origin[1] + 4, origin[2] + 4],
    targetMaterials.origin,
    "",
    false
  );
  generatedBrushEntities.push(
    brushEntity(
      "func_rotatingdoor",
      {
        doortype: "wood",
        angle: "90",
        alwaysaway: "1",
        speed: "200",
      },
      [doorBrush, originBrush]
    )
  );
  stats.rotatingDoors++;
}

const worldspawn = [
  "{",
  `"classname" "worldspawn"`,
  `"message" "Codex Inferno"` ,
  `"ambientlight" "8 9 12"`,
  `"suncolor" "148 128 102"`,
  `"sundirection" "325 212 0"`,
  `"sundiffusecolor" "62 72 92"`,
  `"sundiffuse" "1.15"`,
  `"_color" "0.98 0.99 1.0"`,
  `"farplane" "7600"`,
  `"farplane_color" "0.48 0.54 0.60"`,
  ...worldBrushes.map((brush, index) => `// brush ${index}\n${brush}`),
  "}",
].join("\n");

const entities = [worldspawn, ...generatedBrushEntities];
const terroristSpawns = [];
const counterSpawns = [];
const deathmatchSpawns = [];

for (const source of sourceEntities) {
  const classname = value(source.children, "classname");
  if (
    ![
      "info_player_terrorist",
      "info_player_counterterrorist",
      "info_deathmatch_spawn",
    ].includes(classname)
  ) {
    continue;
  }
  const origin = parseVector(value(source.children, "origin"));
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(value(source.children, "angles", "0 0 0"));
  const spawn = { origin, yaw: Number.isFinite(angles[1]) ? angles[1] : 0 };
  if (classname === "info_player_terrorist") terroristSpawns.push(spawn);
  else if (classname === "info_player_counterterrorist") counterSpawns.push(spawn);
  else deathmatchSpawns.push(spawn);
}

if (!terroristSpawns.length || !counterSpawns.length || !deathmatchSpawns.length) {
  throw new Error("Reference map spawns were not found");
}

const spectator = deathmatchSpawns[0];
entities.push(
  pointEntity("info_player_start", {
    origin: spectator.origin.map(fmt).join(" "),
    angle: fmt(spectator.yaw),
  })
);

for (const spawn of terroristSpawns) {
  const properties = {
    origin: spawn.origin.map(fmt).join(" "),
    angle: fmt(spawn.yaw),
  };
  entities.push(pointEntity("info_player_axis", properties));
}
for (const spawn of counterSpawns) {
  const properties = {
    origin: spawn.origin.map(fmt).join(" "),
    angle: fmt(spawn.yaw),
  };
  entities.push(pointEntity("info_player_allied", properties));
}
for (const spawn of deathmatchSpawns) {
  const properties = {
    origin: spawn.origin.map(fmt).join(" "),
    angle: fmt(spawn.yaw),
  };
  entities.push(pointEntity("info_player_deathmatch", properties));
}

const clusteredLights = new Map();
for (const source of sourceEntities) {
  const classname = value(source.children, "classname");
  if (!["light", "light_spot"].includes(classname)) continue;
  const origin = parseVector(value(source.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const sourceLight = parseVector(value(source.children, "_light", "255 230 200 400"));
  const sourceBrightness = sourceLight[3] || 400;
  stats.sourceLightCandidates++;
  const key = `${Math.round(origin[0] / 128)}:${Math.round(
    origin[1] / 128
  )}:${Math.round(origin[2] / 96)}`;
  const current = clusteredLights.get(key);
  if (!current || sourceBrightness > current.sourceBrightness) {
    clusteredLights.set(key, {
      classname,
      origin,
      sourceLight,
      sourceBrightness,
    });
  }
}

stats.sourceLightsDeduplicated =
  stats.sourceLightCandidates - clusteredLights.size;
for (const candidate of clusteredLights.values()) {
  const { classname, origin, sourceLight, sourceBrightness } = candidate;
  // Source and MOHlight use different intensity ranges. Spot fixtures remain
  // a little dimmer so they read as practical lights without bleaching walls.
  const scale = classname === "light_spot" ? 0.25 : 0.35;
  const brightness = Math.max(15, Math.min(130, sourceBrightness * scale));
  entities.push(
    pointEntity("light", {
      origin: origin.map(fmt).join(" "),
      light: fmt(brightness),
      overbright_range: "0.2",
      _color: `${fmt((sourceLight[0] || 255) / 255)} ${fmt(
        (sourceLight[1] || 230) / 255
      )} ${fmt((sourceLight[2] || 200) / 255)}`,
    })
  );
  stats.sourceLights++;
}

const mapText = `${entities
  .map((entity, index) => `// entity ${index}\n${entity}`)
  .join("\n")}\n`;
fs.writeFileSync(path.join(mapDir, `${mapName}.map`), mapText);

const scriptText = `main:

setcvar "g_obj_alliedtext1" "Codex Inferno"
setcvar "g_obj_alliedtext2" "Direct VMF reconstruction"
setcvar "g_obj_alliedtext3" "Original Inferno brush geometry"
setcvar "g_obj_axistext1" ""
setcvar "g_obj_axistext2" ""
setcvar "g_obj_axistext3" ""

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/${mapName}.scr
level waittill spawn

end
`;
fs.writeFileSync(path.join(mapDir, `${mapName}.scr`), scriptText);
fs.writeFileSync(
  path.join(mapDir, `${mapName}_precache.scr`),
  "exec global/DMprecache.scr\n"
);

const report = {
  mapName,
  revision: 4,
  construction: "direct-source-brush-conversion",
  displacementMode,
  compileBudgetMode,
  propPolicy: "omit-unverified-source-models",
  sourceBrushPolicy: "preserve playable world, func_detail, func_brush, and func_breakable solids",
  reference: path.basename(referencePath),
  referenceBytes: Buffer.byteLength(vmfText),
  referenceSha256: crypto.createHash("sha256").update(vmfText).digest("hex"),
  output: path.posix.join("main", "maps", "dm", `${mapName}.map`),
  worldBrushes: worldBrushes.length,
  entities: entities.length,
  terroristSpawns: terroristSpawns.length,
  counterSpawns: counterSpawns.length,
  neutralSpawns: deathmatchSpawns.length,
  stats,
};
fs.writeFileSync(
  path.join(outputRoot, `${mapName}-conversion-report.json`),
  `${JSON.stringify(report, null, 2)}\n`
);
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
