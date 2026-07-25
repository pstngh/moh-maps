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
  if (/(rock|stone)/.test(material)) return targetMaterials.stone;
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

function displacementBrush(side) {
  const verticesBlock = children(side.children, "vertices_plus")[0];
  if (!verticesBlock) return null;
  const outer = verticesBlock.children
    .filter((entry) => entry.key === "v")
    .map((entry) => parseVector(entry.value));
  if (outer.length < 3) return null;

  const inward = normalized(
    cross(subtract(outer[1], outer[0]), subtract(outer[2], outer[0]))
  );
  if (!inward) return null;

  const thickness = 16;
  const inner = outer.map((point) =>
    point.map((component, axis) => component + inward[axis] * thickness)
  );
  const center = centroid([...outer, ...inner]);
  const visibleMaterial = materialFor(value(side.children, "material"));
  const lines = ["{"];

  lines.push(face(orientedPlane(outer.slice(0, 3), center), visibleMaterial, false));
  lines.push(face(orientedPlane(inner.slice(0, 3), center), targetMaterials.caulk, false));
  for (let index = 0; index < outer.length; index++) {
    const next = (index + 1) % outer.length;
    lines.push(
      face(
        orientedPlane([outer[index], outer[next], inner[next]], center),
        targetMaterials.caulk,
        false
      )
    );
  }
  lines.push("}");
  return lines.join("\n");
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
    const rebuilt = displacementSides.map(displacementBrush).filter(Boolean);
    if (!rebuilt.length) {
      stats.invalid++;
      stats.displacementSkipped++;
      return null;
    }
    stats.displacementRebuilt += rebuilt.length;
    return rebuilt.join("\n");
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

function face(points, materialOrTexture, isDetail = true) {
  const material =
    typeof materialOrTexture === "string"
      ? targetByTexture.get(materialOrTexture) || targetMaterials.concrete
      : materialOrTexture;
  return `${points.map(formatPoint).join(" ")} ${material.texture} 0 0 0 0.5 0.5 ${
    material.contentFlags
  } ${material.surfaceFlags} 0${
    isDetail ? " +surfaceparm detail" : ""
  }`;
}

function boxBrush(min, max, material) {
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], material),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], material),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], material),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], material),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], material),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], material),
    "}",
  ].join("\n");
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
  displacementSkipped: 0,
  unsupportedPropsSkipped: 0,
  coverBrushes: 0,
  decorBrushes: 0,
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
  if (model.includes("du_crate_64x64")) {
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
    size = 56;
    height = 56;
    material = targetMaterials.stone;
  } else if (model.includes("dustteeth_")) {
    const halfX = 24;
    const halfY = 14;
    worldBrushes.push(
      boxBrush(
        [origin[0] - halfX, origin[1] - halfY, origin[2]],
        [origin[0] + halfX, origin[1] + halfY, origin[2] + 36],
        targetMaterials.stone
      )
    );
    stats.decorBrushes++;
    continue;
  } else if (model.includes("du_dome_") || model.includes("dome_star")) {
    worldBrushes.push(
      cylinderBrush(origin, origin[2], origin[2] + 24, 56, targetMaterials.ceiling)
    );
    worldBrushes.push(
      cylinderBrush(origin, origin[2] + 24, origin[2] + 44, 42, targetMaterials.ceiling)
    );
    worldBrushes.push(
      cylinderBrush(origin, origin[2] + 44, origin[2] + 60, 26, targetMaterials.ceiling)
    );
    worldBrushes.push(
      cylinderBrush(origin, origin[2] + 60, origin[2] + 72, 10, targetMaterials.metal)
    );
    stats.decorBrushes += 4;
    continue;
  } else if (model.includes("antenna")) {
    worldBrushes.push(
      cylinderBrush(origin, origin[2], origin[2] + 96, 3, targetMaterials.pipe, 6)
    );
    stats.decorBrushes++;
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
    const carOrigin = [...origin];
    carOrigin[2] -= 28;
    stockPropEntities.push(
      pointEntity("static_vehicle_europe_car-rusted", {
        origin: carOrigin.map(fmt).join(" "),
        angle: fmt(yaw),
        model: "static//vehicle_car_rusted.tik",
        scale: "1.0",
        testanim: "idle",
      })
    );
    worldBrushes.push(
      boxBrush(
        [carOrigin[0] - 70, carOrigin[1] - 32, carOrigin[2]],
        [carOrigin[0] + 70, carOrigin[1] + 32, carOrigin[2] + 42],
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
    worldBrushes.push(
      cylinderBrush(origin, origin[2], origin[2] + 44, 24, targetMaterials.wood)
    );
    stats.decorBrushes++;
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
