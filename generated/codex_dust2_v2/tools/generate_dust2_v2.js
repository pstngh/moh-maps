const fs = require("fs");
const path = require("path");

const referencePath = path.resolve(
  process.argv[2] || path.join("work", "references", "de_dust2_reference.vmf")
);
const outputRoot = path.resolve(process.argv[3] || path.join("work", "generated_dust2_v2"));
const mapName = process.argv[4] || "codex_dust2_v2";
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
  concrete: {
    texture: "general_structure/jh_conc512b",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  wall: {
    texture: "general_structure/bunker_wall",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  stone: {
    texture: "normandy/bunker_conc3",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  rock: {
    texture: "wilderness/wldrrckset1_1",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  floor: {
    texture: "algiers/whsflrset1_1b",
    contentFlags: 0,
    surfaceFlags: 0,
  },
  ceiling: {
    texture: "normandy/bunk_ceiling",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  wood: {
    texture: "general_structure/beam_wood1",
    contentFlags: 0,
    surfaceFlags: 16384,
  },
  shutter: {
    texture: "central_europe/shutter_set2",
    contentFlags: 0,
    surfaceFlags: 16384,
  },
  crate: {
    texture: "german/crate_reinforced1_side",
    contentFlags: 0,
    surfaceFlags: 16384,
  },
  metal: {
    texture: "das_boot/ironwall1",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  rustyMetal: {
    texture: "german/rusty_iron",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  grate: {
    texture: "general_industrial/deckgrate_set1a",
    contentFlags: 8192,
    surfaceFlags: 262176,
  },
  pipe: {
    texture: "general_industrial/jh_pipe1",
    contentFlags: 0,
    surfaceFlags: 32768,
  },
  sky: {
    texture: "sky/mohday1",
    contentFlags: 0,
    surfaceFlags: 276,
  },
  caulk: {
    texture: "common/caulk",
    contentFlags: 0,
    surfaceFlags: 160,
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

  if (/(crate|wood|door|board|plywood)/.test(material)) return targetMaterials.wood;
  if (/(grate|fence|mesh)/.test(material)) return targetMaterials.grate;
  if (/(metal|iron|rust|steel|roof|trim)/.test(material)) return targetMaterials.metal;
  if (/(pipe|vent|duct)/.test(material)) return targetMaterials.pipe;
  if (/(ground|sand|road|floor|tile|step)/.test(material)) return targetMaterials.floor;
  if (/rock/.test(material)) return targetMaterials.rock;
  if (/stone/.test(material)) return targetMaterials.stone;
  if (/(wall|brick|plaster|concrete|crete|temple|resid|siteb)/.test(material)) {
    return targetMaterials.wall;
  }
  return targetMaterials.concrete;
}

const helperMaterial = /tools\/(toolsclip|toolshint|toolsskip|toolstrigger|toolsareaportal|toolsplayerclip|toolsblockbullets|toolsinvisibleladder)/i;

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

function displacementBrushes(side, solidCenter) {
  const verticesBlock = children(side.children, "vertices_plus")[0];
  const dispInfo = children(side.children, "dispinfo")[0];
  if (!verticesBlock || !dispInfo) return null;
  const outer = verticesBlock.children
    .filter((entry) => entry.key === "v")
    .map((entry) => parseVector(entry.value));
  if (outer.length !== 4) return null;

  const power = Number(value(dispInfo.children, "power"));
  const gridSize = 2 ** power + 1;
  if (![5, 9, 17].includes(gridSize)) return null;

  const startPosition = parseVector(value(dispInfo.children, "startposition"));
  if (startPosition.length !== 3 || startPosition.some((number) => !Number.isFinite(number))) {
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
  if (startIndex.index < 0 || startIndex.distanceSquared > 1) return null;

  // VMF rows begin at startposition. With the side's cyclic vertex order,
  // columns advance toward the previous corner and rows toward the next one.
  const p00 = outer[startIndex.index];
  const p10 = outer[(startIndex.index + 3) % 4];
  const p01 = outer[(startIndex.index + 1) % 4];
  const p11 = outer[(startIndex.index + 2) % 4];
  const normals = parseDisplacementRows(dispInfo, "normals", gridSize, 3);
  const distances = parseDisplacementRows(dispInfo, "distances", gridSize, 1);
  const offsets = parseDisplacementRows(dispInfo, "offsets", gridSize, 3);
  if (!normals || !distances || !offsets) return null;

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

  const visibleMaterial = materialFor(value(side.children, "material"));
  const patchNormal = normalized(
    cross(
      subtract(grid[0][1].point, grid[0][0].point),
      subtract(grid[1][0].point, grid[0][0].point)
    )
  );
  if (!patchNormal) return null;
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
  const skirtEdges = [
    grid[0],
    grid[gridSize - 1],
    grid.map((row) => row[0]),
    grid.map((row) => row[gridSize - 1]),
  ];
  let skirtPatchCount = 0;
  let skirtTriangleCount = 0;
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
  if (sourceMaterials.every((material) => helperMaterial.test(material))) {
    stats.helperSkipped++;
    return null;
  }

  const solidPoints = pointsForSolid(solid);
  if (!solidPoints.length) {
    stats.invalid++;
    return null;
  }
  const center = centroid(solidPoints);
  if (center[0] > 4000 || center[2] < -1200) {
    stats.skyboxSkipped++;
    return null;
  }

  const displacementSides = sides.filter(
    (side) => children(side.children, "dispinfo").length > 0
  );
  if (displacementSides.length) {
    const rebuilt = [];
    let rebuiltSides = 0;
    let rebuiltTriangles = 0;
    let rebuiltSurfacePatches = 0;
    let rebuiltSkirtPatches = 0;
    let rebuiltSkirtTriangles = 0;
    let rebuiltFlipped = 0;
    for (const side of displacementSides) {
      const brushes = displacementBrushes(side, center);
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

  const lines = ["{"];
  for (const side of sides) {
    const plane = parsePlane(value(side.children, "plane"));
    if (!plane) {
      stats.invalid++;
      return null;
    }
    const material = materialFor(value(side.children, "material"));
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
      ? targetByTexture.get(materialOrTexture) || targetMaterials.concrete
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

function boxBrush(min, max, material, surfaceParms = "") {
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  return [
    "{",
    face(
      [[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]],
      material,
      true,
      surfaceParms
    ),
    face(
      [[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]],
      material,
      true,
      surfaceParms
    ),
    face(
      [[16, minY, -16], [0, minY, 0], [16, minY, 16]],
      material,
      true,
      surfaceParms
    ),
    face(
      [[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]],
      material,
      true,
      surfaceParms
    ),
    face(
      [[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]],
      material,
      true,
      surfaceParms
    ),
    face(
      [[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]],
      material,
      true,
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

function windowDimensions(model) {
  if (model.includes("du_window_bridge")) return [56, 64];
  if (model.includes("du_window_palace")) return [96, 120];
  const encodedSize = model.match(/du_window_(\d+)x(\d+)/);
  if (!encodedSize) return null;
  return [Number(encodedSize[1]) * 8, Number(encodedSize[2]) * 8];
}

function windowBackingDimensions(model) {
  if (model.includes("du_window_bridge")) return [96, 128];
  if (model.includes("du_window_palace")) return [240, 160];
  const encodedSize = model.match(/du_window_(\d+)x(\d+)/);
  if (!encodedSize) return null;
  return [Number(encodedSize[1]) * 16, Number(encodedSize[2]) * 16];
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

function inPlayableArea(origin) {
  return origin[0] < 4000 && origin[0] > -4500 && origin[2] > -1200;
}

const vmfText = fs.readFileSync(referencePath, "utf8");
const rootEntries = parseEntries(tokenize(vmfText), { index: 0 });
const world = children(rootEntries, "world")[0];
const sourceEntities = children(rootEntries, "entity");
const stats = {
  converted: 0,
  detail: 0,
  helperSkipped: 0,
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
  displacementSkipped: 0,
  unsupportedPropsSkipped: 0,
  coverBrushes: 0,
  decorBrushes: 0,
  facadePanels: 0,
  facadeBackings: 0,
  carsGroundSnapped: 0,
  stockProps: 0,
  sourceLights: 0,
  fillLights: 0,
};

const worldBrushes = [];
const stockPropEntities = [];
for (const solid of children(world.children, "solid")) {
  const converted = convertSolid(solid, false, stats);
  if (converted) worldBrushes.push(converted);
}

for (const entity of sourceEntities) {
  const classname = value(entity.children, "classname");
  if (!["func_detail", "func_brush"].includes(classname)) continue;
  for (const solid of children(entity.children, "solid")) {
    const converted = convertSolid(solid, true, stats);
    if (converted) worldBrushes.push(converted);
  }
}

// Reconstruct gameplay-significant Source props as simple V2-themed cover.
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
  let size = null;
  let height = null;
  let material = targetMaterials.crate;
  const facadeWindow = windowDimensions(model);
  if (facadeWindow) {
    const facadeBacking = windowBackingDimensions(model);
    worldBrushes.push(
      verticalPanelBrush(
        origin,
        yaw,
        facadeBacking[0],
        facadeBacking[1],
        targetMaterials.wall,
        2,
        "-surfaceparm solid"
      )
    );
    worldBrushes.push(
      verticalPanelBrush(
        origin,
        yaw,
        facadeWindow[0],
        facadeWindow[1],
        targetMaterials.shutter,
        4,
        "-surfaceparm solid"
      )
    );
    stats.facadeBackings++;
    stats.facadePanels++;
    continue;
  } else if (model.includes("du_crate_64x64")) {
    size = 64;
    height = 64;
  } else if (model.includes("du_crate_96x96")) {
    size = 96;
    height = 96;
  } else if (model.includes("du_crate_128x128")) {
    size = 128;
    height = 128;
  } else if (model.includes("oildrum")) {
    const normalizedPitch = ((pitch + 180) % 360 + 360) % 360 - 180;
    const normalizedRoll = ((roll + 180) % 360 + 360) % 360 - 180;
    if (Math.abs(normalizedPitch) > 25 || Math.abs(normalizedRoll) > 25) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    worldBrushes.push(
      cylinderBrush(
        origin,
        origin[2] - 34,
        origin[2] + 34,
        22,
        targetMaterials.rustyMetal
      )
    );
    stats.coverBrushes++;
    continue;
  } else if (model.includes("plasticcrate")) {
    size = 32;
    height = 24;
  } else if (model.includes("stoneblock")) {
    stats.unsupportedPropsSkipped++;
    continue;
  } else if (model.includes("dustteeth_")) {
    stats.unsupportedPropsSkipped++;
    continue;
  } else if (
    model.includes("du_dome_") ||
    model.includes("dome_star") ||
    model.includes("antenna")
  ) {
    stats.unsupportedPropsSkipped++;
    continue;
  } else if (model.includes("palm_tree") || model.includes("palm")) {
    const palmOrigin = [...origin];
    palmOrigin[2] -= 536;
    stockPropEntities.push(
      pointEntity("static_natural_tree_regularpalm", {
        origin: palmOrigin.map(fmt).join(" "),
        angle: fmt(yaw),
        model: "static//tree_regularpalm.tik",
        scale: "1.0",
        testanim: "idle",
      })
    );
    stats.stockProps++;
    continue;
  } else if (model.includes("wagon")) {
    stockPropEntities.push(
      pointEntity("static_farm_wagon", {
        origin: origin.map(fmt).join(" "),
        angle: fmt(yaw),
        model: "static//wagon.tik",
        scale: "1.0",
        testanim: "idle",
      })
    );
    worldBrushes.push(
      boxBrush(
        [origin[0] - 54, origin[1] - 28, origin[2]],
        [origin[0] + 54, origin[1] + 28, origin[2] + 42],
        targetMaterials.caulk
      )
    );
    stats.stockProps++;
    stats.coverBrushes++;
    continue;
  } else if (/models\/props_vehicles\/car\d{3}[a-z]?\.mdl$/i.test(model)) {
    if (Math.abs(pitch) > 5 || Math.abs(roll) > 5) {
      stats.unsupportedPropsSkipped++;
      continue;
    }
    const carOrigin = [...origin];
    const gradeZ = Math.round(carOrigin[2] / 64) * 64;
    if (Math.abs(carOrigin[2] - gradeZ) <= 32) {
      carOrigin[2] = gradeZ;
      stats.carsGroundSnapped++;
    }
    stockPropEntities.push(
      pointEntity("static_vehicle_europe_car-rusted", {
        origin: carOrigin.map(fmt).join(" "),
        angles: [pitch, yaw, roll].map(fmt).join(" "),
        model: "static//vehicle_car_rusted.tik",
        scale: "1.0",
        testanim: "idle",
      })
    );
    worldBrushes.push(
      boxBrush(
        [carOrigin[0] - 70, carOrigin[1] - 32, carOrigin[2]],
        [carOrigin[0] + 70, carOrigin[1] + 32, carOrigin[2] + 60],
        targetMaterials.caulk
      )
    );
    stats.stockProps++;
    stats.coverBrushes++;
    continue;
  } else if (model.includes("garbage_metalcan") || model.includes("plasticbucket")) {
    stats.unsupportedPropsSkipped++;
    continue;
  } else if (model.includes("grainbasket")) {
    stats.unsupportedPropsSkipped++;
    continue;
  }

  if (size && height) {
    const half = size / 2;
    const minZ = origin[2] - height / 2;
    worldBrushes.push(
      boxBrush(
        [origin[0] - half, origin[1] - half, minZ],
        [origin[0] + half, origin[1] + half, minZ + height],
        material
      )
    );
    stats.coverBrushes++;
  }
}

const worldspawn = [
  "{",
  `"classname" "worldspawn"`,
  `"message" "Codex Dust II - V2 Facility"`,
  `"ambientlight" "15 15 16"`,
  `"ambient" "42"`,
  `"suncolor" "92 84 68"`,
  `"sundirection" "315 58 0"`,
  `"_color" "1.0 0.92 0.80"`,
  `"farplane" "12000"`,
  ...worldBrushes.map((brush, index) => `// brush ${index}\n${brush}`),
  "}",
].join("\n");

const entities = [worldspawn, ...stockPropEntities];
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

for (const source of sourceEntities) {
  const classname = value(source.children, "classname");
  if (!["light", "light_spot"].includes(classname)) continue;
  const origin = parseVector(value(source.children, "origin", "0 0 -9999"));
  if (!inPlayableArea(origin)) continue;
  const sourceLight = parseVector(value(source.children, "_light", "255 230 200 400"));
  const brightness = Math.max(450, Math.min(1200, (sourceLight[3] || 400) * 1.5));
  entities.push(
    pointEntity("light", {
      origin: origin.map(fmt).join(" "),
      light: fmt(brightness),
      _color: `${fmt((sourceLight[0] || 255) / 255)} ${fmt(
        (sourceLight[1] || 230) / 255
      )} ${fmt((sourceLight[2] || 200) / 255)}`,
    })
  );
  stats.sourceLights++;
}

const allSpawns = [...terroristSpawns, ...counterSpawns];
for (let index = 0; index < allSpawns.length; index += 2) {
  const lightOrigin = [...allSpawns[index].origin];
  lightOrigin[2] += 96;
  entities.push(
    pointEntity("light", {
      origin: lightOrigin.map(fmt).join(" "),
      light: "550",
      _color: "1 0.88 0.68",
    })
  );
  stats.fillLights++;
}

const mapText = `${entities
  .map((entity, index) => `// entity ${index}\n${entity}`)
  .join("\n")}\n`;
fs.writeFileSync(path.join(mapDir, `${mapName}.map`), mapText);

const scriptText = `main:

setcvar "g_obj_alliedtext1" "Codex Dust II"
setcvar "g_obj_alliedtext2" "V2 Facility"
setcvar "g_obj_alliedtext3" "Layout study for OpenMoHAA bots"
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
  reference: path.basename(referencePath),
  output: path.join(mapDir, `${mapName}.map`),
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
