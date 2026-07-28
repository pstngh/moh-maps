const fs = require("fs");
const path = require("path");

const referencePath = path.resolve(
  process.argv[2] || path.join("work", "references", "de_nuke_reference.vmf")
);
const outputRoot = path.resolve(
  process.argv[3] || path.join("generated", "codex_nuke")
);
const mapName = process.argv[4] || "codex_nuke";
const displacementMode = process.argv.includes("--full-displacements")
  ? "full"
  : "planar";
const mainDir = path.join(outputRoot, "main");
const mapDir = path.join(mainDir, "maps", "dm");
fs.mkdirSync(mapDir, { recursive: true });
const referenceAuditPath = path.join(__dirname, "..", "reference-audit.json");
const referenceAudit = JSON.parse(fs.readFileSync(referenceAuditPath, "utf8"));
const modelHeaderByPath = new Map(
  referenceAudit.models.audit
    .filter((model) => model.header)
    .map((model) => [model.model, model.header])
);

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
  paintedConcrete: {
    texture: "codex_nuke/painted_concrete",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  paintedConcreteBlue: {
    texture: "codex_nuke/painted_concrete_blue",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  concreteFloor: {
    texture: "codex_nuke/concrete_floor",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  concreteDark: {
    texture: "codex_nuke/concrete_dark",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  asphalt: {
    texture: "codex_nuke/asphalt",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  grass: {
    texture: "codex_nuke/grass",
    contentFlags: 0,
    surfaceFlags: 524288,
  },
  gravel: {
    texture: "codex_nuke/gravel",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  corrugatedBlue: {
    texture: "codex_nuke/corrugated_blue",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  corrugatedGray: {
    texture: "codex_nuke/corrugated_gray",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  metalTrim: {
    texture: "codex_nuke/metal_trim",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  ceiling: {
    texture: "codex_nuke/ceiling_tile",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  glass: {
    texture: "codex_nuke/glass",
    contentFlags: 0,
    surfaceFlags: 4194304,
  },
  windowBacking: {
    texture: "codex_nuke/window_backing",
    contentFlags: 0,
    surfaceFlags: 4194304,
  },
  chainlink: {
    texture: "codex_nuke/chainlink",
    contentFlags: 0,
    surfaceFlags: 262176,
  },
  grating: {
    texture: "codex_nuke/metal_grating",
    contentFlags: 8192,
    surfaceFlags: 262176,
  },
  door: {
    texture: "codex_nuke/corrugated_blue",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  crate: {
    texture: "codex_nuke/metal_trim",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  metal: {
    texture: "codex_nuke/metal_trim",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  pipe: {
    texture: "codex_nuke/corrugated_gray",
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
    contentFlags: 16777216,
    surfaceFlags: 2176,
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
    /tools\/(toolsclip|toolshint|toolsskip|toolstrigger|toolsareaportal|toolsplayerclip|toolsblockbullets|toolsinvisibleladder)/i.test(
      material
    )
  ) {
    return targetMaterials.caulk;
  }

  if (/(tools\/toolsblack|cs_italy\/black|window_illum)/i.test(material)) {
    return targetMaterials.windowBacking;
  }
  if (/(cobweb|overlay|hanging_wires|dev_measure)/.test(material)) return targetMaterials.caulk;
  if (/(chainlink|railing_001_card)/.test(material)) return targetMaterials.chainlink;
  if (/(stain_glass|glass)/.test(material)) return targetMaterials.glass;
  if (/(water|liquid|river)/.test(material)) return targetMaterials.caulk;
  if (/(grass|foliage|blendgrass)/.test(material)) return targetMaterials.grass;
  if (/(dirt|mulch|ground|gravel|farm)/.test(material)) return targetMaterials.gravel;
  if (/(asphalt)/.test(material)) return targetMaterials.asphalt;
  if (/(ceiling_tile|ceiling_001)/.test(material)) return targetMaterials.ceiling;
  if (/(grating|grate|mesh)/.test(material)) return targetMaterials.grating;
  if (/(floor|stair|polished|roof_001)/.test(material)) {
    return /dark|black/.test(material)
      ? targetMaterials.concreteDark
      : targetMaterials.concreteFloor;
  }
  if (/(door)/.test(material)) return targetMaterials.door;
  if (/(crate|wood|beam|board|plywood)/.test(material)) return targetMaterials.crate;
  if (/(pipe|vent|duct)/.test(material)) return targetMaterials.pipe;
  if (/metal_corrugated_001_blue/.test(material)) return targetMaterials.corrugatedBlue;
  if (/metal_corrugated_001(?!b)/.test(material)) return targetMaterials.corrugatedGray;
  if (/(corrugated|metal_wall)/.test(material)) return targetMaterials.corrugatedGray;
  if (/(metal|iron|rust|steel|trim|panel|security_barrier)/.test(material)) {
    return targetMaterials.metalTrim;
  }
  if (/(stone|brick|rock|pebbledash)/.test(material)) return targetMaterials.concreteDark;
  if (/(wall_painted.*green|wall_painted.*red)/.test(material)) {
    return targetMaterials.paintedConcreteBlue;
  }
  if (/(wall|plaster|concrete|crete|column)/.test(material)) {
    return /wall_006|wall_009|dark|black/.test(material)
      ? targetMaterials.concreteDark
      : targetMaterials.paintedConcrete;
  }
  return targetMaterials.paintedConcrete;
}

const helperMaterial = /tools\/(toolsclip(?:_[^/]+)?|toolsgrenadeclip|toolshint|toolsskip|toolstrigger|toolsareaportal|toolsplayerclip|toolsblockbullets|toolsblocklight|toolsnpcclip|toolsinvisibleladder)/i;
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
  return /(grass|dirt|ground|gravel|asphalt|floor|stair|road|path|rock|rubble)/i.test(
    sourceMaterial
  );
}

function planarSeamUnderlayPatch(surface) {
  const expansion = Math.max(
    24,
    Math.min(
      384,
      Math.ceil((surface.maximumHorizontalDisplacement || 0) + 16)
    )
  );
  const depth = 4;
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
      ? targetByTexture.get(materialOrTexture) || targetMaterials.paintedConcrete
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

function cylinderBrush(
  origin,
  minZ,
  maxZ,
  radius,
  material,
  sides = 8,
  surfaceParms = ""
) {
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
        material,
        true,
        surfaceParms
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
      material,
      true,
      surfaceParms
    )
  );
  lines.push(
    face(
      [
        [centerX + 16, centerY + 16, maxZ],
        [centerX, centerY, maxZ],
        [centerX - 16, centerY + 16, maxZ],
      ],
      material,
      true,
      surfaceParms
    )
  );
  lines.push("}");
  return lines.join("\n");
}

function frustumBrush(
  origin,
  minZ,
  maxZ,
  bottomRadius,
  topRadius,
  material,
  sides = 16,
  surfaceParms = ""
) {
  const [centerX, centerY] = origin;
  const bottom = Array.from({ length: sides }, (_, index) => {
    const angle = (index / sides) * Math.PI * 2;
    return [
      centerX + Math.cos(angle) * bottomRadius,
      centerY + Math.sin(angle) * bottomRadius,
      minZ,
    ];
  });
  const top = Array.from({ length: sides }, (_, index) => {
    const angle = (index / sides) * Math.PI * 2;
    return [
      centerX + Math.cos(angle) * topRadius,
      centerY + Math.sin(angle) * topRadius,
      maxZ,
    ];
  });
  const lines = ["{"];
  for (let index = 0; index < sides; index++) {
    const next = (index + 1) % sides;
    lines.push(
      face(
        [bottom[next], bottom[index], top[index]],
        material,
        true,
        surfaceParms
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
      material,
      true,
      surfaceParms
    )
  );
  lines.push(
    face(
      [
        [centerX + 16, centerY + 16, maxZ],
        [centerX, centerY, maxZ],
        [centerX - 16, centerY + 16, maxZ],
      ],
      material,
      true,
      surfaceParms
    )
  );
  lines.push("}");
  return lines.join("\n");
}

function domedSiloBrushes(
  origin,
  baseZ,
  radius,
  wallHeight,
  domeHeight,
  material,
  surfaceParms = ""
) {
  const brushes = [
    cylinderBrush(
      origin,
      baseZ,
      baseZ + wallHeight,
      radius,
      material,
      16,
      surfaceParms
    ),
  ];
  const steps = 7;
  for (let step = 0; step < steps; step++) {
    const startAngle = (step / steps) * (Math.PI / 2);
    const endAngle = ((step + 1) / steps) * (Math.PI / 2);
    const startRadius = Math.max(8, Math.cos(startAngle) * radius);
    const endRadius = Math.max(8, Math.cos(endAngle) * radius);
    const minZ = baseZ + wallHeight + Math.sin(startAngle) * domeHeight;
    const maxZ = baseZ + wallHeight + Math.sin(endAngle) * domeHeight;
    brushes.push(
      frustumBrush(
        origin,
        minZ,
        maxZ,
        startRadius,
        endRadius,
        material,
        16,
        surfaceParms
      )
    );
  }
  return brushes;
}

function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, propertyValue] of Object.entries(properties)) {
    lines.push(`"${key}" "${propertyValue}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function inPlayableArea(origin) {
  return (
    origin[0] >= -6400 &&
    origin[0] <= 6720 &&
    origin[1] >= -5504 &&
    origin[1] <= 4608 &&
    origin[2] >= -1536 &&
    origin[2] <= 3584
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

function collectPlanarDisplacementSupports(solid, surfaces, stats) {
  const sides = children(solid.children, "side");
  const points = pointsForSolid(solid);
  if (sides.length < 4 || !points.length) return;
  const center = centroid(points);
  for (const side of sides) {
    const dispInfo = children(side.children, "dispinfo")[0];
    if (!dispInfo) continue;
    const vertices = reconstructedFaceVertices(sides, side, center);
    const planePoints = parsePlane(value(side.children, "plane"));
    const plane = planePoints ? brushPlane(planePoints, center) : null;
    if (!vertices || !plane || plane.normal[2] < 0.2) continue;
    const power = Number(value(dispInfo.children, "power"));
    const gridSize = 2 ** power + 1;
    const normals = [5, 9, 17].includes(gridSize)
      ? parseDisplacementRows(dispInfo, "normals", gridSize, 3)
      : null;
    const distances = [5, 9, 17].includes(gridSize)
      ? parseDisplacementRows(dispInfo, "distances", gridSize, 1)
      : null;
    const offsets = children(dispInfo.children, "offsets").length
      ? parseDisplacementRows(dispInfo, "offsets", gridSize, 3)
      : normals
        ? Array.from({ length: gridSize }, () =>
            Array.from({ length: gridSize }, () => [0, 0, 0])
          )
        : null;
    let maximumHorizontalDisplacement = 0;
    if (normals && distances && offsets) {
      for (let row = 0; row < gridSize; row++) {
        for (let column = 0; column < gridSize; column++) {
          const displacement = add(
            offsets[row][column],
            scale(normals[row][column], distances[row][column])
          );
          maximumHorizontalDisplacement = Math.max(
            maximumHorizontalDisplacement,
            Math.hypot(displacement[0], displacement[1])
          );
        }
      }
    }
    stats.maximumPlanarHorizontalDisplacement = Math.max(
      stats.maximumPlanarHorizontalDisplacement,
      maximumHorizontalDisplacement
    );
    if (maximumHorizontalDisplacement < 8) {
      stats.planarHorizontalDisplacementBuckets.under8++;
    } else if (maximumHorizontalDisplacement < 24) {
      stats.planarHorizontalDisplacementBuckets.under24++;
    } else if (maximumHorizontalDisplacement < 64) {
      stats.planarHorizontalDisplacementBuckets.under64++;
    } else if (maximumHorizontalDisplacement < 128) {
      stats.planarHorizontalDisplacementBuckets.under128++;
    } else {
      stats.planarHorizontalDisplacementBuckets.atLeast128++;
    }
    surfaces.push({
      vertices,
      normal: plane.normal,
      distance: plane.distance,
      sourceMaterial: value(side.children, "material"),
      maximumHorizontalDisplacement,
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

function orthogonalYaw(yaw) {
  const rounded = Math.round(yaw / 90) * 90;
  const difference = Math.abs(((yaw - rounded + 180) % 360) - 180);
  return difference <= 0.05 ? rounded : null;
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

function measuredModelBrush(
  model,
  origin,
  yaw,
  material,
  surfaceParms = "",
  isDetail = true
) {
  const header = modelHeaderByPath.get(model);
  const snappedYaw = orthogonalYaw(yaw);
  if (!header || snappedYaw === null) return null;
  const bounds = rotatedLocalBounds(
    origin,
    snappedYaw,
    header.hullMin,
    header.hullMax
  );
  return boxBrush(bounds.min, bounds.max, material, surfaceParms, isDetail);
}

// A few measured cosmetic boxes should not obstruct players. Keep them
// lightmapped: broad `nolightmap` use made the revision-2 substitutes render
// as dominant white/fullbright shapes in the user's screenshots.
const nonBlockingDetail = "-surfaceparm solid";

function brushEntity(classname, properties, brushes) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, propertyValue] of Object.entries(properties)) {
    lines.push(`"${key}" "${propertyValue}"`);
  }
  for (const brush of brushes) lines.push(brush);
  lines.push("}");
  return lines.join("\n");
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
  maximumPlanarUnderlayExpansion: 0,
  displacementSupportSurfaces: 0,
  maximumPlanarHorizontalDisplacement: 0,
  planarHorizontalDisplacementBuckets: {
    under8: 0,
    under24: 0,
    under64: 0,
    under128: 0,
    atLeast128: 0,
  },
  propsGroundSnapped: 0,
  maximumPropGroundAdjustment: 0,
  measuredPropBrushes: 0,
  measuredPropFamilies: {},
  nonOrthogonalPropsSkipped: 0,
  tiltedPropsSkipped: 0,
  embeddedAutocombinesOmitted: 0,
  embeddedAutocombinesReconstructed: 0,
  embeddedAutocombinesSkyboxSkipped: 0,
  autocombineFillBrushes: 0,
  autocombineFillFamilies: {},
  heroIndustrialBrushes: 0,
  heroIndustrialModels: {},
  rotatingDoors: 0,
  doorFrames: 0,
  sourceLights: 0,
  sourceLightCandidates: 0,
  sourceLightsDeduplicated: 0,
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
  collectPlanarDisplacementSupports(solid, planarDisplacementSupports, stats);
}
for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["func_detail", "func_brush", "func_breakable"].includes(classname)) continue;
  for (const solid of children(entity.children, "solid")) {
    collectPlanarDisplacementSupports(solid, planarDisplacementSupports, stats);
  }
}
stats.displacementSupportSurfaces = planarDisplacementSupports.length;

const worldBrushes = [];
const generatedBrushEntities = [];
for (const solid of children(world.children, "solid")) {
  // Imported Source world brushes are internal geometry inside the explicit
  // structural sky shell below. Treating them as detail preserves collision
  // but prevents every castle trim plane from exploding the Q3 visibility
  // tree beyond MOHAA's fixed 2 MiB portal limit.
  const converted = convertSolid(solid, true, stats);
  if (converted) worldBrushes.push(converted);
}

const skyBounds = {
  min: [-6464, -5568, -1600],
  max: [6784, 4672, 3648],
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
    stats.maximumPlanarUnderlayExpansion = Math.max(
      stats.maximumPlanarUnderlayExpansion,
      Math.max(
        24,
        Math.min(
          384,
          Math.ceil((surface.maximumHorizontalDisplacement || 0) + 16)
        )
      )
    );
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

// Rebuild only model families whose studio-header bounds and architectural
// role are understood. Decorative cables, signs, outlets, foliage, and all
// autocombines remain omitted until a family-specific reconstruction exists.
const measuredPropRules = [
  {
    family: "railing",
    pattern: /metal_railing_001\/metal_railing_001_(?:64|128|256)\.mdl$/,
    material: targetMaterials.metalTrim,
  },
  {
    family: "chainlink",
    pattern: /chainlink_fence_001\/chainlink_fence_001_(?:64|128|256)\.mdl$/,
    material: targetMaterials.chainlink,
  },
  {
    family: "roof_trim",
    pattern: /metal_trim_001\/metal_roof_trim_(?:corner_)?001_(?:64|128|256)\.mdl$/,
    material: targetMaterials.metalTrim,
  },
  {
    family: "roof_ac",
    pattern: /nuke_roof_ac\/nuke_roof_ac(?:01|02|03)_low\.mdl$/,
    material: targetMaterials.corrugatedGray,
  },
  {
    family: "ventilation",
    pattern: /nuke_ventilation_exhaust\/nuke_outdoor_vent(?:_exhaust_(?:small|smallb))?\.mdl$/,
    material: targetMaterials.corrugatedGray,
  },
  {
    family: "concrete_barrier",
    pattern: /nuke_concrete_barrier\/(?:nuke_concrete_barrier|nuke_concrete_block128)\.mdl$/,
    material: targetMaterials.concreteDark,
  },
  {
    family: "straight_pipe",
    pattern: /metal_pipe_001\/metal_pipe_001[^/]*_straight_(?:16|32|64|128|256|512)_low\.mdl$/,
    material: targetMaterials.pipe,
  },
  {
    family: "fluorescent_fixture",
    pattern: /nuke_light_fixture\/(?:nuke_fluorescent_light_64|recessed_lighting_fixture_32x(?:32|64)|nuke_ceiling_light)\.mdl$/,
    material: targetMaterials.ceiling,
  },
  {
    family: "window",
    pattern: /window_001\/window_001[a-z]?\.mdl$/,
    material: targetMaterials.glass,
  },
  {
    family: "curb",
    pattern: /curbs_001\/curb_straight_001_(?:64|128|256)\.mdl$/,
    material: targetMaterials.concreteFloor,
  },
  {
    family: "metal_crate",
    pattern: /metal_crate_001\/metal_crate_001_(?:64|96)(?:_corners)?\.mdl$/,
    material: targetMaterials.crate,
  },
  {
    family: "web_joist",
    pattern: /web_joist_001\/web_joist_(?:support_)?001[^/]*\.mdl$/,
    material: targetMaterials.metalTrim,
  },
  {
    family: "electrical_equipment",
    pattern: /(?:transformer_yard_powerbox|nuke_electric_panel)\//,
    material: targetMaterials.metalTrim,
  },
];

for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["prop_static", "prop_dynamic"].includes(classname)) continue;
  const model = value(entity.children, "model").toLowerCase();
  const origin = parseVector(value(entity.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(value(entity.children, "angles", "0 0 0"));
  const pitch = Number.isFinite(angles[0]) ? angles[0] : 0;
  const yaw = Number.isFinite(angles[1]) ? angles[1] : 0;
  const roll = Number.isFinite(angles[2]) ? angles[2] : 0;

  let heroBrushes = null;
  let heroFamily = null;
  if (/medium_silo\/medium_silo\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    heroBrushes = [
      cylinderBrush(
        origin,
        origin[2] + header.hullMin[2],
        origin[2] + header.hullMax[2],
        104,
        targetMaterials.corrugatedGray,
        16,
        "-surfaceparm solid"
      ),
    ];
    heroFamily = "medium_silo";
  } else if (/nuke_water_tank\/nuke_water_tank02\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    heroBrushes = [
      cylinderBrush(
        origin,
        origin[2] + header.hullMin[2],
        origin[2] + header.hullMax[2],
        162,
        targetMaterials.corrugatedGray,
        16,
        "-surfaceparm solid"
      ),
    ];
    heroFamily = "water_tank_small";
  } else if (/nuke_water_tank\/nuke_water_tank\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    heroBrushes = [
      cylinderBrush(
        origin,
        origin[2] + header.hullMin[2],
        origin[2] + header.hullMax[2],
        326,
        targetMaterials.corrugatedGray,
        16,
        "-surfaceparm solid"
      ),
    ];
    heroFamily = "water_tank_large";
  } else if (/nuke_silo_001\/nuke_silo_001a\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    const baseZ = origin[2] + header.hullMin[2];
    heroBrushes = domedSiloBrushes(
      origin,
      baseZ,
      430,
      650,
      520,
      targetMaterials.corrugatedGray,
      "-surfaceparm solid"
    );
    heroFamily = "reactor_silo_secondary";
  } else if (/nuke_silo_001\/nuke_silo_002a\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    heroBrushes = [
      cylinderBrush(
        origin,
        origin[2] + header.hullMin[2],
        origin[2] + header.hullMax[2],
        221,
        targetMaterials.corrugatedGray,
        16,
        "-surfaceparm solid"
      ),
    ];
    heroFamily = "process_silo";
  } else if (/nuke_silo_001\/nuke_silo_003a\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    const baseZ = origin[2] + header.hullMin[2];
    heroBrushes = domedSiloBrushes(
      origin,
      baseZ,
      640,
      600,
      900,
      targetMaterials.corrugatedGray,
      "-surfaceparm solid"
    );
    heroFamily = "reactor_silo_primary";
  }
  if (heroBrushes) {
    worldBrushes.push(...heroBrushes);
    stats.heroIndustrialBrushes += heroBrushes.length;
    stats.heroIndustrialModels[heroFamily] =
      (stats.heroIndustrialModels[heroFamily] || 0) + 1;
    continue;
  }

  if (model.includes("/autocombine/")) {
    // The MDL hull is the aggregate envelope of an autocombined model, not a
    // description of its internal topology. Revision 2 proved that deriving
    // rail/pipe/ladder runs from this box creates arbitrary beams through the
    // level. Omit the family until its actual mesh or verified endpoints can
    // be read.
    stats.embeddedAutocombinesOmitted++;
    continue;
  }

  if (Math.abs(pitch) > 0.05 || Math.abs(roll) > 0.05) {
    stats.tiltedPropsSkipped++;
    continue;
  }

  if (/metal_door_001\/metal_door_frame_001_8\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    const snappedYaw = orthogonalYaw(yaw);
    if (!header || snappedYaw === null) {
      stats.nonOrthogonalPropsSkipped++;
      continue;
    }
    const frameOrigin = [
      origin[0],
      origin[1],
      origin[2] + header.hullMin[2],
    ];
    const width = header.hullMax[1] - header.hullMin[1];
    const height = header.hullMax[2] - header.hullMin[2];
    const depth = header.hullMax[0] - header.hullMin[0];
    worldBrushes.push(
      ...archFrameBrushes(
        frameOrigin,
        snappedYaw,
        width,
        height,
        targetMaterials.metalTrim,
        8,
        depth
      )
    );
    stats.doorFrames++;
    stats.measuredPropBrushes += 3;
    stats.measuredPropFamilies.door_frame =
      (stats.measuredPropFamilies.door_frame || 0) + 1;
    continue;
  }

  if (/nuke_metal_bollard\/nuke_metal_bollard\.mdl$/.test(model)) {
    const header = modelHeaderByPath.get(model);
    if (!header) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    const radius = Math.max(
      Math.abs(header.hullMin[0]),
      Math.abs(header.hullMax[0]),
      Math.abs(header.hullMin[1]),
      Math.abs(header.hullMax[1])
    );
    worldBrushes.push(
      cylinderBrush(
        origin,
        origin[2] + header.hullMin[2],
        origin[2] + header.hullMax[2],
        radius,
        targetMaterials.metalTrim
      )
    );
    stats.measuredPropBrushes++;
    stats.measuredPropFamilies.bollard =
      (stats.measuredPropFamilies.bollard || 0) + 1;
    continue;
  }

  const rule = measuredPropRules.find((candidate) =>
    candidate.pattern.test(model)
  );
  if (!rule) {
    stats.unsupportedPropsSkipped++;
    continue;
  }
  const brush = measuredModelBrush(
    model,
    origin,
    yaw,
    rule.material,
    ["fluorescent_fixture", "roof_trim", "window"].includes(rule.family)
      ? nonBlockingDetail
      : ""
  );
  if (!brush) {
    stats.nonOrthogonalPropsSkipped++;
    continue;
  }
  worldBrushes.push(brush);
  stats.measuredPropBrushes++;
  stats.measuredPropFamilies[rule.family] =
    (stats.measuredPropFamilies[rule.family] || 0) + 1;
}

// Nuke has four genuine rotating doors. Recreate their measured panel bounds
// and hinge origins as AA func_rotatingdoor brush entities.
for (const entity of sourceEntities) {
  if (value(entity.children, "classname") !== "prop_door_rotating") continue;
  const model = value(entity.children, "model").toLowerCase();
  const origin = parseVector(value(entity.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(value(entity.children, "angles", "0 0 0"));
  const yaw = Number.isFinite(angles[1]) ? angles[1] : 0;
  const doorBrush = measuredModelBrush(
    model,
    origin,
    yaw,
    targetMaterials.door,
    "",
    false
  );
  if (!doorBrush) {
    stats.nonOrthogonalPropsSkipped++;
    continue;
  }
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
        doortype: "metal",
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
  `"message" "Codex Nuke"` ,
  `"ambientlight" "14 16 20"`,
  `"suncolor" "132 128 118"`,
  `"sundirection" "300 130 0"`,
  `"sundiffusecolor" "76 84 100"`,
  `"sundiffuse" "1.35"`,
  `"_color" "0.97 0.99 1.0"`,
  `"farplane" "8000"`,
  `"farplane_color" "0.34 0.39 0.46"`,
  ...worldBrushes.map((brush, index) => `// brush ${index}\n${brush}`),
  "}",
].join("\n");

const entities = [worldspawn, ...generatedBrushEntities];
const terroristSpawns = [];
const counterSpawns = [];

for (const source of sourceEntities) {
  const classname = value(source.children, "classname");
  if (!["info_player_terrorist", "info_player_counterterrorist"].includes(classname)) continue;
  const origin = parseVector(value(source.children, "origin"));
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(value(source.children, "angles", "0 0 0"));
  const spawn = { origin, yaw: Number.isFinite(angles[1]) ? angles[1] : 0 };
  if (classname === "info_player_terrorist") terroristSpawns.push(spawn);
  else counterSpawns.push(spawn);
}

if (!terroristSpawns.length || !counterSpawns.length) {
  throw new Error("Reference map spawns were not found");
}

const spectator = counterSpawns[0];
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
  entities.push(pointEntity("info_player_deathmatch", properties));
}
for (const spawn of counterSpawns) {
  const properties = {
    origin: spawn.origin.map(fmt).join(" "),
    angle: fmt(spawn.yaw),
  };
  entities.push(pointEntity("info_player_allied", properties));
  entities.push(pointEntity("info_player_deathmatch", properties));
}

const sourceLightCells = new Map();
for (const source of sourceEntities) {
  const classname = value(source.children, "classname");
  if (!["light", "light_spot"].includes(classname)) continue;
  const origin = parseVector(value(source.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const sourceLight = parseVector(value(source.children, "_light", "255 230 200 400"));
  const sourceBrightness = sourceLight[3] || 400;
  stats.sourceLightCandidates++;
  // Source often stacks a dim point light, a bright spotlight, and a sprite at
  // one fixture. MOHAA has no equivalent clustered-light model and clamps
  // entity-light lists at 60, so retain only the strongest light in each
  // compact fixture cell.
  const cell = [
    Math.round(origin[0] / 128),
    Math.round(origin[1] / 128),
    Math.round(origin[2] / 96),
  ].join(":");
  const score = sourceBrightness + (classname === "light_spot" ? 32 : 0);
  const existing = sourceLightCells.get(cell);
  if (!existing || score > existing.score) {
    sourceLightCells.set(cell, {
      classname,
      origin,
      sourceLight,
      sourceBrightness,
      score,
    });
  }
}

stats.sourceLightsDeduplicated =
  stats.sourceLightCandidates - sourceLightCells.size;
for (const candidate of sourceLightCells.values()) {
  const {
    classname,
    origin,
    sourceLight,
    sourceBrightness,
  } = candidate;
  const brightnessScale = classname === "light_spot" ? 0.42 : 0.62;
  const brightness = Math.max(
    classname === "light_spot" ? 28 : 18,
    Math.min(
      classname === "light_spot" ? 145 : 155,
      sourceBrightness * brightnessScale + 8
    )
  );
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

setcvar "g_obj_alliedtext1" "Codex Nuke"
setcvar "g_obj_alliedtext2" "Industrial deathmatch"
setcvar "g_obj_alliedtext3" "OpenMoHAA bot layout study"
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
  displacementMode,
  reference: path.basename(referencePath),
  output: `main/maps/dm/${mapName}.map`,
  worldBrushes: worldBrushes.length,
  entities: entities.length,
  terroristSpawns: terroristSpawns.length,
  counterSpawns: counterSpawns.length,
  neutralSpawns: terroristSpawns.length + counterSpawns.length,
  stats,
};
fs.writeFileSync(
  path.join(outputRoot, `${mapName}-conversion-report.json`),
  `${JSON.stringify(report, null, 2)}\n`
);
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
